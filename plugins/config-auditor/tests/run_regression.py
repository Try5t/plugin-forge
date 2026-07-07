#!/usr/bin/env python3
"""Regression checks for the config-auditor scripts (read-only).

Run from anywhere:  python run_regression.py   (use `py -3` on Windows if the
bare `python`/`python3` resolve to the Microsoft Store stub.)

Guards against two bugs that produced false findings on valid skills:
  1. Folded / block YAML scalars (`description: >-`) with internal colons were
     misparsed into spurious keys and a truncated length — which also caused the
     real >1024 length gate to be MISSED (a false negative).
  2. Windows path separators (references\\notes.md) made every bundled resource a
     false "unreferenced" finding when the body links it as references/notes.md.

Exits non-zero if any check fails, so it can gate a commit or a change.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
FIXTURES = HERE / "fixtures"


def run(script):
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / script), "--root", str(FIXTURES), "--json"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"{script} failed to run:\n{proc.stderr}")
    return json.loads(proc.stdout)


def get(payload, name):
    for r in payload.get("targets", payload.get("results", [])):
        if r["name"] == name:
            return r
    raise AssertionError(f"target {name!r} not found in scan (fixtures missing?)")


def main():
    failures = []

    # 1. Folded scalar parses to full length, clean keys, no parse error.
    t = get(run("scan_targets.py"), "folded-scalar")
    desc = t["frontmatter"].get("description", "")
    if len(desc) <= 1024:
        failures.append(f"folded scalar: description length {len(desc)} <= 1024 (truncated by the parser?)")
    if set(t["frontmatter"].keys()) != {"name", "description", "license"}:
        failures.append(f"folded scalar: spurious frontmatter keys {list(t['frontmatter'].keys())}")
    if t["parse_error"]:
        failures.append(f"folded scalar: unexpected parse_error {t['parse_error']!r}")

    # 2. check_description trips the >1024 gate and does NOT emit a false 'no WHEN'.
    d = get(run("check_description.py"), "folded-scalar")
    msgs = [m for _, m in d["findings"]]
    if not any("1024" in m for m in msgs):
        failures.append("folded scalar: the >1024 length gate did NOT trip (false negative)")
    if any("WHEN" in m for m in msgs):
        failures.append("folded scalar: false 'no WHEN/trigger phrasing' finding")

    # 3. The forward-slash-linked resource is NOT flagged unreferenced (Windows path fix).
    s = get(run("check_structure.py"), "folded-scalar")
    if any("not referenced" in m for _, m in s["findings"]):
        failures.append(f"resource path: false 'unreferenced' finding {s['findings']}")

    # 4. Embedded-agent invocability: a non-plugin skill that spawns bundled agents is flagged.
    e = get(run("check_structure.py"), "embedded-agents")
    if not any("not invocable as subagents" in m for _, m in e["findings"]):
        failures.append(f"embedded-agents: phantom-capability check did NOT fire; findings={e['findings']}")

    if failures:
        print("REGRESSION FAILURES:")
        for f in failures:
            print("  -", f)
        sys.exit(1)
    print("All regression checks passed.")


if __name__ == "__main__":
    main()
