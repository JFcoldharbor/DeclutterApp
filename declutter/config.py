"""Configuration: defaults, loading, and a generatable example file.

Config is plain data (a dict). It can be loaded from YAML (if PyYAML is
installed) or JSON. If no file is given, sensible cross-platform defaults
are used. No personal data is hard-coded — users tailor rules via config.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Default rules. These are intentionally generic and apply to any machine.
# ---------------------------------------------------------------------------
DEFAULT_CONFIG: dict[str, Any] = {
    # Folders to clean up (relative to home unless absolute).
    "sources": ["~/Desktop", "~/Downloads"],
    # Where organized files are moved to.
    "dest_root": "~/Organized",
    # Subfolder for items we can't confidently classify.
    "ambiguous_folder": "_Unsorted",
    # Subfolder that detected code projects are moved into.
    "code_folder": "Code",
    # Skip dotfiles/dotfolders (except recognized junk like .DS_Store).
    "skip_hidden": True,
    # Move non-project, non-empty folders too? If false, they're left alone.
    "move_other_dirs": False,

    # Keep a config file together with the relative paths it references
    # (e.g. firebase.json + functions/ + firestore.rules) as one atomic move,
    # instead of scattering them. Extra anchor filenames can be added here.
    "bundle_configs": True,
    "anchor_configs": [],

    # A directory is treated as a "code project" if it contains any of these
    # markers at depth <= 2 (names or globs).
    "project_markers": [
        ".git", "package.json", "*.xcodeproj", "*.xcworkspace",
        "build.gradle", "build.gradle.kts", "settings.gradle", "Package.swift",
        "pom.xml", "Cargo.toml", "go.mod", "pyproject.toml", "requirements.txt",
        "CMakeLists.txt", "Gemfile", "composer.json", "Makefile",
    ],

    # Loose files are routed to <dest>/<category> by extension.
    "categories": [
        {"name": "Documents",     "extensions": ["pdf", "doc", "docx", "txt", "rtf", "odt", "pages", "md", "eml"]},
        {"name": "Spreadsheets",  "extensions": ["xls", "xlsx", "csv", "numbers"]},
        {"name": "Presentations", "extensions": ["ppt", "pptx", "key"]},
        {"name": "Images",        "extensions": ["png", "jpg", "jpeg", "gif", "webp", "heic", "heif", "svg", "bmp", "tiff"]},
        {"name": "Audio",         "extensions": ["mp3", "m4a", "wav", "aac", "flac", "aiff", "ogg"]},
        {"name": "Video",         "extensions": ["mp4", "mov", "mkv", "avi", "webm", "m4v"]},
        {"name": "Archives",      "extensions": ["zip", "tar", "gz", "bz2", "7z", "rar"]},
        {"name": "Installers",    "extensions": ["dmg", "pkg", "exe", "msi", "deb", "appimage"]},
        {"name": "Code",          "extensions": ["js", "ts", "jsx", "tsx", "py", "swift", "kt", "java", "go", "rs", "rb", "c", "cpp", "h", "sh", "html", "css"]},
    ],

    # Optional overrides: if a filename contains <keyword> (case-insensitive),
    # route it to <folder> regardless of extension. Great for per-project sorting.
    # Example: {"keyword": "invoice", "folder": "Documents/Finance"}
    "keyword_routes": [],

    # What counts as junk (sent to Trash).
    "junk": {
        "patterns": ["*.crdownload", "*.part", "*.download", "*.tmp", ".DS_Store", "Thumbs.db", "desktop.ini"],
        "trash_empty_dirs": True,
        "trash_empty_files": True,
    },

    # Names we never touch (in sources or as destinations).
    "ignore": ["_Unsorted", "Code", "Organized", ".declutter"],
}

EXAMPLE_YAML = """# Declutter configuration (YAML). Every field is optional; omitted fields
# fall back to built-in defaults. Paths starting with ~ expand to your home.

sources:
  - ~/Desktop
  - ~/Downloads
dest_root: ~/Organized
ambiguous_folder: _Unsorted
code_folder: Code
skip_hidden: true
move_other_dirs: false

# A folder is a "code project" if it contains any of these (names or globs).
project_markers: [.git, package.json, "*.xcodeproj", build.gradle, Cargo.toml, go.mod, pyproject.toml]

categories:
  - {name: Documents,     extensions: [pdf, doc, docx, txt, md]}
  - {name: Images,        extensions: [png, jpg, jpeg, webp, heic, svg]}
  - {name: Audio,         extensions: [mp3, m4a, wav, flac]}
  - {name: Video,         extensions: [mp4, mov, mkv]}
  - {name: Archives,      extensions: [zip, tar, gz, dmg]}

# Route by filename keyword (overrides extension). Tailor these per project.
keyword_routes:
  # - {keyword: invoice, folder: Documents/Finance}
  # - {keyword: stitch,  folder: Projects/Stitch}

junk:
  patterns: ["*.crdownload", "*.part", ".DS_Store", "Thumbs.db"]
  trash_empty_dirs: true
  trash_empty_files: true

ignore: [_Unsorted, Code, Organized, .declutter]
"""


def expand(path: str) -> Path:
    """Expand ~ and environment variables into an absolute Path."""
    return Path(os.path.expandvars(os.path.expanduser(str(path)))).resolve(strict=False)


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: str | os.PathLike | None) -> dict:
    """Load a config file (YAML or JSON) merged over defaults.

    Returns DEFAULT_CONFIG if path is None or the file is empty.
    """
    if not path:
        return dict(DEFAULT_CONFIG)
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    text = p.read_text(encoding="utf-8")
    data: dict = {}
    if p.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise SystemExit(
                "This config is YAML but PyYAML isn't installed. "
                "Run `pip install pyyaml`, or use a .json config."
            ) from e
        data = yaml.safe_load(text) or {}
    else:
        data = json.loads(text or "{}")
    return _deep_merge(DEFAULT_CONFIG, data)


def write_example(path: str | os.PathLike) -> Path:
    """Write a commented example config next to the user."""
    p = Path(path)
    p.write_text(EXAMPLE_YAML, encoding="utf-8")
    return p
