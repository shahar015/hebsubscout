# -*- coding: utf-8 -*-
"""
Hebrew Subtitle Providers
=========================

API integrations for the major Hebrew subtitle sources:
- Wizdom.xyz  (free, no auth needed for searching)
- Ktuvit.me   (aka ScrewZira - needs auth for downloads, search is limited)
- OpenSubtitles.com (universal, needs API key for full access)

Each provider implements a common interface:
    provider.search(imdb_id, season=None, episode=None) -> list of subtitle dicts

Each subtitle dict contains:
    - 'name': release/version name (e.g. "Movie.2024.1080p.BluRay.x264-GROUP")
    - 'provider': provider name string
    - 'id': subtitle identifier (for downloading later)
    - 'language': "he" for Hebrew
"""

import json
import re
import time
import hashlib

try:
    # Kodi environment
    import xbmc
    import xbmcaddon
    import xbmcvfs
    def log(msg, level='INFO'):
        xbmc.log('[HebSubScout] {}: {}'.format(level, msg), xbmc.LOGINFO)
except ImportError:
    # Standalone / testing
    def log(msg, level='INFO'):
        print('[HebSubScout] {}: {}'.format(level, msg))

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode, quote
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode, quote


# =============================================================================
# Cache layer - avoid hammering APIs on repeated checks
# =============================================================================

class SimpleCache:
    """
    In-memory + optional file cache for API responses.
    TTL-based expiration to avoid stale data.
    """
    
    def __init__(self, ttl_seconds=3600, persist_path=None):
        self._cache = {}
        self._ttl = ttl_seconds
        self._persist_path = persist_path
        self._load()
    
    def _load(self):
        if not self._persist_path:
            return
        try:
            import os
            if os.path.exists(self._persist_path):
                with open(self._persist_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Prune expired entries
                now = time.time()
                self._cache = {
                    k: v for k, v in data.items()
                    if v.get('expires', 0) > now
                }
        except Exception:
            self._cache = {}
    
    def _save(self):
        if not self._persist_path:
            return
        try:
            import os
            os.makedirs(os.path.dirname(self._persist_path), exist_ok=True)
            with open(self._persist_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False)
        except Exception:
            pass
    
    def get(self, key):
        entry = self._cache.get(key)
        if entry and entry.get('expires', 0) > time.time():
            return entry.get('data')
        return None
    
    def set(self, key, data):
        self._cache[key] = {
            'data': data,
            'expires': time.time() + self._ttl
        }
        self._save()


# Global cache instance (shared across providers within a session)
_cache = SimpleCache(ttl_seconds=1800)  # 30 min cache


def _make_cache_key(provider, imdb_id, season, episode):
    return '{}:{}:{}:{}'.format(provider, imdb_id, season or '', episode or '')


# =============================================================================
# HTTP helpers
# =============================================================================

def _http_get(url, headers=None, timeout=10):
    """Simple HTTP GET that works in both Kodi and standalone Python."""
    try:
        req = Request(url)
        req.add_header('User-Agent', 'HebSubScout/1.0 Kodi')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        response = urlopen(req, timeout=timeout)
        return response.read().decode('utf-8')
    except HTTPError as e:
        log('HTTP GET error {}: {}'.format(e.code, url), 'ERROR')
        return None
    except (URLError, Exception) as e:
        log('HTTP GET failed: {} - {}'.format(url, str(e)), 'ERROR')
        return None


def _http_post(url, data, headers=None, timeout=10):
    """Simple HTTP POST with JSON body."""
    try:
        body = json.dumps(data).encode('utf-8')
        req = Request(url, data=body)
        req.add_header('User-Agent', 'HebSubScout/1.0 Kodi')
        req.add_header('Content-Type', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        response = urlopen(req, timeout=timeout)
        return response.read().decode('utf-8')
    except HTTPError as e:
        log('HTTP POST error {}: {}'.format(e.code, url), 'ERROR')
        return None
    except (URLError, Exception) as e:
        log('HTTP POST failed: {} - {}'.format(url, str(e)), 'ERROR')
        return None


# =============================================================================
# Provider: Wizdom.xyz
# =============================================================================

class WizdomProvider:
    """
    Wizdom.xyz Hebrew subtitles provider.
    
    API endpoints:
    - Search by IMDB: https://wizdom.xyz/api/search.id.php?imdb=ttXXXXXXX&season=S&episode=E&version=filename
    - Releases:       https://wizdom.xyz/api/releases/ttXXXXXXX
    
    No authentication required for searching.
    Returns list of subtitles with release names.
    """
    
    NAME = 'wizdom'
    BASE_URL = 'https://wizdom.xyz/api'
    
    def search(self, imdb_id, season=None, episode=None, filename=None):
        """
        Search Wizdom for Hebrew subtitles.
        
        Args:
            imdb_id: IMDB ID (e.g. "tt1234567")
            season: Season number (int) for TV shows, None for movies
            episode: Episode number (int) for TV shows, None for movies
            filename: Optional source filename for better matching
        
        Returns:
            List of subtitle dicts: [{'name': str, 'provider': 'wizdom', 'id': str}]
        """
        cache_key = _make_cache_key(self.NAME, imdb_id, season, episode)
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached
        
        results = []
        
        # Try the search.id.php endpoint first (returns version-matched results)
        params = {'imdb': imdb_id}
        if season is not None:
            params['season'] = int(season)
        if episode is not None:
            params['episode'] = int(episode)
        if filename:
            params['version'] = filename
        
        url = '{}/search.id.php?{}'.format(self.BASE_URL, urlencode(params))
        log('Wizdom search: {}'.format(url))
        
        response = _http_get(url)
        if response:
            try:
                data = json.loads(response)
                if isinstance(data, list):
                    for item in data:
                        sub_name = item.get('versioname', '') or item.get('version', '') or item.get('title', '')
                        sub_id = str(item.get('id', ''))
                        if sub_name:
                            results.append({
                                'name': sub_name,
                                'provider': self.NAME,
                                'id': sub_id,
                                'language': 'he'
                            })
            except (json.JSONDecodeError, ValueError):
                pass
        
        # Also try the releases endpoint for more comprehensive results
        if not results:
            releases_url = '{}/releases/{}'.format(self.BASE_URL, imdb_id)
            log('Wizdom releases: {}'.format(releases_url))
            
            response = _http_get(releases_url)
            if response:
                try:
                    data = json.loads(response)
                    subs_list = data if isinstance(data, list) else data.get('subs', [])
                    for item in subs_list:
                        sub_name = item.get('versioname', '') or item.get('version', '') or item.get('title', '')
                        sub_id = str(item.get('id', ''))
                        if sub_name:
                            results.append({
                                'name': sub_name,
                                'provider': self.NAME,
                                'id': sub_id,
                                'language': 'he'
                            })
                except (json.JSONDecodeError, ValueError):
                    pass
        
        _cache.set(cache_key, results)
        log('Wizdom found {} subtitles for {}'.format(len(results), imdb_id))
        return results


# =============================================================================
# Provider: Ktuvit.me (ScrewZira)
# =============================================================================

class KtuvitProvider:
    """
    Ktuvit.me (formerly ScrewZira) Hebrew subtitles provider.
    
    API endpoints:
    - FindFilm:   POST http://api.screwzira.com/FindFilm
    - FindSeries: POST http://api.screwzira.com/FindSeries
    
    Request format:
        {"request": {"SearchPhrase": "ttXXXXXXX", "SearchType": "ImdbID", "Version": "1.0"}}
    
    Response format:
        {"d": '{"Results":[{"SubtitleName":"release.name","Identifier":"hash"}],"IsSuccess":true}'}
    
    Note: The old ScrewZira API is more accessible. Ktuvit.me itself requires login
    for some operations. We try both endpoints.
    """
    
    NAME = 'ktuvit'
    SCREWZIRA_API = 'http://api.screwzira.com'
    KTUVIT_SEARCH = 'https://www.ktuvit.me'  # Fallback
    
    def search(self, imdb_id, season=None, episode=None, filename=None):
        """
        Search Ktuvit/ScrewZira for Hebrew subtitles.
        """
        cache_key = _make_cache_key(self.NAME, imdb_id, season, episode)
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached
        
        results = []
        
        # Determine if movie or series
        if season is not None and episode is not None:
            results = self._search_series(imdb_id, season, episode, filename)
        else:
            results = self._search_film(imdb_id, filename)
        
        _cache.set(cache_key, results)
        log('Ktuvit found {} subtitles for {}'.format(len(results), imdb_id))
        return results
    
    def _search_film(self, imdb_id, filename=None):
        """Search for movie subtitles via ScrewZira API."""
        results = []
        
        # Search by IMDB ID
        payload = {
            "request": {
                "SearchPhrase": imdb_id,
                "SearchType": "ImdbID",
                "Version": "1.0"
            }
        }
        
        url = '{}/FindFilm'.format(self.SCREWZIRA_API)
        log('Ktuvit FindFilm: {}'.format(imdb_id))
        
        response = _http_post(url, payload)
        results.extend(self._parse_response(response))
        
        # Also search by filename if provided (can find additional matches)
        if filename:
            payload_sub = {
                "request": {
                    "SearchPhrase": filename,
                    "SearchType": "Subtitle",
                    "Version": "1.0"
                }
            }
            response2 = _http_post(url, payload_sub)
            existing_ids = {r['id'] for r in results}
            for sub in self._parse_response(response2):
                if sub['id'] not in existing_ids:
                    results.append(sub)
        
        return results
    
    def _search_series(self, imdb_id, season, episode, filename=None):
        """Search for TV series subtitles via ScrewZira API."""
        results = []
        
        # Try IMDB ID search first
        payload = {
            "request": {
                "SearchPhrase": imdb_id,
                "SearchType": "ImdbID",
                "Version": "1.0"
            }
        }
        
        url = '{}/FindSeries'.format(self.SCREWZIRA_API)
        log('Ktuvit FindSeries: {} S{}E{}'.format(imdb_id, season, episode))
        
        response = _http_post(url, payload)
        results.extend(self._parse_response(response))
        
        # Search by formatted episode string
        if filename:
            se_string = filename
        else:
            se_string = 'S{:02d}E{:02d}'.format(int(season), int(episode))
        
        payload_sub = {
            "request": {
                "SearchPhrase": se_string,
                "SearchType": "Subtitle",
                "Version": "1.0"
            }
        }
        response2 = _http_post(url, payload_sub)
        existing_ids = {r['id'] for r in results}
        for sub in self._parse_response(response2):
            if sub['id'] not in existing_ids:
                results.append(sub)
        
        return results
    
    def _parse_response(self, response_text):
        """Parse ScrewZira API response into subtitle list."""
        results = []
        if not response_text:
            return results
        
        try:
            outer = json.loads(response_text)
            # Response is wrapped: {"d": "{\"Results\":[...]}"}
            inner_str = outer.get('d', '{}')
            if isinstance(inner_str, str):
                inner = json.loads(inner_str)
            else:
                inner = inner_str
            
            if inner.get('IsSuccess'):
                for item in inner.get('Results', []):
                    sub_name = item.get('SubtitleName', '')
                    sub_id = item.get('Identifier', '')
                    if sub_name:
                        results.append({
                            'name': sub_name,
                            'provider': self.NAME,
                            'id': sub_id,
                            'language': 'he'
                        })
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            log('Ktuvit parse error: {}'.format(str(e)), 'ERROR')
        
        return results


# =============================================================================
# Provider: OpenSubtitles
# =============================================================================

class OpenSubtitlesProvider:
    """
    OpenSubtitles.com Hebrew subtitles provider.
    
    Uses the REST API v1 (requires API key for full access).
    Falls back to basic search if no API key is configured.
    
    API: https://api.opensubtitles.com/api/v1/subtitles
    """
    
    NAME = 'opensubtitles'
    API_URL = 'https://api.opensubtitles.com/api/v1'
    
    def __init__(self, api_key=None):
        self.api_key = api_key
    
    def search(self, imdb_id, season=None, episode=None, filename=None):
        """
        Search OpenSubtitles for Hebrew subtitles.
        """
        if not self.api_key:
            log('OpenSubtitles: No API key configured, skipping', 'WARNING')
            return []
        
        cache_key = _make_cache_key(self.NAME, imdb_id, season, episode)
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached
        
        results = []
        
        # Build search params
        params = {
            'imdb_id': imdb_id.replace('tt', ''),
            'languages': 'he',
        }
        if season is not None:
            params['season_number'] = int(season)
        if episode is not None:
            params['episode_number'] = int(episode)
        
        url = '{}/subtitles?{}'.format(self.API_URL, urlencode(params))
        headers = {
            'Api-Key': self.api_key,
            'Accept': 'application/json'
        }
        
        log('OpenSubtitles search: {}'.format(imdb_id))
        response = _http_get(url, headers=headers)
        
        if response:
            try:
                data = json.loads(response)
                for item in data.get('data', []):
                    attrs = item.get('attributes', {})
                    release = attrs.get('release', '') or attrs.get('feature_details', {}).get('title', '')
                    files = attrs.get('files', [])
                    sub_id = str(files[0].get('file_id', '')) if files else str(item.get('id', ''))
                    
                    if release:
                        results.append({
                            'name': release,
                            'provider': self.NAME,
                            'id': sub_id,
                            'language': 'he'
                        })
            except (json.JSONDecodeError, ValueError, KeyError) as e:
                log('OpenSubtitles parse error: {}'.format(str(e)), 'ERROR')
        
        _cache.set(cache_key, results)
        log('OpenSubtitles found {} Hebrew subtitles for {}'.format(len(results), imdb_id))
        return results
