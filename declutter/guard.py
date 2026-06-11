"""Config-bundle guard.

Some config files reference sibling files/dirs by *relative path*
(firebase.json -> functions/, firestore.rules, storage.rules;
docker-compose.yml -> build contexts; vercel.json -> public/, ...).

If those are sorted individually, the config moves away from what it
points at and silently breaks. This module detects such an anchor config
sitting loose in a source folder, resolves the siblings it binds, and
returns them as one atomic "bundle" so the organizer keeps them together.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

# Anchors we understand structurally.
STRUCTURED_ANCHORS = {"firebase.json"}

# Anchors we bind via a conservative text scan (no parser / no deps needed).
GENERIC_ANCHORS = {
    "docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml",
    "vercel.json", "netlify.toml", "serverless.yml", "serverless.yaml",
    "turbo.json", "pnpm-workspace.yaml", "lerna.json", "nx.json", "Procfile",
}

# Config files that travel WITH an anchor (same logical project).
COMPANION_FILES = {".firebaserc", ".env", ".env.production", ".env.local"}


@dataclass
class Bundle:
    name: str               # destination subfolder name
    members: list[Path]     # absolute paths to keep together
    anchor: str             # the config that bound them
    reason: str = field(default="")


def _refs_firebase(path: Path) -> set[str]:
    """Relative paths referenced by a firebase.json."""
    refs: set[str] = set()
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return refs

    def as_list(x):
        if isinstance(x, dict):
            return [x]
        return x or []

    for fn in as_list(cfg.get("functions")):
        if isinstance(fn, dict) and fn.get("source"):
            refs.add(fn["source"])
    for fs in as_list(cfg.get("firestore")):
        if isinstance(fs, dict):
            for k in ("rules", "indexes"):
                if fs.get(k):
                    refs.add(fs[k])
    for st in as_list(cfg.get("storage")):
        if isinstance(st, dict) and st.get("rules"):
            refs.add(st["rules"])
    for h in as_list(cfg.get("hosting")):
        if isinstance(h, dict) and h.get("public"):
            refs.add(h["public"])
    return refs


def _refs_generic(path: Path, siblings: list[str]) -> set[str]:
    """Heuristic: a sibling is 'referenced' if its name appears as a
    path-like token in the config text. Over-bundling is the safe direction."""
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return set()
    refs: set[str] = set()
    for name in siblings:
        if len(name) < 3:
            continue
        if re.search(r'(^|[\s"\'/(=:,])' + re.escape(name) + r'($|[\s"\'/)\],:])', text):
            refs.add(name)
    return refs


def _firebaserc_project(folder: Path) -> str | None:
    rc = folder / ".firebaserc"
    if rc.is_file():
        try:
            return json.loads(rc.read_text(encoding="utf-8"))["projects"]["default"]
        except Exception:
            return None
    return None


def _bundle_name(anchor: Path, folder: Path) -> str:
    if anchor.name == "firebase.json":
        proj = _firebaserc_project(folder)
        if proj:
            return f"{proj}-firebase"
        return "firebase-project"
    stem = anchor.stem.replace(".", "-") or anchor.name
    return f"{stem}-project"


def find_bundles(source_dir: Path, extra_anchors: list[str] | None = None) -> tuple[list[Bundle], set[Path]]:
    """Return (bundles, claimed_paths) for one source directory."""
    anchors = STRUCTURED_ANCHORS | GENERIC_ANCHORS | set(extra_anchors or [])
    try:
        children = list(source_dir.iterdir())
    except OSError:
        return [], set()
    sibling_names = [c.name for c in children]

    bundles: list[Bundle] = []
    claimed: set[Path] = set()

    for child in children:
        if child.name not in anchors or not child.is_file():
            continue
        if child.name in STRUCTURED_ANCHORS:
            refs = _refs_firebase(child)
        else:
            others = [n for n in sibling_names if n != child.name]
            refs = _refs_generic(child, others)

        # Resolve each ref to its top-level sibling that actually exists.
        members: list[Path] = [child]
        for ref in refs:
            top = Path(ref).parts[0] if Path(ref).parts else ref
            target = source_dir / top
            if target.exists() and target not in members:
                members.append(target)
        # Pull in companion config files (.firebaserc, .env...).
        for comp in COMPANION_FILES:
            c = source_dir / comp
            if c.exists() and c not in members:
                members.append(c)

        # Only a bundle if the anchor actually binds at least one sibling.
        real_siblings = [m for m in members if m != child and m.name not in COMPANION_FILES]
        if not real_siblings:
            continue

        bundles.append(Bundle(
            name=_bundle_name(child, source_dir),
            members=members,
            anchor=child.name,
            reason=f"kept with {child.name} (relative paths would break if split)",
        ))
        claimed.update(members)

    return bundles, claimed
