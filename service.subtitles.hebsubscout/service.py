# -*- coding: utf-8 -*-
"""
HebSubScout Subtitle Service
=============================
Standard Kodi subtitle service interface.
Kodi calls this when the user opens the subtitle dialog (CC button).
Also used internally by HebScout addon for auto-subtitle download.
"""

import sys
import os

from urllib.parse import parse_qsl, unquote

import xbmc
import xbmcgui
import xbmcaddon
import xbmcplugin
import xbmcvfs

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo('profile'))

# Add our module path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def log(msg, level='INFO'):
    xbmc.log('[HebSubScout-Subs] {}: {}'.format(level, msg), xbmc.LOGINFO)


def get_params():
    return dict(parse_qsl(sys.argv[2].lstrip('?')))


def search(imdb_id='', title='', year='', season='', episode=''):
    """
    Search for Hebrew subtitles - called by Kodi's subtitle system.
    Results appear in Kodi's standard subtitle selection dialog.
    """
    log('Search: imdb={} title={} season={} episode={}'.format(imdb_id, title, season, episode))
    
    try:
        from hebsubscout import SubScout
        scout = SubScout(settings={'providers': ['wizdom', 'ktuvit']})
        
        s = int(season) if season else None
        e = int(episode) if episode else None
        
        subs = scout.fetch_subtitles(imdb_id, season=s, episode=e)
        
        for sub in subs:
            name = sub.get('name', 'Unknown')
            provider = sub.get('provider', '')
            sub_id = sub.get('id', '')
            
            # Create list item for Kodi's subtitle dialog
            li = xbmcgui.ListItem(label='Hebrew', label2=name)
            li.setArt({'icon': '5', 'thumb': 'he'})  # Rating / language flag
            li.setProperty('sync', 'false')
            li.setProperty('hearing_imp', 'false')
            
            # Encode download info into the URL
            url = 'plugin://service.subtitles.hebsubscout/?action=download&provider={}&sub_id={}&name={}'.format(
                provider, sub_id, name
            )
            
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=li, isFolder=False)
        
        log('Found {} subtitles'.format(len(subs)))
    except ImportError:
        log('HebSubScout module not available', 'ERROR')
    except Exception as ex:
        log('Search error: {}'.format(ex), 'ERROR')
    
    xbmcplugin.endOfDirectory(HANDLE)


def download(provider, sub_id, name=''):
    """
    Download a specific subtitle - called when user picks one from Kodi's dialog.
    """
    log('Download: provider={} id={}'.format(provider, sub_id))
    
    from downloader import download_subtitle
    
    path = download_subtitle(provider=provider, subtitle_id=sub_id)
    
    if path:
        log('Downloaded to: {}'.format(path))
        # Tell Kodi about the downloaded subtitle
        li = xbmcgui.ListItem(label=path)
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=path, listitem=li, isFolder=False)
    else:
        log('Download failed', 'ERROR')
    
    xbmcplugin.endOfDirectory(HANDLE)


def main():
    params = get_params()
    action = params.get('action', '')
    
    if action == 'search' or not action:
        # Get current video info from Kodi player
        imdb_id = xbmc.getInfoLabel('VideoPlayer.IMDBNumber')
        title = xbmc.getInfoLabel('VideoPlayer.Title') or xbmc.getInfoLabel('VideoPlayer.OriginalTitle')
        year = xbmc.getInfoLabel('VideoPlayer.Year')
        season = xbmc.getInfoLabel('VideoPlayer.Season')
        episode = xbmc.getInfoLabel('VideoPlayer.Episode')
        
        # Override with params if provided
        imdb_id = params.get('imdb_id', imdb_id)
        
        search(imdb_id=imdb_id, title=title, year=year, season=season, episode=episode)
    
    elif action == 'download':
        download(
            provider=params.get('provider', ''),
            sub_id=params.get('sub_id', ''),
            name=params.get('name', '')
        )


if __name__ == '__main__':
    main()
