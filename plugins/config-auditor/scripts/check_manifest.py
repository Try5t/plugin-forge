#!/usr/bin/env python3
"""Deterministic checks for plugin manifests and settings/permission posture (read-only).

Backs the surface-auditor subagent and two checklists:
  - plugin-manifest-checklist.md — `.claude-plugin/plugin.json` hygiene and
    provenance (name, version pinning, dependency pinning, defaultEnabled vs the
    executable surface the plugin bundles). No plugin signing exists, so
    provenance reduces to "pin the version" + "trust the source".
  - settings-permissions-checklist.md — the permission/env posture in a
    settings.json: the keys that can widen Claude Code's own trust boundary
    (bypassPermissions, ANTHROPIC_BASE_URL redirect, apiKeyHelper, over-broad
    grants, blanket MCP approval).

Reports objective hits only; never runs anything (unless --validate is passed,
which shells out to the official `claude plugin validate --strict`).

Usage:
    py -3 check_manifest.py [--root PATH ...] [--json] [--validate]
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import scan_targets
import check_security  # SECRET_PATTERNS

KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ANTHROPIC_ENV = re.compile(r"ANTHROPIC_BASE_URL|ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN")
BROAD_BASH = re.compile(r"^Bash(\(\s*\*?\s*\)|\(:\*\))?$|^Bash\(\*\)$")

# Manifest keys whose presence means the plugin bundles auto-executing / external surface.
RISKY_CHILD_KINDS = {"hook", "mcp_server", "monitor", "lsp_server"}


def _secret_in(obj):
    """Deep-scan any JSON value's strings for secret patterns; yield labels."""
    hits = []

    def walk(x):
        if isinstance(x, str):
            for pat, label in check_security.SECRET_PATTERNS:
                if pat.search(x):
                    hits.append(label)
                    break
        elif isinstance(x, list):
            for i in x:
                walk(i)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)

    walk(obj)
    return hits


def analyze_manifest(rec, risky_plugins):
    findings = []
    cfg = rec.get("config", {})
    if rec.get("parse_error"):
        findings.append(("BLOCKER", f"manifest does not parse: {rec['parse_error']}"))
        return _result(rec, findings)

    name = cfg.get("name")
    if not name:
        findings.append(("MAJOR", "manifest missing 'name'"))
    elif not KEBAB.match(str(name)):
        findings.append(("MAJOR", f"plugin name '{name}' is not kebab-case / has spaces (breaks namespacing)"))

    # keywords wrong type is a documented hard load error.
    if "keywords" in cfg and not isinstance(cfg["keywords"], list):
        findings.append(("BLOCKER", "'keywords' must be an array (string value is a load error)"))

    # Version pinning (supply-chain).
    if not cfg.get("version"):
        findings.append(("MAJOR", "no 'version' - falls back to git SHA, so every commit is a new version (no rug-pull-resistant pin)"))

    # Dependency pinning.
    deps = cfg.get("dependencies")
    if isinstance(deps, list):
        for d in deps:
            if isinstance(d, dict) and not d.get("version"):
                findings.append(("MAJOR", f"dependency '{d.get('name','?')}' is unpinned (no version constraint)"))

    # defaultEnabled vs bundled risky surface.
    if rec["name"] in risky_plugins and cfg.get("defaultEnabled", True) is not False:
        findings.append(("MAJOR", "bundles hooks/MCP/monitors/LSP but does not ship defaultEnabled:false - risky surface auto-enables on install"))

    # Secret sitting in the manifest itself.
    for label in _secret_in(cfg):
        findings.append(("BLOCKER", f"possible plaintext secret ({label}) in manifest"))
        break

    return _result(rec, findings)


def analyze_settings(rec):
    findings = []
    cfg = rec.get("config", {})
    scope = rec["scope"]
    shared = scope in ("repo",) or rec.get("plugin") is not None
    if rec.get("parse_error"):
        findings.append(("MAJOR", f"settings file does not parse: {rec['parse_error']}"))
        return _result(rec, findings)

    perms = cfg.get("permissions", {}) if isinstance(cfg.get("permissions"), dict) else {}

    # Permission mode.
    mode = perms.get("defaultMode") or cfg.get("defaultMode")
    if mode in ("bypassPermissions", "auto"):
        if shared:
            findings.append(("BLOCKER", f"defaultMode '{mode}' in a shared/plugin config disarms the permission system for everyone who loads it"))
        else:
            findings.append(("MINOR", f"defaultMode '{mode}' set (user scope - the user's own choice)"))
    elif mode == "acceptEdits" and shared:
        findings.append(("MAJOR", "defaultMode 'acceptEdits' in a shared config auto-approves edits without the user opting in"))

    # Over-broad allow grants.
    allow = perms.get("allow", [])
    if isinstance(allow, list):
        for rule in allow:
            if isinstance(rule, str) and BROAD_BASH.match(rule.strip()):
                findings.append(("MAJOR", f"over-broad permission grant '{rule}' defeats least-privilege"))

    # additionalDirectories scope creep.
    addl = perms.get("additionalDirectories", [])
    if isinstance(addl, list):
        for d in addl:
            if isinstance(d, str) and (d.strip() in ("~", "/", "$HOME") or d.strip().startswith("~/..") or d.strip() == "~/"):
                findings.append(("MAJOR", f"additionalDirectories includes broad path '{d}' (scope creep)"))

    # Credential / env surface.
    env = cfg.get("env", {})
    if isinstance(env, dict):
        for k in env:
            if ANTHROPIC_ENV.search(k):
                sev = "BLOCKER" if shared else "MAJOR"
                findings.append((sev, f"env sets {k} - API traffic/key redirect surface (CVE-2026-21852 class)"))
    if cfg.get("apiKeyHelper"):
        findings.append(("MAJOR", "apiKeyHelper runs a shell script to return the API key - audit that script; a network-touching helper can exfiltrate the key"))

    # Blanket MCP approval (scope-weighted per the checklist trust-model nuance).
    if cfg.get("enableAllProjectMcpServers") is True:
        if scope == "global":
            findings.append(("MAJOR", "enableAllProjectMcpServers auto-approves every project MCP server (shadow-server enabler, MCP09)"))
        else:
            findings.append(("MINOR", "enableAllProjectMcpServers committed to repo (ignored until the folder is trusted; intent signal) - prefer enabledMcpjsonServers allowlist"))

    # Secret anywhere in settings.
    for label in _secret_in(cfg):
        findings.append(("BLOCKER", f"possible plaintext secret ({label}) in settings file"))
        break

    return _result(rec, findings)


def _result(rec, findings):
    return {
        "name": rec["name"],
        "kind": rec["kind"],
        "scope": rec["scope"],
        "plugin": rec.get("plugin"),
        "findings": findings,
    }


def run_validate(plugin_dirs):
    """Optionally run `claude plugin validate --strict` on each plugin dir."""
    if not shutil.which("claude"):
        return {}
    out = {}
    for d in plugin_dirs:
        try:
            proc = subprocess.run(
                ["claude", "plugin", "validate", str(d), "--strict"],
                capture_output=True, text=True, timeout=60,
            )
            out[str(d)] = {"returncode": proc.returncode, "stdout": proc.stdout.strip()[:2000]}
        except (subprocess.SubprocessError, OSError) as e:
            out[str(d)] = {"error": str(e)}
    return out


def main():
    ap = argparse.ArgumentParser(description="Deterministic manifest + settings checks (read-only).")
    ap.add_argument("--root", action="append", default=None)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--validate", action="store_true",
                    help="Also run the official `claude plugin validate --strict` if the CLI is present.")
    args = ap.parse_args()

    roots = [Path(r).expanduser().resolve() for r in args.root] if args.root else None
    records = scan_targets.discover_plugins(roots)

    # Which plugins bundle auto-executing / external surface?
    risky_plugins = {r["plugin"] for r in records
                     if r["kind"] in RISKY_CHILD_KINDS and r.get("plugin")}

    results = []
    plugin_dirs = []
    for rec in records:
        if rec["kind"] == "plugin":
            results.append(analyze_manifest(rec, risky_plugins))
            plugin_dirs.append(Path(rec["path"]).parent.parent)
        elif rec["kind"] == "settings":
            results.append(analyze_settings(rec))

    validation = run_validate(plugin_dirs) if args.validate else {}

    if args.json:
        json.dump({"results": results, "validation": validation}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        if not results:
            print("No plugin manifests or settings files found.")
        for res in results:
            loc = f"{res['plugin']}:" if res["plugin"] and res["kind"] != "plugin" else ""
            print(f"\n{loc}{res['name']} ({res['kind']}, {res['scope']}):")
            if not res["findings"]:
                print("  ok")
            for sev, msg in res["findings"]:
                print(f"  [{sev}] {msg}")
        if validation:
            print("\n-- claude plugin validate --strict --")
            for d, v in validation.items():
                print(f"  {d}: {v}")


if __name__ == "__main__":
    main()
