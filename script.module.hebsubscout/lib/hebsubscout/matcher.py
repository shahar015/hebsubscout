# -*- coding: utf-8 -*-
"""
Release Name Matcher
====================

Computes match percentage between a video source filename/release name
and subtitle release names from Hebrew subtitle providers.

The matching algorithm works in layers:
1. Exact match (100%)
2. Normalized match - strip formatting differences (95%)
3. Component match - compare release group, quality, codec, etc. (variable %)
4. Fuzzy token match - sequence matching on cleaned tokens (variable %)

This is the "secret sauce" that makes the pre-source subtitle indicator useful.
"""

import re
import functools
from difflib import SequenceMatcher


# --- Release name parsing patterns ---

QUALITY_PATTERNS = [
    'remux', '2160p', '4k', 'uhd', '1080p', '1080i', '720p', '480p', '360p',
    'hdtv', 'hdrip', 'bdrip', 'brrip', 'bluray', 'blu-ray', 'webdl', 'web-dl',
    'webrip', 'web-rip', 'web', 'dvdrip', 'dvdscr', 'hdcam', 'cam', 'ts',
    'telesync', 'telecine', 'screener', 'pdtv', 'sdtv', 'hdr', 'hdr10',
    'dolby.vision', 'dv', 'sdr', 'imax'
]

CODEC_PATTERNS = [
    'x264', 'x265', 'h264', 'h.264', 'h265', 'h.265', 'hevc', 'avc',
    'xvid', 'divx', 'mpeg', 'mpeg2', 'av1', 'vp9', 'vc1', 'vc-1'
]

AUDIO_PATTERNS = [
    'dts', 'dts-hd', 'dts-hd.ma', 'dts-x', 'truehd', 'atmos',
    'dd5.1', 'ddp5.1', 'dd2.0', 'ac3', 'aac', 'aac2.0', 'aac5.1',
    'flac', 'eac3', 'mp3', 'opus', 'pcm', 'lpcm', 'dolby'
]

# Common release groups (partial list - the matcher works even without these)
SEASON_EPISODE_RE = re.compile(r'[Ss](\d{1,2})[Ee](\d{1,2})')
YEAR_RE = re.compile(r'(?:19|20)\d{2}')


def normalize_release_name(name):
    """
    Normalize a release name for comparison.
    Strips common separators and lowercases.
    """
    if not name:
        return ""
    # Replace common separators with dots
    name = re.sub(r'[\s\-_\[\]\(\)]', '.', name)
    # Remove double dots
    name = re.sub(r'\.{2,}', '.', name)
    # Strip leading/trailing dots
    name = name.strip('.')
    return name.lower()


@functools.lru_cache(maxsize=256)
def _extract_components_cached(name):
    """Cached version — called by extract_components()."""
    normalized = normalize_release_name(name)
    tokens = normalized.split('.')
    
    components = {
        'quality': [],
        'codec': [],
        'audio': [],
        'group': '',
        'season_episode': '',
        'year': '',
        'title_tokens': [],
        'all_tokens': set(tokens),
    }
    
    # Extract season/episode
    se_match = SEASON_EPISODE_RE.search(normalized)
    if se_match:
        components['season_episode'] = se_match.group(0).lower()
    
    # Extract year
    year_match = YEAR_RE.search(name)
    if year_match:
        components['year'] = year_match.group(0)
    
    # Categorize tokens
    title_ended = False
    for i, token in enumerate(tokens):
        token_lower = token.lower()
        
        if token_lower in QUALITY_PATTERNS:
            components['quality'].append(token_lower)
            title_ended = True
        elif token_lower in CODEC_PATTERNS:
            components['codec'].append(token_lower)
            title_ended = True
        elif token_lower in AUDIO_PATTERNS:
            components['audio'].append(token_lower)
            title_ended = True
        elif YEAR_RE.match(token):
            title_ended = True
        elif SEASON_EPISODE_RE.match(token):
            title_ended = True
        elif not title_ended:
            components['title_tokens'].append(token_lower)
    
    # Last token is often the release group (after a dash in the original)
    if tokens:
        # Check if original name has a group pattern like "-GROUP"
        group_match = re.search(r'-([A-Za-z0-9]+)(?:\.\w{2,4})?$', name)
        if group_match:
            components['group'] = group_match.group(1).lower()
    
    return components


def extract_components(name):
    """Extract structured components from a release name (cached)."""
    return _extract_components_cached(name)


def compute_match_score(source_name, subtitle_name):
    """
    Compute a match score (0-100) between a source name and a subtitle name.
    
    This is the core matching algorithm. Higher scores mean better matches.
    
    Scoring breakdown:
    - Title match:          30 points max
    - Quality match:        25 points max  
    - Codec match:          10 points max
    - Audio match:           5 points max
    - Release group match:  20 points max
    - Season/Episode match: 10 points max (or skipped for movies)
    
    Returns:
        int: Score from 0 to 100
    """
    if not source_name or not subtitle_name:
        return 0
    
    # Quick exact match check
    norm_source = normalize_release_name(source_name)
    norm_sub = normalize_release_name(subtitle_name)
    
    if norm_source == norm_sub:
        return 100
    
    # Check if one contains the other (very common with slight variations)
    if norm_source in norm_sub or norm_sub in norm_source:
        return 95
    
    # Component-based matching
    src = extract_components(source_name)
    sub = extract_components(subtitle_name)
    
    score = 0
    max_score = 0
    
    # --- Title match (30 points) ---
    max_score += 30
    if src['title_tokens'] and sub['title_tokens']:
        src_title = '.'.join(src['title_tokens'])
        sub_title = '.'.join(sub['title_tokens'])
        title_ratio = SequenceMatcher(None, src_title, sub_title).ratio()
        score += int(title_ratio * 30)
    
    # --- Quality match (25 points) ---
    max_score += 25
    if src['quality'] and sub['quality']:
        # Check overlap
        src_q = set(src['quality'])
        sub_q = set(sub['quality'])
        if src_q == sub_q:
            score += 25
        elif src_q & sub_q:
            # Partial match - at least the resolution matches
            overlap = len(src_q & sub_q) / max(len(src_q), len(sub_q))
            score += int(overlap * 20)
    elif not src['quality'] and not sub['quality']:
        score += 15  # Both unknown - neutral
    
    # --- Codec match (10 points) ---
    max_score += 10
    if src['codec'] and sub['codec']:
        if set(src['codec']) & set(sub['codec']):
            score += 10
    elif not src['codec'] and not sub['codec']:
        score += 5
    
    # --- Audio match (5 points) ---
    max_score += 5
    if src['audio'] and sub['audio']:
        if set(src['audio']) & set(sub['audio']):
            score += 5
    elif not src['audio'] and not sub['audio']:
        score += 2
    
    # --- Release group match (20 points) ---
    max_score += 20
    if src['group'] and sub['group']:
        if src['group'] == sub['group']:
            score += 20
        else:
            # Different group - this is actually a penalty signal
            # Subs from different groups are less likely to sync
            score += 0
    elif not src['group'] and not sub['group']:
        score += 5
    
    # --- Season/Episode match (10 points) ---
    if src['season_episode'] or sub['season_episode']:
        max_score += 10
        if src['season_episode'] == sub['season_episode']:
            score += 10
        elif src['season_episode'] and sub['season_episode']:
            # Both have S/E but different - bad sign
            score -= 10
    
    # Normalize to 0-100
    if max_score == 0:
        return 0
    
    final_score = int((score / max_score) * 100)
    return max(0, min(100, final_score))


class ReleaseMatcher:
    """
    High-level release matcher that handles batch matching of sources
    against subtitle databases.
    
    Features:
    - Batch matching of multiple sources against multiple subtitles
    - Learning database: remembers which subtitle matched which source well
    - Configurable minimum score threshold
    """
    
    def __init__(self, min_score=50, learning_db_path=None):
        """
        Args:
            min_score: Minimum match percentage to consider a match (0-100)
            learning_db_path: Path to persistent learning database (JSON file)
        """
        self.min_score = min_score
        self.learning_db_path = learning_db_path
        self._learning_db = {}
        self._load_learning_db()
    
    def _load_learning_db(self):
        """Load the learning database from disk."""
        if not self.learning_db_path:
            return
        try:
            import json
            import os
            if os.path.exists(self.learning_db_path):
                with open(self.learning_db_path, 'r', encoding='utf-8') as f:
                    self._learning_db = json.load(f)
        except Exception:
            self._learning_db = {}
    
    def _save_learning_db(self):
        """Save the learning database to disk."""
        if not self.learning_db_path:
            return
        try:
            import json
            import os
            parent = os.path.dirname(self.learning_db_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(self.learning_db_path, 'w', encoding='utf-8') as f:
                json.dump(self._learning_db, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
    
    def record_successful_match(self, source_name, subtitle_name, provider):
        """
        Record that a subtitle was successfully used with a source.
        This improves future matching accuracy (the "learning database").
        
        Call this after a user picks a subtitle and it syncs well.
        """
        key = normalize_release_name(source_name)
        self._learning_db[key] = {
            'subtitle': subtitle_name,
            'provider': provider,
            'score': 100  # Confirmed match
        }
        self._save_learning_db()
    
    def match_source(self, source_name, available_subtitles):
        """
        Match a single source against available subtitles.
        
        Args:
            source_name: The release/file name of the video source
            available_subtitles: List of dicts with at least:
                - 'name': subtitle release name
                - 'provider': which provider it's from
                - 'id': subtitle ID for downloading
        
        Returns:
            List of matches sorted by score (highest first), each containing:
                - 'score': int 0-100
                - 'subtitle_name': str
                - 'provider': str
                - 'subtitle_id': str
        """
        if not source_name or not available_subtitles:
            return []
        
        # Score all subtitles (real scores only, no artificial boosting)
        matches = []
        for sub in available_subtitles:
            score = compute_match_score(source_name, sub.get('name', ''))
            if score >= self.min_score:
                matches.append({
                    'score': score,
                    'subtitle_name': sub['name'],
                    'provider': sub.get('provider', ''),
                    'subtitle_id': sub.get('id', ''),
                    'learned': False
                })

        # Sort by score descending
        matches.sort(key=lambda x: x['score'], reverse=True)
        return matches
    
    def match_sources_batch(self, sources, available_subtitles):
        """
        Match multiple sources against the same subtitle pool.
        This is the main method for enriching a source list.
        
        Args:
            sources: List of dicts, each with at least 'name' (release name)
            available_subtitles: List of subtitle dicts from providers
        
        Returns:
            List of sources (same order), each enriched with:
                - 'has_hebrew_subs': bool
                - 'best_match_pct': int
                - 'best_match_source': str (provider name)
                - 'best_match_name': str
                - 'all_matches': list
        """
        enriched = []
        for source in sources:
            source_copy = dict(source)
            matches = self.match_source(source.get('name', ''), available_subtitles)
            
            if matches:
                best = matches[0]
                source_copy['has_hebrew_subs'] = True
                source_copy['best_match_pct'] = best['score']
                source_copy['best_match_source'] = best['provider']
                source_copy['best_match_name'] = best['subtitle_name']
                source_copy['all_matches'] = matches
            else:
                source_copy['has_hebrew_subs'] = False
                source_copy['best_match_pct'] = 0
                source_copy['best_match_source'] = ''
                source_copy['best_match_name'] = ''
                source_copy['all_matches'] = []
            
            enriched.append(source_copy)
        
        return enriched
