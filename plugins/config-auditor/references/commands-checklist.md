# Commands Checklist (DRAFT — research pass)

**Key fact that shapes this whole checklist (verified against the official docs):
custom commands have been *merged into skills*.** A flat file at
`.claude/commands/deploy.md` and a skill at `.claude/skills/deploy/SKILL.md` both
create `/deploy` and "work the same way"; a command is just a skill without a
directory. So a command is audited by the **same trigger / structure / security
dimensions** the auditor already applies to skills — the rubric and the existing
`antipattern-checklist.md` / `security-checklist.md` apply unchanged.

This file covers only the **delta**: the command-specific execution surface that a
directory-less `.md` prompt file carries and that a normal skill audit does not
already look at.

## Where commands live (discover)

- `.claude/commands/*.md` — repo-local (committed, shared)
- `~/.claude/commands/*.md` — user
- Plugin `commands/` directory, or paths named in the manifest `commands` field

Treat each as a skill of `kind: command` and run the standard trigger/structure/
security checks, plus the delta below.

## The delta — dynamic execution surface

### 1. `!` dynamic bash runs *before the model reads the file*

A line like `` !`git diff HEAD` `` (and ```` ```! ```` blocks) is **dynamic context
injection**: Claude Code *executes the command and inlines its output before Claude
sees the content*. This is auto-executed shell at command-load time — the same class
of surface as a hook, and it gets the same gates:

- [ ] **Fetch-and-execute inside a `!` block** — `` !`curl …| bash` ``, `` !`… | sh` ``.
      **BLOCKER.**
- [ ] **Reverse-shell / credential-read+egress inside a `!` block.** **BLOCKER.**
- [ ] **Destructive command inside a `!` block** without a guardrail (`rm -rf`, etc.).
      **BLOCKER** (same list as `security-checklist.md`).
- [ ] **Unexplained network egress in a `!` block.** **MAJOR.**

### 2. Argument interpolation into a `!` block = command injection (the signature command vuln)

Commands substitute user input via `$ARGUMENTS`, `$ARGUMENTS[N]`, and `$N`
(verified substitution tokens). When an untrusted argument is interpolated **into a
`` !`…` `` shell line**, the user's text becomes shell — classic OS command injection
(CWE-78).

- [ ] **`$ARGUMENTS` / `$N` appears inside a `` !`…` `` block or ```` ```! ```` block.**
      The argument reaches a shell unsanitized; `/cmd $(rm -rf ~)` executes. This is
      the highest-value command-specific finding. **BLOCKER** unless the argument is
      provably constrained (e.g. quoted *and* validated) — and even quoting is fragile,
      so prefer flagging. Recommend: never interpolate raw args into `!` blocks; pass
      them to the *model* as text, not to the shell.

### 3. Frontmatter fit (verified fields)

Commands use the same frontmatter as skills. The command-relevant fields:

- [ ] **`allowed-tools` least-privilege.** A command that only needs `Read Grep`
      should not grant `Bash`. Same rule as skills. **MAJOR** if over-broad.
- [ ] **`disable-model-invocation` fit.** A situational or destructive one-shot
      command (deploy, migrate, delete) that Claude could auto-trigger should set
      `disable-model-invocation: true` so it only runs on an explicit `/name`. This is
      the skill-vs-command fit modifier already in the rubric. **MAJOR** for a
      destructive command left model-invocable.
- [ ] **`shell: powershell`** changes the interpreter for `!` blocks — factor the OS
      into the injection analysis (PowerShell quoting ≠ bash quoting). **MINOR** note.
- [ ] **`disallowed-tools`** on autonomous/loop commands — confirm dangerous tools
      (e.g. `AskUserQuestion` in a background loop) are removed. **MINOR.**

## Gates summary (→ grade F)

BLOCKER: fetch-and-execute / reverse shell / destructive pattern inside a `!` block;
`$ARGUMENTS`/`$N` interpolated into a `!` block without provable constraint; plus all
the inherited skill gates (secret, unparseable frontmatter, reserved-word name, etc.).

## What a static audit *cannot* catch (state honestly)

`!` blocks that invoke a local script or an opaque binary hide their real behavior
from the `.md` — audit the referenced script as a bundled resource; flag an opaque
external binary as **PLAUSIBLE** residual risk, never a clean pass. Argument-injection
safety via quoting is genuinely hard to prove statically — when in doubt, flag.

## Sources

- [Skills / custom commands — Claude Code Docs](https://code.claude.com/docs/en/skills) — "custom commands have been merged into skills," the frontmatter reference (`allowed-tools`, `disable-model-invocation`, `arguments`, `shell`, `user-invocable`, `disallowed-tools`), `!` dynamic context injection, and the `$ARGUMENTS`/`$ARGUMENTS[N]`/`$N` substitution tokens — all verified verbatim.
- CWE-78 (OS Command Injection) — the framework behind the argument-into-`!`-block gate.
- `references/security-checklist.md` and `references/antipattern-checklist.md` — the inherited skill checks a command is also graded against.
