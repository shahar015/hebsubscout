# -*- coding: utf-8 -*-
"""
Subtitle Downloader
===================
Actually downloads .srt files from Hebrew subtitle providers.
This is the piece that closes the loop between "subs exist" and "subs on screen".

HebSubScout module tells us WHICH subtitle matches best.
This module DOWNLOADS it and returns a path Kodi can use.
"""

import os
import json
import zipfile
import tempfile
import time

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode
    from urllib.error import HTTPError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError
    from urllib import urlencode

import xbmc
import xbmcvfs
import xbmcaddon

ADDON = xbmcaddon.Addon('service.subtitles.hebsubscout')
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))
TEMP_DIR = os.path.join(PROFILE, 'temp')


def log(msg, level='INFO'):
    xbmc.log('[HebSubScout-Subs] {}: {}'.format(level, msg), xbmc.LOGINFO)


def _ensure_dirs():
    for d in [PROFILE, TEMP_DIR]:
        if not os.path.exists(d):
            os.makedirs(d)


def _clean_temp():
    """Remove old temp subtitle files."""
    _ensure_dirs()
    try:
        for f in os.listdir(TEMP_DIR):
            fp = os.path.join(TEMP_DIR, f)
            if os.path.isfile(fp):
                os.remove(fp)
    except Exception:
        pass


def _http_get_bytes(url, headers=None, timeout=15, progress_callback=None):
    """Download bytes with optional progress callback."""
    try:
        req = Request(url)
        req.add_header('User-Agent', 'HebSubScout-Subs/1.0 Kodi')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        
        total = int(resp.headers.get('Content-Length', 0))
        data = b''
        chunk_size = 4096
        downloaded = 0
        
        while True:
            chunk = resp.read(chunk_size)
            if not chunk:
                break
            data += chunk
            downloaded += len(chunk)
            if progress_callback and total > 0:
                pct = int((downloaded / total) * 100)
                progress_callback(pct)
        
        return data
    except Exception as e:
        log('Download failed: {} - {}'.format(url, e), 'ERROR')
        return None


def _http_post_bytes(url, payload, headers=None, timeout=15, progress_callback=None):
    """POST request returning bytes."""
    try:
        body = json.dumps(payload).encode('utf-8')
        req = Request(url, data=body)
        req.add_header('User-Agent', 'HebSubScout-Subs/1.0 Kodi')
        req.add_header('Content-Type', 'application/json')
        if headers:
            for k, v in headers.items():
                req.add_header(k, v)
        resp = urlopen(req, timeout=timeout)
        
        total = int(resp.headers.get('Content-Length', 0))
        data = b''
        downloaded = 0
        
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            data += chunk
            downloaded += len(chunk)
            if progress_callback and total > 0:
                progress_callback(int((downloaded / total) * 100))
        
        return data
    except Exception as e:
        log('POST download failed: {} - {}'.format(url, e), 'ERROR')
        return None


def _extract_srt_from_zip(zip_data):
    """Extract .srt file from a zip archive (common subtitle delivery format)."""
    try:
        import io
        zf = zipfile.ZipFile(io.BytesIO(zip_data))
        for name in zf.namelist():
            if name.lower().endswith(('.srt', '.sub', '.ass', '.ssa')):
                return zf.read(name), name
        # If no subtitle extension found, try the first file
        if zf.namelist():
            first = zf.namelist()[0]
            return zf.read(first), first
    except Exception as e:
        log('Zip extraction failed: {}'.format(e), 'ERROR')
    return None, None


def _save_subtitle(content, filename='subtitle.srt'):
    """Save subtitle content to temp dir and return the path."""
    _ensure_dirs()
    _clean_temp()
    
    # Ensure .srt extension
    if not any(filename.lower().endswith(ext) for ext in ('.srt', '.sub', '.ass', '.ssa')):
        filename += '.srt'
    
    path = os.path.join(TEMP_DIR, filename)
    
    # Handle encoding - try to detect and convert to UTF-8
    if isinstance(content, bytes):
        # Try UTF-8 first, then Windows-1255 (Hebrew), then latin-1
        for encoding in ('utf-8-sig', 'utf-8', 'cp1255', 'iso-8859-8', 'latin-1'):
            try:
                text = content.decode(encoding)
                break
            except (UnicodeDecodeError, LookupError):
                continue
        else:
            text = content.decode('utf-8', errors='replace')
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
    else:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    log('Subtitle saved: {}'.format(path))
    return path


# =========================================================================
# WIZDOM DOWNLOADER
# =========================================================================

def download_wizdom(subtitle_id, progress_callback=None):
    """
    Download a subtitle from Wizdom.xyz.
    
    Args:
        subtitle_id: The subtitle ID from Wizdom search results
        progress_callback: Optional callable(percent) for progress UI
    
    Returns:
        Path to saved .srt file, or None on failure
    """
    if not subtitle_id:
        return None
    
    log('Downloading from Wizdom: ID={}'.format(subtitle_id))
    if progress_callback:
        progress_callback(10)
    
    # Wizdom download endpoint
    url = 'https://wizdom.xyz/api/files/sub/{}'.format(subtitle_id)
    data = _http_get_bytes(url, progress_callback=progress_callback)
    
    if not data:
        # Try alternative endpoint
        url = 'https://wizdom.xyz/api/download/{}'.format(subtitle_id)
        data = _http_get_bytes(url, progress_callback=progress_callback)
    
    if not data:
        log('Wizdom download failed for ID {}'.format(subtitle_id), 'ERROR')
        return None
    
    if progress_callback:
        progress_callback(80)
    
    # Check if it's a zip
    if data[:2] == b'PK':
        content, filename = _extract_srt_from_zip(data)
        if content:
            path = _save_subtitle(content, filename or 'wizdom_{}.srt'.format(subtitle_id))
            if progress_callback:
                progress_callback(100)
            return path
    
    # Direct .srt content
    path = _save_subtitle(data, 'wizdom_{}.srt'.format(subtitle_id))
    if progress_callback:
        progress_callback(100)
    return path


# =========================================================================
# KTUVIT / SCREWZIRA DOWNLOADER
# =========================================================================

def download_ktuvit(subtitle_id, progress_callback=None):
    """
    Download a subtitle from Ktuvit.me (ScrewZira).
    
    Args:
        subtitle_id: The Identifier from ScrewZira search results
        progress_callback: Optional callable(percent) for progress
    
    Returns:
        Path to saved .srt file, or None on failure
    """
    if not subtitle_id:
        return None
    
    log('Downloading from Ktuvit: ID={}'.format(subtitle_id))
    if progress_callback:
        progress_callback(10)
    
    # ScrewZira Download API
    url = 'http://api.screwzira.com/Download'
    payload = {
        "request": {
            "subtitleID": subtitle_id,
            "fontSize": "500",
            "hexColor": ""
        }
    }
    
    data = _http_post_bytes(url, payload, progress_callback=progress_callback)
    
    if not data:
        log('Ktuvit download failed for ID {}'.format(subtitle_id), 'ERROR')
        return None
    
    if progress_callback:
        progress_callback(80)
    
    # Ktuvit returns the subtitle content directly or as JSON with embedded content
    # Try parsing as JSON first
    try:
        response = json.loads(data.decode('utf-8'))
        # Ktuvit wraps in {"d": "subtitle content"}
        content = response.get('d', '')
        if content:
            path = _save_subtitle(content, 'ktuvit_{}.srt'.format(subtitle_id))
            if progress_callback:
                progress_callback(100)
            return path
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        pass
    
    # Check if zip
    if data[:2] == b'PK':
        content, filename = _extract_srt_from_zip(data)
        if content:
            path = _save_subtitle(content, filename or 'ktuvit_{}.srt'.format(subtitle_id))
            if progress_callback:
                progress_callback(100)
            return path
    
    # Raw subtitle content
    path = _save_subtitle(data, 'ktuvit_{}.srt'.format(subtitle_id))
    if progress_callback:
        progress_callback(100)
    return path


# =========================================================================
# OPENSUBTITLES DOWNLOADER
# =========================================================================

def download_opensubtitles(file_id, api_key='', progress_callback=None):
    """
    Download a subtitle from OpenSubtitles.com.
    Requires API key for the download endpoint.
    """
    if not file_id or not api_key:
        return None
    
    log('Downloading from OpenSubtitles: file_id={}'.format(file_id))
    if progress_callback:
        progress_callback(10)
    
    # Step 1: Request download link
    url = 'https://api.opensubtitles.com/api/v1/download'
    headers = {
        'Api-Key': api_key,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'HebSubScout v1.0'
    }
    payload = {'file_id': int(file_id)}
    
    try:
        body = json.dumps(payload).encode('utf-8')
        req = Request(url, data=body)
        for k, v in headers.items():
            req.add_header(k, v)
        resp = urlopen(req, timeout=15)
        result = json.loads(resp.read().decode('utf-8'))
        download_url = result.get('link', '')
    except Exception as e:
        log('OpenSubtitles download link request failed: {}'.format(e), 'ERROR')
        return None
    
    if not download_url:
        return None
    
    if progress_callback:
        progress_callback(40)
    
    # Step 2: Download the actual file
    data = _http_get_bytes(download_url, progress_callback=progress_callback)
    if not data:
        return None
    
    if progress_callback:
        progress_callback(90)
    
    path = _save_subtitle(data, 'opensubs_{}.srt'.format(file_id))
    if progress_callback:
        progress_callback(100)
    return path


# =========================================================================
# UNIFIED DOWNLOAD FUNCTION
# =========================================================================

def download_subtitle(provider, subtitle_id, api_key='', progress_callback=None):
    """
    Download a subtitle from any provider.
    
    Args:
        provider: 'wizdom', 'ktuvit', or 'opensubtitles'
        subtitle_id: Provider-specific subtitle ID
        api_key: API key (only needed for OpenSubtitles)
        progress_callback: Optional callable(percent)
    
    Returns:
        Path to the downloaded .srt file, or None on failure
    """
    if provider == 'wizdom':
        return download_wizdom(subtitle_id, progress_callback)
    elif provider == 'ktuvit':
        return download_ktuvit(subtitle_id, progress_callback)
    elif provider == 'opensubtitles':
        return download_opensubtitles(subtitle_id, api_key, progress_callback)
    else:
        log('Unknown provider: {}'.format(provider), 'ERROR')
        return None
