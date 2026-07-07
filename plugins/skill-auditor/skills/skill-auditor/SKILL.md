---
name: skill-auditor
description: This skill should be used when the user asks to "audit my skills", "review my skills", "improve my skills", "score my skills", "check skill quality", "supercharge my skills", "audit my agents", "review my subagents", or mentions evaluating skills or agents in ~/.claude or a repo's .claude directory. Performs a strictly READ-ONLY audit of all skills and agents (global and repo-local, embedded and standalone) and returns a prioritized scorecard with severity-graded findings and concrete recommendations. It does NOT modify any skill or agent until the user explicitly approves specific recommendations. Use it whenever the user wants their skills or agents evaluated, hardened, or made more reliable, even if they don't say the word "audit".
allowed-tools: Read, Grep, Glob, Bash(python3:*), Bash(python:*), Bash(gitleaks:*), Task
---

# Skill Auditor

A read-only auditor for Claude Code skills and agents. It scans every skill and
agent it can find, scores each against a weighted rubric, applies hard severity
gates, and produces a prioritized report of recommendations. It never edits
anything in Phase 1. Refactoring happens only in Phase 2, and only after the user
explicitly approves specific recommendations.

The point of this skill is to turn subjective "this skill feels weak" judgments
into a defensible, evidence-backed audit — the way a senior reviewer would grade
a junior's work: not just "make it better" but "here is exactly what is wrong,
why it matters, how severe it is, and what to change."

## The two-phase contract (non-negotiable)

**Phase 1 — Audit (read-only).** Scan, score, prioritize, report. No `Write`,
no `Edit`, no mutating `Bash`. The frontmatter deliberately withholds those
tools so an accidental edit is impossible during an audit. Output is a report
plus a numbered list of recommendations.

**Approval gate.** The user reviews the report and states which recommendations
to apply. Nothing is written before that.

**Phase 2 — Refactor (only after approval).** Implementation of approved changes
is out of scope for *this* skill's default run. When the user approves, hand off
to the `skill-creator` skill (which owns editing, snapshotting, and eval-based
before/after proof) or, if `skill-creator` is unavailable, re-enter with explicit
write permission and follow `references/refactor-workflow.md`. The inline path (auditor
re-entered with write permission) is a legitimate, common route, not a fallback of last
resort — most fixes arrive as "just fix it." Never skip the snapshot-and-measure step for
a change that makes a **trigger or execution claim**; but for a purely structural or
coherence fix that makes no such claim (a wrong path, a missing dependency file, a
mis-scoped tool grant), a lighter path is fine — apply it inline, then re-run the
deterministic scripts and the Phase-1 audit to confirm the finding closed and nothing
regressed.

If the user opens with "just fix them," still produce the Phase 1 report first
and get explicit sign-off. The report is fast and the sign-off is one message;
skipping it removes the user's control over their own configuration.

## What gets scanned

Four discovery roots plus embedded agents:

1. `~/.claude/skills/` — global skills
2. `.claude/skills/` — repo-local skills (relative to the current working directory)
3. `~/.claude/agents/` — global standalone agents
4. `.claude/agents/` — repo-local standalone agents
5. `agents/` subdirectories inside any discovered skill — embedded agents

The scan covers all of them by default. If the user scopes it ("just this repo",
"only global", "only the wissora skill"), honor that scope.

**Self-exclusion.** This skill and its own agents (`skill-auditor`,
`trigger-analyst`, `security-auditor`, `structure-analyst`, `agent-analyst`)
must be excluded from the audit so the auditor does not recursively grade itself.
`scripts/scan_targets.py` already filters these by name; do not remove that filter.

## Phase 1 workflow

### Step 1 — Discover

**Pick a working interpreter first.** Try `python3`, then `python`, then `py -3`. On
Windows a bare `python`/`python3` is often a Microsoft Store **stub** that prints an
install message and exits without running — if you see that, it is not real Python; try
the next candidate. If none runs, the deterministic scripts are unavailable: fall back to
a **semantic-only audit** (read and diff each target by hand) and **state in the report
that the scripts did not run**, so the user knows the objective backing is missing rather
than silently absent. Substitute your working interpreter for `python3` in every command
below.

**Bundled file locations.** The scripts and reference files ship with this plugin at
`$CLAUDE_PLUGIN_ROOT/scripts/` and `$CLAUDE_PLUGIN_ROOT/references/` (Claude Code sets
`$CLAUDE_PLUGIN_ROOT` to the plugin's install directory). Every `scripts/…` command and
`references/…` read below is relative to that root — resolve it there (run
`echo $CLAUDE_PLUGIN_ROOT` if you need the absolute path). If the variable is empty in
your shell, locate the plugin once with `Glob` for `**/skill-auditor*/scripts/scan_targets.py`
and use its parent directory in place of `$CLAUDE_PLUGIN_ROOT`.

Run the scanner to enumerate every target and parse its frontmatter:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/scan_targets.py" --json
```

It returns one record per target: `path`, `kind` (`skill` | `embedded_agent` |
`standalone_agent`), `scope` (`global` | `repo`), parsed frontmatter fields, body
line count, and a list of bundled resources. Records with unparseable frontmatter
are flagged, not dropped — a broken skill is exactly what the audit needs to
catch.

Read `references/scoring-rubric.md` now. It defines the dimensions, weights,
gates, and grade bands you will apply. Do not invent your own scoring; consistency
across runs is the whole value.

### Step 2 — Analyze (deterministic scripts, then inline semantic judgment)

Run the deterministic scripts first — they are near-free and do the objective,
mechanical checks, so your judgment is spent only where it is actually needed:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check_description.py" --json    # length, POV, XML tags, keyword presence
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check_structure.py" --json      # body line count, references, phantom tools
python3 "$CLAUDE_PLUGIN_ROOT/scripts/check_security.py" --json       # destructive patterns, tool grants, secrets
python3 "$CLAUDE_PLUGIN_ROOT/scripts/detect_collisions.py" --json    # trigger overlap + same-name cross-scope divergence
```

Then do the **semantic analysis inline yourself**, dimension by dimension, using
`references/scoring-rubric.md` plus `references/antipattern-checklist.md` and
`references/security-checklist.md`. **This is the default path and, for a normal
audit (up to a few dozen targets), the right one** — a single coherent pass holds
the whole picture in one context and avoids the token cost and coordination failure
modes of a multi-agent fan-out. The dimensions to judge:

- **Trigger** — description quality, keyword coverage, POV, length, and
  cross-target collisions (visible only across ALL targets at once).
- **Structure** — progressive disclosure, body size, resource organization,
  duplication, phantom tools, embedded-agent invocability, skill-vs-command fit.
- **Security** — least-privilege tool grants, destructive patterns, secret
  leakage, prompt-injection surface, network calls.
- **Agent-specific** (every agent, embedded or standalone) — system-prompt
  quality, tool-selection fit, model choice, delegation/hand-back behavior. This
  is where a "junior" agent gets its senior-level fixes surfaced.

**Optional — specialist sub-agents, for large or deep audits only.** Four agents
in `agents/` (`trigger-analyst`, `structure-analyst`, `security-auditor`,
`agent-analyst`) mirror the four dimensions above, so a big target set can be split
for parallel, context-isolated analysis. Reach for them **only** when the set is
large enough that a single context gets crowded — otherwise inline is better
(cheaper, coherent, fewer failure modes). Because this ships as a **plugin**, the
four agents are registered and spawnable via the Task/Agent tool under their
namespaced names — `skill-auditor:trigger-analyst`, `skill-auditor:structure-analyst`,
`skill-auditor:security-auditor`, and `skill-auditor:agent-analyst`. Reach for them
only when the target set is large enough to warrant the fan-out; otherwise the inline
path above is preferred, and the four agent files double as the checklist it applies.

### Step 3 — Score and gate

For each target, apply `references/scoring-rubric.md`:

1. **Gates first.** Any BLOCKER — unparseable frontmatter; `name` missing, or
   (skills) > 64 chars / not kebab-case / containing a reserved word
   (`anthropic`/`claude`); `description` missing / > 1024 chars / containing XML;
   a plaintext secret; a destructive pattern in an allowed tool without a
   guardrail — sets the grade to F regardless of the weighted score. Gates are
   pass/fail, not points. (A `name`≠directory mismatch is a MAJOR, not a gate.)
2. **Weighted score next.** Compute the 0–100 score using the dimension weights
   for the target's kind (skills and agents use different weight tables — see the
   rubric). Map to a letter grade. **Score from CONFIRMED findings only — a
   DISMISSED flag must not lower a dimension** (see the rubric's Verdict section).
   **Measured ceiling:** score Trigger and
   Execution at most 9 by inspection — the 10th point needs a measurement
   (`trigger_eval.py` / `run_loop` / `aggregate_benchmark`), which the read-only
   Phase 1 never runs. State the cap per target and *offer* the paid measurement,
   or say it is not measurable (see the Measuring section).
3. Record every finding with three attributes: a **severity** (BLOCKER / MAJOR /
   MINOR — how bad if real), a **verdict** (CONFIRMED / PLAUSIBLE / DISMISSED —
   whether it is real; see the rubric's Verdict section), and a **finding class**
   (`skill-level`, `agent-level`, `coherence-level`, or `cross-scope-level`). Every
   raw script flag must be adjudicated to a verdict — never pass one through
   unadjudicated; a DISMISSED finding carries a one-line reason (false-positive or
   not-applicable).

Cross-check findings against `references/antipattern-checklist.md` and
`references/security-checklist.md` so nothing common is missed.

### Step 4 — Report

Produce the report using the exact template in
`references/report-template.md`. Structure:

1. **Executive summary** — target counts by kind/scope, grade distribution, the
   3–5 highest-leverage fixes across the whole set.
2. **Grading table (MANDATORY, every run)** — one row per target: gate, grade,
   score, **CONFIRMED** finding counts by severity (BLK/MAJ/MIN) plus a **Dism**
   count of adjudicated-away flags, and the top *confirmed* finding. Always
   produced, even when every target is clean (all A's). The required at-a-glance
   scoreboard — never finish an audit without it.
3. **Per-target scorecards** — grade, gate status, weighted score, dimension
   breakdown, and findings sorted by severity, each tagged with its verdict
   (`[MAJOR·CONFIRMED]`, `[MAJOR·DISMISSED — reason]`). List DISMISSED flags in a
   separate "Adjudicated / dismissed" block so they never read as to-dos.
4. **Cross-cutting findings** — collisions, cross-scope duplicates, coherence
   mismatches that span more than one target.
5. **Prioritized recommendations** — a single numbered list of **CONFIRMED** (and
   PLAUSIBLE, marked "verify") findings only — never a DISMISSED one; ordered by
   leverage (severity × ease), each with: what, why it matters, the concrete
   change, and the affected file. This numbered list is what the user approves
   from.

End the report by stating plainly that nothing has been changed and asking which
numbered recommendations to apply. Do not begin Phase 2 unprompted.

## Measuring "better" (so it is not subjective)

Whenever a recommendation claims a skill or agent will trigger or perform better,
that claim should be provable, not asserted. Measurement is an **opt-in, paid step
that makes real model calls (`claude -p`) — it is NOT part of the read-only Phase-1
audit.** Two dimensions (Trigger, Execution) reach a 10 only with it (see the scoring
rubric's "measured ceiling"):

- **Trigger reliability** → run `scripts/trigger_eval.py` (shipped here, local) on a
  labeled eval set (should-trigger + hard should-not-trigger near-misses; aim ~12+8),
  each query run 3× for a stable rate; it reports the held-out trigger recall and the
  false-trigger rate. The fuller harness is `skill-creator`'s `run_loop.py`.
- **Execution reliability + cost** → `skill-creator`'s `aggregate_benchmark.py`:
  pass_rate, time, and tokens as mean ± stddev for with-skill vs. baseline, plus the
  delta. A change whose delta sits inside one standard deviation has not been shown to
  help. (No local equivalent ships here; for the unmeasurable class use the n=1 run
  below.)

**Both cost tokens.** Always run `trigger_eval.py --dry-run` first to show the call
count, and get explicit approval before the real run.

**How to offer it (to unlock a Trigger/Execution 10).** When a dimension is capped at
9 pending measurement and the skill *is* measurable, say so in the report and ask,
e.g.: *"Trigger is capped at 9 by inspection — I can run `trigger_eval.py` to measure
it (~N `claude -p` calls, costs tokens) and unlock a 10. Want me to?"* Preview the cost
with `--dry-run`, and run the real eval only on an explicit yes. If the skill is not
measurable (`disable-model-invocation` / interactive), state that instead — do not
offer a measurement that cannot run.

Recommend these measurements in the report where they apply. In Phase 2, run them
around the change to produce a real before/after, not a vibe.

**When neither harness applies — say so, don't fake a number.** Some skills cannot be
measured by these tools: a `disable-model-invocation` skill is never auto-selected, so
`run_loop` has no trigger rate to measure; an interactive, gated, GPU-bound, or otherwise
non-deterministic skill cannot be driven under `claude -p`, so `aggregate_benchmark`
cannot run it. For these, the accepted execution evidence is **one real end-to-end run
against a known-good baseline** — ideally re-running a task whose correct output you
already have — graded by hand and reported honestly as **n=1**: a real run that reproduces
or beats the baseline, explicitly not a distribution. A single honest real-world run beats
a benchmark you did not actually execute.

Note on data residency: the deterministic scripts and gitleaks run locally and
send nothing outward. `run_loop.py` and the benchmark use `claude -p` and are
subject to standard retention (Agent Skills are not covered by ZDR). For
sensitive skills, rely on the local scripts and use the eval loop deliberately.

## Reference files

Read these as needed; do not inline their content into the report.

- `references/scoring-rubric.md` — dimensions, weights (separate tables for
  skills and agents), gates, grade bands. Read in Step 1.
- `references/antipattern-checklist.md` — trigger, structure, security, and
  misclassification antipatterns to check each target against.
- `references/security-checklist.md` — deterministic + semantic security checks.
- `references/report-template.md` — the exact output structure for Phase 1.
- `references/refactor-workflow.md` — the Phase 2 procedure, used only after the
  user approves specific recommendations.

## Scripts

The discovery/analysis scripts accept `--root` (repeatable) to override discovery
roots and `--json` for machine-readable output. With no arguments they scan the four
default roots plus embedded agents. They are **read-only — except `trigger_eval.py`**,
which makes real model calls (see below) and is never run during a Phase-1 audit.

- `scripts/scan_targets.py` — discovery + frontmatter parsing + self-exclusion.
- `scripts/check_description.py` — description length, POV, XML tags, trigger
  keywords, name conventions.
- `scripts/check_structure.py` — body line count, resource references, phantom
  tools, duplication signals.
- `scripts/check_security.py` — tool-grant least-privilege, destructive command
  patterns, secret scan (delegates to gitleaks if present, falls back to regex).
- `scripts/detect_collisions.py` — two checks: pairwise description overlap
  (`collisions`) to surface trigger/delegation competition, AND same-name
  cross-scope divergence (`name_conflicts`) — a name present in more than one
  location whose copies have drifted apart. The second is independent of the
  overlap threshold on purpose: divergence *lowers* description similarity, so
  the overlap check misses exactly the dangerous case (same name, two different
  bodies, undefined which one runs).
- `scripts/trigger_eval.py` — **OPT-IN, COSTS TOKENS, not read-only.** Measures a
  skill's trigger reliability via `claude -p` against a labeled eval set (see the
  Measuring section); run `--dry-run` first to preview the call count. This is the
  only script that leaves the read-only boundary; never run it during a Phase-1 audit.

### JSON output shapes

The envelope key differs by script — read the right one:

- `scan_targets.py` → `{"count", "targets": [{name, dir_name, kind, scope, path,
  frontmatter, body_lines, parse_error, resources}]}`.
- `check_description.py` / `check_structure.py` / `check_security.py` →
  `{"results": [{name, kind, scope, …, "findings": [[SEVERITY, message], …]}]}`;
  a clean target has `"findings": []`.
- `detect_collisions.py` → `{"threshold", "collisions": [...],
  "name_conflicts": [{name, type, severity, body_similarity, differs_in, …}]}`.
