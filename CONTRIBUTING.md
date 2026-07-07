# Contributing to plugin-forge

A private Claude Code plugin marketplace. The root `.claude-plugin/marketplace.json`
is the catalog; every plugin is self-contained under `plugins/<name>/`. This guide is
how to add or update one without breaking the others.

## Repo layout

```
.claude-plugin/marketplace.json   the catalog (lists every plugin)
plugins/<name>/                    one self-contained plugin per directory
  .claude-plugin/plugin.json       plugin manifest (name required)
  skills/<name>/SKILL.md           skill(s)
  agents/*.md                      subagent(s) — auto-namespaced <plugin>:<agent>
  scripts/  references/            bundled resources
  README.md
.gitattributes                     LF normalization
```

## Add a new plugin

1. **Scaffold** `plugins/<name>/`:
   - `.claude-plugin/plugin.json` — `name` is required, **kebab-case, ≤64 chars, no
     reserved word** (`claude`/`anthropic`). Add `version`, `description`, `keywords`.
   - Components: `skills/<name>/SKILL.md`, `agents/*.md`, `scripts/`, `references/`.
2. **Reference bundled files via `$CLAUDE_PLUGIN_ROOT`** (e.g.
   `python3 "$CLAUDE_PLUGIN_ROOT/scripts/foo.py"`), so they resolve regardless of the
   user's working directory. Do **not** assume a relative `scripts/` cwd.
3. **Register it** in `.claude-plugin/marketplace.json`:
   ```json
   { "name": "<name>", "source": "./plugins/<name>", "description": "…" }
   ```
4. **Validate**: `claude plugin validate .` (must pass — it checks both manifests).
5. **Commit and push**, then activate:
   ```bash
   claude plugin marketplace update plugin-forge
   claude plugin install <name>@plugin-forge
   ```
   Restart the session or `/reload-plugins` to apply.

## Component conventions

- **Skills** — keep `SKILL.md` lean (ideally <300 lines); push detail into
  `references/` and point at it. All "when to use" info lives in the `description`.
- **Agents** — least-privilege `tools:`; `model: inherit` for judgment work. They
  auto-namespace as `<plugin>:<agent>`, so names don't need a prefix.
- **Scripts** — read-only unless clearly documented otherwise; referenced via
  `$CLAUDE_PLUGIN_ROOT`. No secrets, no personal data.

## Versioning & releases

- Bump `version` in the plugin's `plugin.json` (semver) for every meaningful change.
- Optional tag: `claude plugin tag plugins/<name>` → creates a `<name>--v<version>`
  git tag and checks that `plugin.json` and the marketplace entry agree.
- Consumers update with `claude plugin marketplace update plugin-forge` then
  `claude plugin update <name>`, then restart/reload. Updates are never automatic.

## Local dev loop (fast iteration)

Avoid the push→pull round-trip while developing:

- Point a marketplace at your **local checkout**:
  `claude plugin marketplace add C:/repos/plugin-forge`, then edit →
  `claude plugin marketplace update` → `/reload-plugins`.
- Or keep a work-in-progress skill **loose** in `~/.claude/skills/` for instant reload,
  and fold it into a plugin only when you cut a release.

## Commit identity (keep it private)

Commit under a **GitLab private noreply email** so no personal address enters history.
Set it **repo-locally** (this repo already has it configured):

```bash
git config --local user.name  "<handle>"
git config --local user.email "<id>-<handle>@users.noreply.gitlab.com"
```

Find your own at GitLab → **Preferences → Profile → private commit email**. Never rely
on the global identity here — it may carry a real name/email.

## Line endings

`.gitattributes` normalizes everything to LF (`* text=auto eol=lf`). Don't commit CRLF.

## Pre-push checklist

- [ ] `claude plugin validate .` passes
- [ ] new/changed plugin has a `README.md`
- [ ] scripts/references referenced via `$CLAUDE_PLUGIN_ROOT`
- [ ] `version` bumped if behavior changed
- [ ] marketplace entry added/updated
- [ ] no secrets or personal data (`git grep -niE 'password|secret|token|@gmail|@gmx'`)
