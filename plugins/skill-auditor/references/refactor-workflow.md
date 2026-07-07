# Refactor Workflow (Phase 2)

This runs **only** after the user has reviewed the Phase 1 report and approved
specific numbered recommendations. If you are not certain the user approved a
given change, do not make it.

The auditor's own frontmatter withholds `Write`/`Edit`. Phase 2 therefore does not
run inside a normal auditor invocation. Prefer handing off to `skill-creator` when a
change makes a **trigger or execution claim** that needs a measured before/after.
For structural or coherence fixes that make no such claim (a wrong path, a missing
dependency file, a mis-scoped tool grant, a divergent duplicate), applying the
approved changes **inline** — the auditor re-entered with write permission — and
verifying with the deterministic scripts plus a re-run of the Phase-1 audit is a
legitimate, lighter route, not a fallback of last resort. Either way, only touch
what the user approved.

## Principle: never change without measuring

An improvement you cannot measure is a guess. Every approved change that claims a
triggering or execution benefit must be bracketed by a before/after measurement.
This is the difference between "I rewrote the description" and "the held-out
trigger rate went from 0.62 to 0.94."

## Steps

1. **Snapshot first.** Before editing anything, copy the target so a real
   baseline exists:
   ```bash
   cp -r <target-path> <workspace>/snapshot/<target-name>/
   ```
   The snapshot is the "before" for the benchmark and the rollback if the change
   regresses.

2. **Apply one approved recommendation at a time.** Atomic changes keep the
   measurement attributable. If you batch five edits and the score moves, you
   don't know which edit did it.

3. **Measure triggering** (for description/name changes) with skill-creator's
   loop:
   ```bash
   python -m scripts.run_loop \
     --eval-set <trigger-eval.json> \
     --skill-path <target-path> \
     --model <current-session-model-id> \
     --max-iterations 5 --verbose
   ```
   Use the model ID of the current session so the test matches real behavior.
   The number that counts is the held-out **test** trigger rate, not train.

4. **Measure execution + cost** (for body/logic changes) with skill-creator's
   benchmark: run the test prompts with the new version and against the snapshot
   baseline, grade, then:
   ```bash
   python -m scripts.aggregate_benchmark <workspace>/iteration-N --skill-name <name>
   ```
   Report pass_rate, time, and tokens as mean ± stddev for both, plus the delta.

5. **Judge the delta honestly.** If the improvement sits inside one standard
   deviation of the baseline, it has not been shown to help — say so rather than
   claiming a win. High stddev means the eval or the instructions are flaky;
   tighten the instructions or add examples rather than piling on features.

6. **Show before/after and get confirmation** before moving to the next
   recommendation. The user stays in control of their own configuration.

7. **Re-run the Phase 1 audit** on the changed targets at the end to confirm the
   fix closed the finding and introduced no new ones.

## Scope discipline

- Do not "improve" things the user did not approve, even if you spot them mid-edit.
  Add them to a fresh recommendation list instead.
- Do not add domain knowledge the target didn't have and the user didn't supply.
  The auditor can fix craft (triggering, structure, guardrails, model choice); it
  cannot invent senior-level domain judgment out of nothing. Where a target is
  thin on real expertise, the recommendation is to source that expertise (docs,
  standards, reference repos), not to fabricate it.
- Preserve names and directory names exactly; a rename breaks references and
  installed paths.
- **Editing a tool grant can trip the harness's self-modification guard.** A change
  to an `allowed-tools`/`tools` line reads as a privilege grant to the auto-mode
  classifier and may be blocked mid-edit. Make it **minimal-delta** — change only
  what the finding requires and keep the existing tool patterns verbatim (e.g. fix a
  list delimiter without rewriting the entries) — or run outside auto mode so the
  user can review the permission change. Do not work around the block; surface it.
