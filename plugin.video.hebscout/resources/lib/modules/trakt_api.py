# -*- coding: utf-8 -*-
"""
Trakt API Module
================
Full Trakt integration: OAuth, scrobbling, watch progress,
watchlist, collections, ratings, next episodes.
"""

import time
import json
import xbmc
from resources.lib.modules.utils import (
    http_get, http_post, log, get_setting, set_setting, notification, t, QRAuthDialog
)
from resources.lib.modules.cache import cache_get, cache_set, make_key, mark_watched as local_mark_watched

from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE = 'https://api.trakt.tv'
CLIENT_ID = 'a04728bb8144a61adca51b59ca76f2feff0d8f7467e7747676bfa4ccf4e4bedd'
CLIENT_SECRET = '982ef7cd073011fae61d3a8087dc96fda775ee1d8eda1042c0b4a65ab6cc0872'
REDIRECT_URI = 'urn:ietf:wg:oauth:2.0:oob'


def _headers(auth=True):
    h = {
        'Content-Type': 'application/json',
        'trakt-api-version': '2',
        'trakt-api-key': get_setting('trakt_client_id') or CLIENT_ID,
    }
    if auth:
        token = get_setting('trakt_token')
        if token:
            h['Authorization'] = 'Bearer {}'.format(token)
    return h


def _api_get(path, auth=True, cache_hours=0):
    if auth:
        refresh_token()
    key = make_key('trakt', path, str(auth))
    if cache_hours > 0:
        cached = cache_get(key)
        if cached:
            return cached
    url = '{}/{}'.format(BASE, path)
    data = http_get(url, headers=_headers(auth))
    if data and cache_hours > 0:
        cache_set(key, data, ttl=int(cache_hours * 3600))
    return data


def _api_post(path, data, auth=True):
    if auth:
        refresh_token()
    url = '{}/{}'.format(BASE, path)
    return http_post(url, data, headers=_headers(auth))


# =========================================================================
# AUTHORIZATION
# =========================================================================

def is_authorized():
    return bool(get_setting('trakt_token'))


def authorize():
    """Device code OAuth flow for Trakt."""
    import xbmcgui

    client_id = get_setting('trakt_client_id') or CLIENT_ID
    data = http_post('{}/oauth/device/code'.format(BASE), {
        'client_id': client_id
    }, headers={'Content-Type': 'application/json'})

    if not data:
        notification(t('trakt_auth_failed'))
        return False

    user_code = data['user_code']
    device_code = data['device_code']
    verify_url = data.get('verification_url', 'https://trakt.tv/activate')
    # Trakt supports code in URL — pre-fills the input field
    qr_url = '{}/{}'.format(verify_url, user_code)
    interval = data.get('interval', 5)
    expires_in = data.get('expires_in', 600)

    dialog = QRAuthDialog(t('trakt_auth_title'), qr_url, user_code)
    dialog.show()

    start = time.time()
    client_secret = get_setting('trakt_client_secret') or CLIENT_SECRET

    while time.time() - start < expires_in:
        if dialog.iscanceled():
            dialog.close()
            return False

        pct = int(((time.time() - start) / expires_in) * 100)
        dialog.update(pct)

        # Sleep in small increments so cancel is responsive
        for _ in range(interval * 5):
            if dialog.iscanceled():
                dialog.close()
                return False
            xbmc.sleep(200)

        token_data = http_post('{}/oauth/device/token'.format(BASE), {
            'code': device_code,
            'client_id': client_id,
            'client_secret': client_secret,
        }, headers={'Content-Type': 'application/json'})

        if token_data and token_data.get('access_token'):
            set_setting('trakt_token', token_data['access_token'])
            set_setting('trakt_refresh', token_data.get('refresh_token', ''))
            set_setting('trakt_expiry', str(time.time() + token_data.get('expires_in', 7776000)))
            dialog.close()
            notification(t('trakt_auth_success'))
            return True

    dialog.close()
    notification(t('trakt_timed_out'))
    return False


def refresh_token():
    expiry = float(get_setting('trakt_expiry') or 0)
    if time.time() < expiry - 86400:
        return True

    refresh = get_setting('trakt_refresh')
    client_id = get_setting('trakt_client_id') or CLIENT_ID
    client_secret = get_setting('trakt_client_secret') or CLIENT_SECRET
    if not refresh:
        return False

    data = http_post('{}/oauth/token'.format(BASE), {
        'refresh_token': refresh,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': REDIRECT_URI,
        'grant_type': 'refresh_token'
    }, headers={'Content-Type': 'application/json'})

    if data and data.get('access_token'):
        set_setting('trakt_token', data['access_token'])
        set_setting('trakt_refresh', data.get('refresh_token', refresh))
        set_setting('trakt_expiry', str(time.time() + data.get('expires_in', 7776000)))
        return True
    return False


def revoke():
    set_setting('trakt_token', '')
    set_setting('trakt_refresh', '')
    notification(t('trakt_removed'))


# =========================================================================
# SCROBBLING
# =========================================================================

def scrobble_start(media_type, imdb_id, progress_pct, season=None, episode=None):
    payload = _build_scrobble_payload(media_type, imdb_id, progress_pct, season, episode)
    log('Trakt scrobble/start: {}'.format(json.dumps(payload)))
    result = _api_post('scrobble/start', payload)
    if not result:
        log('Trakt scrobble/start FAILED for {} {}'.format(media_type, imdb_id), 'ERROR')
    return result


def scrobble_pause(media_type, imdb_id, progress_pct, season=None, episode=None):
    payload = _build_scrobble_payload(media_type, imdb_id, progress_pct, season, episode)
    return _api_post('scrobble/pause', payload)


def scrobble_stop(media_type, imdb_id, progress_pct, season=None, episode=None):
    payload = _build_scrobble_payload(media_type, imdb_id, progress_pct, season, episode)
    result = _api_post('scrobble/stop', payload)
    if progress_pct >= 80:
        local_mark_watched(imdb_id, season or 0, episode or 0)
    return result


def _build_scrobble_payload(media_type, imdb_id, progress_pct, season, episode):
    payload = {'progress': progress_pct}
    if media_type == 'movie':
        payload['movie'] = {'ids': {'imdb': imdb_id}}
    else:
        payload['show'] = {'ids': {'imdb': imdb_id}}
        payload['episode'] = {
            'season': int(season) if season is not None else 1,
            'number': int(episode) if episode is not None else 1
        }
    return payload


# =========================================================================
# WATCHED PROGRESS & HISTORY
# =========================================================================

def watched_movies(page=1):
    data = _api_get('sync/watched/movies', cache_hours=0.5)
    return data or []


def watched_shows():
    data = _api_get('sync/watched/shows', cache_hours=0.5)
    return data or []


def show_progress(imdb_id):
    """Get watched progress for a show - which episodes are watched, next episode, etc."""
    # Need Trakt slug - get it from the show
    data = _api_get('search/imdb/{}?type=show'.format(imdb_id))
    if not data or not data[0]:
        return None
    slug = data[0].get('show', {}).get('ids', {}).get('slug', '')
    if not slug:
        return None
    return _api_get('shows/{}/progress/watched?hidden=false&specials=false'.format(slug))


def playback_progress():
    """Get all in-progress items (resume points)."""
    return _api_get('sync/playback', cache_hours=0) or []


def remove_playback(playback_id):
    """Remove a playback progress entry."""
    try:
        req = Request('{}/sync/playback/{}'.format(BASE, playback_id))
        req.get_method = lambda: 'DELETE'
        for k, v in _headers().items():
            req.add_header(k, v)
        urlopen(req, timeout=10)
    except Exception:
        pass


# =========================================================================
# WATCHLIST
# =========================================================================

def watchlist_movies():
    data = _api_get('sync/watchlist/movies?sort=added', cache_hours=0.5)
    return data or []


def watchlist_shows():
    data = _api_get('sync/watchlist/shows?sort=added', cache_hours=0.5)
    return data or []


def add_to_watchlist(media_type, imdb_id):
    key = 'movies' if media_type == 'movie' else 'shows'
    return _api_post('sync/watchlist', {key: [{'ids': {'imdb': imdb_id}}]})


def remove_from_watchlist(media_type, imdb_id):
    key = 'movies' if media_type == 'movie' else 'shows'
    return _api_post('sync/watchlist/remove', {key: [{'ids': {'imdb': imdb_id}}]})


# =========================================================================
# COLLECTION
# =========================================================================

def collection_movies():
    return _api_get('sync/collection/movies', cache_hours=1) or []


def collection_shows():
    return _api_get('sync/collection/shows', cache_hours=1) or []


# =========================================================================
# NEXT UP (shows with unwatched episodes)
# =========================================================================

def get_next_episodes():
    """
    Get "next up" episodes - the next unwatched episode for each show
    the user is currently watching.
    """
    shows = watched_shows()
    next_eps = []
    for item in shows[:20]:  # Limit to avoid too many API calls
        show = item.get('show', {})
        imdb = show.get('ids', {}).get('imdb', '')
        slug = show.get('ids', {}).get('slug', '')
        if not slug:
            continue
        prog = _api_get('shows/{}/progress/watched?hidden=false&specials=false'.format(slug))
        if prog and prog.get('next_episode'):
            ne = prog['next_episode']
            next_eps.append({
                'show': show,
                'imdb_id': imdb,
                'season': ne.get('season'),
                'episode': ne.get('number'),
                'title': ne.get('title', ''),
            })
    return next_eps


# =========================================================================
# LISTS & RECOMMENDATIONS
# =========================================================================

def trending_movies(page=1):
    return _api_get('movies/trending?page={}&limit=20'.format(page), auth=False, cache_hours=4) or []


def trending_shows(page=1):
    return _api_get('shows/trending?page={}&limit=20'.format(page), auth=False, cache_hours=4) or []


def recommendations_movies():
    return _api_get('recommendations/movies', cache_hours=12) or []


def recommendations_shows():
    return _api_get('recommendations/shows', cache_hours=12) or []


def user_lists():
    return _api_get('users/me/lists', cache_hours=1) or []


def list_items(list_id):
    return _api_get('users/me/lists/{}/items'.format(list_id), cache_hours=0.5) or []


# =========================================================================
# HISTORY / MARK WATCHED
# =========================================================================

def mark_movie_watched(imdb_id):
    return _api_post('sync/history', {'movies': [{'ids': {'imdb': imdb_id}}]})


def mark_episode_watched(imdb_id, season, episode):
    return _api_post('sync/history', {
        'shows': [{'ids': {'imdb': imdb_id}, 'seasons': [
            {'number': season, 'episodes': [{'number': episode}]}
        ]}]
    })


# =========================================================================
# HELPERS
# =========================================================================

def get_imdb_from_trakt(trakt_item):
    """Extract IMDB ID from a Trakt API response item."""
    for key in ('movie', 'show', 'episode'):
        obj = trakt_item.get(key, {})
        imdb = obj.get('ids', {}).get('imdb', '')
        if imdb:
            return imdb
    return ''
