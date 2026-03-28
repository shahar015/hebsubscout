# CLAUDE.md

## IMPORTANT: Session Maintenance
**Every Claude Code session MUST update this file before ending.** Update:
- The **Change Log** section with what was done this session
- The **Current TODOs** section with completed/new items
- Any architecture, API, or file structure changes
- Update this file **incrementally throughout the session**, not just at the end

## CRITICAL: Version & Release Workflow
**NEVER push multiple code changes under the same version number.**
- Bump the version ONCE at the very end, after ALL fixes are confirmed working
- If the user needs to test mid-session, bump the version BEFORE pushing
- Kodi caches repo addons.xml for up to 24 hours — same version = no update detected
- The user should never have to uninstall+reinstall to get updates
- Workflow: code → test locally if possible → bump ALL addon.xml versions → generate_repo.py → delete old zips → update index.html files → commit → push
- Kodi source URL: `https://shahar015.github.io/hebsubscout/repo` (note the /repo)
- Kodi log on this machine: `C:\Users\shaha\AppData\Roaming\Kodi\kodi.log`

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
- **Netflix-style progress**: Background thread saves playback position to SQLite every 5 seconds. Survives crashes and power outages.
- **Continue Watching / History**: Trakt-first, local SQLite fallback. When Trakt is connected, menus pull from Trakt API (`sync/playback` and `sync/watched`). When not connected, falls back to local SQLite. Only ONE "המשך צפייה" and ONE "היסטוריה" in the menu — never both sources at once.

## API Credentials (hardcoded, not secrets)

- TMDB API Key: `814542f9e3ac8132198f2b3d541a4bc2` (in `utils.py`)
- Trakt Client ID: `a04728bb8144a61adca51b59ca76f2feff0d8f7467e7747676bfa4ccf4e4bedd` (in `trakt_api.py`)
- Trakt Client Secret: `982ef7cd073011fae61d3a8087dc96fda775ee1d8eda1042c0b4a65ab6cc0872` (in `trakt_api.py`)
- Real Debrid Client ID: `X245A4XAIBGVM` (open source device auth ID, in `realdebrid.py`)

## External APIs

| Service | Base URL | Auth | Used For |
|---------|----------|------|----------|
| TMDB | `api.themoviedb.org/3` | API key in query param | Movie/show browsing, metadata, IMDB IDs |
| Wizdom.xyz | `wizdom.xyz/api/search?action=by_id` | None | Hebrew subtitle search. Also `/api/releases/{imdb}` for fallback. TV shows: subs are nested `subs[season][episode]` |
| Ktuvit.me | `www.ktuvit.me` | Cookie-based login (email + hashed password) | Hebrew subtitle search. Old `api.screwzira.com` is DEAD (bot wall). Uses HTML scraping. |
| OpenSubtitles | `api.opensubtitles.com/api/v1` | API key header | Hebrew subtitle search (optional) |
| Real Debrid | `api.real-debrid.com/rest/1.0` | Bearer token | Torrent cache check, link unrestrict, streaming. OAuth token endpoint requires form-encoded POST (not JSON). Device auth returns `direct_verification_url` for QR codes. |
| Trakt | `api.trakt.tv` | Bearer token + Client ID | Scrobbling, watchlist, progress, history. Device auth URL supports `trakt.tv/activate/{code}` for QR pre-fill. **Scrobble requires >= 1.0% progress.** |
| Torrentio | `torrentio.strem.fun` | None (public) | Source scraping (torrent search) |
| MediaFusion | `mediafusion.elfhosted.com` | May need auth (returns 403 currently) | Source scraping (torrent search) |

## Trakt Scrobble Flow (CRITICAL — match POV/Twilight behavior)

The correct scrobble flow (verified by studying kodi7rd/repository Twilight addon):
1. **`scrobble/start`** — called **ONCE** when playback starts (after progress >= 1%). Never repeated on a timer.
2. **`scrobble/pause`** — called on user pause AND on playback stop (< 80%). This is what saves the resume point to `sync/playback` (powers "Continue Watching").
3. **`scrobble/stop`** — called ONLY when playback ends at >= 80% (marks as watched).
4. **`scrobble/start`** again — only on resume from pause or seek (re-starts the session).

**Key gotchas:**
- Trakt rejects scrobble calls with progress < 1.0%: `"Progress should be at least 1.0% to pause."`
- Calling `scrobble/start` every N seconds **resets the session** — Trakt may discard the subsequent pause if the session is too short
- `scrobble/stop` does NOT save a resume point — it only marks as watched if >= 80%
- `scrobble/pause` is the only way to save a resume point to `sync/playback`
- Trakt website "Continue Watching" may not show all items from `sync/playback` API — the website has its own filtering
- Our `_handle_end()` must use `_last_known_progress` because `getTime()` fails after player is destroyed

## Development Workflow

### CRITICAL: Never push code changes without bumping the version
Kodi caches zips by version. Same version = Kodi won't update even if zip contents changed.

### After modifying any addon code:
```bash
# 1. Make all code changes
# 2. Bump version in ALL 5 addon.xml files (use sed):
for f in plugin.video.hebscout/addon.xml script.module.hebsubscout/addon.xml service.subtitles.hebsubscout/addon.xml context.hebsubscout/addon.xml repository.hebsubscout/addon.xml; do
  sed -i 's/version="OLD"/version="NEW"/' "$f"
done
# 3. Rebuild the repository:
python generate_repo.py
# 4. Delete old version zips:
find repo/ -name "*OLD*" -delete
# 5. Update index.html files:
sed -i 's/OLD/NEW/g' repo/index.html
for dir in plugin.video.hebscout script.module.hebsubscout service.subtitles.hebsubscout context.hebsubscout repository.hebsubscout; do
  cd "repo/$dir" && files="" && for f in $(ls -1 | grep -v index.html); do files="$files<a href=\"$f\">$f</a>\n"; done && printf "<html><body>\n$files</body></html>\n" > index.html && cd ../..
done
# 6. Commit and push
git add -A && git commit -m "vX.Y.Z: description" && git push
```

### Testing in Kodi:
- Kodi log on this PC: `C:\Users\shaha\AppData\Roaming\Kodi\kodi.log`
- Search for `[HebScout]` and `[HebSubScout]` in logs
- Kodi addon files cached at: `%APPDATA%\Kodi\addons\plugin.video.hebscout\`
- If updates not showing: user must uninstall repo+addon, delete cached addon folders, restart Kodi, reinstall
- To check installed version in log: grep for `plugin.video.hebscout v`

### GitHub Pages:
- The `repo/` directory is served via GitHub Pages from `shahar015.github.io/hebsubscout`
- Pages must be enabled: Settings → Pages → main branch, / (root)
- Kodi source URL: `https://shahar015.github.io/hebsubscout/repo` (note: /repo at the end)
- Each subdirectory in repo/ needs an index.html with `<a href>` links for Kodi to browse (GitHub Pages has no directory listing)

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

### Working (verified — v1.2.x complete):
- [x] QR auth dialogs (RD + Trakt) with cancel support
- [x] Source selection screen: WindowXMLDialog, cinematic dark theme, filters, scroll
- [x] Wizdom subtitle search + auto-download + auto-apply during playback
- [x] Ktuvit login (no errors with credentials)
- [x] Subtitle match % on source cards
- [x] Filter buttons (quality/sort/provider) with dim/bright selected state
- [x] Default all qualities selected on fresh install
- [x] Progress tracking: local SQLite saves every 5s, survives player destruction
- [x] Trakt scrobble: start once, pause on stop saves resume point to sync/playback
- [x] Continue watching + History: Trakt-first, local SQLite fallback, single menu each
- [x] Resume dialog ("continue from X%?")
- [x] Player controls work during playback (no WindowDialog stealing input)
- [x] icon.png + fanart.jpg on all 5 addons
- [x] Source card padding (116px height)

### v1.5 — done (partially working, needs fixes):
- [x] Custom skin (`skin.hebscout`) — Estuary fork, OSD buttons render
- [x] Settings/tools menu overhaul — account dashboard, quick toggles, version info
- [x] Search history — SQLite, shown before search input
- [x] Context menu — multi-action dialog (subs, watchlist, watched, similar)
- [x] Skip intro — TheIntroDB integration, window property for skin visibility
- [x] TMDB recommendations — movie/show similar titles

### v1.5 — needs fixing:
- [ ] OSD button "בחירת כתוביות" truncated — widen from 160px to 200px+
- [ ] OSD button focus texture is stretched ellipse — need rectangular style with border
- [ ] OSD subtitle picker opens Kodi's built-in dialog instead of our custom picker with match %
- [ ] Only 1 sub shown (auto-downloaded) — need to show ALL available Hebrew subs from Wizdom/Ktuvit
- [ ] Skin home screen background is black when no item highlighted — set default fanart
- [ ] Source card feature tags (H.265, 4K, HDR10, DOLBY, etc.) — need own row + feature filter
- [ ] Auto-play toggle may have been accidentally enabled during testing — users lose source picker. Default should be OFF.
- [ ] Context menu addon not registering at all — "HebScout" entry doesn't appear in right-click menu for movies or episodes. May need Kodi restart, or the `kodi.context.item` extension point isn't being loaded. Investigate addon installation status.

### Known issues:
- MediaFusion returns HTTP 403 — may need auth token in URL
- RD `instantAvailability` was removed by RD in Nov 2024. Cache check disabled (addMagnet workaround too slow). Cached sources still play instantly when clicked.
- Ktuvit requires user credentials (email + hashed password in settings) — without them only Wizdom is used
- **WindowDialog overlays STEAL ALL PLAYER INPUT** — never use WindowDialog.show() during video playback. It captures focus and blocks play/pause/seek. Use built-in Kodi OSD or a custom skin instead.
- Trakt requires >= 1.0% progress for scrobble calls — guard all scrobble calls
- `getTime()` throws "Kodi is not playing any media file" after player is destroyed — always use `_last_known_progress` as fallback
- Translation keys must be unique Hebrew strings — `up_next` and `continue_watching` both translated to "המשך צפייה" causing duplicate menu entries
- Display labels with `[COLOR]` markup leak into URL params if passed as the title — always separate display label from data title
- Programmatic ControlButton in WindowXMLDialog looks ugly — always use XML-defined buttons instead
- 1x1 white PNG doesn't work as fullscreen texture — use 16x16 minimum
- Player callbacks (onAVStarted) may not fire if _player global gets garbage collected. Keeping the global ref is essential.
- Kodi plugin scripts are short-lived — don't block with waitForAbort loops (causes loading spinner)
- Dual XML skins: changes to source_select must be made in BOTH _rtl.xml and _ltr.xml
- Ktuvit requires user credentials (email + hashed password in settings) — without them only Wizdom is used
- No icon.png or fanart.jpg assets yet for the addons
- **WindowDialog overlays STEAL ALL PLAYER INPUT** — never use WindowDialog.show() during video playback. It captures focus and blocks play/pause/seek. Use built-in Kodi OSD or a custom skin instead.
- Trakt requires >= 1.0% progress for scrobble calls — guard all scrobble calls
- `getTime()` throws "Kodi is not playing any media file" after player is destroyed — always use `_last_known_progress` as fallback
- Translation keys must be unique Hebrew strings — `up_next` and `continue_watching` both translated to "המשך צפייה" causing duplicate menu entries
- Display labels with `[COLOR]` markup leak into URL params if passed as the title — always separate display label from data title
- Programmatic ControlButton in WindowXMLDialog looks ugly — always use XML-defined buttons instead
- 1x1 white PNG doesn't work as fullscreen texture — use 16x16 minimum
- Player callbacks (onAVStarted) may not fire if _player global gets garbage collected. Keeping the global ref is essential.
- Kodi plugin scripts are short-lived — don't block with waitForAbort loops (causes loading spinner)
- Dual XML skins: changes to source_select must be made in BOTH _rtl.xml and _ltr.xml

## Key UI Architecture

### CRITICAL: Kodi Coordinate Systems
- **WindowDialog** (programmatic, no XML): uses **1280x720** virtual coordinate system ALWAYS — regardless of screen resolution
- **WindowXMLDialog** (XML skin): `1080i/` folder uses **1920x1080**; `720p/` folder uses **1280x720**
- **Never use 1920x1080 coordinates in WindowDialog** — this was a major bug that caused off-center rendering
- Kodi skins live in `resources/skins/Default/1080i/filename.xml`

### UI Components
- **QR Auth Dialog:** `utils.py` → `QRAuthDialog(WindowDialog)` — 1280x720 coords, full-screen double-layer black bg + centered panel, QR from api.qrserver.com, xbmc.sleep(200) for responsive cancel
- **Source Selection Screen:** `source_select.py` → `SourceSelectDialog(WindowXMLDialog)` — XML skin at `resources/skins/Default/1080i/source_select.xml`. Cinematic dark theme. Native ControlList for scroll/focus. All filter buttons in XML, labels managed by Python `setLabel()`. Left panel: quality/sort/provider filters + source cards. Right panel: poster + title + rating + genres + plot + director + cast.
- **Subtitle Picker:** `picker.py` → `SubtitlePickerWindow(WindowDialog)` — top-right floating overlay during playback (1280x720 coords)
- **Player OSD Buttons:** DEFERRED to v1.5 (custom skin). WindowDialog overlays steal player input — cannot be used during playback.
- **Translation system:** `utils.py` → `t(key, *args)` function with `_STRINGS` dict (Hebrew/English)
- **White texture:** `resources/skins/Default/media/white.png` — 16x16 solid white PNG for colorDiffuse tinting. `_get_white_texture()` returns absolute path for programmatic controls.

### Source Selection Architecture (v1.1.0)
- XML defines: backgrounds, filter buttons (uniform width), ControlList with itemlayout/focusedlayout, right info panel
- Python defines: data population, filter state management, label updates for selected/unselected
- Filter buttons: XML `<control type="button">`, Python calls `setLabel('[COLOR ...]...')` for selected state
- Source cards: `ListItem.setProperty('quality'/'provider'/'sub_display'/etc)`, XML reads via `$INFO[ListItem.Property(name)]`
- Quality badge: dimmed (88000000 overlay) when unfocused, full color when focused
- Focused card: quality-colored 2px border glow + brighter background
- **NEVER use programmatic ControlButton in WindowXMLDialog** — they look wrong. Always define buttons in XML.
- **Texture must be 16x16+ pixels** — 1x1 PNG doesn't render as fullscreen texture reliably
- Reference implementation: Twilight (kodi7rd/repository) uses same pattern — white.png + colordiffuse, all XML controls, Python only populates data

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

### 2026-03-26 — Session 3: Major UI overhaul + API fixes
- v1.0.3: Custom source selection screen (source_select.py), QR dialogs, subtitle OSD
- v1.0.3 (hotfix commits): Fixed QR background (full-screen black dimmer), scroll perf, chip toggle
- v1.0.3 (hotfix commits): Fixed Wizdom API (new endpoints), rewrote Ktuvit provider (ktuvit.me direct)
- v1.0.3 (hotfix commits): RD QR uses direct_verification_url for auto-authorize
- v1.0.4: Version bump to force Kodi update (lesson learned: never push code under same version)
- Extended feature detection: DV, HDR10+, HDR10, TrueHD, DTS-HD, AV1, AAC
- Added cast/director to show_details() for TV shows
- Added Ktuvit email/password settings
- Added subtitle search notifications during playback
- Added subtitle picker OSD button ("CC עב") during playback
- Updated CLAUDE.md with proper versioning workflow and API docs
- v1.0.5: Fixed IndentationError in providers.py (leftover Python 2 shim line)
- v1.0.6: Rewrote source_select.py to WindowXMLDialog + XML skin
- v1.0.7: Fixed WindowXMLDialog constructor (__new__ override for Kodi bindings)
- v1.0.8: Fixed XML textures (white.png not `-`), togglebutton→button, Unicode ✗→X
- v1.0.9: QR dialog double-layer backgrounds for opacity
- v1.0.10: QR cancel fix (xbmc.sleep 200ms instead of time.sleep 5s)
- v1.0.11: backgroundcolor, badge 80px, Unicode cleanup, filter label sync
- v1.0.12: Hebrew labels, provider filter row, default empty quality
- v1.0.13: Button widths for Hebrew, window type change
- v1.0.14: Dynamic Python buttons (looked bad, reverted in 1.1.0)
- v1.0.15: Absolute texture paths for programmatic buttons
- v1.0.16: 16x16 white.png (1x1 was too small for Kodi)
- **v1.1.0: Complete source screen redesign** — cinematic dark theme, all XML buttons, clean architecture
- v1.1.1: RTL filter layout, wider buttons (130/235px), quality badge 90px
- v1.1.2: RTL text alignment in chips and right panel, Hebrew label updates
- v1.1.3: Dual XML skins (source_select_rtl.xml / source_select_ltr.xml) for i18n
- v1.1.4: Sub display "50% התאמה לכתוביות"
- v1.1.5: Fixed player callbacks (script was exiting before onAVStarted), subtitle service now required dependency
- v1.1.6: Removed waitForAbort loop that caused loading spinner during playback

### 2026-03-27 — Session 4: Player callbacks fix + Ktuvit setup + QR fix
- v1.1.7: Fixed player callbacks (endOfDirectory + wait loop keeps script alive without spinner)
- v1.1.7: Fixed RD QR dialog showing full direct_verification_url — now shows friendly real-debrid.com/device
- v1.1.7: Added Ktuvit credentials setup to first-run wizard (email + password with SHA-256 hashing)
- v1.1.7: Subtitle OSD button ("CC עב") now appears during playback (was broken because onAVStarted never fired)
- v1.1.8: Added local "המשך צפייה" (continue watching) + "היסטוריה" (history) menus from SQLite bookmarks
- v1.1.8: Changed progress save interval from 30s to 5s for more reliable resume
- v1.1.8: Bookmark table now stores title/poster/fanart/media_type metadata for display
- v1.1.8: Added Trakt token refresh before API calls (refresh_token() in _api_get/_api_post)
- v1.1.8: Added debug logging to Trakt scrobble payload to diagnose 422 errors
- v1.1.8: Ensured episode field always included in scrobble payload (season + number)
- v1.1.8: Removed broken SubtitleOSDOverlay (WindowDialog can't capture input over video player)

### 2026-03-27 — Session 5: Trakt scrobble fix + progress tracking + menu consolidation
- v1.1.9: Fix bookmark overwrite on stop (`_last_known_progress` fallback when `getTime()` fails)
- v1.1.9: ProgressTracker updates `_last_known_progress` on every save; `_handle_end` won't overwrite with 0%
- v1.2.0: CRITICAL fix — removed WindowDialog OSD overlay that stole all player input (play/pause/seek broken)
- v1.2.0: Trakt 422 fix: guard all scrobble calls with `progress >= 1.0` (Trakt error: "Progress should be at least 1.0%")
- v1.2.0: Lower continue watching threshold from 5% to 1%
- v1.2.0: Fix title pollution — `[COLOR]` markup no longer leaks from display labels into URL params
- v1.2.1: Unified menus (Trakt-first, local fallback): ONE "המשך צפייה" + ONE "היסטוריה"
- v1.2.1: Continue watching pulls from `trakt.playback_progress()` when connected, local SQLite otherwise
- v1.2.1: History pulls from `trakt.watched_movies()` + `watched_shows()` when connected
- v1.2.1: Removed duplicate "watch progress" Trakt menu entry
- v1.2.2: Fix `up_next` Hebrew translation: was "המשך צפייה" (duplicate), now "פרק הבא"
- v1.2.2: Use `scrobble/pause` (not `scrobble/stop`) when user stops mid-watch — pause saves resume point
- v1.2.3: Send `scrobble/start` ONCE when progress reaches 1% — not every 5s (was resetting Trakt session)
- v1.2.3: Log full Trakt response bodies for debugging (confirmed scrobble works: Trakt returns show/episode IDs)
- v1.2.3: Verified scrobble flow matches POV/Twilight (kodi7rd): start once → pause to save → stop only at >= 80%
- v1.2.4: Added icon.png (256x256) and fanart.jpg (1920x1080) to all 5 addons with `<assets>` in addon.xml
- v1.2.5: Replaced dead `instantAvailability` with addMagnet workaround (3 API calls per source)
- v1.2.6: Disabled RD cache check (addMagnet too slow — 30 API calls for 10 sources). Source card height 104→116px for padding
- v1.2.7: Default all qualities selected on fresh install. Dim unselected filter buttons (FF333345) for clear on/off distinction

### 2026-03-28 — Session 6: v1.5.0 — Custom skin, skip intro, settings overhaul, search history
- v1.5.0: Major release: custom skin (skin.hebscout), skip intro (TheIntroDB), settings overhaul, search history, context menu, TMDB recommendations
- v1.5.1: Fix skin font (revert to NotoSans), fix context menu visibility
- v1.5.2: Fix skin directory structure (textures/fonts were nested)
- v1.5.3: Fix stray character in VideoOSD.xml breaking custom buttons
- v1.5.4: Text labels on OSD buttons, fix subtitle picker action
