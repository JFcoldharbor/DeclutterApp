"""Execution & undo: carry out a plan, record a manifest, reverse it."""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .config import expand
from .scan import Action
from .trash import trash, unique_path


def _manifest_dir(dest_root: Path) -> Path:
    d = dest_root / ".declutter"
    d.mkdir(parents=True, exist_ok=True)
    return d


def execute(actions: list[Action], cfg: dict) -> dict:
    """Perform every action, writing a manifest. Returns a result summary."""
    dest_root = expand(cfg["dest_root"])
    dest_root.mkdir(parents=True, exist_ok=True)
    quarantine = _manifest_dir(dest_root) / "quarantine"

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    entries: list[dict] = []
    moved = trashed = failed = 0

    for a in actions:
        src = Path(a.src)
        if not src.exists():
            continue
        try:
            if a.kind == "move":
                dest = unique_path(Path(a.dest))
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                entries.append({"kind": "move", "src": str(src), "dest": str(dest),
                                "category": a.category})
                moved += 1
            else:  # trash
                method, restore = trash(src, quarantine)
                entries.append({"kind": "trash", "src": str(src), "method": method,
                                "restore": restore, "category": a.category})
                trashed += 1
        except Exception as e:  # keep going; record nothing for the failure
            failed += 1
            entries.append({"kind": "error", "src": str(src), "error": str(e)})

    manifest = {
        "run_id": run_id,
        "created": datetime.now().isoformat(timespec="seconds"),
        "dest_root": str(dest_root),
        "entries": entries,
    }
    path = _manifest_dir(dest_root) / f"manifest-{run_id}.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"run_id": run_id, "manifest": str(path), "moved": moved,
            "trashed": trashed, "failed": failed}


def list_manifests(dest_root: Path) -> list[Path]:
    d = dest_root / ".declutter"
    if not d.is_dir():
        return []
    return sorted(d.glob("manifest-*.json"))


def undo(manifest_path: str | Path) -> dict:
    """Reverse a run: restore moved files and quarantined trash."""
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored = skipped = system_trash = 0

    for entry in reversed(data.get("entries", [])):
        kind = entry.get("kind")
        if kind == "move":
            dest, src = Path(entry["dest"]), Path(entry["src"])
            if dest.exists():
                src.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(dest), str(unique_path(src)))
                restored += 1
            else:
                skipped += 1
        elif kind == "trash":
            if entry.get("method") == "quarantine" and entry.get("restore"):
                q, src = Path(entry["restore"]), Path(entry["src"])
                if q.exists():
                    src.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(q), str(unique_path(src)))
                    restored += 1
                else:
                    skipped += 1
            else:
                system_trash += 1  # can't auto-restore from OS Trash

    return {"restored": restored, "skipped": skipped, "system_trash": system_trash}
