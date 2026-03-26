# -*- coding: utf-8 -*-
"""
TMDB API Module
===============
Full browsing: trending, popular, top rated, genres, search, discover.
Metadata retrieval for movies and TV shows including IMDB IDs.
"""

from resources.lib.modules.utils import http_get, TMDB_KEY, TMDB_LANG, TMDB_POSTER, TMDB_FANART_URL, log
from resources.lib.modules.cache import cache_get, cache_set, make_key

BASE = 'https://api.themoviedb.org/3'


def _url(path, **kwargs):
    params = {'api_key': TMDB_KEY, 'language': TMDB_LANG}
    params.update(kwargs)
    qs = '&'.join('{}={}'.format(k, v) for k, v in params.items() if v is not None)
    return '{}/{}?{}'.format(BASE, path, qs)


def _fetch(path, cache_hours=6, **kwargs):
    key = make_key('tmdb', path, str(kwargs))
    cached = cache_get(key)
    if cached:
        return cached
    data = http_get(_url(path, **kwargs))
    if data:
        cache_set(key, data, ttl=int(cache_hours * 3600))
    return data


def _parse_movie(item):
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': item.get('imdb_id', ''),
        'title': item.get('title', ''),
        'original_title': item.get('original_title', ''),
        'year': (item.get('release_date') or '')[:4],
        'plot': item.get('overview', ''),
        'rating': item.get('vote_average', 0),
        'votes': item.get('vote_count', 0),
        'poster': (TMDB_POSTER + item['poster_path']) if item.get('poster_path') else '',
        'fanart': (TMDB_FANART_URL + item['backdrop_path']) if item.get('backdrop_path') else '',
        'genre_ids': item.get('genre_ids', []),
        'media_type': 'movie',
    }


def _parse_show(item):
    return {
        'tmdb_id': item.get('id'),
        'imdb_id': item.get('imdb_id', '') or item.get('external_ids', {}).get('imdb_id', ''),
        'title': item.get('name', ''),
        'original_title': item.get('original_name', ''),
        'year': (item.get('first_air_date') or '')[:4],
        'plot': item.get('overview', ''),
        'rating': item.get('vote_average', 0),
        'votes': item.get('vote_count', 0),
        'poster': (TMDB_POSTER + item['poster_path']) if item.get('poster_path') else '',
        'fanart': (TMDB_FANART_URL + item['backdrop_path']) if item.get('backdrop_path') else '',
        'genre_ids': item.get('genre_ids', []),
        'media_type': 'tv',
        'seasons': item.get('number_of_seasons', 0),
    }


# =========================================================================
# LIST HELPER
# =========================================================================

def _list(path, parser, page=1, cache_hours=12, **kwargs):
    """Fetch a paginated TMDB list and parse results."""
    data = _fetch(path, page=page, cache_hours=cache_hours, **kwargs)
    if not data:
        return [], 0
    return [parser(i) for i in data.get('results', [])], data.get('total_pages', 1)


# =========================================================================
# MOVIES
# =========================================================================

def movies_trending(page=1):
    return _list('trending/movie/week', _parse_movie, page, cache_hours=4)

def movies_popular(page=1):
    return _list('movie/popular', _parse_movie, page)

def movies_top_rated(page=1):
    return _list('movie/top_rated', _parse_movie, page, cache_hours=24)

def movies_now_playing(page=1):
    return _list('movie/now_playing', _parse_movie, page)

def movies_upcoming(page=1):
    return _list('movie/upcoming', _parse_movie, page)

def movies_genre(genre_id, page=1):
    return _list('discover/movie', _parse_movie, page, with_genres=genre_id, sort_by='popularity.desc')

def movies_search(query, page=1):
    return _list('search/movie', _parse_movie, page, cache_hours=1, query=query)


def movie_details(tmdb_id):
    """Full movie details including IMDB ID."""
    data = _fetch('movie/{}'.format(tmdb_id), append_to_response='external_ids,credits', cache_hours=72)
    if not data:
        return None
    m = _parse_movie(data)
    m['imdb_id'] = data.get('imdb_id', '') or data.get('external_ids', {}).get('imdb_id', '')
    m['runtime'] = data.get('runtime', 0)
    m['genres'] = [g['name'] for g in data.get('genres', [])]
    m['tagline'] = data.get('tagline', '')
    cast = data.get('credits', {}).get('cast', [])
    m['cast'] = [c['name'] for c in cast[:10]]
    crew = data.get('credits', {}).get('crew', [])
    directors = [c['name'] for c in crew if c.get('job') == 'Director']
    m['director'] = directors[0] if directors else ''
    return m


# =========================================================================
# TV SHOWS
# =========================================================================

def shows_trending(page=1):
    return _list('trending/tv/week', _parse_show, page, cache_hours=4)

def shows_popular(page=1):
    return _list('tv/popular', _parse_show, page)

def shows_top_rated(page=1):
    return _list('tv/top_rated', _parse_show, page, cache_hours=24)

def shows_airing_today(page=1):
    return _list('tv/airing_today', _parse_show, page, cache_hours=4)

def shows_genre(genre_id, page=1):
    return _list('discover/tv', _parse_show, page, with_genres=genre_id, sort_by='popularity.desc')

def shows_search(query, page=1):
    return _list('search/tv', _parse_show, page, cache_hours=1, query=query)


def show_details(tmdb_id):
    """Full show details including IMDB ID and seasons."""
    data = _fetch('tv/{}'.format(tmdb_id), append_to_response='external_ids,credits', cache_hours=48)
    if not data:
        return None
    s = _parse_show(data)
    s['imdb_id'] = data.get('external_ids', {}).get('imdb_id', '')
    s['tvdb_id'] = data.get('external_ids', {}).get('tvdb_id', '')
    s['genres'] = [g['name'] for g in data.get('genres', [])]
    s['status'] = data.get('status', '')
    cast = data.get('credits', {}).get('cast', [])
    s['cast'] = [c['name'] for c in cast[:10]]
    crew = data.get('credits', {}).get('crew', [])
    directors = [c['name'] for c in crew if c.get('job') in ('Director', 'Series Director')]
    creators = [c.get('name', '') for c in data.get('created_by', [])]
    s['director'] = directors[0] if directors else (creators[0] if creators else '')
    s['seasons_data'] = []
    for sn in data.get('seasons', []):
        if sn.get('season_number', 0) == 0:
            continue  # Skip specials
        s['seasons_data'].append({
            'season_number': sn['season_number'],
            'name': sn.get('name', 'Season {}'.format(sn['season_number'])),
            'episode_count': sn.get('episode_count', 0),
            'poster': (TMDB_POSTER + sn['poster_path']) if sn.get('poster_path') else s['poster'],
            'air_date': sn.get('air_date', ''),
        })
    return s


def season_episodes(tmdb_id, season_number):
    """Get all episodes in a season."""
    data = _fetch('tv/{}/season/{}'.format(tmdb_id, season_number), cache_hours=24)
    if not data:
        return []
    episodes = []
    for ep in data.get('episodes', []):
        episodes.append({
            'episode_number': ep.get('episode_number'),
            'season_number': ep.get('season_number', season_number),
            'title': ep.get('name', ''),
            'plot': ep.get('overview', ''),
            'air_date': ep.get('air_date', ''),
            'rating': ep.get('vote_average', 0),
            'still': (TMDB_FANART_URL + ep['still_path']) if ep.get('still_path') else '',
            'runtime': ep.get('runtime', 0),
        })
    return episodes


def episode_details(tmdb_id, season_number, episode_number):
    """Get IMDB ID for a specific episode (needed for scraping)."""
    data = _fetch('tv/{}/season/{}/episode/{}'.format(tmdb_id, season_number, episode_number),
                  append_to_response='external_ids', cache_hours=72)
    if not data:
        return None
    return {
        'imdb_id': data.get('external_ids', {}).get('imdb_id', ''),
        'tvdb_id': data.get('external_ids', {}).get('tvdb_id', ''),
        'title': data.get('name', ''),
        'plot': data.get('overview', ''),
    }


# =========================================================================
# GENRES
# =========================================================================

def movie_genres():
    data = _fetch('genre/movie/list', cache_hours=168)
    return data.get('genres', []) if data else []


def tv_genres():
    data = _fetch('genre/tv/list', cache_hours=168)
    return data.get('genres', []) if data else []


# =========================================================================
# PEOPLE
# =========================================================================

def people_popular(page=1):
    data = _fetch('person/popular', page=page, cache_hours=24)
    if not data:
        return [], 0
    people = []
    for p in data.get('results', []):
        people.append({
            'id': p['id'],
            'name': p.get('name', ''),
            'photo': (TMDB_POSTER + p['profile_path']) if p.get('profile_path') else '',
            'known_for': p.get('known_for_department', ''),
        })
    return people, data.get('total_pages', 1)


def person_credits(person_id):
    data = _fetch('person/{}/combined_credits'.format(person_id), cache_hours=48)
    if not data:
        return [], []
    movies = [_parse_movie(i) for i in data.get('cast', []) if i.get('media_type') == 'movie']
    shows = [_parse_show(i) for i in data.get('cast', []) if i.get('media_type') == 'tv']
    movies.sort(key=lambda x: x.get('rating', 0), reverse=True)
    shows.sort(key=lambda x: x.get('rating', 0), reverse=True)
    return movies, shows
