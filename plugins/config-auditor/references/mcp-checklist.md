# MCP Server Checklist (DRAFT — research pass)

A plugin (or a repo's `.mcp.json`) can register MCP servers, and each one is a
**new tool surface plus a new trust boundary**. A local (`stdio`) server is a child
process Claude Code spawns on your machine; a remote (`http`/`sse`) server is an
external endpoint that both receives your data and returns model-visible content.
Either can carry the OWASP MCP Top-10 risk classes.

The honest scope limit up front: a **read-only config audit can only see what the
config declares** — the command, the URL, the env, the transport, the scope. It
**cannot** see the tool descriptions the server serves at runtime, so the two most
famous MCP attacks — *tool poisoning* and *rug-pulls* — are only partly auditable
statically. This checklist grades what the config reveals and flags the rest as
residual risk, rather than implying a clean bill of health.

## Where MCP servers are declared (discover all)

- `.mcp.json` — project-scoped, **committed and shared with the team** (highest
  static-audit value: secrets and untrusted servers travel with the repo)
- `~/.claude.json` — user-scoped
- Plugin-bundled MCP config — ships with the plugin
- Managed settings — admin-scoped

Fields to parse per server: `command` + `args` (stdio), `url` (remote), `type`/
transport, `env`, `headers`, `cwd`, and any auto-approval flags.

## OWASP MCP Top 10 (2025) — the mapping this checklist grades against

| ID | Risk | Statically auditable? |
|----|------|-----------------------|
| MCP01 | Token Mismanagement & Secret Exposure | **Yes** — secrets in `env`/`headers` |
| MCP02 | Privilege Escalation via Scope Creep | Partly — over-broad roots/env |
| MCP03 | Tool Poisoning | No (runtime descriptions) — flag residual |
| MCP04 | Supply-Chain & Dependency Tampering | **Yes** — unpinned command/args |
| MCP05 | Command Injection & Execution | **Yes** — fetch-and-execute command |
| MCP06 | Intent Flow Subversion | No — flag residual |
| MCP07 | Insufficient AuthN/AuthZ | Partly — plaintext/long-lived tokens |
| MCP08 | Lack of Audit & Telemetry | No — runtime concern, note only |
| MCP09 | Shadow MCP Servers | **Yes** — blanket auto-approve, unknown hosts |
| MCP10 | Context Injection & Over-Sharing | Partly — whole-env passthrough |

## Deterministic checks (a `check_mcp.py` can flag these)

- [ ] **Plaintext secret in `env` or `headers`** (API keys, `Authorization: Bearer …`
      tokens). In a **committed `.mcp.json`** this leaks the credential to everyone
      with repo access — MCP01. **BLOCKER** (defer to gitleaks / secret scan).
- [ ] **Fetch-and-execute as the server command.** `command` (or an `arg`) that is
      `curl …| bash`, `sh -c "$(curl …)"`, etc. — MCP05. **BLOCKER.**
- [ ] **Unpinned supply chain.** `npx -y <pkg>` with no version, `@latest`,
      `uvx <pkg>` unpinned, or a `pip install` of an unpinned package as the launch
      command. This is exactly the rug-pull / dependency-tampering surface (MCP04):
      the code that runs can change silently after approval. **MAJOR.**
- [ ] **Plain `http://` remote URL** (not `https://`). Cleartext transport for a
      channel carrying your data and returning model instructions. **MAJOR.**
- [ ] **Blanket auto-approval.** `enableAllProjectMcpServers: true` (verified real
      key) auto-approves *every* server in project `.mcp.json` files without
      per-server review — the shadow-server enabler (MCP09). **Scope the severity by
      where it is set** (trust-model nuance, verified against the docs): committed to
      a repo's `.claude/settings.json` it is **ignored in an untrusted folder** (the
      server stays Pending), so the real MAJOR is when a **user/global** setting turns
      on blanket approval, or once the user trusts the repo. A committed one is still
      a **MINOR** intent signal. The least-privilege alternative is
      `enabledMcpjsonServers` (allowlist specific servers by name), and
      `disabledMcpjsonServers` to reject.

## Semantic checks (model judgment)

- [ ] **Server-source trust.** Is the `command`/publisher or the remote `url` from a
      known, reputable source, or an unknown host/package? An unknown-provenance
      server is the root of MCP03/MCP09. **MAJOR** for unknown provenance.
- [ ] **Least-privilege scope (MCP02).** A filesystem server rooted at `/`, `$HOME`,
      or the whole repo when the job needs one subdirectory; a database server with
      write/admin creds when read is enough. Scope creep is the #2 OWASP risk.
      **MAJOR.**
- [ ] **Whole-environment passthrough (MCP01/MCP10).** Passing the process's full
      env (or broad secret-bearing vars) into the server instead of the specific
      vars it needs. **MAJOR.**
- [ ] **Long-lived / static tokens (MCP07).** A permanent API key in config vs. a
      short-lived or runtime-injected credential. **MAJOR.**
- [ ] **Remote server returning model-visible content = injection channel (MCP06/
      MCP10).** Any remote server's *responses* are untrusted content the model will
      read. This can't be neutralized in config, but a server whose whole purpose is
      to inject large context into every turn deserves scrutiny. **PLAUSIBLE.**

## Gates summary (→ grade F)

BLOCKER: plaintext secret in a committed MCP config; fetch-and-execute server
command. Both force F.

## What a static audit *cannot* catch (state honestly)

- **Tool poisoning (MCP03)** — malicious instructions live in the *tool descriptions*
  the server serves at connect time, not in the config. Invisible to a static pass.
- **Rug-pulls** — a server (or its unpinned package) can change behavior *after*
  approval; the config looks identical.
- **Cross-server shadowing** — a malicious server intercepting another's calls is a
  runtime, multi-server property.

For all three, the config-level mitigations are what the auditor should *recommend*,
since it cannot verify the runtime: **pin versions**, **prefer trusted publishers**,
**review tool descriptions at connect time**, **isolate untrusted servers**. Report
these as residual risk (PLAUSIBLE), never as a clean pass.

## Mitigations to recommend

- Pin every stdio server to an exact version; never `@latest`/`-y`-unpinned.
- Keep tokens out of committed config; inject at runtime, prefer short-lived.
- `https://` only for remote servers; scope filesystem/db servers to the minimum.
- Approve servers individually with `enabledMcpjsonServers`; avoid blanket
  `enableAllProjectMcpServers`. In managed settings, constrain with
  `allowedMcpServers` / `deniedMcpServers` (and `allowManagedMcpServersOnly`).
- Treat every remote server's output as untrusted content.

## Sources

- [OWASP MCP Top 10 (2025)](https://owasp.org/www-project-mcp-top-10/) / [index.md](https://github.com/OWASP/www-project-mcp-top-10/blob/main/index.md) — the MCP01–MCP10 risk taxonomy this checklist grades against.
- [MCP has prompt injection security problems — Simon Willison](https://simonwillison.net/2025/Apr/9/mcp-prompt-injection/) — tool poisoning via hidden description instructions, rug-pulls, cross-server shadowing, parameter exfiltration.
- [Connect Claude Code to tools via MCP — Claude Code Docs](https://code.claude.com/docs/en/mcp) — `.mcp.json` structure, stdio vs http/sse transports, `command`/`args`/`env`/`headers`, config scopes.
- [Settings reference — Claude Code Docs](https://code.claude.com/docs/en/settings) — verified keys: `enableAllProjectMcpServers`, `enabledMcpjsonServers`, `disabledMcpjsonServers`, `allowedMcpServers`, `deniedMcpServers`, `allowManagedMcpServersOnly`; and the trust-model nuance that committed auto-approve is ignored in untrusted folders.
- [OWASP MCP Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/MCP_Security_Cheat_Sheet.html) — defensive controls behind the least-privilege and auth findings.
