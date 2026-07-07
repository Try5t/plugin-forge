# Hooks Checklist (DRAFT — research pass)

Hooks are the sharpest surface a plugin can carry. Unlike a skill or agent — which
only *proposes* actions the model may take — a `command` hook is **arbitrary shell
that Claude Code executes itself**, automatically, on a lifecycle event, with the
user's full privileges (their credentials, env vars, filesystem, network). There is
no per-invocation model judgment between the config and the shell. That makes a
malicious or careless hook strictly worse than a bad skill, and it is why hooks get
their own gates.

Two real, primary-source-verified CVEs anchor this checklist. Both were disclosed
together by Check Point ("Caught in the Hook") and share one root cause — **project
files processed before the startup trust dialog** — the *trust-timing* class:

- **CVE-2025-59536** (CVSS **8.7 High**, CWE-94; fixed in Claude Code **1.0.111**).
  Official advisory, verbatim: *"Due to a bug in the startup trust dialog
  implementation, Claude Code could be tricked to execute code contained in a project
  before the user accepted the startup trust dialog."* The demonstrated vehicle was a
  `SessionStart` (`startup`) hook in a cloned repo's `.claude/settings.json`, but the
  flaw is code-execution-before-trust generally, not that one hook.
- **CVE-2026-21852** (CVSS **5.3 Moderate**; fixed in **2.0.65**). A settings **`env`**
  block setting `ANTHROPIC_BASE_URL` to an attacker endpoint caused Claude Code to
  issue API requests — leaking the API key — *before* the trust prompt. This is
  fundamentally a settings-env concern (the settings/permissions checklist owns it),
  but the base-URL/key-redirect pattern is worth flagging wherever it appears.

**Scope note (important, and honest):** both original bugs are *patched* in current
Claude Code. The auditor's job is therefore **not** to detect the Anthropic bug — it
is to catch the *attack pattern those CVEs taught* (malicious hooks/settings riding in
untrusted project files or third-party plugins), which a plugin or repo can still
carry regardless of the client fix.

Audit asymmetrically, as with the security checklist: accept false positives to drive
false negatives toward zero. A wrongly flagged safe hook costs a minute; a missed
`curl … | bash` costs the machine.

## Where hooks live (discover all of these)

A hook can be declared in any of:

- `~/.claude/settings.json` — user-wide
- `.claude/settings.json` — project-scoped, **committed and shared** (highest risk:
  travels with a cloned repo)
- `.claude/settings.local.json` — project-scoped, local
- Managed policy settings — org-wide, admin-forced (can force-enable plugin hooks on
  every user)
- **Plugin `hooks/hooks.json`** — ships with the plugin; enabled when the plugin is
- Skill / agent frontmatter — active while the component is

The auditor must parse the `hooks` block in every settings file **and** every
plugin's `hooks/hooks.json`.

## Handler types, by risk

| `type` | What it does | Risk |
|--------|--------------|------|
| `command` | Runs a shell command / executable | **Highest** — arbitrary code |
| `http` | POSTs the event JSON to an endpoint | High — data leaves the machine |
| `mcp_tool` | Calls a tool on a connected MCP server | Inherits that server's risk |
| `prompt` | Single-turn LLM yes/no | Low |
| `agent` | Subagent verifies a condition | Low–medium |

## Deterministic checks (a `check_hooks.py` can flag these at 100%)

- [ ] **Fetch-and-execute in a command.** `curl …| bash`, `wget …| sh`,
      `… | sh -c`, or any pipe from a network fetcher into a shell. **BLOCKER.**
- [ ] **Reverse-shell / remote-shell patterns.** `/dev/tcp/`, `bash -i`,
      `nc -e`, `sh -i >& …`. **BLOCKER.**
- [ ] **Credential-path reads + egress.** Reads of `.env`, `~/.ssh/`, `~/.aws/`,
      `secrets/`, cloud-credential paths *combined with* any network sink
      (`curl`/`wget`/`nc`/`http` handler). **BLOCKER.**
- [ ] **`ANTHROPIC_BASE_URL` / API-key env override** set inside a hook or a
      settings `env` block (the CVE-2026-21852 key-redirect pattern). **BLOCKER.**
      (Primary ownership is the settings/permissions checklist; flag it here too.)
- [ ] **Obfuscated command body.** `base64 -d | sh`, hex/`\x` escapes, `eval` of a
      decoded string. Obfuscation in a config file is itself the signal. **MAJOR→BLOCKER.**
- [ ] **External URL literal** in any hook command or an `http` handler endpoint.
      Flag for adjudication — legitimate uses exist, but every exfil path starts here.
      **MAJOR.**
- [ ] **Plaintext secret** in a hook command or `http` `headers`. **BLOCKER**
      (defer to the existing secret scan / gitleaks).

## Semantic checks (model judgment)

- [ ] **Trust-timing (the CVE-2025-59536 class).** A `SessionStart` (`startup`),
      `SessionStart` (`resume`), or any hook that fires *before the user has acted*
      and produces an external side effect is the most dangerous shape. A committed
      `.claude/settings.json` SessionStart hook that touches the network is
      **BLOCKER** on sight.
- [ ] **Shell-form vs exec-form.** When `args` is **omitted**, `command` goes to
      `sh -c` (or PowerShell) with full tokenization, expansion, pipes, and globs —
      the injection surface. Exec-form (`args` set, spawned directly, no shell) is
      safer. A non-trivial shell-form command that could be exec-form is a **MAJOR**
      hardening finding.
- [ ] **`if` filter treated as a security boundary.** The `if:` Bash matcher is
      **best-effort and fails open** — an unparseable command runs the hook anyway
      (per the official docs). If a hook relies on `if` to stay safe rather than on
      the permission system, that is a **MAJOR** false sense of containment.
- [ ] **Overly broad matcher on a mutating hook.** `matcher: "*"` / `""` / omitted
      on a hook that writes, deletes, or sends means it fires on everything. Scope it.
      **MAJOR** for mutating hooks, **MINOR** for read-only.
- [ ] **Tool input/output rewriting.** `updatedInput` (PreToolUse) and
      `updatedToolOutput` (PostToolUse) let a hook silently change what Claude does
      or sees. Legitimate for redaction; dangerous for injection. Any rewriting hook
      needs a stated, benign purpose. **MAJOR** if unexplained.
- [ ] **Background persistence.** `async: true` / `asyncRewake: true` can keep
      running after Claude Code exits — a channel for delayed exfil or long-running
      operations outside the session's view. Justify or flag **MAJOR.**
- [ ] **`http` handler destination.** Every `http` hook ships the event JSON (which
      includes `tool_input` — file contents, command args, internal state) to a URL.
      The host must be trusted and the purpose stated. **MAJOR** otherwise. Official
      containment exists and its *absence* is itself a finding: `allowedHttpHookUrls`
      allowlists which URL patterns HTTP hooks may target, and
      `httpHookAllowedEnvVars` allowlists which env-var names they may interpolate —
      an `http` hook with neither constraint set is unbounded egress. **MAJOR.**

## Gates summary (→ grade F)

BLOCKER: fetch-and-execute; reverse shell; credential-read + egress; base-URL/API-key
override; committed pre-trust `SessionStart` hook with external side effects;
plaintext secret. Any of these forces the target to F regardless of weighted score.

## What a static audit *cannot* catch (state honestly)

A read-only config audit sees the hook *command*, not what a fetched script does at
runtime, nor a benign-looking helper binary that is itself malicious. A hook that
runs a local script should have that script audited too (it is a bundled resource);
a hook that runs an opaque external binary is an unresolved residual risk — flag it
**PLAUSIBLE** with the mitigation "pin and review the target," never a clean pass.

## Mitigations to recommend

- Prefer exec-form (`args`) over shell-form for anything non-trivial.
- Never rely on `if:` for safety — use the permission system for hard allow/deny.
- For untrusted repos, `disableAllHooks: true` (managed level to be unremovable);
  `allowManagedHooksOnly` in managed settings to load only vetted hooks.
- Constrain `http` hooks with `allowedHttpHookUrls` and `httpHookAllowedEnvVars`.
- Keep secrets out of settings; read them from env at runtime.
- Narrow matchers; add `timeout`; keep hooks fast (<1s).

## Sources

- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks) — official event list, handler types, exit-code/JSON-output semantics, exec-vs-shell form, the best-effort/"fails open" `if` caveat, `disableAllHooks`.
- [Settings reference — Claude Code Docs](https://code.claude.com/docs/en/settings) — verified keys: `allowedHttpHookUrls`, `httpHookAllowedEnvVars`, `disableAllHooks`, `allowManagedHooksOnly`, `env`.
- [GHSA-4fgq-fpq9-mr3g / CVE-2025-59536](https://github.com/advisories/GHSA-4fgq-fpq9-mr3g) — **primary advisory**: CVSS 8.7, CWE-94, fixed 1.0.111, verbatim summary quoted above.
- [GHSA-jh7p-qr78-84p7 / CVE-2026-21852](https://github.com/advisories/GHSA-jh7p-qr78-84p7) — **primary advisory**: CVSS 5.3, fixed 2.0.65, ANTHROPIC_BASE_URL pre-trust key leak.
- [Check Point Research — "Caught in the Hook"](https://research.checkpoint.com/2026/rce-and-api-token-exfiltration-through-claude-code-project-files-cve-2025-59536/) — the original discoverers' write-up of both CVEs.
- [Claude Code Hooks Security — MintMCP](https://www.mintmcp.com/blog/claude-code-hooks-security) — the IOC checklist this section's deterministic patterns draw from (secondary; CVE figures now verified against the GHSA advisories above).
- [Trail of Bits — claude-code-config](https://github.com/trailofbits/claude-code-config) — opinionated hardened defaults (deny curl/fetch/.env, sandboxing, never-root).
- CWE-78 (OS Command Injection) / OWASP command-injection guidance — the established framework behind the shell-form and untrusted-interpolation findings.
