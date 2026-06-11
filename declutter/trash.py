"""Cross-platform, recoverable deletion.

Order of preference:
  1. `send2trash` (if installed) -> the real OS Recycle Bin / Trash.
  2. A local quarantine folder under the destination root -> recoverable,
     and restorable by `declutter undo`.

We never call os.remove / shutil.rmtree on user data.
"""
from __future__ import annotations

import shutil
from pathlib import Path

try:
    from send2trash import send2trash as _send2trash  # type: ignore
    HAVE_SEND2TRASH = True
except Exception:  # pragma: no cover
    HAVE_SEND2TRASH = False


def unique_path(target: Path) -> Path:
    """Return a non-colliding path by appending ' (n)' if needed."""
    target = Path(target)
    if not target.exists():
        return target
    stem, suffix, parent = target.stem, target.suffix, target.parent
    i = 1
    while True:
        cand = parent / f"{stem} ({i}){suffix}"
        if not cand.exists():
            return cand
        i += 1


def trash(path: Path, quarantine_dir: Path) -> tuple[str, str | None]:
    """Send `path` to the OS trash or quarantine.

    Returns (method, restore_path) where method is 'system-trash' (no
    programmatic restore) or 'quarantine' (restore_path points at the moved copy).
    """
    path = Path(path)
    if HAVE_SEND2TRASH:
        _send2trash(str(path))
        return ("system-trash", None)
    quarantine_dir = Path(quarantine_dir)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    dest = unique_path(quarantine_dir / path.name)
    shutil.move(str(path), str(dest))
    return ("quarantine", str(dest))
