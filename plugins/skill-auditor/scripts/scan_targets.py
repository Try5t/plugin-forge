#!/usr/bin/env python3
"""Discover and parse Claude Code skills and agents (read-only).

Scans four default roots plus embedded agents inside skills:
  ~/.claude/skills/      global skills
  .claude/skills/        repo-local skills
  ~/.claude/agents/      global standalone agents
  .claude/agents/        repo-local standalone agents
  <skill>/agents/        embedded agents inside any discovered skill

Emits one record per target with parsed frontmatter, body line count, and
bundled resources. The skill-auditor's own files are excluded so it never audits
itself.

Usage:
    python3 scan_targets.py [--root PATH ...] [--json]

With no --root, the four defaults are used. --root replaces the defaults.
This script never writes or mutates anything.
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Names belonging to the auditor itself — excluded from every scan.
SELF_EXCLUDE = {
    "skill-auditor",
    "trigger-analyst",
    "structure-analyst",
    "security-auditor",
    "agent-analyst",
}


def default_roots():
    home = Path.home()
    cwd = Path.cwd()
    return {
        "skill": [home / ".claude" / "skills", cwd / ".claude" / "skills"],
        "standalone_agent": [home / ".claude" / "agents", cwd / ".claude" / "agents"],
    }


def scope_of(path: Path) -> str:
    try:
        path.relative_to(Path.home())
        # Under home AND under cwd would be ambiguous; treat cwd-relative first.
    except ValueError:
        pass
    try:
        path.relative_to(Path.cwd())
        return "repo"
    except ValueError:
        return "global"


def parse_frontmatter(md_path: Path):
    """Return (frontmatter_dict, body_line_count, parse_error_or_None).

    Minimal YAML frontmatter parser: handles the flat key: value pairs that
    skill/agent frontmatter uses. Avoids a PyYAML dependency so the script runs
    anywhere. Values are kept as raw strings.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {}, 0, f"unreadable: {e}"

    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, len(lines), "missing frontmatter delimiter"

    fm = {}
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, len(lines), "unterminated frontmatter"

    current_key = None
    for raw in lines[1:end]:
        if not raw.strip():
            continue
        # An indented line under a key is a CONTINUATION of that key's value
        # (folded text, a block scalar, or a list item) — even if it contains a
        # colon. Only a non-indented line starts a new key. (Previously an
        # indented line with a colon — a block-scalar description, or a
        # `Bash(git status:*)` list item — was misparsed as a spurious new key.)
        if raw[:1] in (" ", "\t") and current_key is not None:
            fm[current_key] = (fm[current_key] + " " + raw.strip()).strip()
            continue
        if ":" not in raw:
            return fm, len(lines) - end - 1, f"malformed frontmatter line: {raw!r}"
        key, _, value = raw.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Block-scalar indicator: the real value is on the following indented lines.
        if value in ("|", ">", "|-", ">-", "|+", ">+"):
            value = ""
        fm[key] = value
        current_key = key

    body_lines = len(lines) - end - 1
    return fm, body_lines, None


def list_resources(target_dir: Path):
    resources = []
    for sub in ("scripts", "references", "assets", "agents"):
        d = target_dir / sub
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    # Normalize OS separators to '/' so downstream membership
                    # checks match forward-slash markdown links in the body
                    # (otherwise every resource is a false "unreferenced"
                    # positive on Windows).
                    resources.append(str(f.relative_to(target_dir)).replace("\\", "/"))
    return resources


def make_record(md_path: Path, kind: str):
    target_dir = md_path.parent
    fm, body_lines, err = parse_frontmatter(md_path)
    name = fm.get("name", target_dir.name)
    return {
        "name": name,
        "dir_name": target_dir.name,
        "kind": kind,
        "scope": scope_of(md_path),
        "path": str(md_path),
        "frontmatter": fm,
        "body_lines": body_lines,
        "parse_error": err,
        "resources": list_resources(target_dir),
    }


def discover(roots_by_kind):
    records = []
    seen = set()

    # Skills: each subdirectory with a SKILL.md.
    for root in roots_by_kind.get("skill", []):
        if not root.is_dir():
            continue
        for skill_md in sorted(root.glob("*/SKILL.md")):
            if skill_md.parent.name in SELF_EXCLUDE:
                continue
            if str(skill_md) in seen:
                continue
            seen.add(str(skill_md))
            rec = make_record(skill_md, "skill")
            records.append(rec)
            # Embedded agents inside this skill.
            emb_dir = skill_md.parent / "agents"
            if emb_dir.is_dir():
                for agent_md in sorted(emb_dir.glob("*.md")):
                    if agent_md.stem in SELF_EXCLUDE:
                        continue
                    if str(agent_md) in seen:
                        continue
                    seen.add(str(agent_md))
                    arec = make_record(agent_md, "embedded_agent")
                    arec["parent_skill"] = rec["name"]
                    records.append(arec)

    # Standalone agents: *.md files directly under an agents root.
    for root in roots_by_kind.get("standalone_agent", []):
        if not root.is_dir():
            continue
        for agent_md in sorted(root.glob("*.md")):
            if agent_md.stem in SELF_EXCLUDE:
                continue
            if str(agent_md) in seen:
                continue
            seen.add(str(agent_md))
            records.append(make_record(agent_md, "standalone_agent"))

    return records


def main():
    ap = argparse.ArgumentParser(description="Discover Claude Code skills and agents (read-only).")
    ap.add_argument("--root", action="append", default=None,
                    help="Override discovery root(s). Repeatable. Replaces defaults. "
                         "Skill roots and agent roots are auto-detected by folder layout.")
    ap.add_argument("--json", action="store_true", help="Emit JSON.")
    args = ap.parse_args()

    if args.root:
        # When roots are given explicitly, scan each for both skills and agents.
        roots = [Path(r).expanduser().resolve() for r in args.root]
        roots_by_kind = {"skill": roots, "standalone_agent": roots}
    else:
        roots_by_kind = default_roots()

    records = discover(roots_by_kind)

    if args.json:
        json.dump({"count": len(records), "targets": records}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Found {len(records)} target(s):")
        for r in records:
            err = f"  [PARSE ERROR: {r['parse_error']}]" if r["parse_error"] else ""
            print(f"  - {r['name']} ({r['kind']}, {r['scope']}) "
                  f"body={r['body_lines']}L{err}")


if __name__ == "__main__":
    main()
