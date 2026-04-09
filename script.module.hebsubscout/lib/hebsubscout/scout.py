# -*- coding: utf-8 -*-
"""
SubScout - Main API Class
==========================

This is the main entry point for addon developers.
Import this and call check_sources() to enrich your source list
with Hebrew subtitle availability data.

INTEGRATION EXAMPLE (5 lines in your addon):
=============================================

    from hebsubscout import SubScout
    
    scout = SubScout()
    
    # In your source scraping function, after you have sources:
    enriched = scout.check_sources(
        imdb_id='tt1234567',
        sources=[{'name': 'Movie.2024.1080p.BluRay.x264-GROUP', ...}, ...],
        season=None,    # Set for TV shows
        episode=None    # Set for TV shows
    )
    
    # Each source now has: has_hebrew_subs, best_match_pct, best_match_source, etc.
    for src in enriched:
        label = src['name']
        if src['has_hebrew_subs']:
            label += ' [COLOR lime]עב {}%[/COLOR]'.format(src['best_match_pct'])
        # ... render in your list
"""

import os
import time

from hebsubscout.matcher import ReleaseMatcher
from hebsubscout.providers import WizdomProvider, KtuvitProvider, OpenSubtitlesProvider, log


class SubScout:
    """
    Hebrew Subtitle Scout.
    
    The main class that video addon developers interact with.
    Searches multiple Hebrew subtitle providers in parallel,
    then fuzzy-matches results against your scraped video sources.
    """
    
    def __init__(self, settings=None):
        """
        Initialize SubScout.
        
        Args:
            settings: Optional dict to configure behavior:
                - 'min_match_score': int (default 40) - minimum match % to show
                - 'providers': list of str - which providers to use
                    (default: ['wizdom', 'ktuvit', 'opensubtitles'])
                - 'opensubtitles_api_key': str - API key for OpenSubtitles
                - 'cache_dir': str - directory for persistent caches
                - 'learning_db': bool (default True) - enable learning database
                - 'timeout': int (default 8) - max seconds to wait for providers
        """
        self.settings = settings or {}
        
        # Config
        self.min_score = self.settings.get('min_match_score', 40)
        self.enabled_providers = self.settings.get(
            'providers', ['wizdom', 'ktuvit']
        )
        self.timeout = self.settings.get('timeout', 8)
        
        # Set up cache/learning directory
        cache_dir = self.settings.get('cache_dir', '')
        if not cache_dir:
            try:
                import xbmcaddon
                import xbmcvfs
                addon = xbmcaddon.Addon('script.module.hebsubscout')
                profile = xbmcvfs.translatePath(addon.getAddonInfo('profile'))
                cache_dir = os.path.join(profile, 'cache')
            except Exception:
                cache_dir = os.path.join(os.path.expanduser('~'), '.hebsubscout')
        
        # Initialize matcher
        learning_path = None
        if self.settings.get('learning_db', True):
            learning_path = os.path.join(cache_dir, 'learning_db.json')
        
        self.matcher = ReleaseMatcher(
            min_score=self.min_score,
            learning_db_path=learning_path
        )
        
        # Initialize providers
        self.providers = {}
        if 'wizdom' in self.enabled_providers:
            self.providers['wizdom'] = WizdomProvider()
        if 'ktuvit' in self.enabled_providers:
            ktuvit_email = self.settings.get('ktuvit_email', '')
            ktuvit_password = self.settings.get('ktuvit_password', '')
            self.providers['ktuvit'] = KtuvitProvider(email=ktuvit_email, hashed_password=ktuvit_password)
        if 'opensubtitles' in self.enabled_providers:
            api_key = self.settings.get('opensubtitles_api_key', '')
            if api_key:
                self.providers['opensubtitles'] = OpenSubtitlesProvider(api_key=api_key)
    
    def fetch_subtitles(self, imdb_id, season=None, episode=None):
        """
        Fetch all available Hebrew subtitles from enabled providers in parallel.

        Args:
            imdb_id: IMDB ID string (e.g. "tt1234567")
            season: int or None for movies
            episode: int or None for movies

        Returns:
            List of subtitle dicts from all providers combined.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        if not self.providers:
            return []

        def _query(name, provider):
            start = time.time()
            subs = provider.search(imdb_id, season=season, episode=episode)
            elapsed = time.time() - start
            log('{} returned {} results in {:.1f}s'.format(name, len(subs), elapsed))
            return subs

        all_subs = []
        with ThreadPoolExecutor(max_workers=len(self.providers)) as pool:
            futures = {pool.submit(_query, n, p): n for n, p in self.providers.items()}
            for future in as_completed(futures):
                name = futures[future]
                try:
                    all_subs.extend(future.result())
                except Exception as e:
                    log('Provider {} failed: {}'.format(name, str(e)), 'ERROR')

        return all_subs
    
    def check_sources(self, imdb_id, sources, season=None, episode=None):
        """
        THE MAIN METHOD - Enrich a list of video sources with subtitle data.
        
        This is what addon developers call after scraping sources.
        
        Args:
            imdb_id: IMDB ID string (e.g. "tt1234567")
            sources: List of source dicts. Each MUST have a 'name' key
                     containing the release/file name. All other keys are
                     preserved and passed through.
            season: Season number (int) for TV shows, None for movies
            episode: Episode number (int) for TV shows, None for movies
        
        Returns:
            Same list of sources, each enriched with:
                - has_hebrew_subs (bool): True if matching Hebrew subs found
                - best_match_pct (int): 0-100 confidence of best match
                - best_match_source (str): Provider name of best match
                - best_match_name (str): Subtitle release name of best match
                - all_matches (list): All matching subtitles sorted by score
        
        Example:
            >>> scout = SubScout()
            >>> sources = [
            ...     {'name': 'Movie.2024.1080p.BluRay.x264-SPARKS', 'url': '...'},
            ...     {'name': 'Movie.2024.720p.WEBRip.x264-YTS', 'url': '...'},
            ... ]
            >>> enriched = scout.check_sources('tt1234567', sources)
            >>> enriched[0]['has_hebrew_subs']
            True
            >>> enriched[0]['best_match_pct']
            92
        """
        if not imdb_id or not sources:
            return sources
        
        log('Checking {} sources for IMDB {}'.format(len(sources), imdb_id))
        
        # Fetch all available subtitles
        available_subs = self.fetch_subtitles(imdb_id, season=season, episode=episode)
        
        if not available_subs:
            log('No Hebrew subtitles found for {}'.format(imdb_id))
            # Return sources with empty sub info
            return self.matcher.match_sources_batch(sources, [])
        
        log('Found {} total Hebrew subtitles, matching against {} sources'.format(
            len(available_subs), len(sources)
        ))
        
        # Match sources against subtitles
        enriched = self.matcher.match_sources_batch(sources, available_subs)
        
        # Log summary
        matched = sum(1 for s in enriched if s.get('has_hebrew_subs'))
        log('{}/{} sources have Hebrew subtitle matches'.format(matched, len(enriched)))
        
        return enriched
    
    def has_hebrew_subs(self, imdb_id, season=None, episode=None):
        """
        Quick check: does this title have ANY Hebrew subtitles available?
        
        Useful for context menu addons or pre-filtering.
        Faster than check_sources because it doesn't do matching.
        
        Returns:
            bool: True if Hebrew subtitles exist for this title
        """
        subs = self.fetch_subtitles(imdb_id, season=season, episode=episode)
        return len(subs) > 0
    
    def record_match(self, source_name, subtitle_name, provider):
        """
        Record a successful subtitle match (learning database).
        
        Call this after the user picks a subtitle that works well.
        Future matches for similar source names will prefer this subtitle.
        """
        self.matcher.record_successful_match(source_name, subtitle_name, provider)
    
    def format_label(self, source, style='color'):
        """
        Helper: Format a source label with subtitle indicator.
        
        Args:
            source: An enriched source dict (from check_sources)
            style: 'color' for Kodi [COLOR] tags, 'emoji' for unicode,
                   'text' for plain text
        
        Returns:
            str: Formatted label suffix to append to your source label
        """
        if not source.get('has_hebrew_subs'):
            if style == 'color':
                return ' [COLOR red]עב ✗[/COLOR]'
            elif style == 'emoji':
                return ' 🔴 עב ✗'
            else:
                return ' [No HEB subs]'
        
        pct = source.get('best_match_pct', 0)
        provider = source.get('best_match_source', '')
        
        if pct >= 90:
            color = 'lime'
        elif pct >= 70:
            color = 'yellow'
        else:
            color = 'orange'
        
        if style == 'color':
            return ' [COLOR {}]עב {}%[/COLOR]'.format(color, pct)
        elif style == 'emoji':
            indicator = '🟢' if pct >= 90 else '🟡' if pct >= 70 else '🟠'
            return ' {} עב {}%'.format(indicator, pct)
        else:
            return ' [HEB {}% via {}]'.format(pct, provider)
