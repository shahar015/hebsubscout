# -*- coding: utf-8 -*-
"""
HebScout - Main Entry Point
============================
Full-featured video addon with native HebSubScout integration.
"""

import sys
import json

try:
    from urllib.parse import urlencode, parse_qsl, quote_plus
except ImportError:
    from urllib import urlencode, quote_plus
    from urlparse import parse_qsl

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Add our lib to path
sys.path.insert(0, xbmcaddon.Addon().getAddonInfo('path') + '/resources/lib')

from resources.lib.modules import tmdb, realdebrid as rd, trakt_api as trakt
from resources.lib.modules.sources import get_sources, build_source_label, resolve_source
from resources.lib.modules.player import HebScoutPlayer
from resources.lib.modules.cache import is_watched, cache_clear
from resources.lib.modules.utils import (
    log, notification, ADDON, ADDON_NAME, ADDON_FANART,
    progress_dialog, input_dialog, select_dialog, yesno_dialog,
    get_setting, set_setting
)

HANDLE = int(sys.argv[1])
BASE_URL = sys.argv[0]

_player = None


def url_for(**params):
    return '{}?{}'.format(BASE_URL, urlencode(params))


def add_dir(label, action, is_folder=True, poster='', fanart='', plot='', **kwargs):
    li = xbmcgui.ListItem(label=label)
    art = {}
    if poster:
        art['poster'] = art['thumb'] = poster
    if fanart:
        art['fanart'] = fanart
    elif ADDON_FANART:
        art['fanart'] = ADDON_FANART
    li.setArt(art)
    if plot:
        li.setInfo('video', {'plot': plot})
    params = {'action': action}
    params.update(kwargs)
    xbmcplugin.addDirectoryItem(HANDLE, url_for(**params), li, is_folder)


def add_item(meta, action='play', is_folder=False, context_items=None):
    """Add a movie/show/episode list item with full metadata."""
    li = xbmcgui.ListItem(label=meta.get('title', ''))
    
    info_tag = li.getVideoInfoTag()
    info_tag.setTitle(meta.get('title', ''))
    info_tag.setYear(int(meta.get('year') or 0))
    info_tag.setPlot(meta.get('plot', ''))
    info_tag.setRating(float(meta.get('rating') or 0))
    info_tag.setIMDBNumber(meta.get('imdb_id', ''))
    
    media_type = meta.get('media_type', 'movie')
    if media_type == 'movie':
        info_tag.setMediaType('movie')
    elif media_type == 'tv':
        info_tag.setMediaType('tvshow')
    elif media_type == 'episode':
        info_tag.setMediaType('episode')
        info_tag.setSeason(meta.get('season_number', 0))
        info_tag.setEpisode(meta.get('episode_number', 0))
    
    art = {}
    if meta.get('poster'):
        art['poster'] = art['thumb'] = meta['poster']
    if meta.get('fanart'):
        art['fanart'] = meta['fanart']
    if meta.get('still'):
        art['thumb'] = meta['still']
    li.setArt(art)
    
    # Watched overlay
    imdb = meta.get('imdb_id', '')
    season = meta.get('season_number', 0)
    episode = meta.get('episode_number', 0)
    if imdb and is_watched(imdb, season, episode):
        li.setInfo('video', {'playcount': 1})
    
    # Context menu
    cm = context_items or []
    if imdb and trakt.is_authorized():
        cm.append(('Trakt Watchlist +', 'RunPlugin({})'.format(
            url_for(action='trakt_watchlist_add', imdb_id=imdb, media_type=media_type))))
    li.addContextMenuItems(cm)
    
    params = {'action': action, 'tmdb_id': meta.get('tmdb_id', ''),
              'imdb_id': imdb, 'media_type': media_type, 'title': meta.get('title', ''),
              'year': meta.get('year', ''), 'poster': meta.get('poster', ''),
              'fanart': meta.get('fanart', '')}
    if season:
        params['season'] = season
    if episode:
        params['episode'] = episode
    
    xbmcplugin.addDirectoryItem(HANDLE, url_for(**params), li, is_folder)


def end_dir(content='videos', sort=None):
    if content:
        xbmcplugin.setContent(HANDLE, content)
    if sort:
        xbmcplugin.addSortMethod(HANDLE, sort)
    xbmcplugin.endOfDirectory(HANDLE, cacheToDisc=True)


# =========================================================================
# MAIN MENU
# =========================================================================

def main_menu():
    add_dir('[COLOR lime]סרטים[/COLOR] / Movies', 'movies_menu', poster='DefaultMovies.png')
    add_dir('[COLOR lime]סדרות[/COLOR] / TV Shows', 'shows_menu', poster='DefaultTVShows.png')
    
    if trakt.is_authorized():
        add_dir('[COLOR cyan]המשך צפייה[/COLOR] / Up Next', 'trakt_next_up')
        add_dir('[COLOR cyan]רשימת צפייה[/COLOR] / My Watchlist', 'trakt_watchlist_menu')
        add_dir('[COLOR cyan]היסטוריה[/COLOR] / Watch Progress', 'trakt_progress')
    
    add_dir('[COLOR yellow]חיפוש[/COLOR] / Search', 'search')
    add_dir('שחקנים / Popular People', 'people_popular')
    add_dir('[COLOR orange]כלים[/COLOR] / Tools', 'tools_menu')
    end_dir(content='')


# =========================================================================
# MOVIES
# =========================================================================

def movies_menu():
    add_dir('טרנדינג / Trending', 'movies_trending')
    add_dir('פופולרי / Popular', 'movies_popular')
    add_dir('מדורג / Top Rated', 'movies_top_rated')
    add_dir('בקולנוע / Now Playing', 'movies_now_playing')
    add_dir('בקרוב / Upcoming', 'movies_upcoming')
    add_dir('ז\'אנרים / Genres', 'movies_genres')
    add_dir('חיפוש / Search Movies', 'movies_search')
    end_dir(content='')


def list_movies(func, page=1, **kwargs):
    items, total_pages = func(page=page, **kwargs)
    for m in items:
        add_item(m, action='movie_sources', is_folder=True)
    if page < total_pages:
        add_dir('[COLOR yellow]עמוד הבא >[/COLOR]', kwargs.get('list_action', 'movies_trending'),
                page=str(page + 1), **{k: v for k, v in kwargs.items() if k != 'list_action'})
    end_dir(content='movies')


def movies_genres():
    genres = tmdb.movie_genres()
    for g in genres:
        add_dir(g['name'], 'movies_genre', genre_id=str(g['id']))
    end_dir(content='')


# =========================================================================
# TV SHOWS
# =========================================================================

def shows_menu():
    add_dir('טרנדינג / Trending', 'shows_trending')
    add_dir('פופולרי / Popular', 'shows_popular')
    add_dir('מדורג / Top Rated', 'shows_top_rated')
    add_dir('משודר היום / Airing Today', 'shows_airing_today')
    add_dir('ז\'אנרים / Genres', 'shows_genres')
    add_dir('חיפוש / Search Shows', 'shows_search')
    end_dir(content='')


def list_shows(func, page=1, **kwargs):
    items, total_pages = func(page=page, **kwargs)
    for s in items:
        add_item(s, action='show_seasons', is_folder=True)
    if page < total_pages:
        add_dir('[COLOR yellow]עמוד הבא >[/COLOR]', kwargs.get('list_action', 'shows_trending'),
                page=str(page + 1))
    end_dir(content='tvshows')


def show_seasons(tmdb_id):
    details = tmdb.show_details(tmdb_id)
    if not details:
        notification('Show not found')
        return
    for s in details.get('seasons_data', []):
        label = '{} ({} episodes)'.format(s['name'], s['episode_count'])
        add_dir(label, 'show_episodes', tmdb_id=str(tmdb_id),
                season=str(s['season_number']),
                poster=s.get('poster', details.get('poster', '')),
                fanart=details.get('fanart', ''))
    end_dir(content='seasons')


def show_episodes(tmdb_id, season):
    episodes = tmdb.season_episodes(tmdb_id, int(season))
    details = tmdb.show_details(tmdb_id)
    imdb_id = details.get('imdb_id', '') if details else ''
    
    for ep in episodes:
        meta = {
            'title': 'S{:02d}E{:02d} - {}'.format(ep['season_number'], ep['episode_number'], ep['title']),
            'plot': ep.get('plot', ''),
            'rating': ep.get('rating', 0),
            'still': ep.get('still', ''),
            'poster': details.get('poster', '') if details else '',
            'fanart': details.get('fanart', '') if details else '',
            'imdb_id': imdb_id,
            'tmdb_id': tmdb_id,
            'media_type': 'episode',
            'season_number': ep['season_number'],
            'episode_number': ep['episode_number'],
        }
        add_item(meta, action='episode_sources', is_folder=True)
    end_dir(content='episodes')


def shows_genres():
    genres = tmdb.tv_genres()
    for g in genres:
        add_dir(g['name'], 'shows_genre', genre_id=str(g['id']))
    end_dir(content='')


# =========================================================================
# SOURCE SELECTION & PLAYBACK
# =========================================================================

def source_selection(imdb_id, tmdb_id='', title='', year='',
                     season=None, episode=None, media_type='movie',
                     poster='', fanart='', auto_play=False):
    """
    The core flow: scrape → RD check → HebSubScout → filter → display/autoplay.
    """
    # First-run check: make sure API keys are configured
    if not _check_setup():
        return
    
    # Get IMDB ID if we only have TMDB
    if not imdb_id and tmdb_id:
        if media_type == 'movie':
            details = tmdb.movie_details(tmdb_id)
        else:
            details = tmdb.show_details(tmdb_id)
        if details:
            imdb_id = details.get('imdb_id', '')
    
    if not imdb_id:
        notification('IMDB ID not found')
        return
    
    # Progress dialog
    progress = progress_dialog('HebScout', 'מחפש מקורות...')
    
    def on_progress(pct, msg):
        if not progress.iscanceled():
            progress.update(pct, msg)
    
    sources = get_sources(
        imdb_id=imdb_id, tmdb_id=tmdb_id, title=title, year=year,
        season=int(season) if season else None,
        episode=int(episode) if episode else None,
        progress_callback=on_progress
    )
    
    progress.close()
    
    if not sources:
        notification('לא נמצאו מקורות / No sources found')
        return
    
    # Auto-play: pick first RD-cached source with best Hebrew sub match
    should_auto = auto_play or get_setting('auto_play') == 'true'
    
    if should_auto:
        best = None
        for s in sources:
            if s.get('rd_cached'):
                if best is None or s.get('best_match_pct', 0) > best.get('best_match_pct', 0):
                    best = s
        if not best:
            best = sources[0]
        _play_source(best, imdb_id, tmdb_id, title, year, season, episode, media_type, poster, fanart)
        return
    
    # --- SOURCE FILTERS ---
    filtered = _apply_source_filters(sources)
    if filtered is None:
        return  # User cancelled
    
    # Manual selection
    labels = [build_source_label(s) for s in filtered]
    choice = select_dialog('בחר מקור / Select Source ({})'.format(len(filtered)), labels)
    
    if choice < 0:
        return
    
    _play_source(filtered[choice], imdb_id, tmdb_id, title, year, season, episode,
                 media_type, poster, fanart)


def _apply_source_filters(sources):
    """
    Show filter options above the source list.
    Returns filtered list, or None if user cancels.
    """
    while True:
        # Build filter summary
        total = len(sources)
        q_counts = {}
        for s in sources:
            q = s.get('quality', 'SD')
            q_counts[q] = q_counts.get(q, 0) + 1
        
        cached_count = sum(1 for s in sources if s.get('rd_cached'))
        subs_100 = sum(1 for s in sources if s.get('best_match_pct', 0) >= 95)
        subs_70 = sum(1 for s in sources if s.get('best_match_pct', 0) >= 70)
        subs_any = sum(1 for s in sources if s.get('has_hebrew_subs'))
        
        options = [
            '[COLOR lime]▶ הצג הכל ({} מקורות)[/COLOR]'.format(total),
        ]
        
        # Quality filters
        for q in ['4K', '1080p', '720p', '480p', 'SD']:
            if q_counts.get(q, 0) > 0:
                options.append('[COLOR cyan]איכות: {}[/COLOR] ({})'.format(q, q_counts[q]))
        
        # RD filter
        if cached_count > 0:
            options.append('[COLOR cyan]RD Cached בלבד[/COLOR] ({})'.format(cached_count))
        
        # Hebrew subtitle filters
        if subs_100 > 0:
            options.append('[COLOR lime]עב 100% / כתוביות מובנות[/COLOR] ({})'.format(subs_100))
        if subs_70 > 0:
            options.append('[COLOR yellow]עב 70%+ התאמה[/COLOR] ({})'.format(subs_70))
        if subs_any > 0:
            options.append('[COLOR orange]עב כלשהי[/COLOR] ({})'.format(subs_any))
        
        choice = select_dialog('סינון מקורות / Filter Sources', options)
        
        if choice < 0:
            return None  # Cancelled
        
        if choice == 0:
            return sources  # Show all
        
        # Parse the filter choice
        label = options[choice]
        
        # Quality filters
        for q in ['4K', '1080p', '720p', '480p', 'SD']:
            if 'איכות: {}'.format(q) in label:
                return [s for s in sources if s.get('quality') == q]
        
        # RD cached
        if 'RD Cached' in label:
            return [s for s in sources if s.get('rd_cached')]
        
        # Sub filters
        if '100%' in label or 'מובנות' in label:
            return [s for s in sources if s.get('best_match_pct', 0) >= 95]
        if '70%' in label:
            return [s for s in sources if s.get('best_match_pct', 0) >= 70]
        if 'עב כלשהי' in label:
            return [s for s in sources if s.get('has_hebrew_subs')]
        
        return sources  # Fallback: show all


# =========================================================================
# FIRST-RUN SETUP
# =========================================================================

def _check_setup():
    """
    Check if required API keys are configured.
    If not, walk the user through first-time setup.
    Returns True if ready to use, False if user cancelled.
    """
    from resources.lib.modules.utils import TMDB_KEY
    
    missing = []
    if not TMDB_KEY:
        missing.append('TMDB API Key')
    if not rd.is_authorized():
        missing.append('Real Debrid')
    
    if not missing:
        return True
    
    # First-run dialog
    if not TMDB_KEY:
        result = xbmcgui.Dialog().yesno(
            'HebScout - הגדרה ראשונה',
            'נדרש TMDB API Key כדי לדפדף סרטים וסדרות.\n\n'
            'הירשם בחינם ב-themoviedb.org/settings/api\n'
            'וקבל את המפתח שלך.',
            yeslabel='הכנס מפתח',
            nolabel='מאוחר יותר'
        )
        if result:
            key = input_dialog('TMDB API Key')
            if key:
                from resources.lib.modules.utils import ADDON as _a, set_setting
                set_setting('tmdb_api_key', key.strip())
                notification('TMDB API Key saved!')
                # Reload
                import importlib
                from resources.lib.modules import utils
                importlib.reload(utils)
            else:
                return False
        else:
            return False
    
    if not rd.is_authorized():
        result = xbmcgui.Dialog().yesno(
            'HebScout - הגדרה ראשונה',
            'חיבור Real Debrid נדרש להפעלת מקורות.\n\n'
            'יש לך חשבון Real Debrid?',
            yeslabel='חבר עכשיו',
            nolabel='מאוחר יותר'
        )
        if result:
            rd.authorize()
    
    # Trakt is optional - offer but don't require
    if not trakt.is_authorized():
        result = xbmcgui.Dialog().yesno(
            'HebScout - Trakt (אופציונלי)',
            'רוצה לחבר Trakt?\n'
            'זה מאפשר מעקב התקדמות, רשימות צפייה, ועוד.\n\n'
            'תצטרך ליצור אפליקציה ב-trakt.tv/oauth/applications\n'
            'ולקבל Client ID + Client Secret.',
            yeslabel='הגדר Trakt',
            nolabel='דלג'
        )
        if result:
            # Get client ID
            client_id = input_dialog('Trakt Client ID')
            if client_id:
                set_setting('trakt_client_id', client_id.strip())
                client_secret = input_dialog('Trakt Client Secret')
                if client_secret:
                    set_setting('trakt_client_secret', client_secret.strip())
                    trakt.authorize()
    
    return True


def _play_source(source, imdb_id, tmdb_id, title, year, season, episode,
                 media_type, poster, fanart):
    """Resolve and play a selected source."""
    progress = progress_dialog('HebScout', 'מחבר למקור...')
    progress.update(30)
    
    url = resolve_source(source)
    progress.close()
    
    if not url:
        notification('Failed to resolve source')
        return
    
    # Build next episode info for TV
    next_ep_info = None
    resolve_func = None
    if media_type != 'movie' and season and episode:
        next_ep_info = _get_next_episode_info(tmdb_id, int(season), int(episode))
        resolve_func = _resolve_next_episode
    
    # Play with subtitle matches from HebSubScout enrichment
    global _player
    _player = HebScoutPlayer()
    _player.play_source(url, {
        'media_type': media_type,
        'imdb_id': imdb_id,
        'tmdb_id': tmdb_id,
        'title': title,
        'year': year,
        'season': int(season) if season else None,
        'episode': int(episode) if episode else None,
        'poster': poster,
        'fanart': fanart,
        'source_name': source.get('name', ''),
        'sub_matches': source.get('all_matches', []),  # Pass subtitle matches to player
    }, next_ep_info, resolve_func)


def _get_next_episode_info(tmdb_id, current_season, current_episode):
    """Figure out the next episode."""
    episodes = tmdb.season_episodes(tmdb_id, current_season)
    next_ep = current_episode + 1
    for ep in episodes:
        if ep['episode_number'] == next_ep:
            return {
                'season': current_season,
                'episode': next_ep,
                'title': ep.get('title', ''),
                'has_next': True,
            }
    # Try next season
    details = tmdb.show_details(tmdb_id)
    if details:
        for s in details.get('seasons_data', []):
            if s['season_number'] == current_season + 1 and s['episode_count'] > 0:
                return {
                    'season': current_season + 1,
                    'episode': 1,
                    'title': 'Season {} Episode 1'.format(current_season + 1),
                    'has_next': True,
                }
    return None


def _resolve_next_episode(imdb_id, season, episode):
    """Quick resolve for auto-play next episode."""
    sources = get_sources(imdb_id=imdb_id, season=season, episode=episode)
    for s in sources:
        if s.get('rd_cached'):
            url = resolve_source(s)
            if url:
                return url
    if sources:
        return resolve_source(sources[0])
    return None


# =========================================================================
# TRAKT SECTIONS
# =========================================================================

def trakt_next_up():
    """Show next unwatched episodes for shows in progress."""
    next_eps = trakt.get_next_episodes()
    for item in next_eps:
        show = item['show']
        meta = {
            'title': '{} - S{:02d}E{:02d} {}'.format(
                show.get('title', ''), item['season'], item['episode'], item.get('title', '')),
            'imdb_id': item.get('imdb_id', ''),
            'media_type': 'episode',
            'season_number': item['season'],
            'episode_number': item['episode'],
        }
        add_item(meta, action='episode_sources', is_folder=True)
    end_dir(content='episodes')


def trakt_watchlist_menu():
    add_dir('סרטים / Movies', 'trakt_watchlist_movies')
    add_dir('סדרות / Shows', 'trakt_watchlist_shows')
    end_dir(content='')


def trakt_watchlist_movies():
    items = trakt.watchlist_movies()
    for item in items:
        movie = item.get('movie', {})
        ids = movie.get('ids', {})
        meta = {
            'title': movie.get('title', ''),
            'year': str(movie.get('year', '')),
            'imdb_id': ids.get('imdb', ''),
            'tmdb_id': ids.get('tmdb', ''),
            'media_type': 'movie',
        }
        add_item(meta, action='movie_sources', is_folder=True)
    end_dir(content='movies')


def trakt_watchlist_shows():
    items = trakt.watchlist_shows()
    for item in items:
        show = item.get('show', {})
        ids = show.get('ids', {})
        meta = {
            'title': show.get('title', ''),
            'year': str(show.get('year', '')),
            'imdb_id': ids.get('imdb', ''),
            'tmdb_id': ids.get('tmdb', ''),
            'media_type': 'tv',
        }
        add_item(meta, action='show_seasons', is_folder=True)
    end_dir(content='tvshows')


def trakt_progress():
    """Show in-progress items (resume points)."""
    items = trakt.playback_progress()
    for item in items:
        media_type = item.get('type', '')
        progress_pct = item.get('progress', 0)
        if media_type == 'movie':
            movie = item.get('movie', {})
            ids = movie.get('ids', {})
            label = '{} [COLOR yellow]{:.0f}%[/COLOR]'.format(movie.get('title', ''), progress_pct)
            meta = {'title': label, 'imdb_id': ids.get('imdb', ''),
                    'tmdb_id': ids.get('tmdb', ''), 'media_type': 'movie'}
            add_item(meta, action='movie_sources', is_folder=True)
        elif media_type == 'episode':
            show = item.get('show', {})
            ep = item.get('episode', {})
            ids = show.get('ids', {})
            label = '{} S{:02d}E{:02d} [COLOR yellow]{:.0f}%[/COLOR]'.format(
                show.get('title', ''), ep.get('season', 0), ep.get('number', 0), progress_pct)
            meta = {'title': label, 'imdb_id': ids.get('imdb', ''),
                    'tmdb_id': ids.get('tmdb', ''), 'media_type': 'tv',
                    'season_number': ep.get('season', 0), 'episode_number': ep.get('number', 0)}
            add_item(meta, action='episode_sources', is_folder=True)
    end_dir(content='videos')


# =========================================================================
# SEARCH
# =========================================================================

def search():
    query = input_dialog('חיפוש / Search')
    if not query:
        return
    add_dir('[COLOR lime]סרטים / Movies[/COLOR]', 'movies_search_results', query=query)
    add_dir('[COLOR lime]סדרות / TV Shows[/COLOR]', 'shows_search_results', query=query)
    end_dir(content='')


# =========================================================================
# TOOLS
# =========================================================================

def tools_menu():
    # Account status
    rd_status = '[COLOR lime]Connected[/COLOR]' if rd.is_authorized() else '[COLOR red]Not Connected[/COLOR]'
    trakt_status = '[COLOR lime]Connected[/COLOR]' if trakt.is_authorized() else '[COLOR red]Not Connected[/COLOR]'
    
    add_dir('Real Debrid: {}'.format(rd_status), 'rd_auth')
    add_dir('Trakt: {}'.format(trakt_status), 'trakt_auth')
    add_dir('נקה מטמון / Clear Cache', 'clear_cache')
    add_dir('הגדרות / Settings', 'settings')
    end_dir(content='')


# =========================================================================
# ROUTER
# =========================================================================

def router(params):
    action = params.get('action', '')
    page = int(params.get('page', 1))
    tmdb_id = params.get('tmdb_id', '')
    imdb_id = params.get('imdb_id', '')
    media_type = params.get('media_type', 'movie')
    title = params.get('title', '')
    year = params.get('year', '')
    season = params.get('season')
    episode = params.get('episode')
    poster = params.get('poster', '')
    fanart = params.get('fanart', '')
    query = params.get('query', '')
    genre_id = params.get('genre_id', '')

    # Main
    if not action:
        main_menu()
    
    # Movies
    elif action == 'movies_menu':
        movies_menu()
    elif action == 'movies_trending':
        list_movies(tmdb.movies_trending, page, list_action='movies_trending')
    elif action == 'movies_popular':
        list_movies(tmdb.movies_popular, page, list_action='movies_popular')
    elif action == 'movies_top_rated':
        list_movies(tmdb.movies_top_rated, page, list_action='movies_top_rated')
    elif action == 'movies_now_playing':
        list_movies(tmdb.movies_now_playing, page, list_action='movies_now_playing')
    elif action == 'movies_upcoming':
        list_movies(tmdb.movies_upcoming, page, list_action='movies_upcoming')
    elif action == 'movies_genres':
        movies_genres()
    elif action == 'movies_genre':
        list_movies(tmdb.movies_genre, page, genre_id=int(genre_id), list_action='movies_genre')
    elif action == 'movies_search':
        query = input_dialog('חפש סרט / Search Movie')
        if query:
            list_movies(tmdb.movies_search, page, query=query, list_action='movies_search')
    elif action == 'movies_search_results':
        list_movies(tmdb.movies_search, page, query=query, list_action='movies_search_results')
    elif action == 'movie_sources':
        source_selection(imdb_id, tmdb_id, title, year, media_type='movie', poster=poster, fanart=fanart)
    
    # TV Shows
    elif action == 'shows_menu':
        shows_menu()
    elif action == 'shows_trending':
        list_shows(tmdb.shows_trending, page, list_action='shows_trending')
    elif action == 'shows_popular':
        list_shows(tmdb.shows_popular, page, list_action='shows_popular')
    elif action == 'shows_top_rated':
        list_shows(tmdb.shows_top_rated, page, list_action='shows_top_rated')
    elif action == 'shows_airing_today':
        list_shows(tmdb.shows_airing_today, page, list_action='shows_airing_today')
    elif action == 'shows_genres':
        shows_genres()
    elif action == 'shows_genre':
        list_shows(tmdb.shows_genre, page, genre_id=int(genre_id), list_action='shows_genre')
    elif action == 'shows_search':
        query = input_dialog('חפש סדרה / Search Show')
        if query:
            list_shows(tmdb.shows_search, page, query=query, list_action='shows_search')
    elif action == 'shows_search_results':
        list_shows(tmdb.shows_search, page, query=query, list_action='shows_search_results')
    elif action == 'show_seasons':
        show_seasons(tmdb_id)
    elif action == 'show_episodes':
        show_episodes(tmdb_id, season)
    elif action == 'episode_sources':
        source_selection(imdb_id, tmdb_id, title, year, season=season, episode=episode,
                         media_type='tv', poster=poster, fanart=fanart)
    
    # Search
    elif action == 'search':
        search()
    
    # People
    elif action == 'people_popular':
        people, _ = tmdb.people_popular(page)
        for p in people:
            add_dir(p['name'], 'person_credits', poster=p.get('photo', ''),
                    tmdb_id=str(p['id']))
        end_dir(content='artists')
    elif action == 'person_credits':
        movies, shows = tmdb.person_credits(tmdb_id)
        for m in movies[:20]:
            add_item(m, action='movie_sources', is_folder=True)
        for s in shows[:20]:
            add_item(s, action='show_seasons', is_folder=True)
        end_dir(content='videos')
    
    # Trakt
    elif action == 'trakt_next_up':
        trakt_next_up()
    elif action == 'trakt_watchlist_menu':
        trakt_watchlist_menu()
    elif action == 'trakt_watchlist_movies':
        trakt_watchlist_movies()
    elif action == 'trakt_watchlist_shows':
        trakt_watchlist_shows()
    elif action == 'trakt_progress':
        trakt_progress()
    elif action == 'trakt_watchlist_add':
        trakt.add_to_watchlist(media_type, imdb_id)
        notification('Added to Trakt Watchlist')
    
    # Tools
    elif action == 'tools_menu':
        tools_menu()
    elif action == 'rd_auth':
        if rd.is_authorized():
            if yesno_dialog('Real Debrid', 'Disconnect Real Debrid?'):
                rd.revoke()
        else:
            rd.authorize()
    elif action == 'trakt_auth':
        if trakt.is_authorized():
            if yesno_dialog('Trakt', 'Disconnect Trakt?'):
                trakt.revoke()
        else:
            trakt.authorize()
    elif action == 'clear_cache':
        cache_clear()
        notification('Cache cleared')
    elif action == 'settings':
        ADDON.openSettings()
    
    # Direct play
    elif action == 'play':
        source_selection(imdb_id, tmdb_id, title, year, season=season, episode=episode,
                         media_type=media_type, poster=poster, fanart=fanart, auto_play=True)
    
    # Subtitle picker (called during playback)
    elif action == 'subtitle_picker':
        if _player and _player._playing:
            _player.show_subtitle_picker()
        else:
            notification('לא מתנגן כרגע / Not playing')


if __name__ == '__main__':
    params = dict(parse_qsl(sys.argv[2].lstrip('?')))
    router(params)
