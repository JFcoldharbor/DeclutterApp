"""Scanning & classification: turn a messy folder into a list of Actions."""
from __future__ import annotations

import os
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

from .config import expand
from .guard import find_bundles


@dataclass
class Action:
    src: str            # absolute source path
    kind: str           # "move" | "trash"
    dest: str | None    # absolute destination (for moves)
    category: str       # bucket label, e.g. "Images", "Code", "junk"
    reason: str         # human-readable explanation


def _is_junk_name(name: str, patterns: list[str]) -> bool:
    return any(fnmatch(name, pat) for pat in patterns)


def _dir_is_empty(d: Path, junk_patterns: list[str]) -> bool:
    """True if the directory contains no files other than junk."""
    for _root, _dirs, files in os.walk(d):
        for f in files:
            if not _is_junk_name(f, junk_patterns):
                return False
    return True


def _is_project(d: Path, markers: list[str], max_depth: int = 2) -> bool:
    """True if a project marker appears within `max_depth` levels."""
    base = str(d)
    for root, dirs, files in os.walk(d):
        depth = root[len(base):].count(os.sep)
        for name in list(dirs) + list(files):
            if any(fnmatch(name, m) for m in markers):
                return True
        if depth >= max_depth - 1:
            dirs[:] = []  # stop descending further
    return False


def _category_for_ext(ext: str, categories: list[dict]) -> str | None:
    ext = ext.lower().lstrip(".")
    for cat in categories:
        if ext in [e.lower() for e in cat.get("extensions", [])]:
            return cat["name"]
    return None


def _keyword_route(name: str, routes: list[dict]) -> str | None:
    low = name.lower()
    for r in routes:
        kw = str(r.get("keyword", "")).lower()
        if kw and kw in low:
            return r.get("folder")
    return None


def classify(entry: Path, cfg: dict, dest_root: Path) -> Action | None:
    """Decide what to do with a single top-level item. None => leave it."""
    name = entry.name
    junk = cfg["junk"]
    junk_patterns = junk.get("patterns", [])
    ignore = set(cfg.get("ignore", []))

    if name in ignore:
        return None
    if cfg.get("skip_hidden", True) and name.startswith(".") and not _is_junk_name(name, junk_patterns):
        return None
    if _is_junk_name(name, junk_patterns):
        return Action(str(entry), "trash", None, "junk", f"matches junk pattern")

    if entry.is_dir():
        if junk.get("trash_empty_dirs", True) and _dir_is_empty(entry, junk_patterns):
            return Action(str(entry), "trash", None, "junk", "empty folder")
        if _is_project(entry, cfg.get("project_markers", [])):
            dest = dest_root / cfg.get("code_folder", "Code") / name
            return Action(str(entry), "move", str(dest), "Code", "code project (marker found)")
        if cfg.get("move_other_dirs", False):
            dest = dest_root / cfg.get("ambiguous_folder", "_Unsorted") / name
            return Action(str(entry), "move", str(dest), "_Unsorted", "non-project folder")
        return None  # leave plain folders alone by default

    # It's a file.
    try:
        size = entry.stat().st_size
    except OSError:
        size = 1
    if junk.get("trash_empty_files", True) and size == 0:
        return Action(str(entry), "trash", None, "junk", "empty (0-byte) file")

    routed = _keyword_route(name, cfg.get("keyword_routes", []))
    if routed:
        dest = dest_root / routed / name
        return Action(str(entry), "move", str(dest), routed, "keyword route")

    cat = _category_for_ext(entry.suffix, cfg.get("categories", []))
    if cat:
        dest = dest_root / cat / name
        return Action(str(entry), "move", str(dest), cat, f"{entry.suffix.lower()} -> {cat}")

    amb = cfg.get("ambiguous_folder", "_Unsorted")
    dest = dest_root / amb / name
    return Action(str(entry), "move", str(dest), amb, "unrecognized type")


def scan(cfg: dict) -> list[Action]:
    """Produce the full plan of actions across all configured sources."""
    dest_root = expand(cfg["dest_root"])
    code_folder = cfg.get("code_folder", "Code")
    bundle_configs = cfg.get("bundle_configs", True)
    extra_anchors = cfg.get("anchor_configs", [])
    actions: list[Action] = []

    for src in cfg.get("sources", []):
        src_path = expand(src)
        if not src_path.is_dir():
            continue

        # Guard: detect config-bound bundles first so we keep a config and
        # the relative paths it references together as one atomic move.
        claimed: set = set()
        if bundle_configs:
            bundles, claimed = find_bundles(src_path, extra_anchors)
            for b in bundles:
                bundle_root = dest_root / code_folder / b.name
                for member in b.members:
                    actions.append(Action(
                        src=str(member),
                        kind="move",
                        dest=str(bundle_root / member.name),
                        category=f"Code/{b.name}",
                        reason=b.reason,
                    ))

        for entry in sorted(src_path.iterdir(), key=lambda p: p.name.lower()):
            if entry in claimed:
                continue
            # Never reorganize the destination if it lives inside a source.
            if expand(str(entry)) == dest_root:
                continue
            action = classify(entry, cfg, dest_root)
            if action:
                actions.append(action)
    return actions


def summarize(actions: list[Action]) -> dict[str, int]:
    """Count actions per category for a quick preview."""
    out: dict[str, int] = {}
    for a in actions:
        key = "TRASH" if a.kind == "trash" else a.category
        out[key] = out.get(key, 0) + 1
    return out
