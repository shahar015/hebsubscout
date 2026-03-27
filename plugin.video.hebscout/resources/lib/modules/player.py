# -*- coding: utf-8 -*-
"""
Player Module
=============
Custom Kodi player with:
- NETFLIX-STYLE continuous progress saving (every 5s, survives crashes)
- Trakt scrobbling (start/pause/stop)
- Next episode auto-play
- Resume from last position
- HebSubScout learning (record successful subtitle matches)
"""

import sys
import time
import threading
import xbmc
import xbmcgui
import xbmcaddon

from resources.lib.modules.utils import log, get_setting, notification, t
from resources.lib.modules import trakt_api as trakt
from resources.lib.modules.cache import set_bookmark, get_bookmark, mark_watched

try:
    from hebsubscout import SubScout
    _scout = SubScout()
except ImportError:
    _scout = None


def _import_subtitle_downloader():
    """Import download_subtitle from the subtitle service addon."""
    try:
        subs_addon = xbmcaddon.Addon('service.subtitles.hebsubscout')
        subs_path = subs_addon.getAddonInfo('path')
        if subs_path not in sys.path:
            sys.path.insert(0, subs_path)
        from downloader import download_subtitle
        return download_subtitle
    except Exception:
        return None

PROGRESS_SAVE_INTERVAL = 5  # seconds


class ProgressTracker(threading.Thread):
    """
    Background thread that saves watch progress every 5 seconds.

    This is the Netflix approach: if Kodi crashes, power goes out,
    or anything unexpected happens, the user loses at most 5 seconds
    of progress. Also keeps the Trakt scrobble session alive.
    """
    
    def __init__(self, player):
        super().__init__(daemon=True)
        self.player = player
        self._stop_event = threading.Event()
    
    def stop(self):
        self._stop_event.set()
    
    def run(self):
        log('ProgressTracker started (saves every {}s)'.format(PROGRESS_SAVE_INTERVAL))
        while not self._stop_event.is_set():
            # Sleep in 1s increments so stop() is responsive
            for _ in range(PROGRESS_SAVE_INTERVAL):
                if self._stop_event.is_set():
                    return
                time.sleep(1)
            
            if not self.player._playing or self.player._paused:
                continue
            
            try:
                progress = self.player._get_progress()
                if progress <= 0:
                    continue
                
                # Track last known progress for when player is destroyed on stop
                self.player._last_known_progress = progress

                # Save to local SQLite (crash-proof)
                set_bookmark(
                    self.player.imdb_id, self.player.season,
                    self.player.episode, progress
                )
                
                # Keep Trakt scrobble session alive (Trakt requires >= 1.0%)
                if progress >= 1.0 and trakt.is_authorized() and self.player.imdb_id:
                    trakt.scrobble_start(
                        self.player.media_type, self.player.imdb_id,
                        progress, self.player.season, self.player.episode
                    )
                
                log('Auto-saved: {:.1f}% ({})'.format(progress, self.player.title))
                
                # Auto-mark watched at 90%
                if progress >= 90 and not self.player._marked_watched:
                    self.player._mark_as_watched()
            except Exception:
                pass  # Player may have been destroyed


class PlayerActionMonitor(threading.Thread):
    """
    Monitors for 'T' key press during fullscreen video playback.
    Opens subtitle picker when T is pressed. Audio track switching
    uses Kodi's native OSD audio button (no custom overlay needed).

    NOTE: WindowDialog overlays CANNOT be used during playback — they
    steal all input and block play/pause/seek controls. This monitor
    uses executebuiltin('Action(...)') which is non-intrusive.
    """

    def __init__(self, player):
        super().__init__(daemon=True)
        self._player = player
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        log('Player action monitor started')
        while not self._stop_event.is_set():
            self._stop_event.wait(0.5)


class HebScoutPlayer(xbmc.Player):
    """
    Custom player with Netflix-style progress saving.
    
    Progress is saved:
    - Every 5 seconds during playback (background thread)
    - Immediately on pause
    - On stop / end / error

    Even if power goes out mid-stream, the user loses at most 5 seconds.
    """
    
    def __init__(self):
        super().__init__()
        self.media_type = self.imdb_id = self.tmdb_id = None
        self.title = self.year = self.source_name = self.subtitle_name = None
        self.season = self.episode = None
        self._playing = self._paused = self._scrobbled_start = False
        self._marked_watched = False
        self._total_time = 0
        self._last_known_progress = 0.0  # Survives player destruction
        self._next_episode_info = self._resolve_func = None
        self._progress_tracker = None
        self._sub_matches = []      # All subtitle matches from HebSubScout
        self._auto_sub_applied = False
        self._osd_monitor = None

    def play_source(self, url, metadata, next_episode_info=None, resolve_func=None):
        self.media_type = metadata.get('media_type', 'movie')
        self.imdb_id = metadata.get('imdb_id', '')
        self.tmdb_id = metadata.get('tmdb_id', '')
        self.title = metadata.get('title', '')
        self.year = metadata.get('year', '')
        self.season = metadata.get('season')
        self.episode = metadata.get('episode')
        self.source_name = metadata.get('source_name', '')
        self._poster = metadata.get('poster', '')
        self._fanart = metadata.get('fanart', '')
        self._sub_matches = metadata.get('sub_matches', [])  # From source selection
        self._next_episode_info = next_episode_info
        self._resolve_func = resolve_func
        self._playing = self._paused = self._scrobbled_start = False
        self._marked_watched = False
        self._auto_sub_applied = False
        self._last_known_progress = 0.0
        if self._osd_monitor:
            self._osd_monitor.stop()
            self._osd_monitor = None
        if self._progress_tracker:
            self._progress_tracker.stop()
            self._progress_tracker = None

        li = xbmcgui.ListItem(path=url)
        tag = li.getVideoInfoTag()
        tag.setTitle(self.title)
        tag.setIMDBNumber(self.imdb_id)
        if self.media_type != 'movie':
            tag.setMediaType('episode')
            tag.setSeason(self.season or 0)
            tag.setEpisode(self.episode or 0)
        else:
            tag.setMediaType('movie')
        if metadata.get('poster'):
            li.setArt({'poster': metadata['poster'], 'thumb': metadata['poster']})
        if metadata.get('fanart'):
            li.setArt({'fanart': metadata['fanart']})

        # Resume dialog
        bm = get_bookmark(self.imdb_id)
        if bm and bm.get('progress', 0) > 5:
            if xbmcgui.Dialog().yesno(t('resume_title'),
                    t('resume_msg', bm['progress']),
                    yeslabel=t('resume_yes'), nolabel=t('resume_no')):
                li.setProperty('StartPercent', str(bm['progress']))

        self.play(url, li)

    def onAVStarted(self):
        self._playing = True
        self._paused = False
        try:
            self._total_time = self.getTotalTime()
        except Exception:
            self._total_time = 0
        # Trakt scrobble will be sent by ProgressTracker once progress >= 1%
        # (Trakt API requires at least 1.0% progress)
        if trakt.is_authorized() and self.imdb_id:
            self._scrobbled_start = True
        # Start background saver
        self._progress_tracker = ProgressTracker(self)
        self._progress_tracker.start()
        # Immediate first save (with full metadata so continue watching can display it)
        set_bookmark(self.imdb_id, self.season, self.episode, self._get_progress(),
                     title=self.title or '', poster=self._poster or '',
                     fanart=self._fanart or '', media_type=self.media_type or 'movie',
                     tmdb_id=self.tmdb_id or '')
        
        # Start action monitor (lightweight, no WindowDialog overlay)
        self._osd_monitor = PlayerActionMonitor(self)
        self._osd_monitor.start()

        # === AUTO-DOWNLOAD BEST MATCHING SUBTITLE ===
        if self._sub_matches and not self._auto_sub_applied and get_setting('auto_subs') != 'false':
            self._auto_apply_best_subtitle()
    
    def _auto_apply_best_subtitle(self):
        """
        Auto-download and apply the best matching Hebrew subtitle.
        Runs in background thread so it doesn't block playback start.
        """
        if not self._sub_matches:
            return
        
        best = self._sub_matches[0]  # Already sorted by score
        if best.get('score', 0) < 40:
            log('Best subtitle match too low ({}%), skipping auto-apply'.format(best.get('score', 0)))
            return
        
        def do_auto_sub():
            try:
                notification(t('sub_search_start'), time=2000)

                download_subtitle = _import_subtitle_downloader()
                if not download_subtitle:
                    log('Subtitle service not installed - cannot auto-download', 'WARNING')
                    notification(t('no_heb_subs'), time=3000)
                    return

                num_subs = len(self._sub_matches)
                best_pct = best.get('score', 0)
                notification(t('sub_found', num_subs, best_pct), time=3000)

                log('Auto-downloading subtitle: {} ({}%) from {}'.format(
                    best.get('subtitle_name', ''), best_pct, best.get('provider', '')))

                path = download_subtitle(
                    provider=best.get('provider', ''),
                    subtitle_id=best.get('subtitle_id', ''),
                )

                if path and self._playing:
                    self.setSubtitles(path)
                    self._auto_sub_applied = True
                    self.subtitle_name = best.get('subtitle_name', '')
                    notification(t('sub_applied', best_pct), time=3000)
                    log('Auto-applied subtitle: {}'.format(path))

                    # Record in learning DB
                    if _scout and self.source_name:
                        _scout.record_match(self.source_name, self.subtitle_name, best.get('provider', ''))
            except Exception as e:
                log('Auto-subtitle failed: {}'.format(e), 'ERROR')
        
        threading.Thread(target=do_auto_sub, daemon=True).start()
    
    def show_subtitle_picker(self):
        """
        Open the floating subtitle picker popup.
        Call this from a menu action or key binding during playback.
        Shows all available Hebrew subtitles with match percentages.
        User picks one → downloads with progress → auto-applies → popup closes.
        """
        if not self._sub_matches:
            # If we don't have cached matches, fetch them now
            if self.imdb_id:
                try:
                    scout = SubScout() if not _scout else _scout
                    subs = scout.fetch_subtitles(self.imdb_id, self.season, self.episode)
                    
                    if self.source_name:
                        from hebsubscout.matcher import ReleaseMatcher
                        matcher = ReleaseMatcher(min_score=20)
                        self._sub_matches = matcher.match_source(self.source_name, subs)
                    else:
                        # No source name to match against - show all with neutral scores
                        self._sub_matches = [
                            {'score': 50, 'subtitle_name': s.get('name', ''),
                             'provider': s.get('provider', ''), 'subtitle_id': s.get('id', '')}
                            for s in subs
                        ]
                except Exception as e:
                    log('Failed to fetch subs for picker: {}'.format(e), 'ERROR')
        
        if not self._sub_matches:
            xbmcgui.Dialog().notification('HebSubScout', t('no_heb_subs'),
                                          xbmcgui.NOTIFICATION_WARNING, 3000)
            return
        
        try:
            subs_addon = xbmcaddon.Addon('service.subtitles.hebsubscout')
            subs_path = subs_addon.getAddonInfo('path')
            if subs_path not in sys.path:
                sys.path.insert(0, subs_path)
            from picker import show_subtitle_picker

            path = show_subtitle_picker(
                subtitles=self._sub_matches,
                player=self,
                api_key=get_setting('opensubtitles_api_key') or ''
            )

            if path:
                self.subtitle_name = ''
                for m in self._sub_matches:
                    if path:  # Record whichever was chosen
                        self.subtitle_name = m.get('subtitle_name', '')
                        break
                log('User picked subtitle from picker: {}'.format(path))
        except Exception:
            log('Subtitle picker not available - using basic dialog', 'WARNING')
            self._fallback_subtitle_picker()
    
    def _fallback_subtitle_picker(self):
        """
        Fallback subtitle picker using Kodi's built-in dialog.
        Used when the subtitle service addon isn't installed.
        """
        labels = []
        for m in self._sub_matches[:15]:
            score = m.get('score', 0)
            name = m.get('subtitle_name', 'Unknown')
            prov = m.get('provider', '?')
            if len(name) > 50:
                name = name[:47] + '...'
            labels.append('{}% | {} [{}]'.format(score, name, prov))
        
        choice = xbmcgui.Dialog().select(t('pick_heb_subs'), labels)
        if choice < 0:
            return
        
        selected = self._sub_matches[choice]
        
        download_subtitle = _import_subtitle_downloader()
        if not download_subtitle:
            xbmcgui.Dialog().ok('HebSubScout', t('sub_service_missing'))
            return

        try:
            progress = xbmcgui.DialogProgress()
            progress.create('HebSubScout', t('downloading_subs'))

            path = download_subtitle(
                provider=selected.get('provider', ''),
                subtitle_id=selected.get('subtitle_id', ''),
                progress_callback=lambda p: progress.update(p, t('downloading_pct', p))
            )

            progress.close()

            if path:
                self.setSubtitles(path)
                self.subtitle_name = selected.get('subtitle_name', '')
                log('Fallback picker: applied {}'.format(path))
        except Exception as e:
            log('Fallback subtitle download failed: {}'.format(e), 'ERROR')

    def onPlayBackPaused(self):
        if not self._playing:
            return
        self._paused = True
        p = self._get_progress()
        set_bookmark(self.imdb_id, self.season, self.episode, p)
        if p >= 1.0 and trakt.is_authorized() and self.imdb_id:
            trakt.scrobble_pause(self.media_type, self.imdb_id, p, self.season, self.episode)

    def onPlayBackResumed(self):
        if not self._playing:
            return
        self._paused = False
        p = self._get_progress()
        if p >= 1.0 and trakt.is_authorized() and self.imdb_id:
            trakt.scrobble_start(self.media_type, self.imdb_id, p, self.season, self.episode)

    def onPlayBackStopped(self):
        self._handle_end()

    def onPlayBackEnded(self):
        self._handle_end(completed=True)

    def onPlayBackError(self):
        self._handle_end()

    def _handle_end(self, completed=False):
        if not self._playing:
            return
        self._playing = False
        # Stop OSD monitor
        if self._osd_monitor:
            self._osd_monitor.stop()
            self._osd_monitor = None
        if self._progress_tracker:
            self._progress_tracker.stop()
            self._progress_tracker = None
        p = 100.0 if completed else self._get_progress()
        log('_handle_end: completed={} progress={:.1f}% last_known={:.1f}% scrobbled={}'.format(
            completed, p, self._last_known_progress, self._scrobbled_start))
        # _get_progress may return _last_known_progress if player is already destroyed
        # But if even that is 0, don't overwrite a good bookmark
        if p >= 90:
            set_bookmark(self.imdb_id, self.season, self.episode, 0)
        elif p > 0:
            set_bookmark(self.imdb_id, self.season, self.episode, p)
        # else: p==0 means player was destroyed before we could read — keep existing bookmark
        if p >= 1.0 and trakt.is_authorized() and self.imdb_id and self._scrobbled_start:
            trakt.scrobble_stop(self.media_type, self.imdb_id, p, self.season, self.episode)
            if p >= 80:
                self._mark_as_watched()
        if _scout and self.source_name and self.subtitle_name:
            _scout.record_match(self.source_name, self.subtitle_name, 'auto')
        if completed and self._next_episode_info and get_setting('auto_next_episode') != 'false':
            self._play_next_episode()

    def _mark_as_watched(self):
        if self._marked_watched:
            return
        self._marked_watched = True
        mark_watched(self.imdb_id, self.season or 0, self.episode or 0)
        if trakt.is_authorized():
            if self.media_type == 'movie':
                trakt.mark_movie_watched(self.imdb_id)
            else:
                trakt.mark_episode_watched(self.imdb_id, self.season, self.episode)

    def _play_next_episode(self):
        if not self._next_episode_info or not self._resolve_func:
            return
        ni = self._next_episode_info
        ns, ne, nt = ni.get('season'), ni.get('episode'), ni.get('title', '')
        should = xbmcgui.Dialog().yesno(t('next_ep_title'),
            'S{:02d}E{:02d} - {}'.format(ns, ne, nt),
            yeslabel=t('next_ep_play'), nolabel=t('next_ep_stop'), autoclose=15000)
        if should or should is None:
            try:
                url = self._resolve_func(self.imdb_id, ns, ne)
                if url:
                    meta = {'media_type': 'tv', 'imdb_id': self.imdb_id,
                            'tmdb_id': self.tmdb_id, 'title': self.title,
                            'year': self.year, 'season': ns, 'episode': ne}
                    self.play_source(url, meta, None, self._resolve_func)
            except Exception as e:
                log('Next episode failed: {}'.format(e), 'ERROR')

    def _get_progress(self):
        try:
            p = min(100.0, (self.getTime() / self._total_time) * 100.0) if self._total_time > 0 else 0.0
            if p > 0:
                self._last_known_progress = p
            return p
        except Exception:
            return self._last_known_progress
