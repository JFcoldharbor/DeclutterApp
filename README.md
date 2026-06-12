# Declutter

A safe, reversible, cross-platform file organizer with a menu-driven CLI.

It scans messy folders (Desktop, Downloads, …), classifies what it finds —
**code projects, documents, images, audio, video, archives, junk** — and
organizes everything into a clean structure. Built on three rules:

- **Nothing is hard-deleted.** Junk goes to the OS Trash/Recycle Bin (or a
  recoverable quarantine if `send2trash` isn't installed).
- **Preview before you commit.** `scan` shows the full plan; `organize` asks
  to confirm.
- **Always undoable.** Every run writes a manifest; `undo` reverses it.

Works on **macOS, Windows, and Linux**.

## Install

```bash
pip install declutter-cli            # core (quarantine-based trash, JSON config)
pip install "declutter-cli[full]"    # + real OS Trash + YAML config (recommended)
```

Or run from source:

```bash
git clone https://github.com/JFcoldharbor/declutter
cd declutter
pip install -e ".[full]"
```

## Use

```bash
declutter                 # interactive menu
declutter scan            # preview the plan (no changes)
declutter organize        # do it (asks to confirm; --yes to skip)
declutter undo            # reverse the most recent run
declutter init my.yaml    # write an example config to edit
declutter scan --config my.yaml
```

### Interactive menu

```
[1] Scan & preview   [2] Organize   [3] Undo last run
[4] Show config      [5] Write example config   [q] Quit
```

## How it decides

| Item | Rule | Goes to |
|------|------|---------|
| A config that references siblings (`firebase.json`, `docker-compose.yml`, `vercel.json`, …) | **bundle guard** | `<dest>/Code/<name>/` — config + everything it references, kept together |
| Folder with a project marker (`.git`, `package.json`, `*.xcodeproj`, `Cargo.toml`, …) | code project | `<dest>/Code/<name>` |
| Empty folder / 0-byte file / `*.crdownload`, `.DS_Store` | junk | Trash (recoverable) |
| File whose name matches a `keyword_route` | your rule | the folder you chose |
| File with a known extension | by category | `<dest>/<Category>/` |
| Anything else | unsure | `<dest>/_Unsorted/` |

Plain (non-project) folders are left alone unless `move_other_dirs: true`.

### Config-bundle guard

Some config files point at sibling files/dirs by **relative path** — e.g.
`firebase.json` references `functions/`, `firestore.rules`, `storage.rules`.
Sorting those individually moves the config away from what it references and
silently breaks deploys. Declutter detects an anchor config sitting loose,
resolves the paths it binds (structurally for `firebase.json`, via a safe
text scan for others), and moves the whole set together into one
`Code/<name>/` folder — so it stays runnable. Companion files like
`.firebaserc` / `.env` ride along. Toggle with `bundle_configs`; add your own
anchors with `anchor_configs: [my-tool.json]`.

## Windows notes

Declutter runs natively on Windows — the engine is pure `pathlib`/`shutil`, and
junk recognition already covers `Thumbs.db` and `desktop.ini`. Two things worth
knowing:

- **Real Recycle Bin needs the `[full]` extra.** Plain `pip install declutter-cli`
  uses the recoverable quarantine (still safe, still `undo`-able). Install
  `"declutter-cli[full]"` to send junk to the actual Windows Recycle Bin via
  `send2trash`.
- **OneDrive-redirected folders.** On many Windows machines, Desktop and Downloads
  are redirected into OneDrive (`%USERPROFILE%\OneDrive\Desktop`), so the default
  `sources: [~/Desktop, ~/Downloads]` may point at the wrong place. If a scan finds
  nothing, set `sources` explicitly in your config to the real paths.

Console output auto-selects UTF-8 and degrades to ASCII when a stream can't encode
it, so redirecting or piping output (`declutter scan > out.txt`) won't crash.

## Configure

All rules live in a YAML (or JSON) file — no personal data is baked in.
`declutter init` writes a commented starter. Tailor `sources`, `dest_root`,
`categories`, and `keyword_routes` (e.g. route everything containing `invoice`
into `Documents/Finance`).

## Safety model

- Moves are collision-safe (`name (1).ext`).
- The destination is never re-scanned into itself.
- Manifests live in `<dest>/.declutter/`. Quarantined junk lives in
  `<dest>/.declutter/quarantine/` and is restored by `undo`. Items sent to the
  real OS Trash must be restored from there manually.

## License

MIT
