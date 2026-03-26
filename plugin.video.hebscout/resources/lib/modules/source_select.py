# -*- coding: utf-8 -*-
"""
Source Selection Screen (WindowXMLDialog)
=========================================
Full-screen source browser with XML skin layout.
Uses Kodi's native ControlList for smooth scrolling and focus handling.
"""

import xbmcgui
import xbmcaddon

from resources.lib.modules.utils import (
    t, get_setting, set_setting, log
)

QUALITY_COLORS = {
    '4K': 'FF9b59b6',
    '1080p': 'FF2ecc71',
    '720p': 'FFe67e22',
    '480p': 'FFe74c3c',
    'SD': 'FF95a5a6',
}

QUALITY_ORDER = {'4K': 0, '1080p': 1, '720p': 2, '480p': 3, 'SD': 4}

# Filter button IDs from XML
QUALITY_BTNS = {3001: '4K', 3002: '1080p', 3003: '720p', 3004: '480p', 3005: 'SD'}
SORT_BTNS = {3006: 'default', 3007: 'size', 3008: 'subs'}


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
    """Source selection using XML skin for native focus/scroll handling."""

    def __new__(cls, xml_file, addon_path, sources, metadata):
        return super().__new__(cls, xml_file, addon_path, 'Default', '1080i')

    def __init__(self, xml_file, addon_path, sources, metadata):
        super().__init__(xml_file, addon_path, 'Default', '1080i')
        self.all_sources = sources
        self.filtered_sources = list(sources)
        self.metadata = metadata or {}
        self.selected_source = None

        # Filter state
        self._quality_filters = set(
            (get_setting('filter_quality') or '4K|1080p|720p|480p|SD').split('|')
        )
        self._sort_by = get_setting('filter_sort') or 'default'

    def onInit(self):
        """Called when the dialog opens. Populate all controls."""
        self._populate_info_panel()
        self._apply_filters()

    def _populate_info_panel(self):
        """Fill the right-side movie info panel."""
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

    def _apply_filters(self):
        """Filter and sort sources, then populate the list control."""
        result = list(self.all_sources)

        # Quality filter
        if self._quality_filters and len(self._quality_filters) < 5:
            result = [s for s in result if s.get('quality', 'SD') in self._quality_filters]

        # Sort within quality tiers
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
        """Fill the ControlList with source items."""
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

                # Sub match display
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
                    sub_display = '[COLOR FFe74c3c]עב ✗[/COLOR]'
                item.setProperty('sub_display', sub_display)

                # Feature tags
                info_tags = src.get('info', [])
                item.setProperty('info_tags', '  '.join(info_tags[:6]))

                # Size + RD
                size_parts = []
                if src.get('rd_cached'):
                    size_parts.append('[COLOR FF3498db]RD[/COLOR]')
                size = src.get('size', '')
                if size:
                    size_parts.append(size)
                item.setProperty('size_display', '  '.join(size_parts))

                items.append(item)

            list_control.addItems(items)

            # Update count label
            try:
                self.getControl(1001).setLabel(
                    '{} sources'.format(len(self.filtered_sources))
                )
            except Exception:
                pass

        except Exception as e:
            log('Source list populate error: {}'.format(e), 'ERROR')

    def onClick(self, controlID):
        """Handle button clicks."""
        # Source list item selected
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

        # Quality filter buttons
        if controlID in QUALITY_BTNS:
            q = QUALITY_BTNS[controlID]
            if q in self._quality_filters:
                self._quality_filters.discard(q)
                if not self._quality_filters:
                    self._quality_filters = set(QUALITY_BTNS.values())
            else:
                self._quality_filters.add(q)
            self._apply_filters()
            return

        # Sort buttons
        if controlID in SORT_BTNS:
            self._sort_by = SORT_BTNS[controlID]
            self._apply_filters()
            return

    def onAction(self, action):
        """Handle back/escape."""
        if action.getId() in (9, 10, 92, 216):
            self.selected_source = None
            self._save_filters()
            self.close()

    def _save_filters(self):
        set_setting('filter_quality', '|'.join(sorted(self._quality_filters)))
        set_setting('filter_sort', self._sort_by)
