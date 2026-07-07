#!/usr/bin/env python3
"""Detect trigger and delegation collisions across all targets (read-only).

Compares every pair of descriptions and flags pairs whose token overlap is high
enough that they likely compete for the same trigger (skills) or delegation
(agents). Overlap alone is not proof of a collision - the subagent decides
whether an explicit exclusion clause resolves it - but it surfaces the pairs
worth looking at.

Uses Jaccard similarity over content tokens (stopwords removed). Default
threshold 0.35; tune with --threshold.

Usage:
    python3 detect_collisions.py [--root PATH ...] [--threshold F] [--json]
"""

import argparse
import difflib
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import scan_targets

STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "when",
    "this", "that", "it", "is", "are", "be", "used", "use", "user", "should",
    "skill", "agent", "claude", "if", "as", "by", "at", "from", "into", "any",
    "not", "no", "do", "does", "will", "can", "may", "s", "asks", "wants",
    "mentions", "whenever", "even", "they", "their", "them",
}
TOKEN = re.compile(r"[a-z0-9][a-z0-9\-]+")
EXCLUSION = re.compile(r"\b(do not use|don't use|not for|instead of|rather than|except)\b", re.IGNORECASE)


def tokens(desc: str):
    return {t for t in TOKEN.findall(desc.lower()) if t not in STOPWORDS and len(t) > 2}


def jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def read_body(path: str) -> str:
    """Return the target's body (frontmatter stripped), whitespace-normalized."""
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            lines = lines[end + 1:]
    return re.sub(r"\s+", " ", "\n".join(lines)).strip()


def name_conflicts(records):
    """Same name in more than one location.

    Independent of description similarity ON PURPOSE: content divergence LOWERS
    description overlap, so the Jaccard path misses exactly the dangerous case -
    a same-named target whose two copies have drifted apart (e.g. one edited, one
    stale, or two different languages). Which copy actually runs is undefined, so
    this is flagged even (especially) when the descriptions no longer look alike.
    """
    by_name = defaultdict(list)
    for r in records:
        by_name[r["name"]].append(r)

    out = []
    for name, recs in sorted(by_name.items()):
        if len(recs) < 2:
            continue
        for x, y in combinations(recs, 2):
            bx, by = read_body(x["path"]), read_body(y["path"])
            dx = x["frontmatter"].get("description", "")
            dy = y["frontmatter"].get("description", "")
            differs = [f for f, same in (("description", dx == dy), ("body", bx == by)) if not same]
            identical = not differs
            out.append({
                "name": name,
                "a_path": x["path"], "a_scope": x["scope"], "a_kind": x["kind"],
                "b_path": y["path"], "b_scope": y["scope"], "b_kind": y["kind"],
                "type": "cross-scope-identical" if identical else "cross-scope-divergent",
                "severity": "MINOR" if identical else "MAJOR",
                "body_similarity": round(difflib.SequenceMatcher(None, bx, by).ratio(), 3),
                "differs_in": differs,
                "note": ("same name in two locations, byte-identical - redundant copy, "
                         "pick one source of truth" if identical else
                         "same name in two locations with DIFFERENT content - which copy "
                         "runs is undefined; reconcile or delete one"),
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--threshold", type=float, default=0.35)  # heuristic Jaccard cutoff; overlap is not proof, the model adjudicates
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.root:
        roots = [Path(r).expanduser().resolve() for r in args.root]
        roots_by_kind = {"skill": roots, "standalone_agent": roots}
    else:
        roots_by_kind = scan_targets.default_roots()

    records = scan_targets.discover(roots_by_kind)
    enriched = []
    for r in records:
        desc = r["frontmatter"].get("description", "")
        enriched.append({
            "name": r["name"],
            "kind": r["kind"],
            "scope": r["scope"],
            "path": r["path"],
            "tokens": tokens(desc),
            "has_exclusion": bool(EXCLUSION.search(desc)),
        })

    collisions = []
    for x, y in combinations(enriched, 2):
        sim = jaccard(x["tokens"], y["tokens"])
        if sim >= args.threshold:
            # Same-name across scopes is a cross-scope duplicate, not just overlap.
            duplicate = x["name"] == y["name"] and x["scope"] != y["scope"]
            severity = "MAJOR"
            kind = "cross-scope-duplicate" if duplicate else "trigger-overlap"
            resolved = x["has_exclusion"] and y["has_exclusion"]
            collisions.append({
                "a": x["name"], "a_scope": x["scope"], "a_kind": x["kind"],
                "b": y["name"], "b_scope": y["scope"], "b_kind": y["kind"],
                "similarity": round(sim, 3),
                "type": kind,
                "severity": severity,
                "exclusion_present_on_both": resolved,
                "note": "both carry an exclusion clause; may be resolved" if resolved
                        else "no mutual exclusion clause; likely competes",
            })

    collisions.sort(key=lambda c: c["similarity"], reverse=True)

    conflicts = name_conflicts(records)

    if args.json:
        json.dump({"threshold": args.threshold, "collisions": collisions,
                   "name_conflicts": conflicts}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not collisions:
            print(f"No description-overlap collisions at threshold {args.threshold}.")
        for c in collisions:
            print(f"[{c['severity']}] {c['type']} sim={c['similarity']}: "
                  f"{c['a']} ({c['a_scope']}) <-> {c['b']} ({c['b_scope']}) - {c['note']}")
        if not conflicts:
            print("No same-name cross-scope conflicts.")
        for c in conflicts:
            print(f"[{c['severity']}] {c['type']} '{c['name']}' "
                  f"(body_sim={c['body_similarity']}, differs_in={c['differs_in']}): "
                  f"{c['a_path']} <-> {c['b_path']} - {c['note']}")


if __name__ == "__main__":
    main()
