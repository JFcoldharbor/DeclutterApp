"""Declutter CLI — interactive menu + scriptable subcommands.

  declutter                 # launch the interactive menu
  declutter scan            # preview the plan (no changes)
  declutter organize        # execute (asks to confirm unless --yes)
  declutter undo            # reverse the most recent run
  declutter init [path]     # write an example config file

Global flags: --config PATH, --yes
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import DEFAULT_CONFIG, expand, load_config, write_example
from .organize import execute, list_manifests, undo
from .scan import scan, summarize
from .trash import HAVE_SEND2TRASH

BANNER = r"""
  ____            _       _   _
 |  _ \  ___  ___| |_   _| |_| |_ ___ _ __
 | | | |/ _ \/ __| | | | | __| __/ _ \ '__|
 | |_| |  __/ (__| | |_| | |_| ||  __/ |
 |____/ \___|\___|_|\__,_|\__|\__\___|_|   v%s
   safe · reversible · cross-platform
""" % __version__


def _print_plan(actions, cfg) -> None:
    if not actions:
        print("  Nothing to do — everything is already tidy. ✨")
        return
    counts = summarize(actions)
    dest = expand(cfg["dest_root"])
    print(f"\n  Plan ({len(actions)} actions) -> {dest}")
    for k in sorted(counts):
        print(f"    {counts[k]:>4}  {k}")
    print("\n  Examples:")
    for a in actions[:12]:
        if a.kind == "trash":
            print(f"    TRASH   {Path(a.src).name}   ({a.reason})")
        else:
            print(f"    {a.category:<12} {Path(a.src).name}")
    if len(actions) > 12:
        print(f"    … and {len(actions) - 12} more")
    if not HAVE_SEND2TRASH:
        print("\n  Note: `send2trash` not installed — junk goes to a recoverable")
        print("  quarantine under <dest>/.declutter/quarantine (restore via undo).")


def cmd_scan(cfg) -> None:
    _print_plan(scan(cfg), cfg)


def cmd_organize(cfg, assume_yes: bool) -> None:
    actions = scan(cfg)
    _print_plan(actions, cfg)
    if not actions:
        return
    if not assume_yes:
        ans = input("\n  Proceed? Nothing is deleted; junk is recoverable. [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("  Cancelled.")
            return
    result = execute(actions, cfg)
    print(f"\n  Done: {result['moved']} moved, {result['trashed']} trashed, "
          f"{result['failed']} failed.")
    print(f"  Manifest: {result['manifest']}")
    print("  Undo anytime with:  declutter undo")


def cmd_undo(cfg) -> None:
    dest = expand(cfg["dest_root"])
    manifests = list_manifests(dest)
    if not manifests:
        print("  No manifests found — nothing to undo.")
        return
    latest = manifests[-1]
    print(f"  Undoing: {latest.name}")
    r = undo(latest)
    print(f"  Restored {r['restored']}, skipped {r['skipped']}, "
          f"{r['system_trash']} were sent to the OS Trash (restore those manually).")


def cmd_init(path: str) -> None:
    p = write_example(path)
    print(f"  Wrote example config: {p}")
    print("  Edit it, then run:  declutter scan --config " + str(p))


def menu(cfg, cfg_path) -> None:
    print(BANNER)
    print(f"  Sources: {', '.join(cfg['sources'])}")
    print(f"  Dest:    {cfg['dest_root']}")
    if cfg_path:
        print(f"  Config:  {cfg_path}")
    while True:
        print("\n  [1] Scan & preview   [2] Organize   [3] Undo last run")
        print("  [4] Show config      [5] Write example config   [q] Quit")
        choice = input("  > ").strip().lower()
        if choice == "1":
            cmd_scan(cfg)
        elif choice == "2":
            cmd_organize(cfg, assume_yes=False)
        elif choice == "3":
            cmd_undo(cfg)
        elif choice == "4":
            import json
            print(json.dumps(cfg, indent=2))
        elif choice == "5":
            target = input("  Path [declutter.yaml]: ").strip() or "declutter.yaml"
            cmd_init(target)
        elif choice in ("q", "quit", "exit"):
            print("  Bye 👋")
            return
        else:
            print("  Unknown choice.")


def main(argv: list[str] | None = None) -> int:
    # Shared flags work before OR after the subcommand. SUPPRESS keeps unset
    # values from clobbering a value parsed by the other parser.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS, help="Path to a YAML/JSON config file.")
    common.add_argument("--yes", action="store_true", default=argparse.SUPPRESS, help="Skip confirmation prompts.")

    parser = argparse.ArgumentParser(prog="declutter", description="Safe, reversible file organizer.", parents=[common])
    parser.add_argument("--version", action="version", version=f"declutter {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("scan", parents=[common], help="Preview the plan without changing anything.")
    sub.add_parser("organize", parents=[common], help="Execute the plan (asks to confirm).")
    sub.add_parser("undo", parents=[common], help="Reverse the most recent run.")
    p_init = sub.add_parser("init", parents=[common], help="Write an example config file.")
    p_init.add_argument("path", nargs="?", default="declutter.yaml")

    args = parser.parse_args(argv)
    config_path = getattr(args, "config", None)
    assume_yes = getattr(args, "yes", False)

    if args.command == "init":
        cmd_init(args.path)
        return 0

    try:
        cfg = load_config(config_path)
    except (FileNotFoundError, SystemExit) as e:
        print(f"  {e}")
        return 1

    if args.command == "scan":
        cmd_scan(cfg)
    elif args.command == "organize":
        cmd_organize(cfg, assume_yes=assume_yes)
    elif args.command == "undo":
        cmd_undo(cfg)
    else:
        menu(cfg, config_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
