#!/usr/bin/env python3
"""Verify the vendored `trade-skills` plugin is complete and internally linked.

An "install" of a skill is only real if every file its entry point points at is
actually present. This walks the vendored tree and checks:

  1. the structural files the plugin's manifests promise exist;
  2. SKILL.md has valid frontmatter with a name and description;
  3. every relative markdown link inside the plugin resolves on disk;
  4. the pitfalls library is numbered 01..38 with no duplicates or gaps;
  5. the three manifests agree on the version.

Exit code is 0 when everything checks out, 1 otherwise, so it is usable in CI.

Usage:
    python3 tools/check_skill.py [vendor/trade-skills]
"""

from __future__ import annotations

import json
import os
import re
import sys

REQUIRED = [
    "README.md",
    "AGENTS.md",
    ".claude-plugin/marketplace.json",
    "plugins/trade/.codex-plugin/plugin.json",
    "plugins/trade/skills/trade/SKILL.md",
    "plugins/trade/skills/trade/README.md",
    "plugins/trade/skills/trade/references/index.md",
    "plugins/trade/skills/trade/references/OKF.md",
    "plugins/trade/skills/trade/references/log.md",
    "plugins/trade/skills/trade/references/strategies.md",
    "plugins/trade/skills/trade/references/gamma-framework.md",
    "plugins/trade/skills/trade/references/price-action-framework.md",
    "plugins/trade/skills/trade/references/macro-framework.md",
    "plugins/trade/skills/trade/references/overnight-futures-framework.md",
    "plugins/trade/skills/trade/references/parent-order-flow-framework.md",
    "plugins/trade/skills/trade/references/data-collection.md",
    "plugins/trade/skills/trade/references/pitfalls/README.md",
    "plugins/trade/skills/trade/references/commands/analysis.md",
    "plugins/trade/skills/trade/references/commands/daily.md",
    "plugins/trade/skills/trade/references/commands/import.md",
    "plugins/trade/skills/trade/references/commands/report.md",
    "plugins/trade/skills/trade/references/commands/setup.md",
]

# Two parts of the tree deliberately contain links that do not resolve here:
#   * evals/ holds test fixtures, including stub workspaces the harness copies
#     into a scratch directory before a run;
#   * references/commands/templates/ holds files copied *into* a user's
#     knowledge dir, so their relative links resolve at the destination.
# Both are skipped and counted, never silently ignored.
SKIP_DIRS = {".git", "node_modules", os.path.join("plugins", "trade", "evals")}
SKIP_PREFIXES = (os.path.join("plugins", "trade", "skills", "trade",
                              "references", "commands", "templates"),)

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
REFDEF_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(\S+)", re.MULTILINE)
PITFALL_RE = re.compile(r"^(\d{2})-[a-z0-9-]+\.md$")


def rel_links(path: str, text: str) -> list[str]:
    """Relative link targets only: skip URLs, anchors and mailto."""
    out = []
    for match in list(LINK_RE.finditer(text)) + list(REFDEF_RE.finditer(text)):
        target = match.group(1).strip()
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        target = target.split("#", 1)[0]
        if target:
            out.append(target)
    return out


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    key = None
    for line in block.splitlines():
        if not line.strip():
            continue
        if re.match(r"^[A-Za-z_][\w-]*:", line):
            key, _, value = line.partition(":")
            key = key.strip()
            fields[key] = value.strip()
        elif key:  # continuation of a folded scalar
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields


def main() -> int:
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "vendor", "trade-skills")
    if not os.path.isdir(root):
        print(f"FAIL  {root} does not exist")
        return 1

    problems: list[str] = []
    notes: list[str] = []

    for name in REQUIRED:
        if not os.path.isfile(os.path.join(root, name)):
            problems.append(f"missing required file: {name}")

    skill = os.path.join(root, "plugins/trade/skills/trade/SKILL.md")
    if os.path.isfile(skill):
        meta = frontmatter(open(skill, encoding="utf-8").read())
        if not meta.get("name"):
            problems.append("SKILL.md frontmatter has no name")
        if len(meta.get("description", "")) < 40:
            problems.append("SKILL.md frontmatter description is missing or too short")
        if meta.get("name") and meta["name"] != "trade":
            problems.append(f"SKILL.md name is {meta['name']!r}, expected 'trade'")

    # every relative link must resolve
    checked = 0
    md_files = 0
    skipped = 0
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        dirnames[:] = [d for d in dirnames
                       if os.path.normpath(os.path.join(rel_dir, d)) not in SKIP_DIRS
                       and d not in {".git", "node_modules"}]
        for filename in filenames:
            if not filename.endswith(".md"):
                continue
            md_files += 1
            path = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(path, root)
            if rel_path.startswith(SKIP_PREFIXES):
                skipped += 1
                continue
            text = open(path, encoding="utf-8").read()
            for target in rel_links(path, text):
                checked += 1
                resolved = os.path.normpath(os.path.join(dirpath, target))
                if not os.path.exists(resolved):
                    problems.append(
                        f"broken link: {os.path.relpath(path, root)} -> {target}")

    # pitfalls numbered 01..38, no gaps or duplicates
    pit_dir = os.path.join(root, "plugins/trade/skills/trade/references/pitfalls")
    numbers = sorted(int(m.group(1)) for m in
                     (PITFALL_RE.match(f) for f in os.listdir(pit_dir)) if m)
    if numbers != list(range(1, 39)):
        problems.append(f"pitfalls are not 01..38: found {len(numbers)} files, "
                        f"numbers {numbers[:3]}...{numbers[-3:]}")
    notes.append(f"pitfalls: {len(numbers)} concept files (01-{numbers[-1]:02d})"
                 if numbers else "pitfalls: none")

    # manifests must agree on version
    def jget(*path):
        try:
            blob = json.load(open(os.path.join(root, *path), encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"cannot read {os.path.join(*path)}: {exc}")
            return None
        return blob

    market = jget(".claude-plugin/marketplace.json")
    codex = jget("plugins/trade/.codex-plugin/plugin.json")
    versions = {}
    if market:
        versions["marketplace"] = market.get("metadata", {}).get("version")
        entry = next((p for p in market.get("plugins", [])
                      if p.get("name") == "trade"), {})
        versions["plugin"] = entry.get("version")
        if entry.get("source") != "./plugins/trade":
            problems.append(f"marketplace source is {entry.get('source')!r}, "
                            f"expected './plugins/trade'")
    if codex:
        versions["codex"] = codex.get("version")
    distinct = {v for v in versions.values() if v}
    if len(distinct) > 1:
        problems.append(f"manifest versions disagree: {versions}")
    elif distinct:
        notes.append(f"plugin version {distinct.pop()} across "
                     f"{len(versions)} manifests")

    # report
    print(f"Checking {root}")
    print(f"  markdown files   {md_files}")
    print(f"  links checked    {checked}")
    if skipped:
        print(f"  skipped          {skipped} template/fixture files "
              f"(links resolve at their destination)")
    for note in notes:
        print(f"  {note}")
    if problems:
        print(f"\nFAIL  {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nOK  skill is complete and every relative link resolves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
