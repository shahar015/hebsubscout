# -*- coding: utf-8 -*-
"""
Sources Module
==============
Orchestrates the full source pipeline:
1. Scrape sources from all providers
2. Check Real Debrid cache availability
3. Enrich with HebSubScout subtitle matching
4. Present to user or auto-play
"""

import threading
from resources.lib.modules.utils import log, get_setting, notification, t
from resources.lib.modules import realdebrid as rd
from resources.lib.scrapers import scrape_all

# Import HebSubScout - THE KEY INTEGRATION
try:
    from hebsubscout import SubScout
    HEBSUBSCOUT_AVAILABLE = True
    log('HebSubScout module loaded successfully')
except ImportError:
    HEBSUBSCOUT_AVAILABLE = False
    log('HebSubScout module not found - subtitle indicators disabled', 'WARNING')


def get_sources(imdb_id, tmdb_id=None, title='', year='',
                season=None, episode=None, progress_callback=None):
    """
    Full source pipeline:
    1. Scrape all providers
    2. Check RD cache
    3. Enrich with Hebrew subtitle data
    
    Returns list of fully enriched source dicts.
    """
    def update(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    # --- Step 1: Scrape ---
    update(5, t('scraping_sources'))
    
    sources = scrape_all(
        imdb_id=imdb_id,
        tmdb_id=tmdb_id,
        title=title,
        year=year,
        season=season,
        episode=episode,
        use_torrentio=get_setting('enable_torrentio') != 'false',
        use_mediafusion=get_setting('enable_mediafusion') != 'false',
        use_external=get_setting('enable_external_scrapers') != 'false',
        progress_callback=lambda p, m: update(5 + int(p * 0.35), m)
    )

    if not sources:
        update(100, t('no_sources'))
        return []

    # --- Step 2: RD cache check ---
    # DISABLED: RD removed instantAvailability in Nov 2024.
    # The addMagnet workaround (3 API calls per source) is too slow.
    # Cached sources play instantly anyway when the user clicks them.
    # TODO: Re-enable if RD adds a fast cache check endpoint.
    
    update(65, t('found_sources', len(sources)))

    # --- Step 3: HebSubScout enrichment ---
    if HEBSUBSCOUT_AVAILABLE and get_setting('enable_hebsubscout') != 'false':
        update(70, t('checking_subs'))
        
        try:
            scout = SubScout(settings={
                'min_match_score': int(get_setting('min_match_score') or 40),
                'providers': ['wizdom', 'ktuvit'],
                'learning_db': True,
                'ktuvit_email': get_setting('ktuvit_email'),
                'ktuvit_password': get_setting('ktuvit_password'),
            })
            sources = scout.check_sources(imdb_id, sources, season=season, episode=episode)
            
            subs_count = sum(1 for s in sources if s.get('has_hebrew_subs'))
            log('HebSubScout: {}/{} sources have Hebrew sub matches'.format(subs_count, len(sources)))
        except Exception as e:
            log('HebSubScout enrichment failed: {}'.format(e), 'ERROR')
    
    update(95, t('ready_sources', len(sources)))
    return sources


def build_source_label(source):
    """
    Build a display label for a source, including all indicators.
    
    Example output:
    "[COLOR lime]עב 92%[/COLOR] [COLOR cyan]RD[/COLOR] | 1080p HEVC | Movie.2024.1080p.BluRay.x265-GROUP | 4.2 GB"
    """
    parts = []
    
    # Hebrew subtitle indicator (HebSubScout)
    if source.get('has_hebrew_subs'):
        pct = source.get('best_match_pct', 0)
        if pct >= 90:
            parts.append('[COLOR lime]עב {}%[/COLOR]'.format(pct))
        elif pct >= 70:
            parts.append('[COLOR yellow]עב {}%[/COLOR]'.format(pct))
        else:
            parts.append('[COLOR orange]עב {}%[/COLOR]'.format(pct))
    elif HEBSUBSCOUT_AVAILABLE and source.get('has_hebrew_subs') is not None:
        parts.append('[COLOR red]עב X[/COLOR]')
    
    # RD cached indicator
    if source.get('rd_cached'):
        parts.append('[COLOR cyan]RD[/COLOR]')
    
    # Quality + info
    quality = source.get('quality', '')
    info_tags = source.get('info', [])
    quality_str = quality
    if info_tags:
        quality_str += ' ' + ' '.join(info_tags)
    if quality_str:
        parts.append(quality_str)
    
    # Release name
    parts.append(source.get('name', 'Unknown'))
    
    # Size
    size = source.get('size', '')
    if size:
        parts.append(size)
    
    return ' | '.join(parts)


def resolve_source(source):
    """
    Resolve a source to a playable URL.
    
    Handles:
    - RD cached torrents (instant)
    - RD magnet resolution (may take time)
    - Direct hoster links through RD unrestrict
    
    Returns playable URL string or None.
    """
    if not rd.is_authorized():
        notification(t('rd_not_authorized'))
        return None
    
    rd.refresh_token()
    
    source_type = source.get('type', '')
    
    if source_type == 'torrent':
        info_hash = source.get('hash', '')
        if not info_hash:
            return None
        
        # If cached, we can resolve instantly
        if source.get('rd_cached'):
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)
            url = rd.resolve_magnet(magnet)
            return url
        else:
            # Not cached - add and wait
            magnet = 'magnet:?xt=urn:btih:{}'.format(info_hash)
            url = rd.resolve_magnet(magnet)
            return url
    
    elif source_type == 'hoster':
        url = source.get('url', '')
        if url:
            return rd.unrestrict_link(url)
    
    return None
