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


def _ensure_dir():
    d = os.path.dirname(DB_PATH)
    if not os.path.exists(d):
        os.makedirs(d)


def _get_conn():
    _ensure_dir()
    conn = sqlite3.connect(DB_PATH, timeout=10)
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
            imdb_id TEXT PRIMARY KEY,
            season INTEGER,
            episode INTEGER,
            progress REAL,
            paused_at TEXT,
            updated REAL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS watched (
            imdb_id TEXT,
            season INTEGER DEFAULT 0,
            episode INTEGER DEFAULT 0,
            watched_at REAL,
            PRIMARY KEY (imdb_id, season, episode)
        )
    """)
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


def set_bookmark(imdb_id, season, episode, progress, paused_at=''):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO trakt_bookmarks VALUES (?,?,?,?,?,?)",
            (imdb_id, season or 0, episode or 0, progress, paused_at, time.time())
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


def get_bookmark(imdb_id):
    try:
        conn = _get_conn()
        row = conn.execute("SELECT * FROM trakt_bookmarks WHERE imdb_id=?", (imdb_id,)).fetchone()
        conn.close()
        if row:
            return {'imdb_id': row[0], 'season': row[1], 'episode': row[2],
                    'progress': row[3], 'paused_at': row[4]}
    except Exception:
        pass
    return None


def mark_watched(imdb_id, season=0, episode=0):
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO watched VALUES (?,?,?,?)",
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
