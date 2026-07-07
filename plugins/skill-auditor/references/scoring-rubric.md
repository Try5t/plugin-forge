# Scoring Rubric

The auditor scores every target in two stages: hard **gates** first (pass/fail),
then a **weighted 0–100 score** mapped to a letter grade. Gates protect against
the failures that no amount of polish can offset (a leaked secret, a skill that
cannot load). The weighted score ranks everything else by quality.

Skills and agents share most dimensions but weight them differently and add a few
of their own. Use the table that matches the target's `kind`.

## Stage 1 — Gates (BLOCKER → grade F)

A target that trips any gate is graded **F** regardless of its weighted score,
and the corresponding finding is labeled BLOCKER. Gates are deliberately tuned
to accept false positives over false negatives on safety: better to flag a safe
skill than to pass a dangerous one.

Applies to skills and agents:

- Frontmatter is missing or does not parse as YAML.
- `name` missing or empty. For **skills** additionally: > 64 characters, not
  kebab-case, or containing a reserved word (`anthropic`/`claude`) — all
  documented in the Skill frontmatter spec. For **agents** these are convention,
  not gates (the SDK docs specify no `name` constraint) → treat as MAJOR, not F.
  (A `name`≠directory mismatch is a MAJOR convention issue, not a gate — the
  official example uses `name: pdf-processing` in a `pdf/` directory.)
- `description` missing, empty, or > 1024 characters.
- `description` contains XML/HTML tags.
- A plaintext secret appears in the body or any bundled script (gitleaks hit, or
  regex fallback hit).
- An `allowed-tools` grant includes a destructive command pattern (`rm -rf`,
  `dd if=`, `mkfs`, `chmod -R 777`, fork bomb) without an explicit narrowing
  guardrail.

Applies to agents additionally:

- A "judgment" role (review, security, architecture, planning) is pinned to a
  weak/cheap model, or a trivial mechanical role is pinned to the most expensive
  model — a clear misconfiguration. Flag as BLOCKER only when the mismatch is
  unambiguous; otherwise treat as a MAJOR model-choice finding.

## Stage 2 — Weighted dimensions

Each dimension is scored 0–10 by the responsible subagent (or inline), backed by
the deterministic scripts where they apply. Multiply by the weight, sum, and
scale to 100.

### Skills weight table

| # | Dimension | Weight | What it measures |
|---|-----------|--------|------------------|
| 1 | Trigger reliability | 30% | Third-person keyword-rich description; WHAT + WHEN + keywords present; key use case front-loaded for human-listing discoverability (the model receives the full description for triggering, so length is not a trigger limit; official max is 1024 chars); no collisions with other targets; measurable held-out trigger rate (run_loop) when available |
| 2 | Structure / maintainability | 25% | SKILL.md body under ~500 lines (ideally <300); progressive disclosure used; references organized and actually referenced; no body↔reference duplication; versioned; imperative voice |
| 3 | Security / guardrails | 25% | `allowed-tools` present and least-privilege; no destructive/injection patterns; no unnecessary secret reads; network calls justified |
| 4 | Execution reliability | 20% | pass_rate (mean ± stddev) with-skill vs. baseline and its delta when measured; self-containment (scripts exist and run, no phantom tools); a single clear default path |

Skill modifiers (adjust the final score up or down, do not double-count):

- **Novelty / validity** (−): if the skill mostly restates what the base model
  already does, cap the score — a skill with no marginal value can even hurt.
- **Skill-vs-command fit** (±): a situational/destructive one-off that should be
  `disable-model-invocation: true` but isn't, loses points; a genuine reusable
  capability gains nothing extra (it's the baseline expectation).
- **Cost efficiency** (−): excessive token/time per task relative to what the
  skill delivers.

### Measured ceiling — Trigger and Execution cap at 9 by inspection

Two dimensions reward *empirical proof*, not just a clean read, so **inspection
alone caps them at 9**; the 10th point (and thus a 100 overall) is unlocked only by
running a measurement:

- **Trigger** (skills 30% / agents 25%) — the top point needs a **measured held-out
  trigger rate**, not "the description looks discriminating". Unlock it with the
  local `scripts/trigger_eval.py` (opt-in, **costs tokens**) or skill-creator's
  `run_loop`.
- **Execution** (skills 20%) — the top point needs a **measured pass_rate vs.
  baseline** (skill-creator's `aggregate_benchmark`) or, for the unmeasurable class,
  one graded real end-to-end run that beats a known baseline (n=1).

**Not measurable at all** for a `disable-model-invocation` skill (never
auto-selected → no trigger rate) or an interactive/gated/GPU-bound skill (cannot be
driven under `claude -p`). There the 10 is honestly out of reach; score the
inspectable parts and **say so** — do not imply a 10 that cannot be earned.

The auditor must **name this cap in every report**: a dimension at 9 "pending
measurement, run `trigger_eval.py` to unlock 10" is different from a 9 that was
earned, and the reader deserves to know which. Measurement is never run during the
read-only Phase-1 audit — it is offered, and only run on explicit approval.

### Agents weight table

| # | Dimension | Weight | What it measures |
|---|-----------|--------|------------------|
| 1 | Trigger / selection reliability | 25% | Description makes the agent selectable for the right delegations; no collision with sibling agents; clear role boundary |
| 2 | System-prompt quality | 25% | Clear, imperative, self-consistent; correct scope; no contradictory instructions; states its hand-back contract |
| 3 | Tool selection fit | 20% | Toolset matches the role (least-privilege); nothing superfluous, nothing missing for the stated job |
| 4 | Model choice | 15% | Judgment work on a capable model, mechanical work on a cheap one; `inherit` used when appropriate |
| 5 | Delegation / hand-back behavior | 15% | Reports cleanly to the caller; context isolation set sensibly; does not silently swallow results |

## Stage 3 — Grade bands

Map the weighted 0–100 score to a letter, then apply the gate override.

| Score | Grade |
|-------|-------|
| 90–100 | A |
| 80–89 | B |
| 70–79 | C |
| 60–69 | D |
| < 60 | F |

Gate override: any BLOCKER forces **F** even if the weighted score is higher.

Report both the letter grade (for the ship/keep decision) and the raw 0–100
score (for ranking targets against each other so the user knows what to fix
first).

## Severity labels for findings

Every finding carries one severity, independent of the target's overall grade:

- **BLOCKER** — trips a Stage-1 gate. Must be fixed before the target is trusted.
- **MAJOR** — materially degrades one of the weighted dimensions (e.g. vague
  description that measurably undertriggering, missing least-privilege, oversized
  body forcing context bloat). Should be fixed.
- **MINOR** — polish; improves quality but never gates a grade (e.g. missing
  version field, a reference file without a table of contents).

## Finding classes

Tag each finding with the level it lives at, so the report can group cross-cutting
issues separately from single-target ones:

- `skill-level` — a property of one skill.
- `agent-level` — a property of one agent (embedded or standalone).
- `coherence-level` — a mismatch between a skill and its embedded agent (e.g. the
  skill promises a capability the embedded agent lacks the tools to perform).
- `cross-scope-level` — the same skill/agent exists in both global and repo scope
  with diverging content, or two agents have overlapping descriptions that
  compete for the same delegation.

## Calibration note

If too many targets land on the same grade, the ranking has lost its usefulness.
When that happens, lean on the raw 0–100 score and the severity-weighted count of
findings to force a distribution, and say so in the report. The goal is an
actionable ordering, not a flat "everything is a B."
