# -*- coding: utf-8 -*-
"""
Netflix Home Screen (WindowXMLDialog)
=====================================
A Netflix-style home screen with hero area and horizontal poster rows.
Replaces the old Kodi directory listing main menu.
"""

import threading
import xbmc
import xbmcgui
import xbmcaddon

from resources.lib.modules.utils import log, get_setting, t, is_hebrew

ADDON = xbmcaddon.Addon('plugin.video.hebscout')

# Row definitions: (row_index, label_key, data_fetcher_name)
ROW_DEFS = [
    (0, 'continue_watching', '_fetch_continue_watching'),
    (1, 'trending_movies',   '_fetch_trending_movies'),
    (2, 'popular_shows',     '_fetch_popular_shows'),
    (3, 'up_next',           '_fetch_up_next'),
    (4, 'my_watchlist',      '_fetch_watchlist'),
]

# Row control IDs: row_index -> (fixedlist_id, label_id)
ROW_IDS = {
    0: (1000, 1001),
    1: (1010, 1011),
    2: (1020, 1021),
    3: (1030, 1031),
    4: (1040, 1041),
}


class NetflixHome(xbmcgui.WindowXMLDialog):

    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, 'netflix_home.xml', ADDON.getAddonInfo('path'),
                               'Default', '1080i')

    def __init__(self):
        super().__init__('netflix_home.xml', ADDON.getAddonInfo('path'),
                         'Default', '1080i')
        self._rows_data = {}
        self._focused_row = 0
        self._result_action = None
        self._result_item = None

    def onInit(self):
        # Set static labels
        self.setProperty('hero_play_label', t('play'))
        self.setProperty('hero_watchlist_label', t('my_watchlist'))
        self.setProperty('search_label', t('search'))
        self.setProperty('tools_label', t('tools'))
        self.setProperty('version_label', 'v{}'.format(ADDON.getAddonInfo('version')))

        # Set row labels
        self.setProperty('row0_label', t('continue_watching'))
        self.setProperty('row1_label', t('trending_movies'))
        self.setProperty('row2_label', t('popular_shows'))
        self.setProperty('row3_label', t('up_next'))
        self.setProperty('row4_label', t('my_watchlist'))

        # Load all rows in parallel
        self._load_rows_async()

    def _load_rows_async(self):
        """Fetch all row data in parallel, populate as each completes."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def _fetch_row(row_idx, fetcher_name):
            try:
                fetcher = getattr(self, fetcher_name)
                items = fetcher()
                return (row_idx, items)
            except Exception as e:
                log('Netflix home row {} fetch failed: {}'.format(row_idx, e), 'ERROR')
                return (row_idx, [])

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {}
            for row_idx, label_key, fetcher_name in ROW_DEFS:
                futures[pool.submit(_fetch_row, row_idx, fetcher_name)] = row_idx

            first_populated = False
            for future in as_completed(futures):
                try:
                    row_idx, items = future.result()
                    self._rows_data[row_idx] = items
                    if items:
                        self._populate_row(row_idx, items)
                        if not first_populated:
                            first_populated = True
                            self._update_hero(items[0])
                            try:
                                list_id = ROW_IDS[row_idx][0]
                                self.setFocusId(list_id)
                            except Exception:
                                pass
                except Exception as e:
                    log('Netflix home row populate error: {}'.format(e), 'ERROR')

    def _populate_row(self, row_idx, items):
        """Populate a FixedList with poster items."""
        list_id = ROW_IDS[row_idx][0]
        try:
            control = self.getControl(list_id)
            li_items = []
            for item in items[:20]:
                li = xbmcgui.ListItem(item.get('title', ''))
                li.setArt({
                    'poster': item.get('poster', ''),
                    'fanart': item.get('fanart', ''),
                    'thumb': item.get('poster', ''),
                })
                # Store metadata as properties for later retrieval
                li.setProperty('imdb_id', str(item.get('imdb_id', '')))
                li.setProperty('tmdb_id', str(item.get('tmdb_id', '')))
                li.setProperty('media_type', item.get('media_type', 'movie'))
                li.setProperty('year', str(item.get('year', '')))
                li.setProperty('rating', str(item.get('rating', '')))
                li.setProperty('plot', item.get('plot', ''))
                li.setProperty('genres', item.get('genres', ''))
                li.setProperty('fanart_url', item.get('fanart', ''))
                li.setProperty('season', str(item.get('season', '')))
                li.setProperty('episode', str(item.get('episode', '')))
                li_items.append(li)
            control.reset()
            control.addItems(li_items)
            # Show the row
            self.setProperty('row{}_visible'.format(row_idx), 'true')
        except Exception as e:
            log('Failed to populate row {}: {}'.format(row_idx, e), 'ERROR')

    def _update_hero(self, item):
        """Update the hero area with the given item's info."""
        if not item:
            return
        self.setProperty('hero_fanart', item.get('fanart', ''))
        title = item.get('title', '')
        year = item.get('year', '')
        if year:
            title = '{} ({})'.format(title, year)
        self.setProperty('hero_title', title)

        # Build metadata line: rating • genres
        parts = []
        rating = item.get('rating', 0)
        if rating:
            parts.append('{:.1f}'.format(float(rating)))
        genres = item.get('genres', '')
        if genres:
            parts.append(genres)
        media_type = item.get('media_type', '')
        if media_type == 'tv':
            parts.append(t('tv_shows'))
        self.setProperty('hero_meta', '  |  '.join(parts))

    def _get_focused_item(self, control_id):
        """Get the currently focused item's metadata from a FixedList."""
        try:
            control = self.getControl(control_id)
            pos = control.getSelectedPosition()
            li = control.getSelectedItem()
            if li:
                return {
                    'title': li.getLabel(),
                    'imdb_id': li.getProperty('imdb_id'),
                    'tmdb_id': li.getProperty('tmdb_id'),
                    'media_type': li.getProperty('media_type'),
                    'year': li.getProperty('year'),
                    'rating': li.getProperty('rating'),
                    'plot': li.getProperty('plot'),
                    'genres': li.getProperty('genres'),
                    'poster': li.getArt('poster'),
                    'fanart': li.getProperty('fanart_url'),
                    'season': li.getProperty('season'),
                    'episode': li.getProperty('episode'),
                }
        except Exception:
            pass
        return None

    def onFocus(self, control_id):
        """Update hero when a row gains focus."""
        if control_id in (1000, 1010, 1020, 1030, 1040):
            item = self._get_focused_item(control_id)
            if item:
                self._update_hero(item)

    def onAction(self, action):
        action_id = action.getId()
        # Back / Escape
        if action_id in (92, 10):
            self.close()
            return
        # Left/Right in a fixedlist — update hero after scroll
        if action_id in (1, 2):  # ACTION_MOVE_LEFT, ACTION_MOVE_RIGHT
            focus_id = self.getFocusId()
            if focus_id in (1000, 1010, 1020, 1030, 1040):
                xbmc.sleep(50)  # Let Kodi update the selection
                item = self._get_focused_item(focus_id)
                if item:
                    self._update_hero(item)

    def onClick(self, control_id):
        # Hero Play button
        if control_id == 200:
            # Find the focused row and its focused item
            for row_idx in range(5):
                list_id = ROW_IDS[row_idx][0]
                try:
                    control = self.getControl(list_id)
                    if control.size() > 0:
                        item = self._get_focused_item(list_id)
                        if item:
                            self._result_action = 'play'
                            self._result_item = item
                            self.close()
                            return
                except Exception:
                    continue

        # Hero Watchlist button
        elif control_id == 201:
            for row_idx in range(5):
                list_id = ROW_IDS[row_idx][0]
                try:
                    control = self.getControl(list_id)
                    if control.size() > 0:
                        item = self._get_focused_item(list_id)
                        if item:
                            self._result_action = 'watchlist'
                            self._result_item = item
                            self.close()
                            return
                except Exception:
                    continue

        # Poster click in any row
        elif control_id in (1000, 1010, 1020, 1030, 1040):
            item = self._get_focused_item(control_id)
            if item:
                self._result_action = 'select'
                self._result_item = item
                self.close()

        # Search button
        elif control_id == 300:
            self._result_action = 'search'
            self.close()

        # Tools button
        elif control_id == 301:
            self._result_action = 'tools'
            self.close()

    # =====================================================================
    # DATA FETCHERS (each returns a list of item dicts)
    # =====================================================================

    def _fetch_continue_watching(self):
        """Fetch continue watching items from Trakt or local SQLite."""
        try:
            from resources.lib.modules import trakt_api as trakt
            if trakt.is_authorized():
                items = trakt.playback_progress()
                results = []
                for item in items[:20]:
                    movie = item.get('movie', {})
                    show = item.get('show', {})
                    episode = item.get('episode', {})
                    if movie:
                        results.append({
                            'title': movie.get('title', ''),
                            'imdb_id': movie.get('ids', {}).get('imdb', ''),
                            'tmdb_id': str(movie.get('ids', {}).get('tmdb', '')),
                            'media_type': 'movie',
                            'year': str(movie.get('year', '')),
                            'rating': movie.get('rating', 0),
                            'poster': '',  # TMDB poster fetched below
                            'fanart': '',
                            'genres': '',
                        })
                    elif show and episode:
                        ep_title = '{} S{:02d}E{:02d}'.format(
                            show.get('title', ''),
                            episode.get('season', 0),
                            episode.get('number', 0))
                        results.append({
                            'title': ep_title,
                            'imdb_id': show.get('ids', {}).get('imdb', ''),
                            'tmdb_id': str(show.get('ids', {}).get('tmdb', '')),
                            'media_type': 'tv',
                            'year': str(show.get('year', '')),
                            'rating': show.get('rating', 0),
                            'season': episode.get('season'),
                            'episode': episode.get('number'),
                            'poster': '',
                            'fanart': '',
                            'genres': '',
                        })
                # Enrich with TMDB posters
                self._enrich_with_tmdb(results)
                return results
        except Exception as e:
            log('Continue watching fetch failed: {}'.format(e), 'ERROR')

        # Fallback to local
        try:
            from resources.lib.modules.cache import get_continue_watching
            items = get_continue_watching()
            return [{
                'title': i.get('title', ''),
                'imdb_id': i.get('imdb_id', ''),
                'tmdb_id': i.get('tmdb_id', ''),
                'media_type': i.get('media_type', 'movie'),
                'year': '',
                'rating': 0,
                'poster': i.get('poster', ''),
                'fanart': i.get('fanart', ''),
                'genres': '',
                'season': i.get('season', 0),
                'episode': i.get('episode', 0),
            } for i in items[:20]]
        except Exception:
            return []

    def _fetch_trending_movies(self):
        from resources.lib.modules import tmdb
        items, _ = tmdb.movies_trending(page=1)
        return self._tmdb_to_rows(items)

    def _fetch_popular_shows(self):
        from resources.lib.modules import tmdb
        items, _ = tmdb.shows_popular(page=1)
        return self._tmdb_to_rows(items)

    def _fetch_up_next(self):
        try:
            from resources.lib.modules import trakt_api as trakt
            if not trakt.is_authorized():
                return []
            eps = trakt.get_next_episodes()
            results = []
            for ep in eps[:20]:
                show = ep.get('show', {})
                results.append({
                    'title': '{} S{:02d}E{:02d}'.format(
                        show.get('title', ''), ep.get('season', 0), ep.get('episode', 0)),
                    'imdb_id': ep.get('imdb_id', ''),
                    'tmdb_id': str(show.get('ids', {}).get('tmdb', '')),
                    'media_type': 'tv',
                    'year': str(show.get('year', '')),
                    'rating': 0,
                    'season': ep.get('season'),
                    'episode': ep.get('episode'),
                    'poster': '',
                    'fanart': '',
                    'genres': '',
                })
            self._enrich_with_tmdb(results)
            return results
        except Exception:
            return []

    def _fetch_watchlist(self):
        try:
            from resources.lib.modules import trakt_api as trakt
            if not trakt.is_authorized():
                return []
            movies = trakt.watchlist_movies()
            shows = trakt.watchlist_shows()
            results = []
            for item in (movies or [])[:10]:
                m = item.get('movie', {})
                results.append({
                    'title': m.get('title', ''),
                    'imdb_id': m.get('ids', {}).get('imdb', ''),
                    'tmdb_id': str(m.get('ids', {}).get('tmdb', '')),
                    'media_type': 'movie',
                    'year': str(m.get('year', '')),
                    'rating': 0,
                    'poster': '',
                    'fanart': '',
                    'genres': '',
                })
            for item in (shows or [])[:10]:
                s = item.get('show', {})
                results.append({
                    'title': s.get('title', ''),
                    'imdb_id': s.get('ids', {}).get('imdb', ''),
                    'tmdb_id': str(s.get('ids', {}).get('tmdb', '')),
                    'media_type': 'tv',
                    'year': str(s.get('year', '')),
                    'rating': 0,
                    'poster': '',
                    'fanart': '',
                    'genres': '',
                })
            self._enrich_with_tmdb(results)
            return results
        except Exception:
            return []

    def _tmdb_to_rows(self, items):
        """Convert TMDB parsed items to row format."""
        from resources.lib.modules import tmdb
        genre_map = getattr(tmdb, '_GENRE_MAP', {})
        results = []
        for item in items[:20]:
            genres = ', '.join(
                genre_map.get(gid, '') for gid in item.get('genre_ids', []) if gid in genre_map
            )[:40]
            results.append({
                'title': item.get('title', ''),
                'imdb_id': item.get('imdb_id', ''),
                'tmdb_id': str(item.get('tmdb_id', '')),
                'media_type': item.get('media_type', 'movie'),
                'year': str(item.get('year', '')),
                'rating': item.get('rating', 0),
                'poster': item.get('poster', ''),
                'fanart': item.get('fanart', ''),
                'genres': genres,
            })
        return results

    def _enrich_with_tmdb(self, items):
        """Fill in missing poster/fanart from TMDB for Trakt items."""
        from resources.lib.modules import tmdb
        for item in items:
            if item.get('poster') and item.get('fanart'):
                continue
            tmdb_id = item.get('tmdb_id', '')
            if not tmdb_id:
                continue
            try:
                if item.get('media_type') == 'movie':
                    details = tmdb.movie_details(tmdb_id)
                else:
                    details = tmdb.show_details(tmdb_id)
                if details:
                    if not item.get('poster'):
                        item['poster'] = details.get('poster', '')
                    if not item.get('fanart'):
                        item['fanart'] = details.get('fanart', '')
                    if not item.get('genres'):
                        item['genres'] = ', '.join(details.get('genres', []))[:40]
            except Exception:
                pass


def show_netflix_home():
    """Show the Netflix Home screen. Returns (action, item) tuple."""
    dialog = NetflixHome()
    dialog.doModal()
    action = dialog._result_action
    item = dialog._result_item
    del dialog
    return action, item
