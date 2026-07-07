#!/usr/bin/env python3
"""Deterministic checks for MCP servers and LSP servers (read-only).

Backs the surface-auditor subagent and the mcp-checklist. Each bundled MCP or
LSP server is a new tool surface plus a new trust boundary: a stdio server is a
child process Claude Code spawns locally; a remote server is an external endpoint
that both receives data and returns model-visible content.

Graded against the OWASP MCP Top 10 (2025). A static config audit can only see
what the config declares — it cannot see the runtime tool descriptions, so tool
poisoning (MCP03) and rug-pulls are out of static reach and left to the semantic
pass. This script flags the config-level defects.

Reports objective hits only; never launches any server.

Usage:
    py -3 check_mcp.py [--root PATH ...] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import scan_targets
import check_security  # SECRET_PATTERNS, NETWORK
import check_hooks     # FETCH_EXEC (shared)

# npx/uvx/etc. launching an unpinned package = supply-chain / rug-pull surface (MCP04).
UNPINNED_RUNNER = re.compile(r"\b(npx|bunx|pnpm\s+dlx|uvx|pipx\s+run)\b", re.IGNORECASE)
YES_FLAG = re.compile(r"(^|\s)(-y|--yes)(\s|$)")
AT_LATEST = re.compile(r"@latest\b", re.IGNORECASE)
# A pinned package token looks like name@1.2.3 or @scope/name@1.2.3 (semver-ish).
PINNED_TOKEN = re.compile(r"@\d+\.\d+")


def _flatten_str(x):
    """Join a command + args (or any nested str/list) into one searchable string."""
    if isinstance(x, str):
        return x
    if isinstance(x, list):
        return " ".join(_flatten_str(i) for i in x)
    if isinstance(x, dict):
        return " ".join(_flatten_str(v) for v in x.values())
    return ""


def _secret_hits(mapping):
    """Yield secret labels found in the values of an env/headers mapping."""
    hits = []
    if isinstance(mapping, dict):
        for k, v in mapping.items():
            if not isinstance(v, str):
                continue
            for pat, label in check_security.SECRET_PATTERNS:
                if pat.search(v):
                    hits.append((k, label))
                    break
    return hits


def analyze(rec):
    findings = []
    cfg = rec.get("config", {})
    scope = rec["scope"]
    command = cfg.get("command", "")
    args = cfg.get("args", [])
    url = cfg.get("url", "")
    cmd_line = (command + " " + _flatten_str(args)).strip()

    # ── BLOCKER ──
    if command and check_hooks.FETCH_EXEC.search(cmd_line):
        findings.append(("BLOCKER", "fetch-and-execute as the server launch command"))
    # Plaintext secret in env or headers. In a committed (repo) config this leaks
    # the credential to everyone with repo access (MCP01).
    for src in ("env", "headers"):
        for key, label in _secret_hits(cfg.get(src)):
            sev = "BLOCKER" if scope == "repo" else "MAJOR"
            findings.append((sev, f"plaintext secret ({label}) in {src}['{key}']" +
                             (" of a shared/committed config (MCP01)" if scope == "repo" else "")))

    # ── MAJOR ──
    if UNPINNED_RUNNER.search(cmd_line):
        if AT_LATEST.search(cmd_line) or (YES_FLAG.search(cmd_line) and not PINNED_TOKEN.search(cmd_line)):
            findings.append(("MAJOR", "unpinned package runner (@latest / -y with no version pin) - rug-pull / supply-chain surface (MCP04)"))
    if url.startswith("http://"):
        findings.append(("MAJOR", "remote server over plaintext http:// - use https"))

    # ── MINOR / informational ──
    if url and url.startswith("https://"):
        findings.append(("MINOR", "remote server: its responses are untrusted content (MCP06/MCP10) - treat model-visible output as untrusted"))

    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": scope,
        "plugin": rec.get("plugin"),
        "transport": "remote" if url else ("stdio" if command else "unknown"),
        "findings": findings,
    }


def main():
    ap = argparse.ArgumentParser(description="Deterministic MCP/LSP server checks (read-only).")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    roots = [Path(r).expanduser().resolve() for r in args.root] if args.root else None
    records = scan_targets.discover_plugins(roots)
    targets = [r for r in records if r["kind"] in ("mcp_server", "lsp_server")]
    results = [analyze(r) for r in targets]

    if args.json:
        json.dump({"results": results}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not results:
            print("No MCP or LSP servers found.")
        for res in results:
            loc = f"{res['plugin']}:" if res["plugin"] else ""
            print(f"\n{loc}{res['name']} ({res['kind']}, {res['transport']}):")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")


if __name__ == "__main__":
    main()
