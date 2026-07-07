# Plugin Manifest & Provenance Checklist (DRAFT — research pass)

A plugin is the *container* — the unit the user installs and trusts as a whole. This
checklist audits the container itself: the `.claude-plugin/plugin.json` manifest, the
plugin's provenance (where it comes from, how it versions), and — critically — a
**complete inventory of every executable/external surface the plugin can carry**, so
nothing slips through by living in a component the auditor forgot to enumerate.

There is no plugin signing in Claude Code today. Provenance therefore reduces to two
levers the auditor *can* assess: **trust the source** and **pin the version**. Say so
plainly rather than implying attestation exists.

## The manifest schema (verified against the plugins reference)

`.claude-plugin/plugin.json`. The manifest is **optional**; if omitted, components are
auto-discovered and the name is derived from the directory. `name` is the **only
required field**.

| Field | Notes relevant to audit |
|-------|-------------------------|
| `name` (required) | kebab-case, no spaces; used for component namespacing (`plugin:agent`). |
| `version` | Semantic version. **If omitted, Claude Code falls back to the git commit SHA — every commit is a new version, so there is no pin.** Setting it pins updates to explicit bumps. |
| `description`, `author`, `homepage`, `repository`, `license`, `keywords` | Metadata / provenance signals. `repository` is the source-code URL. |
| `defaultEnabled` (bool, default `true`) | `false` = installs disabled; the docs say to use it "for plugins that add cost or scope a user should opt into, such as one that connects to an external service." |
| `dependencies` (array) | Other plugins this one pulls in, with optional semver constraints — a transitive supply-chain edge. |
| `userConfig` (object) | Values prompted at enable time, later substituted as `${user_config.*}` into command strings — an interpolation surface. |
| `channels` (array) | Message-injection channels (Telegram/Slack/Discord style) — an untrusted-input intake. |
| component paths | `skills`, `commands`, `agents`, `hooks`, `mcpServers`, `lspServers`, `outputStyles`, `experimental.themes`, `experimental.monitors`. |

## Deterministic checks

- [ ] **Run the official validator.** `claude plugin validate <dir> --strict` treats
      warnings (misspelled/foreign fields) as errors. A plugin that fails `--strict`
      is a **MAJOR** hygiene finding; a hard load error (e.g. `keywords` a string not
      an array) is a **BLOCKER**. This is the authoritative structural gate — use it.
- [ ] **`version` present and pinned.** No `version` → every commit is a distinct
      version and there is no rug-pull-resistant pin. **MAJOR** (supply-chain, mirrors
      the MCP unpinned-dependency finding).
- [ ] **`name` valid.** kebab-case, no spaces, unique. Malformed → **MAJOR**
      (namespacing breaks). (Reserved-word gate applies to *skill* names, not the
      plugin `name` — do not over-apply it here.)

## Semantic checks — provenance

- [ ] **Source trust.** The plugin installs from a marketplace whose `source` is a git
      repo, or is a `@skills-dir` in-place plugin. Is `repository`/source a known,
      reputable origin, or unknown/typosquat-adjacent? Unknown provenance is the root
      of supply-chain risk (no signing to fall back on). **MAJOR** for unknown source.
- [ ] **`dependencies` provenance.** Each required plugin is another trust decision and
      another audit target. Unpinned or unknown-source dependencies inherit all of the
      above. **MAJOR.**
- [ ] **`defaultEnabled` vs. blast radius.** A plugin that bundles network/MCP servers,
      hooks, or monitors but ships `defaultEnabled: true` (or omits it) auto-activates
      that surface on install. For risky surface, `defaultEnabled: false` is the
      documented pattern. **MAJOR** when high-risk surface auto-enables.

## Executable / external surface inventory (enumerate ALL — nothing skipped)

This is the watertightness step. A plugin can execute code or reach the network
through **more** channels than hooks and MCP. The auditor must enumerate and route
each to its checklist:

| Surface | Where | Routes to |
|---------|-------|-----------|
| **Hooks** | `hooks/hooks.json`, inline `hooks` | `hooks-checklist.md` |
| **MCP servers** | `.mcp.json`, inline `mcpServers` | `mcp-checklist.md` |
| **`!` blocks in commands/skills** | command/SKILL bodies | `commands-checklist.md` |
| **Bundled scripts** | `scripts/` referenced by hooks/commands | `security-checklist.md` |
| **Monitors** ⚠️ | `monitors.json` / `experimental.monitors` | *see below* |
| **LSP servers** ⚠️ | `.lsp.json` / `lspServers` | *see below* |

- [ ] **Monitors** run a shell `command` **automatically when the plugin is active**
      (`when: "always"` starts at session start; the default), often long-running
      (`tail -F`, polling). They support `${user_config.*}` / `${ENV_VAR}` substitution
      into the command — an injection surface. **A monitor `command` gets the exact
      same gates as a hook command** (fetch-and-execute, reverse shell, credential
      egress = BLOCKER; unpinned/opaque = MAJOR). Easy to miss because it is not a
      "hook" — enumerate it explicitly.
- [ ] **LSP servers** launch a language-server process via `command`. Same supply-chain
      and fetch-and-execute checks as an MCP stdio server. **MAJOR** for unpinned/
      unknown; **BLOCKER** for fetch-and-execute.

## Gates summary (→ grade F)

BLOCKER: manifest hard load error (`--strict` type failure); any BLOCKER surfaced by a
bundled hook / MCP / monitor / LSP / command (routed to their checklists).

## What a static audit *cannot* catch (state honestly)

No signing means the auditor verifies *declared* provenance, not authenticity — a
compromised-but-reputable-looking source, or a dependency that rug-pulls after review,
is out of static reach. Report these as PLAUSIBLE residual risk with the mitigations:
pin `version`, pin `dependencies`, install only from trusted marketplaces, re-audit on
update.

## Sources

- [Plugins reference — Claude Code Docs](https://code.claude.com/docs/en/plugins-reference) — the `plugin.json` schema (all fields above verified verbatim), `claude plugin validate --strict`, component path fields, `defaultEnabled`, `dependencies`, `userConfig`, `channels`, and the monitors/LSP component specs.
- [Plugin marketplaces — Claude Code Docs](https://code.claude.com/docs/en/plugin-marketplaces) — marketplace entry `source`/`name` and how install provenance flows.
- SLSA / software-supply-chain framing — the established basis for the "pin + trust source" provenance findings (adjacent framework; Claude Code has no plugin signing yet — stated honestly).
