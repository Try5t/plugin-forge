# Skill Auditor

A read-only auditor for Claude Code **skills and agents**. It scans every skill and
agent it can find (global and repo-local, embedded and standalone), scores each
against a weighted rubric, applies hard severity gates, and returns a prioritized,
evidence-backed report of findings and recommendations. It never edits anything until
you explicitly approve specific recommendations.

The point: turn a subjective "this skill feels weak" into a defensible audit — not
"make it better" but *here is exactly what is wrong, why it matters, how severe it is,
and what to change.*

## What it does

- **Discovers** all skills and agents across `~/.claude/` and the current repo's
  `.claude/`, plus agents embedded inside skills.
- **Scores** each target 0–100 on weighted dimensions (Trigger, Structure, Security,
  Execution for skills; plus system-prompt, tool-fit, model, and hand-back for agents)
  and maps to an A–F grade.
- **Gates** on hard failures (unparseable frontmatter, bad `name`/`description`,
  plaintext secrets, un-guarded destructive commands) — any gate forces an F.
- **Reports** a grading table, per-target scorecards, cross-cutting findings, and a
  single numbered recommendation list to approve from.

Two-phase contract: **Phase 1 is strictly read-only.** Refactoring (Phase 2) happens
only after you approve specific numbered recommendations.

## Components

| Component | Purpose |
|---|---|
| `skills/skill-auditor/` | The audit skill — the default, single-context path |
| `agents/*-analyst.md` | Four specialist subagents (`trigger`, `structure`, `security`, `agent`) for splitting large audits in parallel; namespaced as `skill-auditor:<name>` |
| `scripts/*.py` | Deterministic checks (description, structure, security, collisions) + discovery; read-only |
| `references/*.md` | The scoring rubric, antipattern + security checklists, report template, refactor workflow |

## Install

```bash
# From GitHub once published (replace <your-org> with your GitHub account/org):
claude plugin marketplace add <your-org>/plugin-forge
claude plugin install skill-auditor@plugin-forge

# Or from a local clone:
claude plugin marketplace add /path/to/plugin-forge
claude plugin install skill-auditor@plugin-forge
```

Then start a fresh session. Trigger it by asking to **"audit my skills"** (or "review
my agents", "score my skills", …). Scope it if you like: "only this repo", "just the
global skills", "only the `foo` skill".

## Updating

Plugins update on demand — Claude Code remembers the marketplace source, so there is no
re-clone. Pull the latest and apply:

```bash
claude plugin marketplace update plugin-forge   # refresh the catalog from the repo source
claude plugin update skill-auditor           # bump the plugin to the latest version
```

Then restart the session (or run `/reload-plugins`) to apply. Updates are never
automatic — nothing changes until you run these.

## Measuring "better" (opt-in, costs tokens)

Two dimensions — Trigger and Execution — cap at 9 by inspection; the 10th point needs a
real measurement. `scripts/trigger_eval.py` measures a skill's held-out trigger rate via
`claude -p` against a labeled eval set. It is **not** part of the read-only audit and
makes real model calls — run `trigger_eval.py --dry-run` first to preview the cost, and
run it only on explicit approval.

## Requirements

- Python 3 (`python3`, `python`, or `py -3`) for the deterministic scripts. Without it,
  the audit falls back to a semantic-only read and says so in the report.
- `gitleaks` (optional) for the secret scan; the scripts fall back to a regex scan if
  it is absent.

## Layout

```
.claude-plugin/plugin.json        plugin manifest
skills/skill-auditor/SKILL.md     the skill
agents/                           four analyst subagents
scripts/                          deterministic, read-only checks
references/                       rubric, checklists, templates
tests/                            regression suite + fixtures (dev only)
```

The marketplace catalog lives at the repo root (`.claude-plugin/marketplace.json`), not
inside the plugin.

Bundled scripts and references are resolved at runtime via `$CLAUDE_PLUGIN_ROOT`.

## Safety

Phase 1 grants only `Read, Grep, Glob, Bash(python3|python|gitleaks), Task` — no `Write`
or `Edit` — so an audit cannot mutate a target. The deterministic scripts and gitleaks
run locally and send nothing outward; only the opt-in `trigger_eval.py` makes network
calls.

## License

MIT
