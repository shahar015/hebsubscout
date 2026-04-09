# -*- coding: utf-8 -*-
"""
Utility Module - shared helpers
"""
import os
import sys
import json

from urllib.parse import urlencode, quote_plus, parse_qsl

import requests as _requests

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin

ADDON = xbmcaddon.Addon('plugin.video.hebscout')
ADDON_ID = ADDON.getAddonInfo('id')
ADDON_NAME = ADDON.getAddonInfo('name')
ADDON_ICON = ADDON.getAddonInfo('icon')
ADDON_FANART = ADDON.getAddonInfo('fanart')

TMDB_KEY = ADDON.getSetting('tmdb_api_key') or '814542f9e3ac8132198f2b3d541a4bc2'
TMDB_LANG = ADDON.getSetting('tmdb_language') or 'he-IL'
TMDB_IMG_BASE = 'https://image.tmdb.org/t/p/'
TMDB_POSTER = TMDB_IMG_BASE + 'w500'
TMDB_FANART_URL = TMDB_IMG_BASE + 'w1280'

# =========================================================================
# UI LANGUAGE / TRANSLATION
# =========================================================================

_UI_LANG = ADDON.getSetting('ui_language') or 'עברית'

_STRINGS = {
    # Main menu
    'movies': {'he': 'סרטים', 'en': 'Movies'},
    'tv_shows': {'he': 'סדרות', 'en': 'TV Shows'},
    'up_next': {'he': 'פרק הבא', 'en': 'Up Next'},
    'my_watchlist': {'he': 'רשימת צפייה', 'en': 'My Watchlist'},
    'watch_progress': {'he': 'היסטוריה', 'en': 'Watch Progress'},
    'continue_watching': {'he': 'המשך צפייה', 'en': 'Continue Watching'},
    'watch_history': {'he': 'היסטוריה', 'en': 'History'},
    'progress_pct': {'he': '{}% נצפה', 'en': '{}% watched'},
    'search': {'he': 'חיפוש', 'en': 'Search'},
    'popular_people': {'he': 'שחקנים', 'en': 'Popular People'},
    'tools': {'he': 'כלים', 'en': 'Tools'},
    # Movie/Show submenus
    'trending': {'he': 'טרנדינג', 'en': 'Trending'},
    'popular': {'he': 'פופולרי', 'en': 'Popular'},
    'top_rated': {'he': 'מדורג', 'en': 'Top Rated'},
    'now_playing': {'he': 'בקולנוע', 'en': 'Now Playing'},
    'upcoming': {'he': 'בקרוב', 'en': 'Upcoming'},
    'genres': {'he': "ז'אנרים", 'en': 'Genres'},
    'search_movies': {'he': 'חיפוש סרטים', 'en': 'Search Movies'},
    'search_shows': {'he': 'חיפוש סדרות', 'en': 'Search Shows'},
    'airing_today': {'he': 'משודר היום', 'en': 'Airing Today'},
    'next_page': {'he': 'עמוד הבא >', 'en': 'Next Page >'},
    # Watchlist
    'wl_movies': {'he': 'סרטים', 'en': 'Movies'},
    'wl_shows': {'he': 'סדרות', 'en': 'Shows'},
    # Search
    'search_prompt': {'he': 'חיפוש', 'en': 'Search'},
    'search_movies_prompt': {'he': 'חפש סרט', 'en': 'Search Movie'},
    'search_shows_prompt': {'he': 'חפש סדרה', 'en': 'Search Show'},
    'search_results_movies': {'he': 'סרטים', 'en': 'Movies'},
    'search_results_shows': {'he': 'סדרות', 'en': 'TV Shows'},
    # Tools & Settings
    'connected': {'he': 'מחובר', 'en': 'Connected'},
    'not_connected': {'he': 'לא מחובר', 'en': 'Not Connected'},
    'clear_cache': {'he': 'נקה מטמון', 'en': 'Clear Cache'},
    'clear_search_history': {'he': 'נקה היסטוריית חיפוש', 'en': 'Clear Search History'},
    'settings': {'he': 'הגדרות', 'en': 'Settings'},
    'accounts_header': {'he': '── חשבונות ──', 'en': '── Accounts ──'},
    'toggles_header': {'he': '── הגדרות מהירות ──', 'en': '── Quick Settings ──'},
    'system_header': {'he': '── מערכת ──', 'en': '── System ──'},
    'premium_until': {'he': 'פרימיום עד {}', 'en': 'Premium until {}'},
    'user_label': {'he': 'משתמש: {}', 'en': 'User: {}'},
    'auto_subs_toggle': {'he': 'כתוביות אוטומטיות', 'en': 'Auto Subtitles'},
    'auto_play_toggle': {'he': 'ניגון אוטומטי', 'en': 'Auto Play'},
    'auto_next_toggle': {'he': 'פרק הבא אוטומטי', 'en': 'Auto Next Episode'},
    'language_toggle': {'he': 'שפה: עברית', 'en': 'Language: English'},
    'on': {'he': 'פעיל', 'en': 'ON'},
    'off': {'he': 'כבוי', 'en': 'OFF'},
    'about': {'he': 'אודות', 'en': 'About'},
    'version_info': {'he': 'HebScout גרסה {}', 'en': 'HebScout v{}'},
    'history_cleared': {'he': 'היסטוריית חיפוש נמחקה', 'en': 'Search history cleared'},
    'new_search': {'he': 'חיפוש חדש...', 'en': 'New Search...'},
    # Notifications & dialogs
    'show_not_found': {'he': 'הסדרה לא נמצאה', 'en': 'Show not found'},
    'imdb_not_found': {'he': 'מזהה IMDB לא נמצא', 'en': 'IMDB ID not found'},
    'no_sources_found': {'he': 'לא נמצאו מקורות', 'en': 'No sources found'},
    'failed_resolve': {'he': 'נכשל בחיבור למקור', 'en': 'Failed to resolve source'},
    'cache_cleared': {'he': 'המטמון נוקה', 'en': 'Cache cleared'},
    'added_watchlist': {'he': 'נוסף לרשימת הצפייה ב-Trakt', 'en': 'Added to Trakt Watchlist'},
    'disconnect_rd': {'he': 'לנתק את Real Debrid?', 'en': 'Disconnect Real Debrid?'},
    'disconnect_trakt': {'he': 'לנתק את Trakt?', 'en': 'Disconnect Trakt?'},
    'not_playing': {'he': 'לא מתנגן כרגע', 'en': 'Not currently playing'},
    # Sources
    'searching_sources': {'he': 'מחפש מקורות...', 'en': 'Searching sources...'},
    'connecting_source': {'he': 'מחבר למקור...', 'en': 'Connecting to source...'},
    'checking_rd': {'he': 'בודק זמינות Real Debrid...', 'en': 'Checking RD cache...'},
    'checking_subs': {'he': 'בודק כתוביות בעברית...', 'en': 'Checking Hebrew subs...'},
    'select_source': {'he': 'בחר מקור', 'en': 'Select Source'},
    'filter_sources': {'he': 'סינון מקורות', 'en': 'Filter Sources'},
    'show_all': {'he': 'הצג הכל', 'en': 'Show All'},
    'quality': {'he': 'איכות', 'en': 'Quality'},
    'rd_cached_only': {'he': 'RD Cached בלבד', 'en': 'RD Cached Only'},
    'subs_100': {'he': 'כתוביות מובנות', 'en': 'Embedded Subs'},
    'subs_70': {'he': 'התאמה 70%+', 'en': '70%+ Match'},
    'subs_any': {'he': 'כתוביות כלשהן', 'en': 'Any Subs'},
    'found_sources': {'he': 'נמצאו {} מקורות', 'en': 'Found {} sources'},
    'ready_sources': {'he': 'מוכן - {} מקורות', 'en': 'Ready - {} sources'},
    'scraping_sources': {'he': 'מחפש מקורות...', 'en': 'Scraping sources...'},
    'no_sources': {'he': 'לא נמצאו מקורות', 'en': 'No sources found'},
    # First-run setup
    'first_run_title': {'he': 'HebScout - הגדרה ראשונה', 'en': 'HebScout - First Setup'},
    'first_run_welcome': {
        'he': 'ברוך הבא ל-HebScout!\n\nנדרש חיבור Real Debrid להפעלת מקורות.\nיש לך חשבון Real Debrid?',
        'en': 'Welcome to HebScout!\n\nReal Debrid is required for streaming sources.\nDo you have a Real Debrid account?',
    },
    'connect_now': {'he': 'חבר עכשיו', 'en': 'Connect Now'},
    'later': {'he': 'מאוחר יותר', 'en': 'Later'},
    'trakt_optional_title': {'he': 'HebScout - Trakt (אופציונלי)', 'en': 'HebScout - Trakt (Optional)'},
    'trakt_optional_msg': {
        'he': 'רוצה לחבר Trakt?\n\nמעקב התקדמות צפייה, רשימות צפייה,\nפרק הבא, והמלצות אישיות.',
        'en': 'Connect Trakt?\n\nTrack watch progress, watchlists,\nnext episodes, and personal recommendations.',
    },
    'connect_trakt': {'he': 'חבר Trakt', 'en': 'Connect Trakt'},
    'skip': {'he': 'דלג', 'en': 'Skip'},
    # Ktuvit setup
    'ktuvit_optional_title': {'he': 'HebScout - Ktuvit (אופציונלי)', 'en': 'HebScout - Ktuvit (Optional)'},
    'ktuvit_optional_msg': {
        'he': 'רוצה לחבר Ktuvit.me?\n\nמאגר כתוביות עברית נוסף.\nנדרש חשבון Ktuvit (אימייל + סיסמה).',
        'en': 'Connect Ktuvit.me?\n\nAdditional Hebrew subtitle source.\nRequires Ktuvit account (email + password).',
    },
    'ktuvit_connect': {'he': 'חבר Ktuvit', 'en': 'Connect Ktuvit'},
    'ktuvit_email_prompt': {'he': 'אימייל Ktuvit', 'en': 'Ktuvit Email'},
    'ktuvit_password_prompt': {'he': 'סיסמת Ktuvit', 'en': 'Ktuvit Password'},
    'ktuvit_saved': {'he': 'Ktuvit הוגדר בהצלחה!', 'en': 'Ktuvit configured successfully!'},
    # Real Debrid auth
    'rd_auth_failed': {'he': 'אימות Real Debrid נכשל', 'en': 'Real Debrid authorization failed'},
    'rd_auth_title': {'he': 'אימות Real Debrid', 'en': 'Real Debrid Authorization'},
    'rd_auth_go_to': {'he': 'גש ל: {}\nהכנס קוד: [COLOR lime]{}[/COLOR]', 'en': 'Go to: {}\nEnter code: [COLOR lime]{}[/COLOR]'},
    'rd_auth_success': {'he': 'Real Debrid חובר בהצלחה!', 'en': 'Real Debrid authorized successfully!'},
    'auth_timed_out': {'he': 'האימות פג תוקף', 'en': 'Authorization timed out'},
    'rd_removed': {'he': 'חשבון Real Debrid הוסר', 'en': 'Real Debrid account removed'},
    'rd_not_authorized': {'he': 'Real Debrid לא מחובר', 'en': 'Real Debrid not authorized'},
    # Trakt auth
    'trakt_auth_failed': {'he': 'אימות Trakt נכשל', 'en': 'Trakt authorization failed'},
    'trakt_auth_title': {'he': 'אימות Trakt', 'en': 'Trakt Authorization'},
    'trakt_auth_go_to': {'he': 'גש ל: {}\nהכנס קוד: [COLOR lime]{}[/COLOR]', 'en': 'Go to: {}\nEnter code: [COLOR lime]{}[/COLOR]'},
    'trakt_auth_success': {'he': 'Trakt חובר בהצלחה!', 'en': 'Trakt authorized successfully!'},
    'trakt_timed_out': {'he': 'אימות Trakt פג תוקף', 'en': 'Trakt authorization timed out'},
    'trakt_removed': {'he': 'חשבון Trakt הוסר', 'en': 'Trakt account removed'},
    # Context menu
    'trakt_watchlist_add': {'he': 'הוסף לרשימת צפייה +', 'en': 'Trakt Watchlist +'},
    # Player
    'resume_title': {'he': 'המשך צפייה', 'en': 'Resume Playback'},
    'resume_msg': {'he': 'להמשיך מ-{:.0f}%?', 'en': 'Resume from {:.0f}%?'},
    'resume_yes': {'he': 'המשך', 'en': 'Resume'},
    'resume_no': {'he': 'מההתחלה', 'en': 'From Start'},
    'next_ep_title': {'he': 'פרק הבא', 'en': 'Next Episode'},
    'next_ep_play': {'he': 'הפעל', 'en': 'Play'},
    'next_ep_stop': {'he': 'עצור', 'en': 'Stop'},
    'no_heb_subs': {'he': 'לא נמצאו כתוביות בעברית', 'en': 'No Hebrew subtitles found'},
    'sub_search_start': {'he': 'מחפש כתוביות עבריות...', 'en': 'Searching Hebrew subs...'},
    'sub_found': {'he': 'נמצאו {} כתוביות, התאמה {}%', 'en': 'Found {} subs, best match {}%'},
    'sub_applied': {'he': 'כתוביות הופעלו ({}%)', 'en': 'Subtitles applied ({}%)'},
    'pick_heb_subs': {'he': 'בחירת כתוביות עבריות', 'en': 'Pick Hebrew Subtitles'},
    'downloading_subs': {'he': 'מוריד כתוביות...', 'en': 'Downloading subtitles...'},
    'downloading_pct': {'he': 'מוריד... {}%', 'en': 'Downloading... {}%'},
    'audio_track': {'he': '\u05e2\u05e8\u05d5\u05e5 \u05e9\u05de\u05e2', 'en': 'Audio Track'},
    'sub_service_missing': {
        'he': 'שירות הכתוביות לא מותקן\nהתקן את service.subtitles.hebsubscout מהמאגר',
        'en': 'Subtitle service not installed\nInstall service.subtitles.hebsubscout from the repository',
    },
    # Season/episode labels
    'season_label': {'he': '{} ({} פרקים)', 'en': '{} ({} episodes)'},
    'next_season_ep': {'he': 'עונה {} פרק 1', 'en': 'Season {} Episode 1'},
    # QR Auth dialog
    'scan_or_visit': {'he': 'סרוק או גש ל:', 'en': 'Scan or go to:'},
    'enter_code': {'he': 'הכנס קוד:', 'en': 'Enter code:'},
    # Yes/No defaults
    'yes': {'he': 'כן', 'en': 'Yes'},
    'no': {'he': 'לא', 'en': 'No'},
}


def is_hebrew():
    """Check if UI language is set to Hebrew."""
    return _UI_LANG != 'English'


def t(key, *args):
    """
    Get translated string by key.
    Falls back to English if key not found.
    Use *args for .format() substitution.
    """
    lang = 'he' if is_hebrew() else 'en'
    entry = _STRINGS.get(key, {})
    text = entry.get(lang, entry.get('en', key))
    if args:
        text = text.format(*args)
    return text


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


# Shared HTTP session — connection pooling, gzip, keep-alive
_session = _requests.Session()
_session.headers.update({'User-Agent': 'HebScout/1.0 Kodi'})


def http_get(url, headers=None, timeout=12):
    try:
        resp = _session.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except _requests.HTTPError as e:
        log('HTTP {} from {}'.format(e.response.status_code, url), 'ERROR')
        return None
    except Exception as e:
        log('HTTP GET failed: {} - {}'.format(url, e), 'ERROR')
        return None


def http_post(url, data, headers=None, timeout=12):
    try:
        resp = _session.post(url, json=data, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except _requests.HTTPError as e:
        try:
            err_body = e.response.text[:500]
        except Exception:
            err_body = ''
        log('HTTP POST {} from {} | {}'.format(e.response.status_code, url, err_body), 'ERROR')
        return None
    except Exception as e:
        log('HTTP POST failed: {} - {}'.format(url, e), 'ERROR')
        return None


def http_get_raw(url, headers=None, timeout=12):
    """Return raw text instead of parsed JSON."""
    try:
        resp = _session.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.text
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


def yesno_dialog(heading, message, yes_label=None, no_label=None):
    yes_label = yes_label or t('yes')
    no_label = no_label or t('no')
    return xbmcgui.Dialog().yesno(heading, message, yeslabel=yes_label, nolabel=no_label)


def progress_dialog(heading, message=''):
    d = xbmcgui.DialogProgress()
    d.create(heading, message)
    return d


def _get_white_texture():
    """Get path to white PNG texture for colorDiffuse tinting."""
    # Use the skin media texture (proper 16x16 PNG)
    addon_path = ADDON.getAddonInfo('path')
    skin_tex = os.path.join(addon_path, 'resources', 'skins', 'Default', 'media', 'white.png')
    if os.path.exists(skin_tex):
        return skin_tex
    # Fallback: create in profile
    import xbmcvfs
    profile = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
    os.makedirs(profile, exist_ok=True)
    path = os.path.join(profile, 'white.png')
    if not os.path.exists(path):
        import struct, zlib
        def _chunk(ct, d):
            c = ct + d
            return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
        raw = b''
        for _ in range(16):
            raw += b'\x00' + b'\xff\xff\xff' * 16
        data = (b'\x89PNG\r\n\x1a\n' +
                _chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 2, 0, 0, 0)) +
                _chunk(b'IDAT', zlib.compress(raw)) +
                _chunk(b'IEND', b''))
        with open(path, 'wb') as f:
            f.write(data)
    return path


class QRAuthDialog(xbmcgui.WindowDialog):
    """
    Custom auth dialog with QR code, URL, and code display.
    Used for Real Debrid and Trakt device authorization.
    """

    def __init__(self, heading, verify_url, user_code, display_url=None):
        super().__init__()
        self.cancelled = False
        tex = _get_white_texture()

        # WindowDialog uses 1280x720 coordinate system (NOT 1920x1080)
        SW, SH = 1280, 720

        # Full-screen dimmer (two layers for guaranteed opacity)
        self.addControl(xbmcgui.ControlImage(0, 0, SW, SH, tex, colorDiffuse='FF000000'))
        self.addControl(xbmcgui.ControlImage(0, 0, SW, SH, tex, colorDiffuse='EE000000'))

        # Dialog panel (centered, lighter so text is readable)
        w, h = 460, 400
        x = (SW - w) // 2
        y = (SH - h) // 2
        self.addControl(xbmcgui.ControlImage(x, y, w, h, tex, colorDiffuse='FF1a1a35'))
        # Second layer to ensure opacity
        self.addControl(xbmcgui.ControlImage(x, y, w, h, tex, colorDiffuse='FF1a1a35'))

        # Heading
        self.addControl(xbmcgui.ControlLabel(
            x, y + 8, w, 30, heading,
            font='font13', textColor='FF00d4aa', alignment=0x00000002
        ))

        # QR code image (encode full URL for QR)
        qr_size = 160
        qr_url = 'https://api.qrserver.com/v1/create-qr-code/?size=256x256&bgcolor=0f0f24&color=ffffff&data={}'.format(
            quote_plus(verify_url)
        )
        qr_x = x + (w - qr_size) // 2
        self.addControl(xbmcgui.ControlImage(qr_x, y + 42, qr_size, qr_size, qr_url))

        # "Scan or go to:" label
        self.addControl(xbmcgui.ControlLabel(
            x, y + 210, w, 20, t('scan_or_visit'),
            font='font12', textColor='FFaaaaaa', alignment=0x00000002
        ))

        # URL (show friendly display_url if provided, not the full QR link)
        self.addControl(xbmcgui.ControlLabel(
            x, y + 232, w, 25, '[COLOR cyan]{}[/COLOR]'.format(display_url or verify_url),
            font='font12', alignment=0x00000002
        ))

        # "Enter code:" label
        self.addControl(xbmcgui.ControlLabel(
            x, y + 265, w, 20, t('enter_code'),
            font='font12', textColor='FFaaaaaa', alignment=0x00000002
        ))

        # Code (large, bright)
        self.addControl(xbmcgui.ControlLabel(
            x, y + 290, w, 40, '[COLOR lime]{}[/COLOR]'.format(user_code),
            font='font14', textColor='FFffffff', alignment=0x00000002
        ))

        # Progress bar
        bar_w, bar_h = 340, 4
        bar_x = x + (w - bar_w) // 2
        bar_y = y + h - 18
        self.addControl(xbmcgui.ControlImage(bar_x, bar_y, bar_w, bar_h, tex, colorDiffuse='FF333333'))
        self._progress_bar = xbmcgui.ControlImage(bar_x, bar_y, 1, bar_h, tex, colorDiffuse='FF00d4aa')
        self.addControl(self._progress_bar)
        self._bar_w = bar_w

    def update(self, pct):
        pw = max(1, int(self._bar_w * pct / 100))
        try:
            self._progress_bar.setWidth(pw)
        except Exception:
            pass

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 216):
            self.cancelled = True
            self.close()

    def iscanceled(self):
        return self.cancelled
