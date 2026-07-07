#!/usr/bin/env python3
"""OPT-IN trigger-reliability eval for skill-auditor. COSTS TOKENS.

This is the ONLY skill-auditor script that makes real model calls (via `claude
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


def judge_prompt(name: str, desc: str, query: str) -> str:
    return (
        "You decide whether a Claude Code skill should handle a user's message.\n"
        f"SKILL name: {name}\n"
        f"SKILL description: {desc}\n\n"
        f"USER MESSAGE: {query}\n\n"
        "Should this skill be invoked to handle this message? "
        "Answer with exactly one word: YES or NO."
    )


def call_claude(prompt: str, model: str | None) -> str:
    cmd = ["claude", "-p"]
    if model:
        cmd += ["--model", model]
    cmd += [prompt]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    except (subprocess.SubprocessError, OSError) as e:
        return f"ERR:{e}"
    out = (proc.stdout or "").strip().upper()
    head = out[:20]
    if "YES" in head:
        return "YES"
    if "NO" in head:
        return "NO"
    return "?"


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

    name, desc = read_skill(args.skill)
    queries = json.loads(Path(args.eval_set).read_text(encoding="utf-8"))["queries"]
    n_calls = len(queries) * args.repeats

    print(f"Skill: {name}")
    print(f"Eval set: {len(queries)} queries x {args.repeats} repeats = {n_calls} `claude -p` calls")
    print("WARNING: this makes real model calls and COSTS TOKENS (each call is one short judge")
    print("         prompt; not ZDR-covered). This is not part of the read-only audit.")
    if args.dry_run:
        print("[dry-run] no calls made. Re-run without --dry-run to execute.")
        return
    if not shutil.which("claude"):
        print("ERROR: the `claude` CLI is not on PATH; cannot run the eval in this environment.")
        sys.exit(2)

    tp = fp = tn = fn = 0
    for item in queries:
        q, expect = item["q"], item.get("expect", "trigger")
        votes = [call_claude(judge_prompt(name, desc, q), args.model) for _ in range(args.repeats)]
        fired = votes.count("YES") > args.repeats / 2
        if expect == "trigger":
            tp += fired
            fn += (not fired)
        else:
            fp += fired
            tn += (not fired)
        print(f"  [{'FIRED' if fired else 'no   '}] expect={expect:10} {q[:60]}")

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
