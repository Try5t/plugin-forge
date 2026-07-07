# Security Checklist

Skills and agents are an instruction channel: every line in a SKILL.md or agent
file is treated as a directive, so a malicious or careless one can exfiltrate
data, run destructive commands, or carry a prompt injection. Audit accordingly.

Run the deterministic checks first — they are near-free and catch the
unambiguous defects at 100%. Then apply model judgment to the semantic questions
the scripts cannot settle. Tune the whole section asymmetrically: accept false
positives to drive false negatives toward zero. A wrongly flagged safe skill
costs a minute; a missed dangerous one costs far more.

## Deterministic checks (scripts/check_security.py)

- [ ] **`allowed-tools` present.** Absence means full inherited surface. Flag
      MAJOR. (Agents: same for the `tools` field.)
- [ ] **Least-privilege grant.** The grant should be the minimum for the stated
      job. Ask the reviewer's question: would a human intern in this role be
      handed production credentials? If not, the grant is too wide.
- [ ] **No destructive command patterns** in any grant or script: `rm -rf`,
      `dd if=`, `mkfs`, `chmod -R 777`, `chown -R`, fork bombs `:(){ :|:& };:`,
      unbounded `find … -delete`, `git push --force` to shared branches. Any hit
      without an explicit narrowing guardrail is a BLOCKER.
- [ ] **No plaintext secrets.** Delegate to `gitleaks` if installed; otherwise
      use the regex fallback (API-key shapes, `AKIA…`, private-key headers,
      `password=`, bearer tokens). Any hit is a BLOCKER.

## Semantic checks (subagent judgment)

- [ ] **Network calls are explicit and justified.** `curl`/`wget`/fetch to an
      external host must have a stated purpose tied to the skill's job. Unexplained
      egress is a prompt-injection / exfiltration vector. MAJOR.
- [ ] **No hidden instructions.** Long bundled reference or script files can
      carry directives far from the SKILL.md the user actually read. Scan bundled
      files, not just the top-level body. MAJOR.
- [ ] **No fetch-and-execute.** Instructions that download content and run it,
      or that pull a remote prompt and follow it, invert the trust model. MAJOR.
- [ ] **No environment-variable or credential exfiltration.** Reading env vars
      or credential files and then sending them anywhere (network, commit, log)
      is a critical pattern even if each step looks benign. MAJOR–BLOCKER.
- [ ] **No path traversal.** Reference paths that escape the skill directory
      (`../../…`) can reach unintended files. MINOR–MAJOR.
- [ ] **Write / destructive operations gated by a human.** Any mutating action
      should either require explicit user invocation
      (`disable-model-invocation: true`) or a confirmation step, not run
      autonomously. MAJOR.

## Why least-privilege is the primary mitigation

Prompt injection against skills is, at the model level, only partially solved:
detectors that look for "instructions inside data" fail because in a skill the
data *is* instructions. That means the durable defense is not detection but
constraint — a skill that was never granted a destructive or network tool cannot
be coerced into using one. This is why an empty or over-broad `allowed-tools` is
treated as a real finding, not a style nit: it is the difference between a
contained blast radius and an open one.

## Reporting security findings

Lead the per-target findings with any BLOCKER, then MAJOR, then MINOR. For each,
name the exact file and line where possible, the pattern matched, and the concrete
narrowing change (e.g. "replace `Bash` with `Bash(git status:*, git diff:*)`").
Never propose executing a fix in Phase 1 — only describe it.
