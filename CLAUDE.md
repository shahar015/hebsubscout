# CLAUDE.md

## IMPORTANT: Session Maintenance
**Every Claude Code session MUST update this file before ending.** Update:
- The **Change Log** section with what was done this session
- The **Current TODOs** section with completed/new items
- Any architecture or file structure changes

---

## Project Overview

HebSubScout is a Kodi addon ecosystem built for the Israeli community. It provides video browsing (TMDB), streaming (Real Debrid), watch tracking (Trakt), and a unique Hebrew subtitle matching system that shows subtitle availability and match percentage BEFORE the user picks a source.

The project ships as a Kodi repository containing 5 addons that auto-install via dependency resolution.

## Repository Structure

```
hebsubscout/
├── script.module.hebsubscout/          # Shared Python module (like CocoScrapers)
│   ├── addon.xml
│   └── lib/hebsubscout/
│       ├── __init__.py                 # Public exports: SubScout, ReleaseMatcher, providers
│       ├── scout.py                    # SubScout class - main API for addon developers
│       ├── matcher.py                  # Fuzzy release name matching algorithm (0-100 scoring)
│       └── providers.py               # API integrations: Wizdom.xyz, Ktuvit.me, OpenSubtitles
│
├── plugin.video.hebscout/             # Main video addon (the user-facing app)
│   ├── addon.xml
│   ├── default.py                     # Router + all menu/UI logic + first-run setup
│   └── resources/
│       ├── settings.xml
│       └── lib/
│           ├── modules/
│           │   ├── utils.py           # HTTP helpers, logging, settings, TMDB_KEY lives here
│           │   ├── tmdb.py            # Full TMDB API: trending, popular, search, genres, details
│           │   ├── realdebrid.py      # RD: device auth, cache check, unrestrict, magnet resolve
│           │   ├── trakt_api.py       # Trakt: OAuth, scrobble, watchlist, progress, next up
│           │   ├── sources.py         # Orchestrator: scrape → RD check → HebSubScout enrich
│           │   ├── player.py          # Custom player: Netflix-style progress saving, auto-subs
│           │   └── cache.py           # SQLite cache + bookmarks + watched state
│           └── scrapers/
│               └── __init__.py        # Built-in scrapers: Torrentio, MediaFusion, external
│
├── service.subtitles.hebsubscout/     # Subtitle service addon
│   ├── addon.xml
│   ├── service.py                     # Kodi subtitle service interface (CC button)
│   ├── downloader.py                  # Downloads .srt from Wizdom/Ktuvit/OpenSubs
│   └── picker.py                      # Floating subtitle picker overlay (WindowDialog)
│
├── context.hebsubscout/               # Context menu addon
│   ├── addon.xml
│   └── context_check.py              # Right-click "Check Hebrew Subs" on any title
│
├── repository.hebsubscout/            # Repository addon (users install this first)
│   └── addon.xml                      # Points to shahar015.github.io/hebsubscout
│
├── repo/                              # Built repository (GitHub Pages serves this)
│   ├── addons.xml                     # Combined manifest of all addons
│   ├── addons.xml.md5
│   ├── index.html                     # Hebrew install instructions page
│   ├── repository.hebsubscout-1.0.0.zip
│   └── {addon_id}/                    # Each addon has a subfolder with its zip + addon.xml
│
├── generate_repo.py                   # Run after ANY addon change to rebuild repo/
├── docs/INTEGRATION.md                # Guide for other addon developers to integrate
├── README.md
└── .gitignore
```

## Key Architecture Decisions

- **Module pattern**: `script.module.hebsubscout` is a shared library any Kodi addon can import. Other addons add `<import addon="script.module.hebsubscout"/>` to their addon.xml and call `from hebsubscout import SubScout`.
- **No build step**: Kodi runs raw Python files. No compilation, no bundling, no .env files.
- **API keys are hardcoded**: TMDB key and Trakt Client ID/Secret ship in source code. This is standard for all Kodi addons (POV, Seren, Umbrella all do this). These are app identifiers, not user secrets. User-specific tokens (RD, Trakt OAuth) are stored in Kodi's local settings.
- **Dependency auto-resolution**: Installing `plugin.video.hebscout` from the repository auto-installs `script.module.hebsubscout` (required) and `service.subtitles.hebsubscout` (optional).
- **Netflix-style progress**: Background thread saves playback position to SQLite every 30 seconds. Survives crashes and power outages.

## API Credentials (hardcoded, not secrets)

- TMDB API Key: `814542f9e3ac8132198f2b3d541a4bc2` (in `utils.py`)
- Trakt Client ID: `a04728bb8144a61adca51b59ca76f2feff0d8f7467e7747676bfa4ccf4e4bedd` (in `trakt_api.py`)
- Trakt Client Secret: `982ef7cd073011fae61d3a8087dc96fda775ee1d8eda1042c0b4a65ab6cc0872` (in `trakt_api.py`)
- Real Debrid Client ID: `X245A4XAIBGVM` (open source device auth ID, in `realdebrid.py`)

## External APIs

| Service | Base URL | Auth | Used For |
|---------|----------|------|----------|
| TMDB | `api.themoviedb.org/3` | API key in query param | Movie/show browsing, metadata, IMDB IDs |
| Wizdom.xyz | `wizdom.xyz/api` | None | Hebrew subtitle search + download |
| Ktuvit/ScrewZira | `api.screwzira.com` | None for search | Hebrew subtitle search + download |
| OpenSubtitles | `api.opensubtitles.com/api/v1` | API key header | Hebrew subtitle search (optional) |
| Real Debrid | `api.real-debrid.com/rest/1.0` | Bearer token | Torrent cache check, link unrestrict, streaming |
| Trakt | `api.trakt.tv` | Bearer token + Client ID | Scrobbling, watchlist, progress, history |
| Torrentio | `torrentio.strem.fun` | None (public) | Source scraping (torrent search) |
| MediaFusion | `mediafusion.elfhosted.com` | None (public) | Source scraping (torrent search) |

## Development Workflow

### After modifying any addon code:
```bash
# 1. Bump version in that addon's addon.xml (e.g. 1.0.0 → 1.0.1)
# 2. Rebuild the repository:
python3 generate_repo.py
# 3. Commit and push - Kodi auto-updates within 24 hours
git add .
git commit -m "description of changes"
git push
```

### Testing in Kodi:
- Kodi log location: `~/.kodi/temp/kodi.log` (Linux), `%APPDATA%\Kodi\temp\kodi.log` (Windows)
- Search for `[HebScout]` and `[HebSubScout]` in logs
- To force-reinstall during development: uninstall addon in Kodi, delete the zip from `repo/`, regenerate, push, reinstall

### GitHub Pages:
- The `repo/` directory is served via GitHub Pages from `shahar015.github.io/hebsubscout`
- Pages must be enabled: Settings → Pages → main branch, / (root)
- Kodi source URL: `https://shahar015.github.io/hebsubscout`

## Kodi Addon Conventions

- **Python version**: Kodi 19+ uses Python 3. All code must be Python 3 compatible.
- **addon.xml**: Every addon has one. Declares ID, version, dependencies, and metadata.
- **Imports**: Use `xbmc`, `xbmcgui`, `xbmcplugin`, `xbmcaddon`, `xbmcvfs` for Kodi APIs. These are only available inside Kodi runtime, not in standalone Python.
- **Settings**: Defined in `resources/settings.xml`. Read with `xbmcaddon.Addon().getSetting('key')`.
- **URL routing**: Kodi calls `default.py` with `sys.argv[0]` (base URL) and `sys.argv[2]` (query params). The router in `default.py` dispatches to functions.
- **ListItems**: All UI is built with `xbmcgui.ListItem` + `xbmcplugin.addDirectoryItem()`.
- **Color tags**: Use `[COLOR lime]text[/COLOR]` in labels for colored text.
- **Hebrew/RTL**: Kodi handles RTL automatically when the label contains Hebrew characters.

## Common Tasks

### Add a new TMDB category
1. Add the API function in `tmdb.py`
2. Add a menu entry in `default.py` (in the appropriate menu function)
3. Add the router case in the `router()` function at the bottom of `default.py`

### Add a new scraper source
1. Add the scraper function in `scrapers/__init__.py`
2. Call it from `scrape_all()` in the same file
3. Add an enable/disable setting in `resources/settings.xml`

### Modify subtitle matching algorithm
Edit `script.module.hebsubscout/lib/hebsubscout/matcher.py`. The scoring weights are in `compute_match_score()`. After changes, run `generate_repo.py` to rebuild.

### Add a new subtitle provider
1. Add a new provider class in `script.module.hebsubscout/lib/hebsubscout/providers.py`
2. Add the download function in `service.subtitles.hebsubscout/downloader.py`
3. Register it in `scout.py`'s `__init__` and `fetch_subtitles()`

## Current TODOs

- [ ] Custom source selection screen with filter chips, source cards, movie info panel (`source_select.py`)
- [ ] Subtitle search notifications during playback (search start/found/applied)
- [ ] Subtitle picker OSD button during playback ("CC עב" button + T key interception)
- [ ] Subtitle picker popup during playback (picker.py already exists, needs trigger)
- Scraper APIs (Torrentio/MediaFusion) may need RD token in URL for cached-only results
- Wizdom/Ktuvit download endpoints need live testing — response formats may differ from documentation
- No external scraper module hot-loading yet (CocoScrapers integration is basic)
- No icon.png or fanart.jpg assets yet for the addons

## Key UI Architecture

- **QR Auth Dialog:** `utils.py` → `QRAuthDialog(WindowDialog)` — full-screen dimmer + centered dialog with QR code from api.qrserver.com, URL, device code, progress bar
- **Source Selection Screen:** `source_select.py` → `SourceSelectDialog(WindowDialog)` — full-screen dark overlay, left panel (filter chips + scrollable source cards), right panel (poster + plot + cast)
- **Subtitle Picker:** `picker.py` → `SubtitlePickerWindow(WindowDialog)` — top-right floating overlay during playback, shows subs with match %, download progress, auto-close
- **Translation system:** `utils.py` → `t(key, *args)` function with `_STRINGS` dict (Hebrew/English), controlled by `ui_language` setting
- **White texture helper:** `utils.py` → `_get_white_texture()` creates 1x1 white PNG for WindowDialog solid-color backgrounds via colorDiffuse

## Change Log

### 2026-03-26 — Session 1: Initial setup
- Initial release v1.0.0

### 2026-03-26 — Session 2: API keys, i18n, bug fixes, refactoring
- Embedded TMDB/Trakt API keys (removed manual key entry)
- Simplified first-run setup (only RD auth required, Trakt optional)
- Added Hebrew/English UI language toggle with `t()` translation system (~70 strings)
- Fixed: list_action kwarg leaking into TMDB API calls
- Fixed: deprecated `setInfo()` → use InfoTag API (Kodi 21 compat)
- Fixed: subtitle service import paths (use xbmcaddon path resolution)
- Fixed: picker.py wrong import path
- Fixed: next-episode dict key mismatch causing TypeError
- Fixed: service.py log() signature (1 arg → 2 args)
- Fixed: os.makedirs('') edge case in matcher.py
- Fixed: Real Debrid auth (form-encoded POST, not JSON, for token endpoint)
- Removed all Python 2 compatibility shims
- Refactored: list_movies/list_shows → shared _list_items helper
- Refactored: scrape_torrentio/scrape_mediafusion → shared _scrape_stremio
- Refactored: 14 TMDB list functions → _list() helper
- Refactored: filter dispatch to use (label, func) pairs instead of index math
- Refactored: cache.py DDL runs once at init, named columns in SELECT
- Added QR code auth dialogs for RD and Trakt
- Added GitHub Pages directory index.html files for Kodi repo browsing
- Added Hebrew description to subtitle service addon.xml
- Version bumped to 1.0.2

### 2026-03-26 — Session 3: Major UI overhaul (in progress)
- Fixed QR dialog visuals (dimmer layer, safe fonts)
- Added device code to Trakt QR URL
- Extended feature detection (DV, HDR10+)
- Added cast/director to show_details()
- NEW: Custom source selection screen (source_select.py)
- Added subtitle search notifications during playback
- Added subtitle picker OSD button during playback
- Version bumped to 1.0.3
