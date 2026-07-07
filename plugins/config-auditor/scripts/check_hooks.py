#!/usr/bin/env python3
"""Deterministic security checks for hooks and monitors (read-only).

Backs the surface-auditor subagent and the hooks-checklist. Hooks (`command`
type) and monitors are arbitrary shell that Claude Code executes itself,
automatically, with the user's privileges - the sharpest surface a plugin can
carry. This script flags the objective danger patterns; a monitor `command` is
graded with the exact same gates as a hook `command`.

Anchored on CVE-2025-59536 (code-exec before the trust dialog; SessionStart the
demonstrated vehicle) and CVE-2026-21852 (ANTHROPIC_BASE_URL key redirect). Both
are patched in current Claude Code - this detects the *attack pattern* an
untrusted plugin/repo can still carry, not the client bug.

Tuned to prefer false positives over false negatives. Reports objective hits
only; never executes any matched command.

Usage:
    py -3 check_hooks.py [--root PATH ...] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import scan_targets
import check_security  # reuse DESTRUCTIVE, SECRET_PATTERNS, NETWORK

# Network fetch piped into an interpreter, or command-substituted into one.
FETCH_EXEC = re.compile(
    r"(curl|wget|fetch)\b[^\n|]*\|\s*(bash|sh|zsh|ksh|python[0-9.]*|node|perl|ruby)\b"
    r"|(bash|sh|zsh|python[0-9.]*|node)\s+-c\s*[\"']?\$\((curl|wget|fetch)",
    re.IGNORECASE,
)
REVERSE_SHELL = re.compile(
    r"/dev/tcp/|/dev/udp/|\bbash\s+-i\b|\bnc\b[^\n]*-e\b|\bsh\s+-i\b[^\n]*>&|"
    r"\bncat\b[^\n]*-e\b|\bmkfifo\b[^\n]*\|\s*(bash|sh)\b",
    re.IGNORECASE,
)
CRED_PATHS = re.compile(
    r"\.env\b|~/?\.ssh|\.ssh/|~/?\.aws|\.aws/credentials|\bid_rsa\b|\.npmrc|"
    r"\.git-credentials|\.netrc|\.docker/config|\.kube/config",
    re.IGNORECASE,
)
ANTHROPIC_ENV = re.compile(r"ANTHROPIC_BASE_URL|ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN")
OBFUSCATION = re.compile(
    r"base64\s+(-d|--decode|-D)\b|\beval\b|(\\x[0-9a-fA-F]{2}){3,}|"
    r"echo\s+[A-Za-z0-9+/=]{24,}\s*\|\s*base64",
)
URL_LITERAL = re.compile(r"https?://[^\s\"'`)]+")
SHELL_METACHARS = re.compile(r"[|&;><`]|\$\(")


def command_of(rec):
    """Return (command_string, http_url_or_None) for a hook/monitor record."""
    cfg = rec.get("config", {})
    if rec["kind"] == "monitor":
        return cfg.get("command", ""), None
    # hook handler
    htype = rec.get("handler_type") or cfg.get("type", "command")
    if htype == "http":
        return "", cfg.get("url", "")
    return cfg.get("command", "") or "", None


def analyze(rec):
    findings = []
    cfg = rec.get("config", {})
    event = rec.get("event", "")
    matcher = rec.get("matcher", "")
    htype = rec.get("handler_type") or cfg.get("type", "command")
    cmd, http_url = command_of(rec)
    hay = cmd or ""

    # ── BLOCKER-class command content ──
    if FETCH_EXEC.search(hay):
        findings.append(("BLOCKER", "fetch-and-execute (network fetch piped/substituted into a shell)"))
    if REVERSE_SHELL.search(hay):
        findings.append(("BLOCKER", "reverse-shell / remote-shell pattern"))
    if CRED_PATHS.search(hay) and (check_security.NETWORK.search(hay) or URL_LITERAL.search(hay)):
        findings.append(("BLOCKER", "credential-path read combined with network egress"))
    if ANTHROPIC_ENV.search(hay):
        findings.append(("BLOCKER", "ANTHROPIC_BASE_URL/API-key override (CVE-2026-21852 key-redirect pattern)"))
    for pat, label in check_security.DESTRUCTIVE:
        if pat.search(hay):
            findings.append(("BLOCKER", f"destructive pattern '{label}' in hook/monitor command"))
            break
    for pat, label in check_security.SECRET_PATTERNS:
        if pat.search(hay):
            findings.append(("BLOCKER", f"possible plaintext secret ({label}) in hook/monitor command"))
            break
    # Trust-timing: an auto-firing pre-trust event with an external side effect.
    if event in ("SessionStart", "Setup") and (URL_LITERAL.search(hay) or check_security.NETWORK.search(hay)):
        findings.append(("BLOCKER", f"{event} hook with network side effect (pre-trust auto-exec; CVE-2025-59536 class)"))

    # ── MAJOR-class ──
    if OBFUSCATION.search(hay):
        findings.append(("MAJOR", "obfuscated command body (base64/eval/hex) - decode and re-inspect"))
    if URL_LITERAL.search(hay) and not any(f[0] == "BLOCKER" for f in findings):
        findings.append(("MAJOR", "external URL literal in command - confirm purpose / not exfiltration"))
    # Shell-form vs exec-form: exec-form sets "args"; shell-form with metachars is the injection surface.
    if rec["kind"] == "hook" and htype == "command" and "args" not in cfg and SHELL_METACHARS.search(hay):
        findings.append(("MAJOR", "shell-form command with shell metacharacters - prefer exec-form (args) to avoid injection"))
    if cfg.get("async") or cfg.get("asyncRewake"):
        findings.append(("MAJOR", "async/asyncRewake - may persist after Claude Code exits"))
    if htype == "http" and http_url:
        findings.append(("MAJOR", f"http handler posts event JSON to {http_url}; constrain with allowedHttpHookUrls / httpHookAllowedEnvVars"))
    if cfg.get("updatedInput") is not None or cfg.get("updatedToolOutput") is not None:
        findings.append(("MAJOR", "hook rewrites tool input/output - confirm benign (redaction), not injection"))
    # 'if:' relied upon - best-effort filter, fails open.
    if cfg.get("if") and (FETCH_EXEC.search(hay) or check_security.NETWORK.search(hay)):
        findings.append(("MAJOR", "'if:' filter is best-effort and fails open - do not rely on it for safety; use the permission system"))

    # ── MINOR ──
    mutating = htype == "command"
    if mutating and matcher in ("", "*") and rec["kind"] == "hook":
        findings.append(("MINOR", "broad matcher ('*'/empty) - scope the hook to the tools it needs"))
    if rec["kind"] == "hook" and htype == "command" and "timeout" not in cfg:
        findings.append(("MINOR", "no timeout set on command hook"))

    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": rec["scope"],
        "plugin": rec.get("plugin"),
        "event": event or None,
        "handler_type": htype,
        "findings": findings,
    }


def main():
    ap = argparse.ArgumentParser(description="Deterministic hook/monitor security checks (read-only).")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    roots = [Path(r).expanduser().resolve() for r in args.root] if args.root else None
    records = scan_targets.discover_plugins(roots)
    targets = [r for r in records if r["kind"] in ("hook", "monitor")]
    results = [analyze(r) for r in targets]

    if args.json:
        json.dump({"results": results}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not results:
            print("No hooks or monitors found.")
        for res in results:
            loc = f"{res['plugin']}:" if res["plugin"] else ""
            print(f"\n{loc}{res['name']} ({res['kind']}):")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")


if __name__ == "__main__":
    main()
