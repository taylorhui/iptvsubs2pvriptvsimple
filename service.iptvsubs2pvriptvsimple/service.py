import xbmcplugin,xbmcaddon
import time
import datetime
import xbmc
import os
import urllib2,urllib,json,re
import zipfile
import resources.lib.utils as utils
from resources.lib.croniter import croniter
from collections import namedtuple
from shutil import copyfile
import xml.etree.ElementTree as ET
import traceback

__addon__ = xbmcaddon.Addon()
__author__ = __addon__.getAddonInfo('author')
__scriptid__ = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__cwd__ = __addon__.getAddonInfo('path')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString
debug = __addon__.getSetting("debug")
offset1hr = __addon__.getSetting("offset1hr")

class epgUpdater:
    def __init__(self):
        self.monitor = UpdateMonitor(update_method = self.settingsChanged)
        self.enabled = utils.getSetting("enable_scheduler")
        self.next_run = 0
        self.update_m3u = False
        updater_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/service.iptvsubs2pvriptvsimple')
        if not os.path.isdir(updater_path):
          try:
            os.mkdir(updater_path)
          except:
            pass

        try:
          self.iptvsubs_addon = xbmcaddon.Addon('plugin.video.ruyaiptv')
          utils.setSetting("pluginmissing", "false")
        except:
          utils.log("Failed to find iptvsubs addon")
          self.iptvsubs_addon = None
          utils.setSetting("pluginmissing", "true")
        try:
          self.pvriptvsimple_addon = xbmcaddon.Addon('pvr.iptvsimple')
        except:
          utils.log("Failed to find pvr.iptvsimple addon")
          self.pvriptvsimple_addon = None

    def run(self):
        utils.log("StalkerSettings::scheduler enabled, finding next run time")

        # Update when starting
        self.updateGroups()
        self.updateM3u()
        if self.enabled:
          self.updateEpg()

        self.findNextRun(time.time())
        while(not xbmc.abortRequested):
            # Sleep/wait for abort for 10 seconds
            now = time.time()
            if(self.enabled):
              if(self.next_run <= now):
                  self.updateEpg()
                  self.findNextRun(now)
              else:
                  self.findNextRun(now)
              if(self.update_m3u):
                  self.updateM3u()
                  self.update_m3u = False
            xbmc.sleep(500)
        # del self.monitor

    def updateGroups(self):
      self.groups = []
      for group in [ "English", "Sports", "Adults", "AFRICAN", "BANGLA", "French", "HINDI", "Italian", "PERSIAN/KURDISH", "Polish", "PORTUGUESE", "PUNJABI", "SOUTH INDIAN", "Spanish", "URDU", "VietnamESE", "Chinese", "EUROPEAN/BALKANS", "FilipinO"]:
        if utils.getSetting(group) == 'true':
          self.groups.append(group)

    def installKeyboardFile(self):
      keyboard_file_path = os.path.join(xbmc.translatePath('special://home'), 'addons/service.iptvsubs2pvriptvsimple/keyboard.xml')
      if os.path.isfile(keyboard_file_path):
        utils.log("Keyboard file found.  Copying...")
        copyfile(keyboard_file_path, os.path.join(xbmc.translatePath('special://userdata'), 'keymaps/keyboard.xml'))

    def settingsChanged(self):
        utils.log("Settings changed - update")
        old_settings = utils.refreshAddon()
        current_enabled = utils.getSetting("enable_scheduler")
        install_keyboard_file = utils.getSetting("install_keyboard_file")
        if install_keyboard_file == 'true':
          self.installKeyboardFile()
          utils.setSetting('install_keyboard_file', 'false')
          # Return since this is going to be run immediately again
          return
        
        # Update m3u file if wanted groups has changed
        old_groups = self.groups
        self.updateGroups()
        if self.groups != old_groups or old_settings.getSetting("username") != utils.getSetting("username") or old_settings.getSetting("password") != utils.getSetting("password") or old_settings.getSetting("mergem3u_fn") != utils.getSetting("merge3mu_fn") or old_settings.getSetting("mergem3u") != utils.getSetting("mergem3u"):
          self.update_m3u = True

        if old_settings.getSetting("timezone") != utils.getSetting("timezone"):
          if self.pvriptvsimple_addon:
            utils.log("Changing offset")
            self.checkAndUpdatePVRIPTVSetting("epgTimeShift", utils.getSetting("timezone"))

        if(self.enabled == "true"):
            #always recheck the next run time after an update
            utils.log('recalculate start time , after settings update')
            self.findNextRun(time.time())

    def parseSchedule(self):
        schedule_type = int(utils.getSetting("schedule_interval"))
        cron_exp = utils.getSetting("cron_schedule")

        hour_of_day = utils.getSetting("schedule_time")
        hour_of_day = int(hour_of_day[0:2])
        if(schedule_type == 0 or schedule_type == 1):
            #every day
            cron_exp = "0 " + str(hour_of_day) + " * * *"
        elif(schedule_type == 2):
            #once a week
            day_of_week = utils.getSetting("day_of_week")
            cron_exp = "0 " + str(hour_of_day) + " * * " + day_of_week
        elif(schedule_type == 3):
            #first day of month
            cron_exp = "0 " + str(hour_of_day) + " 1 * *"

        return cron_exp


    def findNextRun(self,now):
        #find the cron expression and get the next run time
        cron_exp = self.parseSchedule()
        cron_ob = croniter(cron_exp,datetime.datetime.fromtimestamp(now))
        new_run_time = cron_ob.get_next(float)
        # utils.log('new run time' +  str(new_run_time))
        # utils.log('next run time' + str(self.next_run))
        if(new_run_time != self.next_run):
            self.next_run = new_run_time
            utils.showNotification('EPG Updater', 'Next Update: ' + datetime.datetime.fromtimestamp(self.next_run).strftime('%m-%d-%Y %H:%M'))
            utils.log("scheduler will run again on " + datetime.datetime.fromtimestamp(self.next_run).strftime('%m-%d-%Y %H:%M'))


    def updateM3u(self):
        if self.iptvsubs_addon is None:
            username = utils.getSetting('username')
            password = utils.getSetting('password')
            updater_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/service.iptvsubs2pvriptvsimple')
        else:
            username = self.iptvsubs_addon.getSetting('username')
            password = self.iptvsubs_addon.getSetting('password')
            updater_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/plugin.video.ruyaiptv')
        if self.pvriptvsimple_addon is None:
            utils.log("pvriptvsimple addon missing")
            return

        self.checkAndUpdatePVRIPTVSetting("epgCache", "false")
        self.checkAndUpdatePVRIPTVSetting("epgPathType", "0")
        self.checkAndUpdatePVRIPTVSetting("epgPath", updater_path + '/iptvsubs_xmltv.xml.gz')
        self.checkAndUpdatePVRIPTVSetting("m3uPathType", "0")
        self.checkAndUpdatePVRIPTVSetting("m3uPath", "{0}/iptvsubs.m3u".format(updater_path))
        utils.log("Updating m3u file")

        cm_path = os.path.join(xbmc.translatePath('special://home'), 'addons/service.iptvsubs2pvriptvsimple/channel_guide_map.txt')

        channel_map = {}
        if os.path.isfile(cm_path):
          utils.log('Adding mapped guide ids')
          with open(cm_path) as f:
            for line in f:
              channel_name,guide_id = line.rstrip().split("\t")
              channel_map[channel_name] = guide_id

        login_url = "http://88888.se:8000/ruyaserver/users/login.php"
        utils.log("username:{0} pass:{1}".format(username, password))
        data = urllib.urlencode({'username':username, 'password':password})
        try:
          u = urllib2.urlopen(login_url, data)
          token = u.read()
        except Exception as e:
          utils.log("Error logging in.\n{0}\n{1}".format(e, traceback.format_exc()))
          return

        packages_url = "http://88888.se:8000/ruyaserver/livetv/get_livetv_packages.php"
        data = urllib.urlencode({'token':token})
        packages = []
        try:
          u = urllib2.urlopen(packages_url, data)
          packages_xml = u.read()
          root = ET.fromstring(packages_xml)
          for package in root.findall('package'):
            packages.append(package.text)
        except Exception as e:
          utils.log("Error retrieving packages.\n{0}\n{1}".format(e, traceback.format_exc()))
          return

        Channel = namedtuple('Channel', ['tvg_id', 'tvg_name', 'tvg_logo', 'group_title', 'channel_url'])
        channels = []

        group_idx = {}
        for idx,group in enumerate(self.groups):
          group_idx[group] = idx


        for package in packages:
          if package in group_idx:
            package_channels_url = "http://88888.se:8000/ruyaserver/livetv/get_livetv_channels_by_package.php"
            data = urllib.urlencode({'token':token, 'package':package})
            try:
              u = urllib2.urlopen(package_channels_url, data)
              channels_xml = u.read()
              e_re = re.compile(r"<([a-z_]+)>(.+)</[a-z_]+>")
              name = ""
              url = ""
              tvgid = ""
              tvglogo = ""
              for line in channels_xml.splitlines():
                m = e_re.search(line)
                if m:
                  if m.group(1) == 'name':
                     name = re.sub('[0-9]+\.\.','',m.group(2))
                     if name == '' : name = 'zzz Ch.{0}'.format(re.sub('\.\.','',m.group(2)))
                     tvgid = ''
                     if name in channel_map : tvgid = 'tvg-id="{0}"'.format(channel_map[name])
                  elif m.group(1) == 'piconname':
                     tvglogo = m.group(2)
                  elif m.group(1) == 'stream_url':
                     url = m.group(2)
                     channels.append(Channel(tvgid,name,tvglogo,package,url))
            except Exception as e:
              utils.log("Error retrieving channels.\n{0}\n{1}".format(e, traceback.format_exc()))
              return

        wanted_channels = channels
        wanted_channels.sort(key=lambda c: "{0}-{1}".format(group_idx[c.group_title], c.tvg_name))

        try:
          with open("{0}/iptvsubs.m3u".format(updater_path), "w") as m3u_f:
            m3u_f.write("#EXTM3U\n")
            for c in wanted_channels:
              m3u_f.write('#EXTINF:-1 tvg-name="{0}" {1} tvg-logo="{2}" group-title="{3}",{0}\n{4}\n'.format(c.tvg_name, c.tvg_id, c.tvg_logo, c.group_title, c.channel_url))
            if utils.getSetting("mergem3u") == "true":
              mergem3u_fn = utils.getSetting("mergem3u_fn")
              if os.path.isfile(mergem3u_fn):
                with open(mergem3u_fn) as mergem3u_f:
                  for line in mergem3u_f:
                    if line.startswith("#EXTM3U"):
                      continue
                    m3u_f.write(line)
        except Exception as e:
          utils.log("Error creating m3u file\n{0}\n{1}".format(e,traceback.format_exc()))


    def checkAndUpdatePVRIPTVSetting(self, setting, value):
      if self.pvriptvsimple_addon.getSetting(setting) != value:
        self.pvriptvsimple_addon.setSetting(setting, value)

    def updateEpg(self):
        epgFileName = 'merged.xml.gz'
        epgFile = None
        if self.iptvsubs_addon is None:
            updater_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/service.iptvsubs2pvriptvsimple')
        else:
            updater_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/plugin.video.ruyaiptv')
        iptvsimple_path = os.path.join(xbmc.translatePath('special://userdata'), 'addon_data/pvr.iptvsimple')

        try:
            response = urllib2.urlopen('http://s.epg.ninja')
            epgFile = response.read()
        except Exception as e:
            utils.log('StalkerSettings: Some issue with epg file')
            utils.log('{0}\n{1}'.format(e, traceback.format_exc()))

        if epgFile is None:
          try:
              response = urllib2.urlopen('https://github.com/psyc0n/epgninja/raw/subs/'+epgFileName)
              epgFile = response.read()
          except Exception as e:
              utils.log('StalkerSettings: Guide backup download failed.')
              utils.log('{0}\n{1}'.format(e, traceback.format_exc()))
              return

        if epgFile:
            epgFH = open(updater_path + '/iptvsubs_xmltv.xml.gz', "wb")
            epgFH.write(epgFile)
            epgFH.close()

        genresFile = None
        try:
            response = urllib2.urlopen('http://g.epg.ninja/')
            genresFile = response.read()
        except Exception as e:
            utils.log('StalkerSettings: Some issue with genres file')
            utils.log('{0}\n{1}'.format(e, traceback.format_exc()))

        if genresFile is None:
          try:
              response = urllib2.urlopen('https://github.com/psyc0n/epgninja/raw/subs/genres.xml')
              epgFile = response.read()
          except Exception as e:
              utils.log('StalkerSettings: Genres backup download failed.')
              utils.log('{0}\n{1}'.format(e, traceback.format_exc()))
              return

        if genresFile:
            genresFH = open(iptvsimple_path + '/genres.xml', "w")
            genresFH.write(epgFile)
            genresFH.close()
        utils.log("EPG updated")

class UpdateMonitor(xbmc.Monitor):
    update_method = None

    def __init__(self,*args, **kwargs):
        xbmc.Monitor.__init__(self)
        self.update_method = kwargs['update_method']

    def onSettingsChanged(self):
        self.update_method()

if __name__ == "__main__":
  epg_updater = epgUpdater()
  epg_updater.run()
