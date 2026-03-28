# -*- coding: utf-8 -*-
"""
Source Selection Screen (WindowXMLDialog)
=========================================
XML skin handles layout + ControlList (native scroll/focus).
Python populates data and manages filter button labels.
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

# XML button IDs
QUALITY_BTNS = {3001: '4K', 3002: '1080p', 3003: '720p', 3004: '480p', 3005: 'SD'}
SORT_BTNS = {3006: 'default', 3007: 'size', 3008: 'subs'}
PROVIDER_BTNS = {3009: 'torrentio', 3010: 'mediafusion'}
FEATURE_BTNS = {3020: 'DV', 3021: 'HDR', 3022: 'Atmos', 3023: 'REMUX', 3024: 'H.265'}


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

        # Filter state (default = all qualities selected)
        saved_q = get_setting('filter_quality')
        if saved_q:
            self._quality_filters = set(q for q in saved_q.split('|') if q)
        else:
            self._quality_filters = {'4K', '1080p', '720p', '480p', 'SD'}
        self._sort_by = get_setting('filter_sort') or 'default'
        saved_p = get_setting('filter_providers') or ''
        self._provider_filters = set(p for p in saved_p.split('|') if p) if saved_p else set()
        saved_f = get_setting('filter_features') or ''
        self._feature_filters = set(f for f in saved_f.split('|') if f) if saved_f else set()

    def onInit(self):
        self._sync_labels()
        self._populate_info_panel()
        self._apply_filters()
        # Focus the source list
        try:
            self.setFocusId(1000)
        except Exception:
            pass

    # ==================================================================
    # FILTER LABEL MANAGEMENT
    # ==================================================================

    def _sync_labels(self):
        """Update all button labels and row labels based on current state."""
        he = is_hebrew()

        # Row labels
        try:
            self.getControl(4001).setLabel('{}:'.format('איכות' if he else 'QUALITY'))
            self.getControl(4002).setLabel('{}:'.format('מיון' if he else 'SORT'))
            self.getControl(4003).setLabel('{}:'.format('מקור' if he else 'SOURCE'))
        except Exception:
            pass

        # Quality buttons (selected = bright color, unselected = dim)
        for btn_id, quality in QUALITY_BTNS.items():
            try:
                ctrl = self.getControl(btn_id)
                color = QUALITY_COLORS.get(quality, 'FFcccccc')
                if quality in self._quality_filters:
                    ctrl.setLabel('[COLOR {}]{}[/COLOR]'.format(color, quality))
                else:
                    ctrl.setLabel('[COLOR FF333345]{}[/COLOR]'.format(quality))
            except Exception:
                pass

        # Sort buttons
        sort_labels = {
            'default': 'ברירת מחדל' if he else 'Default',
            'size': 'גודל קובץ' if he else 'File Size',
            'subs': 'אחוזי התאמת כתוביות' if he else 'Sub Match %',
        }
        for btn_id, sort_val in SORT_BTNS.items():
            try:
                ctrl = self.getControl(btn_id)
                label = sort_labels.get(sort_val, sort_val)
                if self._sort_by == sort_val:
                    ctrl.setLabel('[COLOR FF9b59b6]{}[/COLOR]'.format(label))
                else:
                    ctrl.setLabel('[COLOR FF333345]{}[/COLOR]'.format(label))
            except Exception:
                pass

        # Provider buttons
        for btn_id, prov in PROVIDER_BTNS.items():
            try:
                ctrl = self.getControl(btn_id)
                display = prov.capitalize()
                if prov in self._provider_filters:
                    ctrl.setLabel('[COLOR FF3498db]{}[/COLOR]'.format(display))
                else:
                    ctrl.setLabel('[COLOR FF333345]{}[/COLOR]'.format(display))
            except Exception:
                pass

        # Feature filter row label
        try:
            self.getControl(4004).setLabel('{}:'.format('תכונות' if he else 'FEATURES'))
        except Exception:
            pass

        # Feature buttons
        for btn_id, feat in FEATURE_BTNS.items():
            try:
                ctrl = self.getControl(btn_id)
                if feat in self._feature_filters:
                    ctrl.setLabel('[COLOR FFe67e22]{}[/COLOR]'.format(feat))
                else:
                    ctrl.setLabel('[COLOR FF333345]{}[/COLOR]'.format(feat))
            except Exception:
                pass

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
                self.getControl(2003).setLabel(' · '.join(genres[:4]))

            plot = meta.get('plot', '')
            if plot:
                self.getControl(2004).setText(plot)

            director = meta.get('director', '')
            if director:
                he = is_hebrew()
                lbl = 'במאי: {}' if he else 'Director: {}'
                self.getControl(2005).setLabel(lbl.format(director))

            cast = meta.get('cast', [])
            if cast:
                self.getControl(2006).setText(' · '.join(cast[:10]))
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

        # Feature filter: source must have AT LEAST all selected features
        if self._feature_filters:
            def _has_features(src):
                src_info = set(src.get('info', []))
                # Also check for partial matches (e.g. 'HDR' matches 'HDR10', 'HDR10+')
                for feat in self._feature_filters:
                    if not any(feat in tag or tag in feat for tag in src_info):
                        return False
                return True
            result = [s for s in result if _has_features(s)]

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
                item.setProperty('provider', src.get('provider', '').upper())

                sub_pct = src.get('best_match_pct', 0)
                has_subs = src.get('has_hebrew_subs', False)
                he = is_hebrew()
                if has_subs:
                    sub_text = '{}% התאמה לכתוביות'.format(sub_pct) if he else '{}% Sub Match'.format(sub_pct)
                    if sub_pct >= 90:
                        sub_display = '[COLOR FF2ecc71]{}[/COLOR]'.format(sub_text)
                    elif sub_pct >= 70:
                        sub_display = '[COLOR FFe5a84b]{}[/COLOR]'.format(sub_text)
                    else:
                        sub_display = '[COLOR FFe67e22]{}[/COLOR]'.format(sub_text)
                else:
                    sub_display = '[COLOR FF3a3a50]--[/COLOR]'
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
                he = is_hebrew()
                count_text = '{} מקורות'.format(len(self.filtered_sources)) if he else '{} sources'.format(len(self.filtered_sources))
                self.getControl(1001).setLabel(count_text)
            except Exception:
                pass
        except Exception as e:
            log('Source list error: {}'.format(e), 'ERROR')

    # ==================================================================
    # EVENTS
    # ==================================================================

    def onClick(self, controlID):
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

        if controlID in QUALITY_BTNS:
            q = QUALITY_BTNS[controlID]
            if q in self._quality_filters:
                self._quality_filters.discard(q)
            else:
                self._quality_filters.add(q)
            self._sync_labels()
            self._apply_filters()
            return

        if controlID in SORT_BTNS:
            self._sort_by = SORT_BTNS[controlID]
            self._sync_labels()
            self._apply_filters()
            return

        if controlID in PROVIDER_BTNS:
            p = PROVIDER_BTNS[controlID]
            if p in self._provider_filters:
                self._provider_filters.discard(p)
            else:
                self._provider_filters.add(p)
            self._sync_labels()
            self._apply_filters()
            return

        if controlID in FEATURE_BTNS:
            f = FEATURE_BTNS[controlID]
            if f in self._feature_filters:
                self._feature_filters.discard(f)
            else:
                self._feature_filters.add(f)
            self._sync_labels()
            self._apply_filters()
            return

    def onAction(self, action):
        if action.getId() in (9, 10, 92, 216):
            self.selected_source = None
            self._save_filters()
            self.close()

    def _save_filters(self):
        set_setting('filter_quality', '|'.join(sorted(self._quality_filters)))
        set_setting('filter_sort', self._sort_by)
        set_setting('filter_providers', '|'.join(sorted(self._provider_filters)))
        set_setting('filter_features', '|'.join(sorted(self._feature_filters)))
