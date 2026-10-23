# Plugin Forge

A marketplace of Claude Code plugins and agents.

## Plugins

| Plugin | What it does |
|---|---|
| [`config-auditor`](plugins/config-auditor/) | Read-only auditor for Claude Code skills, agents, and whole plugins (hooks, MCP/LSP servers, monitors, commands, settings) — weighted rubric, hard severity gates, five specialist analyst subagents, prioritized report. |
| [`concept-review`](plugins/concept-review/) | Evidence-based concept-phase pipeline — a Conductor drives 12 specialist sub-agents (product, research, architecture, UX, feasibility, QA, red-team critique, scope-and-value challenge, …) through a gated, dependency-ordered chain to a Go/No-Go decision. |

## Install

Add the marketplace once, then install any plugin from it:

```bash
# Add the marketplace once:
claude plugin marketplace add Try5t/plugin-forge

# Then install either plugin:
claude plugin install config-auditor@plugin-forge
claude plugin install concept-review@plugin-forge
```

Restart the session (or `/reload-plugins`) to activate.

## Enabling only in the repos that need it

Knowing the marketplace and *activating* a plugin are two separate things.
`marketplace add` only registers the catalog (one clone, cached in `~/.claude`) — it
turns on nothing. To enable a plugin **only in a specific repo**, commit this to that
repo's `.claude/settings.json`:

```json
{
  "enabledPlugins": {
    "config-auditor@plugin-forge": true
  }
}
```

This references the marketplace by its **name** (`plugin-forge`), resolved from the
globally known catalog — **no path**. Repos without the entry don't load the plugin.
Prerequisite: the marketplace is known on the machine
(`claude plugin marketplace add Try5t/plugin-forge`, once); teammates run that once too,
or declare it per repo with a **git-source** `extraKnownMarketplaces` entry.

> **Never commit a local or relative marketplace path** (`C:/…`, `./`, or a
> `"source": "directory"`) into a shared repo. Claude Code stores it unresolved, so it
> breaks on every other machine and triggers repeated failed clones — the classic
> "wrong path" symptom. In shared config, always reference the marketplace by the GitHub
> shorthand `Try5t/plugin-forge` (or the full `https://github.com/Try5t/plugin-forge.git`),
> never a filesystem path.

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
