# Config Auditor

A read-only auditor for Claude Code **skills, agents, and whole plugins**. It scans
every target it can find — global and repo-local, standalone and embedded, and every
component a plugin bundles — scores each against a weighted rubric, applies hard
severity gates, and returns a prioritized, evidence-backed report of findings and
recommendations. It never edits anything until you explicitly approve specific
recommendations.

The point: turn a subjective "this feels weak / is this safe?" into a defensible audit
— not "make it better" but *here is exactly what is wrong, why it matters, how severe
it is, and what to change.*

## What it audits

| Target | What gets checked |
|---|---|
| **Skills** | trigger/description quality, structure, security, execution self-containment |
| **Agents** (standalone + embedded) | system-prompt quality, tool-fit, model choice, delegation/hand-back |
| **Commands** | the skill checks **plus** the `` !``-block auto-exec and `$ARGUMENTS`-into-shell injection surface |
| **Hooks + monitors** | fetch-and-execute, reverse shells, credential egress, `ANTHROPIC_BASE_URL`/key redirect, pre-trust auto-exec, shell-form vs exec-form |
| **MCP + LSP servers** | plaintext secrets in `env`/`headers`, fetch-and-execute launch, unpinned supply chain, plaintext `http://` |
| **Plugin manifest** | name/version/dependency pinning, `defaultEnabled` vs the surface it bundles, provenance |
| **Settings / permissions** | `bypassPermissions` in shared config, credential/base-URL redirect, `apiKeyHelper`, over-broad grants, blanket MCP approval |

Every surface check is **evidence-based and primary-source-anchored** — the two Claude
Code CVEs (CVE-2025-59536 pre-trust RCE, CVE-2026-21852 key exfiltration), the OWASP
MCP Top 10, and the official hooks/settings/plugins docs. Each surface checklist also
carries an honest *"what a static audit cannot catch"* section (tool poisoning,
rug-pulls) so nothing is oversold as a clean pass.

## How it works

- **Discovers** every target across `~/.claude/`, the current repo's `.claude/`, and
  any installed or repo-local plugin (`.claude-plugin/plugin.json`) plus its hooks,
  MCP/LSP servers, monitors, commands, and settings.
- **Scores** each target 0–100 on weighted dimensions and maps to an A–F grade.
  Config components are graded on security posture and least-privilege; a plugin
  container inherits the **worst grade** among the components it ships.
- **Gates** on hard failures (unparseable frontmatter, bad `name`/`description`,
  plaintext secrets, fetch-and-execute, `bypassPermissions` in shared config, …) —
  any gate forces an F.
- **Reports** a mandatory grading table, per-target scorecards, cross-cutting
  findings, and a single numbered recommendation list to approve from.

**Two-phase contract: Phase 1 is strictly read-only.** Refactoring (Phase 2) happens
only after you approve specific numbered recommendations.

## Usage

Start a fresh session after installing, then just ask. The skill triggers on natural
requests and **scopes itself to what you name** — it does not sweep your whole plugin
surface when you only asked about a skill:

```
"audit my skills"                → skills only
"review my agents"               → agents only
"audit this plugin"              → the plugin's manifest + all its surface
"check my hooks / MCP / settings"→ surface only
"audit everything / my setup"    → full sweep
```

If a request is genuinely ambiguous (a bare "run the auditor" in a repo holding
several kinds), it asks **once** which scope you want, then proceeds.

**Explicit invocation** takes a scope hint — `argument-hint: [skills|agents|commands|plugins|surface|all] [global|repo|<name>]`:

```
/config-auditor skills repo        # only this repo's skills
/config-auditor surface myplugin   # only the executable surface of `myplugin`
/config-auditor all global         # everything under ~/.claude
```

The report states the resolved scope on its first line, so you always see what was —
and was not — covered. When you approve recommendations, it hands off to Phase 2
(refactor) which implements and, where a claim is empirical, measures them.

## Components

| Component | Purpose |
|---|---|
| `skills/config-auditor/` | The audit skill — the default, single-context path; owns the scoping gate and workflow |
| `agents/*.md` | Five specialist subagents (`trigger`, `structure`, `security`, `agent`, `surface`) for splitting large audits in parallel; namespaced as `config-auditor:<name>` |
| `scripts/*.py` | Deterministic checks (description, structure, security, collisions, hooks, MCP, manifest) + discovery; read-only |
| `references/*.md` | The scoring rubric, antipattern + security checklists, the five surface checklists (hooks, MCP, commands, manifest, settings), report template, refactor workflow |

## Install

```bash
# From the marketplace:
claude plugin marketplace add Try5t/plugin-forge
claude plugin install config-auditor@plugin-forge

# Or from a local clone:
claude plugin marketplace add /path/to/plugin-forge
claude plugin install config-auditor@plugin-forge
```

Then start a fresh session (or `/reload-plugins`).

## Updating

Plugins update on demand — Claude Code remembers the marketplace source, so there is no
re-clone:

```bash
claude plugin marketplace update plugin-forge   # refresh the catalog from the repo source
claude plugin update config-auditor             # bump the plugin to the latest version
```

Restart the session (or `/reload-plugins`) to apply. Updates are never automatic.

## Measuring "better" (opt-in, costs tokens)

Two dimensions — Trigger and Execution — cap at 9 by inspection; the 10th point needs a
real measurement. `scripts/trigger_eval.py` measures a skill's held-out trigger rate via
`claude -p` against a labeled eval set (should-trigger + hard should-not-trigger
near-misses), reporting recall + false-trigger rate. A 10 needs recall ≥ 0.95 **and**
false-trigger ≤ 0.05. It is **not** part of the read-only audit and makes real model
calls. If any call fails (e.g. auth), it aborts without a score rather than fabricating
one — so it must run from a terminal where Claude Code is authenticated (a plain
`claude -p "hi"` must work), not inside a nested agent/sandbox session.

To measure this plugin's own Trigger dimension, a labeled eval set ships at
`tests/fixtures/config-auditor-evalset.json` and a runner resolves the paths for you:

```bash
py -3 scripts/run_trigger_eval.py         # dry-run: preview the cost (no calls)
py -3 scripts/run_trigger_eval.py --go    # real run (COSTS TOKENS)
```

The dry-run prints what the real run actually costs, not just a call count. Each call is
a **fresh `claude -p` session**, so the CLI's own system prompt and tool definitions are
re-sent cold every time — that fixed overhead, not the short judge prompt, dominates the
bill (the shipped 27-query set at the default `--repeats 3` is ~1.2M input tokens across
81 calls). The preview breaks that down and prices it per model, so you can see that the
model choice swings the run ~5x while the call count doesn't move; pass `--model` to mark
the one you'll use. **On a Pro/Max subscription the dollar figures don't apply** — the
calls count against your plan's 5-hour and weekly limits instead, and a full run is a
large burst of cold-context sessions that can exhaust the 5-hour window. Time it
accordingly, or lower `--repeats` (at the cost of the majority-vote smoothing) to shrink
it. Token counts are estimates for sizing the run, not for reconciling a bill.

`trigger_eval.py` is a single-skill judge approximation — evidence, not proof. For true
selection under competition with your other skills, use skill-creator's `run_loop.py`.
(Config-component kinds — hooks, MCP/LSP, monitors, settings — are not measured this way;
they are graded on security posture, so a clean one earns a 10 by inspection.)

## Requirements

- Python 3 (`python3`, `python`, or `py -3`) for the deterministic scripts. Without it,
  the audit falls back to a semantic-only read and says so in the report.
- `gitleaks` (optional) for the secret scan; the scripts fall back to a regex scan if
  it is absent.
- `claude` CLI (optional) for `check_manifest.py --validate`, which runs the official
  `claude plugin validate --strict`.

## Layout

```
.claude-plugin/plugin.json         plugin manifest
skills/config-auditor/SKILL.md     the skill
agents/                            five analyst subagents
scripts/                           deterministic, read-only checks
references/                        rubric, checklists, templates
tests/                             regression suite + fixtures (dev only)
```

The marketplace catalog lives at the repo root (`.claude-plugin/marketplace.json`), not
inside the plugin. Bundled scripts and references are resolved at runtime via
`$CLAUDE_PLUGIN_ROOT`.

## Safety

Phase 1 grants only `Read, Grep, Glob, Bash(python3|python|py|gitleaks), AskUserQuestion,
Task` — no `Write` or `Edit` — so an audit cannot mutate a target. The deterministic
scripts and gitleaks run locally and send nothing outward; only the opt-in
`trigger_eval.py` makes network calls. The auditor excludes its own files so it never
recursively grades itself.

## License

MIT
