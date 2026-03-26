# -*- coding: utf-8 -*-
"""
Source Selection Screen (WindowXMLDialog)
=========================================
Uses XML skin for ControlList (native scroll/focus) and right panel.
Filter buttons are created dynamically by Python in onInit for proper sizing.
"""

import xbmcgui
import xbmcaddon

from resources.lib.modules.utils import (
    t, get_setting, set_setting, log, is_hebrew
)

QUALITY_COLORS = {
    '4K': 'FF9b59b6',
    '1080p': 'FF2ecc71',
    '720p': 'FFe67e22',
    '480p': 'FFe74c3c',
    'SD': 'FF95a5a6',
}
QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, '480p': 3, 'SD': 4}

# Approximate character width for font12 (in 1080i pixels)
CHAR_W = 11
CHIP_H = 36
CHIP_GAP = 8
CHIP_PAD = 24  # padding inside button (left+right)
ROW_H = 46
LABEL_X = 40
CHIP_START_X = 150


def _text_width(text):
    """Estimate pixel width for a text string in font12."""
    return len(text) * CHAR_W + CHIP_PAD


def _parse_size_bytes(size_str):
    if not size_str:
        return 0
    try:
        parts = size_str.strip().split()
        val = float(parts[0])
        unit = parts[1].upper() if len(parts) > 1 else 'MB'
        if 'GB' in unit:
            return int(val * 1024 * 1024 * 1024)
        return int(val * 1024 * 1024)
    except (ValueError, IndexError):
        return 0


class SourceSelectDialog(xbmcgui.WindowXMLDialog):

    def __new__(cls, xml_file, addon_path, sources, metadata):
        return super().__new__(cls, xml_file, addon_path, 'Default', '1080i')

    def __init__(self, xml_file, addon_path, sources, metadata):
        super().__init__(xml_file, addon_path, 'Default', '1080i')
        self.all_sources = sources
        self.filtered_sources = list(sources)
        self.metadata = metadata or {}
        self.selected_source = None

        # Filter state
        saved_q = get_setting('filter_quality') or ''
        self._quality_filters = set(q for q in saved_q.split('|') if q) if saved_q else set()
        self._sort_by = get_setting('filter_sort') or 'default'
        saved_p = get_setting('filter_providers') or ''
        self._provider_filters = set(p for p in saved_p.split('|') if p) if saved_p else set()

        # Collect unique providers from sources
        self._available_providers = sorted(set(
            s.get('provider', '') for s in sources if s.get('provider')
        ))

        # Dynamic button tracking: {control_id: (type, value)}
        self._btn_map = {}
        self._btn_controls = []
        self._label_controls = []
        self._next_id = 5000  # Start above XML control IDs

    def onInit(self):
        self._build_filter_rows()
        self._populate_info_panel()
        self._apply_filters()

    # ==================================================================
    # DYNAMIC FILTER BUTTONS
    # ==================================================================

    def _build_filter_rows(self):
        """Create all filter buttons dynamically with auto-sized widths."""
        he = is_hebrew()
        y = 20
        last_row_btns = []

        # Row 1: Quality
        row1_label = 'איכות' if he else 'Quality'
        qualities = [('4K', '4K'), ('1080p', '1080p'), ('720p', '720p'), ('480p', '480p'), ('SD', 'SD')]
        row1_btns = self._create_chip_row(y, row1_label, qualities, 'quality')
        y += ROW_H

        # Row 2: Sort
        row2_label = 'מיון' if he else 'Sort'
        sort_items = [
            ('ברירת מחדל' if he else 'Default', 'default'),
            ('גודל' if he else 'Size', 'size'),
            ('כתוביות %' if he else 'Sub %', 'subs'),
        ]
        row2_btns = self._create_chip_row(y, row2_label, sort_items, 'sort')
        y += ROW_H

        # Row 3: Provider
        row3_label = 'מקור' if he else 'Source'
        prov_items = [(p.capitalize(), p) for p in self._available_providers]
        row3_btns = self._create_chip_row(y, row3_label, prov_items, 'provider') if prov_items else []
        if row3_btns:
            last_row_btns = row3_btns
            y += ROW_H
        else:
            last_row_btns = row2_btns

        # Update source count + divider position
        try:
            self.getControl(1001).setPosition(LABEL_X, y)
            self.getControl(1002).setPosition(LABEL_X, y + 27)
            self.getControl(1000).setPosition(LABEL_X, y + 35)
            self.getControl(1000).setHeight(1080 - y - 45)
        except Exception as e:
            log('Filter layout error: {}'.format(e), 'ERROR')

        # Set up/down navigation between rows
        self._link_rows(row1_btns, row2_btns)
        self._link_rows(row2_btns, row3_btns if row3_btns else None)
        if row3_btns:
            self._link_rows(row3_btns, None)

        # Link last filter row ↔ source list
        list_ctrl = self.getControl(1000)
        for btn in last_row_btns:
            btn.controlDown(list_ctrl)

        # Update visual state
        self._update_chip_visuals()

    def _create_chip_row(self, y, label_text, items, chip_type):
        """Create a row label + buttons. Returns list of button controls."""
        # Row label
        lbl = xbmcgui.ControlLabel(LABEL_X, y + 5, 100, 30,
                                    '[COLOR FF888888]{}[/COLOR]'.format(label_text),
                                    font='font12')
        self.addControl(lbl)
        self._label_controls.append(lbl)

        buttons = []
        x = CHIP_START_X
        for display_text, value in items:
            w = _text_width(display_text)
            btn = xbmcgui.ControlButton(
                x, y, w, CHIP_H, display_text,
                font='font12',
                focusTexture='white.png', noFocusTexture='white.png',
                focusedColor='FFffffff', textColor='FFcccccc',
            )
            self.addControl(btn)
            btn_id = self._next_id
            self._next_id += 1
            self._btn_map[id(btn)] = (chip_type, value)
            self._btn_controls.append(btn)
            buttons.append(btn)
            x += w + CHIP_GAP

        # Link left/right within row
        for i, btn in enumerate(buttons):
            if i > 0:
                btn.controlLeft(buttons[i - 1])
            if i < len(buttons) - 1:
                btn.controlRight(buttons[i + 1])

        return buttons

    def _link_rows(self, upper_btns, lower_btns):
        """Link up/down navigation between two rows of buttons."""
        if not upper_btns:
            return
        if lower_btns:
            for btn in upper_btns:
                btn.controlDown(lower_btns[0])
            for btn in lower_btns:
                btn.controlUp(upper_btns[0])

    def _update_chip_visuals(self):
        """Update all chip button labels to reflect selected state."""
        he = is_hebrew()
        sort_labels = {
            'default': 'ברירת מחדל' if he else 'Default',
            'size': 'גודל' if he else 'Size',
            'subs': 'כתוביות %' if he else 'Sub %',
        }

        for btn in self._btn_controls:
            key = id(btn)
            if key not in self._btn_map:
                continue
            chip_type, value = self._btn_map[key]

            if chip_type == 'quality':
                color = QUALITY_COLORS.get(value, 'FFcccccc')
                if value in self._quality_filters:
                    btn.setLabel('[COLOR {}][B]{}[/B][/COLOR]'.format(color, value))
                else:
                    btn.setLabel('[COLOR FF666666]{}[/COLOR]'.format(value))

            elif chip_type == 'sort':
                label = sort_labels.get(value, value)
                if self._sort_by == value:
                    btn.setLabel('[COLOR FF9b59b6][B]{}[/B][/COLOR]'.format(label))
                else:
                    btn.setLabel('[COLOR FF666666]{}[/COLOR]'.format(label))

            elif chip_type == 'provider':
                display = value.capitalize()
                if value in self._provider_filters:
                    btn.setLabel('[COLOR FF3498db][B]{}[/B][/COLOR]'.format(display))
                else:
                    btn.setLabel('[COLOR FF666666]{}[/COLOR]'.format(display))

    # ==================================================================
    # INFO PANEL
    # ==================================================================

    def _populate_info_panel(self):
        meta = self.metadata
        try:
            poster = meta.get('poster', '')
            if poster:
                self.getControl(2000).setImage(poster)

            title = meta.get('title', '')
            year = meta.get('year', '')
            self.getControl(2001).setLabel(
                '{} ({})'.format(title, year) if year else title
            )

            rating = meta.get('rating', 0)
            if rating:
                self.getControl(2002).setLabel('{:.1f} / 10'.format(float(rating)))

            genres = meta.get('genres', [])
            if genres:
                self.getControl(2003).setLabel(' | '.join(genres[:4]))

            plot = meta.get('plot', '')
            if plot:
                self.getControl(2004).setText(plot)

            director = meta.get('director', '')
            if director:
                self.getControl(2005).setLabel('[COLOR FF888888]Director:[/COLOR] {}'.format(director))

            cast = meta.get('cast', [])
            if cast:
                self.getControl(2006).setText(', '.join(cast[:10]))
        except Exception as e:
            log('Info panel error: {}'.format(e), 'ERROR')

    # ==================================================================
    # FILTERING & SOURCE LIST
    # ==================================================================

    def _apply_filters(self):
        result = list(self.all_sources)

        if self._quality_filters:
            result = [s for s in result if s.get('quality', 'SD') in self._quality_filters]

        if self._provider_filters:
            result = [s for s in result if s.get('provider', '') in self._provider_filters]

        if self._sort_by == 'size':
            result.sort(key=lambda s: (
                QUALITY_ORDER.get(s.get('quality', 'SD'), 9),
                -_parse_size_bytes(s.get('size', ''))
            ))
        elif self._sort_by == 'subs':
            result.sort(key=lambda s: (
                QUALITY_ORDER.get(s.get('quality', 'SD'), 9),
                -s.get('best_match_pct', 0)
            ))
        else:
            result.sort(key=lambda s: (
                QUALITY_ORDER.get(s.get('quality', 'SD'), 9),
                0 if s.get('rd_cached') else 1
            ))

        self.filtered_sources = result
        self._populate_source_list()

    def _populate_source_list(self):
        try:
            list_control = self.getControl(1000)
            list_control.reset()

            items = []
            for src in self.filtered_sources:
                item = xbmcgui.ListItem(label=src.get('name', 'Unknown'))
                quality = src.get('quality', 'SD')
                item.setProperty('quality', quality)
                item.setProperty('quality_color', QUALITY_COLORS.get(quality, 'FF888888'))
                item.setProperty('provider', src.get('provider', '').capitalize())

                sub_pct = src.get('best_match_pct', 0)
                has_subs = src.get('has_hebrew_subs', False)
                if has_subs:
                    if sub_pct >= 90:
                        sub_display = '[COLOR FF2ecc71]עב {}%[/COLOR]'.format(sub_pct)
                    elif sub_pct >= 70:
                        sub_display = '[COLOR FFf1c40f]עב {}%[/COLOR]'.format(sub_pct)
                    else:
                        sub_display = '[COLOR FFe67e22]עב {}%[/COLOR]'.format(sub_pct)
                else:
                    sub_display = '[COLOR FFe74c3c]עב X[/COLOR]'
                item.setProperty('sub_display', sub_display)
                item.setProperty('info_tags', '  '.join(src.get('info', [])[:6]))

                size_parts = []
                if src.get('rd_cached'):
                    size_parts.append('[COLOR FF3498db]RD[/COLOR]')
                size = src.get('size', '')
                if size:
                    size_parts.append(size)
                item.setProperty('size_display', '  '.join(size_parts))
                items.append(item)

            list_control.addItems(items)

            try:
                self.getControl(1001).setLabel('{} sources'.format(len(self.filtered_sources)))
            except Exception:
                pass
        except Exception as e:
            log('Source list populate error: {}'.format(e), 'ERROR')

    # ==================================================================
    # EVENT HANDLERS
    # ==================================================================

    def onClick(self, controlID):
        # Source list selection
        if controlID == 1000:
            try:
                idx = self.getControl(1000).getSelectedPosition()
                if 0 <= idx < len(self.filtered_sources):
                    self.selected_source = self.filtered_sources[idx]
                    self._save_filters()
                    self.close()
            except Exception:
                pass
            return

    def onControl(self, control):
        """Handle clicks on dynamically created buttons."""
        key = id(control)
        if key not in self._btn_map:
            return

        chip_type, value = self._btn_map[key]

        if chip_type == 'quality':
            if value in self._quality_filters:
                self._quality_filters.discard(value)
            else:
                self._quality_filters.add(value)

        elif chip_type == 'sort':
            self._sort_by = value

        elif chip_type == 'provider':
            if value in self._provider_filters:
                self._provider_filters.discard(value)
            else:
                self._provider_filters.add(value)

        self._update_chip_visuals()
        self._apply_filters()

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 216):
            self.selected_source = None
            self._save_filters()
            self.close()

    def _save_filters(self):
        set_setting('filter_quality', '|'.join(sorted(self._quality_filters)))
        set_setting('filter_sort', self._sort_by)
        set_setting('filter_providers', '|'.join(sorted(self._provider_filters)))
