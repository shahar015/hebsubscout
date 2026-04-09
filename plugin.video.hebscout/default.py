# -*- coding: utf-8 -*-
"""
HebScout - Main Entry Point
============================
Full-featured video addon with native HebSubScout integration.
"""

import sys
import json

from urllib.parse import urlencode, parse_qsl, quote_plus

import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

# Add our lib to path
sys.path.insert(0, xbmcaddon.Addon().getAddonInfo('path') + '/resources/lib')

# Lightweight imports only — heavy modules loaded lazily on first use
from resources.lib.modules.utils import (
    log, notification, ADDON, ADDON_NAME, ADDON_FANART,
    progress_dialog, input_dialog, select_dialog, yesno_dialog,
    get_setting, set_setting, t, is_hebrew
)
from resources.lib.modules.cache import is_watched, cache_clear, get_continue_watching, get_watch_history, get_bookmark

# Lazy module references — imported on first access
_tmdb = _rd = _trakt = _sources = _player = None


def _get_tmdb():
    global _tmdb
    if _tmdb is None:
        from resources.lib.modules import tmdb
        _tmdb = tmdb
    return _tmdb


def _get_rd():
    global _rd
    if _rd is None:
        from resources.lib.modules import realdebrid
        _rd = realdebrid
    return _rd


def _get_trakt():
    global _trakt
    if _trakt is None:
        from resources.lib.modules import trakt_api
        _trakt = trakt_api
    return _trakt


def _get_sources_module():
    global _sources
    if _sources is None:
        from resources.lib.modules import sources
        _sources = sources
    return _sources


def _get_player_class():
    global _player
    if _player is None:
        from resources.lib.modules.player import HebScoutPlayer
        _player = HebScoutPlayer
    return _player

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
        li.getVideoInfoTag().setPlot(plot)
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
    
    # Watched overlay + progress bar
    imdb = meta.get('imdb_id', '')
    season = meta.get('season_number', 0)
    episode = meta.get('episode_number', 0)
    if imdb and is_watched(imdb, season, episode):
        info_tag.setPlaycount(1)
    elif imdb:
        bm = get_bookmark(imdb, season, episode)
        if bm and bm.get('progress', 0) > 1:
            # Both methods for maximum compatibility across Estuary views
            info_tag.setResumePoint(float(bm['progress']), 100.0)
            li.setProperty('percentplayed', str(int(bm['progress'])))

    # Context menu — inline items directly in Kodi's right-click menu
    cm = context_items or []
    if imdb:
        cm.append(('בדוק כתוביות', 'RunPlugin({})'.format(
            url_for(action='check_subs', imdb_id=imdb, season=season, episode=episode, title=meta.get('title', '')))))
    if imdb and _get_trakt().is_authorized():
        cm.append((t('trakt_watchlist_add'), 'RunPlugin({})'.format(
            url_for(action='trakt_watchlist_add', imdb_id=imdb, media_type=media_type))))
    if imdb:
        cm.append(('סמן כנצפה', 'RunPlugin({})'.format(
            url_for(action='mark_watched', imdb_id=imdb, season=season, episode=episode, media_type=media_type))))
    tmdb_id_val = meta.get('tmdb_id', '')
    if tmdb_id_val:
        sim_action = 'movie_similar' if media_type == 'movie' else 'show_similar'
        cm.append(('כותרים דומים', 'Container.Update({})'.format(
            url_for(action=sim_action, tmdb_id=tmdb_id_val))))
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
    add_dir('[COLOR lime]{}[/COLOR]'.format(t('movies')), 'movies_menu', poster='DefaultMovies.png')
    add_dir('[COLOR lime]{}[/COLOR]'.format(t('tv_shows')), 'shows_menu', poster='DefaultTVShows.png')

    # Single continue watching & history (Trakt-first, local fallback)
    add_dir('[COLOR cyan]{}[/COLOR]'.format(t('continue_watching')), 'continue_watching')
    add_dir('[COLOR cyan]{}[/COLOR]'.format(t('watch_history')), 'watch_history')

    if _get_trakt().is_authorized():
        add_dir('[COLOR cyan]{}[/COLOR]'.format(t('up_next')), 'trakt_next_up')
        add_dir('[COLOR cyan]{}[/COLOR]'.format(t('my_watchlist')), 'trakt_watchlist_menu')

    add_dir('[COLOR yellow]{}[/COLOR]'.format(t('search')), 'search')
    add_dir(t('popular_people'), 'people_popular')
    add_dir('[COLOR orange]{}[/COLOR]'.format(t('tools')), 'tools_menu')
    end_dir(content='')


# =========================================================================
# MOVIES
# =========================================================================

def movies_menu():
    add_dir(t('trending'), 'movies_trending')
    add_dir(t('popular'), 'movies_popular')
    add_dir(t('top_rated'), 'movies_top_rated')
    add_dir(t('now_playing'), 'movies_now_playing')
    add_dir(t('upcoming'), 'movies_upcoming')
    add_dir(t('genres'), 'movies_genres')
    add_dir(t('search_movies'), 'movies_search')
    end_dir(content='')


def _list_items(func, item_action, content, page=1, **kwargs):
    """Generic list function for movies and shows."""
    list_action = kwargs.pop('list_action', '')
    items, total_pages = func(page=page, **kwargs)
    for item in items:
        add_item(item, action=item_action, is_folder=True)
    if page < total_pages and list_action:
        add_dir('[COLOR yellow]{}[/COLOR]'.format(t('next_page')), list_action,
                page=str(page + 1), **kwargs)
    end_dir(content=content)


def list_movies(func, page=1, **kwargs):
    kwargs.setdefault('list_action', 'movies_trending')
    _list_items(func, 'movie_sources', 'movies', page, **kwargs)


def movies_genres():
    genres = _get_tmdb().movie_genres()
    for g in genres:
        add_dir(g['name'], 'movies_genre', genre_id=str(g['id']))
    end_dir(content='')


# =========================================================================
# TV SHOWS
# =========================================================================

def shows_menu():
    add_dir(t('trending'), 'shows_trending')
    add_dir(t('popular'), 'shows_popular')
    add_dir(t('top_rated'), 'shows_top_rated')
    add_dir(t('airing_today'), 'shows_airing_today')
    add_dir(t('genres'), 'shows_genres')
    add_dir(t('search_shows'), 'shows_search')
    end_dir(content='')


def list_shows(func, page=1, **kwargs):
    kwargs.setdefault('list_action', 'shows_trending')
    _list_items(func, 'show_seasons', 'tvshows', page, **kwargs)


def show_seasons(tmdb_id):
    details = _get_tmdb().show_details(tmdb_id)
    if not details:
        notification(t('show_not_found'))
        return
    for s in details.get('seasons_data', []):
        label = t('season_label', s['name'], s['episode_count'])
        add_dir(label, 'show_episodes', tmdb_id=str(tmdb_id),
                season=str(s['season_number']),
                poster=s.get('poster', details.get('poster', '')),
                fanart=details.get('fanart', ''))
    end_dir(content='seasons')


def show_episodes(tmdb_id, season):
    episodes = _get_tmdb().season_episodes(tmdb_id, int(season))
    details = _get_tmdb().show_details(tmdb_id)
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
    genres = _get_tmdb().tv_genres()
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

    # Fetch full TMDB details for the info panel
    details = None
    if tmdb_id:
        if media_type == 'movie':
            details = _get_tmdb().movie_details(tmdb_id)
        else:
            details = _get_tmdb().show_details(tmdb_id)
        if details and not imdb_id:
            imdb_id = details.get('imdb_id', '')
    elif imdb_id and not tmdb_id:
        # We have IMDB but no TMDB — can't fetch details easily, use what we have
        pass

    if not imdb_id:
        notification(t('imdb_not_found'))
        return

    # Build metadata for the source selection screen
    metadata = {
        'title': title, 'year': year, 'poster': poster, 'fanart': fanart,
        'media_type': media_type,
    }
    if details:
        metadata.update({
            'title': details.get('title', title),
            'year': details.get('year', year),
            'poster': details.get('poster', poster),
            'fanart': details.get('fanart', fanart),
            'plot': details.get('plot', ''),
            'rating': details.get('rating', 0),
            'genres': details.get('genres', []),
            'cast': details.get('cast', []),
            'director': details.get('director', ''),
            'tagline': details.get('tagline', ''),
        })

    # Progress dialog
    progress = progress_dialog('HebScout', t('searching_sources'))

    def on_progress(pct, msg):
        if not progress.iscanceled():
            progress.update(pct, msg)

    sources = _get_sources_module().get_sources(
        imdb_id=imdb_id, tmdb_id=tmdb_id, title=title, year=year,
        season=int(season) if season else None,
        episode=int(episode) if episode else None,
        progress_callback=on_progress
    )

    progress.close()

    if not sources:
        notification(t('no_sources_found'))
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

    # Custom source selection screen (RTL/LTR XML based on language)
    from resources.lib.modules.source_select import SourceSelectDialog
    addon_path = xbmcaddon.Addon().getAddonInfo('path')
    xml_file = 'source_select_rtl.xml' if is_hebrew() else 'source_select_ltr.xml'
    dialog = SourceSelectDialog(xml_file, addon_path, sources, metadata)
    dialog.doModal()
    chosen = dialog.selected_source
    del dialog

    if not chosen:
        return

    _play_source(chosen, imdb_id, tmdb_id, title, year, season, episode,
                 media_type, poster, fanart)


# =========================================================================
# FIRST-RUN SETUP
# =========================================================================

def _check_setup():
    """
    Check if required services are connected.
    If not, walk the user through first-time setup.
    TMDB and Trakt keys are built into the addon - users only authorize accounts.
    """
    if _get_rd().is_authorized():
        return True
    
    # First-run: need Real Debrid
    result = xbmcgui.Dialog().yesno(
        t('first_run_title'),
        t('first_run_welcome'),
        yeslabel=t('connect_now'),
        nolabel=t('later')
    )
    if result:
        _get_rd().authorize()
    else:
        return False

    # Offer Trakt (optional)
    if not _get_trakt().is_authorized():
        result = xbmcgui.Dialog().yesno(
            t('trakt_optional_title'),
            t('trakt_optional_msg'),
            yeslabel=t('connect_trakt'),
            nolabel=t('skip')
        )
        if result:
            _get_trakt().authorize()

    # Offer Ktuvit (optional) — extra Hebrew subtitle source
    if not get_setting('ktuvit_email'):
        result = xbmcgui.Dialog().yesno(
            t('ktuvit_optional_title'),
            t('ktuvit_optional_msg'),
            yeslabel=t('ktuvit_connect'),
            nolabel=t('skip')
        )
        if result:
            email = xbmcgui.Dialog().input(t('ktuvit_email_prompt'))
            if email:
                password = xbmcgui.Dialog().input(
                    t('ktuvit_password_prompt'),
                    option=xbmcgui.ALPHANUM_HIDE_INPUT
                )
                if password:
                    import hashlib
                    hashed = hashlib.sha256(password.encode('utf-8')).hexdigest()
                    set_setting('ktuvit_email', email)
                    set_setting('ktuvit_password', hashed)
                    notification(t('ktuvit_saved'))

    return _get_rd().is_authorized()


def _play_source(source, imdb_id, tmdb_id, title, year, season, episode,
                 media_type, poster, fanart):
    """Resolve and play a selected source."""
    progress = progress_dialog('HebScout', t('connecting_source'))
    progress.update(30)

    url = _get_sources_module().resolve_source(source)
    progress.close()

    if not url:
        notification(t('failed_resolve'))
        return

    # Build next episode info for TV
    next_ep_info = None
    resolve_func = None
    if media_type != 'movie' and season and episode:
        next_ep_info = _get_next_episode_info(tmdb_id, int(season), int(episode))
        resolve_func = _resolve_next_episode

    # Tell Kodi the directory listing is done BEFORE we start the wait loop.
    # Without this, Kodi shows a loading spinner while we wait for playback.
    xbmcplugin.endOfDirectory(HANDLE, succeeded=False)

    # Play with subtitle matches from HebSubScout enrichment
    global _player
    _player = _get_player_class()()
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
        'sub_matches': source.get('all_matches', []),
    }, next_ep_info, resolve_func)

    # Keep the script alive so player callbacks (onAVStarted, onPlayBackStopped, etc.)
    # can fire. Without this, the Python interpreter exits and the player object is
    # garbage collected, killing all callbacks (subtitle auto-download, progress tracking,
    # Trakt scrobbling, OSD overlay, etc.).
    monitor = xbmc.Monitor()
    # Wait for playback to actually start (up to 30s)
    for _ in range(60):
        if _player._playing or monitor.abortRequested():
            break
        xbmc.sleep(500)
    # Stay alive while playing
    while not monitor.abortRequested():
        if not _player or not _player._playing:
            break
        xbmc.sleep(1000)


def _get_next_episode_info(tmdb_id, current_season, current_episode):
    """Figure out the next episode."""
    episodes = _get_tmdb().season_episodes(tmdb_id, current_season)
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
    details = _get_tmdb().show_details(tmdb_id)
    if details:
        for s in details.get('seasons_data', []):
            if s['season_number'] == current_season + 1 and s['episode_count'] > 0:
                return {
                    'season': current_season + 1,
                    'episode': 1,
                    'title': t('next_season_ep', current_season + 1),
                    'has_next': True,
                }
    return None


def _resolve_next_episode(imdb_id, season, episode):
    """Quick resolve for auto-play next episode."""
    sources = _get_sources_module().get_sources(imdb_id=imdb_id, season=season, episode=episode)
    for s in sources:
        if s.get('rd_cached'):
            url = _get_sources_module().resolve_source(s)
            if url:
                return url
    if sources:
        return _get_sources_module().resolve_source(sources[0])
    return None


# =========================================================================
# CONTINUE WATCHING / HISTORY (Trakt-first, local SQLite fallback)
# =========================================================================

def continue_watching():
    """Show in-progress items. Uses Trakt when connected, local SQLite otherwise."""
    if _get_trakt().is_authorized():
        _continue_watching_trakt()
    else:
        _continue_watching_local()


def _continue_watching_trakt():
    """Pull resume points from Trakt sync/playback."""
    items = _get_trakt().playback_progress()
    if not items:
        notification(t('no_sources'))
        end_dir()
        return
    for item in items:
        media_type = item.get('type', '')
        progress_pct = item.get('progress', 0)
        if media_type == 'movie':
            movie = item.get('movie', {})
            ids = movie.get('ids', {})
            title = movie.get('title', '')
            label = '{} [COLOR cyan]({:.0f}%)[/COLOR]'.format(title, progress_pct)
            li = xbmcgui.ListItem(label=label)
            params = {'action': 'movie_sources', 'imdb_id': ids.get('imdb', ''),
                      'tmdb_id': str(ids.get('tmdb', '')), 'title': title, 'media_type': 'movie'}
            xbmcplugin.addDirectoryItem(HANDLE, url_for(**params), li, True)
        elif media_type == 'episode':
            show = item.get('show', {})
            ep = item.get('episode', {})
            ids = show.get('ids', {})
            title = show.get('title', '')
            label = '{} S{:02d}E{:02d} [COLOR cyan]({:.0f}%)[/COLOR]'.format(
                title, ep.get('season', 0), ep.get('number', 0), progress_pct)
            li = xbmcgui.ListItem(label=label)
            params = {'action': 'episode_sources', 'imdb_id': ids.get('imdb', ''),
                      'tmdb_id': str(ids.get('tmdb', '')), 'title': title, 'media_type': 'tv',
                      'season': ep.get('season', 0), 'episode': ep.get('number', 0)}
            xbmcplugin.addDirectoryItem(HANDLE, url_for(**params), li, True)
    end_dir(content='videos')


def _continue_watching_local():
    """Fallback: pull resume points from local SQLite bookmarks."""
    items = get_continue_watching()
    if not items:
        notification(t('no_sources'))
        end_dir()
        return
    for item in items:
        title = item.get('title', '')
        progress = int(item.get('progress', 0))
        media_type = item.get('media_type', 'movie')
        action = 'episode_sources' if media_type != 'movie' else 'movie_sources'
        display_label = '{} [COLOR cyan]({}%)[/COLOR]'.format(title, progress)
        li = xbmcgui.ListItem(label=display_label)
        art = {}
        if item.get('poster'):
            art['poster'] = art['thumb'] = item['poster']
        if item.get('fanart'):
            art['fanart'] = item['fanart']
        li.setArt(art)
        params = {
            'action': action, 'imdb_id': item.get('imdb_id', ''),
            'tmdb_id': item.get('tmdb_id', ''), 'title': title,
            'media_type': media_type, 'poster': item.get('poster', ''),
            'fanart': item.get('fanart', ''),
        }
        if item.get('season'):
            params['season'] = item['season']
        if item.get('episode'):
            params['episode'] = item['episode']
        xbmcplugin.addDirectoryItem(HANDLE, url_for(**params), li, True)
    end_dir()


def watch_history():
    """Show watched items. Uses Trakt when connected, local SQLite otherwise."""
    if _get_trakt().is_authorized():
        _watch_history_trakt()
    else:
        _watch_history_local()


def _watch_history_trakt():
    """Pull watched history from Trakt."""
    movies = _get_trakt().watched_movies() or []
    shows = _get_trakt().watched_shows() or []
    if not movies and not shows:
        notification(t('no_sources'))
        end_dir()
        return
    for item in movies[:25]:
        movie = item.get('movie', {})
        ids = movie.get('ids', {})
        meta = {
            'title': movie.get('title', ''),
            'year': str(movie.get('year', '')),
            'imdb_id': ids.get('imdb', ''),
            'tmdb_id': str(ids.get('tmdb', '')),
            'media_type': 'movie',
        }
        add_item(meta, action='movie_sources', is_folder=True)
    for item in shows[:25]:
        show = item.get('show', {})
        ids = show.get('ids', {})
        meta = {
            'title': show.get('title', ''),
            'year': str(show.get('year', '')),
            'imdb_id': ids.get('imdb', ''),
            'tmdb_id': str(ids.get('tmdb', '')),
            'media_type': 'tv',
        }
        add_item(meta, action='show_seasons', is_folder=True)
    end_dir(content='videos')


def _watch_history_local():
    """Fallback: pull watched history from local SQLite."""
    items = get_watch_history()
    if not items:
        notification(t('no_sources'))
        end_dir()
        return
    for item in items:
        title = item.get('title', '')
        media_type = item.get('media_type', 'movie')
        action = 'episode_sources' if media_type != 'movie' else 'movie_sources'
        meta = {
            'title': title,
            'imdb_id': item.get('imdb_id', ''),
            'tmdb_id': item.get('tmdb_id', ''),
            'poster': item.get('poster', ''),
            'fanart': item.get('fanart', ''),
            'media_type': media_type,
            'season_number': item.get('season', 0),
            'episode_number': item.get('episode', 0),
        }
        add_item(meta, action=action, is_folder=True)
    end_dir()


# =========================================================================
# TRAKT SECTIONS
# =========================================================================

def trakt_next_up():
    """Show next unwatched episodes for shows in progress."""
    next_eps = _get_trakt().get_next_episodes()
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
    add_dir(t('wl_movies'), 'trakt_watchlist_movies')
    add_dir(t('wl_shows'), 'trakt_watchlist_shows')
    end_dir(content='')


def trakt_watchlist_movies():
    items = _get_trakt().watchlist_movies()
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
    items = _get_trakt().watchlist_shows()
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
    items = _get_trakt().playback_progress()
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
    """Search menu: choose movies or TV shows."""
    add_dir('[COLOR lime]{}[/COLOR]'.format(t('search_movies')), 'search_movies')
    add_dir('[COLOR lime]{}[/COLOR]'.format(t('search_shows')), 'search_shows')
    end_dir(content='')


def search_type_menu(media_type):
    """Show new search + history for a specific media type."""
    from resources.lib.modules.cache import get_search_history
    history = get_search_history(media_type)
    add_dir('[COLOR lime]{}[/COLOR]'.format(t('new_search')), 'search_new', media_type=media_type)
    for q in history:
        action = 'movies_search_results' if media_type == 'movie' else 'shows_search_results'
        add_dir('[COLOR gray]{}[/COLOR]'.format(q), action, query=q)
    end_dir(content='')


def search_new_typed(media_type):
    """New search for a specific media type — input, save to history, show results."""
    prompt = t('search_movies_prompt') if media_type == 'movie' else t('search_shows_prompt')
    query = input_dialog(prompt)
    if query:
        from resources.lib.modules.cache import add_search_history
        add_search_history(query, media_type)
        if media_type == 'movie':
            list_movies(_get_tmdb().movies_search, query=query, list_action='movies_search_results')
        else:
            list_shows(_get_tmdb().shows_search, query=query, list_action='shows_search_results')
        return
    end_dir(content='')


# =========================================================================
# TOOLS
# =========================================================================

def tools_menu():
    # ── Accounts ──
    add_dir('[COLOR orange]{}[/COLOR]'.format(t('accounts_header')), 'noop')

    # Real Debrid
    if _get_rd().is_authorized():
        try:
            info = _get_rd().user_info()
            expiry = info.get('expiration', '')[:10] if info else ''
            rd_label = 'Real Debrid: [COLOR lime]{}[/COLOR]'.format(
                t('premium_until', expiry) if expiry else t('connected'))
        except Exception:
            rd_label = 'Real Debrid: [COLOR lime]{}[/COLOR]'.format(t('connected'))
    else:
        rd_label = 'Real Debrid: [COLOR red]{}[/COLOR]'.format(t('not_connected'))
    add_dir(rd_label, 'rd_auth')

    # Trakt
    if _get_trakt().is_authorized():
        try:
            user = _get_trakt().get_user_settings()
            username = user.get('user', {}).get('username', '') if user else ''
            trakt_label = 'Trakt: [COLOR lime]{}[/COLOR]'.format(
                t('user_label', username) if username else t('connected'))
        except Exception:
            trakt_label = 'Trakt: [COLOR lime]{}[/COLOR]'.format(t('connected'))
    else:
        trakt_label = 'Trakt: [COLOR red]{}[/COLOR]'.format(t('not_connected'))
    add_dir(trakt_label, 'trakt_auth')

    # Ktuvit
    ktuvit_email = get_setting('ktuvit_email')
    if ktuvit_email:
        ktuvit_label = 'Ktuvit: [COLOR lime]{}[/COLOR]'.format(ktuvit_email)
    else:
        ktuvit_label = 'Ktuvit: [COLOR red]{}[/COLOR]'.format(t('not_connected'))
    add_dir(ktuvit_label, 'ktuvit_setup')

    # ── Quick Settings ──
    add_dir('[COLOR orange]{}[/COLOR]'.format(t('toggles_header')), 'noop')

    auto_subs = get_setting('auto_subs') != 'false'
    auto_play = get_setting('auto_play') == 'true'
    auto_next = get_setting('auto_next_episode') != 'false'

    add_dir('{}: [COLOR {}]{}[/COLOR]'.format(
        t('auto_subs_toggle'), 'lime' if auto_subs else 'red',
        t('on') if auto_subs else t('off')), 'toggle_setting', key='auto_subs')
    add_dir('{}: [COLOR {}]{}[/COLOR]'.format(
        t('auto_play_toggle'), 'lime' if auto_play else 'red',
        t('on') if auto_play else t('off')), 'toggle_setting', key='auto_play')
    add_dir('{}: [COLOR {}]{}[/COLOR]'.format(
        t('auto_next_toggle'), 'lime' if auto_next else 'red',
        t('on') if auto_next else t('off')), 'toggle_setting', key='auto_next_episode')
    add_dir(t('language_toggle'), 'toggle_setting', key='ui_language')

    # ── System ──
    add_dir('[COLOR orange]{}[/COLOR]'.format(t('system_header')), 'noop')
    add_dir(t('clear_cache'), 'clear_cache')
    add_dir(t('clear_search_history'), 'clear_search_history')
    add_dir(t('settings'), 'settings')
    add_dir('[COLOR gray]{}[/COLOR]'.format(t('version_info', ADDON.getAddonInfo('version'))), 'noop')
    end_dir(content='')


# =========================================================================
# NETFLIX HOME
# =========================================================================

def _show_netflix_home():
    """Show the Netflix-style home screen and handle its result."""
    from resources.lib.modules.netflix_home import show_netflix_home

    while True:
        action, item = show_netflix_home()

        if not action:
            break  # User pressed Back — exit addon

        if action == 'select' and item:
            # Poster clicked — go to source selection
            mt = item.get('media_type', 'movie')
            if mt == 'movie':
                source_selection(
                    item.get('imdb_id', ''), item.get('tmdb_id', ''),
                    item.get('title', ''), item.get('year', ''),
                    media_type='movie',
                    poster=item.get('poster', ''), fanart=item.get('fanart', ''))
            else:
                source_selection(
                    item.get('imdb_id', ''), item.get('tmdb_id', ''),
                    item.get('title', ''), item.get('year', ''),
                    season=item.get('season'), episode=item.get('episode'),
                    media_type='tv',
                    poster=item.get('poster', ''), fanart=item.get('fanart', ''))

        elif action == 'play' and item:
            # Hero Play button — auto-play
            mt = item.get('media_type', 'movie')
            source_selection(
                item.get('imdb_id', ''), item.get('tmdb_id', ''),
                item.get('title', ''), item.get('year', ''),
                season=item.get('season'), episode=item.get('episode'),
                media_type=mt,
                poster=item.get('poster', ''), fanart=item.get('fanart', ''),
                auto_play=True)

        elif action == 'watchlist' and item:
            _get_trakt().add_to_watchlist(item.get('media_type', 'movie'), item.get('imdb_id', ''))
            notification(t('added_watchlist'))
            continue  # Re-show home

        elif action == 'search':
            search()
            continue  # Re-show home after search

        elif action == 'tools':
            tools_menu()
            break  # Tools uses Kodi directory — don't re-show home

        # After playing or selecting, re-show the home screen
        continue


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

    # Main — Netflix Home screen
    if not action:
        _show_netflix_home()
    
    # Movies
    elif action == 'movies_menu':
        movies_menu()
    elif action == 'movies_trending':
        list_movies(_get_tmdb().movies_trending, page, list_action='movies_trending')
    elif action == 'movies_popular':
        list_movies(_get_tmdb().movies_popular, page, list_action='movies_popular')
    elif action == 'movies_top_rated':
        list_movies(_get_tmdb().movies_top_rated, page, list_action='movies_top_rated')
    elif action == 'movies_now_playing':
        list_movies(_get_tmdb().movies_now_playing, page, list_action='movies_now_playing')
    elif action == 'movies_upcoming':
        list_movies(_get_tmdb().movies_upcoming, page, list_action='movies_upcoming')
    elif action == 'movies_genres':
        movies_genres()
    elif action == 'movies_genre':
        list_movies(_get_tmdb().movies_genre, page, genre_id=int(genre_id), list_action='movies_genre')
    elif action == 'movies_search':
        query = input_dialog(t('search_movies_prompt'))
        if query:
            from resources.lib.modules.cache import add_search_history
            add_search_history(query, 'movie')
            list_movies(_get_tmdb().movies_search, page, query=query, list_action='movies_search_results')
    elif action == 'movies_search_results':
        list_movies(_get_tmdb().movies_search, page, query=query, list_action='movies_search_results')
    elif action == 'movie_sources':
        source_selection(imdb_id, tmdb_id, title, year, media_type='movie', poster=poster, fanart=fanart)
    
    # TV Shows
    elif action == 'shows_menu':
        shows_menu()
    elif action == 'shows_trending':
        list_shows(_get_tmdb().shows_trending, page, list_action='shows_trending')
    elif action == 'shows_popular':
        list_shows(_get_tmdb().shows_popular, page, list_action='shows_popular')
    elif action == 'shows_top_rated':
        list_shows(_get_tmdb().shows_top_rated, page, list_action='shows_top_rated')
    elif action == 'shows_airing_today':
        list_shows(_get_tmdb().shows_airing_today, page, list_action='shows_airing_today')
    elif action == 'shows_genres':
        shows_genres()
    elif action == 'shows_genre':
        list_shows(_get_tmdb().shows_genre, page, genre_id=int(genre_id), list_action='shows_genre')
    elif action == 'shows_search':
        query = input_dialog(t('search_shows_prompt'))
        if query:
            from resources.lib.modules.cache import add_search_history
            add_search_history(query, 'tv')
            list_shows(_get_tmdb().shows_search, page, query=query, list_action='shows_search_results')
    elif action == 'shows_search_results':
        list_shows(_get_tmdb().shows_search, page, query=query, list_action='shows_search_results')
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
    elif action == 'search_movies':
        search_type_menu('movie')
    elif action == 'search_shows':
        search_type_menu('tv')
    elif action == 'search_new':
        search_new_typed(params.get('media_type', 'movie'))

    # People
    elif action == 'people_popular':
        people, _ = _get_tmdb().people_popular(page)
        for p in people:
            add_dir(p['name'], 'person_credits', poster=p.get('photo', ''),
                    tmdb_id=str(p['id']))
        end_dir(content='artists')
    elif action == 'person_credits':
        movies, shows = _get_tmdb().person_credits(tmdb_id)
        for m in movies[:20]:
            add_item(m, action='movie_sources', is_folder=True)
        for s in shows[:20]:
            add_item(s, action='show_seasons', is_folder=True)
        end_dir(content='videos')
    
    # Local continue watching / history
    elif action == 'continue_watching':
        continue_watching()
    elif action == 'watch_history':
        watch_history()

    # Trakt
    elif action == 'trakt_next_up':
        trakt_next_up()
    elif action == 'trakt_watchlist_menu':
        trakt_watchlist_menu()
    elif action == 'trakt_watchlist_movies':
        trakt_watchlist_movies()
    elif action == 'trakt_watchlist_shows':
        trakt_watchlist_shows()
    # trakt_progress removed — merged into continue_watching
    elif action == 'trakt_watchlist_add':
        _get_trakt().add_to_watchlist(media_type, imdb_id)
        notification(t('added_watchlist'))
    elif action == 'check_subs':
        if imdb_id:
            try:
                from hebsubscout import SubScout
                scout = SubScout()
                s = int(params.get('season', 0)) or None
                e = int(params.get('episode', 0)) or None
                subs = scout.fetch_subtitles(imdb_id, season=s, episode=e)
                if subs:
                    by_provider = {}
                    for sub in subs:
                        p = sub.get('provider', 'unknown')
                        by_provider.setdefault(p, []).append(sub)
                    lines = ['[COLOR lime]נמצאו {} כתוביות בעברית![/COLOR]\n'.format(len(subs))]
                    for prov, prov_subs in sorted(by_provider.items()):
                        lines.append('[COLOR cyan]{}[/COLOR]: {} כתוביות'.format(prov.upper(), len(prov_subs)))
                        for sub in prov_subs[:3]:
                            lines.append('  • {}'.format(sub.get('name', '')))
                        if len(prov_subs) > 3:
                            lines.append('  ... ועוד {}'.format(len(prov_subs) - 3))
                    xbmcgui.Dialog().textviewer('HebSubScout - {}'.format(title), '\n'.join(lines))
                else:
                    notification(t('no_heb_subs'))
            except Exception as ex:
                log('Check subs error: {}'.format(ex), 'ERROR')
                notification(t('no_heb_subs'))
    elif action == 'mark_watched':
        from resources.lib.modules.cache import mark_watched as local_mark_watched
        s = int(params.get('season', 0))
        e = int(params.get('episode', 0))
        local_mark_watched(imdb_id, s, e)
        if _get_trakt().is_authorized():
            if media_type == 'movie' or (s == 0 and e == 0):
                _get_trakt().mark_movie_watched(imdb_id)
            else:
                _get_trakt().mark_episode_watched(imdb_id, s, e)
    elif action == 'movie_similar':
        results = _get_tmdb().movie_recommendations(tmdb_id)
        if results:
            for m in results:
                add_item(m, action='movie_sources', is_folder=True)
        end_dir(content='movies')
    elif action == 'show_similar':
        results = _get_tmdb().show_recommendations(tmdb_id)
        if results:
            for s in results:
                add_item(s, action='show_seasons', is_folder=True)
        end_dir(content='tvshows')
    
    # Tools
    elif action == 'tools_menu':
        tools_menu()
    elif action == 'rd_auth':
        if _get_rd().is_authorized():
            if yesno_dialog('Real Debrid', t('disconnect_rd')):
                _get_rd().revoke()
        else:
            _get_rd().authorize()
    elif action == 'trakt_auth':
        if _get_trakt().is_authorized():
            if yesno_dialog('Trakt', t('disconnect_trakt')):
                _get_trakt().revoke()
        else:
            _get_trakt().authorize()
    elif action == 'clear_cache':
        cache_clear()
        notification(t('cache_cleared'))
    elif action == 'clear_search_history':
        from resources.lib.modules.cache import clear_search_history
        clear_search_history()
        notification(t('history_cleared'))
    elif action == 'toggle_setting':
        key = params.get('key', '')
        if key == 'ui_language':
            current = get_setting('ui_language') or 'Hebrew'
            new_val = 'English' if current == 'Hebrew' else 'Hebrew'
            set_setting('ui_language', new_val)
        else:
            current = get_setting(key)
            new_val = 'false' if current != 'false' else 'true'
            set_setting(key, new_val)
        xbmc.executebuiltin('Container.Refresh')
    elif action == 'ktuvit_setup':
        import hashlib
        email = xbmcgui.Dialog().input(t('ktuvit_email_prompt'))
        if email:
            password = xbmcgui.Dialog().input(t('ktuvit_password_prompt'),
                                              type=xbmcgui.INPUT_ALPHANUM,
                                              option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if password:
                set_setting('ktuvit_email', email)
                set_setting('ktuvit_password', hashlib.sha256(password.encode()).hexdigest())
                notification(t('ktuvit_saved'))
        xbmc.executebuiltin('Container.Refresh')
    elif action == 'noop':
        pass
    elif action == 'settings':
        ADDON.openSettings()
    
    # Direct play
    elif action == 'play':
        source_selection(imdb_id, tmdb_id, title, year, season=season, episode=episode,
                         media_type=media_type, poster=poster, fanart=fanart, auto_play=True)
    
    # Skip intro (called from skin OSD button)
    elif action == 'skip_intro':
        try:
            player = xbmc.Player()
            end_sec = int(xbmcgui.Window(10000).getProperty('hebscout.intro_end') or '0')
            if end_sec > 0 and player.isPlaying():
                player.seekTime(end_sec)
                log('Skip intro: seeked to {}s'.format(end_sec))
        except Exception:
            pass

    # Subtitle picker (called from skin OSD button during playback)
    elif action == 'subtitle_picker':
        player = xbmc.Player()
        if player.isPlaying():
            try:
                tag = player.getVideoInfoTag()
                imdb = tag.getIMDBNumber()
                s = tag.getSeason() if tag.getMediaType() == 'episode' else None
                e = tag.getEpisode() if tag.getMediaType() == 'episode' else None
                # Get original source name from window property (set by player), fallback to file URL
                source_name = xbmcgui.Window(10000).getProperty('hebscout.source_name')
                if not source_name:
                    try:
                        source_name = player.getPlayingFile().split('/')[-1].split('?')[0]
                    except Exception:
                        pass
                if imdb:
                    from hebsubscout import SubScout
                    scout = SubScout()
                    subs = scout.fetch_subtitles(imdb, season=s, episode=e)
                    if subs and source_name:
                        # Score subs against the source name
                        try:
                            from hebsubscout.matcher import ReleaseMatcher
                            matcher = ReleaseMatcher(min_score=0)
                            scored = matcher.match_source(source_name, subs)
                            if scored:
                                subs = scored
                        except Exception:
                            pass
                    if subs:
                        # Build labels with match percentage
                        labels = []
                        for sub in subs[:25]:
                            name = sub.get('name', sub.get('subtitle_name', 'Unknown'))
                            prov = sub.get('provider', '?')
                            score = sub.get('score', 0)
                            if len(name) > 45:
                                name = name[:42] + '...'
                            if score > 0:
                                labels.append('[COLOR FF00d4aa]{}%[/COLOR] {} [COLOR FF888888][{}][/COLOR]'.format(score, name, prov))
                            else:
                                labels.append('{} [COLOR FF888888][{}][/COLOR]'.format(name, prov))
                        choice = xbmcgui.Dialog().select(t('pick_heb_subs'), labels)
                        if choice >= 0:
                            selected = subs[choice]
                            download_sub = None
                            try:
                                subs_addon = xbmcaddon.Addon('service.subtitles.hebsubscout')
                                subs_path = subs_addon.getAddonInfo('path')
                                if subs_path not in sys.path:
                                    sys.path.insert(0, subs_path)
                                from downloader import download_subtitle
                                download_sub = download_subtitle
                            except Exception:
                                pass
                            if download_sub:
                                path = download_sub(
                                    provider=selected.get('provider', ''),
                                    subtitle_id=selected.get('id', ''),
                                )
                                if path:
                                    player.setSubtitles(path)
                                    notification(t('sub_applied', 0), time=2000)
                    else:
                        notification(t('no_heb_subs'))
                else:
                    notification(t('imdb_not_found'))
            except Exception as e:
                log('Subtitle picker error: {}'.format(e), 'ERROR')
                notification(t('no_heb_subs'))
        else:
            notification(t('not_playing'))

    # Switch source (called from skin OSD button during playback)
    elif action == 'switch_source':
        player = xbmc.Player()
        if player.isPlaying():
            try:
                tag = player.getVideoInfoTag()
                imdb = tag.getIMDBNumber()
                s = tag.getSeason() if tag.getMediaType() == 'episode' else None
                e = tag.getEpisode() if tag.getMediaType() == 'episode' else None
                mt = 'tv' if tag.getMediaType() == 'episode' else 'movie'
                player.stop()
                xbmc.sleep(500)
                if imdb:
                    source_selection(imdb, '', tag.getTitle() or '', '',
                                     season=s, episode=e, media_type=mt)
            except Exception as e:
                log('Switch source error: {}'.format(e), 'ERROR')
        else:
            notification(t('not_playing'))


if __name__ == '__main__':
    params = dict(parse_qsl(sys.argv[2].lstrip('?')))
    router(params)
