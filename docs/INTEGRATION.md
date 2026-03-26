# HebSubScout - Hebrew Subtitle Scout for Kodi

## What Is This?

HebSubScout is a **shared Kodi module** (like CocoScrapers) that lets any video addon check Hebrew subtitle availability **before** the user picks a source.

It solves the #1 pain point for Israeli Kodi users switching from the Twilight build: losing the built-in Hebrew subtitle matching indicator in the source list.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     YOUR VIDEO ADDON                         │
│                  (POV, Twilight, Umbrella, etc.)             │
│                                                              │
│  1. Scrape sources normally                                  │
│  2. Call scout.check_sources(imdb_id, sources) ◄── 5 LINES │
│  3. Render enriched source list with sub indicators          │
└──────────────────────┬──────────────────────────────────────┘
                       │ imports
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              script.module.hebsubscout                        │
│              (THE SHARED MODULE)                             │
│                                                              │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────┐    │
│  │   SubScout   │  │   Matcher   │  │    Providers     │    │
│  │  (main API)  │──│  (fuzzy     │──│  ┌──────────┐    │    │
│  │              │  │   matching) │  │  │ Wizdom   │    │    │
│  └─────────────┘  └─────────────┘  │  │ Ktuvit   │    │    │
│                                     │  │ OpenSubs │    │    │
│  ┌─────────────┐                    │  └──────────┘    │    │
│  │  Learning   │                    └──────────────────┘    │
│  │  Database   │                                            │
│  └─────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼ queries
┌──────────────────────────────────────┐
│       Hebrew Subtitle APIs           │
│  • wizdom.xyz/api/                   │
│  • api.screwzira.com/               │
│  • api.opensubtitles.com/           │
└──────────────────────────────────────┘
```

## Three Addons in This Project

| Addon | ID | Purpose |
|-------|-----|---------|
| **Shared Module** | `script.module.hebsubscout` | The library other addons import. Like CocoScrapers. |
| **Standalone Addon** | `plugin.video.hebsubscout` | Your own addon for checking subs + reference implementation |
| **Context Menu** | `context.hebsubscout` | Right-click "Check Hebrew Subs" on ANY title in ANY addon |

## Integration Guide for Addon Developers

### Step 1: Add dependency

In your `addon.xml`:
```xml
<import addon="script.module.hebsubscout" version="1.0.0"/>
```

### Step 2: Import and use (5 lines!)

```python
from hebsubscout import SubScout

scout = SubScout()

# After you scrape your sources, enrich them:
enriched_sources = scout.check_sources(
    imdb_id='tt1234567',
    sources=your_scraped_sources,  # List of dicts, each with 'name' key
    season=1,      # None for movies
    episode=5      # None for movies  
)

# Each source now has subtitle data:
for src in enriched_sources:
    label = src['name']
    label += scout.format_label(src)  # Adds "[COLOR lime]עב 92%[/COLOR]"
```

### What gets added to each source:

```python
{
    # Your original source data preserved as-is
    'name': 'Movie.2024.1080p.BluRay.x264-SPARKS',
    'url': '...',
    'quality': '1080p',
    # ... etc
    
    # NEW - added by HebSubScout:
    'has_hebrew_subs': True,
    'best_match_pct': 92,           # 0-100 confidence
    'best_match_source': 'wizdom',  # Which provider
    'best_match_name': 'Movie.2024.1080p.BluRay.x264-SPARKS',  # Matching sub
    'all_matches': [                # All matches sorted by score
        {'score': 92, 'subtitle_name': '...', 'provider': 'wizdom', 'subtitle_id': '123'},
        {'score': 78, 'subtitle_name': '...', 'provider': 'ktuvit', 'subtitle_id': '456'},
    ]
}
```

### Example: Integrating with POV

In POV's source rendering code (roughly `modules/sources.py`):

```python
# BEFORE (original POV code):
def display_sources(self, sources, imdb_id, season=None, episode=None):
    for source in sources:
        label = self.build_label(source)
        # ... add to list

# AFTER (with HebSubScout):
def display_sources(self, sources, imdb_id, season=None, episode=None):
    try:
        from hebsubscout import SubScout
        scout = SubScout()
        sources = scout.check_sources(imdb_id, sources, season, episode)
    except ImportError:
        pass  # Module not installed, degrade gracefully
    
    for source in sources:
        label = self.build_label(source)
        if source.get('has_hebrew_subs'):
            pct = source['best_match_pct']
            color = 'lime' if pct >= 90 else 'yellow' if pct >= 70 else 'orange'
            label += ' [COLOR {}]עב {}%[/COLOR]'.format(color, pct)
        # ... add to list
```

## The Matching Algorithm

The fuzzy matcher (`matcher.py`) scores subtitle matches 0-100 by comparing:

| Component | Weight | What it compares |
|-----------|--------|-----------------|
| Title | 30pts | Movie/show name tokens |
| Quality | 25pts | Resolution (1080p, 720p, etc.) |
| Release Group | 20pts | Group name (-SPARKS, -YTS, etc.) |
| Codec | 10pts | x264, x265, HEVC, etc. |
| Season/Episode | 10pts | S01E05 matching |
| Audio | 5pts | DTS, AC3, AAC, etc. |

**The Learning Database** ("מאגר לומד"): When a user successfully plays with a subtitle, call `scout.record_match(source_name, sub_name, provider)` and future lookups for similar sources will prefer that subtitle. Stored as a JSON file.

## API Reference

### Wizdom.xyz
- `GET https://wizdom.xyz/api/search.id.php?imdb={id}&season={s}&episode={e}&version={filename}`
- `GET https://wizdom.xyz/api/releases/{imdb_id}`
- No auth needed for search

### Ktuvit.me (ScrewZira)
- `POST http://api.screwzira.com/FindFilm` — `{"request":{"SearchPhrase":"tt...","SearchType":"ImdbID","Version":"1.0"}}`
- `POST http://api.screwzira.com/FindSeries` — same format
- Returns: `{"d": "{\"Results\":[{\"SubtitleName\":\"...\",\"Identifier\":\"...\"}],\"IsSuccess\":true}"}`

### OpenSubtitles
- `GET https://api.opensubtitles.com/api/v1/subtitles?imdb_id={id}&languages=he`
- Requires API key header

## Repository Structure

```
hebsubscout/
├── script.module.hebsubscout/        # THE SHARED MODULE
│   ├── addon.xml
│   └── lib/
│       └── hebsubscout/
│           ├── __init__.py           # Package init + exports
│           ├── scout.py              # SubScout main class
│           ├── matcher.py            # Fuzzy release name matcher
│           └── providers.py          # Wizdom, Ktuvit, OpenSubs APIs
│
├── plugin.video.hebsubscout/         # STANDALONE ADDON
│   ├── addon.xml
│   ├── default.py                    # UI + reference implementation
│   └── resources/
│       └── settings.xml
│
├── context.hebsubscout/              # CONTEXT MENU ADDON
│   ├── addon.xml
│   └── context_check.py             # Right-click check for any title
│
└── docs/
    └── INTEGRATION.md                # This file
```

## FAQ

**Q: Will this slow down source scraping?**
A: The subtitle APIs are fast (usually <1s each) and results are cached for 30 minutes. The matching algorithm itself is pure Python string comparison — negligible overhead.

**Q: Does this download subtitles?**
A: No! It only CHECKS availability and match quality. Downloading is handled by your subtitle addon (DarkSubs, All Subs Plus, a4kSubtitles, etc.)

**Q: Can addon devs make this optional?**
A: Yes! Wrap the import in try/except. If the module isn't installed, your addon works exactly as before.

**Q: How is this different from DarkSubs/All Subs?**  
A: Those are subtitle SERVICE addons that download subs during/after playback. HebSubScout checks availability BEFORE you pick a source, so you can choose a source that has good Hebrew subtitle matches.
