#!/usr/bin/env python3
"""Convenience runner for config-auditor's own trigger measurement.

Resolves the skill and the shipped eval set by path (so you don't have to), and
forwards to `trigger_eval.py`. Dry-run by default (shows the cost, makes NO
calls); pass --go to run the real measurement.

IMPORTANT: the real run makes `claude -p` calls, so it must run from a terminal
where Claude Code is authenticated (a plain `claude -p "hi"` must work). It does
NOT run inside a nested agent/sandbox session — there `claude -p` fails auth and
the eval aborts without a score by design.

Usage:
    py -3 run_trigger_eval.py            # dry-run: preview the cost
    py -3 run_trigger_eval.py --go       # real run (COSTS TOKENS)
    py -3 run_trigger_eval.py --go --repeats 3 --model claude-sonnet-5
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # <plugin>/scripts
PLUGIN = HERE.parent                             # <plugin>
SKILL = PLUGIN / "skills" / "config-auditor" / "SKILL.md"
EVALSET = PLUGIN / "tests" / "fixtures" / "config-auditor-evalset.json"
TRIGGER_EVAL = HERE / "trigger_eval.py"


def main():
    ap = argparse.ArgumentParser(description="Run config-auditor's own trigger measurement.")
    ap.add_argument("--go", action="store_true", help="Execute the real run (COSTS TOKENS). Omit for a dry-run preview.")
    ap.add_argument("--repeats", type=int, default=3, help="Calls per query (majority vote). Default 3.")
    ap.add_argument("--model", default=None, help="Model id passed to `claude -p`.")
    args = ap.parse_args()

    for p in (SKILL, EVALSET, TRIGGER_EVAL):
        if not p.is_file():
            print(f"ERROR: expected file not found: {p}", file=sys.stderr)
            sys.exit(2)

    cmd = [sys.executable, str(TRIGGER_EVAL),
           "--skill", str(SKILL), "--eval-set", str(EVALSET),
           "--repeats", str(args.repeats)]
    if args.model:
        cmd += ["--model", args.model]
    if not args.go:
        cmd += ["--dry-run"]
        print("[runner] dry-run (no calls). Re-run with --go to execute the real measurement.\n")

    sys.exit(subprocess.run(cmd).returncode)


if __name__ == "__main__":
    main()
