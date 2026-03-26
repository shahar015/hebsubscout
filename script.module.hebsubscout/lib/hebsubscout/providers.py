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

from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote
from urllib.error import HTTPError, URLError


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
    - Search: https://wizdom.xyz/api/search?action=by_id&imdb=ttXXX&season=S&episode=E
    - Releases: https://wizdom.xyz/api/releases/ttXXX (nested for TV: subs[season][episode])
    - Download: https://wizdom.xyz/api/files/{id}

    No authentication required.
    """

    NAME = 'wizdom'
    BASE_URL = 'https://wizdom.xyz/api'

    def search(self, imdb_id, season=None, episode=None, filename=None):
        cache_key = _make_cache_key(self.NAME, imdb_id, season, episode)
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        results = []

        # Primary endpoint: search?action=by_id
        params = {'action': 'by_id', 'imdb': imdb_id}
        if season is not None:
            params['season'] = int(season)
        if episode is not None:
            params['episode'] = int(episode)
        if filename:
            params['version'] = filename

        url = '{}/search?{}'.format(self.BASE_URL, urlencode(params))
        log('Wizdom search: {}'.format(url))

        response = _http_get(url)
        if response:
            try:
                data = json.loads(response)
                if isinstance(data, list):
                    for item in data:
                        sub_name = item.get('versioname', '') or item.get('version', '') or ''
                        sub_id = str(item.get('id', ''))
                        if sub_name and sub_id:
                            results.append({
                                'name': sub_name,
                                'provider': self.NAME,
                                'id': sub_id,
                                'language': 'he'
                            })
            except (json.JSONDecodeError, ValueError) as e:
                log('Wizdom search parse error: {}'.format(e), 'ERROR')

        # Fallback: releases endpoint
        if not results:
            releases_url = '{}/releases/{}'.format(self.BASE_URL, imdb_id)
            log('Wizdom releases fallback: {}'.format(releases_url))

            response = _http_get(releases_url)
            if response:
                try:
                    data = json.loads(response)
                    subs_data = data.get('subs', data)

                    # TV shows: subs is nested {season: {episode: [list]}}
                    if isinstance(subs_data, dict) and season is not None:
                        season_data = subs_data.get(str(int(season)), {})
                        if isinstance(season_data, dict) and episode is not None:
                            ep_list = season_data.get(str(int(episode)), [])
                        elif isinstance(season_data, list):
                            ep_list = season_data
                        else:
                            ep_list = []
                        subs_list = ep_list if isinstance(ep_list, list) else []
                    elif isinstance(subs_data, list):
                        # Movies: subs is a flat array
                        subs_list = subs_data
                    else:
                        subs_list = []

                    for item in subs_list:
                        if not isinstance(item, dict):
                            continue
                        sub_name = item.get('version', '') or item.get('versioname', '') or ''
                        sub_id = str(item.get('id', ''))
                        if sub_name and sub_id:
                            results.append({
                                'name': sub_name,
                                'provider': self.NAME,
                                'id': sub_id,
                                'language': 'he'
                            })
                except (json.JSONDecodeError, ValueError) as e:
                    log('Wizdom releases parse error: {}'.format(e), 'ERROR')

        _cache.set(cache_key, results)
        log('Wizdom found {} subtitles for {}'.format(len(results), imdb_id))
        return results


# =============================================================================
# Provider: Ktuvit.me (ScrewZira)
# =============================================================================

class KtuvitProvider:
    """
    Ktuvit.me Hebrew subtitles provider.

    The old api.screwzira.com is behind a bot protection wall and no longer works.
    This provider uses the ktuvit.me website directly with cookie-based login.

    Requires Ktuvit email + hashed password in settings.
    If not configured, this provider silently returns empty results.

    Flow: Login → Search for title ID → Fetch subtitle list from HTML → Return results
    """

    NAME = 'ktuvit'
    BASE_URL = 'https://www.ktuvit.me'
    _cookies = None
    _logged_in = False

    def __init__(self, email='', hashed_password=''):
        self._email = email
        self._hashed_password = hashed_password

    def search(self, imdb_id, season=None, episode=None, filename=None):
        cache_key = _make_cache_key(self.NAME, imdb_id, season, episode)
        cached = _cache.get(cache_key)
        if cached is not None:
            return cached

        if not self._email or not self._hashed_password:
            log('Ktuvit: No credentials configured, skipping')
            return []

        results = []
        try:
            if not self._logged_in:
                self._login()

            if not self._logged_in:
                log('Ktuvit: Login failed, skipping')
                return []

            # Search for the title to get Ktuvit ID
            is_tv = season is not None and episode is not None
            ktuvit_id = self._find_title(imdb_id, is_tv)
            if not ktuvit_id:
                log('Ktuvit: Title not found for {}'.format(imdb_id))
                _cache.set(cache_key, [])
                return []

            # Get subtitles
            if is_tv:
                results = self._get_episode_subs(ktuvit_id, season, episode)
            else:
                results = self._get_movie_subs(ktuvit_id)

        except Exception as e:
            log('Ktuvit error: {}'.format(e), 'ERROR')

        _cache.set(cache_key, results)
        log('Ktuvit found {} subtitles for {}'.format(len(results), imdb_id))
        return results

    def _login(self):
        """Login to ktuvit.me and store session cookies."""
        try:
            from http.cookiejar import CookieJar
            from urllib.request import build_opener, HTTPCookieProcessor

            self._cookie_jar = CookieJar()
            self._opener = build_opener(HTTPCookieProcessor(self._cookie_jar))

            login_url = '{}/Services/MembershipService.svc/Login'.format(self.BASE_URL)
            payload = json.dumps({
                'request': {'Email': self._email, 'Password': self._hashed_password}
            }).encode('utf-8')

            req = Request(login_url, data=payload)
            req.add_header('Content-Type', 'application/json')
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')

            resp = self._opener.open(req, timeout=10)
            result = json.loads(resp.read().decode('utf-8'))

            inner = json.loads(result.get('d', '{}'))
            if inner.get('IsSuccess'):
                self._logged_in = True
                log('Ktuvit: Login successful')
            else:
                log('Ktuvit: Login failed - {}'.format(inner.get('ErrorMessage', 'unknown')), 'ERROR')
        except Exception as e:
            log('Ktuvit login error: {}'.format(e), 'ERROR')

    def _ktuvit_request(self, url, data=None):
        """Make an authenticated request to ktuvit.me."""
        if not hasattr(self, '_opener'):
            return None
        try:
            if data is not None:
                body = json.dumps(data).encode('utf-8')
                req = Request(url, data=body)
                req.add_header('Content-Type', 'application/json')
            else:
                req = Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            resp = self._opener.open(req, timeout=15)
            return resp.read().decode('utf-8')
        except Exception as e:
            log('Ktuvit request failed: {} - {}'.format(url, e), 'ERROR')
            return None

    def _find_title(self, imdb_id, is_tv):
        """Search ktuvit.me for a title and return its Ktuvit ID."""
        url = '{}/Services/ContentProvider.svc/SearchPage_search'.format(self.BASE_URL)
        payload = {
            'request': {
                'FilmName': imdb_id,
                'Actors': [], 'Studios': None, 'Directors': [], 'Genres': [],
                'Countries': [], 'Languages': [], 'Year': '', 'Rating': [],
                'Page': 1,
                'SearchType': '1' if is_tv else '0',
                'WithSubsOnly': False
            }
        }
        response = self._ktuvit_request(url, payload)
        if not response:
            return None

        try:
            outer = json.loads(response)
            inner = json.loads(outer.get('d', '{}'))
            films = inner.get('Films', [])
            if films:
                return films[0].get('ID', '')
        except Exception as e:
            log('Ktuvit find_title error: {}'.format(e), 'ERROR')
        return None

    def _get_movie_subs(self, ktuvit_id):
        """Get subtitles for a movie from ktuvit.me HTML page."""
        url = '{}/MovieInfo.aspx?ID={}'.format(self.BASE_URL, ktuvit_id)
        html = self._ktuvit_request(url)
        if not html:
            return []
        return self._parse_subtitle_html(html, ktuvit_id)

    def _get_episode_subs(self, ktuvit_id, season, episode):
        """Get subtitles for a TV episode from ktuvit.me AJAX endpoint."""
        url = '{}/Services/GetModuleAjax.ashx?moduleName=SubtitlesList&SeriesID={}&Season={}&Episode={}'.format(
            self.BASE_URL, ktuvit_id, int(season), int(episode))
        html = self._ktuvit_request(url)
        if not html:
            return []
        return self._parse_subtitle_html(html, ktuvit_id)

    def _parse_subtitle_html(self, html, ktuvit_id):
        """Parse subtitle names and IDs from Ktuvit HTML using regex."""
        results = []
        # Match subtitle IDs: data-subtitle-id="..." or data-sub-id="..."
        id_pattern = re.compile(r'data-(?:subtitle|sub)-id="([^"]+)"')
        # Match release names in table rows
        row_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL)
        td_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL)
        tag_strip = re.compile(r'<[^>]+>')

        for row_match in row_pattern.finditer(html):
            row_html = row_match.group(1)
            sub_id_match = id_pattern.search(row_html)
            if not sub_id_match:
                continue

            sub_id = sub_id_match.group(1)
            cells = td_pattern.findall(row_html)
            if cells:
                # First cell typically contains the release name
                release_name = tag_strip.sub('', cells[0]).strip()
                if release_name:
                    results.append({
                        'name': release_name,
                        'provider': self.NAME,
                        'id': '{}:{}'.format(ktuvit_id, sub_id),
                        'language': 'he'
                    })
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
