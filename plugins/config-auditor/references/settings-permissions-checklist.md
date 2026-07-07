# Settings & Permissions Checklist (DRAFT — research pass)

A `settings.json` is where a plugin or repo can **widen Claude Code's own trust
boundary** — turn off prompts, broaden tool grants, redirect credentials, or force
organization-wide behavior. It is the highest-leverage config surface after hooks,
because a single key can neutralize every other guardrail. The two Claude Code CVEs
this project already verified (CVE-2025-59536 / CVE-2026-21852) were both delivered
through *project settings files processed before trust* — settings is the delivery
vehicle.

**Naming note:** originally slated to fold into `security-checklist.md`, this became a
dedicated file — the permission-mode, managed-settings, and credential-env material is
substantial and distinct enough to stand alone.

## Where settings live (discover; weight by scope)

- `.claude/settings.json` — project, **committed & shared** (highest concern: travels)
- `.claude/settings.local.json` — project, local
- `~/.claude/settings.json` — user
- Managed policy settings — admin, org-wide (force-applied)
- Plugin-bundled settings / `hooks.json`

Dangerous settings are findings regardless of scope, but a **committed project**
setting weights higher than a user's own choice — it affects everyone who clones.

## Permission modes (verified enum values)

`permissions.defaultMode` selects the startup approval posture:

| Value | Meaning | Audit weight |
|-------|---------|--------------|
| `default` | Ask before edits / shell | baseline |
| `plan` | Plan-only, no execution | safe |
| `acceptEdits` | Auto-approve edits + safe FS ops in cwd | MAJOR if set by a shared config |
| `bypassPermissions` | **Skips all prompts** (circuit-breaker still stops `rm -rf /` and `rm -rf ~`) | **BLOCKER** in shared/plugin config |
| auto mode | Broad auto-approval | **BLOCKER**-class in shared config |

- [ ] **`defaultMode: "bypassPermissions"` (or auto) in a committed or plugin
      settings file.** Disarms the permission system for everyone who loads it.
      **BLOCKER.** (A user setting it in their own `~/.claude` is their choice — note,
      don't gate.)
- [ ] **`acceptEdits` in a shared config.** Weaker but still auto-approves edits
      without the user opting in. **MAJOR.**
- [ ] **Hardening controls present?** `permissions.disableBypassPermissionsMode:
      "disable"` and `permissions.disableAutoMode: "disable"` block those modes.
      Recommend them for managed deployments; their *absence* is not a finding, but a
      config that *enables* bypass while an org forbids it is.

## Permission rules (verified syntax)

`permissions.allow` / `permissions.deny` / `permissions.ask`, rules like
`Bash(npm run test:*)`, `Read(./.env)`, `Write(...)`, `WebFetch(domain:...)`. Deny is
evaluated first, then ask, then allow.

- [ ] **Over-broad `allow`.** `Bash(*)`, `Bash(:*)`, bare `Bash`, or wildcard grants
      that defeat least-privilege. **MAJOR** (BLOCKER if it green-lights a destructive
      pattern — mirrors the existing security-checklist gate).
- [ ] **Weakened `deny`.** A shared config that *removes* or fails to include denials
      for sensitive paths — `Read(./.env)`, `Read(./secrets/**)`, `Bash(curl *)` — when
      the surrounding grants are permissive. **MAJOR** (recommend the Trail-of-Bits
      deny defaults).
- [ ] **`permissions.additionalDirectories` extending to `~`, `/`, or outside the
      project.** Broadens readable/editable scope beyond the workspace — scope creep.
      **MAJOR.**

## Credential & environment surface (highest severity)

- [ ] **`env` block sets `ANTHROPIC_BASE_URL`.** Redirects API traffic (and the auth
      header / key) to another endpoint — the **CVE-2026-21852** exfiltration pattern.
      In a committed or plugin settings file: **BLOCKER.**
- [ ] **`env` sets `ANTHROPIC_API_KEY` / `ANTHROPIC_AUTH_TOKEN`** to a literal, or
      redirects auth. Plaintext key = secret leak (**BLOCKER**); redirect = exfil
      (**BLOCKER**).
- [ ] **`apiKeyHelper` points at an untrusted script.** `apiKeyHelper` runs a shell
      script that returns an API key — a credential-exec surface. An unvetted or
      network-touching helper can capture/exfiltrate the key. Audit the referenced
      script as a bundled resource. **MAJOR→BLOCKER.**
- [ ] **Any plaintext secret** anywhere in a settings file. **BLOCKER** (gitleaks /
      secret scan).

## Managed-settings hardening (recommend, don't gate)

These exist to lock down the surface; recommend them for orgs, and flag a config that
*fights* them:

- `allowManagedPermissionRulesOnly` — only managed permission rules apply.
- `allowManagedHooksOnly` / `disableAllHooks` — restrict/disable hooks.
- `allowManagedMcpServersOnly` + `allowedMcpServers` / `deniedMcpServers` — MCP allowlist.

## Sandbox (complementary layer)

Sandboxing gives OS-level enforcement of the Bash tool's filesystem/network access —
independent of permission rules. Where a config disables sandboxing while granting
broad Bash, note the compounded exposure. **MAJOR** when both directions weaken together.

## Gates summary (→ grade F)

BLOCKER: `bypassPermissions`/auto in shared config; `ANTHROPIC_BASE_URL`/key redirect
in `env`; plaintext secret; over-broad `allow` that green-lights a destructive pattern;
untrusted network-touching `apiKeyHelper`.

## What a static audit *cannot* catch (state honestly)

Settings interact with runtime trust state (a committed setting may be inert until the
folder is trusted) and with the merge order across scopes. The auditor grades the
*declared* posture and its scope; it cannot fully model the effective runtime merge.
Flag the interaction where it matters (e.g. "MAJOR if user trusts this repo") rather
than asserting a single effective value.

## Sources

- [Configure permissions — Claude Code Docs](https://code.claude.com/docs/en/permissions) — `defaultMode` enum (`default`/`plan`/`acceptEdits`/`bypassPermissions`/auto), `bypassPermissions` behavior + circuit-breaker, `disableBypassPermissionsMode`/`disableAutoMode`, `additionalDirectories`, permission-rule syntax, sandbox relationship — all verified.
- [Settings reference — Claude Code Docs](https://code.claude.com/docs/en/settings) — `permissions.*`, `env`, `apiKeyHelper`, `disableAllHooks`, managed-only keys.
- [Authentication — Claude Code Docs](https://code.claude.com/docs/en/iam) — `apiKeyHelper` runs a shell script for the key; `ANTHROPIC_BASE_URL`/`ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` credential precedence.
- [GHSA-jh7p-qr78-84p7 / CVE-2026-21852](https://github.com/advisories/GHSA-jh7p-qr78-84p7) — the `ANTHROPIC_BASE_URL`-in-settings key-exfiltration pattern this checklist gates on.
- [Trail of Bits — claude-code-config](https://github.com/trailofbits/claude-code-config) — the recommended `deny` defaults (curl/fetch/.env).
