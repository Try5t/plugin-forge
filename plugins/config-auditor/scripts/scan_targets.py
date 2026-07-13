#!/usr/bin/env python3
"""Discover and parse Claude Code skills and agents (read-only).

Scans four default roots plus embedded agents inside skills:
  ~/.claude/skills/      global skills
  .claude/skills/        repo-local skills
  ~/.claude/agents/      global standalone agents
  .claude/agents/        repo-local standalone agents
  <skill>/agents/        embedded agents inside any discovered skill

Emits one record per target with parsed frontmatter, body line count, and
bundled resources. The config-auditor's own files are excluded so it never audits
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

# The auditor's own install root, resolved from THIS script's location so it
# works wherever the plugin lives — no absolute path is baked in, which keeps it
# correct across machines that clone the shared repo. A target belongs to the
# auditor iff its file sits inside this tree. Matching on bare component names
# instead (the old approach) wrongly excluded any audited plugin that reused a
# generic name such as "structure-analyst", silently dropping it from the scan.
SELF_ROOT = Path(__file__).resolve().parent.parent


def _is_self(path) -> bool:
    """True when `path` is one of the auditor's own bundled files (inside its
    own plugin tree), so it is excluded from every scan and never audits itself.
    Portable: `SELF_ROOT` is derived from this script's location, not hardcoded."""
    try:
        Path(path).resolve().relative_to(SELF_ROOT)
        return True
    except (ValueError, OSError):
        return False


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
            if _is_self(skill_md):
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
                    if _is_self(agent_md):
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
            if _is_self(agent_md):
                continue
            if str(agent_md) in seen:
                continue
            seen.add(str(agent_md))
            records.append(make_record(agent_md, "standalone_agent"))

    return records


# ─────────────────────────────────────────────────────────────────────────────
# Plugin + component discovery
#
# A plugin is a directory containing `.claude-plugin/plugin.json`. Beyond the
# skills and agents the four-root scan already finds, a plugin can carry
# executable / external surface the base scan never looked at: hooks, MCP
# servers, monitors, LSP servers, and flat commands. Each becomes its own record
# with a parsed `config` dict (instead of markdown `frontmatter`) so the
# check_* scripts can grade it. Settings files (`settings.json`) can also declare
# hooks and permissions outside any plugin, so those are discovered too.
# ─────────────────────────────────────────────────────────────────────────────

def load_json(path: Path):
    """Return (data, error_or_None). Read-only, tolerant of a leading BOM."""
    try:
        text = path.read_text(encoding="utf-8-sig", errors="replace")
    except OSError as e:
        return None, f"unreadable: {e}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, f"invalid JSON: {e}"


def plugin_roots():
    """Default roots to search for installed and repo-local plugins.

    Marketplace-source layout and the current repo. Deliberately avoids rglob
    over the whole plugin cache (which holds many duplicate temp copies); use
    --root to target a specific plugin or marketplace directory precisely.
    """
    home = Path.home()
    cwd = Path.cwd()
    roots = []
    mp = home / ".claude" / "plugins" / "marketplaces"
    if mp.is_dir():
        roots.append(mp)
    roots.append(cwd)
    return roots


def find_plugin_manifests(roots):
    """Yield each `.claude-plugin/plugin.json` path under the given roots.

    Bounded search: a manifest is found at `<root>/**/.claude-plugin/plugin.json`
    but capped in depth and deduped by resolved path so a messy cache does not
    explode the scan.
    """
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        for manifest in root.rglob(".claude-plugin/plugin.json"):
            rp = str(manifest.resolve())
            if rp in seen:
                continue
            # Skip the auditor's own plugin tree.
            if _is_self(manifest):
                continue
            seen.add(rp)
            yield manifest


def _component_record(name, kind, scope, path, config, plugin_name, **extra):
    rec = {
        "name": name,
        "dir_name": Path(path).parent.name,
        "kind": kind,
        "scope": scope,
        "path": str(path),
        "config": config,
        "parse_error": None,
        "resources": [],
        "plugin": plugin_name,
    }
    rec.update(extra)
    return rec


def _flatten_hooks(hooks_block):
    """Yield (event, matcher, handler_dict) for a settings/hooks.json hooks map.

    Accepts either a full `{"hooks": {...}}` wrapper or the bare event map.
    """
    if isinstance(hooks_block, dict) and "hooks" in hooks_block and isinstance(hooks_block["hooks"], dict):
        hooks_block = hooks_block["hooks"]
    if not isinstance(hooks_block, dict):
        return
    for event, entries in hooks_block.items():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            matcher = entry.get("matcher", "")
            handlers = entry.get("hooks", [])
            if not isinstance(handlers, list):
                continue
            for h in handlers:
                if isinstance(h, dict):
                    yield event, matcher, h


def discover_hooks_from(source_config, source_path, scope, plugin_name):
    """Yield hook records from a parsed hooks block (settings or hooks.json)."""
    records = []
    for i, (event, matcher, handler) in enumerate(_flatten_hooks(source_config)):
        htype = handler.get("type", "command")
        records.append(_component_record(
            name=f"{event}:{matcher or '*'}#{i}",
            kind="hook",
            scope=scope,
            path=source_path,
            config=handler,
            plugin_name=plugin_name,
            event=event,
            matcher=matcher,
            handler_type=htype,
        ))
    return records


def discover_mcp_from(source_config, source_path, scope, plugin_name):
    """Yield mcp_server records from a parsed .mcp.json / inline mcpServers."""
    servers = source_config.get("mcpServers", source_config) if isinstance(source_config, dict) else {}
    records = []
    if isinstance(servers, dict):
        for name, cfg in servers.items():
            if isinstance(cfg, dict):
                records.append(_component_record(
                    name=name, kind="mcp_server", scope=scope,
                    path=source_path, config=cfg, plugin_name=plugin_name,
                ))
    return records


def discover_lsp_from(source_config, source_path, scope, plugin_name):
    servers = source_config.get("lspServers", source_config) if isinstance(source_config, dict) else {}
    records = []
    if isinstance(servers, dict):
        for name, cfg in servers.items():
            if isinstance(cfg, dict):
                records.append(_component_record(
                    name=name, kind="lsp_server", scope=scope,
                    path=source_path, config=cfg, plugin_name=plugin_name,
                ))
    return records


def discover_monitors_from(source_config, source_path, scope, plugin_name):
    entries = source_config
    if isinstance(source_config, dict):
        entries = source_config.get("monitors", source_config.get("experimental", {}).get("monitors", []))
    records = []
    if isinstance(entries, list):
        for i, cfg in enumerate(entries):
            if isinstance(cfg, dict):
                records.append(_component_record(
                    name=cfg.get("name", f"monitor#{i}"), kind="monitor",
                    scope=scope, path=source_path, config=cfg, plugin_name=plugin_name,
                ))
    return records


def discover_plugin(manifest_path: Path):
    """Return the list of records for one plugin: the manifest plus every
    component (hooks, MCP, monitors, LSP, commands, skills, agents)."""
    records = []
    plugin_dir = manifest_path.parent.parent  # <plugin>/.claude-plugin/plugin.json
    scope = scope_of(manifest_path)
    manifest, err = load_json(manifest_path)
    manifest = manifest or {}
    plugin_name = manifest.get("name", plugin_dir.name)

    # 1. The manifest record (kind=plugin).
    records.append({
        "name": plugin_name,
        "dir_name": plugin_dir.name,
        "kind": "plugin",
        "scope": scope,
        "path": str(manifest_path),
        "config": manifest,
        "parse_error": err,
        "resources": [],
        "plugin": plugin_name,
    })

    # 2. Hooks — hooks/hooks.json and inline manifest `hooks`.
    hooks_json = plugin_dir / "hooks" / "hooks.json"
    if hooks_json.is_file():
        data, e = load_json(hooks_json)
        if data is not None:
            records += discover_hooks_from(data, hooks_json, scope, plugin_name)
    if isinstance(manifest.get("hooks"), (dict, list)):
        records += discover_hooks_from({"hooks": manifest["hooks"]} if isinstance(manifest["hooks"], dict) else {}, manifest_path, scope, plugin_name)

    # 3. MCP servers — .mcp.json and inline manifest `mcpServers`.
    mcp_json = plugin_dir / ".mcp.json"
    if mcp_json.is_file():
        data, e = load_json(mcp_json)
        if data is not None:
            records += discover_mcp_from(data, mcp_json, scope, plugin_name)
    if isinstance(manifest.get("mcpServers"), dict):
        records += discover_mcp_from({"mcpServers": manifest["mcpServers"]}, manifest_path, scope, plugin_name)

    # 4. LSP servers — .lsp.json and inline manifest `lspServers`.
    lsp_json = plugin_dir / ".lsp.json"
    if lsp_json.is_file():
        data, e = load_json(lsp_json)
        if data is not None:
            records += discover_lsp_from(data, lsp_json, scope, plugin_name)
    if isinstance(manifest.get("lspServers"), dict):
        records += discover_lsp_from({"lspServers": manifest["lspServers"]}, manifest_path, scope, plugin_name)

    # 5. Monitors — monitors.json and inline experimental.monitors.
    mon_json = plugin_dir / "monitors.json"
    if mon_json.is_file():
        data, e = load_json(mon_json)
        if data is not None:
            records += discover_monitors_from(data, mon_json, scope, plugin_name)
    inline_mon = manifest.get("experimental", {}).get("monitors") if isinstance(manifest.get("experimental"), dict) else None
    if isinstance(inline_mon, list):
        records += discover_monitors_from(inline_mon, manifest_path, scope, plugin_name)

    # 6. Commands — flat commands/*.md (each is a skill of kind=command).
    cmd_dir = plugin_dir / "commands"
    if cmd_dir.is_dir():
        for cmd_md in sorted(cmd_dir.glob("*.md")):
            if _is_self(cmd_md):
                continue
            crec = make_record(cmd_md, "command")
            # A flat command's invocation name is its filename stem, not the
            # parent `commands/` dir (make_record's default fallback).
            if not crec["frontmatter"].get("name"):
                crec["name"] = cmd_md.stem
            crec["plugin"] = plugin_name
            records.append(crec)

    # 7. Skills and agents packaged inside the plugin (reuse markdown discovery
    #    so the existing check_* scripts can grade them too).
    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
            if _is_self(skill_md):
                continue
            srec = make_record(skill_md, "skill")
            srec["plugin"] = plugin_name
            records.append(srec)
            emb = skill_md.parent / "agents"
            if emb.is_dir():
                for agent_md in sorted(emb.glob("*.md")):
                    if _is_self(agent_md):
                        continue
                    arec = make_record(agent_md, "embedded_agent")
                    arec["parent_skill"] = srec["name"]
                    arec["plugin"] = plugin_name
                    records.append(arec)
    agents_dir = plugin_dir / "agents"
    if agents_dir.is_dir():
        for agent_md in sorted(agents_dir.glob("*.md")):
            if _is_self(agent_md):
                continue
            arec = make_record(agent_md, "standalone_agent")
            arec["plugin"] = plugin_name
            records.append(arec)

    return records


def discover_settings():
    """Yield hook records and settings records from standalone settings files
    (outside any plugin): the permission/env posture and any hooks declared there."""
    home = Path.home()
    cwd = Path.cwd()
    files = [
        (home / ".claude" / "settings.json", "global"),
        (cwd / ".claude" / "settings.json", "repo"),
        (cwd / ".claude" / "settings.local.json", "repo"),
    ]
    records = []
    for path, scope in files:
        if not path.is_file():
            continue
        data, err = load_json(path)
        if data is None:
            records.append({
                "name": str(path.name), "dir_name": path.parent.name,
                "kind": "settings", "scope": scope, "path": str(path),
                "config": {}, "parse_error": err, "resources": [], "plugin": None,
            })
            continue
        # The settings file itself (for permission/env auditing).
        records.append({
            "name": str(path.name), "dir_name": path.parent.name,
            "kind": "settings", "scope": scope, "path": str(path),
            "config": data, "parse_error": None, "resources": [], "plugin": None,
        })
        # Any hooks declared inside it.
        if isinstance(data.get("hooks"), dict):
            records += discover_hooks_from({"hooks": data["hooks"]}, path, scope, None)
    return records


def discover_plugins(roots=None):
    """Discover every plugin (and its components) plus standalone settings files."""
    roots = roots if roots is not None else plugin_roots()
    records = []
    seen_plugins = set()
    for manifest in find_plugin_manifests(roots):
        recs = discover_plugin(manifest)
        pname = recs[0]["name"] if recs else None
        key = (pname, recs[0]["scope"] if recs else None)
        if key in seen_plugins:
            continue
        seen_plugins.add(key)
        records += recs
    records += discover_settings()
    return records


# Friendly --kind aliases → the concrete record kinds they expand to. Lets the
# scoping gate use the same vocabulary as the SKILL ("agents", "surface", …).
KIND_ALIASES = {
    "skill": {"skill"},
    "skills": {"skill"},
    "agent": {"standalone_agent", "embedded_agent"},
    "agents": {"standalone_agent", "embedded_agent"},
    "command": {"command"},
    "commands": {"command"},
    "plugin": {"plugin"},
    "plugins": {"plugin"},
    "server": {"mcp_server", "lsp_server"},
    "servers": {"mcp_server", "lsp_server"},
    "surface": {"hook", "monitor", "mcp_server", "lsp_server", "settings"},
}


def filter_records(records, kinds=None, scope=None):
    """Post-discovery convenience filter. Default (both None) is a no-op, so this
    never changes behavior for callers that do not ask for a filter."""
    if kinds:
        wanted = set()
        for k in kinds:
            wanted |= KIND_ALIASES.get(k, {k})
        records = [r for r in records if r["kind"] in wanted]
    if scope and scope != "all":
        records = [r for r in records if r["scope"] == scope]
    return records


def main():
    ap = argparse.ArgumentParser(description="Discover Claude Code skills and agents (read-only).")
    ap.add_argument("--root", action="append", default=None,
                    help="Override discovery root(s). Repeatable. Replaces defaults. "
                         "Skill roots and agent roots are auto-detected by folder layout.")
    ap.add_argument("--json", action="store_true", help="Emit JSON.")
    ap.add_argument("--plugins", action="store_true",
                    help="Also discover plugins and their components (hooks, MCP "
                         "servers, monitors, LSP servers, commands) plus settings files.")
    ap.add_argument("--plugins-only", action="store_true",
                    help="Discover only plugins/components/settings, not the skill/agent roots.")
    ap.add_argument("--kind", action="append", default=None,
                    help="Convenience filter: keep only these kinds. Repeatable. Accepts "
                         "concrete kinds (skill, standalone_agent, hook, mcp_server, …) or "
                         "aliases (agents, servers, surface). Default: no filter.")
    ap.add_argument("--scope", choices=["global", "repo", "all"], default=None,
                    help="Convenience filter: keep only this scope. Default: no filter.")
    args = ap.parse_args()

    if args.root:
        # When roots are given explicitly, scan each for both skills and agents.
        roots = [Path(r).expanduser().resolve() for r in args.root]
        roots_by_kind = {"skill": roots, "standalone_agent": roots}
    else:
        roots_by_kind = default_roots()

    records = []
    if not args.plugins_only:
        records += discover(roots_by_kind)
    if args.plugins or args.plugins_only:
        plugin_search_roots = (
            [Path(r).expanduser().resolve() for r in args.root] if args.root else None
        )
        records += discover_plugins(plugin_search_roots)

    records = filter_records(records, kinds=args.kind, scope=args.scope)

    if args.json:
        json.dump({"count": len(records), "targets": records}, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print(f"Found {len(records)} target(s):")
        for r in records:
            err = f"  [PARSE ERROR: {r['parse_error']}]" if r.get("parse_error") else ""
            extra = f"body={r['body_lines']}L" if "body_lines" in r else f"kind-config"
            plugin = f" @{r['plugin']}" if r.get("plugin") else ""
            print(f"  - {r['name']} ({r['kind']}, {r['scope']}){plugin} {extra}{err}")


if __name__ == "__main__":
    main()
