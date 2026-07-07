#!/usr/bin/env python3
"""Security checks for every target (read-only).

Deterministic checks that back the security-auditor subagent:
  - allowed-tools / tools present (absence = MAJOR)
  - destructive command patterns in grants or scripts (BLOCKER)
  - plaintext secrets in body or scripts (BLOCKER) via gitleaks if present,
    regex fallback otherwise
  - unexplained network egress signals (MAJOR hint)

Tuned to prefer false positives over false negatives. Judgment is left to the
subagent; this script reports objective hits only. It never executes any
matched command — it only detects and reports.

Usage:
    python3 check_security.py [--root PATH ...] [--json]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import scan_targets

DESTRUCTIVE = [
    (re.compile(r"\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r"), "rm -rf"),
    (re.compile(r"\bdd\s+if="), "dd if="),
    (re.compile(r"\bmkfs\b"), "mkfs"),
    (re.compile(r"\bchmod\s+-R\s+777"), "chmod -R 777"),
    (re.compile(r"\bchown\s+-R\b"), "chown -R"),
    (re.compile(r":\(\)\s*\{\s*:\|:&\s*\}\s*;\s*:"), "fork bomb"),
    (re.compile(r"\bgit\s+push\s+.*--force"), "git push --force"),
    (re.compile(r"\bfind\b[^\n]*-delete"), "find -delete"),
]

NETWORK = re.compile(r"\b(curl|wget|nc|netcat|fetch\()\b")

# Regex fallback secret patterns (used only when gitleaks is absent).
SECRET_PATTERNS = [
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"), "private key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{20,}"), "API key (sk- prefix)"),
    (re.compile(r"(?i)\b(password|passwd|secret|token)\s*[:=]\s*['\"][^'\"]{6,}"), "hardcoded credential"),
    (re.compile(r"ghp_[A-Za-z0-9]{30,}"), "GitHub token"),
]

GATE_TOOLS = ("allowed-tools", "tools")


def gather_text(rec):
    """Return concatenated body + script text and a per-file map for locating hits."""
    md_path = Path(rec["path"])
    target_dir = md_path.parent
    files = {str(md_path): ""}
    try:
        files[str(md_path)] = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        pass
    for res in rec["resources"]:
        if res.startswith("scripts/"):
            p = target_dir / res
            try:
                files[str(p)] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
    return files


def run_gitleaks(target_dir: Path):
    """Return list of secret findings via gitleaks, or None if gitleaks absent."""
    if not shutil.which("gitleaks"):
        return None
    try:
        proc = subprocess.run(
            ["gitleaks", "detect", "--no-git", "--source", str(target_dir),
             "--report-format", "json", "--report-path", "/dev/stdout"],
            capture_output=True, text=True, timeout=60,
        )
        out = proc.stdout.strip()
        if not out:
            return []
        data = json.loads(out)
        return [f"{f.get('RuleID','secret')} in {f.get('File','?')}" for f in data]
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError):
        return None


def check_target(rec):
    findings = []
    fm = rec["frontmatter"]

    # Tool grant presence.
    grant = None
    for key in GATE_TOOLS:
        if key in fm:
            grant = fm[key]
            break
    if grant is None:
        findings.append(("MAJOR", "no allowed-tools/tools restriction; inherits full tool surface"))

    files = gather_text(rec)

    # Destructive patterns in grant and in scripts.
    grant_text = grant or ""
    for path, text in files.items():
        haystack = text if path.endswith(".py") else text
        for pat, label in DESTRUCTIVE:
            if pat.search(haystack) or pat.search(grant_text):
                findings.append(("BLOCKER", f"destructive pattern '{label}' present ({Path(path).name}); needs narrowing guardrail"))
                break

    # Network egress signal.
    for path, text in files.items():
        if NETWORK.search(text):
            findings.append(("MAJOR", f"network call signal in {Path(path).name}; confirm it is justified"))
            break

    # Secrets.
    target_dir = Path(rec["path"]).parent
    gl = run_gitleaks(target_dir)
    if gl is None:
        # regex fallback
        for path, text in files.items():
            for pat, label in SECRET_PATTERNS:
                if pat.search(text):
                    findings.append(("BLOCKER", f"possible secret ({label}) in {Path(path).name}"))
                    break
        secret_method = "regex-fallback"
    else:
        for hit in gl:
            findings.append(("BLOCKER", f"gitleaks: {hit}"))
        secret_method = "gitleaks"

    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": rec["scope"],
        "tool_grant": grant,
        "secret_scan": secret_method,
        "findings": findings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.root:
        roots = [Path(r).expanduser().resolve() for r in args.root]
        roots_by_kind = {"skill": roots, "standalone_agent": roots}
    else:
        roots_by_kind = scan_targets.default_roots()

    records = scan_targets.discover(roots_by_kind)
    results = [check_target(r) for r in records]

    if args.json:
        json.dump({"results": results}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        for res in results:
            print(f"\n{res['name']} ({res['kind']}) [secrets: {res['secret_scan']}]:")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")


if __name__ == "__main__":
    main()
