# Plugin Forge

A private marketplace of Claude Code plugins and agents.

## Plugins

| Plugin | What it does |
|---|---|
| [`skill-auditor`](plugins/skill-auditor/) | Read-only auditor for Claude Code skills and agents — weighted rubric, hard severity gates, four specialist analyst subagents, prioritized report. |
| [`concept-review`](plugins/concept-review/) | Evidence-based concept-phase pipeline — a Conductor drives 12 specialist sub-agents (product, research, architecture, UX, feasibility, QA, red-team critique, scope-and-value challenge, …) through a gated, dependency-ordered chain to a Go/No-Go decision. |

## Install

Add the marketplace once, then install any plugin from it:

```bash
# Add the marketplace once (private GitLab repo):
claude plugin marketplace add https://gitlab.com/Try5t/plugin-forge.git

# Then install either plugin:
claude plugin install skill-auditor@plugin-forge
claude plugin install concept-review@plugin-forge
```

Restart the session (or `/reload-plugins`) to activate.

## Updating

The marketplace source is remembered — no re-clone. Pull the latest and apply:

```bash
claude plugin marketplace update plugin-forge
claude plugin update <plugin-name>
```

Then restart the session (or `/reload-plugins`). Updates are never automatic.

## Adding a plugin to this marketplace

1. Create `plugins/<name>/` with a `.claude-plugin/plugin.json` and its components
   (`skills/`, `agents/`, `scripts/`, `references/`).
2. Add an entry to `.claude-plugin/marketplace.json` with `"source": "./plugins/<name>"`.
3. Validate: `claude plugin validate .`

Each plugin owns its own `README.md` and version. See
[CONTRIBUTING.md](CONTRIBUTING.md) for the full guide (conventions, versioning,
local dev loop, commit-identity, and the pre-push checklist).

## Layout

```
.claude-plugin/marketplace.json   the marketplace catalog (lists all plugins)
plugins/<name>/                    one directory per plugin, each self-contained
README.md
```
