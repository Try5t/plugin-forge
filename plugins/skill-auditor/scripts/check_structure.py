#!/usr/bin/env python3
"""Check structure and progressive disclosure for every target (read-only).

Deterministic checks that back the structure-analyst subagent:
  - SKILL.md body line count (warn >500, ideal <300)
  - bundled resources vs. resources actually referenced from the body
  - phantom tools: scripts referenced in the body but not shipped
  - embedded agents that are not invocable (agents/ subdir in a non-plugin skill)
  - large reference files without a table of contents (>300 lines)

Usage:
    python3 check_structure.py [--root PATH ...] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

import scan_targets

# Heuristics (progressive-disclosure guidance), NOT official limits: keep the
# SKILL.md body lean so it does not bloat context on every trigger. Tune freely.
BODY_WARN = 500
BODY_IDEAL = 300
REF_TOC_THRESHOLD = 300
SCRIPT_REF = re.compile(r"(?:scripts/|\./)?([A-Za-z0-9_\-]+\.py)")


def read_body(md_path: Path) -> str:
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    parts = text.split("---", 2)
    return parts[2] if len(parts) == 3 else text


def _is_plugin(target_dir: Path) -> bool:
    """True if the skill sits inside a Claude Code plugin (which DOES register its
    bundled agents). Checks the skill dir and a few ancestors for a manifest."""
    for d in [target_dir, *list(target_dir.parents)[:3]]:
        if (d / ".claude-plugin" / "plugin.json").is_file() or (d / "plugin.json").is_file():
            return True
    return False


def _agent_registered(stem: str) -> bool:
    """True if an agent by this filename stem is installed where Claude Code
    actually loads agents from (global or repo `.claude/agents/`)."""
    for base in (Path.home() / ".claude" / "agents", Path.cwd() / ".claude" / "agents"):
        if (base / f"{stem}.md").is_file():
            return True
    return False


def check_target(rec):
    findings = []
    md_path = Path(rec["path"])
    target_dir = md_path.parent
    body = read_body(md_path)

    # Body size (skills mainly; agents are usually short by design).
    if rec["kind"] == "skill":
        if rec["body_lines"] > BODY_WARN:
            findings.append(("MAJOR", f"SKILL.md body {rec['body_lines']} lines (> {BODY_WARN}); move detail into references/"))
        elif rec["body_lines"] > BODY_IDEAL:
            findings.append(("MINOR", f"SKILL.md body {rec['body_lines']} lines (> {BODY_IDEAL} ideal)"))

    # Referenced vs. shipped resources.
    referenced = set()
    for res in rec["resources"]:
        base = res.split("/")[-1]
        if base in body or res in body:
            referenced.add(res)
    unreferenced = [r for r in rec["resources"] if r not in referenced
                    and not r.startswith("assets/")
                    and not r.startswith("agents/")]
    if unreferenced:
        findings.append(("MINOR", f"bundled resources not referenced from body: {', '.join(unreferenced)}"))

    # Phantom tools: .py referenced in body but not present.
    shipped = {r.split("/")[-1] for r in rec["resources"] if r.endswith(".py")}
    for m in SCRIPT_REF.finditer(body):
        script = m.group(1)
        if script not in shipped:
            findings.append(("MAJOR", f"body references script '{script}' that is not shipped (phantom tool)"))
            break

    # Embedded agents Claude Code cannot actually invoke. Agents load only from
    # ~/.claude/agents/ (or a plugin), NOT from a skill's agents/ subdir — so a
    # non-plugin skill that spawns its embedded agents has a phantom capability.
    if rec["kind"] == "skill":
        embedded = [r for r in rec["resources"] if r.startswith("agents/") and r.endswith(".md")]
        if embedded and not _is_plugin(target_dir):
            stems = [r.split("/")[-1][:-3] for r in embedded]
            unregistered = [s for s in stems if not _agent_registered(s)]
            if unregistered:
                refs_them = bool(re.search(r"\b(spawn|delegate|sub-?agent|Agent tool)\b", body, re.IGNORECASE)) \
                            or any(s in body for s in unregistered)
                sev = "MAJOR" if refs_them else "MINOR"
                note = "body spawns them -> phantom capability" if refs_them else "confirm they are reference-only"
                findings.append((sev, f"embedded agents not invocable as subagents ({note}); skill is "
                                       f"not a plugin and they are not in ~/.claude/agents/: "
                                       f"{', '.join(unregistered)}. Move them to ~/.claude/agents/ or package as a plugin"))

    # Large reference files without a TOC.
    for res in rec["resources"]:
        if res.startswith("references/") and res.endswith(".md"):
            rp = target_dir / res
            try:
                rlines = rp.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            if len(rlines) > REF_TOC_THRESHOLD:
                head = "\n".join(rlines[:40]).lower()
                if "contents" not in head and "## " not in "\n".join(rlines[:15]):
                    findings.append(("MINOR", f"{res} is {len(rlines)} lines with no table of contents"))

    # TODO / placeholder remnants.
    if re.search(r"\bTODO\b|\bFIXME\b|__PLACEHOLDER__|\bTBD\b", body):
        findings.append(("MAJOR", "body contains TODO/FIXME/placeholder remnants"))

    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": rec["scope"],
        "body_lines": rec["body_lines"],
        "resource_count": len(rec["resources"]),
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
            print(f"\n{res['name']} ({res['kind']}, {res['body_lines']}L):")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")


if __name__ == "__main__":
    main()
