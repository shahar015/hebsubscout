# HebSubScout 🎬

A complete Kodi addon ecosystem built for the Israeli community. Browse, stream, and get Hebrew subtitles — all in one place.

## What's Inside

| Addon | Description |
|-------|-------------|
| **HebScout** (`plugin.video.hebscout`) | Full video addon: TMDB browsing, Real Debrid, Trakt, source scraping |
| **HebSubScout Module** (`script.module.hebsubscout`) | Shared library for Hebrew subtitle intelligence — any addon can import it |
| **HebSubScout Subtitles** (`service.subtitles.hebsubscout`) | Subtitle downloader + floating picker overlay with match percentages |
| **Context Menu** (`context.hebsubscout`) | Right-click any title in any addon → check Hebrew subtitle availability |
| **Repository** (`repository.hebsubscout`) | Kodi repository for auto-install and auto-updates |

## Install

1. Kodi → Settings → File Manager → Add Source → `https://shahar015.github.io/hebsubscout`
2. Add-ons → Install from zip → `repository.hebsubscout-1.0.0.zip`
3. Add-ons → Install from repository → HebSubScout Repository → Video add-ons → **HebScout** → Install

Dependencies install automatically.

## Key Features

- **Hebrew subtitle matching** — see subtitle match percentage on every source *before* you pick it
- **Auto-subtitle download** — best matching subtitle downloads and applies automatically when playback starts
- **Subtitle picker** — floating popup during playback to switch subtitles with download progress
- **Netflix-style progress saving** — saves your position every 30 seconds (survives crashes and power outages)
- **Source filters** — filter by quality, RD cached, subtitle match percentage
- **No external subtitle addons needed** — Wizdom, Ktuvit, and OpenSubtitles are built in
- **Lightweight** — just an addon, not a build. No heavy skins. Runs on any Android TV box

## For Addon Developers

HebSubScout Module works like CocoScrapers — any addon can integrate with 5 lines:

```python
from hebsubscout import SubScout
scout = SubScout()
enriched = scout.check_sources(imdb_id, your_sources, season, episode)
for src in enriched:
    label += scout.format_label(src)  # Adds "עב 92%" indicator
```

See [docs/INTEGRATION.md](docs/INTEGRATION.md) for full documentation.

## Requirements

- **TMDB API Key** (free) — [themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)
- **Real Debrid account** — [real-debrid.com](https://real-debrid.com)
- **Trakt account** (optional) — [trakt.tv/oauth/applications](https://trakt.tv/oauth/applications)

## Development

After modifying any addon source, bump its version in `addon.xml` and run:

```bash
python3 generate_repo.py
```

This rebuilds all zips and the `addons.xml` manifest. Commit and push — Kodi picks up updates automatically.

## License

GPL-3.0
