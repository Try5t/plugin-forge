#!/usr/bin/env bash
#
# FALLBACK for concept-review audit finding A.
#
# Run this ONLY IF the pre-cutover check fails — i.e. after you move the loose
# ~/.claude/skills/concept-doc-standard aside and reload, a spawned
# concept-review:concept-* agent reports "NO DOC STANDARD LOADED".
#
# It scopes the 12 concept-* agents' `skills:` dependency from the bare
# `concept-doc-standard` to the plugin-scoped `concept-review:concept-doc-standard`,
# so each agent resolves the plugin's own doc-standard, then validates + commits.
#
# Idempotent: re-running after it has applied does nothing.
#
set -e
REPO="C:/repos/plugin-forge"
AGENTS="$REPO/plugins/concept-review/agents"

echo "== scoping skills: field in the 12 concept-* agents =="
py -3 - "$AGENTS" <<'PY'
import sys, pathlib
d = pathlib.Path(sys.argv[1]); n = 0
for f in sorted(d.glob("concept-*.md")):
    t = f.read_text(encoding="utf-8")
    if "\n  - concept-doc-standard\n" in t:
        t = t.replace("\n  - concept-doc-standard\n",
                      "\n  - concept-review:concept-doc-standard\n")
        f.write_text(t, encoding="utf-8"); n += 1
print(f"scoped skills in {n} agent(s)")
PY

echo "== verify =="
grep -h "concept-doc-standard" "$AGENTS"/concept-*.md | sort | uniq -c

echo "== validate =="
claude plugin validate "$REPO" | grep -E "passed|error|Error" | head -1

git -C "$REPO" add -A
git -C "$REPO" commit -m "concept-review: scope agents' skills to concept-review:concept-doc-standard (finding-A fallback)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"

echo
echo "Done. Next:"
echo "  1. git -C $REPO push"
echo "  2. claude plugin update concept-review   (then /reload-plugins)"
echo "  3. Re-run the cutover probe: spawn concept-review:concept-po and confirm the"
echo "     doc-standard return format + filenames come back."
