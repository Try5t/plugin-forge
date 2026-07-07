#!/usr/bin/env python3
"""Check description and name quality for every target (read-only).

Deterministic checks that back the trigger-analyst subagent:
  - description length (gate at 1024), presence, XML tags
  - name length (gate at 64), kebab-case, directory match
  - point-of-view signal (second person / bare gerund vs. third person)
  - WHEN / trigger-phrase presence
  - key-use-case front-loading for the HUMAN skill listing (unverified ~250-char
    UI cutoff; NOT a triggering limit — the model is given the full description)

Emits per-target findings with a severity hint. Judgment calls are left to the
subagent; this script only reports what is objectively measurable.

Usage:
    python3 check_description.py [--root PATH ...] [--json]
"""

import argparse
import json
import re
import sys

import scan_targets

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
XML_TAG = re.compile(r"<[a-zA-Z/][^>]*>")
SECOND_PERSON = re.compile(r"\b(you|your|yourself)\b", re.IGNORECASE)
WHEN_SIGNAL = re.compile(
    r"\b(when|use (this|it)|should be used|whenever|if the user|for tasks?)\b",
    re.IGNORECASE,
)
# Unverified heuristic for the HUMAN skill-listing display only (discoverability).
# NOT a triggering limit: per the official docs the model is given the FULL
# description for skill selection, so length does not gate triggering. A real
# listing truncation does exist (GitHub issue #881), but the exact ~250 figure
# comes from secondary sources, not the official Anthropic docs. Front-loading
# the key use case is good practice regardless; the finding is MINOR by design.
LISTING_CUTOFF = 250


def check_target(rec):
    findings = []
    fm = rec["frontmatter"]
    name = fm.get("name", "")
    desc = fm.get("description", "")

    # name gates
    if not name:
        findings.append(("BLOCKER", "name missing"))
    else:
        # 64-char max and kebab-case are DOCUMENTED for skills (Skill frontmatter
        # spec); for agents the SDK docs specify no such constraint, so there they
        # are a convention (MAJOR), not a hard gate.
        name_sev = "BLOCKER" if rec["kind"] == "skill" else "MAJOR"
        if len(name) > 64:
            findings.append((name_sev, f"name too long ({len(name)} > 64)"))
        if not KEBAB.match(name):
            findings.append((name_sev, "name not kebab-case (lowercase, digits, hyphens)"))
        # Skill names may not contain the reserved words anthropic/claude (spec).
        if rec["kind"] == "skill" and re.search(r"\b(anthropic|claude)\b", name, re.IGNORECASE):
            findings.append(("BLOCKER", "name contains a reserved word (anthropic/claude)"))
        # name==directory is a CONVENTION, not a documented hard requirement: the
        # official example uses name 'pdf-processing' in a 'pdf/' directory. A
        # mismatch is confusing (Claude Code addresses a skill by its folder name),
        # so it is a MAJOR, not a grade-F gate.
        if name != rec["dir_name"] and rec["kind"] == "skill":
            findings.append(("MAJOR", f"name '{name}' != directory '{rec['dir_name']}' (convention mismatch; Claude Code uses the folder name)"))

    # description gates + quality
    if not desc:
        findings.append(("BLOCKER", "description missing"))
        return {"name": rec["name"], "kind": rec["kind"], "findings": findings}

    if len(desc) > 1024:  # official hard max per the Skill frontmatter spec
        findings.append(("BLOCKER", f"description too long ({len(desc)} > 1024)"))
    if XML_TAG.search(desc):
        findings.append(("BLOCKER", "description contains XML/HTML tags"))

    if SECOND_PERSON.search(desc):
        findings.append(("MAJOR", "description uses second person; prefer third person"))
    if not WHEN_SIGNAL.search(desc):
        findings.append(("MAJOR", "description has no explicit WHEN/trigger phrasing"))
    if len(desc) > LISTING_CUTOFF and not WHEN_SIGNAL.search(desc[:LISTING_CUTOFF]):
        findings.append(("MINOR", f"key use case may fall past ~{LISTING_CUTOFF} chars in the human skill listing (discoverability only; the model sees the full description for triggering)"))
    if len(desc) < 40:  # heuristic: no official minimum, but sub-40-char descriptions are usually too vague
        findings.append(("MAJOR", f"description very short ({len(desc)} chars); likely too vague to trigger reliably"))

    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": rec["scope"],
        "description_length": len(desc),
        "findings": findings,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.root:
        from pathlib import Path
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
            print(f"\n{res['name']} ({res['kind']}):")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")


if __name__ == "__main__":
    main()
