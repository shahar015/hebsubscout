# -*- coding: utf-8 -*-
"""
Utility Module - shared helpers
"""
import sys
import json

from urllib.request import Request, urlopen
from urllib.parse import urlencode, quote_plus, parse_qsl
from urllib.error import HTTPError, URLError

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
    'up_next': {'he': 'המשך צפייה', 'en': 'Up Next'},
    'my_watchlist': {'he': 'רשימת צפייה', 'en': 'My Watchlist'},
    'watch_progress': {'he': 'היסטוריה', 'en': 'Watch Progress'},
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
    # Tools
    'connected': {'he': 'מחובר', 'en': 'Connected'},
    'not_connected': {'he': 'לא מחובר', 'en': 'Not Connected'},
    'clear_cache': {'he': 'נקה מטמון', 'en': 'Clear Cache'},
    'settings': {'he': 'הגדרות', 'en': 'Settings'},
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
    'pick_heb_subs': {'he': 'בחירת כתוביות עבריות', 'en': 'Pick Hebrew Subtitles'},
    'downloading_subs': {'he': 'מוריד כתוביות...', 'en': 'Downloading subtitles...'},
    'downloading_pct': {'he': 'מוריד... {}%', 'en': 'Downloading... {}%'},
    'sub_service_missing': {
        'he': 'שירות הכתוביות לא מותקן\nהתקן את service.subtitles.hebsubscout מהמאגר',
        'en': 'Subtitle service not installed\nInstall service.subtitles.hebsubscout from the repository',
    },
    # Season/episode labels
    'season_label': {'he': '{} ({} פרקים)', 'en': '{} ({} episodes)'},
    'next_season_ep': {'he': 'עונה {} פרק 1', 'en': 'Season {} Episode 1'},
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


def yesno_dialog(heading, message, yes_label=None, no_label=None):
    yes_label = yes_label or t('yes')
    no_label = no_label or t('no')
    return xbmcgui.Dialog().yesno(heading, message, yeslabel=yes_label, nolabel=no_label)


def progress_dialog(heading, message=''):
    d = xbmcgui.DialogProgress()
    d.create(heading, message)
    return d
