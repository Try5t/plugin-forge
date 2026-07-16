#!/usr/bin/env python3
"""OPT-IN trigger-reliability eval for config-auditor. COSTS TOKENS.

This is the ONLY config-auditor script that makes real model calls (via `claude
-p`). It is NOT part of the read-only Phase-1 audit; run it deliberately, only on
explicit approval, and always show the cost first. It measures how reliably a
skill's DESCRIPTION selects it: for a labeled set of queries (should-trigger plus
hard should-not-trigger near-misses), it asks the model per query whether the
skill should handle it, then reports the held-out trigger recall, the
false-trigger rate, and a suggested measured Trigger-dimension score (which is
what unlocks a 10 that inspection alone caps at 9).

Honesty note: this is a single-skill JUDGE approximation (does the description
make the model say "this handles it" for real cases and "no" for near-misses). It
does NOT reproduce full multi-skill competition. Treat the number as evidence,
not proof. For the fuller harness see skill-creator's run_loop.

Usage:
  # 1) Preview the cost first (makes NO model calls):
  python trigger_eval.py --skill <path/SKILL.md> --eval-set <queries.json> --dry-run
  # 2) Run it (makes queries x repeats `claude -p` calls, COSTS TOKENS):
  python trigger_eval.py --skill <path/SKILL.md> --eval-set <queries.json> --repeats 3

eval-set JSON:
  {"queries": [
     {"q": "log a bug for the crash on save", "expect": "trigger"},
     {"q": "create a user story for search",   "expect": "no-trigger"}
  ]}
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import scan_targets  # reuse the (fixed) frontmatter parser


def read_skill(path: str):
    fm, _, err = scan_targets.parse_frontmatter(Path(path))
    if err:
        print(f"WARNING: frontmatter parse issue on {path}: {err}", file=sys.stderr)
    return fm.get("name", Path(path).parent.name), fm.get("description", "")


def judge_prompt(desc: str, query: str) -> str:
    # Framed as classifying inert example text (not "should YOU handle this"): the
    # full `claude -p` agent otherwise either tries to ACT on the message or reasons
    # about its OWN installed skills, instead of judging the description we pass in.
    # Asking for one sentence of reasoning then an explicit VERDICT tag makes the
    # answer both reliable and machine-parseable.
    return (
        "Below is a skill description and one example user message. Decide whether a\n"
        "router should select this skill for that message, based only on the description.\n\n"
        f"--- skill description ---\n{desc}\n--- end ---\n\n"
        f"example user message: {query!r}\n\n"
        "Reason in one sentence, then end with exactly 'VERDICT: YES' or 'VERDICT: NO'."
    )


def call_claude(prompt: str, model: str | None) -> str:
    # Resolve the executable so the exec-form subprocess works on Windows too
    # (where `claude` is a `.cmd`/npm shim that a bare "claude" arg won't find).
    exe = shutil.which("claude") or "claude"
    cmd = [exe, "-p"]
    if model:
        cmd += ["--model", model]
    # Deliver the prompt on STDIN, not as a positional arg. `claude -p "<prompt>"`
    # does NOT reliably hand an argv prompt to the model in a piped subprocess — the
    # model receives no message ("I don't see a request") and every judgment comes
    # back unparseable. Piping on stdin delivers it deterministically.
    try:
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=180)
    except (subprocess.SubprocessError, OSError) as e:
        return f"ERR:{e}"
    # A failed call (non-zero exit: auth error, rate limit, etc.) is NOT a "no"
    # judgment — it is missing evidence. Surface it as ERR so the run aborts
    # rather than silently scoring every failure as not-triggered.
    if proc.returncode != 0:
        first = ((proc.stderr or proc.stdout or "").strip().splitlines() or ["exit " + str(proc.returncode)])[0]
        return f"ERR:{first[:90]}"
    out = (proc.stdout or "").strip().upper()
    # Take the LAST `VERDICT: YES|NO` so the final verdict wins over any YES/NO used
    # mid-reasoning. A reply with NO parseable verdict is MISSING EVIDENCE, not a
    # "no" — return ERR so the abort guards fire instead of silently scoring it as
    # not-triggered (which is exactly how the old code fabricated a score).
    verdicts = re.findall(r"VERDICT:\s*(YES|NO)", out)
    if verdicts:
        return verdicts[-1]
    head = out[:60].replace("\n", " ")
    return f"ERR:unparseable judge reply (no VERDICT): {head}"


# Each `claude -p` call is a FRESH CLI session: the full Claude Code system
# prompt + tool definitions are re-sent every time, cold, with no cache reuse
# across calls. That fixed overhead — not our short judge prompt — dominates the
# bill. The figure is an order-of-magnitude estimate, not a measurement; it moves
# with the CLI version and the installed plugin/MCP surface.
SESSION_OVERHEAD_TOKENS = 15_000
VERDICT_REPLY_TOKENS = 50          # "one sentence + VERDICT: YES|NO"
CHARS_PER_TOKEN = 4                # crude but adequate for a preview

# USD per million tokens (input, output, footnote marker).
PRICING = {
    "claude-opus-4-8":  (5.00, 25.00, ""),
    "claude-sonnet-5":  (2.00, 10.00, "*"),   # intro pricing through 2026-08-31
    "claude-haiku-4-5": (1.00, 5.00, ""),
}
SONNET_NOTE = ("* Sonnet 5 introductory pricing, through 2026-08-31; "
               "list price after that is $3.00/$15.00.")


def cost_preview(name: str, desc: str, queries: list, repeats: int, model: str | None) -> None:
    """Print what the real run would actually cost, in tokens and dollars."""
    n_calls = len(queries) * repeats
    avg_prompt_chars = sum(len(judge_prompt(desc, q["q"])) for q in queries) / len(queries)
    prompt_tok = round(avg_prompt_chars / CHARS_PER_TOKEN)
    in_per_call = SESSION_OVERHEAD_TOKENS + prompt_tok
    total_in = in_per_call * n_calls
    total_out = VERDICT_REPLY_TOKENS * n_calls

    print(f"Skill:    {name}")
    print(f"Eval set: {len(queries)} queries x {repeats} repeats = {n_calls} `claude -p` calls")
    print(f"Model:    {model or 'whatever the CLI is configured to use (pass --model to pin one)'}")
    print()
    print("Per call — every call is a fresh `claude -p` session, so the CLI's own")
    print("system prompt and tool definitions are re-sent cold each time:")
    print(f"  {'session overhead (system prompt + tools)':<40} ~{SESSION_OVERHEAD_TOKENS:>9,} tok in")
    print(f"  {'judge prompt (description + one query)':<40} ~{prompt_tok:>9,} tok in")
    print(f"  {'verdict reply':<40} ~{VERDICT_REPLY_TOKENS:>9,} tok out")
    print(f"  {f'x {n_calls} calls':<40} ~{total_in:>9,} tok in")
    print(f"  {'':<40} ~{total_out:>9,} tok out")
    print()
    print("Estimated cost of one full run, at API list price:")
    w = (20, 11, 12, 10)
    print("  ┌" + "┬".join("─" * n for n in w) + "┐")
    print(f"  │ {'model':<19}│ in $/MTok │ out $/MTok │ est. run │")
    print("  ├" + "┼".join("─" * n for n in w) + "┤")
    for mid, (pin, pout, mark) in PRICING.items():
        cost = total_in / 1e6 * pin + total_out / 1e6 * pout
        sel = "→ " if model == mid else "  "
        print(f"  │ {sel}{mid:<16} │ {pin:>8.2f}{mark:<1} │ {pout:>9.2f}{mark:<1} │ ${cost:>7.2f} │")
    print("  └" + "┴".join("─" * n for n in w) + "┘")
    print(f"  {SONNET_NOTE}")
    print()
    print("  Token counts are estimates (the session overhead is not measured and")
    print("  moves with your CLI version and installed plugins) — use them to size")
    print("  the run, not to reconcile a bill.")
    print()
    print("  The dollar figures apply ONLY if `claude` is authenticated with an API")
    print("  key. On a Claude subscription (Pro/Max) you are billed nothing here —")
    print(f"  instead these {n_calls} calls count against your plan's 5-hour and weekly")
    print("  usage limits, on top of whatever this terminal is already spending. A")
    print("  full run is a large burst of cold-context sessions and can exhaust the")
    print("  5-hour window; start it when being rate-limited for a while is OK, or")
    print("  lower --repeats to shrink it.")


def suggested_score(recall: float, false_rate: float, acc: float):
    if recall != recall or false_rate != false_rate:  # NaN guard
        return None
    if recall >= 0.95 and false_rate <= 0.05:
        return 10.0
    return round(10 * acc, 1)


def main():
    ap = argparse.ArgumentParser(description="Opt-in trigger-reliability eval (COSTS TOKENS).")
    ap.add_argument("--skill", required=True, help="Path to the skill's SKILL.md.")
    ap.add_argument("--eval-set", required=True, help="Path to the labeled queries JSON.")
    ap.add_argument("--repeats", type=int, default=3, help="Calls per query (majority vote).")
    ap.add_argument("--model", default=None, help="Model id passed to `claude -p`.")
    ap.add_argument("--dry-run", action="store_true", help="Preview cost only; make NO calls.")
    args = ap.parse_args()

    # The preview draws a box-drawing table; a legacy Windows console defaults to
    # cp1252 and would raise UnicodeEncodeError on it.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    name, desc = read_skill(args.skill)
    queries = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))["queries"]
    n_calls = len(queries) * args.repeats

    cost_preview(name, desc, queries, args.repeats, args.model)
    print()
    print("WARNING: the real run makes real model calls and COSTS TOKENS (not ZDR-covered).")
    print("         This is not part of the read-only audit.")
    if args.dry_run:
        print("[dry-run] no calls made. Re-run without --dry-run to execute.")
        return
    if not shutil.which("claude"):
        print("ERROR: the `claude` CLI is not on PATH; cannot run the eval in this environment.")
        sys.exit(2)

    tp = fp = tn = fn = n_err = 0
    first_err = None
    for i, item in enumerate(queries):
        q, expect = item["q"], item.get("expect", "trigger")
        votes = [call_claude(judge_prompt(desc, q), args.model) for _ in range(args.repeats)]
        errs = [v for v in votes if v.startswith("ERR")]
        n_err += len(errs)
        if errs and first_err is None:
            first_err = errs[0]
        # Fail fast: if the very first query cannot be evaluated at all, the
        # environment is broken (auth/rate limit) — abort before burning the rest.
        if i == 0 and len(errs) == args.repeats:
            print(f"\nABORTED after 1 query: every call failed ({first_err}).", file=sys.stderr)
            print("The `claude -p` calls cannot run in this environment, so no trigger", file=sys.stderr)
            print("measurement is possible. NOT emitting a score (an evidence tool must not", file=sys.stderr)
            print("fabricate a number from failed calls). Trigger stays capped at 9 by inspection.", file=sys.stderr)
            sys.exit(3)
        fired = votes.count("YES") > args.repeats / 2
        if expect == "trigger":
            tp += fired
            fn += (not fired)
        else:
            fp += fired
            tn += (not fired)
        print(f"  [{'FIRED' if fired else 'no   '}] expect={expect:10} {q[:60]}")

    # Any errors at all invalidate the rate — refuse to emit a score.
    if n_err:
        print(f"\nABORTED: {n_err}/{n_calls} calls failed (e.g. {first_err}).", file=sys.stderr)
        print("Cannot produce a reliable trigger measurement with failed calls — NOT emitting", file=sys.stderr)
        print("a score. Fix the environment (auth/rate limit) and re-run, or keep Trigger at 9.", file=sys.stderr)
        sys.exit(3)

    trig, nono = tp + fn, fp + tn
    recall = tp / trig if trig else float("nan")
    false_rate = fp / nono if nono else float("nan")
    acc = (tp + tn) / (trig + nono) if (trig + nono) else float("nan")

    print(f"\nTrigger recall (should-trigger that fired): {recall:.2f} ({tp}/{trig})")
    print(f"False-trigger rate (should-not that fired): {false_rate:.2f} ({fp}/{nono})")
    print(f"Overall accuracy: {acc:.2f}")
    score = suggested_score(recall, false_rate, acc)
    print(f"Suggested measured Trigger-dimension score: {score}/10 "
          "(a 10 needs high recall AND near-zero false-trigger)")
    print("NOTE: single-skill judge approximation, not full multi-skill selection. Evidence, not proof.")


if __name__ == "__main__":
    main()
