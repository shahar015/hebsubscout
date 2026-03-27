# -*- coding: utf-8 -*-
"""
Real Debrid API Module
======================
Authorization, torrent cache checking, link unrestricting, and streaming.
"""

import time
import json
import xbmc
from resources.lib.modules.utils import (
    http_get, http_post, log, get_setting, set_setting, notification, t, QRAuthDialog
)
from resources.lib.modules.cache import cache_get, cache_set, make_key

from urllib.request import Request, urlopen
from urllib.parse import urlencode

BASE = 'https://api.real-debrid.com/rest/1.0'
OAUTH_BASE = 'https://api.real-debrid.com/oauth/v2'
CLIENT_ID = 'X245A4XAIBGVM'  # Open source client ID for device auth


def _headers():
    token = get_setting('rd_token')
    return {'Authorization': 'Bearer {}'.format(token)} if token else {}


def _api_get(path, **params):
    url = '{}/{}'.format(BASE, path)
    if params:
        url += '?{}'.format(urlencode(params))
    return http_get(url, headers=_headers())


def _api_post(path, data):
    url = '{}/{}'.format(BASE, path)
    # Real Debrid uses form-encoded POST, not JSON
    try:
        body = urlencode(data).encode('utf-8')
        req = Request(url, data=body)
        req.add_header('User-Agent', 'HebScout/1.0')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        token = get_setting('rd_token')
        if token:
            req.add_header('Authorization', 'Bearer {}'.format(token))
        resp = urlopen(req, timeout=15)
        return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        log('RD POST error: {}'.format(e), 'ERROR')
        return None


# =========================================================================
# AUTHORIZATION (Device Code Flow)
# =========================================================================

def is_authorized():
    return bool(get_setting('rd_token'))


def authorize():
    """
    Start device code authorization flow.
    Returns (user_code, device_code, verification_url) for the UI to display.
    """
    import xbmcgui
    url = '{}/device/code?client_id={}&new_credentials=yes'.format(OAUTH_BASE, CLIENT_ID)
    data = http_get(url)
    if not data:
        notification(t('rd_auth_failed'))
        return False

    device_code = data['device_code']
    user_code = data['user_code']
    verify_url = data.get('verification_url', 'https://real-debrid.com/device')
    # Use direct_verification_url for QR (auto-authorizes, no code typing)
    qr_url = data.get('direct_verification_url') or '{}?user_code={}'.format(verify_url, user_code)
    interval = data.get('interval', 5)
    expires_in = data.get('expires_in', 600)

    dialog = QRAuthDialog(t('rd_auth_title'), qr_url, user_code, display_url=verify_url)
    dialog.show()

    start = time.time()
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

        # Poll for credentials
        cred_url = '{}/device/credentials?client_id={}&code={}'.format(
            OAUTH_BASE, CLIENT_ID, device_code
        )
        cred = http_get(cred_url)
        if cred and cred.get('client_id'):
            # Got credentials, now get token (RD requires form-encoded POST)
            token_form = urlencode({
                'client_id': cred['client_id'],
                'client_secret': cred['client_secret'],
                'code': device_code,
                'grant_type': 'http://oauth.net/grant_type/device/1.0'
            }).encode('utf-8')
            try:
                req = Request('{}/token'.format(OAUTH_BASE), data=token_form)
                req.add_header('Content-Type', 'application/x-www-form-urlencoded')
                req.add_header('User-Agent', 'HebScout/1.0')
                resp = urlopen(req, timeout=15)
                token_data = json.loads(resp.read().decode('utf-8'))
            except Exception as e:
                log('RD token request failed: {}'.format(e), 'ERROR')
                token_data = None
            if token_data and token_data.get('access_token'):
                set_setting('rd_token', token_data['access_token'])
                set_setting('rd_refresh', token_data.get('refresh_token', ''))
                set_setting('rd_client_id', cred['client_id'])
                set_setting('rd_client_secret', cred['client_secret'])
                set_setting('rd_expiry', str(time.time() + token_data.get('expires_in', 86400)))
                dialog.close()
                notification(t('rd_auth_success'))
                return True

    dialog.close()
    notification(t('auth_timed_out'))
    return False


def refresh_token():
    """Refresh the access token if expired."""
    expiry = float(get_setting('rd_expiry') or 0)
    if time.time() < expiry - 600:  # 10 min buffer
        return True

    refresh = get_setting('rd_refresh')
    client_id = get_setting('rd_client_id')
    client_secret = get_setting('rd_client_secret')
    if not all([refresh, client_id, client_secret]):
        return False

    try:
        form = urlencode({
            'client_id': client_id,
            'client_secret': client_secret,
            'code': refresh,
            'grant_type': 'http://oauth.net/grant_type/device/1.0'
        }).encode('utf-8')
        req = Request('{}/token'.format(OAUTH_BASE), data=form)
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        req.add_header('User-Agent', 'HebScout/1.0')
        resp = urlopen(req, timeout=15)
        data = json.loads(resp.read().decode('utf-8'))
    except Exception:
        data = None
    if data and data.get('access_token'):
        set_setting('rd_token', data['access_token'])
        set_setting('rd_refresh', data.get('refresh_token', refresh))
        set_setting('rd_expiry', str(time.time() + data.get('expires_in', 86400)))
        return True
    return False


def revoke():
    set_setting('rd_token', '')
    set_setting('rd_refresh', '')
    set_setting('rd_client_id', '')
    set_setting('rd_client_secret', '')
    notification(t('rd_removed'))


# =========================================================================
# TORRENT CACHE CHECK (the key feature for source scraping)
# =========================================================================

MAX_CACHE_CHECK = 10  # Only check top N sources (each requires 3 API calls)


def check_cache(hashes):
    """
    Check which torrent hashes are instantly available (cached) on RD.

    Uses addMagnet → torrent_info → delete workaround since RD removed
    the instantAvailability endpoint in Nov 2024.

    Only checks the first MAX_CACHE_CHECK hashes to avoid API rate limits
    (each check requires 3 API calls: add, info, delete).

    Args:
        hashes: list of info_hash strings (only first 10 are checked)

    Returns:
        set of lowercase hashes that are cached
    """
    if not hashes:
        return set()
    refresh_token()

    cached = set()
    for h in hashes[:MAX_CACHE_CHECK]:
        magnet = 'magnet:?xt=urn:btih:{}'.format(h)
        try:
            tid = add_magnet(magnet)
            if not tid:
                continue
            info = torrent_info(tid)
            if info and info.get('status') == 'downloaded':
                cached.add(h.lower())
            delete_torrent(tid)
        except Exception as e:
            log('RD cache check failed for {}: {}'.format(h[:8], e), 'ERROR')
    return cached


# =========================================================================
# UNRESTRICT & RESOLVE
# =========================================================================

def unrestrict_link(link):
    """Unrestrict a hoster link through Real Debrid."""
    refresh_token()
    data = _api_post('unrestrict/link', {'link': link})
    if data and data.get('download'):
        return data['download']
    return None


def add_magnet(magnet_link):
    """Add a magnet link to RD and return torrent ID."""
    refresh_token()
    data = _api_post('torrents/addMagnet', {'magnet': magnet_link})
    if data and data.get('id'):
        return data['id']
    return None


def select_files(torrent_id, file_ids='all'):
    """Select files from a torrent for downloading."""
    refresh_token()
    _api_post('torrents/selectFiles/{}'.format(torrent_id), {'files': file_ids})


def torrent_info(torrent_id):
    """Get torrent status/info."""
    refresh_token()
    return _api_get('torrents/info/{}'.format(torrent_id))


def delete_torrent(torrent_id):
    """Delete a torrent from RD."""
    refresh_token()
    try:
        req = Request('{}/torrents/delete/{}'.format(BASE, torrent_id))
        req.get_method = lambda: 'DELETE'
        req.add_header('Authorization', 'Bearer {}'.format(get_setting('rd_token')))
        urlopen(req, timeout=10)
    except Exception:
        pass


def resolve_magnet(magnet_link):
    """
    Full resolution flow: add magnet -> select files -> get download link.
    Returns playable URL or None.
    """
    tid = add_magnet(magnet_link)
    if not tid:
        return None

    select_files(tid)

    # Poll for completion
    for _ in range(30):
        info = torrent_info(tid)
        if not info:
            break
        status = info.get('status', '')
        if status == 'downloaded':
            links = info.get('links', [])
            if links:
                # Find the largest file (usually the video)
                url = unrestrict_link(links[0])
                delete_torrent(tid)
                return url
            break
        elif status in ('magnet_error', 'error', 'virus', 'dead'):
            break
        time.sleep(1)

    delete_torrent(tid)
    return None


# =========================================================================
# USER INFO
# =========================================================================

def user_info():
    refresh_token()
    return _api_get('user')
