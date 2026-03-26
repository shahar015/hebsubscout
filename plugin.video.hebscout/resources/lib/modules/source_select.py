# -*- coding: utf-8 -*-
"""
Source Selection Screen
=======================
Full-screen custom WindowDialog for browsing and selecting sources.
Left panel: filter chips + scrollable source cards.
Right panel: movie/show poster, plot, cast, director, rating.
"""

import xbmc
import xbmcgui

from resources.lib.modules.utils import (
    t, get_setting, set_setting, log, _get_white_texture
)

# Quality color mapping
QUALITY_COLORS = {
    '4K': 'FF9b59b6',      # purple
    '1080p': 'FF2ecc71',   # green
    '720p': 'FFe67e22',    # orange
    '480p': 'FFe74c3c',    # red
    'SD': 'FF95a5a6',      # gray
}

# All feature tags that can appear
ALL_FEATURES = ['DV', 'HDR', 'HDR10', 'HDR10+', 'REMUX', 'Atmos', 'TrueHD', 'DTS-HD', 'DTS']

MAX_VISIBLE_CARDS = 7
CARD_H = 100
CARD_SPACING = 8
CARD_START_Y = 220
CARD_W = 1140
CARD_X = 40


def _parse_size_bytes(size_str):
    """Parse size string like '4.2 GB' or '850 MB' to bytes for sorting."""
    if not size_str:
        return 0
    try:
        parts = size_str.strip().split()
        val = float(parts[0])
        unit = parts[1].upper() if len(parts) > 1 else 'MB'
        if 'GB' in unit:
            return int(val * 1024 * 1024 * 1024)
        elif 'MB' in unit:
            return int(val * 1024 * 1024)
        return int(val)
    except (ValueError, IndexError):
        return 0


class SourceSelectDialog(xbmcgui.WindowDialog):
    """Full-screen source selection with filters, source cards, and movie info."""

    def __init__(self, sources, metadata):
        super().__init__()
        self.tex = _get_white_texture()
        self.all_sources = sources
        self.filtered_sources = list(sources)
        self.metadata = metadata or {}
        self.selected_source = None

        # Filter state (loaded from settings)
        self._quality_filters = set(self._load_filter('filter_quality', '4K|1080p|720p|480p|SD').split('|'))
        self._subs_filter = self._load_filter('filter_subs', 'All')
        self._feature_filters = set(f for f in self._load_filter('filter_features', '').split('|') if f)
        self._sort_by = self._load_filter('filter_sort', 'default')

        # Scroll state
        self._scroll_offset = 0
        self._focused_card = 0
        self._in_filters = True  # True = navigating filters, False = navigating cards
        self._filter_row = 0
        self._filter_col = 0

        # Controls tracking
        self._card_buttons = []
        self._card_controls = []  # all controls for current visible cards
        self._chip_buttons = {}   # {(row, col): ControlButton}
        self._all_controls = []

        self._build_ui()
        self._apply_filters()

    def _load_filter(self, key, default):
        return get_setting(key) or default

    def _save_filters(self):
        set_setting('filter_quality', '|'.join(sorted(self._quality_filters)))
        set_setting('filter_subs', self._subs_filter)
        set_setting('filter_features', '|'.join(sorted(self._feature_filters)))
        set_setting('filter_sort', self._sort_by)

    # =====================================================================
    # UI BUILDING
    # =====================================================================

    def _build_ui(self):
        """Build the full-screen UI."""
        # Full-screen solid black background (fully opaque)
        self.addControl(xbmcgui.ControlImage(0, 0, 1920, 1080, self.tex, colorDiffuse='FF000000'))
        # Slightly lighter content area
        self.addControl(xbmcgui.ControlImage(0, 0, 1920, 1080, self.tex, colorDiffuse='FF0a0a1a'))

        # -- FILTER CHIPS --
        self._build_filter_chips()

        # -- Divider line --
        self.addControl(xbmcgui.ControlImage(40, 205, 1140, 2, self.tex, colorDiffuse='FF333355'))

        # -- RIGHT PANEL: Movie info --
        self._build_info_panel()

    def _build_filter_chips(self):
        """Build the 4 rows of filter chips."""
        self._chip_controls = []  # Track for rebuild
        self._chip_buttons = {}
        y_base = 20
        row_h = 42
        chip_h = 32
        chip_spacing = 8

        # Row 0: Quality filters (multi-select)
        self._add_chip_label(40, y_base, t('quality'))
        x = 160
        for i, q in enumerate(['4K', '1080p', '720p', '480p', 'SD']):
            active = q in self._quality_filters
            btn = self._make_chip(x, y_base, 90, chip_h, q, active, QUALITY_COLORS.get(q, 'FF888888'))
            self._chip_buttons[(0, i)] = btn
            x += 90 + chip_spacing

        # Row 1: Subtitle filters (single-select)
        y = y_base + row_h
        self._add_chip_label(40, y, 'Subs')
        x = 160
        for i, (label, val) in enumerate([('100%', '100'), ('>75%', '75'), ('>50%', '50'), ('All', 'All')]):
            active = self._subs_filter == val
            btn = self._make_chip(x, y, 80, chip_h, label, active, 'FF3498db')
            self._chip_buttons[(1, i)] = btn
            x += 80 + chip_spacing

        # Row 2: Feature filters (multi-select)
        y = y_base + row_h * 2
        self._add_chip_label(40, y, 'Features')
        x = 160
        for i, feat in enumerate(ALL_FEATURES):
            active = feat in self._feature_filters
            btn = self._make_chip(x, y, 85, chip_h, feat, active, 'FFe67e22')
            self._chip_buttons[(2, i)] = btn
            x += 85 + chip_spacing

        # Row 3: Sort by (single-select)
        y = y_base + row_h * 3
        self._add_chip_label(40, y, 'Sort')
        x = 160
        for i, (label, val) in enumerate([('Size', 'size'), ('Sub %', 'subs'), ('Default', 'default')]):
            active = self._sort_by == val
            btn = self._make_chip(x, y, 90, chip_h, label, active, 'FF9b59b6')
            self._chip_buttons[(3, i)] = btn
            x += 90 + chip_spacing

    def _add_chip_label(self, x, y, text):
        label = xbmcgui.ControlLabel(x, y + 4, 110, 30, text, font='font12', textColor='FF888888')
        self.addControl(label)
        self._chip_controls.append(label)

    def _make_chip(self, x, y, w, h, text, active, color):
        """Create a filter chip as a colored label on a background."""
        if active:
            label_text = '[COLOR {}]{}[/COLOR]'.format(color, text)
            bg_color = 'FF222244'
            border_color = color
        else:
            label_text = '[COLOR FF666666]{}[/COLOR]'.format(text)
            bg_color = 'FF151530'
            border_color = 'FF333355'

        # Single background (no layering issues)
        bg = xbmcgui.ControlImage(x, y, w, h, self.tex, colorDiffuse=bg_color)
        self.addControl(bg)
        self._chip_controls.append(bg)

        # Text label centered
        lbl = xbmcgui.ControlLabel(x, y + 2, w, h - 4, label_text, font='font12', alignment=0x00000002)
        self.addControl(lbl)
        self._chip_controls.append(lbl)

        # Invisible button for focus
        btn = xbmcgui.ControlButton(x, y, w, h, '', focusTexture='', noFocusTexture='')
        self.addControl(btn)
        self._chip_controls.append(btn)

        return btn

    def _build_info_panel(self):
        """Build right panel with poster, plot, cast."""
        rx = 1260
        rw = 600

        # Poster
        poster_url = self.metadata.get('poster', '')
        if poster_url:
            self.addControl(xbmcgui.ControlImage(rx + 90, 20, 380, 540, poster_url))

        # Title
        title = self.metadata.get('title', '')
        year = self.metadata.get('year', '')
        title_text = '{} ({})'.format(title, year) if year else title
        self.addControl(xbmcgui.ControlLabel(
            rx, 570, rw, 35, '[COLOR FFffffff]{}[/COLOR]'.format(title_text),
            font='font13', alignment=0x00000002
        ))

        # Rating
        rating = self.metadata.get('rating', 0)
        if rating:
            self.addControl(xbmcgui.ControlLabel(
                rx, 605, rw, 25, '[COLOR FFf1c40f]{:.1f} / 10[/COLOR]'.format(float(rating)),
                font='font12', alignment=0x00000002
            ))

        # Genres
        genres = self.metadata.get('genres', [])
        if genres:
            genre_text = ' | '.join(genres[:4])
            self.addControl(xbmcgui.ControlLabel(
                rx, 630, rw, 25, '[COLOR FF888888]{}[/COLOR]'.format(genre_text),
                font='font12', alignment=0x00000002
            ))

        # Plot
        plot = self.metadata.get('plot', '')
        if plot:
            plot_box = xbmcgui.ControlTextBox(rx + 20, 665, rw - 40, 150, font='font12', textColor='FFcccccc')
            self.addControl(plot_box)
            plot_box.setText(plot)

        # Director
        director = self.metadata.get('director', '')
        if director:
            self.addControl(xbmcgui.ControlLabel(
                rx, 825, rw, 25, '[COLOR FF888888]Director:[/COLOR] {}'.format(director),
                font='font12'
            ))

        # Cast chips
        cast = self.metadata.get('cast', [])
        if cast:
            self.addControl(xbmcgui.ControlLabel(
                rx, 855, rw, 25, '[COLOR FF888888]Cast:[/COLOR]',
                font='font12'
            ))
            cx = rx + 10
            cy = 882
            for name in cast[:8]:
                chip_w = len(name) * 9 + 20
                if cx + chip_w > rx + rw:
                    cx = rx + 10
                    cy += 30
                # Chip background
                self.addControl(xbmcgui.ControlImage(cx, cy, chip_w, 24, self.tex, colorDiffuse='FF222244'))
                self.addControl(xbmcgui.ControlLabel(
                    cx, cy + 1, chip_w, 22, '[COLOR FFcccccc]{}[/COLOR]'.format(name),
                    font='font10', alignment=0x00000002
                ))
                cx += chip_w + 6

    # =====================================================================
    # SOURCE CARD RENDERING
    # =====================================================================

    def _clear_cards(self):
        """Remove all current card controls."""
        for ctrl in self._card_controls:
            try:
                self.removeControl(ctrl)
            except Exception:
                pass
        self._card_controls = []
        self._card_buttons = []

    def _render_cards(self):
        """Render visible source cards based on scroll offset."""
        self._clear_cards()

        visible = self.filtered_sources[self._scroll_offset:self._scroll_offset + MAX_VISIBLE_CARDS]
        for i, src in enumerate(visible):
            abs_idx = self._scroll_offset + i
            focused = (not self._in_filters and abs_idx == self._focused_card)
            self._render_one_card(src, i, focused)

        # Source count label
        count_lbl = xbmcgui.ControlLabel(
            40, CARD_START_Y - 20, CARD_W, 18,
            '[COLOR FF888888]{} {}[/COLOR]'.format(len(self.filtered_sources), t('found_sources', '').strip()),
            font='font10'
        )
        self.addControl(count_lbl)
        self._card_controls.append(count_lbl)

    def _render_one_card(self, src, vis_idx, focused):
        """Render a single source card."""
        y = CARD_START_Y + vis_idx * (CARD_H + CARD_SPACING)
        x = CARD_X
        quality = src.get('quality', 'SD')
        q_color = QUALITY_COLORS.get(quality, 'FF888888')

        # Card dimensions (scale up if focused)
        if focused:
            cw, ch = CARD_W + 10, CARD_H + 8
            cx, cy = x - 5, y - 4
            bg_color = 'FF1a1a3e'
            border_color = q_color
        else:
            cw, ch = CARD_W, CARD_H
            cx, cy = x, y
            bg_color = 'FF111128'
            border_color = 'FF222244'

        # Border
        border = xbmcgui.ControlImage(cx - 2, cy - 2, cw + 4, ch + 4, self.tex, colorDiffuse=border_color)
        self.addControl(border)
        self._card_controls.append(border)

        # Background
        bg = xbmcgui.ControlImage(cx, cy, cw, ch, self.tex, colorDiffuse=bg_color)
        self.addControl(bg)
        self._card_controls.append(bg)

        # Quality badge (left side)
        badge_w = 65
        badge = xbmcgui.ControlImage(cx, cy, badge_w, ch, self.tex, colorDiffuse=q_color)
        self.addControl(badge)
        self._card_controls.append(badge)

        q_label = xbmcgui.ControlLabel(
            cx, cy + (ch - 25) // 2, badge_w, 25, quality,
            font='font12', textColor='FFffffff', alignment=0x00000002
        )
        self.addControl(q_label)
        self._card_controls.append(q_label)

        # Content area (right of badge)
        content_x = cx + badge_w + 12
        content_w = cw - badge_w - 24

        # Row 1: Provider (left) + Sub match % (right)
        provider = src.get('provider', '').capitalize()
        sub_pct = src.get('best_match_pct', 0)
        has_subs = src.get('has_hebrew_subs', False)

        prov_lbl = xbmcgui.ControlLabel(
            content_x, cy + 5, content_w // 2, 20,
            '[COLOR FF888888]{}[/COLOR]'.format(provider), font='font10'
        )
        self.addControl(prov_lbl)
        self._card_controls.append(prov_lbl)

        if has_subs:
            if sub_pct >= 90:
                sub_color = 'FF2ecc71'
            elif sub_pct >= 70:
                sub_color = 'FFf1c40f'
            else:
                sub_color = 'FFe67e22'
            sub_text = '[COLOR {}]עב {}%[/COLOR]'.format(sub_color, sub_pct)
        else:
            sub_text = '[COLOR FFe74c3c]עב ✗[/COLOR]'

        sub_lbl = xbmcgui.ControlLabel(
            content_x + content_w - 100, cy + 5, 100, 20,
            sub_text, font='font12', alignment=0x00000001  # right align
        )
        self.addControl(sub_lbl)
        self._card_controls.append(sub_lbl)

        # Row 2: Filename
        name = src.get('name', 'Unknown')
        if len(name) > 80:
            name = name[:77] + '...'
        name_lbl = xbmcgui.ControlLabel(
            content_x, cy + 26, content_w, 20,
            '[COLOR FFdddddd]{}[/COLOR]'.format(name), font='font10'
        )
        self.addControl(name_lbl)
        self._card_controls.append(name_lbl)

        # Row 3: Feature tags
        info_tags = src.get('info', [])
        if info_tags:
            tags_text = '  '.join('[COLOR FFaaaaaa]{}[/COLOR]'.format(tag) for tag in info_tags[:6])
            tags_lbl = xbmcgui.ControlLabel(content_x, cy + 48, content_w, 18, tags_text, font='font10')
            self.addControl(tags_lbl)
            self._card_controls.append(tags_lbl)

        # Row 4: File size + RD cached
        size = src.get('size', '')
        rd_cached = src.get('rd_cached', False)
        bottom_parts = []
        if rd_cached:
            bottom_parts.append('[COLOR FF3498db]RD[/COLOR]')
        if size:
            bottom_parts.append('[COLOR FF888888]{}[/COLOR]'.format(size))
        if bottom_parts:
            size_lbl = xbmcgui.ControlLabel(content_x, cy + 68, content_w, 18,
                                             '  '.join(bottom_parts), font='font10')
            self.addControl(size_lbl)
            self._card_controls.append(size_lbl)

        # Invisible button for selection
        btn = xbmcgui.ControlButton(cx, cy, cw, ch, '', focusTexture='', noFocusTexture='')
        self.addControl(btn)
        self._card_controls.append(btn)
        self._card_buttons.append(btn)

    # =====================================================================
    # FILTERING & SORTING
    # =====================================================================

    def _apply_filters(self):
        """Filter and sort sources based on current filter state."""
        result = list(self.all_sources)

        # Quality filter
        if self._quality_filters and len(self._quality_filters) < 5:
            result = [s for s in result if s.get('quality', 'SD') in self._quality_filters]

        # Subtitle filter
        if self._subs_filter == '100':
            result = [s for s in result if s.get('best_match_pct', 0) >= 95]
        elif self._subs_filter == '75':
            result = [s for s in result if s.get('best_match_pct', 0) >= 75]
        elif self._subs_filter == '50':
            result = [s for s in result if s.get('best_match_pct', 0) >= 50]

        # Feature filter ("at least" logic — show if source has ANY of the selected features)
        if self._feature_filters:
            result = [s for s in result if
                      any(f in s.get('info', []) for f in self._feature_filters)]

        # Sort within quality tiers
        quality_order = {'4K': 0, '1080p': 1, '720p': 2, '480p': 3, 'SD': 4}

        if self._sort_by == 'size':
            result.sort(key=lambda s: (quality_order.get(s.get('quality', 'SD'), 9),
                                       -_parse_size_bytes(s.get('size', ''))))
        elif self._sort_by == 'subs':
            result.sort(key=lambda s: (quality_order.get(s.get('quality', 'SD'), 9),
                                       -s.get('best_match_pct', 0)))
        else:
            result.sort(key=lambda s: (quality_order.get(s.get('quality', 'SD'), 9),
                                       0 if s.get('rd_cached') else 1))

        self.filtered_sources = result
        self._scroll_offset = 0
        self._focused_card = 0
        self._render_cards()

    # =====================================================================
    # CHIP TOGGLE LOGIC
    # =====================================================================

    def _toggle_chip(self, row, col):
        """Handle chip toggle at (row, col)."""
        if row == 0:  # Quality (multi-select)
            qualities = ['4K', '1080p', '720p', '480p', 'SD']
            q = qualities[col]
            if q in self._quality_filters:
                self._quality_filters.discard(q)
                if not self._quality_filters:
                    self._quality_filters = set(qualities)  # can't deselect all
            else:
                self._quality_filters.add(q)
        elif row == 1:  # Subs (single-select)
            vals = ['100', '75', '50', 'All']
            self._subs_filter = vals[col]
        elif row == 2:  # Features (multi-select)
            feat = ALL_FEATURES[col]
            if feat in self._feature_filters:
                self._feature_filters.discard(feat)
            else:
                self._feature_filters.add(feat)
        elif row == 3:  # Sort (single-select)
            vals = ['size', 'subs', 'default']
            self._sort_by = vals[col]

        self._save_filters()
        # Rebuild filter chips visually (simplest: rebuild entire UI)
        self._rebuild_chips()
        self._apply_filters()

    def _rebuild_chips(self):
        """Remove old chip controls and rebuild with updated state."""
        for ctrl in self._chip_controls:
            try:
                self.removeControl(ctrl)
            except Exception:
                pass
        self._chip_controls = []
        self._chip_buttons = {}
        self._build_filter_chips()

    # =====================================================================
    # NAVIGATION
    # =====================================================================

    def _get_filter_row_len(self, row):
        if row == 0:
            return 5  # qualities
        elif row == 1:
            return 4  # subs
        elif row == 2:
            return len(ALL_FEATURES)
        elif row == 3:
            return 3  # sort
        return 0

    def onAction(self, action):
        action_id = action.getId()

        # Close on back/escape
        if action_id in (9, 10, 92, 216):
            self.selected_source = None
            self._save_filters()
            self.close()
            return

        # Select/Enter
        if action_id in (7, 100):  # ACTION_SELECT_ITEM, ACTION_MOUSE_LEFT_CLICK
            if self._in_filters:
                self._toggle_chip(self._filter_row, self._filter_col)
            else:
                if self.filtered_sources and 0 <= self._focused_card < len(self.filtered_sources):
                    self.selected_source = self.filtered_sources[self._focused_card]
                    self._save_filters()
                    self.close()
            return

        # Navigation
        if action_id == 3:  # UP
            if self._in_filters:
                if self._filter_row > 0:
                    self._filter_row -= 1
                    self._filter_col = min(self._filter_col, self._get_filter_row_len(self._filter_row) - 1)
            else:
                if self._focused_card > 0:
                    old_offset = self._scroll_offset
                    self._focused_card -= 1
                    if self._focused_card < self._scroll_offset:
                        self._scroll_offset = self._focused_card
                    if self._scroll_offset != old_offset:
                        self._render_cards()
                else:
                    self._in_filters = True
                    self._filter_row = 3

        elif action_id == 4:  # DOWN
            if self._in_filters:
                if self._filter_row < 3:
                    self._filter_row += 1
                    self._filter_col = min(self._filter_col, self._get_filter_row_len(self._filter_row) - 1)
                else:
                    self._in_filters = False
                    self._focused_card = self._scroll_offset
            else:
                if self._focused_card < len(self.filtered_sources) - 1:
                    old_offset = self._scroll_offset
                    self._focused_card += 1
                    if self._focused_card >= self._scroll_offset + MAX_VISIBLE_CARDS:
                        self._scroll_offset = self._focused_card - MAX_VISIBLE_CARDS + 1
                    if self._scroll_offset != old_offset:
                        self._render_cards()

        elif action_id == 1:  # LEFT
            if self._in_filters and self._filter_col > 0:
                self._filter_col -= 1

        elif action_id == 2:  # RIGHT
            if self._in_filters:
                max_col = self._get_filter_row_len(self._filter_row) - 1
                if self._filter_col < max_col:
                    self._filter_col += 1
