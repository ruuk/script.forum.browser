import urllib2, re, os, sys, time, urlparse, binascii, math, fnmatch
import xbmc, xbmcgui, xbmcaddon #@UnresolvedImport
from distutils.version import StrictVersion
import threading

try:
	from webviewer import webviewer #@UnresolvedImport
	print 'FORUM BROWSER: WEB VIEWER IMPORTED'
except:
	import traceback
	traceback.print_exc()
	print 'FORUM BROWSER: COULD NOT IMPORT WEB VIEWER'

'''
TODO:

Read/Delete PM's in xbmc4xbox.org

'''

__plugin__ = 'Forum Browser'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/forumbrowserxbmc/'
__date__ = '1-28-2013'
__addon__ = xbmcaddon.Addon(id='script.forum.browser')
__version__ = __addon__.getAddonInfo('version')
__language__ = __addon__.getLocalizedString

THEME = 'Default'
SKINS = ['Default','Dark']
if __addon__.getSetting('skin') == '1':
	THEME = 'Dark'

ACTION_MOVE_LEFT      = 1
ACTION_MOVE_RIGHT     = 2
ACTION_MOVE_UP        = 3
ACTION_MOVE_DOWN      = 4
ACTION_PAGE_UP        = 5
ACTION_PAGE_DOWN      = 6
ACTION_SELECT_ITEM    = 7
ACTION_HIGHLIGHT_ITEM = 8
ACTION_PARENT_DIR     = 9
ACTION_PARENT_DIR2	  = 92
ACTION_PREVIOUS_MENU  = 10
ACTION_SHOW_INFO      = 11
ACTION_PAUSE          = 12
ACTION_STOP           = 13
ACTION_NEXT_ITEM      = 14
ACTION_PREV_ITEM      = 15
ACTION_SHOW_GUI       = 18
ACTION_PLAYER_PLAY    = 79
ACTION_MOUSE_LEFT_CLICK = 100
ACTION_CONTEXT_MENU   = 117

#Actually it's show codec info but I'm using in a threaded callback
ACTION_RUN_IN_MAIN = 27

PLAYER = None

MEDIA_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins','Default','media'))
FORUMS_STATIC_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'forums'))
FORUMS_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'forums'))
FORUMS_SETTINGS_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'forums_settings'))
CACHE_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'cache'))
if not os.path.exists(FORUMS_PATH): os.makedirs(FORUMS_PATH)
if not os.path.exists(FORUMS_SETTINGS_PATH): os.makedirs(FORUMS_SETTINGS_PATH)
if not os.path.exists(CACHE_PATH): os.makedirs(CACHE_PATH)

STARTFORUM = None

def ERROR(message,hide_tb=False):
	LOG('ERROR: ' + message)
	short = str(sys.exc_info()[1])
	if hide_tb:
		LOG('ERROR Message: ' + short)
	else:
		import traceback #@Reimport
		traceback.print_exc()
		if getSetting('debug_show_traceback_dialog',False):
			dialogs.showText('Traceback', traceback.format_exc())
	return short
	
def LOG(message):
	print 'FORUMBROWSER: %s' % message

LOG('Version: ' + __version__)
LOG('Python Version: ' + sys.version)
DEBUG = __addon__.getSetting('debug') == 'true'
if DEBUG: LOG('DEBUG LOGGING ON')
LOG('Skin: ' + THEME)

CLIPBOARD = None
try:
	import SSClipboard #@UnresolvedImport
	CLIPBOARD = SSClipboard.Clipboard()
	LOG('Clipboard Enabled')
except:
	LOG('Clipboard Disabled: No SSClipboard')

def getSetting(key,default=None):
	setting = __addon__.getSetting(key)
	return _processSetting(setting,default)

def _processSetting(setting,default):
	if not setting: return default
	if isinstance(default,bool):
		return setting == 'true'
	elif isinstance(default,int):
		return int(float(setting or 0))
	elif isinstance(default,list):
		if setting: return setting.split(':!,!:')
		else: return default
	
	return setting

def setSetting(key,value):
	if isinstance(value,list):
		value = ':!,!:'.join(value)
	__addon__.setSetting(key,value)
	
FB = None

from forumbrowser import forumbrowser
from forumbrowser import texttransform
from crypto import passmanager
from forumbrowser import tapatalk
from webviewer import video #@UnresolvedImport
from lib import dialogs, mods

dialogs.CACHE_PATH = CACHE_PATH
dialogs.DEBUG = DEBUG
dialogs.LOG = LOG
dialogs.ERROR = ERROR
dialogs.getSetting = getSetting
dialogs.setSetting = setSetting

mods.CACHE_PATH = CACHE_PATH
mods.DEBUG = DEBUG
mods.LOG = LOG
mods.ERROR = ERROR
mods.getSetting = getSetting
mods.setSetting = setSetting


video.LOG = LOG
video.ERROR = ERROR

######################################################################################
# Base Window Classes
######################################################################################
def _async_raise(tid, exctype):
	try:
		LOG('Trying to kill thread...')
		import inspect,ctypes
		'''Raises an exception in the threads with id tid'''
		if not inspect.isclass(exctype):
			raise TypeError("Only types can be raised (not instances)")
		res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid,
													  ctypes.py_object(exctype))
		if res == 0:
			raise ValueError("invalid thread id")
		elif res != 1:
			# "if it returns a number greater than one, you're in trouble,
			# and you should call it again with exc=NULL to revert the effect"
			ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
			raise SystemError("PyThreadState_SetAsyncExc failed")
	except:
		ERROR('Error killing thread')

class StoppableThread(threading.Thread):
	def __init__(self,group=None, target=None, name=None, args=(), kwargs=None):
		kwargs = kwargs or {}
		self._stop = threading.Event()
		threading.Thread.__init__(self,group=group, target=target, name=name, args=args, kwargs=kwargs)
		
	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.isSet()
	
	def _get_my_tid(self):
		"""determines this (self's) thread id

		CAREFUL : this function is executed in the context of the caller
		thread, to get the identity of the thread represented by this
		instance.
		"""
		if not self.isAlive():
			raise threading.ThreadError("the thread is not active")

		# do we have it cached?
		if hasattr(self, "_thread_id"):
			return self._thread_id

		# no, look for it in the _active dict
		for tid, tobj in threading._active.items():
			if tobj is self:
				self._thread_id = tid
				return tid

		# TODO: in python 2.6, there's a simpler way to do : self.ident

		raise AssertionError("could not determine the thread's id")

	def raiseExc(self, exctype):
		"""Raises the given exception type in the context of this thread.

		If the thread is busy in a system call (time.sleep(),
		socket.accept(), ...), the exception is simply ignored.

		If you are sure that your exception should terminate the thread,
		one way to ensure that it works is:

			t = ThreadWithExc( ... )
			...
			t.raiseExc( SomeException )
			while t.isAlive():
				time.sleep( 0.1 )
				t.raiseExc( SomeException )

		If the exception is to be caught by the thread, you need a way to
		check that your thread has caught it.

		CAREFUL : this function is executed in the context of the
		caller thread, to raise an excpetion in the context of the
		thread represented by this instance.
		"""
		_async_raise( self._get_my_tid(), exctype )

		
class ThreadError:
	def __init__(self,message='Unknown'):
		self.message = message
		
	def __nonzero__(self):
		return False
	
class StoppableCallbackThread(StoppableThread):
	def __init__(self,target=None, name='FBUNKOWN'):
		self._target = target
		self._stop = threading.Event()
		self._finishedHelper = None
		self._finishedCallback = None
		self._progressHelper = None
		self._progressCallback = None
		self._errorHelper = None
		self._errorCallback = None
		self._threadName = name
		StoppableThread.__init__(self,name=name)
		
	def setArgs(self,*args,**kwargs):
		self.args = args
		self.kwargs = kwargs
		
	def run(self):
		try:
			self._target(*self.args,**self.kwargs)
		except forumbrowser.Error,e:
			LOG('ERROR IN THREAD: ' + e.message)
			self.errorCallback(ThreadError('%s: %s' % (self._threadName,e.message)))
		except:
			err = ERROR('ERROR IN THREAD: ' + self._threadName)
			self.errorCallback(ThreadError('%s: %s' % (self._threadName,err)))
		
	def setFinishedCallback(self,helper,callback):
		self._finishedHelper = helper
		self._finishedCallback = callback
	
	def setErrorCallback(self,helper,callback):
		self._errorHelper = helper
		self._errorCallback = callback
		
	def setProgressCallback(self,helper,callback):
		self._progressHelper = helper
		self._progressCallback = callback
		
	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.isSet()
		
	def progressCallback(self,*args,**kwargs):
		if xbmc.abortRequested:
			self.stop()
			return False
		if self.stopped(): return False
		if self._progressCallback: self._progressHelper(self._progressCallback,*args,**kwargs)
		return True
		
	def finishedCallback(self,*args,**kwargs):
		if xbmc.abortRequested:
			self.stop()
			return False
		if self.stopped(): return False
		if self._finishedCallback: self._finishedHelper(self._finishedCallback,*args,**kwargs)
		return True
	
	def errorCallback(self,error):
		if xbmc.abortRequested:
			self.stop()
			return False
		if self.stopped(): return False
		if self._errorCallback: self._errorHelper(self._errorCallback,error)
		return True

class ThreadWindow:
	def __init__(self):
		self._currentThread = None
		self._stopControl = None
		self._startCommand = None
		self._progressCommand = None
		self._endCommand = None
		self._isMain = False
		self._resetFunction()
			
	def setAsMain(self):
		self._isMain = True
		
	def setStopControl(self,control):
		self._stopControl = control
		control.setVisible(False)
		
	def setProgressCommands(self,start=None,progress=None,end=None):
		self._startCommand = start
		self._progressCommand = progress
		self._endCommand = end
		
	def onAction(self,action):
		if action == ACTION_RUN_IN_MAIN:
			if self._function:
				func,args,kwargs = self.getFunction()
				func(*args,**kwargs)
				return True
		elif action == ACTION_PREVIOUS_MENU:
			if self._currentThread and self._currentThread.isAlive():
				self._currentThread.stop()
				if self._endCommand: self._endCommand()
				if self._stopControl: self._stopControl.setVisible(False)
			if self._isMain and len(threading.enumerate()) > 1:
				d = xbmcgui.DialogProgress()
				d.create(__language__(30220),__language__(30221))
				d.update(0)
				self.stopThreads()
				if d.iscanceled():
					d.close()
					return True
				d.close()
			return False
		return False
	
	def stopThreads(self):
		for t in threading.enumerate():
			if isinstance(t,StoppableThread): t.stop()
		time.sleep(1)
		while len(threading.enumerate()) > 1:
			for t in threading.enumerate():
				#if t != threading.currentThread(): t.join()
				if isinstance(t,StoppableThread): t.raiseExc(Exception)
			time.sleep(1)
		
	def getFunction(self):
		func = self._function
		args = self._functionArgs
		kwargs = self._functionKwargs
		self._resetFunction()
		return func,args,kwargs
	
	def _resetFunction(self):
		self._function = None
		self._functionArgs = []
		self._functionKwargs = {}
		
	def runInMain(self,function,*args,**kwargs):
		self._function = function
		self._functionArgs = args
		self._functionKwargs = kwargs
		xbmc.executebuiltin('Action(codecinfo)')
		
	def endInMain(self,function,*args,**kwargs):
		if self._endCommand: self._endCommand()
		if self._stopControl: self._stopControl.setVisible(False)
		self.runInMain(function,*args,**kwargs)
		
	def getThread(self,function,finishedCallback=None,progressCallback=None,errorCallback=None,name='FBUNKNOWN'):
		if self._currentThread: self._currentThread.stop()
		if not progressCallback: progressCallback = self._progressCommand
		t = StoppableCallbackThread(target=function,name=name)
		t.setFinishedCallback(self.endInMain,finishedCallback)
		t.setErrorCallback(self.endInMain,errorCallback)
		t.setProgressCallback(self.runInMain,progressCallback)
		self._currentThread = t
		if self._stopControl: self._stopControl.setVisible(True)
		if self._startCommand: self._startCommand()
		return t
		
	def stopThread(self):
		if self._stopControl: self._stopControl.setVisible(False)
		if self._currentThread:
			self._currentThread.stop()
			self._currentThread = None
			if self._endCommand: self._endCommand()
		
class BaseWindowFunctions(ThreadWindow):
	def __init__( self, *args, **kwargs ):
		self._progMessageSave = ''
		self.closed = False
		self.headerTextFormat = '%s'
		ThreadWindow.__init__(self)
		
	def onClick( self, controlID ):
		return False
			
	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if ThreadWindow.onAction(self,action): return
		if action == ACTION_PREVIOUS_MENU:
			self.closed = True
			self.close()
		#xbmcgui.WindowXML.onAction(self,action)
	
	def startProgress(self):
		self._progMessageSave = self.getControl(104).getLabel()
		#self.getControl(310).setVisible(True)
	
	def setProgress(self,pct,message=''):
		if pct<0:
			self.stopThread()
			dialogs.showMessage('ERROR',message,error=True)
			return False
		w = int((pct/100.0)*self.getControl(300).getWidth())
		self.getControl(310).setWidth(w)
		self.getControl(104).setLabel(self.headerTextFormat % message)
		return True
		
	def endProgress(self):
		#self.getControl(310).setVisible(False)
		self.getControl(104).setLabel(self._progMessageSave)
		
	def highlightTerms(self,message):
		message = self.searchRE[0].sub(self.searchReplace,message)
		for sRE in self.searchRE[1:]: message = sRE.sub(self.searchWordReplace,message)
		message = message.replace('\r','')
		message = FB.MC.removeNested(message,'\[/?B\]','[B]')
		return message
	
	def searchReplace(self,m):
		return '[COLOR FFFF0000][B]%s[/B][/COLOR]' % '\r'.join(list(m.group(0)))
	
	def searchWordReplace(self,m):
		return '[COLOR FFAAAA00][B]%s[/B][/COLOR]' % m.group(0)
	
	def setupSearch(self):
		self.searchRE = None
		if self.search and not self.search.startswith('@!RECENT'):
			self.searchRE = [re.compile(re.sub('[\'"]','',self.search),re.I)]
			words = self.getSearchWords(self.search)
			if len(words) > 1:
				for w in words: self.searchRE.append(re.compile(w,re.I))
	
	def getSearchWords(self,text):
		words = []
		quoted = re.findall('(?P<quote>["\'])(.+?)(?P=quote)',text)
		for q in quoted: words.append(q[1])
		words += re.sub('(?P<quote>["\'])(.+?)(?P=quote)','',text).split()
		return words
		
class BaseWindow(xbmcgui.WindowXML,BaseWindowFunctions):
	def __init__(self, *args, **kwargs):
		BaseWindowFunctions.__init__(self, *args, **kwargs)
		xbmcgui.WindowXML.__init__( self )
		
	def onInit(self):
		pass
		
	def onAction(self,action):
		BaseWindowFunctions.onAction(self,action)
		
class BaseWindowDialog(xbmcgui.WindowXMLDialog,BaseWindowFunctions):
	def __init__(self, *args, **kwargs):
		BaseWindowFunctions.__init__(self, *args, **kwargs)
		xbmcgui.WindowXMLDialog.__init__( self )
	
	def onInit(self):
		pass
		
	def onAction(self,action):
		BaseWindowFunctions.onAction(self,action)

class PageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.next = ''
		self.prev = ''
		self.pageData = FB.getPageData(total_items=kwargs.get('total_items',0))
		self.firstRun = True
		self._firstPage = __language__(30110)
		self._lastPage = __language__(30111)
		self._newestPage = None
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onFocus( self, controlId ):
		self.controlId = controlId

	def onClick( self, controlID ):
		if controlID == 200:
			if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
		elif controlID == 202:
			if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
		elif controlID == 105:
			self.pageMenu()
		BaseWindow.onClick(self,controlID)
	
	def onAction(self,action):
		BaseWindow.onAction(self,action)
		if action == ACTION_NEXT_ITEM:
			if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
		elif action == ACTION_PREV_ITEM:
			if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
		
	def pageMenu(self):
		options = [self._firstPage,self._lastPage]
		if self._newestPage: options.append(self._newestPage)
		options.append(__language__(30115))
		idx = dialogs.dialogSelect(__language__(30114),options)
		if idx < 0: return
		if options[idx] == self._firstPage: self.gotoPage(self.pageData.getPageNumber(1))
		elif options[idx] == self._lastPage: self.gotoPage(self.pageData.getPageNumber(-1))
		elif options[idx] == self._newestPage:
			self.firstRun = True #For replies window
			self.gotoPage(self.pageData.getPageNumber(-1))
		else: self.askPageNumber()
		
	def askPageNumber(self):
		page = xbmcgui.Dialog().numeric(0,__language__(30116))
		try: int(page)
		except: return
		self.gotoPage(self.pageData.getPageNumber(page))
		
	def setupPage(self,pageData):
		if pageData:
			self.pageData = pageData
		else:
			from forumbrowser.forumbrowser import PageData
			pageData = PageData(None)
		self.getControl(200).setVisible(pageData.prev)
		self.getControl(202).setVisible(pageData.next)
		self.getControl(105).setLabel(pageData.getPageDisplay())
		
	def gotoPage(self,page): pass

######################################################################################
# Image Dialog
######################################################################################
class ImagesDialog(BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		BaseWindowDialog.__init__( self, *args, **kwargs )
	
	def onInit(self):
		BaseWindowDialog.onInit(self)
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
		if BaseWindow.onClick(self, controlID): return
		if controlID == 200:
			self.nextImage()
		elif controlID == 202:
			self.prevImage()
	
	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_NEXT_ITEM:
			self.nextImage()
		elif action == ACTION_PREV_ITEM:
			self.prevImage()
		elif action == ACTION_CONTEXT_MENU:
			self.doMenu()
		BaseWindowDialog.onAction(self,action)
		
	def doMenu(self):
		d = dialogs.ChoiceMenu('Options')
		d.addItem('save', 'Save Image')
		d.addItem('help','Help')
		result = d.getResult()
		if not result: return
		if result == 'save':
			self.saveImage()
		elif result == 'help':
			dialogs.showHelp('imageviewer')
			
	def downloadImage(self,url):
		base = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'slideshow'))
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		return Downloader(message=__language__(30148)).downloadURLs(base,[url],'.jpg')
		
	def saveImage(self):
		#browse(type, heading, shares[, mask, useThumbs, treatAsFolder, default])
		source = self.images[self.index]
		firstfname = os.path.basename(source)
		if source.startswith('http'):
			result = self.downloadImage(source)
			if not result:
				dialogs.showMessage('Failed','Failed to download file.',success=False)
				return
			source = result[0]
		filename = dialogs.doKeyboard('Enter Filename', firstfname)
		if filename == None: return
		default = __addon__.getSetting('last_download_path') or ''
		result = xbmcgui.Dialog().browse(3,'Select Directory','files','',False,True,default)
		__addon__.setSetting('last_download_path',result)
		if not os.path.exists(source): return
		target = os.path.join(result,filename)
		ct = 1
		original = filename
		while os.path.exists(target):
			fname, ext = os.path.splitext(original)
			filename = fname + '_' + str(ct) + ext
			ct+=1
			if os.path.exists(os.path.join(result,filename)): continue
			yes = xbmcgui.Dialog().yesno('File Exists','File exists!','Save as:',filename + '?','Enter New','Yes')
			if not yes:
				ct = 0
				filename = dialogs.doKeyboard('Enter Filename', filename)
				original = filename
				if filename == None: return
			target = os.path.join(result,filename)
		import shutil
		shutil.copy(source, target)
		dialogs.showMessage('Finished','File Saved Successfully: ',os.path.basename(target),success=True)

######################################################################################
# Forum Settings Dialog
######################################################################################
class ForumSettingsDialog(BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.colorsDir = os.path.join(CACHE_PATH,'colors')
		self.colorGif = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'white1px.gif')
		self.gifReplace = chr(255)*6
		self.items = []
		self.data = {}
		self.help = {}
		self.helpSep = FB.MC.hrReplace
		self.header = ''
		self.settingsChanged = False
		self.OK = False
		BaseWindowDialog.__init__( self, *args, **kwargs )
		
	def setHeader(self,header):
		self.header = header
		
	def onInit(self):
		self.getControl(250).setLabel('[B]%s[/B]' % self.header)
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
		item = xbmcgui.ListItem(name,valueDisplay)
		item.setProperty('value_type',vtype.split('.',1)[0])
		item.setProperty('value',str(value))
		item.setProperty('id',sid)
		if vtype == 'text.long':
			item.setProperty('help',self.help.get(sid,'') + '[CR][COLOR FF999999]%s[/COLOR][CR][B]Current:[/B][CR][CR]%s' % (self.helpSep,valueDisplay))
		else:
			item.setProperty('help',self.help.get(sid,''))
		self.items.append(item)
		self.data[sid] = {'name':name, 'value':value, 'type':vtype}
	
	def addSep(self):
		if len(self.items) > 0: self.items[-1].setProperty('separator','separator')
			
	def fillList(self):
		self.getControl(320).addItems(self.items)
		
	def onClick(self,controlID):
		if controlID == 320:
			self.editSetting()		
		elif controlID == 100:
			self.OK = True
			self.close()
		elif controlID == 101:
			self.cancel()
		
	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			self.cancel()
		
	def cancel(self):
		if self.settingsChanged:
			yes = xbmcgui.Dialog().yesno('Settings Changed','Settings changed.','Really discard changes?')
			if not yes: return
		self.close()
		
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
				val = dialogs.doKeyboard('Enter New Value',data['value'])
				item.setProperty('help',self.help.get(dID,'') + '[CR][COLOR FF999999]%s[/COLOR][CR][B]Current:[/B][CR][CR]%s' % (self.helpSep,val))
			elif data['type'].startswith('text.url'):
				if data['value']:
					yes = xbmcgui.Dialog().yesno('Clear?','Select yes to clear URL,','No to set new URL')
					if yes:
						data['value'] = ''
						item.setLabel2('')
						return
				val = browseWebURL(data['type'].split('.',2)[-1])
			else:
				val = dialogs.doKeyboard('Enter New Value',data['value'],hidden=data['type']=='text.password')
			if val == None: return
			if not self.validate(val,data['type']): return
			data['value'] = val
			item.setLabel2(data['type'] != 'text.password' and val or len(val) * '*')
		elif data['type'].startswith('webimage.'):
			url = data['type'].split('.',1)[-1]
			yes = xbmcgui.Dialog().yesno('Edit?','Select yes to edit the URL,','No to browse site images')
			if yes:
				logo = dialogs.doKeyboard('Edit Url:',data['value'] or 'http://')
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
			item.setLabel2(self.makeColorFile(color))
		elif data['type'] == 'function':
			data['value'][0](*data['value'][1:])
		
	def validate(self,val,vtype):
		if vtype == 'text.integer':
			if not val: return True
			try:
				int(val)
			except:
				dialogs.showMessage('Bad Value','Value must be an integer.')
				return False
		return True
				
	def refreshImage(self):
		cid = self.getFocusId()
		if not cid: return
		self.setFocusId(100)
		self.setFocusId(cid)
		
	def getWebImage(self,url):
		splash = dialogs.showActivitySplash('Getting Images')
		try:
			info = forumbrowser.HTMLPageInfo(url)
		finally:
			splash.close()
		domain = url.split('://',1)[-1].split('/',1)[0]
		logo = chooseLogo(domain,info.images(),keep_colors=True)
		return logo
	
	def makeColorFile(self,color):
		path = self.colorsDir
		try:
			replace = binascii.unhexlify(color)
		except:
			replace = chr(255)
		replace += replace
		target = os.path.join(path,color + '.gif')
		open(target,'w').write(open(self.colorGif,'r').read().replace(self.gifReplace,replace))
		return target
		
def editForumSettings(forumID):
	w = dialogs.openWindow(ForumSettingsDialog,'script-forumbrowser-forum-settings.xml',return_window=True,modal=False,theme='Default')
	sett,rules = loadForumSettings(forumID,get_both=True) or {'username':'','password':'','notify':False}
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	w.setHeader(forumID[3:])
	w.setHelp(dialogs.loadHelp('forumsettings.help') or {})
	w.addItem('username','Login User',sett.get('username',''),'text')
	w.addItem('password','Login Password',sett.get('password',''),'text.password')
	w.addItem('notify','Notifications',sett.get('notify',''),'boolean')
	w.addItem('extras','Post Attributes',sett.get('extras',''),'text')
	w.addItem('time_offset_hours','Time Offset',sett.get('time_offset_hours',''),'text.integer')
	w.addSep()
	w.addItem('description','Description',fdata.description,'text.long')
	w.addItem('logo','Logo',fdata.urls.get('logo',''),'webimage.' + fdata.forumURL())
	w.addItem('header_color','Header Color',fdata.theme.get('header_color',''),'color.' + forumID)
	if forumID.startswith('GB.'):
		w.addSep()
		w.addItem('login_url','Login Page',rules.get('login_url',''),'text.url.' + fdata.forumURL())
		w.addItem('rules','Post Parser Rules',(manageParserRules,forumID,rules),'function')
	oldLogo = fdata.urls.get('logo','')
	w.doModal()
	if w.OK:
		rules['login_url'] = w.data.get('login_url') and w.data['login_url']['value'] or None
		saveForumSettings(	forumID,
							username=w.data['username']['value'],
							password=w.data['password']['value'],
							notify=w.data['notify']['value'],
							extras=w.data['extras']['value'],
							time_offset_hours=w.data['time_offset_hours']['value'],
							rules=rules)
		fdata.description = w.data['description']['value']
		fdata.urls['logo'] = w.data['logo']['value']
		fdata.theme['header_color'] = w.data['header_color']['value']
		fdata.writeData()
	del w
	if oldLogo != fdata.urls['logo']:
		getCachedLogo(fdata.urls['logo'],forumID,clear=True)
	
######################################################################################
# Notifications Dialog
######################################################################################
class NotificationsDialog(BaseWindowDialog):
	def __init__( self, *args, **kwargs ):
		self.forumsWindow = kwargs.get('forumsWindow')
		self.initialForumID = kwargs.get('forumID')
		self.initialIndex = 0
		self.colorsDir = os.path.join(CACHE_PATH,'colors')
		if not os.path.exists(self.colorsDir): os.makedirs(self.colorsDir)
		self.colorGif = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'white1px.gif')
		self.gifReplace = chr(255)*6
		self.items = None
		self.stopTimeout = False
		self.started = False
		self.createItems()
		BaseWindowDialog.__init__( self, *args, **kwargs )
	
	def onInit(self):
		if self.started: return
		self.started = True
		BaseWindowDialog.onInit(self)
		if not self.forumsWindow: self.getControl(250).setLabel('Forum Browser: New Posts')
		self.fillList()
		self.startDisplayTimeout()
		if self.items:
			self.setFocusId(220)
		else:
			if self.forumsWindow: self.setFocusId(200)
		
	def onClick( self, controlID ):
		if BaseWindowDialog.onClick(self, controlID): return
		forumID = self.getSelectedForumID()
		if controlID == 220: self.changeForum()
		elif controlID == 200:
			forumID = addForum()
			if forumID: self.refresh(forumID)
		elif controlID == 201:
			forumID = addForumFromOnline()
			if forumID: self.refresh(forumID)
		elif controlID == 202:
			if removeForum(forumID): self.refresh()
		elif controlID == 203:
			addFavorite(forumID)
			self.refresh()
		elif controlID == 204:
			removeFavorite(forumID)
			self.refresh()
		elif controlID == 205:
			editForumSettings(forumID)
			item = self.getControl(220).getSelectedItem()
			if not item: return
			ndata = loadForumSettings(forumID) or {}
			item.setProperty('notify',ndata.get('notify') and 'notify' or '')
			
			fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
			logo = fdata.urls.get('logo','')
			exists, logopath = getCachedLogo(logo,forumID)
			if exists: logo = logopath
			item.setIconImage(logo)
			
			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			item.setProperty('bgcolor',hc)
			color = hc.upper()[2:]
			path = self.makeColorFile(color, self.colorsDir)
			item.setProperty('bgfile',path)
			
			self.setFocusId(220)
			
		elif controlID == 206: setForumColor(askColor(forumID),forumID)
		elif controlID == 207: addCurrentForumToOnlineDatabase(forumID)
		elif controlID == 208: updateThemeODB(forumID)
		elif controlID == 209:
			menu = dialogs.ChoiceMenu('Choose:')
			menu.addItem('login','Set Login Page')
			menu.addItem('rules','Set Post Parser Rules')
			result = menu.getResult()
			if not result: return
			if result == 'login':
				setLoginPage(forumID)
			elif result == 'rules':
				manageParserRules(forumID)
		elif controlID == 210:
			dialogs.showMessage(str(self.getControl(210).getLabel()),dialogs.loadHelp('options.help').get('help',''))
			
	def onAction(self,action):
		BaseWindowDialog.onAction(self,action)
		self.stopTimeout = True
		if action == ACTION_CONTEXT_MENU:
			focusID = self.getFocusId()
			if focusID == 220:
				self.toggleNotify()
			elif focusID > 199 and focusID < 210:
				helpname = ''
				if focusID  == 200: helpname = 'addforum'
				if focusID  == 201: helpname = 'addonline'
				if focusID  == 202: helpname = 'removeforum'
				if focusID  == 203: helpname = 'addfavorite'
				if focusID  == 204: helpname = 'removefavorite'
				if focusID  == 205: helpname = 'setlogins'
				if focusID  == 206: helpname = 'setcurrentcolor'
				if focusID  == 207: helpname = 'addcurrentonline'
				if focusID  == 208: helpname = 'updatethemeodb'
				if focusID  == 209: helpname = 'parserbrowser'
				dialogs.showMessage(str(self.getControl(focusID).getLabel()),dialogs.loadHelp('options.help').get(helpname,''))

		
	def startDisplayTimeout(self):
		if self.forumsWindow: return
		if getSetting('notify_dialog_close_only_video',True) and not self.isVideoPlaying(): return 
		duration = getSetting('notify_dialog_timout',0)
		if duration:
			xbmc.sleep(1000 * duration)
			if self.stopTimeout and getSetting('notify_dialog_close_activity_stops',True): return
			self.close()
	
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
		forumID = item.getProperty('forumID')
		return forumID or None
		
	def changeForum(self):
		forumID = self.getSelectedForumID()
		if not forumID: return
		if self.forumsWindow:
			self.forumsWindow.changeForum(forumID)
		else:
			#startForumBrowser(forumID)
			xbmc.executebuiltin("RunScript(script.forum.browser,forum=%s)" % forumID)
		self.close()
		
	def createItems(self):
		favs = []
		if not self.forumsWindow and getSetting('notify_dialog_only_enabled'):
			final = getNotifyList()
		else:
			favs = getFavorites()
			flist_tmp = os.listdir(FORUMS_PATH)
			rest = sorted(flist_tmp,key=fidSortFunction)
			if favs:
				for f in favs:
					if f in rest: rest.pop(rest.index(f))
				favs.append('')
			whole = favs + rest
			final = []
			for f in whole:
				if f and not f in final and not f.startswith('.'):
					final.append(f)
		unreadData = self.loadLastData() or {}
		uitems = []
		items = []
		colors = {}
		for f in final:
			flag = False
			path = getForumPath(f,just_path=True)
			unread = unreadData.get(f) or {}
			if not path: continue
			if not os.path.isfile(os.path.join(path,f)): continue
			fdata = forumbrowser.ForumData(f,path)
			ndata = loadForumSettings(f) or {}
			name = fdata.name
			logo = fdata.urls.get('logo','')
			exists, logopath = getCachedLogo(logo,f)
			if exists: logo = logopath
			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			item = xbmcgui.ListItem(name,iconImage=logo)
			item.setProperty('bgcolor',hc)
			color = hc.upper()[2:]
			if color in colors:
				path = colors[color]
			else:
				path = self.makeColorFile(color, self.colorsDir)
				colors[color] = path
			if f in favs: item.setProperty('favorite','favorite')
			item.setProperty('bgfile',path)
			item.setProperty('forumID',f)
			item.setProperty('type',f[:2])
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
			if flag:
				uitems.append(item)
			else:
				items.append(item)
		self.items = uitems + items
		idx = 0
		for item in self.items:
			if item.getProperty('forumID') == self.initialForumID: self.initialIndex = idx
			idx += 1
		
	def fillList(self):
		self.getControl(220).addItems(self.items)
		self.getControl(220).selectItem(self.initialIndex)
		self.initialForumID = None
		self.initialIndex = 0
		
	def refresh(self,forumID=None):
		self.initialForumID = forumID
		self.getControl(220).reset()
		self.createItems()
		self.fillList()
		
	def makeColorFile(self,color,path):
		try:
			replace = binascii.unhexlify(color)
		except:
			replace = chr(255)
		replace += replace
		target = os.path.join(path,color + '.gif')
		open(target,'w').write(open(self.colorGif,'r').read().replace(self.gifReplace,replace))
		return target
	
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
		flist = listForumSettings()
		nlist = []
		for f in flist:
			data = loadForumSettings(f)
			if data:
				if data['notify']: nlist.append(f)
		return nlist
######################################################################################
# Post Dialog
######################################################################################
class PostDialog(BaseWindowDialog):
	failedPM = None
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.doNotPost = kwargs.get('donotpost') or False
		self.title = self.post.title
		self.posted = False
		self.moderated = False
		self.display_base = '%s\n \n'
		BaseWindowDialog.__init__( self, *args, **kwargs )
	
	def onInit(self):
		BaseWindowDialog.onInit(self)
		self.getControl(122).setText(' ') #to remove scrollbar
		if self.failedPM:
			if self.failedPM.isPM == self.post.isPM and self.failedPM.tid == self.post.tid and self.failedPM.to == self.post.to:
				yes = xbmcgui.Dialog().yesno('Failed post found','Re-use previous failed post?')
				if yes:
					self.post = self.failedPM
					for line in self.post.message.split('\n'): self.addQuote(line)
					self.updatePreview()
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
					self.addQuote(line)
			else:
				for line in self.post.quote.split('\n'): self.addQuote(line)
		elif self.post.isEdit:
			for line in self.post.message.split('\n'): self.addQuote(line)
				
		self.updatePreview()
		self.setTheme()
		if self.post.moderated:
			self.moderated = True
			dialogs.showMessage('Note','Posting appears to be moderated.','Your message may not appear right away.')
		if self.isPM() or self.doNotPost: self.setTitle() #We're creating a thread
	
	def setTheme(self):
		if self.isPM():
			self.getControl(103).setLabel('[B]%s[/B]' % __language__(30177))
			self.getControl(202).setLabel(__language__(30178))
		else:
			self.getControl(103).setLabel('[B]Post Reply[/B]')
		if self.post.title:
			self.getControl(104).setLabel(self.post.title)
		else:
			self.getControl(104).setLabel(__language__(30120))
		
	def onClick( self, controlID ):
		if BaseWindow.onClick(self, controlID): return
		if controlID == 202:
			self.postReply()
		elif controlID == 104:
			self.setTitle()

	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_PREVIOUS_MENU:
			if not self.confirmExit(): return
		BaseWindowDialog.onAction(self,action)
		
	def confirmExit(self):
		if not self.getOutput() and not self.title: return True
		return xbmcgui.Dialog().yesno('Are You Sure?','Really close?','Changes will be lost.')
	
	def isPM(self):
		return str(self.post.pid).startswith('PM') or self.post.to
	
	def getOutput(self): pass
	
	def setTitle(self):
		keyboard = xbmc.Keyboard(self.title,__language__(30125))
		keyboard.doModal()
		if not keyboard.isConfirmed(): return
		title = keyboard.getText()
		self.getControl(104).setLabel(title)
		self.title = title
	
	def dialogCallback(self,pct,message):
		self.prog.update(pct,message)
		return True
		
	def postReply(self):
		message = self.getOutput()
		self.post.setMessage(self.title,message)
		self.posted = True
		if self.doNotPost:
			self.close()
			return
		splash = dialogs.showActivitySplash('Posting')
		try:
			if self.post.isPM:
				if not FB.doPrivateMessage(self.post,callback=splash.update):
					self.posted = False
					dialogs.showMessage(__language__(30050),__language__(30246),' ',self.post.error or '?',success=False)
					return
			else:
				if not FB.post(self.post,callback=splash.update):
					self.posted = False
					dialogs.showMessage(__language__(30050),__language__(30227),' ',self.post.error or '?',success=False)
					return
			dialogs.showMessage('Success',self.post.isPM and 'Message sent.' or 'Message posted.',' ',str(self.post.successMessage),success=True)
		except:
			self.posted = False
			err = ERROR('Error creating post')
			dialogs.showMessage('ERROR','Error creating post:',err,error=True)
			PostDialog.failedPM = self.post
		finally:
			splash.close()
		if not self.moderated and self.post.moderated:
			dialogs.showMessage('Note','Posting appears to be moderated.','Your message may not appear right away.')
		self.close()
		
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
	
	def updatePreview(self):
		disp = self.display_base % self.getOutput()
		if FB.browserType == 'ScraperForumBrowser':
			qf = FB.getQuoteFormat()
			if qf: disp = re.sub(qf,self.processQuote,disp)
			disp = self.parseCodes(disp).replace('\n','[CR]')
			disp = re.sub('\[(/?)b\]',r'[\1B]',disp)
			disp = re.sub('\[(/?)i\]',r'[\1I]',disp)
		else:
			disp =  FB.MC.messageToDisplay(disp.replace('\n','[CR]'))
		self.getControl(122).reset()
		self.getControl(122).setText(self.parseCodes(disp).replace('\n','[CR]'))

class LinePostDialog(PostDialog):
	def addQuote(self,quote):
		self.addLine(quote)
		
	def onClick( self, controlID ):
		if controlID == 200:
			self.addLineSingle()
		elif controlID == 201:
			self.addLineMulti()
		elif controlID == 120:
			self.editLine()
		PostDialog.onClick(self, controlID)
			
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		PostDialog.onAction(self,action)
		
	def doMenu(self):
		d = dialogs.ChoiceMenu(__language__(30051))
		item = self.getControl(120).getSelectedItem()
		if item:
			d.addItem('addbefore',__language__(30128))
			d.addItem('delete',__language__(30122))
			if CLIPBOARD and CLIPBOARD.hasData(('link','image','video')):
				d.addItem('pastebefore','Paste From Clipboard Before: ' + CLIPBOARD.hasData().title())
		if CLIPBOARD and CLIPBOARD.hasData(('link','image','video')):
			d.addItem('paste','Paste From Clipboard: ' + CLIPBOARD.hasData().title())
		d.addItem('help',__language__(30244))
		result = d.getResult()
		if result == 'addbefore': self.addLineSingle(before=True)
		elif result == 'delete': self.deleteLine()
		elif result == 'paste': self.paste()
		elif result == 'pastebefore': self.paste(before=True)
		elif result == 'help': dialogs.showHelp('editor')
		
	def paste(self,before=False):
		share = CLIPBOARD.getClipboard()
		if share.shareType == 'link':
			text = dialogs.doKeyboard('Enter Link Text')
			if not text: text = share.page
			paste = '[url=%s]%s[/url]' % (share.page,text)
		elif share.shareType == 'image':
			paste = '[img]%s[/img]' % share.url
		elif share.shareType == 'video':
			source = video.WebVideo().getVideoObject(share.page).sourceName.lower()
			paste = '[video=%s]%s[/video]' % (source,share.page)
			
		if before:
			self.addLineSingle(paste,True,False)
		else:
			self.addLine(paste)
		self.updatePreview()
			
	def getOutput(self):
		llist = self.getControl(120)
		out = ''
		for x in range(0,llist.size()):
			out += llist.getListItem(x).getProperty('text') + '\n'
		return out
		
	def addLine(self,line=''):
		item = xbmcgui.ListItem(label=self.displayLine(line))
		#we set text separately so we can have the display be formatted...
		item.setProperty('text',line)
		self.getControl(120).addItem(item)
		self.getControl(120).selectItem(self.getControl(120).size()-1)
		return True
		
	def displayLine(self,line):
		return line	.replace('\n',' ')\
					.replace('[/B]','[/b]')\
					.replace('[/I]','[/i]')\
					.replace('[/COLOR]','[/color]')
			
	def addLineSingle(self,line=None,before=False,update=True):
		if line == None: line = dialogs.doKeyboard(__language__(30123),'')
		if line == None: return False
		if before:
			clist = self.getControl(120)
			idx = clist.getSelectedPosition()
			lines = []
			for i in range(0,clist.size()):
				if i == idx: lines.append(line)
				lines.append(clist.getListItem(i).getProperty('text'))
			clist.reset()
			for l in lines: self.addLine(l)
			self.updatePreview()
			return True
				
		else:
			self.addLine(line)
			self.updatePreview()
			return True
		
	def addLineMulti(self):
		while self.addLineSingle(): pass
		
	def deleteLine(self):
		llist = self.getControl(120)
		pos = llist.getSelectedPosition()
		lines = []
		for x in range(0,llist.size()):
			if x != pos: lines.append(llist.getListItem(x).getProperty('text'))
		llist.reset()
		for line in lines: self.addLine(line)
		self.updatePreview()
		if pos > llist.size(): pos = llist.size()
		llist.selectItem(pos)
	
	def editLine(self):
		item = self.getControl(120).getSelectedItem()
		if not item: return
		line = dialogs.doKeyboard(__language__(30124),item.getLabel())
		if line == None: return False
		item.setProperty('text',line)
		item.setLabel(self.displayLine(line))
		self.updatePreview()
		#re.sub(q,'[QUOTE=\g<user>;\g<postid>]\g<quote>[/QUOTE]',FB.MC.lineFilter.sub('',test3))

######################################################################################
#
# PlayerMonitor
#
######################################################################################
class PlayerMonitor(xbmc.Player):
	def __init__(self,core=None):
		self.init()
		xbmc.Player.__init__(core)
		
	def init(self):
		self.interrupted = None
		self.isSelfPlaying = False
		self.stack = 0
		self.currentTime = None
		self.FBisRunning = True
		
	def start(self,path):
		interrupted = None
		if getSetting('video_return_interrupt',True):
			interrupted = video.current()
			self.getCurrentTime()
		self.interrupted = interrupted
		self.doPlay(path)
		
	def finish(self):
		self.FBisRunning = False
		if getSetting('video_stop_on_exit',True):
			self.doStop()
			if self.interrupted: self.wait()
		else:
			if getSetting('video_return_interrupt_after_exit',False) and self.interrupted:
				self.waitLong()
		LOG('PLAYER: Exiting')
		
	def doPlay(self,path):
		self.played = path
		self.isSelfPlaying = True
		if getSetting('video_start_preview',True):
			video.play(path, preview=True)
		else:
			self.play(path)
		
	def doStop(self):
		if not self.isSelfPlaying: return
		LOG('PLAYER: Stopping forum video')
		self.stop()
		
	def wait(self):
		LOG('PLAYER: Waiting for video to stop...')
		ct = 0
		while self.interrupted and not xbmc.abortRequested:
			xbmc.sleep(1000)
			ct+=1
			if ct > 19: break #Don't know if this is necessary, but it's here just in case.
			
	def waitLong(self):
		LOG('PLAYER: Waiting after FB close to resume interrupted video...')
		while self.interrupted and not xbmc.abortRequested:
			xbmc.sleep(1000)
		
	def playInterrupted(self):
		if not self.isSelfPlaying: return
		self.isSelfPlaying = False
		if self.interrupted:
			LOG('PLAYER: Playing interrupted video')
			if getSetting('video_bypass_resume_dialog',True) and self.currentTime:
				try:
					xbmc.sleep(1000)
					video.playAt(self.interrupted, *self.currentTime)
				except:
					ERROR('PLAYER: Failed manually resume video - sending to XBMC')
					xbmc.sleep(1000)
					video.play(self.interrupted)
			else:
				xbmc.sleep(1000)
				video.play(self.interrupted,getSetting('video_resume_as_preview',False))
		self.interrupted = None
		self.currentTime = None
	
	def onPlayBackStarted(self):
		if self.FBisRunning and getSetting('video_resume_as_preview',False) and not self.isSelfPlaying:
			xbmc.sleep(1000)
			xbmc.executebuiltin('Action(FullScreen)')
		
	def onPlayBackEnded(self):
		self.playInterrupted()
		
	def onPlayBackStopped(self):
		self.playInterrupted()
		
	def pauseStack(self):
		if not self.stack: video.pause()
		self.stack += 1
		
	def resumeStack(self):
		self.stack -= 1
		if self.stack < 1:
			self.stack = 0
			video.resume()
		
	def getCurrentTime(self):
		if not video.isPlaying(): return None
		offset = getSetting('video_resume_offset',0)
		val = self.getTime() - offset
		if val < 0: val = 0
		(ms,tsec) = math.modf(val)
		m, s = divmod(int(tsec), 60)
		h, m = divmod(m, 60)
		self.currentTime = (h,m,s,int(ms*1000))
		
######################################################################################
#
# Message Window
#
######################################################################################		
class MessageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.searchRE = kwargs.get('search_re')
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]'
		self.imageReplace = 'IMG #%s'
		self.action = None
		self.started = False
		self.interruptedVideo = None
		self.videoHandler = video.WebVideo()
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		BaseWindow.onInit(self)
		if self.started: return
		self.started = True
		self.setLoggedIn()
#		if __addon__.getSetting('use_forum_colors') == 'true':
#			if (FB.theme.get('mode') == 'dark' or __addon__.getSetting('color_mode') == '1') and __addon__.getSetting('color_mode') != '2':
#				text = '[COLOR FFFFFFFF]%s[/COLOR][CR] [CR]' % (self.post.translated or self.post.messageAsDisplay())
#			else:
#				text = '[COLOR FF000000]%s[/COLOR][CR] [CR]' % (self.post.translated or self.post.messageAsDisplay())
#		else:
#			text = '%s[CR] [CR]' % (self.post.translated or self.post.messageAsDisplay())
		s = dialogs.showActivitySplash()
		try:
			text = '%s[CR] [CR]' % self.post.messageAsDisplay(raw=True)
		finally:
			s.close()
			
		if self.searchRE: text = self.highlightTerms(text)
		self.getControl(122).setText(text)
		self.getControl(102).setImage(self.post.avatarFinal)
		self.setTheme()
		self.getImages()
		self.getLinks()
		
	def setTheme(self):
		self.getControl(103).setLabel('[B]%s[/B]' % self.post.cleanUserName() or '')
		title = ''
		if self.post.postNumber: title = '#' + str(self.post.postNumber) + ' '
		title += self.post.title or ''
		self.getControl(104).setLabel('[B]%s[/B]' % title)
		self.getControl(105).setLabel(self.post.date or '')
		
	def getLinks(self):
		ulist = self.getControl(148)
		links = self.post.links()
		checkVideo = False
		for link in links:
			checkVideo = self.videoHandler.mightBeVideo(link.url)
			if checkVideo: break
			checkVideo = self.videoHandler.mightBeVideo(link.text)
			if checkVideo: break
		s = None
		if checkVideo: s = dialogs.showActivitySplash('Getting Video Info...')
		try:
			for link in links:
				item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
				video = None
				if checkVideo:
					try:
						video = self.videoHandler.getVideoObject(link.url)
						if not video: video = self.videoHandler.getVideoObject(link.text)
					except:
						LOG('Error getting video info')
				if video:
					item.setIconImage(video.thumbnail)
					if video.title: item.setLabel(video.title)
					item.setLabel2('%s: %s' % (video.sourceName,video.ID))
				elif link.textIsImage():
					item.setIconImage(link.text)
				elif link.isImage():
					item.setIconImage(link.url)
				elif link.isPost():
					item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-post.png'))
				elif link.isThread():
					item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-thread.png'))
				else:
					item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-link.png'))
				ulist.addItem(item)
		finally:
			if s: s.close()

	def getImages(self):
		i=0
		urlParentDirFilter = re.compile('(?<!/)/\w[^/]*?/\.\./')
		for url in self.post.imageURLs():
			i+=1
			while urlParentDirFilter.search(url):
				#TODO: Limit
				url = urlParentDirFilter.sub('/',url)
			url = url.replace('/../','/')
			item = xbmcgui.ListItem(self.imageReplace % i,iconImage=url)
			item.setProperty('url',url)
			self.getControl(150).addItem(item)
		#targetdir = os.path.join(__addon__.getAddonInfo('profile'),'messageimages')
		#TD.startDownload(targetdir,self.post.imageURLs(),ext='.jpg',callback=self.getImagesCallback)
		
	def getImagesCallback(self,file_dict):
		for fname,idx in zip(file_dict.values(),range(0,self.getControl(150).size())):
			fname = xbmc.translatePath(fname)
			self.getControl(150).getListItem(idx).setIconImage(fname)
			
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if BaseWindow.onClick(self, controlID): return
		if controlID == 148:
			self.linkSelected()
		elif controlID == 150:
			self.showImage(self.getControl(150).getSelectedItem().getProperty('url'))
	
	def showVideo(self,source):
		if video.isPlaying() and getSetting('video_ask_interrupt',True):
			line2 = getSetting('video_return_interrupt',True) and __language__(30254) or ''
			if not xbmcgui.Dialog().yesno(__language__(30255),__language__(30256),line2):
				return
		PLAYER.start(source)
		#video.play(source)
		
	def getSelectedLink(self):
		idx = self.getControl(148).getSelectedPosition()
		if idx < 0: return None
		links = self.post.links()
		if idx >= len(links): return None
		return links[idx]
		
	def linkSelected(self):
		link = self.getSelectedLink()
		if not link: return
		if self.videoHandler.mightBeVideo(link.url) or self.videoHandler.mightBeVideo(link.text):
			s = dialogs.showActivitySplash()
			try:
				video = self.videoHandler.getVideoObject(link.url)
				if not video: video = self.videoHandler.getVideoObject(link.text)
				if video and video.isVideo:
					self.showVideo(video.getPlayableURL())
					return
			finally:
				s.close()
		
		if link.isImage() and not link.textIsImage():
			self.showImage(link.url)
		elif link.isPost() or link.isThread():
			self.action = forumbrowser.PostMessage(tid=link.tid,pid=link.pid)
			self.close()
		else:
			try:
				webviewer.getWebResult(link.url,dialog=True,browser=FB.browser)
			except:
				raise
				#We're in Boxee
				wvPath = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'webviewer'))
				webviewer.getWebResult(link.url,dialog=True,runFromSubDir=wvPath)
				#xbmc.executebuiltin('XBMC.RunScript(special://home/apps/script.web.viewer/default.py,%s)' % link.url)
			
#			base = xbmcgui.Dialog().browse(3,__language__(30144),'files')
#			if not base: return
#			fname,ftype = Downloader(message=__language__(30145)).downloadURL(base,link.url)
#			if not fname: return
#			dialogs.showMessage(__language__(30052),__language__(30146),fname,__language__(30147) % ftype)
		
	def showImage(self,url):
		#base = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'slideshow'))
		#if not os.path.exists(base): os.makedirs(base)
		#clearDirFiles(base)
		#image_files = Downloader(message=__language__(30148)).downloadURLs(base,[url],'.jpg')
		#if not image_files: return
		image_files = self.post.imageURLs()
		for l in self.post.links():
			if l.isImage() and not l.textIsImage(): image_files.append(l.url)
		if url in image_files:
			image_files.pop(image_files.index(url))
			image_files.insert(0,url)
		w = ImagesDialog("script-forumbrowser-imageviewer.xml" ,__addon__.getAddonInfo('path'),THEME,images=image_files,parent=self)
		w.doModal()
		del w
			
	def onAction(self,action):
		BaseWindow.onAction(self,action)
		if action == ACTION_CONTEXT_MENU:
			if self.getFocusId() == 148:
				self.doLinkMenu()
			elif self.getFocusId() == 150:
				self.doImageMenu()
			else:
				self.doMenu()
		
	def doLinkMenu(self):
		link = self.getSelectedLink()
		if not link: return
		d = dialogs.ChoiceMenu('Link Options')
		if CLIPBOARD:
			d.addItem('copy','Copy Link To Clipboard')
			if link.isImage():
				d.addItem('copyimage','Copy Image URL To Clipboard')
			video = self.videoHandler.getVideoObject(link.url)
			if not video: video = self.videoHandler.getVideoObject(link.text)
			if video and video.isVideo: d.addItem('copyvideo','Copy Video URL To Clipboard')
				
		if d.isEmpty(): return
		result = d.getResult()
		if result == 'copy':
			share = CLIPBOARD.getShare('script.evernote','link')
			share.page = link.url
			CLIPBOARD.setClipboard(share)
		elif result == 'copyimage':
			share = CLIPBOARD.getShare('script.evernote','image')
			share.url = link.url
			CLIPBOARD.setClipboard(share)
		elif result == 'copyvideo':
			share = CLIPBOARD.getShare('script.evernote','video')
			video = self.videoHandler.getVideoObject(link.url)
			if video:
				share.page = link.url
			else:
				share.page = link.text
			CLIPBOARD.setClipboard(share)
				
	def doImageMenu(self):
		img = self.getControl(150).getSelectedItem().getProperty('url')
		d = dialogs.ChoiceMenu('Image Options')
		if CLIPBOARD:
			d.addItem('copy','Copy Image URL To Clipboard')
		if d.isEmpty(): return
		result = d.getResult()
		if result == 'copy':
			share = CLIPBOARD.getShare('script.evernote','image')
			share.url = img
			CLIPBOARD.setClipboard(share)
	
	def doMenu(self):
		d = dialogs.ChoiceMenu(__language__(30051))
		if FB.canPost(): d.addItem('quote',self.post.isPM and __language__(30249) or __language__(30134))
		if FB.canDelete(self.post.cleanUserName(),self.post.messageType()): d.addItem('delete',__language__(30141))
		if FB.canEditPost(self.post.cleanUserName()): d.addItem('edit',__language__(30232))
		if self.post.extras: d.addItem('extras','User/Post Extra Info')
		d.addItem('help',__language__(30244))
		result = d.getResult()
		if result == 'quote': self.openPostDialog(quote=True)
		elif result == 'delete': self.deletePost()
		elif result == 'edit':
			splash = dialogs.showActivitySplash('Getting post for edit...')
			try:
				pm = FB.getPostForEdit(self.post)
			finally:
				splash.close()
			pm.tid = self.post.tid
			if openPostDialog(editPM=pm):
				self.action = forumbrowser.Action('REFRESH-REOPEN')
				self.action.pid = pm.pid
				self.close()
		elif result == 'extras':
			showUserExtras(self.post)
		elif result == 'help':
			dialogs.showHelp('message')
			
	def deletePost(self):
		result = deletePost(self.post,is_pm=self.post.isPM)
		self.action = forumbrowser.Action('REFRESH')
		if result: self.close()
		
	def openPostDialog(self,quote=False):
		pm = openPostDialog(quote and self.post or None,pid=self.post.postId,tid=self.post.tid,fid=self.post.fid)
		if pm:
			self.action = forumbrowser.PostMessage(pid=pm.pid)
			self.action.action = 'GOTOPOST'
			self.close()
		
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
			to = dialogs.doKeyboard('Enter Recipient(s)',default=default)
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
	yes = xbmcgui.Dialog().yesno('Really Delete?','Are you sure you want to delete this message?')
	if not yes: return
	splash = dialogs.showActivitySplash('Deleting')
	try:
		if is_pm or post.isPM:
			pm.isPM = True
			result = FB.deletePrivateMessage(pm)
		else:
			result = FB.deletePost(pm)
		if not result:
			dialogs.showMessage('Failed','Failed to delete: ',pm.error or 'Reason unknown.',success=False)
		else:
			dialogs.showMessage('Success',pm.isPM and 'Message deleted.' or 'Post deleted.',success=True)
	except:
		err = ERROR('Delete post error.')
		LOG('Error deleting post/pm: ' + err)
		dialogs.showMessage('ERROR','Error while deleting post: [CR]',err,error=True)
		return None
	finally:
		splash.close()
	return result

def showUserExtras(post,ignore=None):
	out = ''
	for k,v in post.getExtras(ignore=ignore).items():
		out += '[B]' + k.title() + ':[/B] [COLOR FF550000]' + texttransform.convertHTMLCodes(str(v)) + '[/COLOR]\n'
	dialogs.showMessage('User/Post Info',out,scroll=True)

######################################################################################
#
# Replies Window
#
######################################################################################
class RepliesWindow(PageWindow):
	info_display = {'postcount':'posts','joindate':'joined'}
	def __init__( self, *args, **kwargs ):
		PageWindow.__init__( self,total_items=int(kwargs.get('reply_count',0)),*args, **kwargs )
		self.pageData.isReplies = True
		self.threadItem = item = kwargs.get('item')
		self.dontOpenPD = False
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
		self.search_uname = kwargs.get('search_name','')
		self.parent = kwargs.get('parent')
		#self._firstPage = __language__(30113)
		self._newestPage = __language__(30112)
		self.me = FB.user
		self.posts = {}
		self.empty = True
		self.desc_base = u'[CR]%s[CR] [CR]'
		self.ignoreSelect = False
		self.firstRun = True
		self.started = False
		self.currentPMBox = {}
		self.timeOffset = getForumSetting(FB.getForumID(),'time_offset_hours',0)
	
	def onInit(self):
		BaseWindow.onInit(self)
		if self.started: return
		self.started = True
		self.setLoggedIn()
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.postSelected()
		self.setPMBox()
		self.setTheme()
		self.setPostButton()
		self.showThread()
		#self.setFocusId(120)
				
	def setPostButton(self):
		if self.isPM():
			self.getControl(201).setEnabled(FB.canPrivateMessage())
			self.getControl(201).setLabel(__language__(30177))
		elif self.search:
			self.getControl(201).setEnabled(True)
			self.getControl(201).setLabel(__language__(3014))
		else:
			self.getControl(201).setEnabled(FB.canPost())
			self.getControl(201).setLabel(__language__(3002))
			
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
		mtype = self.isPM() and self.currentPMBox.get('name','Inbox') or __language__(30130)
		#if self.isPM(): self.getControl(201).setLabel(__language__(30177))
		self.getControl(103).setLabel('[B]%s[/B]' % mtype)
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
		
	def showThread(self,nopage=False):
		if nopage:
			page = ''
		else:
			page = '1'
			if __addon__.getSetting('open_thread_to_newest') == 'true':
				if not self.searchRE: page = '-1'
		self.fillRepliesList(FB.getPageData(is_replies=True).getPageNumber(page))
		
	def isPM(self):
		return self.tid == 'private_messages'
	
	def errorCallback(self,error):
		dialogs.showMessage(__language__(30050),__language__(30131),error.message,error=True)
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
				t.setArgs(uname=self.search_uname,uid=self.uid,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
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
		message = post.messageAsDisplay(short)
		if self.searchRE: message = self.highlightTerms(message)
		item.setProperty('message',message)
	
	def updateItem(self,item,post):
		alt = self.getUserInfoAttributes()
		defAvatar = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins',THEME,'media','forum-browser-avatar-none.png'))
		webvid = video.WebVideo()
		showIndicators = getSetting('show_media_indicators',True)
		countLinkImages = getSetting('smi_count_link_images',False)
		item.setProperty('alternate1','')
		item.setProperty('alternate2','')
		item.setProperty('alternate3','')
		
		self._updateItem(item,post,defAvatar,showIndicators,countLinkImages,webvid,alt)
		self.setFocusId(120)
		
	def _updateItem(self,item,post,defAvatar,showIndicators,countLinkImages,webvid,alt):
		url = defAvatar
		if post.avatar: url = FB.makeURL(post.avatar)
		post.avatarFinal = url
		self.setMessageProperty(post,item,True)
		item.setProperty('post',post.postId)
		item.setProperty('avatar',url)
		#item.setProperty('status',texttransform.convertHTMLCodes(post.status))
		item.setProperty('date',post.getDate(self.timeOffset))
		item.setProperty('online',post.online and 'online' or '')
		item.setProperty('postnumber',post.postNumber and unicode(post.postNumber) or '')
		if post.online:
			item.setProperty('activity',post.getActivity(self.timeOffset * 3600))
		else:
			item.setProperty('last_seen',post.getActivity(self.timeOffset * 3600))
		if showIndicators:
			hasimages,hasvideo = post.hasMedia(webvid,countLinkImages)
			item.setProperty('hasimages',hasimages and 'hasimages' or 'noimages')
			item.setProperty('hasvideo',hasvideo and 'hasvideo' or 'novideo')
		altused = []
		extras = post.getExtras()
		for a in alt:
			val = extras.get(a)
			if val != None and str(val):
				edisp = val and '%s: %s' % (self.info_display.get(a,a).title(),texttransform.convertHTMLCodes(str(val))) or ''
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
			
	def doFillRepliesList(self,data):
		if 'newthreadid' in data: self.tid = data['newthreadid']
		if not data:
			self.setFocusId(201)
			if data.error == 'CANCEL': return
			LOG('GET REPLIES ERROR')
			dialogs.showMessage(__language__(30050),self.isPM() and __language__(30135) or __language__(30131),__language__(30053),'[CR]' + data.error,success=False)
			return
		elif not data.data:
			if data.data == None:
				self.setFocusId(201)
				LOG('NO REPLIES')
				dialogs.showMessage(__language__(30050),self.isPM() and __language__(30135) or __language__(30131),__language__(30053),success=False)
			else:
				self.setFocusId(201)
				self.getControl(104).setLabel(self.isPM() and __language__(30251) or __language__(30250))
				LOG('No messages/posts - clearing list')
				self.getControl(120).reset()
				self.getControl(120).addItems([])
			return
		
		self.empty = False
		defAvatar = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins',THEME,'media','forum-browser-avatar-none.png'))
		#xbmcgui.lock()
		try:
			self.getControl(120).reset()
			if not self.topic: self.topic = data.pageData.topic
			if not self.tid: self.tid = data.pageData.tid
			self.setupPage(data.pageData)
			if getSetting('reverse_sort',False) and not self.isPM():
				data.data.reverse()
			alt = self.getUserInfoAttributes()
			self.posts = {}
			select = -1
			webvid = video.WebVideo()
			showIndicators = getSetting('show_media_indicators',True)
			countLinkImages = getSetting('smi_count_link_images',False)
			items = []
			for post,idx in zip(data.data,range(0,len(data.data))):
				if self.pid and post.postId == self.pid: select = idx
				self.posts[post.postId] = post
				user = re.sub('<.*?>','',post.userName)
				item = xbmcgui.ListItem(label=post.isSent and 'To: ' + user or user)
				if user == self.me: item.setInfo('video',{"Director":'me'})
				self._updateItem(item,post,defAvatar,showIndicators,countLinkImages,webvid,alt)
				items.append(item)
			self.getControl(120).addItems(items)
			self.setFocusId(120)
			if select > -1:
				self.getControl(120).selectItem(int(select))
			elif self.firstRun and getSetting('open_thread_to_newest',False) and not self.isPM() and not getSetting('reverse_sort',False) and FB.canOpenLatest() and not self.search:
				self.getControl(120).selectItem(self.getControl(120).size() - 1)
			self.firstRun = False
		except:
			self.setFocusId(201)
			#xbmcgui.unlock()
			ERROR('FILL REPLIES ERROR')
			dialogs.showMessage(__language__(30050),__language__(30133),error=True)
			raise
		#xbmcgui.unlock()
		if select > -1 and not self.dontOpenPD:
			self.dontOpenPD = False
			self.postSelected(itemindex=select)
		
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
		self.pid = ''
		self.setLoggedIn()
			
	def getUserInfoAttributes(self):
		data = loadForumSettings(FB.getForumID())
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
		
	def postSelected(self,itemindex=-1):
		if itemindex > -1:
			item = self.getControl(120).getListItem(itemindex)
		else:
			item = self.getControl(120).getSelectedItem()
		if not item: return
		post = self.posts.get(item.getProperty('post'))
		if self.search and getSetting('search_open_thread',False):
			return self.openPostThread(post)
		post.tid = self.tid
		post.fid = self.fid
		w = dialogs.openWindow(MessageWindow,"script-forumbrowser-message.xml" ,return_window=True,post=post,search_re=self.searchRE,parent=self)
		self.setMessageProperty(post,item)
		self.setFocusId(120)
		if w.action:
			if w.action.action == 'CHANGE':
				self.topic = ''
				self.pid = w.action.pid
				self.tid = w.action.tid
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
		del w
		
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
		PageWindow.onClick(self,controlID)
		
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		PageWindow.onAction(self,action)
	
	def newSearch(self):
		terms = dialogs.doKeyboard('Enter Search Terms',self.search or '')
		if not terms: return
		self.search = terms
		self.setupSearch()
		self.fillRepliesList()
	
	def selectNewPMBox(self):
		boxes = FB.getPMBoxes(update=False)
		if not boxes: return #TODO: Show message
		d = dialogs.ChoiceMenu('Select Box')
		for b in boxes:
			d.addItem(b,b.get('name','?'))
		box = d.getResult()
		if not box: return
		self.currentPMBox = box
		self.setTheme()
		self.fillRepliesList()
		
	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu(__language__(30051),with_splash=True)
		post = None
		try:
			if self.isPM():
				boxes = FB.getPMBoxes(update=False)
				if boxes and len(boxes) > 1:
					d.addItem('changebox','Change PM Box')
			if item:
				post = self.posts.get(item.getProperty('post'))
				if FB.canPost() and not self.search:
					d.addItem('quote',self.isPM() and __language__(30249) or __language__(30134))
				if FB.canDelete(item.getLabel(),post.messageType()):
					d.addItem('delete',__language__(30141))
				if not self.isPM():
					if FB.canEditPost(item.getLabel()):
						d.addItem('edit',__language__(30232))
						
			if self.threadItem:
				if FB.isThreadSubscribed(self.tid,self.threadItem.getProperty('subscribed')):
					if FB.canUnSubscribeThread(self.tid): d.addItem('unsubscribe',__language__(30240) + ': ' + self.threadItem.getLabel2()[:25])
				else:
					if FB.canSubscribeThread(self.tid): d.addItem('subscribe',__language__(30236) + ': ' + self.threadItem.getLabel2()[:25])
			if post and item.getProperty('extras'):
				d.addItem('extras','User/Post Extra Info')
			if item and FB.canPrivateMessage() and not self.isPM():
				d.addItem('pm',__language__(30253) % item.getLabel())
			if post and post.canLike():
				d.addItem('like','Like Post')
			if post and post.canUnlike():
				d.addItem('unlike','Unlike Post')
			if self.searchRE and not getSetting('search_open_thread',False):
				d.addItem('open_thread','Open Post Thread')
			d.addItem('refresh',__language__(30054))
			d.addItem('help',__language__(30244))
		finally:
			d.cancel()
		
		result = d.getResult()
		if not result: return
		if result == 'changebox':
			self.selectNewPMBox()
			return
		elif result == 'quote':
			self.stopThread()
			self.openPostDialog(post)
		elif result == 'refresh':
			self.stopThread()
			self.fillRepliesList(self.pageData.getPageNumber())
		elif result == 'edit':
			splash = dialogs.showActivitySplash('Getting post for edit...')
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
			quote = xbmcgui.Dialog().yesno('Quote?','Quote the message?')
			self.openPostDialog(post,force_pm=True,no_quote=not quote)
		elif result == 'like':
			splash = dialogs.showActivitySplash('Liking')
			try:
				post.like()
				self.updateItem(item, post)
			finally:
				splash.close()
		elif result == 'unlike':
			splash = dialogs.showActivitySplash('Un-Liking')
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
			
	def deletePost(self):
		item = self.getControl(120).getSelectedItem()
		pid = item.getProperty('post')
		if not pid: return
		post = self.posts.get(pid)
		if deletePost(post,is_pm=self.isPM()):
			self.fillRepliesList(self.pageData.getPageNumber())
		
	def openPostThread(self,post):
		if not post: return
		dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,fid=post.fid,tid=post.tid,pid=post.postId,topic=post.topic,search_re=self.searchRE,parent=self)
	
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
			dialogs.showMessage('Success','Subscribed to thread.',success=True)
		else:
			dialogs.showMessage('Failed','Failed to subscribed to thread:',str(result),success=False)
		return result
	finally:
		splash.close()
		
def unSubscribeThread(tid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.unSubscribeThread(tid)
		if result == True:
			dialogs.showMessage('Success','Unsubscribed from thread.',success=True)
		else:
			dialogs.showMessage('Failed','Failed to unsubscribed from thread:',str(result),success=False)
		return result
	finally:
		splash.close()

def subscribeForum(fid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.subscribeForum(fid)
		if result == True:
			dialogs.showMessage('Success','Subscribed to forum.',success=True)
		else:
			dialogs.showMessage('Failed','Failed to subscribed to forum:',str(result),success=False)
		return result
	finally:
		splash.close()

def unSubscribeForum(fid):
	splash = dialogs.showActivitySplash()
	try:
		result = FB.unSubscribeForum(fid)
		if result == True:
			dialogs.showMessage('Success','Unsubscribed from forum.',success=True)
		else:
			dialogs.showMessage('Failed','Failed to unsubscribed from forum:',str(result),success=False)
		return result
	finally:
		splash.close()
	
######################################################################################
#
# Threads Window
#
######################################################################################
class ThreadsWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.parent = kwargs.get('parent')
		self.forumItem = kwargs.get('item')
		self.me = self.parent.getUsername() or '?'
		self.search = kwargs.get('search_terms')
		self.search_uname = kwargs.get('search_name','')
		
		self.setupSearch()
		
		self.empty = True
		self.textBase = '%s'
		self.newBase = '[B]%s[/B]'
		self.highBase = '%s'
		self.forum_desc_base = '[I]%s [/I]'
		self.started = False
		PageWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		BaseWindow.onInit(self)
		if self.started: return
		self.started = True
		self.setLoggedIn()
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.setTheme()
		self.fillThreadList()
		#self.setFocus(self.getControl(120))
			
	def setTheme(self):
		self.desc_base = unicode.encode(__language__(30162)+' %s','utf8')
		self.getControl(103).setLabel('[B]%s[/B]' % (self.fid != 'subscriptions' and __language__(30160) or ''))
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
	
	def errorCallback(self,error):
		dialogs.showMessage(__language__(30050),__language__(30161),error.message,error=True)
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
				t.setArgs(uname=self.search_uname,callback=t.progressCallback,donecallback=t.finishedCallback,page_data=self.pageData)
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
		if 'newforumid' in data: self.fid = data['newforumid']
		if not data:
			if data.error == 'CANCEL': return
			LOG('GET THREADS ERROR')
			dialogs.showMessage(__language__(30050),__language__(30161),__language__(30053),data.error,success=False)
			return
		
		self.empty = False
		try:
			self.getControl(120).reset()
			self.setupPage(data.pageData)
			if not (self.addForums(data['forums']) + self.addThreads(data.data)):
				LOG('Empty Forum')
				dialogs.showMessage(__language__(30229),__language__(30230),success=False)
			self.setFocusId(120)
		except:
			ERROR('FILL THREAD ERROR')
			dialogs.showMessage(__language__(30050),__language__(30163),error=True)
		self.setLoggedIn()
			
	def addThreads(self,threads):
		if not threads: return False
		for t in threads:
			if hasattr(t,'groupdict'):
				tdict = t.groupdict()
			else:
				tdict = t
			tid = tdict.get('threadid','')
			starter = tdict.get('starter','Unknown')
			title = tdict.get('title','')
			title = texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',title))
			last = tdict.get('lastposter','')
			fid = tdict.get('forumid','')
			sticky = tdict.get('sticky') and 'sticky' or ''
			reply_count = unicode(tdict.get('reply_number','0') or '0')
			if starter == self.me: starterbase = self.highBase
			else: starterbase = self.textBase
			#title = (tdict.get('new_post') and self.newBase or self.textBase) % title
			titleDisplay = title
			if self.searchRE: titleDisplay = self.highlightTerms(titleDisplay)
			item = xbmcgui.ListItem(label=starterbase % starter,label2=titleDisplay)
			if tdict.get('new_post'): item.setProperty('unread','unread')
			item.setInfo('video',{"Genre":sticky})
			item.setInfo('video',{"Director":starter == self.me and 'me' or ''})
			item.setInfo('video',{"Studio":last == self.me and 'me' or ''})
			item.setProperty("id",unicode(tid))
			item.setProperty("fid",unicode(fid))
			item.setProperty("lastposter",last)
			if last:
				last = self.desc_base % last
				short = tdict.get('short_content','')
				if short: last += '[CR]' + re.sub('<[^>]+?>','',texttransform.convertHTMLCodes(short))[:100]
			else:
				last = re.sub('<[^>]+?>','',texttransform.convertHTMLCodes(tdict.get('short_content','')))
			if self.searchRE: last = self.highlightTerms(last)
			item.setProperty("last",last)
			
			item.setProperty("lastid",tdict.get('lastid',''))
			item.setProperty('title',title)
			item.setProperty('announcement',unicode(tdict.get('announcement','')))
			item.setProperty('reply_count',reply_count)
			item.setProperty('subscribed',tdict.get('subscribed') and 'subscribed' or '')
			self.getControl(120).addItem(item)
		return True
			
	def addForums(self,forums):
		if not forums: return False
		for f in forums:
			if hasattr(f,'groupdict'):
				fdict = f.groupdict()
			else:
				fdict = f
			fid = fdict.get('forumid','')
			title = fdict.get('title',__language__(30050))
			desc = fdict.get('description') or __language__(30172)
			text = self.textBase
			title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?')
			item = xbmcgui.ListItem(label=self.textBase % __language__(30164),label2=text % title)
			item.setInfo('video',{"Genre":'is_forum'})
			item.setProperty("last",self.forum_desc_base % texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',FB.MC.brFilter.sub(' ',desc))))
			item.setProperty("title",title)
			item.setProperty("id",fid)
			item.setProperty("fid",fid)
			item.setProperty("is_forum",'True')
			if fdict.get('new_post'): item.setProperty('unread','unread')
			item.setProperty('subscribed',fdict.get('subscribed') and 'subscribed' or '')
			self.getControl(120).addItem(item)
		return True
				
	def openRepliesWindow(self):
		item = self.getControl(120).getSelectedItem()
		item.setProperty('unread','')
		fid = item.getProperty('fid') or self.fid
		topic = item.getProperty('title')
		if item.getProperty('is_forum') == 'True':
			dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",fid=fid,topic=topic,parent=self.parent,item=item)
			#self.fid = fid
			#self.topic = topic
			#self.setTheme()
			#self.fillThreadList()
		else:
			dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,fid=fid,topic=topic,item=item,search_re=self.searchRE,parent=self)

	def onFocus( self, controlId ):
		self.controlId = controlId
	
	def onClick( self, controlID ):
		if controlID == 120:
			if not self.empty: self.stopThread()
			self.openRepliesWindow()
		elif controlID == 106:
			self.stopThread()
			return
		if self.empty: self.fillThreadList()
		PageWindow.onClick(self,controlID)
	
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		PageWindow.onAction(self,action)
		
	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu('Options',with_splash=True)
		try:
			if item:
				if item.getProperty("is_forum") == 'True':
					if FB.isForumSubscribed(item.getProperty('id'),item.getProperty('subscribed')):
						if FB.canUnSubscribeForum(item.getProperty('id')): d.addItem('unsubscribeforum', __language__(30242))
					else:
						if FB.canSubscribeForum(item.getProperty('id')): d.addItem('subscribeforum', __language__(30243))
				else:
					if FB.isThreadSubscribed(item.getProperty('id'),item.getProperty('subscribed')):
						if FB.canUnSubscribeThread(item.getProperty('id')): d.addItem('unsubscribe', __language__(30240))
					else:
						if FB.canSubscribeThread(item.getProperty('id')): d.addItem('subscribe', __language__(30236))
				if self.fid != 'subscriptions':
					if self.forumItem:
						if FB.isForumSubscribed(self.forumItem.getProperty('id'),self.forumItem.getProperty('subscribed')):
							if FB.canUnSubscribeForum(self.forumItem.getProperty('id')): d.addItem('unsubscribecurrentforum', __language__(30242) + ': ' + self.forumItem.getLabel()[:25])
						else:
							if FB.canSubscribeForum(self.forumItem.getProperty('id')): d.addItem('subscribecurrentforum', __language__(30243) + ': ' + self.forumItem.getLabel()[:25])
					if FB.canCreateThread(item.getProperty('id')):
						d.addItem('createthread',__language__(30252))
				if FB.canSearchAdvanced():
					d.addItem('search','Search [B][I]%s[/I][/B]' % item.getProperty('title')[:30])
			d.addItem('help',__language__(30244))
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
				searchPosts(self,item.getProperty('id'))
			else:
				searchThreads(self.parent,item.getProperty('id'))
		elif result == 'createthread':
			self.createThread()
		elif result == 'help':
			if self.fid == 'subscriptions':
				dialogs.showHelp('subscriptions')
			else:
				dialogs.showHelp('threads')
	
	def createThread(self):
		pm = openPostDialog(fid=self.fid,donotpost=True)
		if pm:
			splash = dialogs.showActivitySplash('Creating Thread...')
			try:
				result = FB.createThread(self.fid,pm.title,pm.message)
				if result == True:
					dialogs.showMessage('Success','Thread created: ','\n',pm.title,success=True)
					self.fillThreadList()
				else:
					dialogs.showMessage('Failed','Failed create thread:','\n',str(result),success=False)
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
class ForumsWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		BaseWindow.__init__( self, *args, **kwargs )
		#FB.setLogin(self.getUsername(),self.getPassword(),always=__addon__.getSetting('always_login') == 'true')
		self.parent = self
		self.empty = True
		self.setAsMain()
		self.started = False
		self.headerIsDark = False
	
	def getUsername(self):
		data = loadForumSettings(FB.getForumID())
		if data and data['username']: return data['username']
		return ''
		
	def getPassword(self):
		data = loadForumSettings(FB.getForumID())
		if data and data['password']: return data['password']
		return ''
		
	def getNotify(self):
		data = loadForumSettings(FB.getForumID())
		if data: return data['notify']
		return False
	
	def hasLogin(self):
		return self.getUsername() != '' and self.getPassword() != ''
		
	def onInit(self):
		BaseWindow.onInit(self)
		self.getControl(112).setVisible(False)
		try:
			self.setLoggedIn() #So every time we return to the window we check
			if self.started: return
			self.setVersion()
			self.setStopControl(self.getControl(105))
			self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
			self.started = True
			self.getControl(105).setVisible(True)
			self.setFocusId(105)
			self.startGetForumBrowser()
		except:
			self.setStopControl(self.getControl(105)) #In case the error happens before we do this
			self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
			self.getControl(105).setVisible(False)
			self.endProgress() #resets the status message to the forum name
			self.setFocusId(202)
			raise
		
	def startGetForumBrowser(self,forum=None,url=None):
		self.getControl(201).setEnabled(False)
		self.getControl(203).setEnabled(False)
		self.getControl(204).setEnabled(False)
		t = self.getThread(getForumBrowser,finishedCallback=self.endGetForumBrowser,errorCallback=self.errorCallback,name='GETFORUMBROWSER')
		t.setArgs(forum=forum,url=url,donecallback=t.finishedCallback)
		t.start()
		
	def endGetForumBrowser(self,fb):
		global FB
		FB = fb
		self.setTheme()
		self.getControl(112).setVisible(False)
		self.resetForum()
		self.fillForumList(True)
		__addon__.setSetting('last_forum',FB.getForumID())
		
	def setVersion(self):
		self.getControl(109).setLabel('v' + __version__)
		
	def setTheme(self):
		hc = FB.theme.get('header_color')
		if hc and hc.upper() != 'FFFFFF':
			self.headerIsDark = self.hexColorIsDark(hc)
			self.headerTextFormat = '[B]%s[/B]'
			if self.headerIsDark: self.headerTextFormat = '[COLOR FFFFFFFF][B]%s[/B][/COLOR]'
			hc = 'FF' + hc.upper()
			self.getControl(100).setColorDiffuse(hc)
			self.getControl(251).setVisible(False)
		else:
			self.getControl(100).setColorDiffuse('FF888888')
			self.getControl(251).setVisible(True)
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
		self.getControl(103).setLabel(self.headerTextFormat % __language__(30170))
		self.getControl(104).setLabel(self.headerTextFormat % FB.getDisplayName())
		
	def errorCallback(self,error):
		dialogs.showMessage(__language__(30050),__language__(30171),error.message,error=True)
		self.setFocusId(202)
		self.endProgress()
	
	def fillForumList(self,first=False):
		if not FB: return
		self.setLabels()
		if not FB.guestOK() and not self.hasLogin():
			yes = xbmcgui.Dialog().yesno('Login Required','This forum does not allow guest access.','Login required.','Set login info now?')
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
		if first and __addon__.getSetting('auto_thread_subscriptions_window') == 'true':
			if self.hasLogin() and FB.hasSubscriptions():
				FB.getForums(callback=self.setProgress,donecallback=self.doFillForumList)
				self.openSubscriptionsWindow()
				return
		t = self.getThread(FB.getForums,finishedCallback=self.doFillForumList,errorCallback=self.errorCallback,name='FORUMS')
		t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def doFillForumList(self,data):
		self.endProgress()
		self.setLogo(data.getExtra('logo'))
		if not data:
			self.setFocusId(202)
			if data.error == 'CANCEL': return
			dialogs.showMessage(__language__(30050),__language__(30171),__language__(30053),'[CR]'+data.error,success=False)
			return
		self.empty = True
		
		try:
			#xbmcgui.lock()
			self.getControl(120).reset()
			self.setPMCounts(data.getExtra('pm_counts'))
			
			for f in data.data:
				self.empty = False
				if hasattr(f,'groupdict'):
					fdict = f.groupdict()
				else:
					fdict = f
				fid = fdict.get('forumid','')
				title = fdict.get('title',__language__(30050))
				desc = fdict.get('description') or __language__(30172)
				sub = fdict.get('subforum')
				if sub: desc = __language__(30173)
				title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?')
				item = xbmcgui.ListItem(label=title)
				item.setInfo('video',{"Genre":sub and 'sub' or ''})
				item.setProperty("description",texttransform.convertHTMLCodes(FB.MC.tagFilter.sub('',FB.MC.brFilter.sub(' ',desc))))
				item.setProperty("topic",title)
				item.setProperty("id",unicode(fid))
				item.setProperty("link",fdict.get('link',''))
				if fdict.get('new_post'): item.setProperty('unread','unread')
				item.setProperty('subscribed',fdict.get('subscribed') and 'subscribed' or '')
				self.getControl(120).addItem(item)
				self.setFocusId(120)
		except:
			#xbmcgui.unlock()
			ERROR('FILL FORUMS ERROR')
			dialogs.showMessage(__language__(30050),__language__(30174),error=True)
			self.setFocusId(202)
		if self.empty: self.setFocusId(202)
		#xbmcgui.unlock()
		self.setLoggedIn()
		if not FB.guestOK() and not FB.isLoggedIn():
			yes = xbmcgui.Dialog().yesno('Login Required','This forum does not allow guest access.','Login required.','Set login info now?')
			if yes:
				setLogins()
				self.resetForum()
				self.fillForumList()
		
	def setLogoFromFile(self):
		logopath = getCurrentLogo()
		if not logopath:
			LOG('NO LOGO WHEN SETTING LOGO')
			return
		return self.getControl(250).setImage(logopath)
			
	def setLogo(self,logo):
		if not logo: return
		if getSetting('save_logos',False):
			exists, logopath = getCachedLogo(logo,FB.getForumID())
			if exists:
				logo = logopath
			else:
				
				try:
					open(logopath,'wb').write(urllib2.urlopen(logo).read())
					logo = logopath
				except:
					LOG('ERROR: Could not save logo for: ' + FB.getForumID())
		if logo: self.getControl(250).setImage(logo)
		if 'ForumBrowser' in FB.browserType:
			image = 'forum-browser-logo-128.png'
		else:
			image = 'forum-browser-%s.png' % FB.browserType or ''
		self.getControl(249).setImage(image)
			
	def setPMCounts(self,pm_counts=False):
		if not FB: return
		if pm_counts == False: return
		disp = ''
		if not pm_counts: pm_counts = FB.getPMCounts()
		if pm_counts: disp = ' (%s/%s)' % (pm_counts.get('unread','?'),pm_counts.get('total','?'))
		self.getControl(203).setLabel(__language__(3009) + disp)
		self.setLoggedIn()
		
	def openPMWindow(self):
		dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,tid='private_messages',topic=__language__(30176),parent=self)
		self.setPMCounts(FB.getPMCounts())
	
	def openThreadsWindow(self):
		item = self.getControl(120).getSelectedItem()
		if not item: return False
		link = item.getProperty('link')
		if link:
			return self.openLink(link)
		fid = item.getProperty('id')
		topic = item.getProperty('topic')
		dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",fid=fid,topic=topic,parent=self,item=item)
		self.setPMCounts(FB.getPMCounts())
		return True
		
	def openLink(self,link):
		LOG('Forum is a link. Opening URL: ' + link)
		webviewer.getWebResult(link,dialog=True,browser=hasattr(FB,'browser') and FB.browser)
	
	def openSubscriptionsWindow(self):
		fid = 'subscriptions'
		topic = __language__(30175)
		dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",fid=fid,topic=topic,parent=self)
		self.setPMCounts(FB.getPMCounts())
	
	def showOnlineUsers(self):
		s = dialogs.showActivitySplash('Getting List')
		try:
			users = FB.getOnlineUsers()
		finally:
			s.close()
		if isinstance(users,str):
			dialogs.showMessage('Not Available',users,success=False)
			return
		users.sort(key=lambda u: u['user'].lower())
		d = dialogs.OptionsChoiceMenu('Online Users')
		d.setContextCallback(self.showOnlineContext)
		for u in users:
			d.addItem(u.get('userid'),u.get('user'),u.get('avatar') or 'forum-browser-avatar-none.png',u.get('status'))
		d.getResult(close_on_context=False)
		
	def showOnlineContext(self,menu,item):
		d = dialogs.ChoiceMenu('Options')
		if FB.canPrivateMessage(): d.addItem('pm',__language__(30253) % item.get('disp'))
		if FB.canSearchAdvanced(): d.addItem('search','Search Posts Of %s' % item.get('disp'))
		if FB.canGetUserInfo(): d.addItem('info','View User Info')
		result = d.getResult()
		if not result: return
		if result == 'pm':
			menu.close()
			openPostDialog(tid='private_messages',to=item.get('disp'))
		elif result == 'search':
			menu.close()
			searchUser(self,item.get('id'))
		elif result == 'info':
			self.showUserInfo(item.get('id'),item.get('disp'))

	def showUserInfo(self,uid,uname):
		s = dialogs.showActivitySplash('Getting Info')
		try:
			user = FB.getUserInfo(uid,uname)
			if not user: return
			out = '[B]Name:[/B] [COLOR FF550000]' + user.name + '[/COLOR]\n'
			out += '[B]Status:[/B] [COLOR FF550000]' + user.status + '[/COLOR]\n'
			out += '[B]Post Count:[/B] [COLOR FF550000]' + str(user.postCount) + '[/COLOR]\n'
			out += '[B]Join Date:[/B] [COLOR FF550000]' + user.joinDate + '[/COLOR]\n'
			if user.activity: out += '[B]Current Activity:[/B] [COLOR FF550000]' + user.activity + '[/COLOR]\n'
			if user.lastActivityDate: out += '[B]Last Activity Date:[/B] [COLOR FF550000]' + user.lastActivityDate + '[/COLOR]\n'
			for k,v in user.extras.items():
				out += '[B]' + k.title() + ':[/B] [COLOR FF550000]' + v + '[/COLOR]\n'
			dialogs.showMessage('Info',out,scroll=True)
		finally:
			s.close()
		
	def changeForum(self,forum=None):
		if not forum: forum = askForum()
		if not forum: return False
		url = None
		self.stopThread()
		fid = 'Unknown'
		if FB: fid = FB.getForumID()
		LOG('------------------ CHANGING FORUM FROM: %s TO: %s' % (fid,forum))
		self.startGetForumBrowser(forum,url=url)
		return True

	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if controlID == 200:
			self.stopThread()
			self.openSettings()
		elif controlID == 201:
			self.stopThread()
			self.openSubscriptionsWindow()
		elif controlID == 203:
			self.stopThread()
			self.openPMWindow()
		elif controlID == 202:
			return self.openForumsManager()
		elif controlID == 205:
			searchPosts(self)
		elif controlID == 206:
			searchThreads(self)
		elif controlID == 207:
			searchUser(self)
		elif controlID == 120:
			if not self.empty: self.stopThread()
			self.openThreadsWindow()
		elif controlID == 105:
			self.stopThread()
			self.setFocusId(202)
			return
		if BaseWindow.onClick(self, controlID): return
		if self.empty: self.fillForumList()
	
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			if not self.preClose(): return
		BaseWindow.onAction(self,action)
	
	def openForumsManager(self):
		forumsManager(self,size='manage',forumID=FB and FB.getForumID() or None)
		if not FB: return
		forumID = FB.getForumID()
		fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
		logo = fdata.urls.get('logo','')
		self.setLogo(logo)
		
		hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
		self.getControl(100).setColorDiffuse(hc.upper())
		
	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		d = dialogs.ChoiceMenu('Options',with_splash=True)
		try:
			if FB:
				if item:
					fid = item.getProperty('id')
					if FB.isForumSubscribed(fid,item.getProperty('subscribed')):
						if FB.canUnSubscribeForum(fid): d.addItem('unsubscribecurrentforum', __language__(30242))
					else:
						if FB.canSubscribeForum(fid): d.addItem('subscribecurrentforum', __language__(30243))
					if FB.canSearchAdvanced():
						d.addItem('search','Search [B][I]%s[/I][/B]' % item.getProperty('topic')[:30])
				if FB.canGetOnlineUsers():
					d.addItem('online','View Online Users')
				d.addItem('foruminfo','View Forum Info')
			d.addItem('refresh',__language__(30054))
			d.addItem('help',__language__(30244))
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
			out += u'[B]%s[/B]: [COLOR FF550000]%s[/COLOR][CR]' % (k.replace('_',' ').title(),v)
		dialogs.showMessage('Forum Info',out,scroll=True)
				
	def preClose(self):
		if not __addon__.getSetting('ask_close_on_exit') == 'true': return True
		if self.closed: return True
		return xbmcgui.Dialog().yesno('Really Exit?','Really exit?')
		
	def resetForum(self,hidelogo=True):
		if not FB: return
		FB.setLogin(self.getUsername(),self.getPassword(),always=__addon__.getSetting('always_login') == 'true',rules=loadForumSettings(FB.getForumID(),get_rules=True))
		self.setButtons()
		if hidelogo: self.getControl(250).setImage('')
		__addon__.setSetting('last_forum',FB.getForumID())
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
		self.getControl(204).setEnabled(loggedIn and FB.canSearch())
		self.getControl(205).setEnabled(loggedIn and FB.canSearchPosts())
		self.getControl(206).setEnabled(loggedIn and FB.canSearchThreads())
		
	def openSettings(self):
		#if not FB: return
		oldLogin = FB and self.getUsername() + self.getPassword() or ''
		doSettings(self)
		newLogin = FB and self.getUsername() + self.getPassword() or ''
		if not oldLogin == newLogin:
			self.resetForum(False)
			self.setPMCounts()
		self.setLoggedIn()
		self.resetForum(False)
		skin = SKINS[getSetting('skin',0)]
		if skin != THEME:
			dialogs.showMessage('Skin Changed','Skin changed. Restart Forum Browser to apply.')
		forumbrowser.ForumPost.hideSignature = getSetting('hide_signatures',False)

# Functions -------------------------------------------------------------------------------------------------------------------------------------------
def appendSettingList(key,value,limit=0):
	slist = getSetting(key,[])
	if value in slist: slist.remove(value)
	slist.append(value)
	if limit: slist = slist[-limit:]
	setSetting(key,slist)
	
def getSearchDefault(setting,default='',with_global=True,heading='Search Options',new='New Search',extra=None):
	if not getSetting('show_search_history',True): return default
	slist = getSetting(setting,[])
	slistDisplay = slist[:]
	if with_global:
		glist = getSetting('last_search',[])
		for g in glist:
			if not g in slist:
				slistDisplay.insert(0,'[COLOR FFAAAA00]%s[/COLOR]' % g)
				slist.insert(0,g)
	if slist:
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
		
def searchPosts(parent,tid=None):
	default = getSearchDefault('last_post_search')
	if default == None: return
	terms = dialogs.doKeyboard('Enter Search Terms',default)
	if not terms: return
	appendSettingList('last_post_search',terms,10)
	appendSettingList('last_search',terms,10)
	dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,search_terms=terms,topic='Post Search Results',tid=tid,parent=parent)
	
def searchThreads(parent,fid=None):
	default = getSearchDefault('last_thread_search')
	if default == None: return
	terms = dialogs.doKeyboard('Enter Search Terms',default)
	if not terms: return
	appendSettingList('last_thread_search',terms,10)
	appendSettingList('last_search',terms,10)
	dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",search_terms=terms,topic='Thread Search Results',fid=fid,parent=parent)

def searchUser(parent,uid=None):
	uname = None
	if not uid:
		default = getSearchDefault('last_search_user',with_global=False,heading='User Options',new='New User')
		if default == None: return
		if default:
			uname = default
		else:
			uname = dialogs.doKeyboard('Enter Name Of User To Search',default)
		if not uname: return
		appendSettingList('last_search_user',uname,10)
	extra = None
	ct = FB.canGetUserThreads()
	if ct:
		if not extra: extra = []
		extra.append(('@!RECENTTHREADS!@','Recent Threads'))
	ct = FB.canGetUserPosts()
	if ct:
		if not extra: extra = []
		extra.append(('@!RECENT!@','Recent Posts'))
		
	default = getSearchDefault('last_user_search',extra=extra)
	if default == None: return
	topic = 'Post Search Results'
	if default == '@!RECENT!@':
		terms = default
		topic = 'Recent Posts'
	elif default == '@!RECENTTHREADS!@':
		terms = default
		dialogs.openWindow(ThreadsWindow,"script-forumbrowser-threads.xml",search_terms=terms,search_name=uname,topic='Recent Threads',parent=parent)
		return 
	else:
		terms = dialogs.doKeyboard('Enter Search Terms',default)
		if not terms: return
		appendSettingList('last_user_search',terms,10)
		appendSettingList('last_search',terms,10)
	dialogs.openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,search_terms=terms,topic=topic,uid=uid,search_name=uname,parent=parent)

def getCachedLogo(logo,forumID,clear=False):
	root, ext = os.path.splitext(logo) #@UnusedVariable
	logopath = os.path.join(CACHE_PATH,forumID + ext or '.jpg')
	if not ext:
		if not os.path.exists(logopath): logopath = os.path.join(CACHE_PATH,forumID + '.png')
		if not os.path.exists(logopath): logopath = os.path.join(CACHE_PATH,forumID + '.gif')
	if os.path.exists(logopath):
		if clear: os.remove(logopath)
		return True, logopath
	return False, logopath

def getForumSetting(forumID,key,default=None):
	data = loadForumSettings(forumID)
	return _processSetting(data.get(key),default)

def loadForumSettings(forumID,get_rules=False,get_both=False):
	fsPath = os.path.join(FORUMS_SETTINGS_PATH,forumID)
	if not os.path.exists(fsPath):
		if get_both:
			return {},{}
		else:
			return {}
	fsFile = open(fsPath,'r')
	lines = fsFile.read()
	fsFile.close()
	try:
		ret = {}
		rules = {}
		mode = 'settings'
		for l in lines.splitlines():
			if l.startswith('[rules]'):
				if not get_rules and not get_both: break
				mode = 'rules'
			else:
				k,v = l.split('=',1)
				if mode == 'rules':
					rules[k] = v.strip()
				else:
					ret[k] = v.strip()
	except:
		ERROR('Failed to get settings for forum: %s' % forumID)
		if get_both:
			return {},{}
		else:
			return {}
		
	if get_rules:
		return rules
	
	ret['username'] = ret.get('username','')
	ret['password'] = passmanager.decryptPassword(ret['username'] or '?', ret.get('password',''))
	ret['notify'] = ret.get('notify') == 'True'
		
	if get_both:
		return ret,rules
	else:
		return ret

def saveForumSettings(forumID,**kwargs):
	username=kwargs.pop('username',None)
	password=kwargs.pop('password',None)
	notify=kwargs.pop('notify',None)
	rules=kwargs.pop('rules',None)
	
	data, rules_data = loadForumSettings(forumID,get_both=True) or ({},{})
	#data.update(kwargs)
	if rules: rules_data.update(rules)
	if data: data.update(kwargs)
	
	if notify == None: data['notify'] = data.get('notify')  or False
	else: data['notify'] = notify
	
	if username == None: data['username'] = data.get('username') or ''
	else: data['username'] = username
	
	if password == None: data['password'] = data.get('password') or ''
	else: data['password'] = password
	
	try:
		password = passmanager.encryptPassword(data['username'] or '?', data['password'])
		data['password'] = password
		out = []
		for k,v in data.items():
			out.append('%s=%s' % (k,v))
		if rules_data:
			out.append('[rules]')
			for k,v in rules_data.items():
				if v != None: out.append('%s=%s' % (k,v))
		fsFile = open(os.path.join(FORUMS_SETTINGS_PATH,forumID),'w')
		#fsFile.write('username=%s\npassword=%s\nnotify=%s' % (data['username'],password,data['notify']))
		fsFile.write('\n'.join(out))
		fsFile.close()
		return True
	except:
		ERROR('Failed to save forum settings for: %s' % forumID)
		return False

def addParserRule(forumID,key,value):
	if key.startswith('extra.'):
		saveForumSettings(rules={key:value})
	else:
		rules = loadForumSettings(get_rules=True)
		if key == 'head':
			vallist = rules.get('head') and rules['head'].split(';&;') or []
		elif key == 'tail':
			vallist = rules.get('tail') and rules['tail'].split(';&;') or []
		if not value in vallist: vallist.append(value)
		saveForumSettings(rules={key:';&;'.join(vallist)})

def removeParserRule(forumID,key,value=None):
	if key.startswith('extra.'):
		saveForumSettings(rules={key:None})
	else:
		rules = loadForumSettings(get_rules=True)
		if key == 'head':
			vallist = rules.get('head') and rules['head'].split(';&;') or []
		elif key == 'tail':
			vallist = rules.get('tail') and rules['tail'].split(';&;') or []
		if value in vallist: vallist.pop(vallist.index(value))
		saveForumSettings(rules={key:';&;'.join(vallist)})
		
def listForumSettings():
	return os.listdir(FORUMS_SETTINGS_PATH)

def getForumPath(forumID,just_path=False):
	path = os.path.join(FORUMS_PATH,forumID)
	if os.path.exists(path):
		if just_path: return FORUMS_PATH
		return path
	path = os.path.join(FORUMS_STATIC_PATH,forumID)
	if os.path.exists(path):
		if just_path: return FORUMS_STATIC_PATH
		return path
	return None
	
def fidSortFunction(fid):
	if fid[:3] in ['TT.','FR.','GB.']: return fid[3:]
	return fid

def askForum(just_added=False,just_favs=False,caption='Choose Forum',forumID=None,hide_extra=False):
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
			path = getForumPath(f,just_path=True)
			if not path: continue
			if not os.path.isfile(os.path.join(path,f)): continue
			fdata = forumbrowser.ForumData(f,path)
			name = fdata.name
			desc = fdata.description
			logo = fdata.urls.get('logo','')
			exists, logopath = getCachedLogo(logo,f)
			if exists: logo = logopath
			hc = 'FF' + fdata.theme.get('header_color','FFFFFF')
			desc = '[B]Description[/B]: [COLOR FFFF9999]' + (desc or 'None') + '[/COLOR]'
			interface = ''
			if f.startswith('TT.'):
				#desc += '\n\n[B]Forum Interface[/B]: [COLOR FFFF9999]Tapatalk[/COLOR]'
				interface = 'TT'
			elif f.startswith('FR.'):
				#desc += '\n\n[B]Forum Interface[/B]: [COLOR FFFF9999]Forumrunner[/COLOR]'
				interface = 'FR'
			elif f.startswith('GB.'):
				#desc += '\n\n[B]Forum Interface[/B]: [COLOR FFFF9999]Parser Browser[/COLOR]'
				interface = 'GBalt'
			menu.addItem(f, name,logo,desc,bgcolor=hc,interface=interface)

	#if getSetting('experimental',False) and not just_added and not just_favs and not forumID and not hide_extra:
	#	menu.addItem('experimental.general','Experimental General Browser','forum-browser-logo-128.png','')
	forum = menu.getResult('script-forumbrowser-forum-select.xml',select=forumID)
	return forum

def setLogins(force_ask=False,forumID=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID or force_ask: forumID = askForum(forumID=forumID)
	if not forumID: return
	data = loadForumSettings(forumID)
	user = ''
	if data: user = data.get('username','')
	user = dialogs.doKeyboard(__language__(30201),user)
	if user is None: return
	password = ''
	if data: password = data.get('password','')
	password = dialogs.doKeyboard(__language__(30202),password,True)
	if password is None: return
	saveForumSettings(forumID,username=user,password=password)
	if not user and not password:
		dialogs.showMessage('Login Cleared','Username and password cleared.')
	else:
		dialogs.showMessage('Login Set','Username and password set.')
		
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
	saveForumSettings(forumID,rules={'login_url':url})
	
def browseWebURL(url):
	(url,html) = webviewer.getWebResult(url,dialog=True) #@UnusedVariable
	if not url: return None
	yes = xbmcgui.Dialog().yesno('Use URL?',str(url),'','Use this URL?')
	if not yes: return None
	return url
	
###########################################################################################
## - Version Conversion
###########################################################################################

def updateOldVersion():
	lastVersion = getSetting('last_version') or '0.0.0'
	if StrictVersion(__version__) <= StrictVersion(lastVersion): return False
	setSetting('last_version',__version__)
	LOG('NEW VERSION (OLD: %s): Converting any old formats...' % lastVersion)
	if StrictVersion(lastVersion) < StrictVersion('1.1.4'):
		convertForumSettings_1_1_4()
	if StrictVersion(lastVersion) < StrictVersion('1.3.5') and not lastVersion == '0.0.0':
		if getSetting('use_skin_mods',False):
			dialogs.showMessage('Update','Skin modifications need to be updated. Click OK to continue.')
			mods.installSkinMods(update=True)
	if lastVersion == '0.0.0': doFirstRun()
	return True

def doFirstRun():
	LOG('EXECUTING FIRST RUN FUNCTIONS')
	xbmc_org = os.path.join(FORUMS_PATH,'TT.xbmc.org')
	if not os.path.exists(xbmc_org):
		local = os.path.join(FORUMS_STATIC_PATH,'TT.xbmc.org')
		if os.path.exists(local): open(xbmc_org,'w').write(open(local,'r').read())

def convertForumSettings_1_1_4():
	forums = os.listdir(FORUMS_PATH) + os.listdir(FORUMS_STATIC_PATH)
	for f in forums:
		username = getSetting('login_user_' + f.replace('.','_'))
		key = 'login_pass_' + f.replace('.','_')
		password = passmanager.getPassword(key, username)
		if username or password:
			LOG('CONVERTING FORUM SETTINGS: %s' % f)
			saveForumSettings(f,username=username,password=password)
			setSetting('login_user_' + f.replace('.','_'),'')
			setSetting('login_pass_' + f.replace('.','_'),'')

## - Version Conversion End ###############################################################

def toggleNotify(forumID=None):
	notify = True
	if not forumID and FB: forumID = FB.getForumID()
	if not forumID: return None
	data = loadForumSettings(forumID)
	if data: notify = not data['notify']
	saveForumSettings(forumID,notify=notify)
	return notify
		
def doSettings(window=None):
	w = dialogs.openWindow(xbmcgui.WindowXMLDialog,'script-forumbrowser-overlay.xml',return_window=True,modal=False,theme='Default')
	try:
		__addon__.openSettings()
	finally:
		w.close()
		del w
	global DEBUG
	DEBUG = getSetting('debug',False)
	if FB: FB.MC.resetRegex()
	mods.checkForSkinMods()

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
	if not forumID: return
	returnRules = False
	if rules != None:
		returnRules = True
	else:
		rules = loadForumSettings(forumID,get_rules=True)
	choice = True
	while choice:
		menu = dialogs.OptionsChoiceMenu('Select Rule:')
		keys = rules.keys()
		keys.sort()
		for k in keys:
			v = rules[k]
			if k.startswith('extra.'):
				if v: menu.addItem(k,'[EXTRA] ' + k.split('.')[-1],display2=v)
			elif k == 'login_url':
				if v: menu.addItem(k,'Login Page',display2=texttransform.textwrap.fill(v,30))
			else:
				for i in v.split(';&;'):
					if i: menu.addItem(k + '.' + i,'[%s FILTER] ' % k.upper() + i)
		menu.addItem('add','[COLOR FFFFFF00]+ Add Rule[/COLOR]')
		menu.addItem('share','[COLOR FF00FFFF]Share->[/COLOR]',display2='Share rules to the Forum Browser online database')
		menu.addItem('save',returnRules and '[COLOR FF00FF00]Done[/COLOR]' or '[COLOR FF00FF00]<- Save[/COLOR]')
		choice = menu.getResult()
		if not choice: return
		if choice == 'save':
			for k in rules.keys():
				if not rules[k]: rules[k] = None
			if returnRules: return rules
			saveForumSettings(forumID,rules=rules)
			continue
		elif choice == 'share':
			shareForumRules(forumID,rules)
			continue
		elif choice == 'add':
			menu = dialogs.ChoiceMenu('Type:')
			menu.addItem('extra','User/Post Extra Info')
			menu.addItem('head','Head Filter')
			menu.addItem('tail','Tail Filter')
			rtype = menu.getResult()
			if not rtype: continue
			if rtype == 'extra':
				name = dialogs.doKeyboard('Enter Name:')
				if not name: continue
				default = ''
				if 'extra.' + name in rules: default = rules['extra.' + name]
				val = dialogs.doKeyboard('Enter Python Regular Expression:',default)
				if not val: continue
				rules['extra.' + name] = val
			else:
				val = dialogs.doKeyboard('Enter Phrase')
				if not val: continue
				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if not val in vallist:
					vallist.append(val)
					rules[rtype] = ';&;'.join(vallist)
			continue
		menu = dialogs.ChoiceMenu('Select')
		if not choice == 'login_url': menu.addItem('edit','Edit')
		menu.addItem('remove','Remove')
		choice2 = menu.getResult()
		if not choice2: continue
		if choice2 == 'remove':
			if choice.startswith('extra.') or choice == 'login_url':
				rules[choice] = None
			else:
				rtype, val = choice.split('.')
				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if val in vallist:
					vallist.pop(vallist.index(val))
					rules[rtype] = ';&;'.join(vallist)
		else:
			if choice.startswith('extra.') or choice == 'login_url':
				val = rules[choice]
#				if choice == 'login_url':
#					edit = dialogs.doKeyboard('Edit',val)
#				else:
				edit = dialogs.doKeyboard('Edit',val)
				if edit == None: continue
				rules[choice] = edit
			else:
				rtype, val = choice.split('.')
				edit = dialogs.doKeyboard('Edit',val)
				if edit == None: continue
				vallist = rules.get(rtype) and rules[rtype].split(';&;') or []
				if val in vallist:
					vallist.pop(vallist.index(val))
					vallist.append(edit)
					rules[rtype] = ';&;'.join(vallist)

def shareForumRules(forumID,rules):
	odb = forumbrowser.FBOnlineDatabase()
	odbrules = odb.getForumRules(forumID)
	if odbrules:
		out = []
		for k,v in odbrules.items():
			if k.startswith('extra.'):
				out.append('[EXTRA] ' + k.split('.',1)[-1] + ' = ' + v)
			elif k == 'head':
				out.append('[HEAD FILTERS] = ' + ', '.join(v.split(';&;')))
			elif k == 'tail':
				out.append('[TAIL FILTERS] = ' + ', '.join(v.split(';&;')))
		dialogs.showMessage('Current Rules','Rules already exist for this forum.\n\nRules:\n\n' + '[CR]'.join(out),scroll=True)
		yes = xbmcgui.Dialog().yesno('Overwrite?','Overwrite existing rules?')
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
	__addon__.setSetting('favorites','*:*'.join(favs))
	dialogs.showMessage('Added','Current forum added to favorites!')
	
def removeFavorite(forum=None):
	if not forum: forum = askForum(just_favs=True)
	if not forum: return
	favs = getFavorites()
	if not forum in favs: return
	favs.pop(favs.index(forum))
	__addon__.setSetting('favorites','*:*'.join(favs))
	dialogs.showMessage('Removed','Forum removed from favorites.')
	
def getFavorites():
	favs = __addon__.getSetting('favorites')
	if favs:
		favs = favs.split('*:*')
	else:
		favs = []
	return favs
	
def selectForumCategory(with_all=False):
	d = dialogs.ChoiceMenu('Select Category')
	if with_all:
		d.addItem('search','Search Database')
		d.addItem('all','Show All')
	for x in range(0,17):
		d.addItem(str(x), str(__language__(30500 + x)))
	return d.getResult()

def addForum(current=False):
	dialog = xbmcgui.DialogProgress()
	dialog.create('Add Forum')
	dialog.update(0,'Enter Name/Address')
	info = None
	user = None
	password=None
	try:
		if current:
			if not FB: return
			ftype = FB.prefix[:2]
			forum = FB.forum
			url = orig = FB._url
			url = tapatalk.testForum(url)
			if url: pageURL = url.split('/mobiquo/',1)[0]
			if not url:
				from forumbrowser import forumrunner
				url = forumrunner.testForum(orig)
			if url: pageURL = url.split('/forumrunner/',1)[0]
			if not url:
				dialogs.showMessage('Failed','Forum not found or not compatible',success=False)
				return
		else:
			forum = dialogs.doKeyboard('Enter forum URL')
			if forum == None: return
			forum = forum.lower()
			dialog.update(10,'Testing Forum: Tapatalk')
			url = tapatalk.testForum(forum)
			ftype = ''
			label = ''
			if url:
				ftype = 'TT'
				label = 'Tapatalk'
				pageURL = url.split('/mobiquo/',1)[0]
			else:
				dialog.update(13,'Testing Forum: Forumrunner')
				from forumbrowser import forumrunner #@Reimport
				url = forumrunner.testForum(forum)
				if url:
					ftype = 'FR'
					label = 'Forumrunner'
					pageURL = url.split('/forumrunner/',1)[0]
					
			if not url:
				dialog.update(16,'Testing Forum: Parser Browser')
				yes = xbmcgui.Dialog().yesno('Question...','Does this forum require a login?','Click "Yes" if you cannot view this forum','without already being a member.')
				if yes:
					user = dialogs.doKeyboard(__language__(30201))
					if user: password = dialogs.doKeyboard(__language__(30202),hidden=True)
				from forumbrowser import genericparserbrowser
				url,info,parser = genericparserbrowser.testForum(forum,user,password)
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
				dialogs.showMessage('Failed','Forum not found or not compatible',success=False)
				return
		
			dialogs.showMessage('Found','Forum %s found' % forum,'[CR]Type: ' + label,'[CR]'+ url,success=True)
			if ftype == 'GB':
				if parser.getForumTypeName().lower() == 'generic':
					dialogs.showInfo('parserbrowser-generic')
				else:
					dialogs.showInfo('parserbrowser-normal')
			forum = url.split('http://',1)[-1].split('/',1)[0]
			
		dialog.update(20,'Getting Description And Images')
		if not info: info = forumbrowser.HTMLPageInfo(pageURL)
		tmp_desc = info.description(info.title(''))
		tmp_desc = texttransform.convertHTMLCodes(tmp_desc).strip()
		images = info.images()
		dialog.update(30,'Enter Description')
		desc = dialogs.doKeyboard('Enter Description',default=tmp_desc)
		if not desc: desc = tmp_desc
		dialog.update(40,'Choose Logo')
		logo = chooseLogo(forum,images)
		LOG('Adding Forum: %s at URL: %s' % (forum,url))
		name = forum
		if name.startswith('www.'): name = name[4:]
		if name.startswith('forum.'): name = name[6:]
		if name.startswith('forums.'): name = name[7:]
		forumID = ftype + '.' + name
		saveForum(ftype,forumID,name,desc,url,logo)
		if user and password: saveForumSettings(forumID,username=user,password=password)
		dialog.update(60,'Add To Online Database')
		if not (not current and ftype == 'GB'): addForumToOnlineDatabase(name,url,desc,logo,ftype,dialog=dialog)
		return forumID
	finally:
		dialog.close()
	
def saveForum(ftype,forumID,name,desc,url,logo,header_color="FFFFFF"): #TODO: Do these all the same. What... was I crazy?
	if ftype == 'TT':
		open(os.path.join(FORUMS_PATH,forumID),'w').write('#%s\n#%s\nurl:tapatalk_server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))
	elif ftype == 'FR':
		open(os.path.join(FORUMS_PATH,forumID),'w').write('#%s\n#%s\nurl:forumrunner_server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))
	else:
		open(os.path.join(FORUMS_PATH,forumID),'w').write('#%s\n#%s\nurl:server=%s\nurl:logo=%s\ntheme:header_color=%s' % (name,desc,url,logo,header_color))
	
def addForumFromOnline(stay_open_on_select=False):
	odb = forumbrowser.FBOnlineDatabase()
	res = True
	added = False
	while res:
		res = selectForumCategory(with_all=True)
		if not res: return
		cat = res
		terms = None
		if cat == 'all': cat = None
		if cat == 'search':
			terms = dialogs.doKeyboard('Enter Search Terms')
			if not terms: continue
			cat = None
		splash = dialogs.showActivitySplash('Getting Forums List')
		try:
			flist = odb.getForumList(cat,terms)
		finally:
			splash.close()
		if not flist:
			dialogs.showMessage('No Forums','No forums in that category.')
			continue
		if cat and cat.isdigit():
			caption = '[COLOR FF9999FF]'+str(__language__(30500 + int(cat)))+'[/COLOR]'
		else:
			caption = '[COLOR FF9999FF]All[/COLOR]'
		menu = dialogs.ImageChoiceMenu(caption)
		for f in flist:
			interface = f.get('type')
			rf=ra=''
			if interface == 'GB':
				rf = {'1':'FFFF0000','2':'FFFFFF00','3':'FF00FF00'}.get(f.get('rating_function'),'')
				ra = {'1':'FFFF0000','2':'FFFFFF00','3':'FF00FF00'}.get(f.get('rating_accuracy'),'')
			desc = f.get('desc','None') or 'None'
			desc = '[B]Category[/B]: [COLOR FFFF9999]' + str(__language__(30500 + f.get('cat',0))) + '[/COLOR][CR][CR][B]Description[/B]: [COLOR FFFF9999]' + desc + '[/COLOR]'
			bgcolor = formatHexColorToARGB(f.get('header_color','FFFFFF'))
			menu.addItem(f, f.get('name'), f.get('logo'), desc,bgcolor=bgcolor,interface=interface,function=rf,accuracy=ra)
		f = True
		while f:
			f = menu.getResult('script-forumbrowser-forum-select.xml',filtering=True)
			if f:
				forumID = doAddForumFromOnline(f,odb)
				added = forumID
				if not stay_open_on_select: return added
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
	old_rules = loadForumSettings(forumID,get_rules=True)
	if rules and not old_rules: saveForumSettings(forumID,rules=rules)
	dialogs.showMessage('Added','Forum added: ' + f['name'])
	return forumID
	
def setRulesODB(forumID,rules):
	odb = forumbrowser.FBOnlineDatabase()
	out = []
	for k,v in rules.items():
		out.append(k + '=' + v)
	result = str(odb.setRules(forumID,'\n'.join(out)))
	LOG('Updating ODB Rules: ' + result)
	if result == '1':
		dialogs.showMessage('Done','Online database forum rules updated.',success=True)
	else:
		dialogs.showMessage('Failed','Failed to update the online database.',error=True)
	
def addCurrentForumToOnlineDatabase(forumID=None):
	if not forumID:
		if FB: forumID = FB.getForumID()
	if not forumID: return
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	url = fdata.urls.get('tapatalk_server',fdata.urls.get('forumrunner_server',fdata.urls.get('server',FB and FB._url or '')))
	if not url: raise Exception('No URL')
	addForumToOnlineDatabase(fdata.name,url,fdata.description,fdata.urls.get('logo'),forumID[:2],header_color=fdata.theme.get('header_color','FFFFFF'))
	
def addForumToOnlineDatabase(name,url,desc,logo,ftype,header_color='FFFFFF',dialog=None):
	if not xbmcgui.Dialog().yesno('Add To Database?','Share to the Forum Browser','online database?'): return
	LOG('Adding Forum To Online Database: %s at URL: %s' % (name,url))
	frating = arating = '0'
	if ftype == 'GB':
		frating,arating = askForumRating()
		if not frating:
			dialogs.showMessage('Failed','Forum must be rated in order to be added to the online database.',success=False)
			return
		
	cat = selectForumCategory() or '0'
	splash = None
	if dialog:
		dialog.update(80,'Saving To Database')
	else:
		splash = dialogs.showActivitySplash('Saving TO ODB')
		
	try:
		odb = forumbrowser.FBOnlineDatabase()
	finally:
		if splash: splash.close()
		
	msg = odb.addForum(name, url, logo, desc, ftype, cat, rating_function=frating, rating_accuracy=arating, header_color=header_color)
	if msg == 'OK':
		dialogs.showMessage('Added','Forum added successfully',success=True)
	elif msg =='EXISTS':
		dialogs.showMessage('Updated','Forum entry exists. Updated successfully',success=True)
	else:
		dialogs.showMessage('Not Added','Forum not added:',str(msg),success=False)
		LOG('Forum Not Added: ' + str(msg))
	
def askForumRating():
	d = dialogs.ChoiceMenu('Function Rating')
	d.addItem('3','Fully Functional')
	d.addItem('2','Partially Functional')
	d.addItem('1','Not Functional')
	frating = d.getResult()
	if not frating: return None,None
	d = dialogs.ChoiceMenu('Accuracy Rating')
	d.addItem('3','Full Accuracy')
	d.addItem('2','OK Accuracy')
	d.addItem('1','Poor Accuracy')
	arating = d.getResult()
	if not arating: return None,None
	return frating,arating
	
def chooseLogo(forum,image_urls,keep_colors=False):
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
	menu = dialogs.ImageChoiceMenu('Choose Logo')
	for url in image_urls: menu.addItem(url, url, url)
	url = menu.getResult(keep_colors=keep_colors)
	return url or ''
		
def getCurrentLogo(forumID=None,logo=None):
	if not logo:
		if FB: logo = FB.urls.get('logo')
	if not logo: return
	if not forumID: forumID = FB.getForumID()
	if not forumID: return
	root, ext = os.path.splitext(logo) #@UnusedVariable
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
	w = dialogs.openWindow(dialogs.ColorDialog,'script-forumbrowser-color-dialog.xml',return_window=True,image=logo,hexcolor=color,theme='Default')
	hexc = w.hexValue()
	del w
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
	dialogs.showMessage('Done','Color Set!')
	return True

def updateThemeODB(forumID=None):
	if not forumID:
		forumID = FB.getForumID()
	odb = forumbrowser.FBOnlineDatabase()
	fdata = forumbrowser.ForumData(forumID,FORUMS_PATH)
	splash = dialogs.showActivitySplash('Saving To ODB')
	try:
		result = str(odb.setTheme(forumID[3:],fdata.theme))
	finally:
		splash.close()
	LOG('Updating ODB Theme: ' + result)
	if result == '1':
		dialogs.showMessage('Done','Online database color updated.')
	else:
		dialogs.showMessage('Failed','Failed to update the online database.')
	
def removeForum(forum=None):
	if forum: return doRemoveForum(forum)
	forum = True
	while forum:
		forum = askForum(caption='Choose Forum To Remove',hide_extra=True)
		if not forum: return
		doRemoveForum(forum)
		
def doRemoveForum(forum):
	yes = xbmcgui.Dialog().yesno('Remove?','Really remove forum:','','%s?' % forum[3:])
	if not yes: return False
	path = os.path.join(FORUMS_PATH,forum)
	if not os.path.exists(path): return
	os.remove(path)
	dialogs.showMessage('Removed','Forum removed.')
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
			idx = int(__addon__.getSetting('language'))
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
		
class DownloadThread(StoppableThread):
	def __init__(self,targetdir,urllist,ext='',callback=None,old_thread=None,nothread=False):
		StoppableThread.__init__(self,name='Downloader')
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
	def __init__(self,header=__language__(30205),message=''):
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
				self.display = 'File %s of %s' % (i+1,self.total)
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
			self.display = __language__(30206) % os.path.basename(path)
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
		urlObj = urllib2.urlopen(url)
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
		
def getForumBrowser(forum=None,url=None,donecallback=None,silent=False,no_default=False):
	showError = dialogs.showMessage
	if silent: showError = dialogs.showMessageSilent
	global STARTFORUM
	if not forum and STARTFORUM:
			forum = STARTFORUM
			STARTFORUM = None
			
	if not forum:
		if no_default: return False
		forum = __addon__.getSetting('last_forum') or 'TT.xbmc.org'
	#global FB
	#if forum.startswith('GB.') and not url:
	#	url = getSetting('exp_general_forums_last_url')
	#	if not url: forum = 'TT.xbmc.org'
		
	if not getForumPath(forum):
		if no_default: return False
		forum = 'TT.xbmc.org'
	err = ''
	try:
		if forum.startswith('GB.'):
			err = 'getForumBrowser(): General'
			from forumbrowser import genericparserbrowser
			FB = genericparserbrowser.GenericParserForumBrowser(forum,always_login=getSetting('always_login',False))
		elif forum.startswith('TT.'):
			err = 'getForumBrowser(): Tapatalk'
			FB = tapatalk.TapatalkForumBrowser(forum,always_login=getSetting('always_login',False))
		elif forum.startswith('FR.'):
			err = 'getForumBrowser(): Forumrunner'
			from forumbrowser import forumrunner
			FB = forumrunner.ForumrunnerForumBrowser(forum,always_login=getSetting('always_login',False))
		#else:
		#	err = 'getForumBrowser(): Boxee'
		#	from forumbrowser import parserbrowser
		#	FB = parserbrowser.ParserForumBrowser(forum,always_login=__addon__.getSetting('always_login') == 'true')
	except forumbrowser.ForumMovedException,e:
		showError(__language__(30050),'Error accessing forum.\n\nIt apppears the forum may have moved. Check the forum address in a browser and try re-adding it, or if there is a URL listed below, you can try re-adding it with that URL.\n',e.message,error=True)
		return False
	except forumbrowser.ForumNotFoundException,e:
		showError(__language__(30050),'Error accessing forum.\n\nIt apppears the forum interface (%s) is no longer installed, is missing or has moved.\n\nVerify the forum\'s URL in a browser and then try re-adding it.\n\nCheck with the forum administrator if the problem persists.' % e.message,error=True)
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
			showError(__language__(30050),'Error accessing forum.\n\nForum interface appears to have changed from %s to %s.\n\nTry re-adding it.' % (fromType,toType),error=True)
		else:
			showError(__language__(30050),'Error accessing forum.\n\nPlease contact the forum administrator if this problem continues.',error=True)
		return False
	except:
		err = ERROR(err)
		showError(__language__(30050),__language__(30171),err,error=True)
		return False
	
	if donecallback: donecallback(FB)
	return FB

def startForumBrowser(forumID=None):
	global PLAYER, STARTFORUM
	PLAYER = PlayerMonitor()
	updateOldVersion()
	forumbrowser.ForumPost.hideSignature = getSetting('hide_signatures',False)
	mods.checkForSkinMods()

	#TD = ThreadDownloader()
	if forumID:
		STARTFORUM = forumID
	elif sys.argv[-1].startswith('forum='):
		STARTFORUM = sys.argv[-1].split('=',1)[-1]
	dialogs.openWindow(ForumsWindow,"script-forumbrowser-forums.xml")
	#sys.modules.clear()
	PLAYER.finish()
	
######################################################################################
# Startup
######################################################################################
if __name__ == '__main__':
	if sys.argv[-1] == 'settings':
		doSettings()
	elif sys.argv[-1].startswith('settingshelp_'):
		dialogs.showHelp('settings-' + sys.argv[-1].split('_')[-1])
	else:
		startForumBrowser()
		