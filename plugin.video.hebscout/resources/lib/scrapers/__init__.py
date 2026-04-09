# -*- coding: utf-8 -*-
"""
Built-in Scrapers
=================
Searches torrent indexers and checks Real Debrid cache.
Also supports external scraper modules (CocoScrapers pattern).
"""

import re
import hashlib
from resources.lib.modules.utils import http_get, http_get_raw, log

from urllib.parse import quote_plus, urlencode


QUALITY_ORDER = {'4k': 0, '2160p': 0, '1080p': 1, '720p': 2, '480p': 3, 'sd': 4}


def _detect_quality(name):
    name_lower = name.lower()
    if any(q in name_lower for q in ('2160p', '4k', 'uhd')):
        return '4K'
    elif '1080p' in name_lower:
        return '1080p'
    elif '720p' in name_lower:
        return '720p'
    elif '480p' in name_lower:
        return '480p'
    return 'SD'


def _detect_info(name):
    """Extract codec, audio, HDR, and feature tags from release name."""
    info = []
    name_lower = name.lower()
    # Codec
    if any(x in name_lower for x in ('hevc', 'x265', 'h265', 'h.265')):
        info.append('H.265')
    elif any(x in name_lower for x in ('x264', 'h264', 'h.264')):
        info.append('H.264')
    elif 'av1' in name_lower:
        info.append('AV1')
    # HDR / Dolby Vision
    if any(x in name_lower for x in ('dolby.vision', 'dolbyvision', '.dv.', ' dv ', 'dovi')):
        info.append('DV')
    if 'hdr10+' in name_lower or 'hdr10plus' in name_lower:
        info.append('HDR10+')
    elif 'hdr10' in name_lower:
        info.append('HDR10')
    elif 'hdr' in name_lower:
        info.append('HDR')
    # Release type
    if 'remux' in name_lower:
        info.append('REMUX')
    if 'bluray' in name_lower or 'blu-ray' in name_lower:
        info.append('BluRay')
    elif 'web-dl' in name_lower or 'webdl' in name_lower:
        info.append('WEB-DL')
    elif 'webrip' in name_lower:
        info.append('WEBRip')
    # Audio format
    if 'atmos' in name_lower:
        info.append('Atmos')
    if 'truehd' in name_lower:
        info.append('TrueHD')
    if 'dts-hd' in name_lower or 'dtshd' in name_lower or 'dts.hd' in name_lower:
        info.append('DTS-HD')
    elif 'dts' in name_lower:
        info.append('DTS')
    if any(x in name_lower for x in ('ddp5', 'dd+', 'ddplus', 'eac3', 'ddp')):
        info.append('DD+')
    elif any(x in name_lower for x in ('dd5', 'ac3', 'dolby.digital', 'dolbydigital')):
        info.append('DD5.1')
    elif 'aac' in name_lower:
        info.append('AAC')
    # Audio channels
    if '7.1' in name_lower:
        info.append('7.1')
    elif '5.1' in name_lower and 'DD5.1' not in info and 'DD+' not in info:
        info.append('5.1')
    # Multi audio
    if any(x in name_lower for x in ('dual', 'multi', 'dual.audio', 'multi.audio')):
        info.append('Multi')
    return info


def _size_str(size_bytes):
    if not size_bytes:
        return ''
    gb = size_bytes / (1024 * 1024 * 1024)
    if gb >= 1:
        return '{:.1f} GB'.format(gb)
    mb = size_bytes / (1024 * 1024)
    return '{:.0f} MB'.format(mb)


# =========================================================================
# STREMIO ADDON SCRAPER (shared logic for Torrentio, MediaFusion, etc.)
# =========================================================================

def _scrape_stremio(base_url, provider_name, imdb_id, season=None, episode=None):
    """Scrape a Stremio-compatible addon for torrent sources."""
    sources = []
    try:
        if season is not None and episode is not None:
            media_type = 'series'
            media_id = '{}:{}:{}'.format(imdb_id, season, episode)
        else:
            media_type = 'movie'
            media_id = imdb_id

        url = '{}/stream/{}/{}.json'.format(base_url, media_type, media_id)
        data = http_get(url, timeout=15)
        if not data:
            return sources

        for stream in data.get('streams', []):
            title = stream.get('title', '') or stream.get('name', '') or stream.get('description', '')
            info_hash = stream.get('infoHash', '')
            file_idx = stream.get('fileIdx')
            # Prefer behaviorHints.filename for actual release name (MediaFusion uses this)
            hints = stream.get('behaviorHints', {})
            release_name = hints.get('filename', '')

            # Clean Unicode emoji/symbols from title lines
            clean_title = ''.join(c for c in title if ord(c) < 0x2600 or c in ' .')
            clean_title = re.sub(r'\s+', ' ', clean_title).strip()

            if not release_name:
                lines = clean_title.split('\n')
                release_name = lines[0] if lines else clean_title

            size_info = ''
            # Check behaviorHints.videoSize first (bytes)
            if hints.get('videoSize'):
                try:
                    gb = hints['videoSize'] / (1024 ** 3)
                    size_info = '{:.1f} GB'.format(gb) if gb >= 1 else '{:.0f} MB'.format(gb * 1024)
                except Exception:
                    pass
            if not size_info:
                for line in clean_title.split('\n'):
                    if 'gb' in line.lower() or 'mb' in line.lower():
                        size_info = re.sub(r'\s+', ' ', line).strip()
                        break

            # Use direct URL if available (MediaFusion provides playback URLs)
            stream_url = stream.get('url', '')
            source_type = 'torrent' if info_hash else ('direct' if stream_url else 'torrent')

            sources.append({
                'name': release_name,
                'quality': _detect_quality(release_name),
                'info': _detect_info(release_name),
                'size': size_info,
                'hash': info_hash,
                'url': stream_url,
                'file_idx': file_idx,
                'provider': provider_name,
                'type': source_type,
            })
    except Exception as e:
        log('{} scrape error: {}'.format(provider_name, e), 'ERROR')

    return sources


def scrape_torrentio(imdb_id, season=None, episode=None):
    return _scrape_stremio('https://torrentio.strem.fun/realdebrid=', 'torrentio', imdb_id, season, episode)


def _get_mediafusion_url():
    """Get or auto-generate MediaFusion config URL using existing RD token.
    Regenerates when the RD token changes (e.g. after refresh)."""
    from resources.lib.modules.utils import get_setting, set_setting, http_post, log
    rd_token = get_setting('rd_token') or ''
    if not rd_token:
        return ''
    # Check if cached URL was generated with current token
    cached = get_setting('mediafusion_url') or ''
    cached_token = get_setting('mediafusion_rd_token') or ''
    if cached and cached_token == rd_token:
        return cached
    # Token changed or no cached URL — regenerate
    if cached and cached_token != rd_token:
        log('MediaFusion: RD token changed, regenerating config URL')
    try:
        payload = {
            'sps': [{'sv': 'realdebrid', 'tk': rd_token}],
            'ap': 'changemeelfie'
        }
        resp = http_post('https://mediafusion.elfhosted.com/encrypt-user-data',
                         payload, timeout=10)
        if resp and resp.get('encrypted_str'):
            url = 'https://mediafusion.elfhosted.com/{}'.format(resp['encrypted_str'])
            set_setting('mediafusion_url', url)
            set_setting('mediafusion_rd_token', rd_token)
            log('MediaFusion: auto-configured from RD token')
            return url
    except Exception as e:
        log('MediaFusion auto-config failed: {}'.format(e), 'ERROR')
    return ''


def scrape_mediafusion(imdb_id, season=None, episode=None):
    url = _get_mediafusion_url()
    if not url:
        return []
    return _scrape_stremio(url, 'mediafusion', imdb_id, season, episode)


# =========================================================================
# EXTERNAL SCRAPERS SUPPORT (CocoScrapers / custom modules)
# =========================================================================

def scrape_external(imdb_id, tmdb_id=None, title='', year='', season=None, episode=None):
    """
    Try to import and use external scraper packages.
    Supports CocoScrapers-style modules.
    """
    sources = []

    # Try CocoScrapers
    try:
        from cocoscrapers import sources as coco
        log('CocoScrapers found, scraping...')
        # CocoScrapers API varies - this is a general pattern
        if hasattr(coco, 'sources'):
            scrapers = coco.sources()
            for scraper in scrapers:
                try:
                    if season is not None:
                        results = scraper.episode(title, year, imdb_id, season, episode)
                    else:
                        results = scraper.movie(title, year, imdb_id)
                    if results:
                        for r in results:
                            sources.append({
                                'name': r.get('release_title', r.get('url', '')),
                                'quality': r.get('quality', _detect_quality(r.get('release_title', ''))),
                                'info': [],
                                'url': r.get('url', ''),
                                'provider': 'coco:{}'.format(r.get('source', 'unknown')),
                                'type': 'hoster' if 'magnet' not in r.get('url', '') else 'torrent',
                            })
                except Exception:
                    pass
    except ImportError:
        log('CocoScrapers not installed, skipping external scrapers')

    return sources


# =========================================================================
# MASTER SCRAPER - Combines all sources
# =========================================================================

def scrape_all(imdb_id, tmdb_id=None, title='', year='', season=None, episode=None,
               use_torrentio=True, use_mediafusion=True, use_external=True,
               progress_callback=None):
    """
    Master scraping function. Runs all enabled scrapers in parallel and combines results.

    Args:
        progress_callback: Optional callable(percent, message) for UI updates

    Returns:
        List of source dicts, sorted by quality then provider
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    all_sources = []

    def update(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    # Build list of scrapers to run
    tasks = []
    if use_torrentio:
        tasks.append(('Torrentio', scrape_torrentio, (imdb_id, season, episode)))
    if use_mediafusion:
        tasks.append(('MediaFusion', scrape_mediafusion, (imdb_id, season, episode)))
    if use_external:
        tasks.append(('External', scrape_external, (imdb_id, tmdb_id, title, year, season, episode)))

    if not tasks:
        update(70, 'No scrapers enabled')
        return []

    update(10, 'Scanning {} sources...'.format(len(tasks)))

    # Run all scrapers in parallel
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        futures = {}
        for name, func, args in tasks:
            futures[pool.submit(func, *args)] = name

        for future in as_completed(futures):
            name = futures[future]
            try:
                sources = future.result()
                log('{}: {} sources'.format(name, len(sources)))
                all_sources.extend(sources)
            except Exception as e:
                log('{} scraper failed: {}'.format(name, e), 'ERROR')

    update(50, 'Processing {} sources...'.format(len(all_sources)))

    # Deduplicate by hash
    seen_hashes = set()
    unique = []
    for src in all_sources:
        h = src.get('hash', '')
        if h and h.lower() in seen_hashes:
            continue
        if h:
            seen_hashes.add(h.lower())
        unique.append(src)

    # Sort: 4K > 1080p > 720p > SD, then by provider
    def sort_key(s):
        q = s.get('quality', 'SD').lower()
        return (QUALITY_ORDER.get(q, 99), s.get('name', ''))

    unique.sort(key=sort_key)

    update(70, 'Found {} sources'.format(len(unique)))
    log('Total unique sources: {}'.format(len(unique)))
    return unique
