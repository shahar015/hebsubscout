# -*- coding: utf-8 -*-
"""
HebSubScout Context Menu Integration
======================================

This script runs when the user right-clicks any movie/TV show in Kodi
and selects "Check Hebrew Subs".

It reads the IMDB ID from the ListItem's metadata and checks subtitle
availability using the HebSubScout module.

This works with ANY video addon - no integration needed from the addon developer.
"""

import xbmc
import xbmcgui

from hebsubscout import SubScout


def get_item_info():
    """Extract IMDB ID and media info from the currently focused ListItem."""
    info = {}
    
    # Try to get IMDB ID from various sources
    imdb_id = xbmc.getInfoLabel('ListItem.IMDBNumber')
    if not imdb_id:
        imdb_id = xbmc.getInfoLabel('ListItem.Property(imdb_id)')
    if not imdb_id:
        imdb_id = xbmc.getInfoLabel('ListItem.Property(IMDBNumber)')
    if not imdb_id:
        # Some addons store it in the path or as a unique ID
        unique_id = xbmc.getInfoLabel('ListItem.Property(tmdb_id)')
        # Can't do much without IMDB ID
        pass
    
    info['imdb_id'] = imdb_id
    info['title'] = xbmc.getInfoLabel('ListItem.Title') or xbmc.getInfoLabel('ListItem.Label')
    info['year'] = xbmc.getInfoLabel('ListItem.Year')
    
    # Check if it's a TV episode
    season = xbmc.getInfoLabel('ListItem.Season')
    episode = xbmc.getInfoLabel('ListItem.Episode')
    if season and episode:
        try:
            info['season'] = int(season)
            info['episode'] = int(episode)
        except ValueError:
            pass
    
    return info


def main():
    item_info = get_item_info()
    imdb_id = item_info.get('imdb_id', '')
    title = item_info.get('title', 'Unknown')
    
    if not imdb_id:
        # Prompt the user to enter IMDB ID manually
        kb = xbmc.Keyboard('', 'לא נמצא IMDB ID - הכנס ידנית (tt...)')
        kb.doModal()
        if kb.isConfirmed():
            imdb_id = kb.getText().strip()
            if not imdb_id.startswith('tt'):
                imdb_id = 'tt' + imdb_id
        else:
            return
    
    season = item_info.get('season')
    episode = item_info.get('episode')
    
    # Show progress
    progress = xbmcgui.DialogProgress()
    header = 'בודק כתוביות בעברית'
    if title:
        header += ' - {}'.format(title)
    progress.create(header, 'מחפש...')
    progress.update(10)
    
    # Check subtitles
    scout = SubScout()
    subs = scout.fetch_subtitles(imdb_id, season=season, episode=episode)
    
    progress.update(90)
    progress.close()
    
    if not subs:
        xbmcgui.Dialog().ok(
            'HebSubScout',
            '[COLOR red]לא נמצאו כתוביות בעברית[/COLOR]\n\n'
            'Title: {}\nIMDB: {}'.format(title, imdb_id)
        )
        return
    
    # Build results summary
    by_provider = {}
    for sub in subs:
        p = sub.get('provider', 'unknown')
        if p not in by_provider:
            by_provider[p] = []
        by_provider[p].append(sub)
    
    lines = ['[COLOR lime]נמצאו {} כתוביות בעברית![/COLOR]\n'.format(len(subs))]
    for provider, provider_subs in sorted(by_provider.items()):
        lines.append('[COLOR cyan]{}[/COLOR]: {} כתוביות'.format(
            provider.upper(), len(provider_subs)
        ))
        # Show first 3 release names
        for sub in provider_subs[:3]:
            lines.append('  • {}'.format(sub.get('name', '')))
        if len(provider_subs) > 3:
            lines.append('  ... ועוד {}'.format(len(provider_subs) - 3))
    
    xbmcgui.Dialog().textviewer(
        'HebSubScout - {} ({})'.format(title, imdb_id),
        '\n'.join(lines)
    )


if __name__ == '__main__':
    main()
