# config-auditor — Changelog

## 1.1.0 — 2026-07-07

Verdict axis: every finding is now tagged CONFIRMED / PLAUSIBLE / DISMISSED alongside
its severity. The letter grade and the recommendation list are computed from CONFIRMED
(and cautiously PLAUSIBLE) findings only; DISMISSED flags — raw script false-positives
or not-applicable-in-context — are shown separately with a one-line reason and never
move the grade or become a to-do. The grading table gains a **Dism** column. Docs-only;
no script changes.

## Update — 2026-07-05

Drop-in update for `~/.claude/skills/config-auditor/`. Read-only analysis skill; no
runtime dependencies (no PyYAML needed). After copying the files in, restart Claude
Code. On Windows, run the scripts with `py -3` if a bare `python`/`python3` resolves
to the Microsoft Store stub.

> **If you have the "Fix config-auditor frontmatter/path parsing bugs" task open:**
> both bugs it describes (the folded-scalar YAML parser and the Windows
> path-separator false positives) are **already fixed in this version** — you can
> dismiss that task and use these files.

---

### Bug fixes (correctness)

- **Folded / block YAML scalars are parsed correctly.** `scan_targets.py`'s
  frontmatter parser now treats any indented line under a key as a continuation of
  that key's value (folded text, `>-`/`|`/`>` block scalars, or list items) — even
  when it contains an internal colon. Previously a multi-line folded `description:`
  with internal colons was split into spurious extra keys **and** truncated, which
  also caused the real **> 1024-character length gate to be missed** (a false
  negative). Also strips the block-scalar indicator so the measured length is the
  real length.
- **Windows path separators no longer produce false findings.** `list_resources`
  now normalizes `\` to `/`, so a bundled resource (`references\notes.md`) matches
  a forward-slash markdown link (`references/notes.md`) in the body. Fixes false
  "unreferenced resource", false "phantom tool", and mis-scoped large-reference
  findings on Windows.
- **Text-mode output is ASCII-safe.** Removed non-ASCII characters (an arrow, em
  dashes) from script *output* strings that crashed `--text`-mode printing on a
  Windows `cp1252` console. All five scripts now run in text mode on Windows.

### Grounding corrections (claims verified against the official docs)

The auditor previously asserted some limits as hard facts. Each was checked against
the official Claude Code / Agent Skills documentation and corrected:

- **The "~250-char cutoff" is a display heuristic, not a triggering limit.** The
  model receives the **full** description for skill selection (confirmed in the
  docs), so description length does **not** gate triggering. The ~250 figure is a
  secondary-source estimate for the *human* skill-listing display only. Reworded
  everywhere; still a MINOR discoverability nudge (front-load the key use case).
- **`name` ≠ directory downgraded from BLOCKER (grade F) to MAJOR.** Matching the
  directory is a convention, not a documented hard requirement — the official
  example uses `name: pdf-processing` in a `pdf/` directory. Still worth flagging
  (Claude Code addresses a skill by its folder name), just not an F.
- **`name` length (64) and kebab-case: BLOCKER for skills, MAJOR for agents.** Both
  are documented for skills; the SDK docs specify no `name` constraint for
  subagents, so there they are convention.
- **New gate: reserved words in a skill name.** `anthropic`/`claude` in a skill
  `name` is a documented hard constraint → BLOCKER (was not checked before).
- **`description` > 1024 and XML tags in `description`** confirmed as real,
  documented gates (unchanged; now sourced in comments).
- Soft heuristics (`description < 40`, body `500`/`300` lines, the `0.35` collision
  threshold) are now labeled as heuristics in the code, not implied limits.

### New checks

- **Embedded-agent invocability (`check_structure.py`).** Flags a skill that
  bundles agents in an `agents/` subdirectory but is **not** a plugin
  (`.claude-plugin/plugin.json`) and whose agents are **not** also in
  `~/.claude/agents/`. Claude Code loads agents only from `~/.claude/agents/` or a
  plugin, so such embedded agents cannot be spawned — a phantom capability. MAJOR
  if the body spawns them, MINOR if they appear reference-only.
- **Same-name cross-scope divergence (`detect_collisions.py`).** New
  `name_conflicts` output: the same `name` present in more than one location with
  divergent bodies. This is independent of the description-overlap threshold on
  purpose — divergence *lowers* description similarity, so the overlap check misses
  exactly the dangerous case (two copies drifted apart, undefined which runs).
- Four new antipattern-checklist entries: embedded-agents-not-invocable,
  name/description that oversells behavior, unverified platform claim stated as
  fact, and reference content duplicated across sibling skills.

### Report behavior

- **A grading table is now mandatory on every run.** The report always ends with a
  one-row-per-target table (gate, grade, score, BLOCKER/MAJOR/MINOR counts, top
  finding) — even for a fully clean audit. The per-target scorecards expand each
  row.

### Docs & robustness

- **Interpreter robustness (Step 1).** Try `python3` → `python` → `py -3`; detect
  the Windows Microsoft Store stub; if none runs, fall back to a semantic-only
  audit and say so in the report rather than failing silently.
- **`--json` output shapes documented** for every script (the envelope key differs:
  `targets` vs `results` vs `collisions`/`name_conflicts`).
- **Step 2 is inline-first.** The deterministic scripts + inline semantic judgment
  are the documented primary path; the four specialist sub-agents are explicitly
  optional (large/deep audits only) and honestly noted as *not invocable* unless
  installed to `~/.claude/agents/` or packaged as a plugin.
- **Measurability honesty.** For skills that can't be benchmarked
  (`disable-model-invocation`, interactive/gated), the accepted evidence is one
  real end-to-end run vs. a known-good baseline (n=1), not a faked number.
- **Naming.** The skill is `config-auditor` (the name reflects the read-only-audit
  default; the fix / measure step is the opt-in Phase 2). No stray old names remain.

### New: opt-in trigger measurement (unlocks the Trigger/Execution 10)

- **`scripts/trigger_eval.py`** — the only script that makes model calls (`claude
  -p`), so it is **not** part of the read-only audit. It measures trigger reliability
  against a labeled eval set and reports recall + false-trigger rate. **Costs tokens**;
  always `--dry-run` first to preview the call count. Example set:
  `tests/fixtures/example-eval-set.json`.
- **Measured ceiling made honest.** Trigger and Execution are now explicitly capped at
  9 by inspection; the report states the cap per target and *offers* the (paid)
  measurement to unlock a 10, or says the skill is not measurable
  (`disable-model-invocation` / interactive). The scale no longer shows a 10 it can
  never award on its own.

### Tests

- **`tests/run_regression.py`** + fixtures (`tests/fixtures/folded-scalar/`,
  `tests/fixtures/embedded-agents/`) guard all three fixed/new behaviors: the
  folded-scalar length + WHEN detection, the Windows resource-path handling, and
  the embedded-agent invocability check. Run: `py -3 tests/run_regression.py`
  (exits non-zero on failure). Fixtures live under `tests/` and are never picked up
  by a normal audit.
