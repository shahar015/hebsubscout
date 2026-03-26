# -*- coding: utf-8 -*-
"""
HebSubScout - Hebrew Subtitle Scout Module for Kodi
====================================================

A shared module (like CocoScrapers) that any Kodi video addon can import
to check Hebrew subtitle availability and match quality BEFORE source selection.

Usage by addon developers:
    from hebsubscout import SubScout
    scout = SubScout()
    results = scout.check_sources(imdb_id, sources_list)

Each source in results will be enriched with:
    - has_hebrew_subs: bool
    - best_match_pct: int (0-100)
    - best_match_source: str ("wizdom", "ktuvit", "opensubtitles")
    - best_match_name: str (subtitle release name)
    - all_matches: list of all matching subtitles with scores

Author: HebSubScout Community
License: GPL-3.0
"""

__version__ = "1.0.0"
__addon_id__ = "script.module.hebsubscout"

from hebsubscout.scout import SubScout
from hebsubscout.matcher import ReleaseMatcher
from hebsubscout.providers import WizdomProvider, KtuvitProvider, OpenSubtitlesProvider
