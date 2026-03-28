# -*- coding: utf-8 -*-
"""
Cache Module - SQLite-backed persistent cache
"""
import os
import time
import json
import sqlite3
import hashlib

try:
    import xbmcaddon
    import xbmcvfs
    _addon = xbmcaddon.Addon('plugin.video.hebscout')
    _profile = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))
except Exception:
    _profile = os.path.join(os.path.expanduser('~'), '.hebscout')

DB_PATH = os.path.join(_profile, 'cache.db')
_initialized = False


def _ensure_dir():
    d = os.path.dirname(DB_PATH)
    if d and not os.path.exists(d):
        os.makedirs(d)


def _get_conn():
    global _initialized
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
    if not _initialized:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                expires REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trakt_bookmarks (
                imdb_id TEXT,
                season INTEGER DEFAULT 0,
                episode INTEGER DEFAULT 0,
                progress REAL,
                paused_at TEXT,
                updated REAL,
                title TEXT DEFAULT '',
                poster TEXT DEFAULT '',
                fanart TEXT DEFAULT '',
                media_type TEXT DEFAULT 'movie',
                tmdb_id TEXT DEFAULT '',
                PRIMARY KEY (imdb_id, season, episode)
            )
        """)
        # Migrate from old schema (imdb_id-only PRIMARY KEY) to composite key
        try:
            pk_info = conn.execute("PRAGMA table_info(trakt_bookmarks)").fetchall()
            pk_cols = [r[1] for r in pk_info if r[5] > 0]  # r[5] = pk flag
            if pk_cols == ['imdb_id']:
                conn.execute("ALTER TABLE trakt_bookmarks RENAME TO _bookmarks_old")
                conn.execute("""
                    CREATE TABLE trakt_bookmarks (
                        imdb_id TEXT, season INTEGER DEFAULT 0, episode INTEGER DEFAULT 0,
                        progress REAL, paused_at TEXT, updated REAL,
                        title TEXT DEFAULT '', poster TEXT DEFAULT '', fanart TEXT DEFAULT '',
                        media_type TEXT DEFAULT 'movie', tmdb_id TEXT DEFAULT '',
                        PRIMARY KEY (imdb_id, season, episode)
                    )
                """)
                conn.execute("INSERT OR IGNORE INTO trakt_bookmarks SELECT * FROM _bookmarks_old")
                conn.execute("DROP TABLE _bookmarks_old")
                conn.commit()
        except Exception:
            pass
        # Add new columns if upgrading from older schema
        for col, coltype in [('title', 'TEXT'), ('poster', 'TEXT'), ('fanart', 'TEXT'),
                              ('media_type', 'TEXT'), ('tmdb_id', 'TEXT')]:
            try:
                conn.execute("ALTER TABLE trakt_bookmarks ADD COLUMN {} {} DEFAULT ''".format(col, coltype))
            except Exception:
                pass  # Column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watched (
                imdb_id TEXT,
                season INTEGER DEFAULT 0,
                episode INTEGER DEFAULT 0,
                watched_at REAL,
                PRIMARY KEY (imdb_id, season, episode)
            )
        """)
        _initialized = True
    return conn


def cache_get(key, default=None):
    try:
        conn = _get_conn()
        row = conn.execute("SELECT value, expires FROM cache WHERE key=?", (key,)).fetchone()
        conn.close()
        if row and row[1] > time.time():
            return json.loads(row[0])
    except Exception:
        pass
    return default


def cache_set(key, value, ttl=3600):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO cache (key, value, expires) VALUES (?, ?, ?)",
            (key, json.dumps(value, ensure_ascii=False), time.time() + ttl)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def cache_delete(key):
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM cache WHERE key=?", (key,))
        conn.commit()
        conn.close()
    except Exception:
        pass


def cache_clear():
    try:
        conn = _get_conn()
        conn.execute("DELETE FROM cache")
        conn.commit()
        conn.close()
    except Exception:
        pass


def _ensure_search_history_table():
    try:
        conn = _get_conn()
        conn.execute("""CREATE TABLE IF NOT EXISTS search_history_v2 (
            query TEXT, media_type TEXT DEFAULT 'movie',
            created TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (query, media_type))""")
        conn.commit()
        conn.close()
    except Exception:
        pass


def add_search_history(query, media_type='movie'):
    """Save a search query to history (max 20 per type, most recent first)."""
    _ensure_search_history_table()
    try:
        conn = _get_conn()
        conn.execute("INSERT OR REPLACE INTO search_history_v2 (query, media_type, created) VALUES (?, ?, CURRENT_TIMESTAMP)", (query, media_type))
        conn.execute("DELETE FROM search_history_v2 WHERE media_type=? AND query NOT IN "
                     "(SELECT query FROM search_history_v2 WHERE media_type=? ORDER BY created DESC LIMIT 20)",
                     (media_type, media_type))
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_search_history(media_type='movie'):
    """Get search history for a media type, most recent first."""
    _ensure_search_history_table()
    try:
        conn = _get_conn()
        rows = conn.execute("SELECT query FROM search_history_v2 WHERE media_type=? ORDER BY created DESC LIMIT 20",
                            (media_type,)).fetchall()
        conn.close()
        return [r[0] for r in rows]
    except Exception:
        return []


def clear_search_history():
    """Clear all search history entries."""
    try:
        conn = _get_conn()
        conn.execute("DROP TABLE IF EXISTS search_history_v2")
        conn.execute("DROP TABLE IF EXISTS search_history")
        conn.commit()
        conn.close()
    except Exception:
        pass


def set_bookmark(imdb_id, season, episode, progress, paused_at='',
                 title='', poster='', fanart='', media_type='', tmdb_id=''):
    try:
        s = season or 0
        e = episode or 0
        conn = _get_conn()
        # Preserve metadata from initial save when periodic saves omit it
        existing = conn.execute(
            "SELECT title, poster, fanart, media_type, tmdb_id FROM trakt_bookmarks "
            "WHERE imdb_id=? AND season=? AND episode=?",
            (imdb_id, s, e)
        ).fetchone()
        if existing:
            title = title or existing[0] or ''
            poster = poster or existing[1] or ''
            fanart = fanart or existing[2] or ''
            media_type = media_type or existing[3] or 'movie'
            tmdb_id = tmdb_id or existing[4] or ''
        conn.execute(
            "INSERT OR REPLACE INTO trakt_bookmarks "
            "(imdb_id, season, episode, progress, paused_at, updated, title, poster, fanart, media_type, tmdb_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (imdb_id, s, e, progress, paused_at, time.time(),
             title, poster, fanart, media_type or 'movie', tmdb_id)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_bookmark(imdb_id, season=0, episode=0):
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT imdb_id, season, episode, progress, paused_at, title, poster, fanart, media_type, tmdb_id "
            "FROM trakt_bookmarks WHERE imdb_id=? AND season=? AND episode=?",
            (imdb_id, season or 0, episode or 0)
        ).fetchone()
        conn.close()
        if row:
            return {'imdb_id': row[0], 'season': row[1], 'episode': row[2],
                    'progress': row[3], 'paused_at': row[4], 'title': row[5] or '',
                    'poster': row[6] or '', 'fanart': row[7] or '',
                    'media_type': row[8] or 'movie', 'tmdb_id': row[9] or ''}
    except Exception:
        pass
    return None


def get_continue_watching():
    """Get all in-progress items (1-90% watched), most recent first."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT imdb_id, season, episode, progress, title, poster, fanart, media_type, tmdb_id "
            "FROM trakt_bookmarks WHERE progress > 1 AND progress < 90 "
            "ORDER BY updated DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [{'imdb_id': r[0], 'season': r[1], 'episode': r[2], 'progress': r[3],
                 'title': r[4] or '', 'poster': r[5] or '', 'fanart': r[6] or '',
                 'media_type': r[7] or 'movie', 'tmdb_id': r[8] or ''} for r in rows]
    except Exception:
        return []


def get_watch_history():
    """Get recently watched items (from watched table), most recent first."""
    try:
        conn = _get_conn()
        rows = conn.execute(
            "SELECT w.imdb_id, w.season, w.episode, w.watched_at, "
            "b.title, b.poster, b.fanart, b.media_type, b.tmdb_id "
            "FROM watched w LEFT JOIN trakt_bookmarks b ON w.imdb_id = b.imdb_id "
            "ORDER BY w.watched_at DESC LIMIT 50"
        ).fetchall()
        conn.close()
        return [{'imdb_id': r[0], 'season': r[1], 'episode': r[2], 'watched_at': r[3],
                 'title': r[4] or '', 'poster': r[5] or '', 'fanart': r[6] or '',
                 'media_type': r[7] or 'movie', 'tmdb_id': r[8] or ''} for r in rows]
    except Exception:
        return []


def mark_watched(imdb_id, season=0, episode=0):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO watched (imdb_id, season, episode, watched_at) VALUES (?,?,?,?)",
            (imdb_id, season, episode, time.time())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def is_watched(imdb_id, season=0, episode=0):
    try:
        conn = _get_conn()
        row = conn.execute(
            "SELECT 1 FROM watched WHERE imdb_id=? AND season=? AND episode=?",
            (imdb_id, season, episode)
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def make_key(*parts):
    raw = ':'.join(str(p) for p in parts)
    return hashlib.md5(raw.encode()).hexdigest()
