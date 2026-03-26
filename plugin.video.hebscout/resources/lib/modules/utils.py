# -*- coding: utf-8 -*-
"""
Utility Module - shared helpers
"""
import sys
import json

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode, quote_plus, parse_qsl
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError
    from urllib import urlencode, quote_plus
    from urlparse import parse_qsl

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

ADDON = xbmcaddon.Addon('plugin.video.hebscout')
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = ADDON.getAddonInfo('fanart')

TMDB_KEY = ADDON.getSetting('tmdb_api_key') or ''
TMDB_LANG = ADDON.getSetting('tmdb_language') or 'he-IL'
TMDB_IMG_BASE = 'https://image.tmdb.org/t/p/'
TMDB_POSTER = TMDB_IMG_BASE + 'w500'
TMDB_FANART_URL = TMDB_IMG_BASE + 'w1280'


def log(msg, level='INFO'):
    xbmc.log('[HebScout] {}: {}'.format(level, msg), xbmc.LOGINFO)


def get_setting(key, fallback=''):
    return ADDON.getSetting(key) or fallback


def set_setting(key, value):
    ADDON.setSetting(key, str(value))


def notification(msg, heading=None, icon=None, time=3000):
    heading = heading or ADDON_NAME
    icon = icon or ADDON_ICON or 'DefaultIconInfo.png'
    xbmcgui.Dialog().notification(heading, msg, icon, time)


def http_get(url, headers=None, timeout=12):
    try:
        req = Request(url)
        req.add_header('User-Agent', 'HebScout/1.0 Kodi')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        log('HTTP {} from {}'.format(e.code, url), 'ERROR')
        return None
    except Exception as e:
        log('HTTP GET failed: {} - {}'.format(url, e), 'ERROR')
        return None


def http_post(url, data, headers=None, timeout=12):
    try:
        body = json.dumps(data).encode('utf-8')
        req = Request(url, data=body)
        req.add_header('User-Agent', 'HebScout/1.0 Kodi')
        req.add_header('Content-Type', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        return json.loads(resp.read().decode('utf-8'))
    except HTTPError as e:
        log('HTTP POST {} from {}'.format(e.code, url), 'ERROR')
        return None
    except Exception as e:
        log('HTTP POST failed: {} - {}'.format(url, e), 'ERROR')
        return None


def http_get_raw(url, headers=None, timeout=12):
    """Return raw text instead of parsed JSON."""
    try:
        req = Request(url)
        req.add_header('User-Agent', 'HebScout/1.0 Kodi')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        return resp.read().decode('utf-8')
    except Exception as e:
        log('HTTP raw GET failed: {}'.format(e), 'ERROR')
        return None


def build_url(base_url, params):
    return '{}?{}'.format(base_url, urlencode(params))


def parse_params(param_string):
    return dict(parse_qsl(param_string.lstrip('?')))


def select_dialog(heading, items):
    """Show a selection dialog and return chosen index or -1."""
    return xbmcgui.Dialog().select(heading, items)


def input_dialog(heading, input_type=xbmcgui.INPUT_ALPHANUM):
    return xbmcgui.Dialog().input(heading, type=input_type)


def yesno_dialog(heading, message, yes_label='כן', no_label='לא'):
    return xbmcgui.Dialog().yesno(heading, message, yeslabel=yes_label, nolabel=no_label)


def progress_dialog(heading, message=''):
    d = xbmcgui.DialogProgress()
    d.create(heading, message)
    return d
