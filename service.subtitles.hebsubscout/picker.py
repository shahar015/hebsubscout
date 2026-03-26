# -*- coding: utf-8 -*-
"""
Subtitle Picker Popup
=====================
A floating overlay window that appears on top of the video player.
Shows all available Hebrew subtitles with match percentages,
handles download with progress indicator, and auto-closes after applying.

Design:
┌─────────────────────────────────────┐
│ בחירת כתוביות          [X]         │
│─────────────────────────────────────│
│ 🟢 92% Movie.2024.1080p.x264  WIZ  │  ← selected/highlighted
│ 🟡 78% Movie.2024.720p.WEB    KTU  │
│ 🟠 55% Movie.2024.BRRip       WIZ  │
│ 🔴  0% (no match)             OPN  │
│                                     │
│        [מוריד... 45%]              │  ← shown during download
└─────────────────────────────────────┘
"""

import threading
import time
import xbmc
import xbmcgui

from service.subtitles.hebsubscout.downloader import download_subtitle, log

# Layout constants - positioned in top-right corner
POPUP_W = 620
POPUP_H = 450
POPUP_X = 1920 - POPUP_W - 40  # 40px from right edge
POPUP_Y = 60                    # 60px from top

# Control IDs
BG_ID = 100
TITLE_ID = 101
CLOSE_BTN_ID = 102
LIST_ID = 200
STATUS_ID = 300
PROGRESS_ID = 301

# Colors
COLOR_BG = '0xE0101020'
COLOR_HEADER = '0xFF1a1a3e'
COLOR_LIME = '0xFF00FF00'
COLOR_YELLOW = '0xFFFFFF00'
COLOR_ORANGE = '0xFFFF8800'
COLOR_RED = '0xFFFF3333'
COLOR_WHITE = '0xFFFFFFFF'
COLOR_GRAY = '0xFF888888'
COLOR_CYAN = '0xFF00DDDD'


class SubtitlePickerWindow(xbmcgui.WindowDialog):
    """
    Floating subtitle picker overlay.
    
    Usage:
        picker = SubtitlePickerWindow(subtitles_list, player_instance)
        picker.doModal()
        # After modal closes, check picker.selected_path for the downloaded sub path
    """
    
    def __init__(self, subtitles, player=None, api_key=''):
        """
        Args:
            subtitles: List of subtitle dicts from HebSubScout matching, each with:
                - score: int (0-100)
                - subtitle_name: str
                - provider: str ('wizdom', 'ktuvit', 'opensubtitles')
                - subtitle_id: str
            player: Optional xbmc.Player instance to apply subs to
            api_key: OpenSubtitles API key if needed
        """
        super().__init__()
        self.subtitles = subtitles or []
        self.player = player
        self.api_key = api_key
        self.selected_path = None
        self._downloading = False
        self._download_thread = None
        self._controls = {}
        self._list_buttons = []
        self._focused_index = 0
        
        self._build_ui()
    
    def _build_ui(self):
        """Build all UI controls programmatically."""
        
        # --- Background panel ---
        bg = xbmcgui.ControlImage(
            POPUP_X, POPUP_Y, POPUP_W, POPUP_H,
            '', colorDiffuse=COLOR_BG
        )
        self.addControl(bg)
        
        # --- Header bar ---
        header_bg = xbmcgui.ControlImage(
            POPUP_X, POPUP_Y, POPUP_W, 50,
            '', colorDiffuse=COLOR_HEADER
        )
        self.addControl(header_bg)
        
        # Title
        title = xbmcgui.ControlLabel(
            POPUP_X + 20, POPUP_Y + 8, POPUP_W - 80, 35,
            'בחירת כתוביות עבריות',
            font='font14', textColor=COLOR_CYAN,
            alignment=0x00000001  # XBFONT_RIGHT for Hebrew RTL
        )
        self.addControl(title)
        
        # Close button [X]
        self._close_btn = xbmcgui.ControlButton(
            POPUP_X + POPUP_W - 55, POPUP_Y + 5, 45, 40,
            '✕', font='font14',
            textColor=COLOR_WHITE,
            focusTexture='', noFocusTexture='',
            alignment=0x00000002 | 0x00000004  # Center
        )
        self.addControl(self._close_btn)
        
        # --- Subtitle list area ---
        list_y = POPUP_Y + 55
        list_h = POPUP_H - 120  # Leave room for status bar at bottom
        max_visible = min(len(self.subtitles), 8)
        item_h = 42
        
        for i, sub in enumerate(self.subtitles[:max_visible]):
            y = list_y + (i * item_h)
            
            score = sub.get('score', 0)
            name = sub.get('subtitle_name', 'Unknown')
            provider = sub.get('provider', '?')
            
            # Truncate long names
            if len(name) > 45:
                name = name[:42] + '...'
            
            # Color by score
            if score >= 90:
                score_color = COLOR_LIME
                indicator = '●'
            elif score >= 70:
                score_color = COLOR_YELLOW
                indicator = '●'
            elif score >= 40:
                score_color = COLOR_ORANGE
                indicator = '●'
            else:
                score_color = COLOR_RED
                indicator = '●'
            
            # Provider short label
            prov_label = {'wizdom': 'WIZ', 'ktuvit': 'KTU', 'opensubtitles': 'OPN'}.get(provider, provider[:3].upper())
            
            # Build label text
            label = '{} {}%  {}  [COLOR {}]{}[/COLOR]'.format(
                indicator, score, name, 'FF888888', prov_label
            )
            
            btn = xbmcgui.ControlButton(
                POPUP_X + 10, y, POPUP_W - 20, item_h - 2,
                label, font='font12',
                textColor=score_color,
                focusTexture='', noFocusTexture='',
                focusedColor=COLOR_WHITE,
                alignment=0x00000001  # Right-aligned for Hebrew
            )
            self.addControl(btn)
            self._list_buttons.append((btn, i))
        
        # Set up navigation between buttons
        all_buttons = [b for b, _ in self._list_buttons] + [self._close_btn]
        for i, btn in enumerate(all_buttons):
            if i > 0:
                btn.controlUp(all_buttons[i - 1])
            if i < len(all_buttons) - 1:
                btn.controlDown(all_buttons[i + 1])
        
        # --- Status bar (bottom) ---
        self._status_label = xbmcgui.ControlLabel(
            POPUP_X + 20, POPUP_Y + POPUP_H - 60, POPUP_W - 40, 25,
            '', font='font13', textColor=COLOR_GRAY,
            alignment=0x00000002  # Center
        )
        self.addControl(self._status_label)
        
        # Progress bar background
        self._progress_bg = xbmcgui.ControlImage(
            POPUP_X + 40, POPUP_Y + POPUP_H - 30, POPUP_W - 80, 12,
            '', colorDiffuse='0xFF333344'
        )
        self.addControl(self._progress_bg)
        self._progress_bg.setVisible(False)
        
        # Progress bar fill
        self._progress_fill = xbmcgui.ControlImage(
            POPUP_X + 40, POPUP_Y + POPUP_H - 30, 0, 12,
            '', colorDiffuse=COLOR_CYAN
        )
        self.addControl(self._progress_fill)
        self._progress_fill.setVisible(False)
        
        # Focus first item
        if self._list_buttons:
            self.setFocus(self._list_buttons[0][0])
    
    def _update_status(self, text):
        """Update the status text at the bottom."""
        try:
            self._status_label.setLabel(text)
        except Exception:
            pass
    
    def _update_progress(self, percent):
        """Update the download progress bar."""
        try:
            if percent <= 0:
                self._progress_bg.setVisible(False)
                self._progress_fill.setVisible(False)
                return
            
            self._progress_bg.setVisible(True)
            self._progress_fill.setVisible(True)
            
            fill_width = int((POPUP_W - 80) * (percent / 100.0))
            self._progress_fill.setWidth(max(1, fill_width))
            
            self._update_status('מוריד... {}%'.format(percent))
        except Exception:
            pass
    
    def _download_and_apply(self, index):
        """Download the selected subtitle and apply it to the player."""
        if self._downloading or index >= len(self.subtitles):
            return
        
        self._downloading = True
        sub = self.subtitles[index]
        provider = sub.get('provider', '')
        sub_id = sub.get('subtitle_id', '')
        sub_name = sub.get('subtitle_name', '')
        
        self._update_status('מוריד: {}...'.format(sub_name[:40]))
        self._update_progress(5)
        
        def do_download():
            try:
                path = download_subtitle(
                    provider=provider,
                    subtitle_id=sub_id,
                    api_key=self.api_key,
                    progress_callback=self._update_progress
                )
                
                if path:
                    self.selected_path = path
                    self._update_status('כתוביות הופעלו ✓')
                    self._update_progress(100)
                    
                    # Apply to player
                    if self.player:
                        try:
                            self.player.setSubtitles(path)
                            log('Subtitles applied: {}'.format(path))
                        except Exception as e:
                            log('Failed to apply subs: {}'.format(e), 'ERROR')
                    
                    # Auto-close after 1.5 seconds
                    time.sleep(1.5)
                    self.close()
                else:
                    self._update_status('[COLOR red]שגיאה בהורדה - נסה אחרת[/COLOR]')
                    self._update_progress(0)
                    self._downloading = False
            except Exception as e:
                log('Download thread error: {}'.format(e), 'ERROR')
                self._update_status('[COLOR red]שגיאה: {}[/COLOR]'.format(str(e)[:30]))
                self._update_progress(0)
                self._downloading = False
        
        self._download_thread = threading.Thread(target=do_download, daemon=True)
        self._download_thread.start()
    
    # =================================================================
    # Input handling
    # =================================================================
    
    def onAction(self, action):
        """Handle remote/keyboard input."""
        action_id = action.getId()
        
        # Back / Escape / Close
        if action_id in (92, 10, 110):  # ACTION_NAV_BACK, ACTION_PREVIOUS_MENU, ACTION_BACKSPACE
            if not self._downloading:
                self.close()
            return
        
        # Up/Down navigation is handled by Kodi's control navigation
        # Select / Enter
        if action_id in (7, 100):  # ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK
            self._handle_click()
    
    def onControl(self, control):
        """Handle control click events."""
        # Close button
        if control == self._close_btn:
            if not self._downloading:
                self.close()
            return
        
        # Subtitle list items
        for btn, index in self._list_buttons:
            if control == btn:
                self._download_and_apply(index)
                return
    
    def _handle_click(self):
        """Handle select/enter on focused control."""
        try:
            focused = self.getFocusId()
        except Exception:
            focused = -1
        
        # Check if it's the close button
        try:
            if self.getFocus() == self._close_btn:
                if not self._downloading:
                    self.close()
                return
        except Exception:
            pass
        
        # Check subtitle buttons
        try:
            current_focus = self.getFocus()
            for btn, index in self._list_buttons:
                if current_focus == btn:
                    self._download_and_apply(index)
                    return
        except Exception:
            pass


def show_subtitle_picker(subtitles, player=None, api_key=''):
    """
    Convenience function to show the subtitle picker.
    
    Args:
        subtitles: List of match dicts from HebSubScout
        player: Active xbmc.Player instance
        api_key: OpenSubtitles API key
    
    Returns:
        Path to downloaded subtitle, or None if cancelled
    """
    if not subtitles:
        xbmcgui.Dialog().ok('HebSubScout', 'לא נמצאו כתוביות בעברית')
        return None
    
    picker = SubtitlePickerWindow(subtitles, player, api_key)
    picker.doModal()
    result = picker.selected_path
    del picker
    return result
