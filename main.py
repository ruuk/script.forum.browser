# -*- coding: utf-8 -*-
import os, sys, xbmc
import urllib2, re, time, urlparse, binascii, textwrap, codecs
import xbmcgui #@UnresolvedImport
from lib import util, signals, asyncconnections  # @Reimport
from lib.util import LOG, ERROR, getSetting, setSetting
from lib.xbmcconstants import * # analysis:ignore
import YDStreamExtractor as StreamExtractor
import YDStreamUtils as StreamUtils

StreamExtractor.overrideParam('noplaylist',True)
StreamExtractor.generateBlacklist(('.*:(?:user|channel|search)$','(?i)generic.*'))

import warnings

warnings.filterwarnings('ignore',category=UnicodeWarning)

try:
	from webviewer import webviewer #@UnresolvedImport
	print 'FORUMBROWSER: WEB VIEWER IMPORTED'
except:
	import traceback
	traceback.print_exc()
	print 'FORUMBROWSER: COULD NOT IMPORT WEB VIEWER'

__plugin__ = 'Forum Browser'
__author__ = 'ruuk (Rick Phillips)'
__date__ = '1-28-2013'
__version__ = util.__addon__.getAddonInfo('version')
T = util.T

THEME = util.getSavedTheme()


PLAYER = None
SIGNALHUB = None

MEDIA_PATH = util.MEDIA_PATH
FORUMS_STATIC_PATH = util.FORUMS_STATIC_PATH
FORUMS_PATH = util.FORUMS_PATH
FORUMS_SETTINGS_PATH = util.FORUMS_SETTINGS_PATH
CACHE_PATH = util.CACHE_PATH
TEMP_DIR = util.TEMP_DIR

STARTFORUM = None

LOG('Version: ' + __version__)
LOG('Python Version: ' + sys.version)
DEBUG = getSetting('debug') == 'true'
if DEBUG: LOG('DEBUG LOGGING ON')
LOG('Skin: ' + THEME)

CLIPBOARD = None
try:
	import SSClipboard #@UnresolvedImport
	CLIPBOARD = SSClipboard.Clipboard()
	LOG('Clipboard Enabled')
except:
	LOG('Clipboard Disabled: No SSClipboard')

FB = None

from lib.forumbrowser import forumbrowser
from lib.forumbrowser import texttransform
from lib.forumbrowser import tapatalk
from lib import dialogs, windows, mods  # @Reimport

util.DEBUG = DEBUG

signals.DEBUG = DEBUG

dialogs.CACHE_PATH = CACHE_PATH
dialogs.DEBUG = DEBUG

mods.CACHE_PATH = CACHE_PATH
mods.DEBUG = DEBUG

StreamExtractor.DEBUG = DEBUG

asyncconnections.LOG = LOG
asyncconnections.setEnabled(not getSetting('disable_async_connections',False))

######################################################################################
#
# Image Dialog
#
######################################################################################
class ImagesDialog(windows.BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		windows.BaseWindowDialog.__init__( self, *args, **kwargs )

	def onInit(self):
		windows.BaseWindowDialog.onInit(self)
		self.getControl(200).setEnabled(len(self.images) > 1)
		self.getControl(202).setEnabled(len(self.images) > 1)
		self.showImage()

	def onFocus( self, controlId ):
		self.controlId = controlId

	def showImage(self):
		if not self.images: return
		self.getControl(102).setImage(self.images[self.index])

	def nextImage(self):
		self.index += 1
		if self.index >= len(self.images): self.index = 0
		self.showImage()

	def prevImage(self):
		self.index -= 1
		if self.index < 0: self.index = len(self.images) - 1
		self.showImage()

	def onClick( self, controlID ):
		if windows.BaseWindow.onClick(self, controlID): return
		if controlID == 200:
			self.nextImage()
		elif controlID == 202:
			self.prevImage()

	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_NEXT_ITEM or action == ACTION_MOVE_RIGHT:
			self.nextImage()
			self.setFocusId(202)
		elif action == ACTION_PREV_ITEM or action == ACTION_MOVE_LEFT:
			self.prevImage()
			self.setFocusId(200)
		elif action == ACTION_CONTEXT_MENU:
			self.doMenu()
		windows.BaseWindowDialog.onAction(self,action)

	def doMenu(self):
		d = dialogs.ChoiceMenu(T(32051))
		d.addItem('save', T(32129))
		d.addItem('help',T(32244))
		result = d.getResult()
		if not result: return
		if result == 'save':
			self.saveImage()
		elif result == 'help':
			dialogs.showHelp('imageviewer')

	def downloadImage(self,url):
		base = xbmc.translatePath(os.path.join(util.__addon__.getAddonInfo('profile'),'slideshow'))
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		return Downloader(message=T(32148)).downloadURLs(base,[url],'.jpg')

	def saveImage(self):
		#browse(type, heading, shares[, mask, useThumbs, treatAsFolder, default])
		source = self.images[self.index]
		firstfname = os.path.basename(source)
		if source.startswith('http'):
			result = self.downloadImage(source)
			if not result:
				dialogs.showMessage(T(32257),T(32258),success=False)
				return
			source = result[0]

		path = getSetting('last_download_path') or ''
		if path:
			if not util.getSetting('assume_default_image_save_path', False):
				new = dialogs.dialogYesNo(T(32560),T(32561)+'[CR]',path,'[CR]'+T(32562),T(32563),T(32276))
				if new: path = ''
		if not path: path = xbmcgui.Dialog().browse(3,T(32260),'files','',False,True)
		if not path: return
		setSetting('last_download_path',path)
		if not os.path.exists(source): return
		if util.getSetting('dont_ask_image_filename', False):
			filename = firstfname
		else:
			filename = dialogs.doKeyboard(T(32259), firstfname)
			if filename == None: return
		target = os.path.join(path,filename)
		ct = 1
		original = filename
		while os.path.exists(target):
			fname, ext = os.path.splitext(original)
			filename = fname + '_' + str(ct) + ext
			ct+=1
			if os.path.exists(os.path.join(path,filename)): continue
			yes = dialogs.dialogYesNo(T(32261),T(32262),T(32263),filename + '?',T(32264),T(32265))
			if yes is None: return
			if not yes:
				ct = 0
				filename = dialogs.doKeyboard(T(32259), filename)
				original = filename
				if filename == None: return
			target = os.path.join(path,filename)
		import xbmcvfs
		xbmcvfs.copy(source, target)
		dialogs.showMessage(T(32266),T(32267),os.path.basename(target),success=True)

######################################################################################
#
# Forum Settings Dialog
#
######################################################################################
class ForumSettingsDialog(windows.BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.colorsDir = os.path.join(CACHE_PATH,'colors')
		self.colorGif = os.path.join(xbmc.translatePath(util.__addon__.getAddonInfo('path')),'resources','media','white1px.gif')
		self.gifReplace = chr(255)*6
		self.items = []
		self.data = {}
		self.help = {}
		self.helpSep = FB.MC.hrReplace
		self.header = ''
		self.headerColor = ''
		self.settingsChanged = False
		self.OK = False
		windows.BaseWindowDialog.__init__( self, *args, **kwargs )

	def setHeader(self,header):
		self.header = header

	def onInit(self):
		self.getControl(250).setLabel('%s' % self.header)
		self.fillList()
		self.setFocusId(320)

	def setHelp(self,hlp):
		self.help = hlp

	def addItem(self,sid,name,value,vtype):
		valueDisplay = str(value)
		if vtype == 'text.password': valueDisplay = len(valueDisplay) * '*'
		elif vtype == 'boolean': valueDisplay = value and 'booleanTrue' or 'booleanFalse'
		elif vtype.startswith('color.'):
			valueDisplay = self.makeColorFile(value.upper())
			self.headerColor = valueDisplay
		item = xbmcgui.ListItem(name,valueDisplay)
		item.setProperty('value_type',vtype.split('.',1)[0])
		item.setProperty('value',str(value))
		item.setProperty('id',sid)
		if vtype == 'text.long':
			item.setProperty('help', u'{0}[CR][COLOR FF999999]{1}[/COLOR][CR][B]Current:[/B][CR][CR]{2}'.format(self.help.get(sid,''),
																											self.helpSep,
																											texttransform.convertHTMLCodes(valueDisplay).decode('utf-8')))
		else:
			item.setProperty('help',self.help.get(sid,''))
		self.items.append(item)
		self.data[sid] = {'name':name, 'value':value, 'type':vtype}

	def addSep(self):
		if len(self.items) > 0: self.items[-1].setProperty('separator','separator')

	def fillList(self):
		for i in self.items:
			if i.getProperty('id') == 'logo': i.setProperty('header_color', str(self.headerColor))
		self.getControl(320).addItems(self.items)

	def onClick(self,controlID):
		if controlID == 320:
			self.editSetting()
		elif controlID == 100:
			self.OK = True
			self.doClose()
		elif controlID == 101:
			self.cancel()

	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			self.cancel()

	def cancel(self):
		if self.settingsChanged:
			yes = dialogs.dialogYesNo(T(32268),T(32269),T(32270))
			if not yes: return
		self.doClose()

	def editSetting(self):
		item = self.getControl(320).getSelectedItem()
		if not item: return
		dID = item.getProperty('id')
		data = self.data.get(dID)
		value = data['value']
		self.doEditSetting(dID,item,data)
		if value != data['value']: self.settingsChanged = True

	def doEditSetting(self,dID,item,data):
		if not data:
			LOG('ERROR GETTING FORUM SETTING FROM LISTITEM')
			return
		if data['type'] == 'boolean':
			data['value'] = not data['value']
			item.setLabel2(data['value'] and 'booleanTrue' or 'booleanFalse')
		elif data['type'].startswith('text'):
			if data['type'] == 'text.long':
				val = dialogs.doKeyboard(T(32271),data['value'],mod=True)
				item.setProperty('help',self.help.get(dID,'') + '[CR][COLOR FF999999]%s[/COLOR][CR][B]Current:[/B][CR][CR]%s' % (self.helpSep,val))
			elif data['type'].startswith('text.url'):
				if data['value']:
					yes = dialogs.dialogYesNo(T(32272),T(32274),T(32273),'',T(32276),T(32275))
					if yes:
						data['value'] = ''
						item.setLabel2('')
						return
				val = browseWebURL(data['type'].split('.',2)[-1])
			else:
				val = dialogs.doKeyboard(T(32271),data['value'],hidden=data['type']=='text.password')
			if val == None: return
			if not self.validate(val,data['type']): return
			data['value'] = val
			item.setLabel2(data['type'] != 'text.password' and val or len(val) * '*')
		elif data['type'].startswith('webimage.'):
			url = data['type'].split('.',1)[-1]
			yes = dialogs.dialogYesNo(T(32272),T(32278),T(32277),'',T(32280),T(32279))
			if yes is None: return
			if yes:
				logo = dialogs.doKeyboard(T(32281),data['value'] or 'http://')
				logo = logo or ''
			else:
				logo = self.getWebImage(url)
				if not logo: return
			data['value'] = logo
			item.setProperty('value',logo)
			self.refreshImage()
		elif data['type'].startswith('color.'):
			forumID = data['type'].split('.',1)[-1]
			color = askColor(forumID,data['value'],logo=(self.data.get('logo') or {}).get('value'))
			if not color: return
			data['value'] = color
			colorFile = self.makeColorFile(color)
			item.setLabel2(colorFile)
			self.headerColor = colorFile
			self.updateHeaderColor()
		elif data['type'] == 'function':
			if data['value'][0](*data['value'][1:]): self.settingsChanged = True

	def validate(self,val,vtype):
		if vtype == 'text.integer':
			if not val: return True
			try:
				int(val)
			except:
				dialogs.showMessage(T(32282),T(32283))
				return False
		elif vtype == 'text.time':
			if not val: return True
			if val.startswith('-'): val = val[1:]
			if not ':' in val:
				if val.isdigit() and len(val) < 3: return True
			else:
				left, right = val.split(':',1)
				left = left or '00'
				if left.isdigit() and right.isdigit() and len(right) == 2: return True
			dialogs.showMessage(T(32282),T(32284).format('-mmm:ss'))
			return False
		return True

	def updateHeaderColor(self):
		clist = self.getControl(320)
		for idx in range(0,clist.size()):
			i = clist.getListItem(idx)
			if i.getProperty('id') == 'logo':
				i.setProperty('header_color', str(self.headerColor))
				self.refreshImage()
				return

	def refreshImage(self):
		cid = self.getFocusId()
		if not cid: return
		#self.setFocusId(100)
		self.setFocusId(cid)

	def getWebImage(self,url):
		with dialogs.xbmcDialogProgress(T(32285)) as d:
			info = forumbrowser.HTMLPageInfo(url,progress_callback=d.update)
			if d.iscanceled(): return ''
			domain = url.split('://',1)[-1].split('/',1)[0]
			logo = chooseLogo(domain,info.images(),keep_colors=True,splash=d)
		return logo

	def makeColorFile(self,color):
		return util.makeColorGif(color, os.path.join(self.colorsDir,color + '.gif'))

def editForumSettings(forumID):
	w = dialogs.openWindow(ForumSettingsDialog,'script-forumbrowser-forum-settings.xml',return_window=True,modal=False,theme='Default')
	sett,rules = util.loadForumSettings(forumID,get_both=True) or {'username':'','password':'','notify':False}
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	w.setHeader(forumID[3:])
	w.setHelp(dialogs.loadHelp('forumsettings.help') or {})

	if forumID.startswith('YT.'):
		from lib.forumbrowser import youtube
		label = 'Authorize'
		if youtube.authorized(): label = 'Re-authorize'
		w.addItem('authorize',label,(youtube.authorize,sett),'function')
	else:
		w.addItem('username',T(32286),sett.get('username',''),'text')
		w.addItem('password',T(32287),sett.get('password',''),'text.password')
	w.addItem('notify',T(32018),sett.get('notify',''),'boolean')
	w.addItem('extras',T(32288),sett.get('extras',''),'text')
	w.addItem('time_offset_hours',T(32289),sett.get('time_offset_hours',''),'text.time')
	w.addItem('right_align',T(32555),sett.get('right_align',''),'boolean')
	w.addSep()
	w.addItem('description',T(32290),fdata.description,'text.long')
	w.addItem('logo',T(32291),fdata.urls.get('logo',''),'webimage.' + fdata.forumURL())
	w.addItem('header_color',T(32292),fdata.theme.get('header_color',''),'color.' + forumID)
	if forumID.startswith('GB.'):
		w.addSep()
		w.addItem('login_url',T(32293),rules.get('login_url',''),'text.url.' + fdata.forumURL())
		w.addItem('ignore_forum_images',T(32016),sett.get('ignore_forum_images',True),'boolean')
		w.addItem('rules',T(32294),(manageParserRules,forumID,rules),'function')
	oldLogo = fdata.urls.get('logo','')
	w.doModal()
	if w.OK:
		rules['login_url'] = w.data.get('login_url') and w.data['login_url']['value'] or None
		ifi = None
		if forumID.startswith('GB.'):
			ifi = w.data['ignore_forum_images']['value']
		util.saveForumSettings(	forumID,
								username=w.data.get('username',{}).get('value',''),
								password=w.data.get('password',{}).get('value',''),
								notify=w.data['notify']['value'],
								extras=w.data['extras']['value'],
								time_offset_hours=w.data['time_offset_hours']['value'],
								ignore_forum_images=ifi,
								right_align=w.data['right_align']['value'],
								rules=rules)
		fdata.description = w.data['description']['value']
		fdata.urls['logo'] = w.data['logo']['value']
		fdata.theme['header_color'] = w.data['header_color']['value']
		fdata.writeData()
	del w
	if oldLogo != fdata.urls['logo']:
		util.getCachedLogo(fdata.urls['logo'],forumID,clear=True)

######################################################################################
#
# Forums Manager/ Notifications Dialog
#
######################################################################################
class NotificationsDialog(windows.BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.forumsWindow = kwargs.get('forumsWindow')
		self.initialForumID = kwargs.get('forumID')
		self.initialIndex = 0
		self.colorsDir = os.path.join(CACHE_PATH,'colors')
		if not os.path.exists(self.colorsDir): os.makedirs(self.colorsDir)
		self.colorGif = os.path.join(xbmc.translatePath(util.__addon__.getAddonInfo('path')),'resources','media','white1px.gif')
		self.gifReplace = chr(255)*6
		self.items = None
		self.stopTimeout = False
		self.started = False
		self.folder = None
		self.createItems()
		windows.BaseWindowDialog.__init__( self, *args, **kwargs )

	def newPostsCallback(self,signal,data):
		winid = xbmcgui.getCurrentWindowDialogId()
		xbmcgui.Window(winid).setProperty('PulseNotify', '1')
		self.refresh()

	def onInit(self):
		if self.started: return
		if SIGNALHUB: SIGNALHUB.registerReceiver('NEW_POSTS', self, self.newPostsCallback)
		self.started = True
		windows.BaseWindowDialog.onInit(self)
		if not self.forumsWindow: self.getControl(250).setLabel(T(32295))
		self.fillList()
		self.startDisplayTimeout()
		if self.items:
			self.setFocusId(220)
		else:
			if self.forumsWindow: self.setFocusId(200)

	def onClick( self, controlID ):
		if windows.BaseWindowDialog.onClick(self, controlID): return
		forumID = self.getSelectedForumID()
		if controlID > 199 and controlID < 210: self.setHelp()
		if controlID == 220:
			return self.changeForum()
		elif controlID == 200:
			self.setInactive()
			forumID = addForum()
			if forumID: self.refresh(forumID)
			self.setInactive(False)
		elif controlID == 202:
			if removeForum(forumID):
				item = self.getControl(220).getSelectedItem()
				item.setProperty('removed','1')
				self.refresh()
		elif controlID == 203:
			addFavorite(forumID)
			self.refresh()
		elif controlID == 204:
			removeFavorite(forumID)
			self.refresh()
		elif controlID == 205:
			self.setInactive()
			editForumSettings(forumID)
			item = self.getControl(220).getSelectedItem()
			if not item: return self.setInactive(False)
			ndata = util.loadForumSettings(forumID) or {}
			item.setProperty('notify',ndata.get('notify') and 'notify' or '')

			fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
			logo = fdata.urls.get('logo','')
			exists, logopath = util.getCachedLogo(logo,forumID)
			if exists: logo = logopath
			item.setIconImage(logo)

			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			item.setProperty('bgcolor',hc)
			color = hc.upper()[2:]
			path = self.makeColorFile(color, self.colorsDir)
			item.setProperty('bgfile',path)

			#self.setFocusId(220)
			self.setInactive(False)

		elif controlID == 207: addCurrentForumToOnlineDatabase(forumID)
		elif controlID == 208: updateThemeODB(forumID)
		elif controlID == 210:
			dialogs.showMessage(str(self.getControl(210).getLabel()),dialogs.loadHelp('options.help').get('help',''))
		elif controlID == 211:
			self.moveFavoriteUp(forumID)
		elif controlID == 212:
			self.moveFavoriteDown(forumID)
		self.setHelp(self.getFocusId())

	def onAction(self,action):
		self.stopTimeout = True
		try:
			if action == ACTION_CONTEXT_MENU:
				focusID = self.getFocusId()
				if focusID == 220:
					self.doMenu()
				elif focusID > 199 and focusID < 210:
					helpname = ''
					if focusID  == 200: helpname = 'addforum'
					elif focusID  == 201: helpname = 'addonline'
					elif focusID  == 202: helpname = 'removeforum'
					elif focusID  == 203: helpname = 'addfavorite'
					elif focusID  == 204: helpname = 'removefavorite'
					elif focusID  == 205: helpname = 'settings'
					elif focusID  == 207: helpname = 'addcurrentonline'
					elif focusID  == 208: helpname = 'updatethemeodb'
					dialogs.showMessage(str(self.getControl(focusID).getLabel()),dialogs.loadHelp('options.help').get(helpname,''))
			elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
				if self.folder:
					folder = self.folder
					self.folder = None
					self.refresh(folder)
					return
		except:
			windows.BaseWindowDialog.onAction(self,action)
			raise
		windows.BaseWindowDialog.onAction(self,action)


	def doMenu(self):
		item = self.getControl(220).getSelectedItem()
		if not item: return None
		d = dialogs.ChoiceMenu('Options')
		if not item.getProperty('isFolder'): d.addItem('add_to_folder','Add To Folder')
		if self.folder:
			d.addItem('remove_from_folder','Remove From Folder')
		else:
			if item.getProperty('isFolder'): d.addItem('remove_folder','Remove Folder')
			d.addItem('add_folder','New Folder')
		result = d.getResult()
		if not result: return
		if result == 'add_folder':
			self.addFolder()
		elif result == 'add_to_folder':
			self.addToFolder(item)
		elif result == 'remove_from_folder':
			self.removeFromFolder(item)
		elif result == 'remove_folder':
			self.removeFolder(item)

	def removeFolder(self,item):
		with dialogs.ActivitySplash():
			folder = item.getProperty('folder')
			folders = self.loadFolders()
			for i in range(0,len(folders)):
				if folder == folders[i]['name']:
					folders.pop(i)
					break
			self.saveFolders(folders)
			self.clearForumFolder(folder)
		self.refresh()

	def clearForumFolder(self,folder):
		for forumID in self.getForumIDList():
			self.removeFolderFromForumSettings(forumID,folder)

	def removeFromFolder(self,item):
		forumID = item.getProperty('forumID')
		self.removeFolderFromForumSettings(forumID,self.folder)
		item.setProperty('removed','1')
		self.refresh()

	def removeFolderFromForumSettings(self,forumID,folder):
		ndata = util.loadForumSettings(forumID,skip_password=True)
		folders = util._processSetting(ndata.get('folders',''),[])
		if folder in folders: folders.remove(folder)
		util.saveForumSettings(forumID,folders=util._processSettingForWrite(folders))

	def addToFolder(self,item):
		d = dialogs.ChoiceMenu('Choose Folder')
		for f in self.loadFolders():
			d.addItem(f['name'],f['name'])
		result = d.getResult()
		if not result: return
		forumID = item.getProperty('forumID')
		ndata = util.loadForumSettings(forumID,skip_password=True)
		folders = util._processSetting(ndata.get('folders',''),[])
		if result in folders: return
		folders.append(result)
		util.saveForumSettings(forumID,folders=util._processSettingForWrite(folders))
		if not self.folder and not item.getProperty('favorite'): item.setProperty('removed','1')
		self.refresh()

	def addFolder(self):
		name = dialogs.doKeyboard('Enter Folder Name')
		if not name: return
		folders = self.loadFolders()
		for f in folders:
			if f['name'] == name: return
		folders.append({'name':name})
		self.saveFolders(folders)
		self.refresh()

	def onFocus(self, focusID):
		if focusID < 200 or focusID > 212: return
		self.setHelp(focusID)

	def setInactive(self,inactive=True):
		self.setProperty('inactive', inactive and '1' or '0')

	def setHelp(self,focusID=None):
		if not focusID:
			return self.setProperty('menu_help',''
								)
		if focusID  == 200: helpname = 'addforum'
		elif focusID  == 201: helpname = 'addonline'
		elif focusID  == 202: helpname = 'removeforum'
		elif focusID  == 203: helpname = 'addfavorite'
		elif focusID  == 204: helpname = 'removefavorite'
		elif focusID  == 205: helpname = 'settings'
		elif focusID  == 207: helpname = 'addcurrentonline'
		elif focusID  == 208: helpname = 'updatethemeodb'
		else:
			self.setProperty('menu_help','')
			return

		self.setProperty('menu_help',dialogs.loadHelp('options.help').get(helpname,''))

	def moveFavoriteUp(self,forumID):
		favs = getFavorites()
		if not forumID in favs: return
		idx = favs.index(forumID)
		if idx == 0: return
		favs.remove(forumID)
		idx-=1
		favs.insert(idx, forumID)
		saveFavorites(favs)
		self.refresh(forumID)
		self.setFocusId(260)

	def moveFavoriteDown(self,forumID):
		favs = getFavorites()
		if not forumID in favs: return
		idx = favs.index(forumID)
		if idx >= len(favs): return
		favs.remove(forumID)
		idx+=1
		favs.insert(idx, forumID)
		saveFavorites(favs)
		self.refresh(forumID)
		self.setFocusId(260)

	def startDisplayTimeout(self):
		if self.forumsWindow: return
		if getSetting('notify_dialog_close_only_video',True) and not self.isVideoPlaying(): return
		duration = getSetting('notify_dialog_timout',0)
		if duration:
			xbmc.sleep(1000 * duration)
			if self.stopTimeout and getSetting('notify_dialog_close_activity_stops',True): return
			self.doClose()

	def isVideoPlaying(self):
		return xbmc.getCondVisibility('Player.Playing') and xbmc.getCondVisibility('Player.HasVideo')

	def toggleNotify(self):
		item = self.getControl(220).getSelectedItem()
		if not item: return
		forumID = item.getProperty('forumID')
		if not forumID: return
		current = toggleNotify(forumID)
		item.setProperty('notify',current and 'notify' or '')

	def getSelectedForumID(self):
		item = self.getControl(220).getSelectedItem()
		if not item: return None
		if item.getProperty('removed'):
			pos = self.getControl(220).getSelectedPosition()
			pos -= 1
			if pos < 1: return None
			item = item = self.getControl(220).getListItem(pos)
		forumID = item.getProperty('forumID')
		return forumID or None

	def changeFolder(self):
		item = self.getControl(220).getSelectedItem()
		if not item: return None
		self.folder = item.getProperty('folder')
		self.refresh()

	def changeForum(self):
		forumID = self.getSelectedForumID()
		if not forumID: return self.changeFolder()
		if self.forumsWindow:
			self.forumsWindow.changeForum(forumID)
		else:
			#startForumBrowser(forumID)
			section = ''
			if getSetting('notify_open_subs_pms',True):
				item = self.getControl(220).getSelectedItem()
				if item:
					if getSetting('notify_prefer_subs',False):
						section = item.getProperty('new_subs') and 'SUBSCRIPTIONS' or ''
					if not section: section = item.getProperty('new_PMs') and 'PM' or ''
					if not section: section = item.getProperty('new_subs') and 'SUBSCRIPTIONS' or ''
			furl = util.createForumBrowserURL(forumID,section)
			xbmc.executebuiltin("RunScript(script.forum.browser,%s)" % furl)
		self.doClose()

	def getJSON(self):
		try:
		    import json
		except:
		    import simplejson as json
		return json

	def loadFolders(self):
		path = xbmc.translatePath(os.path.join(util.__addon__.getAddonInfo('profile'),'forum_folders.json'))
		if not os.path.exists(path): return []
		json = self.getJSON()
		with open(path,'r') as fp:
			data = json.load(fp)
		return data.get('folders')

	def saveFolders(self,folders):
		path = xbmc.translatePath(os.path.join(util.__addon__.getAddonInfo('profile'),'forum_folders.json'))
		json = self.getJSON()
		with open(path,'w') as fp:
			json.dump({'version':1,'folders':folders}, fp)

	def getColorPath(self,colors,hc):
		color = hc.upper()[2:]
		if color in colors:
			path = colors[color]
		else:
			path = self.makeColorFile(color, self.colorsDir)
			colors[color] = path
		return path

	def getForumIDList(self):
		forums = []
		for f in os.listdir(FORUMS_PATH):
			if not f.startswith('.'): forums.append(f)
		return forums

	def createItems(self):
		folders = []
		colors = {}
		if not self.folder:
			foldersList = self.loadFolders()
			ficon = os.path.join(util.MEDIA_PATH,'forum-browser-thread.png')
			hcpath = self.getColorPath(colors,'FFEBC987')
			for f in foldersList:
				item = xbmcgui.ListItem(f['name'],iconImage=ficon)
				item.setProperty('folder',f['name'])
				item.setProperty('isFolder','1')
				item.setProperty('bgcolor','FFEBC987')

				item.setProperty('bgfile',hcpath)
				folders.append(item)
		favs = getFavorites()
		if not self.forumsWindow and getSetting('notify_dialog_only_enabled'):
			final = getNotifyList()
		else:
			final = self.getForumIDList()

		unreadData = self.loadLastData() or {}
		uitems = []
		items = []
		fitems =[]
		datas = []
		sortkey = lambda x: x.name.lower()
		for f in final:
			path = util.getForumPath(f,just_path=True)
			if not path: continue
			if not os.path.isfile(os.path.join(path,f)): continue
			try:
				fdata = forumbrowser.ForumData(f,path)
			except:
				import xbmcvfs
				ERROR('Deleting broken forum file')
				xbmcvfs.delete(os.path.join(path,f))
				dialogs.showMessage('NOTICE', 'Broken forum file for:', f.split('.',1)[-1], 'was deleted.', error=True)
				continue
			datas.append(fdata)
		datas.sort(key=sortkey)

		for fdata in datas:
			flag = False
			unread = unreadData.get(fdata.forumID) or {}
			ndata = util.loadForumSettings(fdata.forumID,skip_password=True) or {}

			if self.folder:
				if not self.folder in util._processSetting(ndata.get('folders',''),[]): continue
			else:
				if not fdata.forumID in favs:
					if ndata.get('folders'): continue

			name = fdata.name
			logo = fdata.urls.get('logo','')
			exists, logopath = util.getCachedLogo(logo,fdata.forumID)
			if exists: logo = logopath
			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			item = xbmcgui.ListItem(name,iconImage=logo)
			item.setProperty('bgcolor',hc)
			path = self.getColorPath(colors,hc)
			item.setProperty('bgfile',path)
			item.setProperty('forumID',fdata.forumID)
			item.setProperty('type',fdata.forumID[:2])
			item.setProperty('notify',ndata.get('notify') and 'notify' or '')
			up = unread.get('PM','')
			if up:
				flag = True
				item.setProperty('new_PMs','newpms')
			upms = str(up) or ''
			if 'PM' in unread: del unread['PM']
			uct = unread.values().count(True)
			if uct:
				flag = True
				item.setProperty('new_subs','newsubs')
			usubs = unread and str(uct) or ''
			tsubs = unread and str(len(unread.values())) or ''
			usubs = usubs and '%s/%s' % (usubs,tsubs) or ''
			item.setProperty('unread_subs',usubs)
			item.setProperty('unread_PMs',upms)

			if fdata.forumID in favs:
				item.setProperty('favorite','favorite')
				fitems.append(item)
			elif flag:
				uitems.append(item)
			else:
				items.append(item)
		fsortkey = lambda x: favs.index(x.getProperty('forumID'))
		fitems.sort(key=fsortkey)
		self.items = fitems + folders + uitems + items
		idx = 0
		for item in self.items:
			if item.getProperty('forumID') == self.initialForumID:
				self.initialIndex = idx
			elif item.getProperty('folder') == self.initialForumID:
				self.initialIndex = idx
			idx += 1

	def fillList(self):
		self.getControl(220).addItems(self.items)
		self.getControl(220).selectItem(self.initialIndex)
		self.initialForumID = None
		self.initialIndex = 0

	def refresh(self,forumID=None):
		self.initialForumID = forumID or self.getSelectedForumID()
		self.createItems()
		self.getControl(220).reset()
		self.fillList()

	def makeColorFile(self,color,path):
		return util.makeColorGif(color, os.path.join(path,color + '.gif'))

	def loadLastData(self):
		dataFile = os.path.join(CACHE_PATH,'notifications')
		if not os.path.exists(dataFile): return
		seconds = (getSetting('notify_interval',20) + 5) * 60
		df = open(dataFile,'r')
		lines = df.read()
		df.close()
		try:
			dtime,data = lines.splitlines()
			if time.time() - float(dtime) > seconds: return
			import ast
			return ast.literal_eval(data)
		except:
			ERROR('Failed To Read Data File')

def getNotifyList():
		flist = os.listdir(FORUMS_PATH)
		nlist = []
		for f in flist:
			data = util.loadForumSettings(f)
			if data:
				if data['notify']: nlist.append(f)
		return nlist

######################################################################################
#
# Post Dialog
#
######################################################################################
class PostDialog(windows.BaseWindow):
	failedPM = None
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.doNotPost = kwargs.get('donotpost') or False
		self.title = self.post.title
		self.posted = False
		self.moderated = False
		self.display_base = '%s\n \n'
		windows.BaseWindow.__init__( self, *args, **kwargs )
		self.viewType = 'EDITOR'
		self.textLines = []
		self.quote_wrap = 80

	def setPreview(self,text):
		try:
			self.getControl(122).setLabel(text)
		except:
			self.getControl(122).setText(text)

	def onInit(self):
		windows.BaseWindow.onInit(self)
		self.setLoggedIn()
		self.setPreview(' ') #to remove scrollbar
		self.quote_wrap = self.quoteWrap()
		if self.failedPM:
			if self.failedPM.isPM == self.post.isPM and self.failedPM.tid == self.post.tid and self.failedPM.to == self.post.to:
				yes = dialogs.dialogYesNo(T(32296),T(32297))
				if yes:
					self.post = self.failedPM
					self.textLines = self.stripEmptyLines(self.post.message.split('\n'))
					self.updatePreview(-1)
					self.setTheme()
					PostDialog.failedPM = None
					return
		if self.post.quote:
			qformat = FB.getQuoteReplace()
			pid = self.post.pid
			if False:
				#This won't work with other formats, need to do this better TODO
				if not pid or self.isPM(): qformat = qformat.replace(';!POSTID!','')
				for line in qformat.replace('!USER!',self.post.quser).replace('!POSTID!',self.post.pid).replace('!QUOTE!',self.post.quote).split('\n'):
					self.textLines.append(line)
			else:
				self.textLines = self.stripEmptyLines(self.post.quote.split('\n'))
		elif self.post.isEdit:
			self.textLines = self.stripEmptyLines(self.post.message.split('\n'))

		self.updatePreview(-1)
		self.setTheme()
		if self.post.moderated:
			self.moderated = True
			dialogs.showMessage(T(32298),T(32299),T(32300))
		if self.isPM() or self.doNotPost: self.setTitle() #We're creating a thread

	def stripEmptyLines(self,lines):
		lines2 = []
		started = False
		for l in lines: #Strip empty lines from top
			if l.strip() or started:
				lines2.append(l)
				started = True
		lines = []
		started = False
		for l in reversed(lines2): #Strip empty lines from bottom
			if l.strip() or started:
				lines.insert(0,l)
				started = True
		return lines

	def setTheme(self):
		self.setProperty('loggedin',FB.isLoggedIn() and 'loggedin' or '')
		if self.isPM():
			self.setProperty('posttype',T(32177))
			self.setProperty('submit_button',T(32178))
		else:
			self.setProperty('posttype',T(32902))
			self.setProperty('submit_button',T(32908))
		self.showTitle(self.post.title)

	def showTitle(self,title):
		self.setProperty('title',title or '')
		self.setProperty('toggle_title',title or T(32921))

	def onClick( self, controlID ):
		if windows.BaseWindow.onClick(self, controlID): return
		if controlID == 202:
			self.postReply()
		elif controlID == 104:
			self.setTitle()

	def onFocus( self, controlId ):
		self.controlId = controlId

	def onAction(self,action):
		if action == ACTION_PREVIOUS_MENU:
			if util.Control.HasFocus(group=196):
				if self.getControl(120).size():
					self.setFocusId(120)
					return
			if not self.confirmExit(): return
		windows.BaseWindow.onAction(self,action)

	def confirmExit(self):
		if not self.getOutput() and not self.title: return True
		return dialogs.dialogYesNo(T(32301),T(32302),T(32303))

	def isPM(self):
		return str(self.post.pid).startswith('PM') or self.post.to

	def getOutput(self): return '\n'.join(self.textLines)

	def setTitle(self):
		title = dialogs.doKeyboard(T(32125), self.title)
		if not title: return
		self.showTitle(title)
		self.title = title

	def dialogCallback(self,pct,message):
		self.prog.update(pct,message)
		return True

	def postReply(self):
		message = self.getOutput()
		self.post.setMessage(self.title,message)
		self.posted = True
		if self.doNotPost:
			self.doClose()
			return
		splash = dialogs.showActivitySplash(T(32126))
		try:
			if self.post.isPM:
				if not FB.doPrivateMessage(self.post,callback=splash.update):
					self.posted = False
					splash.close()
					dialogs.showMessage(T(32050),T(32246),' ',self.post.error or '?',success=False)
					return
			else:
				if not FB.post(self.post,callback=splash.update):
					self.posted = False
					splash.close()
					dialogs.showMessage(T(32050),T(32227),' ',self.post.error or '?',success=False)
					return
			splash.close()
			dialogs.showMessage(T(32304),self.post.isPM and T(32305) or T(32306),' ',str(self.post.successMessage),success=True)
		except:
			self.posted = False
			err = ERROR('Error creating post')
			splash.close()
			dialogs.showMessage(T(32050),T(32307),err,error=True)
			PostDialog.failedPM = self.post
		finally:
			splash.close()
		if not self.moderated and self.post.moderated:
			dialogs.showMessage(T(32298),T(32299),T(32300))
		self.doClose()

	def parseCodes(self,text):
		return FB.MC.parseCodes(text)

	def processQuote(self,m):
		gd = m.groupdict()
		quote = FB.MC.imageFilter.sub(FB.MC.quoteImageReplace,gd.get('quote',''))
		if gd.get('user'):
			ret = FB.MC.quoteReplace % (gd.get('user',''),quote)
		else:
			ret = FB.MC.aQuoteReplace % quote
		return re.sub(FB.getQuoteFormat(),self.processQuote,ret)

	def updatePreview(self,pos=None):
		disp = self.display_base % self.getOutput()
		if FB.browserType == 'ScraperForumBrowser':
			qf = FB.getQuoteFormat()
			if qf: disp = re.sub(qf,self.processQuote,disp)
			disp = self.parseCodes(disp).replace('\n','[CR]')
			disp = re.sub('\[(/?)b\]',r'[\1B]',disp)
			disp = re.sub('\[(/?)i\]',r'[\1I]',disp)
		else:
			disp =  FB.MC.messageToDisplay(disp.replace('\n','[CR]'),quote_wrap=self.quote_wrap)
		self.setPreview('')
		self.setPreview(self.parseCodes(disp).replace('\n','[CR]'))
		items = []
		for line in self.textLines:
			items.append(xbmcgui.ListItem(label=self.displayLine(line)))
		plusItem = xbmcgui.ListItem(label='')
		plusItem.setProperty('plus_item','1')
		items.append(plusItem)
		self.getControl(120).reset()
		self.getControl(120).addItems(items)
		if pos is not None: self.resumePos(pos)

	def resumePos(self,pos):
		llist = self.getControl(120)
		size = llist.size()
		if pos > size or pos < 0:
			pos = size - 1
		llist.selectItem(pos)

	def getText(self,pos):
		try:
			return self.textLines[pos]
		except:
			ERROR('',hide_tb=True)
			return None

	def setText(self,pos,text):
		try:
			self.textLines[pos] = text
		except:
			ERROR('',hide_tb=True)

	def displayLine(self,line):
		return line	.replace('\n',' ')\
					.replace('[/B]','[/b]')\
					.replace('[/I]','[/i]')\
					.replace('[/COLOR]','[/color]')

	def setLoggedIn(self):
		try:
			if FB.isLoggedIn():
				self.getControl(111).setColorDiffuse('FF00FF00')
			else:
				self.getControl(111).setColorDiffuse('FF555555')
		except:
			pass

class LinePostDialog(PostDialog):
	def onClick( self, controlID ):
		if controlID == 200:
			self.addLineSingle()
		elif controlID == 201:
			self.addLineMulti()
		elif controlID == 301:
			self.deleteLine()
		elif controlID == 302:
			self.addLineSingle(before=True)
		elif controlID == 303:
			self.addLineSingle(after=True)
		elif controlID == 120:
			self.editLine()
		PostDialog.onClick(self, controlID)

	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			if self.getFocusId() == 302:
				self.doAddLinesMenu('before')
			elif self.getFocusId() == 303:
				self.doAddLinesMenu('after')
			else:
				self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		PostDialog.onAction(self,action)

	def doMenu(self):
		d = dialogs.ChoiceMenu(T(32051))
		item = self.getControl(120).getSelectedItem()
		if item.getProperty('plus_item'): return self.doAddLinesMenu()
		skinLevel = self.skinLevel()
		if item:
			if skinLevel < 1:
				d.addItem('addbefore',T(32128))
				d.addItem('delete',T(32122))
			if CLIPBOARD and CLIPBOARD.hasData(('link','image','video')):
				if not item.getProperty('plus_item'): d.addItem('pastebefore',T(32308) + ' %s' % CLIPBOARD.hasData().title())
		if CLIPBOARD and CLIPBOARD.hasData(('link','image','video')):
			d.addItem('paste',T(32309) + ' %s' % CLIPBOARD.hasData().title())
		d.addItem('help',T(32244))
		result = d.getResult()
		if result == 'addbefore': self.addLineSingle(before=True)
		elif result == 'delete': self.deleteLine()
		elif result == 'paste': self.paste()
		elif result == 'pastebefore': self.paste(before=True)
		elif result == 'help': dialogs.showHelp('editor')

	def doAddLinesMenu(self,mode='normal'):
		d = dialogs.ChoiceMenu(T(32051))
		d.addItem('addlines',mode == 'normal' and T(32568) or T(32569))
		res = d.getResult()
		if not res: return
		if mode == 'before':
			self.addLineMulti(before=True)
		elif mode == 'after':
			self.addLineMulti(after=True)
		else:
			self.addLineMulti()

	def paste(self,before=False):
		share = CLIPBOARD.getClipboard()
		if share.shareType == 'link':
			text = dialogs.doKeyboard(T(32310),mod=True)
			if not text: text = share.page
			paste = '[url=%s]%s[/url]' % (share.page,text)
		elif share.shareType == 'image':
			paste = '[img]%s[/img]' % share.url
		elif share.shareType == 'video':
			paste = '[video=%s]%s[/video]' % (share.sourceName.lower(),share.page)

		if before:
			self.addLineSingle(paste,True,False)
		else:
			self.addLine(paste)
			self.updatePreview(pos=-1)

	def addLine(self,line=''):
		self.textLines.append(line)
		return True

	def addLineSingle(self,line=None,before=False,update=True,after=False):
		if line == None: line = dialogs.doKeyboard(T(32123),'',mod=True,smilies=FB.getSmilies())
		if line == None: return False
		clist = self.getControl(120)
		pos = clist.getSelectedPosition()
		if before or after:
			if after: pos += 1
			self.textLines.insert(pos,line)
			self.updatePreview(pos)
			return True
		else:
			self.addLine(line)
			self.updatePreview(-1)
			return True

	def addLineMulti(self, before=False,after=False):
		clist = self.getControl(120)
		while self.addLineSingle(before=before,after=after):
			if before:
				pos = clist.getSelectedPosition() + 1
				self.resumePos(pos)

	def deleteLine(self):
		llist = self.getControl(120)
		pos = llist.getSelectedPosition()
		try:
			self.textLines.pop(pos)
		except:
			ERROR('Error Deleting Post Line',hide_tb=True)
		self.updatePreview(pos)

	def editLine(self):
		pos = self.getControl(120).getSelectedPosition()
		if pos < 0: return
		if pos >= len(self.textLines):
			return self.addLineSingle()
		text = self.getText(pos)
		if text == None: return
		line = dialogs.doKeyboard(T(32124),text,mod=True,smilies=FB.getSmilies())
		if line == None: return False
		self.setText(pos,line)
		self.updatePreview(pos)
		#re.sub(q,'[QUOTE=\g<user>;\g<postid>]\g<quote>[/QUOTE]',FB.MC.lineFilter.sub('',test3))

######################################################################################
#
# Message Window
#
######################################################################################
class MessageWindow(windows.BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.searchRE = kwargs.get('search_re')
		self.threadTopic = kwargs.get('thread_topic','')
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]'
		self.imageReplace = 'IMG #%s'
		self.action = None
		self.started = False
		self.interruptedVideo = None
		self.hasImages = False
		self.hasLinks = False
		if self.post: FB.updateAppURL(post=self.post.postId)
		windows.BaseWindow.__init__( self, *args, **kwargs )
		self.viewType = 'MESSAGE'
		self.videoCache = {}
		self.registerSettings(['hide_signatures','hide_image_urls','hide_link_urls'])

	def onInit(self):
		windows.BaseWindow.onInit(self)
		if self.started: return
		self.started = True
		self.setLoggedIn()
		self.setWindowProperties()
		self.setMessage()
		self.getControl(102).setImage(self.post.avatarFinal)
		self.setTheme()
		self.getLinks()
		self.getImages()
		self.setWindowProperties()

	def onSettingsChanged(self,changed):
		self.setMessage()

	def setMessage(self):
		s = dialogs.showActivitySplash()
		try:
			text = '%s[CR] [CR]' % self.post.messageAsDisplay(raw=True,quote_wrap=self.quoteWrap())
			#open('/home/ruuk/test.txt','w').write(repr(text))
		finally:
			s.close()

		if self.searchRE: text = self.highlightTerms(FB,text)
		try:
			self.getControl(122).setLabel(text)
		except:
			self.getControl(122).setText(text)

	def setTheme(self):
		self.getControl(103).setLabel(self.post.cleanUserName() or '')
		title = []
		if self.post.postNumber: title.append('#' + str(self.post.postNumber))
		if self.post.title: title.append(self.post.title)
		title = ' '.join(title)
		self.getControl(104).setLabel(title)
		self.getControl(105).setLabel(self.post.date or '')

	def getLinks(self):
		ulist = self.getControl(148)
		mlist = self.getControl(150)
		links = self.post.links()
		quality = getSetting('video_quality',1)
		self.videoCache = {}
		s = None
		try:
			ct=0
			for link in links:
				item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
				item.setProperty('index',str(ct))
				ct+=1
				vid = None
				try:
					if StreamExtractor.mightHaveVideo(link.url):
						if not s:
							s = dialogs.showActivitySplash(T(32311))
							StreamExtractor.setOutputCallback(s.updateMsg)
						vid = StreamExtractor.getVideoInfo(link.url,quality=quality)
					elif StreamExtractor.mightHaveVideo(link.text):
						if not s:
							s = dialogs.showActivitySplash(T(32311))
							StreamExtractor.setOutputCallback(s.updateMsg)
						vid = StreamExtractor.getVideoInfo(link.text,quality=quality)
				except:
					LOG('Error getting video info')

				if vid:
					self.videoCache[str(ct)] = vid
					item.setProperty('videoID',str(ct))
					item.setIconImage(vid.thumbnail)
					if vid.title: item.setLabel(vid.title)
					item.setLabel2('%s: %s' % (vid.sourceName,vid.ID))
					item.setProperty('video',link.url)
					mlist.addItem(item)
					self.hasImages = True
					self.setProperty('has_media', '1')
					continue
				elif link.isImage():
					if link.textIsImage():
						item.setIconImage(link.text)
					else:
						item.setIconImage(link.url)
					item2 = xbmcgui.ListItem('',iconImage=link.url)
					item2.setProperty('wrapped_url',textwrap.fill(link.url, 60, break_long_words=True))
					item.setProperty('url',link.url)
					mlist.addItem(item2)
					self.hasImages = True
				elif link.textIsImage():
					item.setIconImage(link.text)
				elif link.isPost():
					item.setIconImage('../../../media/forum-browser-post.png')
				elif link.isThread():
					item.setIconImage('../../../media/forum-browser-thread.png')
				else:
					item.setIconImage('../../../media/forum-browser-link.png')
				self.hasLinks = True
				ulist.addItem(item)

			if self.hasLinks: self.setProperty('has_links', '1')
			if self.hasImages: self.setProperty('has_media', '1')
		finally:
			if s: s.close()
			StreamExtractor.setOutputCallback(None)

	def getImages(self):
		urlParentDirFilter = re.compile('(?<!/)/\w[^/]*?/\.\./')
		urls = self.post.imageURLs()
		if urls:
			self.hasImages = True
			self.setProperty('has_media', '1')
		for i,url in urls:
			try:
				i = int(i)
			except:
				i = 0
			while urlParentDirFilter.search(url):
				#TODO: Limit
				url = urlParentDirFilter.sub('/',url)
			url = url.replace('/../','/')
			if getSetting('use_skin_mods',True):
				disp = FB.MC.makeCamera(i)
			else:
				disp = self.imageReplace % i
			item = xbmcgui.ListItem(disp,iconImage=url)
			item.setProperty('url',url)
			item.setProperty('wrapped_url',textwrap.fill(url, 60, break_long_words=True))
			self.getControl(150).addItem(item)

		#targetdir = os.path.join(util.__addon__.getAddonInfo('profile'),'messageimages')
		#TD.startDownload(targetdir,self.post.imageURLs(),ext='.jpg',callback=self.getImagesCallback)

	def getImagesCallback(self,file_dict):
		for fname,idx in zip(file_dict.values(),range(0,self.getControl(150).size())):
			fname = xbmc.translatePath(fname)
			self.getControl(150).getListItem(idx).setIconImage(fname)

	def setWindowProperties(self):
		extras = showUserExtras(self.post,just_return=True)
		self.setProperty('extras',extras)
		self.setProperty('avatar',self.post.avatarFinal)
		if self.hasLinks: self.setProperty('haslinks','1')
		if self.hasImages: self.setProperty('hasimages','1')
		if self.post.online: self.setProperty('online','1')

	def onFocus( self, controlID ):
		if controlID != 150: self.setProperty('media_preview', '0')

	def onClick( self, controlID ):
		if windows.BaseWindow.onClick(self, controlID): return
		if controlID == 148:
			self.linkSelected()
		elif controlID == 150:
			item = self.getControl(150).getSelectedItem()
			if item.getProperty('video'):
				self.handleVideoLinkURL(item)
			else:
				if self.getProperty('ignore_media_click'):
					self.setProperty('media_preview', self.getProperty('media_preview') == '1' and '0' or '1')
					return
				self.showImage(item.getProperty('url'))

	def showVideo(self,source):
		if StreamUtils.isPlaying() and getSetting('video_ask_interrupt',True):
			line2 = getSetting('video_return_interrupt',True) and T(32254) or ''
			if not dialogs.dialogYesNo(T(32255),T(32256),line2):
				return
		PLAYER.start(source)
		#StreamUtils.play(source)

	def getSelectedLink(self):
		item = self.getControl(148).getSelectedItem()
		if not item: return None
		idx = int(item.getProperty('index'))
		links = self.post.links()
		if idx >= len(links): return None
		return links[idx]

	def handleVideoLinkURL(self,item):
		s = dialogs.showActivitySplash()
		try:
			videoID = item.getProperty('videoID')
			url = item.getProperty('video')
			if videoID in self.videoCache:
				vid = self.videoCache[videoID]
			else:
				vid = StreamExtractor.getVideoInfo(url,quality=getSetting('video_quality',1))
			if vid:
				if vid.hasMultipleStreams():
					d = dialogs.ChoiceMenu(T(32597))
					for i in vid.streams():
						d.addItem(i,i['title'],i['thumbnail'])
					s.close()
					info = d.getResult()
					if not info: return
					vid.selectStream(info)
				self.showVideo(vid.streamURL())
				return
		finally:
			s.close()

	def downloadVideo(self,videoID,url):
		if videoID in self.videoCache:
			vid = self.videoCache[videoID]
		else:
			vid = StreamExtractor.getVideoInfo(url,quality=getSetting('video_quality',1))
		if vid.hasMultipleStreams():
			d = dialogs.ChoiceMenu(T(32597))
			for i in vid.streams():
				d.addItem(i,i['title'],i['thumbnail'])
			info = d.getResult()
			if not info: return
			vid.selectStream(info)

		path = self.getDownloadPath()
		if not path: return
		with StreamUtils.DownloadProgress() as prog:
			try:
				StreamExtractor.setOutputCallback(prog)
				result = StreamExtractor.downloadVideo(vid,path)
			finally:
				StreamExtractor.setOutputCallback(None)
		if not result and result.status != 'canceled':
				dialogs.showMessage(T(32258),'[CR]',result.message,success=False)
		elif result:
			dialogs.showMessage(T(32052),T(32601),'[CR]',result.filepath,success=True)

	def linkSelected(self):
		link = self.getSelectedLink()
		if not link: return
		if StreamExtractor.mightHaveVideo(link.url) or StreamExtractor.mightHaveVideo(link.text):
			s = dialogs.showActivitySplash()
			try:
				vid = StreamExtractor.getVideoInfo(link.url,quality=getSetting('video_quality',1))
				if not vid: vid = StreamExtractor.getVideoInfo(link.text,quality=getSetting('video_quality',1))
				if vid:
					self.showVideo(vid.streamURL())
					return
			finally:
				s.close()

# 		if link.isImage() and not link.textIsImage():
# 			self.showImage(link.url)
		if link.isPost() or link.isThread():
			self.action = forumbrowser.PostMessage(tid=link.tid,pid=link.pid)
			self.doClose()
		else:
			try:
				webviewer.getWebResult(link.url,dialog=True,browser=FB.browser)
			except:
				raise

	def showImage(self,url):
		image_files = []
		imgURLs = self.post.imageURLs()
		if imgURLs:
			counts, image_files = zip(*imgURLs)  # @UnusedVariable
			image_files = list(image_files)
		for l in self.post.links():
			if l.isImage() and not l.textIsImage(): image_files.append(l.url)
		if url in image_files:
			image_files.pop(image_files.index(url))
			image_files.insert(0,url)
		w = ImagesDialog("script-forumbrowser-imageviewer.xml" ,util.__addon__.getAddonInfo('path'),THEME,images=image_files)
		w.doModal()
		del w

	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			if self.getFocusId() == 148:
				self.doLinkMenu()
			elif self.getFocusId() == 150:
				self.doImageMenu()
			else:
				self.doMenu()
			return
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2 or action == ACTION_PREVIOUS_MENU:
			if self.getFocusId() == 148:
				self.setFocusId(127)
				return
			elif self.getFocusId() == 150:
				if not self.getProperty('ignore_media_click') == '1':
					self.setFocusId(127)
					return
		windows.BaseWindow.onAction(self,action)

	def onClose(self):
		if self.post: FB.updateAppURL(post=self.post.postId,close=True)

	def doLinkMenu(self):
		link = self.getSelectedLink()
		if not link: return
		d = dialogs.ChoiceMenu(T(32312))
		if CLIPBOARD:
			d.addItem('copy',T(32313))
			if link.isImage():
				d.addItem('copyimage',T(32314))
			vid = StreamExtractor.getVideoInfo(link.url,quality=getSetting('video_quality',1))
			if not vid: vid = StreamExtractor.getVideoInfo(link.text,quality=getSetting('video_quality',1))
			if vid and vid.isVideo: d.addItem('copyvideo',T(32315))
		#d.addItem('open_as_forum','Open As Forum Link')

		if d.isEmpty(): return
		result = d.getResult()
		if result == 'copy':
			share = CLIPBOARD.getShare('script.forum.browser','link')
			share.page = link.url
			CLIPBOARD.setClipboard(share)
		elif result == 'copyimage':
			share = CLIPBOARD.getShare('script.forum.browser','image')
			share.url = link.url
			CLIPBOARD.setClipboard(share)
		elif result == 'copyvideo':
			share = CLIPBOARD.getShare('script.forum.browser','video')
			video = StreamExtractor.getVideoInfo(link.url)
			if video:
				share.page = link.url
			else:
				share.page = link.text
			CLIPBOARD.setClipboard(share)
		elif result == 'open_as_forum':
			forumID = forumbrowser.getForumIDByURL(link.url)
			if not forumID: return
			self.action = forumbrowser.ChangeForumAction(link.url)
			self.doClose()
			#if forumID == FB.getForumID():
			#	pass


	def doImageMenu(self):
		img = self.getControl(150).getSelectedItem().getProperty('url')
		vid = self.getControl(150).getSelectedItem().getProperty('videoID')
		d = dialogs.ChoiceMenu(T(32316))
		d.addItem('save', T(32129))
		if CLIPBOARD and not vid:
			d.addItem('copy',T(32314))
		if d.isEmpty(): return
		result = d.getResult()
		if not result: return
		if result == 'copy':
			share = CLIPBOARD.getShare('script.evernote','image')
			share.url = img
			CLIPBOARD.setClipboard(share)
		elif result == 'save':
			if vid:
				url = self.getControl(150).getSelectedItem().getProperty('video')
				self.downloadVideo(vid,url)
			else:
				self.saveImage(img)

	def downloadImage(self,url):
		base = xbmc.translatePath(os.path.join(util.__addon__.getAddonInfo('profile'),'slideshow'))
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		return Downloader(message=T(32148)).downloadURLs(base,[url],'.jpg')

	def getDownloadPath(self):
		path = getSetting('last_download_path') or ''
		if path:
			if not util.getSetting('assume_default_image_save_path', False):
				new = dialogs.dialogYesNo(T(32560),T(32561)+'[CR]',path,'[CR]'+T(32562),T(32563),T(32276))
				if new: path = ''
		if not path: path = xbmcgui.Dialog().browse(3,T(32260),'files','',False,True)
		if not path: return
		setSetting('last_download_path',path)
		return path

	def saveImage(self,source):
		#browse(type, heading, shares[, mask, useThumbs, treatAsFolder, default])
		firstfname = os.path.basename(source)
		if source.startswith('http'):
			result = self.downloadImage(source)
			if not result:
				dialogs.showMessage(T(32257),T(32258),success=False)
				return
			source = result[0]

		path = self.getDownloadPath()

		if not os.path.exists(source): return
		if util.getSetting('dont_ask_image_filename', False):
			filename = firstfname
		else:
			filename = dialogs.doKeyboard(T(32259), firstfname)
			if filename == None: return
		target = os.path.join(path,filename)
		ct = 1
		original = filename
		while os.path.exists(target):
			fname, ext = os.path.splitext(original)
			filename = fname + '_' + str(ct) + ext
			ct+=1
			if os.path.exists(os.path.join(path,filename)): continue
			yes = dialogs.dialogYesNo(T(32261),T(32262),T(32263),filename + '?',T(32264),T(32265))
			if yes is None: return
			if not yes:
				ct = 0
				filename = dialogs.doKeyboard(T(32259), filename)
				original = filename
				if filename == None: return
			target = os.path.join(path,filename)
		import xbmcvfs
		xbmcvfs.copy(source, target)
		dialogs.showMessage(T(32266),T(32267),os.path.basename(target),success=True)

	def doMenu(self):
		d = dialogs.ChoiceMenu(T(32051))
		if FB.canPost(): d.addItem('quote',self.post.isPM and T(32249) or T(32134))
		if FB.canDelete(self.post.cleanUserName(),self.post.messageType()): d.addItem('delete',T(32141))
		if FB.canEditPost(self.post.cleanUserName()): d.addItem('edit',T(32232))
		if self.post.extras: d.addItem('extras',T(32317))
		d.addItem('bookmark',T(32553))
		d.addItem('help',T(32244))
		result = d.getResult()
		if result == 'quote': self.openPostDialog(quote=True)
		elif result == 'delete': self.deletePost()
		elif result == 'edit':
			splash = dialogs.showActivitySplash(T(32318))
			try:
				pm = FB.getPostForEdit(self.post)
			finally:
				splash.close()
			pm.tid = self.post.tid
			if openPostDialog(editPM=pm):
				self.action = forumbrowser.Action('REFRESH-REOPEN')
				self.action.pid = pm.pid
				self.doClose()
		elif result == 'extras':
			showUserExtras(self.post)
		elif result =='bookmark':
			dialogs.addBookmark(FB,name=self.post.title or ('#%s in %s' % (self.post.postNumber or self.post.postId,self.threadTopic)))
		elif result == 'help':
			dialogs.showHelp('message')

	def deletePost(self):
		result = deletePost(self.post,is_pm=self.post.isPM)
		self.action = forumbrowser.Action('REFRESH')
		if result: self.doClose()

	def openPostDialog(self,quote=False):
		pm = openPostDialog(quote and self.post or None,pid=self.post.postId,tid=self.post.tid,fid=self.post.fid)
		if pm:
			self.action = forumbrowser.PostMessage(pid=pm.pid)
			self.action.action = 'GOTOPOST'
			self.doClose()

	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)

def openPostDialog(post=None,pid='',tid='',fid='',editPM=None,donotpost=False,no_quote=False,to=''):
	if editPM:
		pm = editPM
	else:
		pm = forumbrowser.PostMessage(pid,tid,fid,is_pm=(tid == 'private_messages'))
		if post and not no_quote:
			s = dialogs.showActivitySplash()
			try:
				pm.setQuote(post.userName,post.messageAsQuote())
				pm.title = post.title
			finally:
				s.close()
		if tid == 'private_messages':
			default = to
			if post: default = post.userName
			to = dialogs.doKeyboard(T(32319),default=default)
			if not to: return
			pm.to = to
	w = dialogs.openWindow(LinePostDialog,"script-forumbrowser-post.xml" ,post=pm,return_window=True,donotpost=donotpost)
	posted = w.posted
	del w
	if posted: return pm
	return None

def deletePost(post,is_pm=False):
	pm = forumbrowser.PostMessage().fromPost(post)
	if not pm.pid: return
	yes = dialogs.dialogYesNo(T(32320),T(32321))
	if not yes: return
	splash = dialogs.showActivitySplash(T(32322))
	try:
		if is_pm or post.isPM:
			pm.isPM = True
			result = FB.deletePrivateMessage(pm)
		else:
			result = FB.deletePost(pm)
		if not result:
			dialogs.showMessage(T(32323),T(32324),pm.error or T(32325),success=False)
		else:
			dialogs.showMessage(T(32304),pm.isPM and T(32326) or T(32327),success=True)
	except:
		err = ERROR('Delete post error.')
		LOG('Error deleting post/pm: ' + err)
		dialogs.showMessage(T(32050),T(32328),'[CR]',err,error=True)
		return None
	finally:
		splash.close()
	return result

def showUserExtras(post,ignore=None,just_return=False):
	out = ''
	color = 'FFA00000'
	if just_return: color = 'FFA00000'
	for k,v in post.getExtras(ignore=ignore).items():
		if not hasattr(v,'decode'): v = str(v)
		val = texttransform.convertHTMLCodes(v,FB)
		tmp = FB.unicode(u'[B]{0}:[/B] [COLOR {1}]{2}[/COLOR]\n')
		out += tmp.format(	k.title(),
							color,
							FB.unicode(val)
						)
	if just_return: return out
	dialogs.showMessage(T(32329),out,scroll=True)

######################################################################################
#
# Replies Window
#
######################################################################################
class RepliesWindow(windows.PageWindow):
	info_display = {'postcount':'posts','joindate':'joined'}
	def __init__( self, *args, **kwargs ):
		windows.PageWindow.__init__( self,total_items=int(kwargs.get('reply_count',0)),*args, **kwargs )
		self.viewType = 'POST'
		self.action = None
		self.setPageData(FB)
		self.pageData.isReplies = True
		self.threadItem = item = kwargs.get('item')
		self.dontOpenPD = False
		self.forumElements = kwargs.get('forumElements')
		if item:
			self.tid = item.getProperty('id')
			self.lastid = item.getProperty('lastid')
			self.topic = item.getProperty('title')
			self.reply_count = item.getProperty('reply_count')
			self.isAnnouncement = bool(item.getProperty('announcement'))
			self.search = item.getProperty('search_terms')
		else:
			self.tid = kwargs.get('tid')
			self.lastid = ''
			self.topic = kwargs.get('topic')
			self.reply_count = ''
			self.isAnnouncement = False
			self.search = kwargs.get('search_terms')

		self.searchRE = kwargs.get('search_re')
		if not self.searchRE: self.setupSearch()

		self.fid = kwargs.get('fid','')
		self.pid = kwargs.get('pid','')
		self.uid = kwargs.get('uid','')

		FB.updateAppURL(thread=self.tid)

		self.search_uname = kwargs.get('search_name','')
		#self._firstPage = T(32113)
		self._newestPage = T(32112)
		self.me = FB.user
		self.posts = {}
		self.empty = True
		self.desc_base = u'[CR]%s[CR] [CR]'
		self.ignoreSelect = False
		self.firstRun = True
		self.started = False
		self.stayAtTop = False
		self.currentPMBox = {}
		self.timeOffset = 0
		self._doingMenu = False
		timeOffset = util.getForumSetting(FB.getForumID(),'time_offset_hours','').replace(':','')
		if timeOffset:
			negative = timeOffset.startswith('-') and -1 or 1
			timeOffset = timeOffset.strip('-')
			seconds = timeOffset[-2:] or 0
			minutes = timeOffset[:-2] or 0
			try:
				self.timeOffset = negative * ((int(minutes) * 60) + int(seconds))
			except:
				pass
		self.registerSettings(['hide_signatures','post_user_info','hide_image_urls','hide_link_urls','show_media_indicators','smi_count_link_images'])
		if not self.isPM():
			if self.search:
				self.registerSettings(['reverse_sort_search'])
			else:
				self.registerSettings(['reverse_sort'])

	def onInit(self):
		windows.BaseWindow.onInit(self)
		self.quote_wrap = self.quoteWrap()
		self.setLoggedIn()
		if self.started: return
		self.started = True
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.postSelected()
		self.setPMBox()
		self.setTheme()
		self.setPostButton()
		self.showThread()
		self.forumElements = None
		#self.setFocusId(120)

	def setPostButton(self):
		if self.isPM():
			self.getControl(201).setEnabled(FB.canPrivateMessage())
			self.getControl(201).setLabel(T(32177))
			self.setProperty('mode', 'pm')
		elif self.search:
			self.getControl(201).setEnabled(True)
			self.getControl(201).setLabel(T(32914))
			self.setProperty('mode', 'search')
		else:
			self.getControl(201).setEnabled(FB.canPost())
			self.getControl(201).setLabel(T(32902))
			self.setProperty('mode', 'post')

	def setPMBox(self,boxid=None):
		if not self.isPM(): return
		boxes = FB.getPMBoxes(update=False)
		self.currentPMBox = {}
		if not boxes: return
		if not boxid:
			for b in boxes:
				if b.get('default'):
					self.currentPMBox = b
					return
		else:
			for b in boxes:
				if b.get('id') == boxid:
					self.currentPMBox = b
					return

	def setTheme(self):
		mtype = self.isPM() and self.currentPMBox.get('name','Inbox') or T(32130)
		#if self.isPM(): self.getControl(201).setLabel(T(32177))
		self.getControl(103).setLabel('[B]%s[/B]' % mtype)
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)

	def showThread(self,nopage=False):
		self.stayAtTop = False
		if nopage:
			page = ''
		else:
			page = '1'
			if self.forumElements and self.forumElements.get('post') == 'last':
				page = FB.getPageData(is_replies=True).getPageNumber('-1')
			elif self.forumElements and self.forumElements.get('post') == 'first':
				self.stayAtTop = True
				page = FB.getPageData(is_replies=True).getPageNumber('1')
			elif self.forumElements and self.forumElements.get('args') and self.forumElements['args'].get('page'):
				self.stayAtTop = True
				page = self.forumElements['args'].get('page')
			elif self.forumElements and self.forumElements.get('post'):
				self.pid = self.forumElements.get('post')
			elif getSetting('open_thread_to_newest') == 'true':
				if not self.search: page = FB.getPageData(is_replies=True).getPageNumber('-1')
		self.fillRepliesList(page)

	def isPM(self):
		return self.tid == 'private_messages'

	def errorCallback(self,error):
		dialogs.showMessage(T(32050),T(32131),error.message,error=True)
		self.endProgress()

	def fillRepliesList(self,page='',pid=None):
		#page = int(page)
		#if page < 0: raise Exception()
		self.getControl(106).setVisible(True)
		self.setFocusId(106)
		if self.tid == 'private_messages':
			t = self.getThread(FB.getPrivateMessages,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='PRIVATE MESSAGES')
			t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback,boxid=self.currentPMBox.get('id'))
		elif self.isAnnouncement:
			t = self.getThread(FB.getAnnouncement,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='ANNOUNCEMENT')
			t.setArgs(self.tid,callback=t.progressCallback,donecallback=t.finishedCallback)
		elif self.search:
			if self.search == '@!RECENT!@':
				t = self.getThread(FB.getUserPosts,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='USER-RECENT-POSTS')
				t.setArgs(uname=self.search_uname,page=page or 0,uid=self.uid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
			elif self.uid:
				t = self.getThread(FB.searchAdvanced,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='UID-SEARCHPOSTS')
				t.setArgs(self.search,page,sid=self.lastid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData,uid=self.uid)
			elif self.search_uname:
				t = self.getThread(FB.searchAdvanced,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='UNAME-SEARCHPOSTS')
				t.setArgs(self.search,page,sid=self.lastid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData,uname=self.search_uname)
			elif self.tid:
				t = self.getThread(FB.searchAdvanced,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='TID-SEARCHPOSTS')
				t.setArgs(self.search,page,sid=self.lastid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData,tid=self.tid)
			else:
				t = self.getThread(FB.searchReplies,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='SEARCHPOSTS')
				t.setArgs(self.search,page,sid=self.lastid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
		else:
			t = self.getThread(FB.getReplies,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='POSTS')
			t.setArgs(self.tid,self.fid,page,lastid=self.lastid,pid=self.pid or pid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
		t.start()

	def setMessageProperty(self,post,item,short=False):
		title = (self.search and post.topic or post.title) or ''
		item.setProperty('title',title)
		message = post.messageAsDisplay(short,quote_wrap=self.quote_wrap)
		if self.searchRE: message = self.highlightTerms(FB,message)
		item.setProperty('message',message)

	def updateItem(self,item,post):
		alt = self.getUserInfoAttributes()
		defAvatar = '../../../media/forum-browser-avatar-none.png'
		showIndicators = getSetting('show_media_indicators',True)
		countLinkImages = getSetting('smi_count_link_images',False)
		item.setProperty('alternate1','')
		item.setProperty('alternate2','')
		item.setProperty('alternate3','')

		self._updateItem(item,post,defAvatar,showIndicators,countLinkImages,alt)
		self.setFocusId(120)

	def fixAvatar(self,url):
		if not 'http%3A%2F%2F' in url: return url
		return url + '&time=%s' % str(time.time())

	def _updateItem(self,item,post,defAvatar,showIndicators,countLinkImages,alt):
		url = defAvatar
		if post.avatar: url = FB.makeURL(post.avatar)
		post.avatarFinal = url
		self.setMessageProperty(post,item,True)
		item.setProperty('post',str(post.postId))
		item.setProperty('avatar',self.fixAvatar(url))
		#item.setProperty('status',texttransform.convertHTMLCodes(post.status,FB))
		item.setProperty('date',post.getDate(self.timeOffset))
		item.setProperty('online',post.online and 'online' or '')
		item.setProperty('postnumber',post.postNumber and unicode(post.postNumber) or '')
		if post.online:
			item.setProperty('activity',post.getActivity(self.timeOffset))
		else:
			item.setProperty('last_seen',post.getActivity(self.timeOffset))
		if showIndicators:
			hasimages,hasvideo = post.hasMedia(countLinkImages)
			item.setProperty('hasimages',hasimages and 'hasimages' or 'noimages')
			item.setProperty('hasvideo',hasvideo and 'hasvideo' or 'novideo')
		altused = []
		extras = post.getExtras()
		for a in alt:
			val = extras.get(a)
			if val != None:
				if not hasattr(val,'decode'): val = str(val)
				val = texttransform.convertHTMLCodes(val,FB)
				if not val: continue
				edisp = '%s: %s' % (self.info_display.get(a,a).title(),val)
				del extras[a]
				altused.append(a)
				if item.getProperty('alternate1'):
					if item.getProperty('alternate2'):
						item.setProperty('alternate3',edisp)
						break
					else:
						item.setProperty('alternate2',edisp)
				else:
					item.setProperty('alternate1',edisp)

		if extras:
			item.setProperty('extras','extras')
			item.setProperty('usedExtras',','.join(altused))

	def shouldReverse(self):
		if self.isPM(): return False
		if self.search: return getSetting('reverse_sort_search',False)
		return getSetting('reverse_sort',False)

	def shouldDropToBottom(self):
		if self.stayAtTop:
			self.stayAtTop = False
			return False
		if self.isPM(): return False
		if self.search: return getSetting('reverse_sort_search',False)
		return not getSetting('reverse_sort',False)

	def doFillRepliesList(self,data):
		if 'newthreadid' in data: self.tid = data['newthreadid']
		if not data:
			self.setFocusId(201)
			if data.error == 'CANCEL': return
			LOG('GET REPLIES ERROR')
			dialogs.showMessage(T(32050),self.isPM() and T(32135) or T(32131),T(32053),'[CR]' + data.error,success=False)
			return
		elif not data.data:
			if data.data == None:
				self.setFocusId(201)
				LOG('NO REPLIES')
				dialogs.showMessage(T(32050),self.isPM() and T(32135) or T(32131),T(32053),success=False)
			else:
				self.setFocusId(201)
				self.getControl(104).setLabel(self.isPM() and T(32251) or T(32250))
				LOG('No messages/posts - clearing list')
				self.getControl(120).reset()
				self.getControl(120).addItems([])
			return

		self.empty = False
		defAvatar = '../../../media/forum-browser-avatar-none.png'
		#xbmcgui.lock()
		try:
			self.getControl(120).reset()
			if not self.topic: self.topic = data.pageData.topic
			if not self.tid: self.tid = data.pageData.tid
			self.setupPage(data.pageData)
			if self.shouldReverse():
				data.data.reverse()
			alt = self.getUserInfoAttributes()
			self.posts = {}
			showIndicators = getSetting('show_media_indicators',True)
			countLinkImages = getSetting('smi_count_link_images',False)
			prevItem = xbmcgui.ListItem(label='prev')
			prevItem.setProperty('paging','1')
			nextItem = xbmcgui.ListItem(label='next')
			nextItem.setProperty('paging','2')
			items = []
			lastItem = len(data.data) - 1
			for post,idx in zip(data.data,range(0,len(data.data))):
				self.posts[post.postId] = post
				user = re.sub('<.*?>','',post.userName)
				item = xbmcgui.ListItem(label=post.isSent and 'To: ' + user or user)
				if user == self.me: item.setInfo('video',{"Director":'me'})
				if idx == lastItem:
					item.setProperty('end_item','last')
				elif idx == 0:
					item.setProperty('end_item','first')
				self._updateItem(item,post,defAvatar,showIndicators,countLinkImages,alt)
				items.append(item)
			if self.pageData.prev and self.skinLevel(1): items.insert(0,prevItem)
			if self.pageData.next and self.skinLevel(1): items.append(nextItem)
			self.getControl(120).addItems(items)
			self.setFocusId(120)
			if not self.pid and self.firstRun and getSetting('open_thread_to_newest',False) and FB.canOpenLatest() and self.shouldDropToBottom():
				self.getControl(120).selectItem(self.getControl(120).size() - 1)
			self.firstRun = False
		except:
			self.setFocusId(201)
			#xbmcgui.unlock()
			ERROR('FILL REPLIES ERROR')
			dialogs.showMessage(T(32050),T(32133),error=True)
			raise
		#xbmcgui.unlock()
		if self.pid:
			item = util.selectListItemByProperty(self.getControl(120),'post',self.pid)
			if item and not self.dontOpenPD:
				self.dontOpenPD = False
				self.postSelected(item=item)

		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
		self.pid = ''
		self.setLoggedIn()
		self.openElements()

	def openElements(self):
		if not self.forumElements: return
		if self.forumElements.get('post'):
			util.selectListItemByProperty(self.getControl(120),'post',self.forumElements.get('post'))
			if item: self.onClick(120)
		self.forumElements = None

	def getUserInfoAttributes(self):
		data = util.loadForumSettings(FB.getForumID())
		try:
			if 'extras' in data and data['extras']: return data['extras'].split(',')
			return getSetting('post_user_info','status,postcount,reputation,joindate,location').split(',')
		except:
			ERROR('getUserInfoAttributes(): Bad settings data')
			return ['postcount','reputation','joindate','location']

	def makeLinksArray(self,miter):
		if not miter: return []
		urls = []
		for m in miter:
			urls.append(m)
		return urls

	def postSelected(self,itemindex=-1,item=None):
		if not item:
			if itemindex > -1:
				item = self.getControl(120).getListItem(itemindex)
			else:
				item = self.getControl(120).getSelectedItem()
		if not item: return

		if self.processPaging(item.getProperty('paging')): return

		post = self.posts.get(item.getProperty('post'))
		if self.search and getSetting('search_open_thread',False):
			return self.openPostThread(post)
		post.tid = self.tid
		post.fid = self.fid
		w = dialogs.openWindow(MessageWindow,"script-forumbrowser-message.xml" ,return_window=True,post=post,search_re=self.searchRE,thread_topic=self.topic)
		self.setMessageProperty(post,item)
		self.setFocusId(120)
		if w.action:
			if w.action.action == 'CHANGE':
				self.topic = ''
				self.pid = w.action.pid
				self.tid = w.action.tid
				FB.updateAppURL(thread=self.tid)
				self.search = ''
				self.searchRE = None
				self.firstRun = True
				self.setPostButton()
				if w.action.pid: self.showThread(nopage=True)
				else: self.showThread()
			elif w.action.action == 'REFRESH':
				self.fillRepliesList(self.pageData.getPageNumber())
			elif w.action.action == 'REFRESH-REOPEN':
				self.pid = w.action.pid
				self.fillRepliesList(self.pageData.getPageNumber())
			elif w.action.action == 'GOTOPOST':
				self.firstRun = True
				self.fillRepliesList(self.pageData.getPageNumber(),pid=w.action.pid)
			elif w.action.action == 'CHANGE-FORUM':
				self.action = w.action
				self.doClose()
		del w

	def onSettingsChanged(self,changed):
		self.refresh()

	def onClick(self,controlID):
		if controlID == 201:
			self.stopThread()
			if self.search:
				self.newSearch()
			else:
				self.openPostDialog()
		elif controlID == 120:
			if not self.empty: self.stopThread()
			self.postSelected()
		elif controlID == 106:
			self.stopThread()
			return
		if self.empty: self.fillRepliesList()
		windows.PageWindow.onClick(self,controlID)

	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2 or action == ACTION_PREVIOUS_MENU:
			if util.Control.HasFocus(group=196):
					if self.getControl(120).size():
						self.setFocusId(120)
						return
		windows.PageWindow.onAction(self,action)

	def onClose(self):
		FB.updateAppURL(thread=self.tid,close=True)

	def newSearch(self):
		terms = dialogs.doKeyboard(T(32330),self.search or '')
		if not terms: return
		self.search = terms
		self.setupSearch()
		self.fillRepliesList()

	def selectNewPMBox(self):
		boxes = FB.getPMBoxes(update=False)
		if not boxes: return #TODO: Show message
		d = dialogs.ChoiceMenu(T(32331))
		for b in boxes:
			d.addItem(b,b.get('name','?'))
		box = d.getResult()
		if not box: return
		self.currentPMBox = box
		self.setTheme()
		self.fillRepliesList()

	def refresh(self):
		self.stopThread()
		self.fillRepliesList(self.pageData.getPageNumber())

	def doMenu(self):
		#Otherwise you can open on top of itself
		if self._doingMenu:return
		self._doingMenu = True
		self.reallyDoMenu()
		self._doingMenu = False

	def reallyDoMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu(T(32051),with_splash=True)
		post = None
		try:
			if self.isPM():
				boxes = FB.getPMBoxes(update=False)
				if boxes and len(boxes) > 1:
					d.addItem('changebox',T(32332))
			else:
				if FB.canGetRepliesURL():
					d.addItem('webviewer',T(32535))
				if self.posts: d.addItem('pageview',T(32537))

			if item:
				post = self.posts.get(item.getProperty('post'))
				if FB.canPost() and not self.search:
					d.addItem('quote',self.isPM() and T(32249) or T(32134))
				if FB.canDelete(item.getLabel(),post.messageType()):
					d.addItem('delete',T(32141))
				if not self.isPM():
					if FB.canEditPost(item.getLabel()):
						d.addItem('edit',T(32232))

			if self.threadItem:
				if FB.isThreadSubscribed(self.tid,self.threadItem.getProperty('subscribed')):
					if FB.canUnSubscribeThread(self.tid): d.addItem('unsubscribe',T(32240) + ': ' + self.threadItem.getProperty('title')[:25])
				else:
					if FB.canSubscribeThread(self.tid): d.addItem('subscribe',T(32236) + ': ' + self.threadItem.getProperty('title')[:25])
			if post and item.getProperty('extras'):
				d.addItem('extras',T(32317))
			if item and FB.canPrivateMessage() and not self.isPM():
				d.addItem('pm',T(32253).format(item.getLabel()))
			if post and post.canLike():
				d.addItem('like',T(32333))
			if post and post.canUnlike():
				d.addItem('unlike',T(32334))
			if self.searchRE and not getSetting('search_open_thread',False):
				d.addItem('open_thread',T(32335))
			d.addItem('bookmark',T(32553))
			d.addItem('refresh',T(32054))
			d.addItem('help',T(32244))
		finally:
			d.cancel()

		result = d.getResult()
		if not result: return
		if result == 'changebox':
			self.selectNewPMBox()
			return
		elif result == 'webviewer':
			url = FB.getRepliesURL(self.tid,self.fid,self.pageData.getPageNumber())
			webviewer.getWebResult(url,dialog=True,browser=hasattr(FB,'browser') and FB.browser)
			return
		elif result == 'bookmark':
			dialogs.addBookmark(FB,page=self.pageData.getPageNumber(),name=self.topic,page_disp=self.pageData.page)
		elif result == 'pageview':
			self.pageView()
		elif result == 'quote':
			self.stopThread()
			self.openPostDialog(post)
		elif result == 'refresh':
			self.refresh()
		elif result == 'edit':
			splash = dialogs.showActivitySplash(T(32318))
			try:
				pm = FB.getPostForEdit(post)
			finally:
				splash.close()
			pm.tid = self.tid
			if openPostDialog(editPM=pm):
				self.pid = pm.pid
				self.dontOpenPD = True
				self.fillRepliesList(self.pageData.getPageNumber())
		elif result == 'delete':
			self.stopThread()
			self.deletePost()
		elif result == 'subscribe':
			if subscribeThread(self.tid): self.threadItem.setProperty('subscribed','subscribed')
		elif result == 'unsubscribe':
			if unSubscribeThread(self.tid): self.threadItem.setProperty('subscribed','')
		elif result == 'extras':
			showUserExtras(post,ignore=(item.getProperty('usedExtras') or '').split(','))
		elif result == 'pm':
			quote = dialogs.dialogYesNo(T(32336),T(32337))
			self.openPostDialog(post,force_pm=True,no_quote=not quote)
		elif result == 'like':
			splash = dialogs.showActivitySplash(T(32338))
			try:
				post.like()
				self.updateItem(item, post)
			finally:
				splash.close()
		elif result == 'unlike':
			splash = dialogs.showActivitySplash(T(32339))
			try:
				post.unLike()
				self.updateItem(item, post)
			finally:
				splash.close()
		elif result == 'open_thread':
			self.openPostThread(post)
		elif result == 'help':
			if self.isPM():
				dialogs.showHelp('pm')
			else:
				dialogs.showHelp('posts')
		if self.empty: self.fillRepliesList()

	def pageView(self):
		with dialogs.ActivitySplash() as splash:
			out = ''
			if util.getSetting('use_skin_mods',True):
				divider = FB.unicode(u'\u2580'*200)
				underHeader = FB.unicode(u'\u2594'*200)
			else:
				divider = '_'*200
				underHeader = '-'*200
			keys = self.posts.keys()
			keys.sort()
			for k in keys:
				p = self.posts[k]
				postNumber = str(p.postNumber)
				splash.update(0,'Adding Post #{0}'.format(postNumber))
				out += '[COLOR FF808080]#' + postNumber + ' - ' + re.sub('<.*?>','',p.userName) + '[/COLOR][CR]'+ underHeader + '[CR]'
				out += p.messageAsDisplay(raw=True) + '[CR]' + divider + '[CR]'
		dialogs.showText('Posts', out)

	def deletePost(self):
		item = self.getControl(120).getSelectedItem()
		pid = item.getProperty('post')
		if not pid: return
		post = self.posts.get(pid)
		if deletePost(post,is_pm=self.isPM()):
			self.fillRepliesList(self.pageData.getPageNumber())

	def openPostThread(self,post):
		if not post: return
		dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,fid=post.fid,tid=post.tid,pid=post.postId,topic=post.topic,search_re=self.searchRE)

	def openPostDialog(self,post=None,force_pm=False,no_quote=False):
		tid = self.tid
		if force_pm:
			tid = 'private_messages'

		if post:
			item = self.getControl(120).getSelectedItem()
		else:
			if self.isPM():
				item = None
			else:
				if not self.getControl(120).size(): return
				item = self.getControl(120).getListItem(0)
		#if not item.getProperty('post'): item = self.getControl(120).getListItem(1)
		if item:
			pid = item.getProperty('post')
		else:
			pid = 0
		pm = openPostDialog(post,pid,tid,self.fid,no_quote=no_quote)
		if pm and not force_pm:
			self.firstRun = True
			self.fillRepliesList(self.pageData.getPageNumber('-1'),pid=pm.pid)

	def gotoPage(self,page):
		self.stopThread()
		self.fillRepliesList(page)

	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			if FB.loginError:
				self.getControl(111).setColorDiffuse('FFFF0000')
			else:
				self.getControl(111).setColorDiffuse('FF555555')
		#self.getControl(160).setLabel(FB.loginError)

def subscribeThread(tid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.subscribeThread(tid)
		if result == True:
			dialogs.showMessage(T(32304),T(32340),success=True)
		else:
			dialogs.showMessage(T(32323),T(32341),str(result),success=False)
		return result
	finally:
		splash.close()

def unSubscribeThread(tid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.unSubscribeThread(tid)
		if result == True:
			dialogs.showMessage(T(32304),T(32342),success=True)
		else:
			dialogs.showMessage(T(32323),T(32343),str(result),success=False)
		return result
	finally:
		splash.close()

def subscribeForum(fid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.subscribeForum(fid)
		if result == True:
			dialogs.showMessage(T(32304),T(32344),success=True)
		else:
			dialogs.showMessage(T(32323),T(32345),str(result),success=False)
		return result
	finally:
		splash.close()

def unSubscribeForum(fid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.unSubscribeForum(fid)
		if result == True:
			dialogs.showMessage(T(32304),T(32346),success=True)
		else:
			dialogs.showMessage(T(32323),T(32347),str(result),success=False)
		return result
	finally:
		splash.close()

######################################################################################
#
# Threads Window
#
######################################################################################
class ThreadsWindow(windows.PageWindow):
	def __init__( self, *args, **kwargs ):
		self.action = None
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.forumItem = kwargs.get('item')
		self.me = FB.user or '?'
		self.search = kwargs.get('search_terms')
		self.search_uname = kwargs.get('search_name','')
		self.forumElements = kwargs.get('forumElements','')

		self.setupSearch()

		self.empty = True
		self.textBase = '%s'
		self.newBase = '[B]%s[/B]'
		self.highBase = '%s'
		self.forum_desc_base = '[I]%s [/I]'
		self.started = False
		FB.updateAppURL(forum=self.fid)
		windows.PageWindow.__init__( self, *args, **kwargs )
		self.setPageData(FB)
		self.viewType = 'THREAD'

	def onInit(self):
		windows.BaseWindow.onInit(self)
		self.setLoggedIn()
		if self.started: return
		self.started = True
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.setTheme()
		self.fillThreadList()
		#self.setFocus(self.getControl(120))

	def setTheme(self):
		self.desc_base = unicode.encode(T(32162)+' %s','utf8')
		if self.fid == 'subscriptions':
			self.getControl(103).setLabel('[B]%s[/B]' % T(32175))
			self.getControl(104).setLabel('')
			self.setProperty('mode', 'subscriptions')
		else:
			self.getControl(103).setLabel('[B]%s[/B]' % T(32160))
			self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
			if self.search and not self.search == '@!RECENTTHREADS!@' and not self.search == '@!UNREAD!@':
				self.setProperty('mode', 'search')
			else:
				self.setProperty('mode', 'threads')
		create = False
		if not self.search and not self.fid == 'subscriptions': create = FB.canCreateThread(self.fid)
		try:
			self.getControl(201).setEnabled(create)
		except:
			pass

	def errorCallback(self,error):
		dialogs.showMessage(T(32050),T(32161),error.message,error=True)
		self.endProgress()

	def fillThreadList(self,page=''):
		self.getControl(106).setVisible(True)
		self.setFocusId(106)
		if self.fid == 'subscriptions':
			t = self.getThread(FB.getSubscriptions,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='SUBSCRIPTIONS')
			t.setArgs(page,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
		elif self.search:
			if self.search == '@!RECENTTHREADS!@':
				t = self.getThread(FB.getUserThreads,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='USERRECENTTHREADS')
				t.setArgs(uname=self.search_uname,page=page or 0,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
			elif self.search == '@!UNREAD!@':
				t = self.getThread(FB.getUnreadThreads,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='UNREADTHREADS')
				t.setArgs(page=page or 0,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
			elif self.fid:
				t = self.getThread(FB.searchAdvanced,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='SEARCHTHREADS')
				t.setArgs(self.search,page or 0,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData,fid=self.fid)
			else:
				t = self.getThread(FB.searchThreads,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='SEARCHTHREADS')
				t.setArgs(self.search,page or 0,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
		else:
			t = self.getThread(FB.getThreads,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='THREADS')
			t.setArgs(self.fid,page,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
		t.start()

	def doFillThreadList(self,data):
		self.endProgress()
		if 'newforumid' in data: self.fid = data['newforumid']
		if not data:
			if data.error == 'CANCEL': return
			LOG('GET THREADS ERROR')
			dialogs.showMessage(T(32050),T(32161),T(32053),data.error,success=False)
			return

		self.empty = False
		try:
			self.getControl(120).reset()
			self.setupPage(data.pageData)
			if not (self.addForums(data['forums']) + self.addThreads(data.data)):
				LOG('Empty Forum')
				dialogs.showMessage(T(32229),T(32230),success=False)
			self.setFocusId(120)
		except:
			ERROR('FILL THREAD ERROR')
			dialogs.showMessage(T(32050),T(32163),error=True)
		self.setLoggedIn()
		self.openElements()

	def openElements(self):
		if not self.forumElements: return
		if self.forumElements.get('section') == 'SUBSCRIPTIONS' and self.forumElements.get('forum'):
			item = util.selectListItemByProperty(self.getControl(120),'id',self.forumElements.get('forum'))
			if item:
				self.onClick(120)
			else:
				self.openRepliesWindow(self.forumElements)
				self.forumElements = None
		elif self.forumElements.get('thread'):
			item = util.selectListItemByProperty(self.getControl(120),'id',self.forumElements.get('thread'))
			if item:
				self.onClick(120)
			else:
				self.openRepliesWindow(self.forumElements)
				self.forumElements = None

	def addThreads(self,threads):
		self.setProperty('bullet',FB.MC.bullet)
		if not threads: return False
		prevItem = xbmcgui.ListItem(label='prev')
		prevItem.setProperty('paging','1')
		nextItem = xbmcgui.ListItem(label='next')
		nextItem.setProperty('paging','2')
		if self.pageData.prev and self.skinLevel(1): self.getControl(120).addItem(prevItem)
		for t in threads:
			if hasattr(t,'groupdict'):
				tdict = t.groupdict()
			else:
				tdict = t
			tid = tdict.get('threadid','')
			starter = tdict.get('starter',T(32348))
			title = tdict.get('title','')
			title = texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',title),FB)
			last = FB.unicode(tdict.get('lastposter',''))
			fid = tdict.get('forumid','')
			sticky = tdict.get('sticky') and 'sticky' or ''
			reply_count = unicode(tdict.get('reply_number','') or '')
			if starter == self.me: starterbase = self.highBase
			else: starterbase = self.textBase
			#title = (tdict.get('new_post') and self.newBase or self.textBase) % title
			titleDisplay = title
			if self.searchRE: titleDisplay = self.highlightTerms(FB,titleDisplay)
			item = xbmcgui.ListItem(label=starterbase % starter,label2=titleDisplay)
			if tdict.get('new_post'): item.setProperty('unread','unread')
			item.setInfo('video',{"Genre":sticky})
			item.setInfo('video',{"Director":starter == self.me and FB.MC.bullet or ''})
			item.setInfo('video',{"Studio":last == self.me and FB.MC.bullet or ''})
			item.setProperty("id",unicode(tid))
			item.setProperty("fid",unicode(fid))
			item.setProperty("lastposter",last)
			preview = tdict.get('short_content','')
			if preview: preview = re.sub(u'<[^>]+?>',u'',texttransform.convertHTMLCodes(preview,FB))

			if last:
				last = FB.unicode(self.desc_base % last)
				if preview: last += '[CR]' + preview
			else:
				last = preview
			if self.searchRE: last = self.highlightTerms(FB,last)
			item.setProperty("preview",preview)
			item.setProperty("last",last)
			item.setProperty("starter",starter)
			item.setProperty("lastid",tdict.get('lastid',''))
			item.setProperty('title',title)
			item.setProperty('announcement',unicode(tdict.get('announcement','')))
			item.setProperty('reply_count',reply_count)
			item.setProperty('subscribed',tdict.get('subscribed') and 'subscribed' or '')
			item.setProperty('avatar',str(tdict.get('icon_url') or ''))
			item.setProperty('thumbnail',str(tdict.get('thumb') or ''))
			item.setProperty('replies',reply_count)
			item.setProperty('views',str(tdict.get('view_number') or ''))
			item.setProperty('last_reply_time',str(tdict.get('last_reply_time') or ''))
			self.getControl(120).addItem(item)
		if self.pageData.next and self.skinLevel(1): self.getControl(120).addItem(nextItem)
		return True

	def addForums(self,forums):
		if not forums: return False
		for f in forums:
			if hasattr(f,'groupdict'):
				fdict = f.groupdict()
			else:
				fdict = f
			fid = fdict.get('forumid','')
			title = fdict.get('title',T(32050))
			desc = fdict.get('description') or T(32172)
			text = self.textBase
			title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?',FB)
			item = xbmcgui.ListItem(label=self.textBase % T(32164),label2=text % title)
			item.setInfo('video',{"Genre":'is_forum'})
			desc = self.forum_desc_base % texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',FB.MC.brFilter.sub(' ',desc)),FB)
			item.setProperty("last",desc)
			item.setProperty("preview",desc)
			item.setProperty("title",title)
			item.setProperty("topic",title)
			item.setProperty("id",fid)
			item.setProperty("fid",fid)
			item.setProperty('thumbnail',str(fdict.get('thumb') or ''))
			item.setProperty("is_forum",'True')
			if fdict.get('new_post'): item.setProperty('unread','unread')
			item.setProperty('subscribed',fdict.get('subscribed') and 'subscribed' or '')
			self.getControl(120).addItem(item)
		return True

	def openRepliesWindow(self,forumElements=None):
		forumElements = forumElements or self.forumElements
		self.forumElements = None
		if forumElements and forumElements.get('section') == 'SUBSCRIPTIONS' and forumElements.get('forum'):
			item = util.getListItemByProperty(self.getControl(120),'id',forumElements.get('forum'))
			if not item:
				item = xbmcgui.ListItem()
				item.setProperty('fid',forumElements.get('forum'))
				item.setProperty('id',forumElements.get('forum'))
				item.setProperty('is_forum','True')
		elif forumElements and forumElements.get('thread'):
			item = util.getListItemByProperty(self.getControl(120),'id',forumElements.get('thread'))
			if not item:
				item = xbmcgui.ListItem()
				item.setProperty('fid',forumElements.get('forum'))
				item.setProperty('id',forumElements.get('thread'))
		else:
			item = self.getControl(120).getSelectedItem()
			if self.processPaging(item.getProperty('paging')): return

		item.setProperty('unread','')
		fid = item.getProperty('fid') or self.fid
		topic = item.getProperty('title')
		if item.getProperty('is_forum') == 'True':
			w = dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",return_window=True,fid=fid,topic=topic,item=item)
			#self.fid = fid
			#self.topic = topic
			#self.setTheme()
			#self.fillThreadList()
		else:
			w = dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,return_window=True,fid=fid,topic=topic,item=item,search_re=self.searchRE,forumElements=forumElements)

		action = w.action
		del w
		if action and action.action == 'CHANGE-FORUM':
			self.action = action
			self.doClose()

	def onFocus( self, controlId ):
		self.controlId = controlId

	def onClick( self, controlID ):
		if controlID == 120:
			if not self.empty: self.stopThread()
			self.openRepliesWindow()
		elif controlID == 106:
			self.stopThread()
			return
		elif controlID == 201:
			self.createThread()

		if self.empty: self.fillThreadList()
		windows.PageWindow.onClick(self,controlID)

	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2 or action == ACTION_PREVIOUS_MENU:
			if util.Control.HasFocus(group=196):
				if self.getControl(120).size():
					self.setFocusId(120)
					return
		windows.PageWindow.onAction(self,action)

	def onClose(self):
		FB.updateAppURL(forum=self.fid,close=True)

	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu('Options',with_splash=True)
		try:
			if item:
				if item.getProperty("is_forum") == 'True':
					if FB.isForumSubscribed(item.getProperty('id'),item.getProperty('subscribed')):
						if FB.canUnSubscribeForum(item.getProperty('id')): d.addItem('unsubscribeforum', T(32242))
					else:
						if FB.canSubscribeForum(item.getProperty('id')): d.addItem('subscribeforum', T(32243))
				else:
					if FB.isThreadSubscribed(item.getProperty('id'),item.getProperty('subscribed')):
						if FB.canUnSubscribeThread(item.getProperty('id')): d.addItem('unsubscribe', T(32240))
					else:
						if FB.canSubscribeThread(item.getProperty('id')): d.addItem('subscribe', T(32236))
				if self.fid != 'subscriptions':
					if self.forumItem:
						if FB.isForumSubscribed(self.forumItem.getProperty('id'),self.forumItem.getProperty('subscribed')):
							if FB.canUnSubscribeForum(self.forumItem.getProperty('id')): d.addItem('unsubscribecurrentforum', T(32242) + ': ' + self.forumItem.getProperty('topic')[:25])
						else:
							if FB.canSubscribeForum(self.forumItem.getProperty('id')): d.addItem('subscribecurrentforum', T(32243) + ': ' + self.forumItem.getProperty('topic')[:25])
					if FB.canCreateThread(item.getProperty('id')):
						d.addItem('createthread',T(32252))
				if FB.canSearchAdvanced('TID'):
					d.addItem('search','{0} [B][I]{1}[/I][/B]'.format(T(32371),item.getProperty('title')[:30]))
			d.addItem('bookmark',T(32553))
			d.addItem('help',T(32244))
		finally:
			d.cancel()
		result = d.getResult()
		if not result: return
		if result == 'subscribe':
			if subscribeThread(item.getProperty('id')): item.setProperty('subscribed','subscribed')
		elif result == 'subscribeforum':
			if subscribeForum(item.getProperty('id')): item.setProperty('subscribed','subscribed')
		elif result == 'unsubscribe':
			if unSubscribeThread(item.getProperty('id')):
				item.setProperty('subscribed','')
				self.removeItem(item)
		elif result == 'unsubscribeforum':
			if unSubscribeForum(item.getProperty('id')):
				item.setProperty('subscribed','')
				self.removeItem(item)
		elif result == 'subscribecurrentforum':
			if subscribeForum(self.fid): self.forumItem.setProperty('subscribed','subscribed')
		elif result == 'unsubscribecurrentforum':
			if unSubscribeForum(self.fid): self.forumItem.setProperty('subscribed','')
		elif result == 'search':
			if not item.getProperty("is_forum") == 'True':
				searchPosts(item.getProperty('id'))
			else:
				searchThreads(item.getProperty('id'))
		elif result == 'createthread':
			self.createThread()
		elif result == 'bookmark':
			dialogs.addBookmark(FB, name=self.topic)
		elif result == 'help':
			if self.fid == 'subscriptions':
				dialogs.showHelp('subscriptions')
			else:
				dialogs.showHelp('threads')

	def createThread(self):
		pm = openPostDialog(fid=self.fid,donotpost=True)
		if pm:
			splash = dialogs.showActivitySplash(T(32349))
			try:
				result = FB.createThread(self.fid,pm.title,pm.message)
				if result == True:
					dialogs.showMessage(T(32304),T(32350),'\n',pm.title,success=True)
					self.fillThreadList()
				else:
					dialogs.showMessage(T(32323),T(32351),'\n',str(result),success=False)
			finally:
				splash.close()


	def removeItem(self,item):
		clist = self.getControl(120)
		#items = []
		storageList = xbmcgui.ControlList(-100,-100,80,80)
		for idx in range(0,clist.size()):
			i = clist.getListItem(idx)
			#print str(item.getProperty('id')) + ' : ' + str(i.getProperty('id'))
			if item.getProperty('id') != i.getProperty('id'): storageList.addItem(i)
		clist.reset()
		clist.addItems(self.getListItems(storageList))
		del storageList

	def getListItems(self,alist):
		items = []
		for x in range(0,alist.size()):
			items.append(alist.getListItem(x))
		return items

	def gotoPage(self,page):
		self.stopThread()
		self.fillThreadList(page)

	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			if FB.loginError:
				self.getControl(111).setColorDiffuse('FFFF0000')
			else:
				self.getControl(111).setColorDiffuse('FF555555')
		#self.getControl(160).setLabel(FB.loginError)

######################################################################################
#
# Forums Window
#
######################################################################################
class ForumsWindow(windows.BaseWindow):
	def __init__( self, *args, **kwargs ):
		windows.BaseWindow.__init__( self, *args, **kwargs )
		#FB.setLogin(self.getUsername(),self.getPassword(),always=getSetting('always_login') == 'true')
		self.empty = True
		self.setAsMain()
		self.started = False
		self.headerIsDark = False
		self.forumElements = None
		self.headerTextFormat = '[B]%s[/B]'
		self.forumsManagerWindowIsOpen = False
		self.lastFB = None
		self.data = kwargs.get('data')
		self.viewType = 'FORUM'
		windows.WM.main = self

	def newPostsCallback(self,signal,data):
		self.openForumsManager(external=True)

	def getUsername(self):
		data = util.loadForumSettings(FB.getForumID())
		if data and data['username']: return data['username']
		return ''

	def getPassword(self):
		data = util.loadForumSettings(FB.getForumID())
		if data and data['password']: return data['password']
		return ''

	def getNotify(self):
		data = util.loadForumSettings(FB.getForumID())
		if data: return data['notify']
		return False

	def hasLogin(self):
		return self.getUsername() != '' and self.getPassword() != ''

	def onInit(self):
		windows.BaseWindow.onInit(self)
		self.setLoggedIn() #So every time we return to the window we check
		self.getControl(112).setVisible(False)
		try:
			if self.started: return
			windows.SIGNALHUB.registerReceiver('NEW_POSTS', self, self.newPostsCallback)
			self.setProperty('ForumBrowserMAIN','MAIN')
			self.setVersion()
			self.setStopControl(self.getControl(105))
			self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
			self.started = True
			if self.data:
				self.startProgress()
				self.fillForumList(data=self.data)
			else:
				self.showProgress()
				self.setFocusId(105)
				self.startGetForumBrowser()
		except:
			self.setStopControl(self.getControl(105)) #In case the error happens before we do this
			self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
			self.hideProgress()
			self.endProgress() #resets the status message to the forum name
			self.setFocusId(202)
			raise

	def startGetForumBrowser(self,forum=None,url=None,all_at_once=True):
		self.getControl(201).setEnabled(False)
		self.getControl(203).setEnabled(False)
		self.getControl(204).setEnabled(False)
		self.getControl(208).setEnabled(False)
		if all_at_once:
			t = self.getThread(self.openForum,finishedCallback=self.doFillForumList,errorCallback=self.errorCallback,name='OPENFORUM')
			t.setArgs(forum=forum,url=url,callback=t.progressCallback,donecallback=t.finishedCallback)
			t.start()
		else:
			t = self.getThread(getForumBrowser,finishedCallback=self.endGetForumBrowser,errorCallback=self.errorCallback,name='GETFORUMBROWSER')
			t.setArgs(forum=forum,url=url,donecallback=t.finishedCallback)
			t.start()

	def openForum(self,forum=None,url=None,callback=None,donecallback=None):
		result = getForumBrowser(forum,url)
		if not result:
			if donecallback: donecallback(None)
			return None
		fb, forumElements = result
		self.endGetForumBrowser(fb, forumElements, skip_fillForumList=True)
		self.fillForumList(first=True, skip_getForums=True)
		FB.getForums(callback=callback,donecallback=donecallback)

	def endGetForumBrowser(self,fb,forumElements,skip_fillForumList=False):
		global FB
		FB = fb
		#self.setTheme()
		self.getControl(112).setVisible(False)
		self.resetForum(no_theme=True)
		if not skip_fillForumList: self.fillForumList(True)
		setSetting('last_forum',FB.getForumID())
		self.forumElements = forumElements

	def openElements(self):
		if not self.forumElements: return
		forumElements = self.forumElements
		if not FB or forumElements.get('forumID') != FB.getForumID():
			global STARTFORUM
			STARTFORUM = util.createForumBrowserURL(forumElements)
			self.startGetForumBrowser(all_at_once=True)
			return

		if forumElements.get('section'):
			if forumElements.get('section') == 'SUBSCRIPTIONS':
				self.openSubscriptionsWindow(forumElements)
				self.forumElements = None
			elif forumElements.get('section') == 'PM':
				self.openPMWindow(forumElements)
				self.forumElements = None
		elif forumElements.get('forum'):
			fid = forumElements.get('forum')
			item = util.selectListItemByProperty(self.getControl(120),'id',fid)
			if item:
				self.onClick(120)
			else:
				self.openThreadsWindow(forumElements)
				self.forumElements = None
		elif forumElements.get('thread'):
			#tid = forumElements.get('thread')
			self.forumElements = None
		elif forumElements.get('post'):
			#pid = forumElements.get('post')
			self.forumElements = None

	def setVersion(self):
		dialogs.setGlobalSkinProperty('ForumBrowser_version', 'v' + __version__)

	def setTheme(self):
		hc = FB.theme.get('header_color')
		if hc and hc.upper() != 'FFFFFF':
			self.headerIsDark = self.hexColorIsDark(hc)
			dialogs.setGlobalSkinProperty('ForumBrowser_header_color','FF' + hc.upper())
		else:
			self.headerIsDark = False
			dialogs.setGlobalSkinProperty('ForumBrowser_header_color','')
		if self.headerIsDark:
			self.setProperty('header_is_dark', '1')
			dialogs.setGlobalSkinProperty('ForumBrowser_header_is_dark','1')
			dialogs.setGlobalSkinProperty('ForumBrowser_header_text_color','FFFFFFFF')
		else:
			self.setProperty('header_is_dark', '0')
			dialogs.setGlobalSkinProperty('ForumBrowser_header_is_dark','0')
			dialogs.setGlobalSkinProperty('ForumBrowser_header_text_color','FF000000')

		self.setLabels()

	def hexColorIsDark(self,h):
		r,g,b = self.hexToRGB(h)
		if r > 140 or g > 140 or b > 200: return False
		return True

	def hexToRGB(self,h):
		try:
			r = h[:2]
			g = h[2:4]
			b = h[4:]
			#print h
			#print r,g,b
			return (int(r,16),int(g,16),int(b,16))
		except:
			ERROR('hexToRGB()')
			return (255,255,255)

	def setLabels(self):
		self.getControl(103).setLabel(self.headerTextFormat % T(32170))
		self.getControl(104).setLabel(self.headerTextFormat % FB.getDisplayName())

	def errorCallback(self,error):
		self.failedToGetForum()
		dialogs.showMessage(T(32050),T(32171),error.message,error=True)
		self.setFocusId(202)
		self.endProgress()

	def failedToGetForum(self):
		global FB
		FB = self.lastFB
		if FB: setSetting('last_forum',FB.getForumID())

	def stopThread(self):
		self.failedToGetForum()
		windows.ThreadWindow.stopThread(self)
		if FB: self.getControl(104).setLabel('[B]%s[/B]' % FB.getDisplayName())

	def fillForumList(self,first=False,data=None,skip_getForums=False):
		if not FB: return
		self.setLabels()
		if data:
			self.doFillForumList(data)
			return
		if not FB.guestOK() and not self.hasLogin():
			yes = dialogs.dialogYesNo(T(32352),T(32353),T(32354),T(32355))
			if yes:
				setLogins()
				if not self.hasLogin():
					self.setFocusId(202)
					return
				self.resetForum()
			else:
				self.setFocusId(202)
				return
		self.setFocusId(105)
		if first and getSetting('auto_thread_subscriptions_window') == 'true':
			if self.hasLogin() and FB.hasSubscriptions():
				FB.getForums(callback=self.setProgress,donecallback=self.doFillForumList)
				self.openSubscriptionsWindow()
				return
		if skip_getForums: return
		t = self.getThread(FB.getForums,finishedCallback=self.doFillForumList,errorCallback=self.errorCallback,name='FORUMS')
		t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()

	def doFillForumList(self,data):
		self.endProgress()
		self.lastFB = FB
		if not data:
			if data == None: return
			self.setFocusId(202)
			if data.error == 'CANCEL': return
			dialogs.showMessage(T(32050),T(32171),T(32053),'[CR]'+data.error,success=False)
			return
		self.setBackground()
		self.setLogo(data.getExtra('logo'),data.getExtra('force',False))
		self.data = data
		self.empty = True

		if dialogs.alignChanged():
			self._doHop(self.data,"script-forumbrowser-forums.xml",False)

		try:
			#xbmcgui.lock()
			self.getControl(120).reset()
			self.setPMCounts(data.getExtra('pm_counts'))
			self.setStats(data.getExtra('stats'))

			for f in data.data:
				self.empty = False
				if hasattr(f,'groupdict'):
					fdict = f.groupdict()
				else:
					fdict = f
				fid = fdict.get('forumid','')
				title = fdict.get('title',T(32050))
				realdesc = texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',FB.MC.brFilter.sub(' ',fdict.get('description',''))),FB)
				sub = fdict.get('subforum')
				if sub and not realdesc:
					desc = T(32173)
				else:
					desc = realdesc or T(32172)

				title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?',FB)
				item = xbmcgui.ListItem(label=title)
				item.setInfo('video',{"Genre":sub and 'sub' or ''})
				item.setProperty("ignore",fdict.get('ignore') and 'ignore' or '')
				item.setProperty("description",desc)
				item.setProperty("realdescription",realdesc)
				item.setProperty("topic",title)
				item.setProperty("id",unicode(fid))
				item.setProperty("link",fdict.get('link',''))
				item.setProperty("artwork",fdict.get('logo_url') or '')
				item.setProperty("thumbnail",fdict.get('thumb') or '')
				if fdict.get('new_post'): item.setProperty('unread','unread')
				item.setProperty('subscribed',fdict.get('subscribed') and 'subscribed' or '')
				self.getControl(120).addItem(item)
				self.setFocusId(120)
		except:
			#xbmcgui.unlock()
			ERROR('FILL FORUMS ERROR')
			dialogs.showMessage(T(32050),T(32174),error=True)
			self.setFocusId(202)
		if self.empty: self.setFocusId(202)
		#xbmcgui.unlock()
		self.setLoggedIn()
		self.resetForum()
		if not FB.guestOK() and not FB.isLoggedIn():
			yes = dialogs.dialogYesNo(T(32352),T(32353),T(32354),T(32355))
			if yes:
				setLogins()
				self.resetForum()
				self.fillForumList()
		if data.select is not None: self.getControl(120).selectItem(data.select)
		self.openElements()

	def setBackground(self):
		background = None
		if getSetting('show_forum_specific_backgrounds',True): background = FB.background
		windows.setWindowBackgroundImage(background,'FORUM',save=False)

	def setLogoFromFile(self):
		logopath = getCurrentLogo()
		if not logopath:
			LOG('NO LOGO WHEN SETTING LOGO')
			return
		return self.getControl(250).setImage(logopath)

	def setLogo(self,logo,force=False):
		if not logo: return
		if getSetting('save_logos',False):
			exists, logopath = util.getCachedLogo(logo,FB.getForumID())
			if exists and not force:
				logo = logopath
			else:

				try:
					open(logopath,'wb').write(urllib2.urlopen(logo).read())
					logo = logopath
				except:
					LOG('ERROR: Could not save logo for: ' + FB.getForumID())
		if logo: self.getControl(250).setImage(logo)
		if 'ForumBrowser' in FB.browserType:
			image = '../../../media/forum-browser-logo-128.png'
		else:
			image = '../../../media/forum-browser-%s.png' % FB.browserType or ''
		self.getControl(249).setImage(image)

	def setPMCounts(self,pm_counts=False):
		if not FB: return
		if pm_counts == False: return
		disp = ''
		if not pm_counts: pm_counts = FB.getPMCounts()
		if pm_counts: disp = ' (%s/%s)' % (pm_counts.get('unread','?'),pm_counts.get('total','?'))
		messages_text = T(32909)
		if FB.hasConversation(): messages_text = T(32941)

		self.getControl(203).setLabel(messages_text + disp)
		self.setLoggedIn()

	def setStats(self,stats=None):
		if not stats: stats = {}
		self.setProperty('stats_total_threads',str(stats.get('total_threads','')))
		self.setProperty('stats_total_posts',str(stats.get('total_posts','')))
		self.setProperty('stats_total_members',str(stats.get('total_members','')))
		self.setProperty('stats_total_online',str(stats.get('total_online','')))
		self.setProperty('stats_guest_online',str(stats.get('guest_online','')))

	def openPMWindow(self,forumElements=None):
		if self.nextWindow(self.data,RepliesWindow,"script-forumbrowser-replies.xml" ,tid='private_messages',topic=T(32176),forumElements=forumElements):
			return
		#dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,tid='private_messages',topic=T(32176),forumElements=forumElements)
		self.setPMCounts(FB.getPMCounts())

	def openThreadsWindow(self,forumElements=None):
		forumElements = forumElements or self.forumElements
		self.forumElements = None
		fid = None
		topic = ''
		item = None
		if forumElements and forumElements.get('forum'):
			fid = forumElements.get('forum')
			item = util.getListItemByProperty(self.getControl(120),'id',fid)
		else:
			item = self.getControl(120).getSelectedItem()

		if item:
			if item.getProperty('ignore'): return False
			link = item.getProperty('link')
			if link:
				return self.openLink(link)
			if not fid: fid = item.getProperty('id')
			topic = item.getProperty('topic')
		if self.nextWindow(self.data, ThreadsWindow,"script-forumbrowser-threads.xml",fid=fid,topic=topic,item=item,forumElements=forumElements):
			return True
		self.setPMCounts(FB.getPMCounts())
		return True

	def openLink(self,link):
		LOG('Forum is a link. Opening URL: ' + link)
		webviewer.getWebResult(link,dialog=True,browser=hasattr(FB,'browser') and FB.browser)

	def openSubscriptionsWindow(self,forumElements=None):
		fid = 'subscriptions'
		topic = T(32175)
		if self.nextWindow(self.data, ThreadsWindow,"script-forumbrowser-threads.xml",fid=fid,topic=topic,forumElements=forumElements):
			return
		self.setPMCounts(FB.getPMCounts())

	def showOnlineUsers(self):
		s = dialogs.showActivitySplash(T(32356))
		try:
			users = FB.getOnlineUsers()
		finally:
			s.close()
		if isinstance(users,str):
			dialogs.showMessage(T(32357),users,success=False)
			return
		users.sort(key=lambda u: u['user'].lower())
		d = dialogs.OptionsChoiceMenu(T(32358))
		d.setContextCallback(self.showOnlineContext)
		for u in users:
			d.addItem(u.get('userid'),u.get('user'),u.get('avatar') or '../../../media/forum-browser-avatar-none.png',u.get('status'))
		d.getResult(close_on_context=False)

	def showOnlineContext(self,menu,item):
		d = dialogs.ChoiceMenu(T(32051))
		if FB.canPrivateMessage(): d.addItem('pm',T(32253).format(item.get('disp')))
		if FB.canSearchAdvanced('UID'): d.addItem('search',T(32359).format(item.get('disp')))
		if FB.canGetUserInfo(): d.addItem('info',T(32360))
		result = d.getResult()
		if not result: return
		if result == 'pm':
			menu.close()
			self.function(self.data,'script-forumbrowser-forums.xml',openPostDialog,tid='private_messages',to=item.get('disp'))
			return
		elif result == 'search':
			menu.close()
			searchUser(item.get('id'))
		elif result == 'info':
			self.showUserInfo(item.get('id'),item.get('disp'))

	def showUserInfo(self,uid,uname):
		s = dialogs.showActivitySplash(T(32361))
		try:
			user = FB.getUserInfo(uid,uname)
			if not user: return
			out = '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32362),user.name)
			out += '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32363),user.status)
			out += '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32364),user.postCount)
			out += '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32365),user.joinDate)
			if user.activity: out += '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32366),user.activity)
			if user.lastActivityDate: out += '[B]%s:[/B] [COLOR FF550000]%s[/COLOR]\n' % (T(32367),user.lastActivityDate)
			for k,v in user.extras.items():
				out += '[B]' + k.title() + ':[/B] [COLOR FF550000]' + v + '[/COLOR]\n'
			dialogs.showMessage(T(32368),out,scroll=True)
		finally:
			s.close()

	def changeForum(self,forum=None):
		if not self.closeSubWindows(): return
		if not forum: forum = askForum()
		if not forum: return False
		url = None
		self.stopThread()
		fid = 'Unknown'
		if FB: fid = FB.getForumID()
		LOG('------------------ CHANGING FORUM FROM: %s TO: %s' % (fid,forum))
		self.startGetForumBrowser(forum,url=url)
		return True

	def closeSubWindows(self):
		for x in range(0,10):  # @UnusedVariable
			winid = xbmcgui.getCurrentWindowId()
			if winid > 0:
				window = xbmcgui.Window(winid)
				if window.getProperty('ForumBrowserMAIN'): return True
				#print winid
				xbmc.executebuiltin('Action(PreviousMenu)')
				xbmc.sleep(100)
			else:
				print winid

		return False

	def onFocus( self, controlId ):
		self.controlId = controlId

	def onClick( self, controlID ):
		if controlID == 200:
			self.stopThread()
			windows.WM.main.openSettings() # @UndefinedVariable
		elif controlID == 201:
			self.stopThread()
			self.openSubscriptionsWindow()
		elif controlID == 203:
			self.stopThread()
			self.openPMWindow()
		elif controlID == 202:
			return self.openForumsManager()
		elif controlID == 205:
			searchPosts()
		elif controlID == 206:
			searchThreads(FB.getForumID())
		elif controlID == 207:
			searchUser()
		elif controlID == 208:
			self.showUnread()
		elif controlID == 120:
			if not self.empty: self.stopThread()
			self.openThreadsWindow()
		elif controlID == 105:
			self.stopThread()
			self.setFocusId(202)
			return
		if windows.BaseWindow.onClick(self, controlID): return
		if self.empty: self.fillForumList()

	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			if util.Control.HasFocus(group=198):
				self.setFocusId(204)
				return
			elif util.Control.HasFocus(group=196):
				if self.getControl(120).size():
					self.setFocusId(120)
					return
			if not self.preClose(): return
		windows.BaseWindow.onAction(self,action)

	def openForumsManager(self,external=False):
		if self.forumsManagerWindowIsOpen: return
		self.forumsManagerWindowIsOpen = True
		size = 'manage'
		if external:
			methods = ('manage','small','full')
			if StreamUtils.isPlaying():
				size = methods[getSetting('notify_method_video',0)]
			else:
				size = methods[getSetting('notify_method',0)]

		forumsManager(self,size=size,forumID=FB and FB.getForumID() or None)
		self.forumsManagerWindowIsOpen = False
		if not FB: return
		forumID = FB.getForumID()
		fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
		logo = fdata.urls.get('logo','')
		self.setLogo(logo)
		FB.theme = fdata.theme
		self.setTheme()

	def selectedIndex(self):
		idx = self.getControl(120).getSelectedPosition()
		if idx < 0: return None
		return idx

	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu('Options',with_splash=True)
		try:
			if FB:
				if item:
					fid = item.getProperty('id')
					if FB.isForumSubscribed(fid,item.getProperty('subscribed')):
						if FB.canUnSubscribeForum(fid): d.addItem('unsubscribecurrentforum', T(32242))
					else:
						if FB.canSubscribeForum(fid): d.addItem('subscribecurrentforum', T(32243))
					if FB.canSearchAdvanced('FID'):
						d.addItem('search','{0} [B][I]{1}[/I][/B]'.format(T(32371),item.getProperty('topic')[:30]))
				if FB.canGetOnlineUsers(): d.addItem('online',T(32369))
				d.addItem('foruminfo',T(32370))
			d.addItem('bookmarks',T(32554))
			d.addItem('refresh',T(32054))
			d.addItem('help',T(32244))
		finally:
			d.cancel()
		result = d.getResult()
		if result == 'subscribecurrentforum':
			if subscribeForum(fid): pass #item.setProperty('subscribed','subscribed') #commented out because can't change if we unsubscribe from subs view
		elif result == 'unsubscribecurrentforum':
			if unSubscribeForum(fid): item.setProperty('subscribed','')
		elif result == 'search':
			searchThreads(self,item.getProperty('id'))
		elif result == 'foruminfo':
			self.showForumInfo()
		elif result == 'bookmarks':
			url = dialogs.bookmarks()
			if not url: return
			self.forumElements = util.parseForumBrowserURL(url)
			self.openElements()
		elif result == 'refresh':
			if FB:
				self.fillForumList()
			else:
				self.startGetForumBrowser()
		elif result == 'online':
			self.showOnlineUsers()
		elif result == 'help':
			dialogs.showHelp('forums')

	def showForumInfo(self):
		out = ''
		for k,v in FB.getForumInfo():
			out += u'[B]%s[/B]: [COLOR FFA00000]%s[/COLOR][CR]' % (k.replace('_',' ').title(),v)
		dialogs.showMessage(T(32372),out,scroll=True)

	def showUnread(self):
		dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",search_terms='@!UNREAD!@',topic=T(32565))

	def preClose(self):
		if not getSetting('ask_close_on_exit') == 'true': return True
		if self.closed: return True
		return dialogs.dialogYesNo(T(32373),T(32373))

	def resetForum(self,hidelogo=True,no_theme=False):
		if not FB: return
		FB.setLogin(self.getUsername(),self.getPassword(),always=getSetting('always_login') == 'true',rules=util.loadForumSettings(FB.getForumID(),get_rules=True))
		self.setButtons()
		setSetting('last_forum',FB.getForumID())
		if no_theme: return
		if hidelogo: self.getControl(250).setImage('')
		self.setTheme()
		self.setLogoFromFile()

	def setLoggedIn(self):
		if not FB: return
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			if FB.loginError:
				self.getControl(111).setColorDiffuse('FFFF0000')
			else:
				self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)
		self.getControl(112).setVisible(FB.SSL)
		self.setButtons()

	def setButtons(self):
		loggedIn = FB.isLoggedIn()
		self.getControl(201).setEnabled(loggedIn and FB.hasSubscriptions())
		self.getControl(203).setEnabled(loggedIn and FB.hasPM())
		self.getControl(204).setEnabled(FB.canSearch())
		self.getControl(205).setEnabled(FB.canSearchPosts())
		self.getControl(206).setEnabled(FB.canSearchThreads())
		self.getControl(207).setEnabled(FB.canSearchAdvanced('UNAME'))
		self.getControl(208).setEnabled(FB.canGetUnreadThreads())

	def openSettings(self,external=False):
		#if not FB: return
		oldLogin = FB and self.getUsername() + self.getPassword() or ''
		doSettings(self)
		newLogin = FB and self.getUsername() + self.getPassword() or ''
		self.setBackground()
		if not oldLogin == newLogin:
			self.resetForum(False)
			self.setPMCounts()
		self.setLoggedIn()
		self.resetForum(False)
		global THEME
		skin = util.getSavedTheme(current=THEME)
		forumbrowser.ForumPost.hideSignature = getSetting('hide_signatures',False)
		refresh = util.xbmcSkinAwaitingRefresh()
		if (skin != THEME or refresh) and external:
			dialogs.showMessage(T(32374),T(32375))
		elif (skin != THEME or refresh) and not external:
			THEME = util.getSavedTheme(current=skin,get_current=True)
			self._doHop(self.data,"script-forumbrowser-forums.xml",refresh)

# Functions -------------------------------------------------------------------------------------------------------------------------------------------
def appendSettingList(key,value,limit=0):
	slist = getSetting(key,[])
	if value in slist: slist.remove(value)
	slist.append(value)
	if limit: slist = slist[-limit:]
	setSetting(key,slist)

def getSearchDefault(setting,default='',with_global=True,heading=T(32376),new=T(32377),extra=None):
	if getSetting('show_search_history',True):
		slist = getSetting(setting,[])
		slistDisplay = slist[:]
		if with_global:
			glist = getSetting('last_search',[])
			glist.reverse()
			for g in glist:
				if not g in slist:
					slistDisplay.insert(0,'[COLOR FFAAAA00]%s[/COLOR]' % g)
					slist.insert(0,g)
	else:
		slist = []
		slistDisplay = []

	if slist or extra:
		slist.reverse()
		slistDisplay.reverse()
		if extra:
			for eid,edisplay in extra:
				slistDisplay.insert(0,'[[COLOR FF009999][B]%s[/B][/COLOR]]' % edisplay)
				slist.insert(0,eid)
		slistDisplay.insert(0,'[[COLOR FF00AA00][B]%s[/B][/COLOR]]' % new)
		slist.insert(0,'')
		idx = xbmcgui.Dialog().select(heading,slistDisplay)
		if idx < 0: return None
		elif idx > 0: default = slist[idx]
	return default

def searchPosts(tid=None):
	default = getSearchDefault('last_post_search')
	if default == None: return
	terms = dialogs.doKeyboard(T(32330),default)
	if not terms: return
	appendSettingList('last_post_search',terms,10)
	appendSettingList('last_search',terms,10)
	dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,search_terms=terms,topic=T(32378),tid=tid)

def searchThreads(fid=None):
	default = getSearchDefault('last_thread_search')
	if default == None: return
	terms = dialogs.doKeyboard(T(32330),default)
	if not terms: return
	appendSettingList('last_thread_search',terms,10)
	appendSettingList('last_search',terms,10)
	dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",search_terms=terms,topic=T(32379),fid=fid)

def searchUser(uid=None):
	uname = None
	if not uid:
		default = getSearchDefault('last_search_user',with_global=False,heading=T(32380),new=T(32381))
		if default == None: return
		if default:
			uname = default
		else:
			uname = dialogs.doKeyboard(T(32382),default)
		if not uname: return
		appendSettingList('last_search_user',uname,10)
	extra = None
	ct = FB.canGetUserThreads()
	if ct:
		if not extra: extra = []
		extra.append(('@!RECENTTHREADS!@',T(32383)))
	ct = FB.canGetUserPosts()
	if ct:
		if not extra: extra = []
		extra.append(('@!RECENT!@',T(32384)))

	default = getSearchDefault('last_user_search',extra=extra)
	if default == None: return
	topic = T(32385)
	if default == '@!RECENT!@':
		terms = default
		topic = T(32384)
	elif default == '@!RECENTTHREADS!@':
		terms = default
		dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",search_terms=terms,search_name=uname,topic=T(32383))
		return
	else:
		terms = dialogs.doKeyboard(T(32330),default)
		if not terms: return
		appendSettingList('last_user_search',terms,10)
		appendSettingList('last_search',terms,10)
	dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,search_terms=terms,topic=topic,uid=uid,search_name=uname)

def addParserRule(forumID,key,value):
	if key.startswith('extra.'):
		util.saveForumSettings(rules={key:value})
	else:
		rules = util.loadForumSettings(get_rules=True)
		if key == 'head':
			vallist = rules.get('head') and rules['head'].split(';&;') or []
		elif key == 'tail':
			vallist = rules.get('tail') and rules['tail'].split(';&;') or []
		if not value in vallist: vallist.append(value)
		util.saveForumSettings(rules={key:';&;'.join(vallist)})

def removeParserRule(forumID,key,value=None):
	if key.startswith('extra.'):
		util.saveForumSettings(rules={key:None})
	else:
		rules = util.loadForumSettings(get_rules=True)
		if key == 'head':
			vallist = rules.get('head') and rules['head'].split(';&;') or []
		elif key == 'tail':
			vallist = rules.get('tail') and rules['tail'].split(';&;') or []
		if value in vallist: vallist.pop(vallist.index(value))
		util.saveForumSettings(rules={key:';&;'.join(vallist)})

def listForumSettings():
	return os.listdir(FORUMS_SETTINGS_PATH)

def fidSortFunction(fid):
	if fid[:3] in ['TT.','FR.','PB.','YK.','GB.','YT.']: return fid[3:]
	return fid

def askForum(just_added=False,just_favs=False,caption=T(32386),forumID=None,hide_extra=False):
	favs = getFavorites()
	flist_tmp = os.listdir(FORUMS_PATH)
	rest = sorted(flist_tmp,key=fidSortFunction)
	if favs:
		for f in favs:
			if f in rest: rest.pop(rest.index(f))
		favs.append('')
	if just_favs:
		if not favs: return None
		whole = favs[:-1]
	elif just_added:
		whole = flist_tmp
	else:
		whole = favs + rest
	menu = dialogs.ImageChoiceMenu(caption)
	final = []
	for f in whole:
		if not f in final: final.append(f)
	for f in final:
		if not f.startswith('.'):
			if not f:
				menu.addSep()
				continue
			path = util.getForumPath(f,just_path=True)
			if not path: continue
			if not os.path.isfile(os.path.join(path,f)): continue
			fdata = forumbrowser.ForumData(f,path)
			name = fdata.name
			desc = fdata.description
			logo = fdata.urls.get('logo','')
			exists, logopath = util.getCachedLogo(logo,f)
			if exists: logo = logopath
			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			desc = '[B]%s[/B]: [COLOR FFFF9999]%s[/COLOR]' % ( T(32290) , (desc or 'None') )
			interface = ''
			if f.startswith('TT.'):
				interface = 'TT'
			elif f.startswith('FR.'):
				interface = 'FR'
			elif f.startswith('PB.'):
				interface = 'PB'
			elif f.startswith('YK.'):
				interface = 'YK'
			elif f.startswith('GB.'):
				interface = 'GBalt'
			menu.addItem(f, name,logo,desc,bgcolor=hc,interface=interface,description_window='show')

	forum = menu.getResult('script-forumbrowser-forum-select.xml',select=forumID)
	return forum

def setLogins(force_ask=False,forumID=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID or force_ask: forumID = askForum(forumID=forumID)
	if not forumID: return
	data = util.loadForumSettings(forumID)
	user = ''
	if data: user = data.get('username','')
	user = dialogs.doKeyboard(T(32201),user)
	if user is None: return
	password = ''
	if data: password = data.get('password','')
	password = dialogs.doKeyboard(T(32202),password,True)
	if password is None: return
	if not user and not password:
		dialogs.showMessage(T(32387),T(32388))
	else:
		util.saveForumSettings(forumID,username=user,password=password)
		dialogs.showMessage(T(32389),T(32390))

def setLoginPage(forumID=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID: return

	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	url = fdata.forumURL()
	if not url: return
	LOG('Open Forum Main Page - URL: ' + url)
	url = browseWebURL(url)
	if url == None: return
	util.saveForumSettings(forumID,rules={'login_url':url})

def browseWebURL(url):
	(url,html) = webviewer.getWebResult(url,dialog=True) #@UnusedVariable
	if not url: return None
	yes = dialogs.dialogYesNo(T(32391),str(url),'',T(32392))
	if not yes: return None
	return url

###########################################################################################
## - Version Conversion
###########################################################################################

def updateOldVersion():
	lastVersion = getSetting('last_version') or '0.0.0'
	if util.Version(__version__) <= util.Version(lastVersion): return False
	setSetting('last_version',__version__)
	LOG('NEW VERSION (OLD: %s): Converting any old formats...' % lastVersion)
	if util.Version(lastVersion) < util.Version('1.1.4'):
		convertForumSettings_1_1_4()
	if util.Version(lastVersion) < util.Version('2.1.30') and not lastVersion == '0.0.0':
		if getSetting('use_skin_mods',False):
			dialogs.showMessage(T(32393),T(32394))
			mods.installSkinMods(update=True)
			util.setRefreshXBMCSkin()
	if util.Version(lastVersion) < util.Version('2.1.71') and not lastVersion == '0.0.0':
		updateToKodi()
	if lastVersion == '0.0.0': doFirstRun()
	return True

def doFirstRun():
	LOG('EXECUTING FIRST RUN FUNCTIONS')
	xbmc_org = os.path.join(FORUMS_PATH,'TT.kodi.tv')
	if not os.path.exists(xbmc_org):
		local = os.path.join(FORUMS_STATIC_PATH,'TT.kodi.tv')
		if os.path.exists(local): open(xbmc_org,'w').write(open(local,'r').read())
	dialogs.showInfo('first')

def convertForumSettings_1_1_4():
	from lib.crypto import passmanager
	forums = os.listdir(FORUMS_PATH) + os.listdir(FORUMS_STATIC_PATH)
	for f in forums:
		username = getSetting('login_user_' + f.replace('.','_'))
		key = 'login_pass_' + f.replace('.','_')
		password = passmanager.getPassword(key, username)
		if username or password:
			LOG('CONVERTING FORUM SETTINGS: %s' % f)
			util.saveForumSettings(f,username=username,password=password)
			setSetting('login_user_' + f.replace('.','_'),'')
			setSetting('login_pass_' + f.replace('.','_'),'')

def updateToKodi():
	LOG('Converting xbmc.org to kodi.tv...')
	favs = getFavorites()
	if 'TT.xbmc.org' in favs:
		favs[favs.index('TT.xbmc.org')] = 'TT.kodi.tv'
		saveFavorites(favs)
		LOG('- Favorites updated')
	forumPath = os.path.join(FORUMS_PATH,'TT.xbmc.org')
	if os.path.exists(forumPath):
		with open(forumPath,'r') as s:
			with open(os.path.join(FORUMS_PATH,'TT.kodi.tv'),'w') as t:
				t.write(s.read().replace('xbmc.org','kodi.tv'))
		os.remove(forumPath)
		LOG('- Forums updated')
	setPath = os.path.join(FORUMS_SETTINGS_PATH,'TT.xbmc.org')
	if os.path.exists(setPath):
		password = util.getForumSetting('TT.xbmc.org','password')
		os.rename(setPath,os.path.join(FORUMS_SETTINGS_PATH,'TT.kodi.tv'))
		util.saveForumSettings('TT.kodi.tv',password=password)
		LOG('- Settings updated')

## - Version Conversion End ###############################################################

def toggleNotify(forumID=None):
	notify = True
	if not forumID and FB: forumID = FB.getForumID()
	if not forumID: return None
	data = util.loadForumSettings(forumID)
	if data: notify = not data['notify']
	util.saveForumSettings(forumID,notify=notify)
	return notify

def doSettings(window=None):
	w = dialogs.openWindow(xbmcgui.WindowXMLDialog,'script-forumbrowser-overlay.xml',return_window=True,modal=False,theme='Default')
	try:
		util.__addon__.openSettings()
	finally:
		w.close()
		del w
	global DEBUG
	DEBUG = getSetting('debug',False)
	util.DEBUG = DEBUG
	signals.DEBUG = DEBUG
	tapatalk.DEBUG = DEBUG
	StreamExtractor.DEBUG = DEBUG
	if FB:
		FB.MC.resetRegex()
		FB.MC.setReplaces()
	forumbrowser.ForumPost.hideSignature = getSetting('hide_signatures',False)
	dialogs.setGlobalSkinProperty('ForumBrowser_hidePNP',util.getSetting('hide_pnp',False) and '1' or '0')
	if util.getSetting('hide_pnp',False):
		dialogs.setGlobalSkinProperty('ForumBrowser_slideUpOnVideo','0')
	else:
		dialogs.setGlobalSkinProperty('ForumBrowser_slideUpOnVideo',util.getSetting('slide_up_on_video',False) and '1' or '0')
	if mods.checkForSkinMods():
		util.setRefreshXBMCSkin()
		return True
	return False

def forumsManager(window=None,size='full',forumID=None):
	if size == 'small':
		xmlFile = 'script-forumbrowser-notifications-small.xml'
	elif size == 'manage':
		xmlFile = 'script-forumbrowser-manage-forums.xml'
	else:
		xmlFile = 'script-forumbrowser-notifications.xml'

	if FB and window and forumID: canLogin = FB.canLogin()

	dialogs.openWindow(NotificationsDialog,xmlFile,theme='Default',forumsWindow=window,forumID=forumID)

	if FB and window and forumID:
		if forumID == FB.getForumID() and not canLogin:
			window.resetForum()
			if FB.canLogin():
				window.fillForumList()

def manageParserRules(forumID=None,rules=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	horLine = '-'
	if FB: horLine = FB.MC.hrReplace
	if not forumID: return
	changed = False
	returnIfChanged = False
	if rules != None:
		returnIfChanged = True
	else:
		rules = util.loadForumSettings(forumID,get_rules=True)
	rhelp = dialogs.loadHelp('postrules.help')
	choice = True
	while choice:
		menu = dialogs.OptionsChoiceMenu(T(32395))
		keys = rules.keys()
		keys.sort()
		for k in keys:
			v = rules[k]
			if k.startswith('extra.'):
				if v: menu.addItem(k,'[%s] ' % T(32396) + k.split('.')[-1],display2=v + '[CR]%s[CR]%s' % (horLine,rhelp['extra']))
			elif k == 'login_url':
				if v: menu.addItem(k,T(32398),display2=texttransform.textwrap.fill(v,30))
			else:
				if v:
					for i in v.split(';&;'):
						if i:
							if k == 'split':
								disp = i.replace(';&&;',' [COLOR FFFF9999]|[/COLOR] ')
								s,e = i.split(';&&;',1)
								disp2 = '[COLOR FF808080]S:[/COLOR] %s[CR][COLOR FF808080]E:[/COLOR] %s' % (s,e) + '[CR]%s[CR]%s' % (horLine,rhelp[k])
							else:
								disp = i
								disp2 = disp + '[CR]%s[CR]%s' % (horLine,rhelp[k])
							menu.addItem(k + '.' + i,'[%s %s] ' % (k.upper(),T(32397)) + disp,'',disp2)
		menu.addSep()
		menu.addItem('add','[COLOR FFFFFF00]+ %s[/COLOR]' % T(32399))
		menu.addItem('share','[COLOR FF00FFFF]%s->[/COLOR]' % T(32400),display2='Share rules to the Forum Browser online database')
		menu.addItem('save',returnIfChanged and '[COLOR FF00FF00]%s[/COLOR]' % T(32052) or '[COLOR FF00FF00]<- %s[/COLOR]' % T(32401))
		choice = menu.getResult()

		if not choice:
			if returnIfChanged: return changed
			return

		if choice == 'save':
			for k in rules.keys():
				if not rules[k]: rules[k] = None
			if returnIfChanged: return changed
			util.saveForumSettings(forumID,rules=rules)
			continue
		elif choice == 'share':
			shareForumRules(forumID,rules)
			continue
		elif choice == 'add':
			menu = dialogs.OptionsChoiceMenu(T(32402))
			menu.addItem('extra',T(32317),'',rhelp['extra'])
			menu.addItem('head',T(32403),'',rhelp['head'])
			menu.addItem('tail',T(32404),'',rhelp['tail'])
			menu.addItem('class',T(32549),'',rhelp['class'])
			menu.addItem('split',T(32550),'',rhelp['split'])
			rtype = menu.getResult()
			if not rtype: continue
			if rtype == 'extra':
				name = dialogs.doKeyboard(T(32405))
				if not name: continue
				default = ''
				if 'extra.' + name in rules: default = rules['extra.' + name]
				val = dialogs.doKeyboard(T(32406),default)
				if not val: continue
				rules['extra.' + name] = val
				changed = True
			else:
				if rtype == 'split':
					val1 = dialogs.doKeyboard(T(32551))
					if val1 == None: continue
					val1 = val1 or ''
					val2 = dialogs.doKeyboard(T(32552))
					val2 = val2 or ''
					if not val1 and not val2: continue
					val = val1 + ';&&;' + val2
				else:
					val = dialogs.doKeyboard(T(32407))
					if not val: continue

				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if not val in vallist:
					vallist.append(val)
					rules[rtype] = ';&;'.join(vallist)
					changed = True
			continue
		menu = dialogs.ChoiceMenu(T(32408))
		if not choice == 'login_url': menu.addItem('edit',T(32232))
		menu.addItem('remove',T(32409))
		choice2 = menu.getResult()
		if not choice2: continue
		if choice2 == 'remove':
			if choice.startswith('extra.') or choice == 'login_url':
				rules[choice] = None
				changed = True
			else:
				rtype, val = choice.split('.')
				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if val in vallist:
					vallist.pop(vallist.index(val))
					rules[rtype] = ';&;'.join(vallist)
					changed = True
		else:
			if choice.startswith('extra.') or choice == 'login_url':
				val = rules[choice]
#				if choice == 'login_url':
#					edit = dialogs.doKeyboard('Edit',val)
#				else:
				edit = dialogs.doKeyboard(T(32232),val)
				if edit == None: continue
				rules[choice] = edit
				changed = True
			else:
				rtype, val = choice.split('.')
				if rtype == 'split':
					val1,val2 = val.split(';&&;',1)
					val1 = dialogs.doKeyboard(T(32551),val1)
					if val1 == None: continue
					val1 = val1 or ''
					val2 = dialogs.doKeyboard(T(32552),val2)
					if val2 == None: continue
					val2 = val2 or ''
					edit = val1 + ';&&;' + val2
				else:
					edit = dialogs.doKeyboard(T(32232),val)
				if edit == None: continue
				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if val in vallist:
					vallist.pop(vallist.index(val))
					vallist.append(edit)
					rules[rtype] = ';&;'.join(vallist)
					changed = True

def shareForumRules(forumID,rules):
	odb = forumbrowser.FBOnlineDatabase()
	odbrules = odb.getForumRules(forumID)
	if odbrules:
		out = []
		for k,v in odbrules.items():
			if k.startswith('extra.'):
				out.append('[%s] ' % T(32396) + k.split('.',1)[-1] + ' = ' + v)
			elif k == 'head':
				out.append('[%s] = ' % T(32410) + ', '.join(v.split(';&;')))
			elif k == 'tail':
				out.append('[%s] = ' % T(32411) + ', '.join(v.split(';&;')))
		dialogs.showMessage(T(32412),'%s\n\n%s' % (T(32413),'[CR]'.join(out)),scroll=True)
		yes = dialogs.dialogYesNo(T(32414),T(32415))
		if not yes: return
	setRulesODB(forumID, rules)

def registerForum():
	url = FB.getRegURL()
	LOG('Registering - URL: ' + url)
	webviewer.getWebResult(url,dialog=True)

def addFavorite(forum=None):
	if not forum:
		if not FB: return
		forum = FB.getForumID()
	favs = getFavorites()
	if forum in favs: return
	favs.append(forum)
	setSetting('favorites','*:*'.join(favs))
	dialogs.showMessage(T(32416),T(32418))

def removeFavorite(forum=None):
	if not forum: forum = askForum(just_favs=True)
	if not forum: return
	favs = getFavorites()
	if not forum in favs: return
	favs.pop(favs.index(forum))
	setSetting('favorites','*:*'.join(favs))
	dialogs.showMessage(T(32417),T(32419))

def getFavorites():
	favs = getSetting('favorites')
	if favs:
		favs = favs.split('*:*')
	else:
		favs = []
	return favs

def saveFavorites(favs):
	setSetting('favorites','*:*'.join(favs))

def selectForumCategory(with_all=False):
	d = dialogs.ChoiceMenu(T(32420))
	if with_all:
		d.addItem('search',T(32421))
		d.addItem('all',T(32422))
	for x in range(0,17):
		d.addItem(str(x), unicode(T(32500 + x)))
	return d.getResult()

def addForumManual(current=False):
	user = None
	password=None
	with dialogs.xbmcDialogProgress(T(32423),T(32424)) as dialog:
		if current:
			if not FB: return
			ftype = FB.prefix[:2]
			forum = FB.forum
			url = orig = FB._url
			url = tapatalk.testForum(url)
			if url: pageURL = url.split('/mobiquo/',1)[0]
			if not url:
				from lib.forumbrowser import forumrunner
				url = forumrunner.testForum(orig)
			if url: pageURL = url.split('/forumrunner/',1)[0]
			if not url:
				dialogs.showMessage(T(32257),T(32425),success=False)
				return
		else:
			forum = dialogs.doKeyboard(T(32426))
			if forum == None: return
			forum = forum.lower()
			if not dialog.update(10,'%s: Tapatalk' % T(32427)): return
			url = tapatalk.testForum(forum)
			ftype = ''
			label = ''
			if url:
				if 'proboards.com' in url or 'index.cgi?action=tapatalk' in url:
					ftype = 'PB'
					label = 'ProBoards'
					pageURL = url.split('/',1)[0]
				elif 'yuku.com' in url:
					ftype = 'YK'
					label = 'Yuku'
					pageURL = url.split('/',1)[0]
				else:
					ftype = 'TT'
					label = 'Tapatalk'
					pageURL = url.split('/mobiquo/',1)[0]
			else:
				if not dialog.update(13,'%s: Forumrunner' % T(32427)): return
				from lib.forumbrowser import forumrunner #@Reimport
				url = forumrunner.testForum(forum)
				if url:
					ftype = 'FR'
					label = 'Forumrunner'
					pageURL = url.split('/forumrunner/',1)[0]

			if not url:
				if not dialog.update(16,'%s: Parser Browser' % T(32427)): return
				yes = dialogs.dialogYesNo(T(32428),T(32429),'',T(32430))
				if yes:
					user = dialogs.doKeyboard(T(32201))
					if user: password = dialogs.doKeyboard(T(32202),hidden=True)
				from lib.forumbrowser import genericparserbrowser
				url,parser = genericparserbrowser.testForum(forum,user,password,progress_callback=dialog.update)
				if url:
					ftype = 'GB'
					label = 'Parser Browser (%s)' % parser.getForumTypeName()
					if url.startswith('http'):
						pre,post = url.split('://',1)
					else:
						pre = 'http'
						post = url
					post = post.split('/',1)[0]
					pageURL = pre + '://' + post

			if not url:
				dialogs.showMessage(T(32257),T(32431),success=False)
				return

			dialogs.showMessage(T(32432),T(32433).format(forum),'[CR]%s: %s' % (T(32402),label),'[CR]'+ url,success=True)
			if ftype == 'GB':
				if parser.getForumTypeName().lower() == 'generic':
					dialogs.showInfo('parserbrowser-generic')
				else:
					dialogs.showInfo('parserbrowser-normal')
			forum = url.split('http://',1)[-1].split('/',1)[0]

		if not dialog.update(20,T(32434)): return
		dialog.setRange(20,30)
		info = forumbrowser.HTMLPageInfo(pageURL,progress_callback=dialog.update)
		dialog.setRange()
		tmp_desc = info.description(info.title(''))
		tmp_desc = texttransform.convertHTMLCodes(tmp_desc,FB).strip()
		images = info.images()
		if not dialog.update(30,T(32435)): return
		desc = dialogs.doKeyboard(T(32435),default=tmp_desc,mod=True)
		if desc is None: return
		if not desc: desc = tmp_desc
		if not dialog.update(40,T(32436)): return
		logo = chooseLogo(forum,images)
		LOG('Adding Forum: %s at URL: %s' % (forum,url))
		name = forumbrowser.nameFromURL(forum)
		forumID = ftype + '.' + name
		saveForum(ftype,forumID,name,desc,url,logo)
		if user and password: util.saveForumSettings(forumID,username=user,password=password)
		dialog.update(60,T(32437))
		if not (not current and ftype == 'GB'): addForumToOnlineDatabase(name,url,desc,logo,ftype,dialog=dialog)
		return forumID

def saveForum(ftype,forumID,name,desc,url,logo,header_color="FFFFFF"): #TODO: Do these all the same. What... was I crazy?
	if ftype == 'TT' or ftype == 'PB' or ftype == 'YK':
		codecs.open(os.path.join(FORUMS_PATH,forumID),'w','utf-8').write('#%s\n#%s\nurl:tapatalk_server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))
	elif ftype == 'FR':
		codecs.open(os.path.join(FORUMS_PATH,forumID),'w','utf-8').write('#%s\n#%s\nurl:forumrunner_server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))
	else:
		codecs.open(os.path.join(FORUMS_PATH,forumID),'w','utf-8').write('#%s\n#%s\nurl:server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))

def addForum(current=False):
	stay_open_on_select=True
	source = True
	last = None
	while source:
		d = dialogs.OptionsChoiceMenu('Choose Database')
		hlp = dialogs.loadHelp('forumdatabases.help')
		d.addItem('fb', 'Forum Browser {0}'.format(T(32558)), '../../../media/forum-browser-logo-128.png',hlp.get('fb',''))
		d.addItem('tt', 'Tapatalk {0}'.format(T(32558)), '../../../media/forum-browser-tapatalk.png',hlp.get('tt',''))
		d.addItem('fr', 'Forumrunner {0}'.format(T(32558)), '../../../media/forum-browser-forumrunner.png',hlp.get('fr',''))
		d.addItem('pb', 'ProBoards {0}'.format(T(32558)), '../../../media/forum-browser-proboards.png',hlp.get('pb',''))
		d.addItem('yk', 'Yuku {0}'.format(T(32558)), '../../../media/forum-browser-yuku.png',hlp.get('yk',''))
		d.addItem('yt', 'YouTube Channels', '../../../media/forum-browser-youtube.png',hlp.get('yt',''))
		d.addItem('manual', T(32559), '../../../media/forum-browser-plus.png',hlp.get('manual',''))

		source = d.getResult(select=last)
		if not source: return None
		last = source
		if source =='fb':
			added = addForumFromOnlineFB(stay_open_on_select=stay_open_on_select)
		elif source == 'manual':
			added = addForumManual(current=current)
		else:
			added = addForumFromTapatalkDB(stay_open_on_select=stay_open_on_select,source=source)
		if added: return added

def addItemToMenuFB(menu,f,existing,update=False):
	interface = f.get('type')
	rf=ra=''
	if interface == 'GB':
		rf = {'1':'FFFF0000','2':'FFFFFF00','3':'FF00FF00'}.get(f.get('rating_function'),'')
		ra = {'1':'FFFF0000','2':'FFFFFF00','3':'FF00FF00'}.get(f.get('rating_accuracy'),'')
	desc = f.get('desc','None') or 'None'
	desc = '[B]{0}[/B]: [COLOR FFFF9999]{1}[/COLOR][CR][CR][B]{2}[/B]: [COLOR FFFF9999]{3}[/COLOR]'.format(T(32441),str(T(32500 + f.get('cat',0))),T(32290),desc)
	#desc = util.makeUnicode(desc,'windows-1251')
	bgcolor = formatHexColorToARGB(f.get('header_color','FFFFFF'))
	disabled = f.get('name') in existing and 'ALREADY ADDED' or False
	menu.addItem(f, f.get('name'), f.get('logo'), desc,disabled=disabled,bgcolor=bgcolor,interface=interface,function=rf,accuracy=ra,update=update,description_window='show')

def addForumFromOnlineFB(stay_open_on_select=False):
	odb = forumbrowser.FBOnlineDatabase()
	res = True
	added = None
	while res:
		res = selectForumCategory(with_all=True)
		if not res: return added
		cat = res
		terms = None
		if cat == 'all': cat = None
		if cat == 'search':
			terms = dialogs.doKeyboard(T(32330))
			if not terms: continue
			cat = None
		splash = dialogs.showActivitySplash(T(32438))
		try:
			flist = odb.getForumList(cat,terms)
		finally:
			splash.close()
		if not flist:
			dialogs.showMessage(T(32439),T(32440))
			continue
		if cat and cat.isdigit():
			caption = '[COLOR FF9999FF]'+str(T(32500 + int(cat)))+'[/COLOR]'
		else:
			caption = '[COLOR FF9999FF]All[/COLOR]'
		menu = dialogs.ImageChoiceMenu(caption)
		existing = forumbrowser.getForumNameList()
		for f in flist:
			addItemToMenuFB(menu,f,existing)
		f = True
		select = None
		while f:
			f = menu.getResult('script-forumbrowser-forum-select.xml',filtering=True,select=select)
			if f:
				forumID = doAddForumFromOnline(f,odb)
				added = forumID
				if not stay_open_on_select: return added
				existing = forumbrowser.getForumNameList()
				addItemToMenuFB(menu,f,existing,update=True)
			select = f
	return added

def addItemToMenuNonFB(menu,f,existing,update=False):
	interface = f.forumType
	rf=ra=''
	desc = f.description
	desc = u'[B]{0}[/B]: [COLOR FFFF9999]{1}[/COLOR][CR][CR][B]{2}[/B]: [COLOR FFFF9999]{3}[/COLOR]'.format(T(32441),f.category,T(32290),util.makeUnicode(desc,'utf-8'))
	bgcolor = formatHexColorToARGB('FFFFFF')
	disabled = f.name in existing and 'ALREADY ADDED' or False
	menu.addItem(f, f.displayName or f.name, f.getLogo(), desc,disabled=disabled,bgcolor=bgcolor,interface=interface,function=rf,accuracy=ra,update=update,description_window='show')

def addForumFromTapatalkDB(stay_open_on_select=False,source=None):
	if source == 'fr':
		from lib.forumbrowser import forumrunner
		db = forumrunner.ForumrunnerDatabaseInterface()
	elif source == 'pb':
		db = tapatalk.ProBoardsDatabaseInterface()
	elif source == 'yk':
		db = tapatalk.YukuDatabaseInterface()
	elif source == 'yt':
		from lib.forumbrowser import youtube
		db = youtube.YouTubeCategoryInterface()
	else:
		db = tapatalk.TapatalkDatabaseInterface()
	res = True
	added = None
	page = 1
	perPage = 20
	cat = 0
	terms = None
	lastCat = None
	select = None
	while res:
		clearDirFiles(util.TEMP_DIR)
		cats = []
		flist = []
		if cat == 'search' or terms:
			if not terms:
				page = 1
				terms = dialogs.doKeyboard(T(32330))
			if not terms:
				cat = 0
				continue
			cat = None
			splash = dialogs.showActivitySplash(T(32438))
			try:
				flist = db.search(terms,page=page,per_page=perPage,p_dialog=splash)
			finally:
				splash.close()
			if not flist:
				dialogs.showMessage(T(32439),T(32440))
				terms = dialogs.doKeyboard(T(32330))
				if not terms: return added
				continue
		else:
			splash = dialogs.showActivitySplash(T(32438))
			try:
				cats = db.categories(cat_id=cat,page=page,per_page=perPage,p_dialog=splash)
			finally:
				splash.close()
			flist = cats.get('forums',[])
			cats = cats.get('cats',[])

		menu = dialogs.ImageChoiceMenu('Results')
		if page > 1:
			menu.addItem('prev_page', '[<- {0}]'.format(T(32529).upper()),os.path.join(util.GENERIC_MEDIA_PATH,'prev_icon.png'),bgcolor='00000000')
		elif not cat == 'search' and not terms and cat == 0:
			menu.addItem('search',T(32421),os.path.join(util.GENERIC_MEDIA_PATH,'search_icon.png'),bgcolor='FF333333')
		else:
			menu.addItem(u'back','[{0}]'.format(T(32556).upper()),os.path.join(util.GENERIC_MEDIA_PATH,'prev_icon.png'),bgcolor='00000000')
		for c in cats:
			menu.addItem('cat-' + c.get('id'),'[+] ' + c.get('name',''), c.get('icon',''),bgcolor=c.get('bgcolor','FF000000'))
		existing = forumbrowser.getForumNameList()
		for f in flist:
			addItemToMenuNonFB(menu,f,existing)
		if len(flist) >= perPage:
			menu.addItem('next_page', '[{0} ->]'.format(T(32530).upper()),os.path.join(util.GENERIC_MEDIA_PATH,'next_icon.png'),bgcolor='00000000')
		f = True
		while f:
			f = menu.getResult('script-forumbrowser-forum-select.xml',filtering=True,select=select,selectFirstOnBack=cat!=0 and True or False)
			if not f: return added
			select = f
			if f == 'search':
				lastCat = 0
				cat = 'search'
				page = 1
				terms = None
				break
			elif f == 'back':
				cat = lastCat
				terms = None
				break
			elif not isinstance(f,forumbrowser.ForumEntry) and f.startswith('cat-'):
				lastCat = cat
				cat = f[4:]
				page = 1
				terms = None
				break
			elif f == 'prev_page':
				page -= 1
				if page < 1: page = 1
				break
			elif f == 'next_page':
				select = None
				page += 1
				break
			else:
				forumID = doAddForumFromTTorFR_DB(f)
				added = forumID
				if not stay_open_on_select: return added
				existing = forumbrowser.getForumNameList()
				addItemToMenuNonFB(menu,f,existing,update=True)

	return added

def formatHexColorToARGB(hexcolor):
	try:
		binascii.unhexlify(hexcolor)
		return 'FF' + hexcolor
	except:
		return "FFFFFFFF"

def doAddForumFromOnline(f,odb):
	if not isinstance(f,dict): return
	forumID = f['type']+'.'+f['name']
	saveForum(f['type'],forumID,f['name'],f.get('desc',''),f['url'],f.get('logo',''),f.get('header_color',''))
	rules = isinstance(f,dict) and odb.getForumRules(f['type']+'.'+f['name']) or {}
	old_rules = util.loadForumSettings(forumID,get_rules=True)
	if rules and not old_rules: util.saveForumSettings(forumID,rules=rules)
	dialogs.showMessage(T(32416),'{0}: {1}'.format(T(32442),f['name']))
	return forumID

def doAddForumFromTTorFR_DB(f):
	if not f: return
	forumID = f.forumID
	if os.path.exists(f.getLogo()):
		import shutil
		shutil.copyfile(f.getLogo(), os.path.join(util.CACHE_PATH,os.path.basename(f.getLogo())))
	saveForum(f.forumType,forumID,f.displayName or f.name,f.description,f.url,f.getLogo(),'FFFFFF')
	odb = forumbrowser.FBOnlineDatabase()
	rules = isinstance(f,dict) and odb.getForumRules(forumID) or {}
	old_rules = util.loadForumSettings(forumID,get_rules=True)
	if rules and not old_rules: util.saveForumSettings(forumID,rules=rules)
	dialogs.showMessage(T(32416),'{0}: {1}'.format(T(32442),f.name))
	return forumID

def setRulesODB(forumID,rules):
	odb = forumbrowser.FBOnlineDatabase()
	out = []
	for k,v in rules.items():
		if k and v:
			out.append(k + '=' + v)
	result = str(odb.setRules(forumID,'\n'.join(out)))
	LOG('Updating ODB Rules: ' + result)
	if result == '1':
		dialogs.showMessage(T(32052),T(32443),success=True)
	else:
		dialogs.showMessage(T(32257),T(32444),error=True)

def addCurrentForumToOnlineDatabase(forumID=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID: return
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	url = fdata.urls.get('tapatalk_server',fdata.urls.get('forumrunner_server',fdata.urls.get('server',FB and FB._url or '')))
	if not url: raise Exception('No URL')
	addForumToOnlineDatabase(fdata.name,url,fdata.description,fdata.urls.get('logo'),forumID[:2],header_color=fdata.theme.get('header_color','FFFFFF'))

def addForumToOnlineDatabase(name,url,desc,logo,ftype,header_color='FFFFFF',dialog=None):
	if not dialogs.dialogYesNo(T(32445),T(32446)): return
	LOG('Adding Forum To Online Database: %s at URL: %s' % (name,url))
	frating = arating = '0'
	if ftype == 'GB':
		frating,arating = askForumRating()
		if not frating:
			dialogs.showMessage(T(32257),T(32447),success=False)
			return

	cat = selectForumCategory() or '0'
	splash = None
	if dialog:
		dialog.update(80,T(32448))
	else:
		splash = dialogs.showActivitySplash(T(32448))

	try:
		odb = forumbrowser.FBOnlineDatabase()
	finally:
		if splash: splash.close()

	msg = odb.addForum(name, url, logo, desc, ftype, cat, rating_function=frating, rating_accuracy=arating, header_color=header_color)
	if msg == 'OK':
		dialogs.showMessage(T(32416),T(32451),success=True)
	elif msg =='EXISTS':
		dialogs.showMessage(T(32449),T(32452),success=True)
	else:
		dialogs.showMessage(T(32450),T(32453) + ':',str(msg),success=False)
		LOG('Forum Not Added: ' + str(msg))

def askForumRating():
	d = dialogs.ChoiceMenu(T(32454))
	d.addItem('3',T(32455))
	d.addItem('2',T(32456))
	d.addItem('1',T(32457))
	frating = d.getResult()
	if not frating: return None,None
	d = dialogs.ChoiceMenu(T(32458))
	d.addItem('3',T(32459))
	d.addItem('2',T(32460))
	d.addItem('1',T(32461))
	arating = d.getResult()
	if not arating: return None,None
	return frating,arating

def chooseLogo(forum,image_urls,keep_colors=False,splash=None):
	#if not image_urls: return
	base = '.'.join(forum.split('.')[-2:])
	top = []
	middle = []
	bottom = []
	for u in image_urls:
		if 'logo' in u.lower() and base in u:
			top.append(u)
		elif base in u:
			middle.append(u)
		else:
			bottom.append(u)
	image_urls = ['http://%s/favicon.ico' % forum] + top + middle + bottom
	menu = dialogs.ImageChoiceMenu(T(32436))
	for url in image_urls: menu.addItem(url, url, url)
	if splash: splash.close()
	url = menu.getResult(keep_colors=keep_colors)
	return url or ''

def getCurrentLogo(forumID=None,logo=None):
	if not logo:
		if FB: logo = FB.urls.get('logo')
	if not logo: return
	if not forumID: forumID = FB.getForumID()
	if not forumID: return
	root, ext = os.path.splitext(logo) #@UnusedVariable
	ext = re.split('[^\w\.]',ext,1)[0]
	logopath = os.path.join(CACHE_PATH,forumID + (ext or '.jpg'))
	if os.path.exists(logopath): return logopath
	logopath = os.path.join(CACHE_PATH,forumID + '.png')
	if os.path.exists(logopath): return logopath
	logopath = os.path.join(CACHE_PATH,forumID + '.gif')
	if os.path.exists(logopath): return logopath
	logopath = os.path.join(CACHE_PATH,forumID + '.ico')
	if os.path.exists(logopath): return logopath
	return logo

def askColor(forumID=None,color=None,logo=None):
	#fffaec
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID: return
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	color = color or fdata.theme.get('header_color')
	logo = logo or getCurrentLogo(forumID,fdata.urls.get('logo'))
	try:
		hexc = dialogs.showSelectionColorDialog('FF' + color, logo, 'FF', 1)
		if not hexc: return
		hexc = hexc[2:]
	except:
		w = dialogs.openWindow(dialogs.ColorDialog,'script-forumbrowser-color-dialog.xml',return_window=True,image=logo,hexcolor=color,theme='Default')
		hexc = w.hexValue()
		del w
	if not hexc: return
	return hexc

def setForumColor(color,forumID=None):
	if not color: return False
	if forumID:
		fid = forumID
	else:
		fid = FB.getForumID()
	fdata = forumbrowser.ForumData(fid,FORUMS_PATH)
	fdata.theme['header_color'] = color
	if FB and FB.getForumID() == forumID: FB.theme['header_color'] = color
	fdata.writeData()
	dialogs.showMessage(T(32052),T(32462))
	return True

def updateThemeODB(forumID=None):
	if not forumID:
		forumID = FB.getForumID()
	odb = forumbrowser.FBOnlineDatabase()
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	splash = dialogs.showActivitySplash(T(32448))
	try:
		result = str(odb.setTheme(forumID[3:],fdata.theme))
	finally:
		splash.close()
	LOG('Updating ODB Theme: ' + result)
	if result == '1':
		dialogs.showMessage(T(32052),T(32463))
	else:
		dialogs.showMessage(T(32257),T(32464))

def removeForum(forum=None):
	if forum: return doRemoveForum(forum)
	forum = True
	while forum:
		forum = askForum(caption=T(32465),hide_extra=True)
		if not forum: return
		doRemoveForum(forum)

def doRemoveForum(forum):
	yes = dialogs.dialogYesNo(T(32466),T(32467),'',forum[3:])
	if not yes: return False
	path = os.path.join(FORUMS_PATH,forum)
	if not os.path.exists(path): return
	os.remove(path)
	dialogs.showMessage(T(32417),T(32468))
	return True

def clearDirFiles(filepath):
	if not os.path.exists(filepath): return
	for f in os.listdir(filepath):
		f = os.path.join(filepath,f)
		if os.path.isfile(f): os.remove(f)

def getFile(url,target=None):
	if not target: return #do something else eventually if we need to
	req = urllib2.urlopen(url)
	open(target,'w').write(req.read())
	req.close()

def getLanguage():
		langs = ['Afrikaans', 'Albanian', 'Amharic', 'Arabic', 'Armenian', 'Azerbaijani', 'Basque', 'Belarusian', 'Bengali', 'Bihari', 'Breton', 'Bulgarian', 'Burmese', 'Catalan', 'Cherokee', 'Chinese', 'Chinese_Simplified', 'Chinese_Traditional', 'Corsican', 'Croatian', 'Czech', 'Danish', 'Dhivehi', 'Dutch', 'English', 'Esperanto', 'Estonian', 'Faroese', 'Filipino', 'Finnish', 'French', 'Frisian', 'Galician', 'Georgian', 'German', 'Greek', 'Gujarati', 'Haitian_Creole', 'Hebrew', 'Hindi', 'Hungarian', 'Icelandic', 'Indonesian', 'Inuktitut', 'Irish', 'Italian', 'Japanese', 'Javanese', 'Kannada', 'Kazakh', 'Khmer', 'Korean', 'Kurdish', 'Kyrgyz', 'Lao', 'Latin', 'Latvian', 'Lithuanian', 'Luxembourgish', 'Macedonian', 'Malay', 'Malayalam', 'Maltese', 'Maori', 'Marathi', 'Mongolian', 'Nepali', 'Norwegian', 'Occitan', 'Oriya', 'Pashto', 'Persian', 'Polish', 'Portuguese', 'Portuguese_Portugal', 'Punjabi', 'Quechua', 'Romanian', 'Russian', 'Sanskrit', 'Scots_Gaelic', 'Serbian', 'Sindhi', 'Sinhalese', 'Slovak', 'Slovenian', 'Spanish', 'Sundanese', 'Swahili', 'Swedish', 'Syriac', 'Tajik', 'Tamil', 'Tatar', 'Telugu', 'Thai', 'Tibetan', 'Tonga', 'Turkish', 'Uighur', 'Ukrainian', 'Urdu', 'Uzbek', 'Vietnamese', 'Welsh', 'Yiddish', 'Yoruba', 'Unknown']
		try:
			idx = int(getSetting('language'))
		except:
			return ''
		return langs[idx]

class ThreadDownloader:
	def __init__(self):
		self.thread = None

	def startDownload(self,targetdir,urllist,ext='',callback=None):
		old_thread = None
		if self.thread and self.thread.isAlive():
			self.thread.stop()
			old_thread = self.thread
		self.thread = DownloadThread(targetdir,urllist,ext,callback,old_thread)

	def stop(self):
		self.thread.stop()

class DownloadThread(util.StoppableThread):
	def __init__(self,targetdir,urllist,ext='',callback=None,old_thread=None,nothread=False):
		util.StoppableThread.__init__(self,name='Downloader')
		if not os.path.exists(targetdir): os.makedirs(targetdir)
		self.callback = callback
		self.targetdir = targetdir
		self.urllist = urllist
		self.ext = ext
		self.old_thread = old_thread
		if nothread:
			self.run()
		else:
			self.start()

	def run(self):
		#Wait until old downloader is stopped
		if self.old_thread: self.old_thread.join()
		clearDirFiles(self.targetdir)
		file_list = {}
		total = len(self.urllist)
		fnbase = 'file_' + str(int(time.time())) + '%s' + self.ext
		try:
			for url,i in zip(self.urllist,range(0,total)):
				fname = os.path.join(self.targetdir,fnbase % i)
				file_list[url] = fname
				if self.stopped(): return None
				self.getUrlFile(url,fname)
			if self.stopped(): return None
		except:
			ERROR('THREADED DOWNLOAD URLS ERROR')
			return None
		self.callback(file_list)

	def getUrlFile(self,url,target):
		urlObj = urllib2.urlopen(url)
		outfile = open(target, 'wb')
		outfile.write(urlObj.read())
		outfile.close()
		urlObj.close()
		return target


class Downloader:
	def __init__(self,header=T(32205),message=''):
		self.message = message
		self.prog = xbmcgui.DialogProgress()
		self.prog.create(header,message)
		self.current = 0
		self.display = ''
		self.file_pct = 0

	def progCallback(self,read,total):
		if self.prog.iscanceled(): return False
		pct = int(((float(read)/total) * (self.file_pct)) + (self.file_pct * self.current))
		self.prog.update(pct)
		return True

	def downloadURLs(self,targetdir,urllist,ext=''):
		file_list = []
		self.total = len(urllist)
		self.file_pct = (100.0/self.total)
		try:
			for url,i in zip(urllist,range(0,self.total)):
				self.current = i
				if self.prog.iscanceled(): break
				self.display = T(32469).format(i+1,self.total)
				self.prog.update(int((i/float(self.total))*100),self.message,self.display)
				fname = os.path.join(targetdir,str(i) + ext)
				fname, ftype = self.getUrlFile(url,fname,callback=self.progCallback) #@UnusedVariable
				file_list.append(fname)
		except:
			ERROR('DOWNLOAD URLS ERROR')
			self.prog.close()
			return None
		self.prog.close()
		return file_list

	def downloadURL(self,targetdir,url,fname=None):
		if not fname:
			fname = os.path.basename(urlparse.urlsplit(url)[2])
			if not fname: fname = 'file'
		f,e = os.path.splitext(fname)
		fn = f
		ct=0
		while ct < 1000:
			ct += 1
			path = os.path.join(targetdir,fn + e)
			if not os.path.exists(path): break
			fn = f + str(ct)
		else:
			raise Exception

		try:
			self.current = 0
			self.display = T(32206).format(os.path.basename(path))
			self.prog.update(0,self.message,self.display)
			t,ftype = self.getUrlFile(url,path,callback=self.progCallback) #@UnusedVariable
		except:
			ERROR('DOWNLOAD URL ERROR')
			self.prog.close()
			return (None,'')
		self.prog.close()
		return (os.path.basename(path),ftype)



	def fakeCallback(self,read,total): return True

	def getUrlFile(self,url,target=None,callback=None):
		if not target: return #do something else eventually if we need to
		if not callback: callback = self.fakeCallback
		opener = urllib2.build_opener()
		opener.addheaders = [('User-agent', 'Mozilla/5.0')]
		urlObj = opener.open(url)
		size = int(urlObj.info().get("content-length",-1))
		ftype = urlObj.info().get("content-type",'')
		ext = None
		if '/' in ftype: ext = '.' + ftype.split('/')[-1].replace('jpeg','jpg')
		if ext:
			fname, x = os.path.splitext(target) #@UnusedVariable
			target = fname + ext
		#print urlObj.info()
		#Content-Disposition: attachment; filename=FILENAME
		outfile = open(target, 'wb')
		read = 0
		bs = 1024 * 8
		while 1:
			block = urlObj.read(bs)
			if block == "": break
			read += len(block)
			outfile.write(block)
			if not callback(read, size): raise Exception('Download Canceled')
		outfile.close()
		urlObj.close()
		return (target,ftype)

def getForumList():
	ft2 = os.listdir(FORUMS_PATH)
	flist = []
	for f in ft2:
		if not f.startswith('.') and not f == 'general':
			if not f in flist: flist.append(f)
	return flist

def checkForInterface(url):
	url = url.split('/forumrunner')[0].split('/mobiquo')[0]
	LOG('Checking for forum type at URL: ' + url)
	try:
		html = urllib2.urlopen(url).read()
		if 'tapatalkdetect.js' in html:
			return 'TT'
		elif '/detect.js' in html:
			return 'FR'
		return None
	except:
		return None

def getForumBrowser(forum=None,url=None,donecallback=None,silent=False,no_default=False,log_function=None):
	showError = dialogs.showMessage
	if silent: showError = dialogs.showMessageSilent
	global STARTFORUM
	forumElements = None
	if not forum and STARTFORUM:
			forumElements = util.parseForumBrowserURL(STARTFORUM)
			forum = forumElements.get('forumID')
			STARTFORUM = None

	if not forum:
		if no_default: return False
		forum = getSetting('last_forum') or 'TT.kodi.tv'
	#global FB
	#if forum.startswith('GB.') and not url:
	#	url = getSetting('exp_general_forums_last_url')
	#	if not url: forum = 'TT.kodi.tv'

	if not util.getForumPath(forum):
		if no_default: return False
		forum = 'TT.kodi.tv'
	err = ''
	try:
		asyncconnections.setEnabled(not getSetting('disable_async_connections',False))
		if forum.startswith('GB.'):
			err = 'getForumBrowser(): General'
			from lib.forumbrowser import genericparserbrowser
			if log_function: genericparserbrowser.LOG = log_function
			FB = genericparserbrowser.GenericParserForumBrowser(forum,always_login=getSetting('always_login',False))
		elif forum.startswith('TT.') or forum.startswith('PB.') or forum.startswith('YK.'):
			err = 'getForumBrowser(): Tapatalk'
			prefix = 'TT.'
			if forum.startswith('PB.'):
				prefix = 'PB.'
			elif forum.startswith('YK.'):
				prefix = 'YK.'
			FB = tapatalk.TapatalkForumBrowser(forum,always_login=getSetting('always_login',False),prefix=prefix)
		elif forum.startswith('FR.'):
			err = 'getForumBrowser(): Forumrunner'
			from lib.forumbrowser import forumrunner
			if log_function: forumrunner.LOG = log_function
			FB = forumrunner.ForumrunnerForumBrowser(forum,always_login=getSetting('always_login',False))
		elif forum.startswith('YT.'):
			err = 'getForumBrowser(): YouTube'
			from lib.forumbrowser import youtube
			FB = youtube.YoutubeForumBrowser(forum,always_login=getSetting('always_login',False))
	except forumbrowser.ForumMovedException,e:
		showError(T(32050),T(32470),'\n' + e.message,error=True)
		return False
	except forumbrowser.ForumNotFoundException,e:
		showError(T(32050),T(32471).format(e.message),error=True)
		return False
	except forumbrowser.BrokenForumException,e:
		url = e.message
		ftype = checkForInterface(url)
		currentType = forum[:2]
		if ftype and ftype != currentType:
			LOG('Forum type changed to: ' + ftype)
			if ftype == 'TT':
				fromType = 'Forumrunner'
				toType = 'Tapatalk'
			else:
				toType = 'Forumrunner'
				fromType = 'Tapatalk'
			showError(T(32050),T(32472).format(fromType,toType),error=True)
		else:
			showError(T(32050),T(32473),error=True)
		return False
	except:
		err = ERROR(err)
		showError(T(32050),T(32171),err,error=True)
		return False
	sett = util.loadForumSettings(FB.getForumID())
	util.setSetting('last_right_align',util.getSetting('current_right_align', False))
	util.setSetting('current_right_align', sett.get('right_align') or '')
	if donecallback: donecallback(FB,forumElements)
	return FB, forumElements

def startForumBrowser(forumID=None):
	global PLAYER, SIGNALHUB, STARTFORUM
	PLAYER = util.initPlayer()
	SIGNALHUB = signals.SignalHub()
	windows.SIGNALHUB = SIGNALHUB
	updateOldVersion()
	forumbrowser.ForumPost.hideSignature = getSetting('hide_signatures',False)
	try:
		if mods.checkForSkinMods() or util.xbmcSkinAwaitingRefresh():
			LOG('Skin Mods Changed: Reloading Skin')
			util.refreshXBMCSkin()
	except:
		ERROR('Error Installing Skin Mods')

	#TD = ThreadDownloader()
	if forumID:
		STARTFORUM = forumID
	elif sys.argv[-1].startswith('forum='):
		STARTFORUM = sys.argv[-1].split('=',1)[-1]
	elif sys.argv[-1].startswith('forumbrowser://'):
		STARTFORUM = sys.argv[-1]

	windows.setWindowProperties()

	windows.startWindowManager(ForumsWindow,"script-forumbrowser-forums.xml")

	#sys.modules.clear()
	PLAYER.finish()
	del PLAYER
	del SIGNALHUB

######################################################################################
# Startup
######################################################################################
def init():
	if sys.argv[-1] == 'settings':
		doSettings()
	else:
		try:
			setSetting('FBIsRunning',True)
			setSetting('manageForums',False)
			startForumBrowser()
		except KeyboardInterrupt:
			LOG('XBMC - abort requested: Shutting down...')
		finally:
			setSetting('FBIsRunning',False)
