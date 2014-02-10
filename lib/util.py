import os, sys, xbmc, xbmcaddon, filelock, threading, urllib, urlparse, binascii, math
from lib import chardet
from webviewer import video #@UnresolvedImport

__addon__ = xbmcaddon.Addon(id='script.forum.browser')
T = __addon__.getLocalizedString

MEDIA_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins','Default','media'))
GENERIC_MEDIA_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','media'))
SETTINGS_PATH = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'settings.xml')
FORUMS_SETTINGS_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'forums_settings'))
FORUMS_STATIC_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'forums'))
FORUMS_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'forums'))
CACHE_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'cache'))
TEMP_DIR = os.path.join(CACHE_PATH,'tmp')

if not os.path.exists(FORUMS_PATH): os.makedirs(FORUMS_PATH)
if not os.path.exists(FORUMS_SETTINGS_PATH): os.makedirs(FORUMS_SETTINGS_PATH)
if not os.path.exists(TEMP_DIR): os.makedirs(TEMP_DIR)

CURRENT_THEME = None
DEBUG = None
PLAYER = None

class AbortRequestedException(Exception): pass
class StopRequestedException(Exception): pass

LOG_PREFIX = 'FORUMBROWSER' 

def ERROR(message,hide_tb=False):
	if sys.exc_info()[0] == AbortRequestedException:
		LOG('Abort Requested (%s): Exiting....' % str(threading.currentThread().getName()))
		import thread
		thread.interrupt_main()
		return 'AbortRequested'
	elif sys.exc_info()[0] == StopRequestedException:
		LOG('Stop exception handled')
		return
	
	LOG('ERROR: ' + message)
	short = str(sys.exc_info()[1])
	if hide_tb:
		LOG('ERROR Message: ' + short)
	else:
		import traceback #@Reimport
		traceback.print_exc()
		if getSetting('debug_show_traceback_dialog',False):
			import dialogs #import dialogs here so we can import this module into dialogs
			dialogs.showText('Traceback', traceback.format_exc())
	return short
	
def LOG(message):
	print '%s: %s' % (LOG_PREFIX,message)

def getSetting(key,default=None):
	with filelock.FileLock(SETTINGS_PATH, timeout=5, delay=0.1):
		setting = __addon__.getSetting(key)
	return _processSetting(setting,default)

def _processSetting(setting,default):
	if not setting: return default
	if isinstance(default,bool):
		return setting.lower() == 'true'
	elif isinstance(default,int):
		return int(float(setting or 0))
	elif isinstance(default,list):
		if setting: return setting.split(':!,!:')
		else: return default
	
	return setting

def setSetting(key,value):
	value = _processSettingForWrite(value)
	with filelock.FileLock(SETTINGS_PATH, timeout=5, delay=0.1):
		__addon__.setSetting(key,value)
	
def _processSettingForWrite(value):
	if isinstance(value,list):
		value = ':!,!:'.join(value)
	elif isinstance(value,bool):
		value = value and 'true' or 'false'
	return str(value)
		
def getSettingExternal(key,default=None):
	with filelock.FileLock(SETTINGS_PATH, timeout=5, delay=0.1):
		setting = xbmcaddon.Addon(id='script.forum.browser').getSetting(key)
	return _processSetting(setting,default)

def setSettingExternal(key,value):
	value = _processSettingForWrite(value)
	with filelock.FileLock(SETTINGS_PATH, timeout=5, delay=0.1):
		xbmcaddon.Addon(id='script.forum.browser').setSetting(key,value)
	
def parseForumBrowserURL(url):
	if not url.startswith('forumbrowser://'):
		return {'forumID':url}
	args = None
	if '?' in url:
		url, args = url.split('?',1)
		args = dict(urlparse.parse_qsl(args))
	parts = url.split('://',1)[-1].split('/',4)
	elements = {}
	elements['forumID'] = parts[0]
	if len(parts) > 1: elements['section'] = parts[1]
	if len(parts) > 2: elements['forum'] = parts[2].replace('%2F','/')
	if len(parts) > 3: elements['thread'] = parts[3].replace('%2F','/')
	if len(parts) > 4: elements['post'] = parts[4].replace('%2F','/')
	elements['args'] = args
	return elements

def createForumBrowserURL(forumID,section='',forum='',thread='',post='',args=None):
	if isinstance(forumID,dict):
		ret = 'forumbrowser://%s/%s/%s/%s/%s' % (	forumID.get('forumID','') or '',
													forumID.get('section','') or '',
													(forumID.get('forum','') or '').replace('/','%2F'),
													(forumID.get('thread','') or '').replace('/','%2F'),
													(forumID.get('post','') or '').replace('/','%2F')
												)
		args = args or forumID.get('args')
	else:
		ret = 'forumbrowser://%s/%s/%s/%s/%s' % (forumID,section,forum,thread,post)
	if args:
		ret += '?' + urllib.urlencode(args)
	return ret.strip('/')
	
def getListItemByProperty(clist,prop,value):
	for idx in range(0,clist.size()):
		item = clist.getListItem(idx)
		if item.getProperty(prop) == value: return item
	return None
	
def selectListItemByProperty(clist,prop,value):
	for idx in range(0,clist.size()):
		item = clist.getListItem(idx)
		if item.getProperty(prop) == value:
			clist.selectItem(idx)
			return item
	return None

def getSavedTheme(current=None,get_current=False):
	if current:
		global CURRENT_THEME
		CURRENT_THEME = current
	if get_current and CURRENT_THEME: return CURRENT_THEME
	try:			
		return ('Sequel','Video')[getSetting('skin',0)]
	except:
		return 'Sequel'

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

######################################################################################
#
# PlayerMonitor
#
######################################################################################
def initPlayer():
	global PLAYER
	PLAYER = PlayerMonitor()
	return PLAYER
	
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

def setRefreshXBMCSkin(off=False):
	#We have to write to file because the settings won't be saved if the settings dialog is closed without an OK
	signal_file = os.path.join(CACHE_PATH,'skin-refresh')
	if off:
		setSetting('refresh_skin',False)
		import xbmcvfs
		xbmcvfs.delete(signal_file)
		return
	with open(signal_file,'w') as f: f.write('True')
	setSetting('refresh_skin',True)
	
def xbmcSkinAwaitingRefresh():
	return getSetting('refresh_skin',False) or os.path.exists(os.path.join(CACHE_PATH,'skin-refresh'))

def refreshXBMCSkin():
	if not xbmcSkinAwaitingRefresh(): return False
	setRefreshXBMCSkin(off=True)
	#showNotice('Forum Browser',T(32542),500)
	from lib import dialogs
	with dialogs.xbmcDialogProgress('Forum Browser',T(32542)) as d:
		for p in range(10,110,10):
			xbmc.sleep(50)
			d.update(p)
	LOG('! REFRESHING XBMC SKIN !')
	xbmc.executebuiltin('ReloadSkin()')
	return True
	
def showNotice(header,message,mtime='',image=__addon__.getAddonInfo('icon')):
	xbmc.executebuiltin('Notification(%s,%s,%s,%s)' % (header,message,mtime,image))

###################################################################	
## Forum Settings
###################################################################
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

def loadForumSettings(forumID,get_rules=False,get_both=False,skip_password=False):
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
	
	import passwordStorage

	ret['username'] = ret.get('username','')
	if skip_password:
		ret['password'] = ''
	else:
		ret['password'] = passwordStorage.retrieve(forumID.replace('.','_') + '_' + ret['username'],ask_on_fail=False) or ''
	ret['notify'] = _processSetting(ret.get('notify'),False)
	ret['right_align'] = _processSetting(ret.get('right_align'),False)
	ret['ignore_forum_images'] = _processSetting(ret.get('ignore_forum_images'),True)
		
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
		import passwordStorage

		password = passwordStorage.store(forumID.replace('.','_') + '_' + data['username'], data['password'])
		del data['password']
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
	
###################################################################	
## Bookmarks
###################################################################	
def addBookmark(url,name):
	bookmarks = loadBookmarks()
	bookmarks.append((url,name))
	saveBookmarks(bookmarks)

def removeBookmark(idx):
	bookmarks = loadBookmarks()
	bookmarks.pop(idx)
	saveBookmarks(bookmarks)

def loadBookmarks():
	bmfile = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'bookmarks')
	if not os.path.exists(bmfile): return []
	with open(bmfile,'r') as f:
		data = f.read()
	lines = data.split('\n')
	bookmarks = []
	for l in lines:
		if l: bookmarks.append(tuple(l.split('\t',1)))
	return bookmarks

def saveBookmarks(bookmarks):
	bmfile = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('profile')),'bookmarks')
	out = []
	for b in bookmarks:
		out.append('\t'.join(b))
	with open(bmfile,'w') as f:
		f.write('\n'.join(out))

def rgbToHex(rgb):
	return ('00' + hex(rgb[0]).split('x')[-1].upper())[-2:] + ('00' + hex(rgb[1]).split('x')[-1].upper())[-2:] + ('00' + hex(rgb[2]).split('x')[-1].upper())[-2:]

def getImageBackgroundColor(path):
	try:
		from PIL import Image # @UnresolvedImport
		img = Image.open(path).convert('RGB')
		h = img.histogram()
		rgb = tuple([b.index(max(b)) for b in [ h[i*256:(i+1)*256] for i in range(3) ]])
		print rgb
		return rgb
	except:
		ERROR('getImageBackgroundColor(): Failed to get background color')
		return (255,255,255)

def makeUnicode(string,encoding='utf-8'):
	if isinstance(string,unicode): return string
	try:
		ret = unicode.decode(string,encoding)
		if DEBUG: LOG('util.makeUnicode(): Successfully used: %s' % encoding)
		return ret
	except:
		detected_encoding = chardet.detect(string)
		if DEBUG: LOG('util.makeUnicode(): Detected encoding: %s' % detected_encoding)
		try:
			string = unicode(string,detected_encoding['encoding'])
			return string
		except:
			return unicode(string,encoding,'replace')

def makeColorGif(hex6color,outpath):
	sourceGIF = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'resources','media','white1px.gif')
	gifReplace = chr(255)*6
	try:
		replace = binascii.unhexlify(hex6color)
	except:
		replace = chr(255)*3
	replace += replace
	with open(outpath,'w') as t:
		with open(sourceGIF,'r') as c:
			t.write(c.read().replace(gifReplace,replace))
	return outpath
	
###################################################################	
## XBMCControlConditionalVisiblity
###################################################################	
class XBMCControlConditionalVisiblity:
	def __init__(self):
		self.cache = {}
		
	def __getattr__(self,attr):
		if attr in self.cache: return self.cache[attr]
		def method(control=0,group=None):
			if group:
				return bool(xbmc.getCondVisibility('ControlGroup(%s).%s(%s)' % (group,attr,control)))
			else:
				return bool(xbmc.getCondVisibility('Control.%s(%s)' % (attr,control)))
										
		self.cache[attr] = method
		return method		
		
Control = XBMCControlConditionalVisiblity()

		