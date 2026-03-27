# -*- coding: utf-8 -*-
"""
HebSubScout Context Menu
=========================
Right-click any movie/TV show → shows actions:
- Check Hebrew Subs
- Add to Trakt Watchlist
- Mark as Watched / Unwatched
- Similar Titles
"""

import sys
import xbmc
import xbmcgui
import xbmcaddon


def get_item_info():
    """Extract metadata from the currently focused ListItem."""
    info = {}
    imdb_id = (xbmc.getInfoLabel('ListItem.IMDBNumber')
               or xbmc.getInfoLabel('ListItem.Property(imdb_id)')
               or xbmc.getInfoLabel('ListItem.Property(IMDBNumber)'))
    info['imdb_id'] = imdb_id
    info['tmdb_id'] = xbmc.getInfoLabel('ListItem.Property(tmdb_id)')
    info['title'] = xbmc.getInfoLabel('ListItem.Title') or xbmc.getInfoLabel('ListItem.Label')
    info['year'] = xbmc.getInfoLabel('ListItem.Year')
    info['media_type'] = xbmc.getInfoLabel('ListItem.Property(media_type)') or ''
    season = xbmc.getInfoLabel('ListItem.Season')
    episode = xbmc.getInfoLabel('ListItem.Episode')
    if season and episode:
        try:
            info['season'] = int(season)
            info['episode'] = int(episode)
        except ValueError:
            pass
    return info


def _trakt_available():
    """Check if Trakt is authorized in the main addon."""
    try:
        addon = xbmcaddon.Addon('plugin.video.hebscout')
        return bool(addon.getSetting('trakt_token'))
    except Exception:
        return False


def check_hebrew_subs(info):
    """Check Hebrew subtitle availability."""
    imdb_id = info.get('imdb_id', '')
    title = info.get('title', 'Unknown')
    if not imdb_id:
        kb = xbmc.Keyboard('', 'לא נמצא IMDB ID - הכנס ידנית (tt...)')
        kb.doModal()
        if kb.isConfirmed():
            imdb_id = kb.getText().strip()
            if not imdb_id.startswith('tt'):
                imdb_id = 'tt' + imdb_id
        else:
            return

    from hebsubscout import SubScout
    progress = xbmcgui.DialogProgress()
    progress.create('בודק כתוביות בעברית - {}'.format(title), 'מחפש...')
    progress.update(10)

    scout = SubScout()
    subs = scout.fetch_subtitles(imdb_id, season=info.get('season'), episode=info.get('episode'))
    progress.update(90)
    progress.close()

    if not subs:
        xbmcgui.Dialog().ok('HebSubScout', '[COLOR red]לא נמצאו כתוביות בעברית[/COLOR]')
        return

    by_provider = {}
    for sub in subs:
        p = sub.get('provider', 'unknown')
        by_provider.setdefault(p, []).append(sub)

    lines = ['[COLOR lime]נמצאו {} כתוביות בעברית![/COLOR]\n'.format(len(subs))]
    for provider, provider_subs in sorted(by_provider.items()):
        lines.append('[COLOR cyan]{}[/COLOR]: {} כתוביות'.format(provider.upper(), len(provider_subs)))
        for sub in provider_subs[:3]:
            lines.append('  • {}'.format(sub.get('name', '')))
        if len(provider_subs) > 3:
            lines.append('  ... ועוד {}'.format(len(provider_subs) - 3))

    xbmcgui.Dialog().textviewer('HebSubScout - {}'.format(title), '\n'.join(lines))


def trakt_watchlist_add(info):
    """Add item to Trakt watchlist via the main addon."""
    imdb_id = info.get('imdb_id', '')
    media_type = info.get('media_type', 'movie')
    if not imdb_id:
        return
    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.hebscout/?action=trakt_watchlist_add&imdb_id={}&media_type={})'.format(
        imdb_id, media_type))


def mark_watched(info):
    """Mark item as watched via the main addon."""
    imdb_id = info.get('imdb_id', '')
    if not imdb_id:
        return
    season = info.get('season', 0)
    episode = info.get('episode', 0)
    xbmc.executebuiltin('RunPlugin(plugin://plugin.video.hebscout/?action=mark_watched&imdb_id={}&season={}&episode={})'.format(
        imdb_id, season, episode))
    xbmcgui.Dialog().notification('HebScout', 'סומן כנצפה', xbmcgui.NOTIFICATION_INFO, 2000)


def similar_titles(info):
    """Open similar titles in the main addon."""
    tmdb_id = info.get('tmdb_id', '')
    media_type = info.get('media_type', 'movie')
    if not tmdb_id:
        xbmcgui.Dialog().notification('HebScout', 'לא נמצא TMDB ID', xbmcgui.NOTIFICATION_WARNING, 2000)
        return
    action = 'movie_similar' if media_type == 'movie' else 'show_similar'
    xbmc.executebuiltin('Container.Update(plugin://plugin.video.hebscout/?action={}&tmdb_id={})'.format(
        action, tmdb_id))


def main():
    info = get_item_info()
    title = info.get('title', '')

    # Build menu options
    options = ['בדוק כתוביות בעברית']
    actions = [check_hebrew_subs]

    if _trakt_available():
        options.append('הוסף לרשימת צפייה (Trakt)')
        actions.append(trakt_watchlist_add)

    options.append('סמן כנצפה')
    actions.append(mark_watched)

    if info.get('tmdb_id'):
        options.append('כותרים דומים')
        actions.append(similar_titles)

    if len(options) == 1:
        # Only one option, run it directly
        actions[0](info)
        return

    choice = xbmcgui.Dialog().select('HebScout - {}'.format(title), options)
    if choice >= 0:
        actions[choice](info)


if __name__ == '__main__':
    main()
