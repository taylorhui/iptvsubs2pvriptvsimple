import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__addon_id__ = __scriptid__


def check_data_dir():
    if(not xbmcvfs.exists(xbmc.translatePath(data_dir()))):
        xbmcvfs.mkdir(xbmc.translatePath(data_dir()))

def data_dir():
    return __addon__.getAddonInfo('profile')

def addon_dir():
    return __addon__.getAddonInfo('path')

def log(message,loglevel=xbmc.LOGNOTICE):
    xbmc.log(encode(__addon_id__ + "-" + __addon__.getAddonInfo('version') + " : " + message),level=loglevel)

def showNotification(title,message):
    xbmcgui.Dialog().notification(encode(getString(30000)),encode(message),time=4000,icon=xbmc.translatePath(__addon__.getAddonInfo('path') + "/icon.png"),sound=False)

def setSetting(name,value):
    __addon__.setSetting(name,value)

def getSetting(name):
    return __addon__.getSetting(name)

def refreshAddon():
    log("Updated addon")
    global __addon__
    old_addon = __addon__
    __addon__ = xbmcaddon.Addon()
    return old_addon

def getString(string_id):
    return __addon__.getLocalizedString(string_id)

def encode(string):
    return string.encode('UTF-8','replace')
