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

Applies to plugin config components (hooks, monitors, MCP/LSP servers, commands,
settings) — any one forces the component (and the plugin that ships it) to **F**.
These are the deterministic gates the `check_hooks.py` / `check_mcp.py` /
`check_manifest.py` scripts emit; each still passes through verdict adjudication.

- **Hook / monitor / command `!`-block**: fetch-and-execute (`curl … | bash`),
  reverse shell, credential-path read + network egress, `ANTHROPIC_BASE_URL` /
  API-key override, or a destructive pattern in the command. A `SessionStart`/
  `Setup` hook with a network side effect (the CVE-2025-59536 pre-trust class) is
  a gate on sight.
- **Command**: `$ARGUMENTS`/`$N` interpolated into a `` !`…` `` shell block without a
  provable constraint (command injection, CWE-78).
- **MCP / LSP server**: plaintext secret in `env`/`headers` of a committed config
  (MCP01); fetch-and-execute as the launch command (MCP05).
- **Settings**: `defaultMode: bypassPermissions`/auto in a shared or plugin config;
  `ANTHROPIC_BASE_URL`/key redirect in `env`; a plaintext secret; an over-broad
  `allow` grant that green-lights a destructive pattern.
- **Manifest**: a hard load error (e.g. `keywords` not an array); a plaintext secret
  in the manifest.

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

### Config-component kinds (plugins and their surface)

Hooks, monitors, MCP/LSP servers, and settings are not instruction-authoring
artifacts like skills and agents — they are *configuration*, graded almost entirely
on **security posture and least-privilege**, not on trigger or prose quality. They
are gate-dominated: most of the score is pass/fail, and a clean component is simply
one with no confirmed findings. A **command** is the exception — it *is* a skill
(officially merged), so it uses the skills table above **plus** the command gates.

| Kind | Dimension | Weight | What it measures |
|------|-----------|--------|------------------|
| **hook / monitor** | Guardrails / no-dangerous-pattern | 60% | none of the gate patterns; command is not fetch-and-execute / reverse-shell / credential-egress |
| | Least-privilege scope | 25% | narrow matcher; exec-form over shell-form; no `async` persistence; scoped `if` not relied on |
| | Hygiene | 15% | `timeout` set; http handler constrained by `allowedHttpHookUrls`/`httpHookAllowedEnvVars` |
| **mcp_server / lsp_server** | Secrets & execution safety | 50% | no plaintext secret in `env`/`headers`; not fetch-and-execute |
| | Supply-chain pinning | 30% | pinned version, not `@latest`/`-y`-unpinned (rug-pull surface) |
| | Least-privilege & transport | 20% | `https://` not `http://`; scoped filesystem/db roots; provenance known |
| **plugin (container)** | Manifest hygiene | 30% | valid `name`, `version` pinned, `keywords` typed, passes `validate --strict` |
| | Provenance | 30% | trusted source; pinned `dependencies`; `defaultEnabled:false` when it bundles risky surface |
| | Aggregate component safety | 40% | the plugin inherits the **worst grade among its components** — one BLOCKER child fails the plugin |
| **settings** | Permission/env posture | 100% | no bypass mode in shared config; no credential/base-URL redirect; least-privilege `allow`/`deny`; scoped `additionalDirectories` |

**Scoring these:** start at 10 per dimension and subtract for each CONFIRMED finding
(BLOCKER → gate to F; MAJOR → −3 to −5; MINOR → −1). A component with no findings
scores 10s and grades A. The **measured ceiling does not apply** — these are not
trigger/execution dimensions, so a clean config component *can* earn a 10 by
inspection. The plugin container's "aggregate component safety" is mechanical: take
the minimum grade across every hook, MCP server, monitor, LSP server, command, and
skill/agent the plugin ships.

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

## Verdict (adjudication status) — the second axis

Severity says *how bad a finding is if real*. Verdict says *whether it is real*. They
are independent: the deterministic scripts raise **suspects**; the model's adjudication
decides which are **defects**. Every finding carries exactly one verdict.

- **CONFIRMED** — adjudicated a real defect on inspection. Counts against the grade and
  appears in the recommendations.
- **PLAUSIBLE** — looks real but rests on a check Phase-1 cannot perform (a runtime test,
  a measurement, a packaging behavior). Appears in recommendations marked "verify"; weigh
  it into the grade cautiously, never as if confirmed.
- **DISMISSED** — a raw script flag cleared on inspection. **Requires a one-line reason**
  of one of two kinds: *false-positive* (the flag is wrong — e.g. a destructive-pattern
  string that is the detector's own pattern list) or *not-applicable* (technically true
  but does not govern this target — e.g. missing WHEN phrasing on a delegation-only agent
  whose selection is name-driven, not description-driven). A DISMISSED finding **never
  moves the grade and never becomes a recommendation.**

**Grade rule.** Compute dimension scores and the letter grade from **CONFIRMED** findings
(and PLAUSIBLE ones, weighed cautiously) only. A DISMISSED flag must not pull a dimension
down: if a raw script MAJOR is dismissed, the dimension is scored as if it were never
raised. This is what stops a cleared flag from silently lowering a grade — or its removal
from silently raising one.

## Finding classes

Tag each finding with the level it lives at, so the report can group cross-cutting
issues separately from single-target ones:

- `skill-level` — a property of one skill.
- `agent-level` — a property of one agent (embedded or standalone).
- `surface-level` — a property of one plugin surface component: a hook, monitor,
  MCP/LSP server, command, or settings posture.
- `plugin-level` — a property of the plugin container: manifest hygiene, provenance,
  or the aggregate safety of everything it bundles.
- `coherence-level` — a mismatch between a skill and its embedded agent (e.g. the
  skill promises a capability the embedded agent lacks the tools to perform), or
  between a plugin's manifest and what it actually ships.
- `cross-scope-level` — the same skill/agent exists in both global and repo scope
  with diverging content, or two agents have overlapping descriptions that
  compete for the same delegation.

## Calibration note

If too many targets land on the same grade, the ranking has lost its usefulness.
When that happens, lean on the raw 0–100 score and the severity-weighted count of
findings to force a distribution, and say so in the report. The goal is an
actionable ordering, not a flat "everything is a B."
