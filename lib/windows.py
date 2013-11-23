import threading, xbmc, xbmcgui, time, re, signals, asyncconnections, dialogs
from xbmcconstants import *  # @UnusedWildImport
from lib.forumbrowser import forumbrowser
import util

SIGNALHUB = None

######################################################################################
# Base Window Classes
######################################################################################
class ThreadError:
	def __init__(self,message='Unknown'):
		self.message = message
		
	def __nonzero__(self):
		return False
	
class StoppableCallbackThread(util.StoppableThread):
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
		util.StoppableThread.__init__(self,name=name)
		
	def setArgs(self,*args,**kwargs):
		self.args = args
		self.kwargs = kwargs
		
	def run(self):
		try:
			self._target(*self.args,**self.kwargs)
		except forumbrowser.Error,e:
			util.LOG('ERROR IN THREAD: ' + e.message)
			self.errorCallback(ThreadError('%s: %s' % (self._threadName,e.message)))
		except:
			err = util.ERROR('ERROR IN THREAD: ' + self._threadName)
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
		self._funcID = 0
		if SIGNALHUB: SIGNALHUB.registerSelfReceiver('RUN_IN_MAIN', self, self.runInMainCallback)
		self._resetFunction()
			
	def setAsMain(self):
		self._isMain = True
		
	def setStopControl(self,control):
		self._stopControl = control
		self.hideProgress()
		
	def showProgress(self):
		self.setProperty('progress','progress')
		if self._stopControl: self._stopControl.setVisible(True)
	
	def hideProgress(self):
		self.setProperty('progress','')
		if self._stopControl: self._stopControl.setVisible(False)
	
	def setProgressCommands(self,start=None,progress=None,end=None):
		self._startCommand = start
		self._progressCommand = progress
		self._endCommand = end
		
	def runInMainCallback(self,signal,data):
		if self._functionStack:
			func,args,kwargs = self.getNextFunction(data)
			if not func: return
			func(*args,**kwargs)
	
	def onAction(self,action):
		if action == ACTION_RUN_IN_MAIN:
			#print 'yy %s' % repr(self._functionStack)
			if self._functionStack:
				self.runInMainCallback(None, None)
				return True
			else:
				signals.sendSignal('RUN_IN_MAIN')
		elif action == ACTION_PREVIOUS_MENU:
			asyncconnections.StopConnection()
			if self._currentThread and self._currentThread.isAlive():
				self._currentThread.stop()
				if self._endCommand: self._endCommand()
				self.hideProgress()
			if self._isMain and len(threading.enumerate()) > 1:
				d = xbmcgui.DialogProgress()
				d.create(util.T(32220),util.T(32221))
				d.update(0)
				self.stopThreads()
				if d.iscanceled():
					d.close()
					return True
				d.close()
			return False
		return False
	
	def onClose(self):
		if SIGNALHUB: SIGNALHUB.unRegister(None, self)
		
	def stopThreads(self):
		for t in threading.enumerate():
			if isinstance(t,util.StoppableThread): t.stop()
		time.sleep(1)
		while len(threading.enumerate()) > 1:
			for t in threading.enumerate():
				#if t != threading.currentThread(): t.join()
				if isinstance(t,util.StoppableThread) and t.isAlive(): t.raiseExc(Exception)
			time.sleep(1)
	
	def _resetFunction(self):
		self._functionStack = []
	
	def getNextFunction(self,funcID):
		if self._functionStack:
			for i in range(0,len(self._functionStack)):
				if funcID == self._functionStack[i][3]: return self._functionStack.pop(i)[:-1]
		return (None,None,None)
		
	def addFunction(self,function,args,kwargs,funcID):
		self._functionStack.append((function,args,kwargs,funcID))
		
	def runInMain(self,function,*args,**kwargs):
		#print 'xx %s' % repr(function)
		funcID = function.__name__ + ':' + str(self._funcID)
		self.addFunction(function, args, kwargs,funcID)
		signals.sendSelfSignal(self,'RUN_IN_MAIN',funcID)
		self._funcID+=1
		if self._funcID > 9999: self._funcID = 0
		#xbmc.executebuiltin('Action(codecinfo)')
		
	def endInMain(self,function,*args,**kwargs):
		if self._endCommand: self._endCommand()
		self.hideProgress()
		self.runInMain(function,*args,**kwargs)
		
	def getThread(self,function,finishedCallback=None,progressCallback=None,errorCallback=None,name='FBUNKNOWN'):
		if self._currentThread: self._currentThread.stop()
		if not progressCallback: progressCallback = self._progressCommand
		t = StoppableCallbackThread(target=function,name=name)
		t.setFinishedCallback(self.endInMain,finishedCallback)
		t.setErrorCallback(self.endInMain,errorCallback)
		t.setProgressCallback(self.runInMain,progressCallback)
		self._currentThread = t
		if self._startCommand: self._startCommand()
		self.showProgress()
		return t
		
	def stopThread(self):
		asyncconnections.StopConnection()
		self.hideProgress()
		if self._currentThread:
			self._currentThread.stop()
			self._currentThread = None
			if self._endCommand: self._endCommand()
		
class ManagedWindow():
	managed = util.getSetting('disable_window_stacking',False)
	
	def __init__(self):
		self._data = None
		self._XML = ''
		self._KWArgs = None
		self._nextWindow = None
		self._nextXML = ''
		self._nextKWArgs = None
		self._nextData = None
		self._function = None
		self._funcArgs = None
		self._funcKWArgs = None
		self._hop = False
		
	def selectedIndex(self): return None
	
	def nextWindow(self, data, window, xml, **kwargs):
		if not self.managed:
			dialogs.openWindow(window,xml,**kwargs)
			return False
		data.select = self.selectedIndex()
		self._data = data
		self._nextWindow = window
		self._nextXML = xml
		self._nextKWArgs = kwargs
		self.close()
		return True
	
	def hop(self,data, xml, **kwargs):
		return self._doHop(data,xml,False,**kwargs)
		
	def _doHop(self, data, xml, _refresh_xbmc_skin, **kwargs):
		if not self.managed:
			self.close()
			if _refresh_xbmc_skin: util.refreshXBMCSkin()
			dialogs.openWindow(self.__class__,xml,data=data,**kwargs)
			return False
		self._nextData = data
		self._nextWindow = self.__class__
		self._nextXML = xml
		self._nextKWArgs = kwargs
		self._hop = True
		self.close()
		if _refresh_xbmc_skin: util.refreshXBMCSkin()
		return True
		
	def function(self,data, xml, function,*args,**kwargs):
		if not self.managed: return function(*args,**kwargs)
		self._nextData = data
		self._nextWindow = self.__class__
		self._nextXML = xml
		self._function = function
		self._funcArgs = args
		self._funcKWArgs = kwargs
		self.close()
		
class BaseWindowFunctions(ThreadWindow,ManagedWindow):
	def __init__( self, *args, **kwargs ):
		self._progMessageSave = ''
		self.closed = False
		self.headerTextFormat = '%s'
		self._externalWindow = None
		self._progressWidth = 1
		self.viewType = None
		ThreadWindow.__init__(self)
		ManagedWindow.__init__(self)
		
	def skinLevel(self):
		try:
			return int(self.getProperty('skin_level'))
		except:
			return 0
		
	def externalWindow(self):
		if not self._externalWindow: self._externalWindow = self._getExternalWindow()
		return self._externalWindow
		
	def _getExternalWindow(self): pass
	
	def onClick( self, controlID ):
		if controlID == 186:
			self.toggleSlideUp()
		elif controlID == 187:
			self.toggleDark()
		elif controlID == 188:
			self.openWindowSettings()
	
	def toggleSlideUp(self):
		val = not util.getSetting('window_slide_up_%s' % self.viewType, False)
		setWindowSlideUp(val,view=self.viewType)
		
	def toggleDark(self):
		val = not util.getSetting('window_colors_dark_%s' % self.viewType, False)
		setWindowColorsDark(val,view=self.viewType)
		
	def openWindowSettings(self):
		d = dialogs.ChoiceMenu('Options')
		d.addItem('back_view','Set Default Background Image For This View')
		#d.addItem('back_view_forum','Set Background Image For This View On This Forum')
		d.addItem('clear_back_view','Clear The Default Background Image For This View')
		#d.addItem('clear_back_view_forum','Clear The Background Image For This View On This Forum')
		d.addItem('set_fade','Set The Background Fade Level')
		d.addItem('set_selection_color','Set The List Selection Color')
		res = d.getResult()
		if not res: return
		if res == 'back_view':
			val = xbmcgui.Dialog().browse(2,'Choose Image','files','',True,False)
			if not val: return
			setWindowBackgroundImage(val,view=self.viewType)
		elif res == 'clear_back_view':
			setWindowBackgroundImage('',view=self.viewType,clear=True)
		elif res == 'set_fade':
			#dialogs.showMessage('Uhh...', 'Hmmm, this is embarassing. I haven\'t implemented this yet :)')
			dialogs.showFadeDialog(view_type=self.viewType)
		elif res == 'set_selection_color':
			image = util.getSetting('window_background_%s' % self.viewType)
			f = util.getSetting('background_fade_%s' % self.viewType, 50)
			val = hex(int((f/100.0)*255))[2:].upper()
			fade = val
			color = util.getSetting('selection_color_%s' % self.viewType, '802080FF')
			color = dialogs.showSelectionColorDialog(start_color=color,preview_image=image,fade=fade)
			setWindowSelectionColors(color,view=self.viewType)
	
	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if ThreadWindow.onAction(self,action): return
		if action == ACTION_PREVIOUS_MENU:
			self.doClose()
		#xbmcgui.WindowXML.onAction(self,action)
	
	def doClose(self):
		self.closed = True
		self.close()
		self.onClose()
	
	def startProgress(self):
		self._progMessageSave = self.getControl(104).getLabel()
		self._progressWidth = self.getControl(300).getWidth()
		self.getControl(310).setWidth(1)
		#self.getControl(310).setVisible(True)
	
	def setProgress(self,pct,message=''):
		if pct<0:
			self.stopThread()
			dialogs.showMessage('ERROR',message,error=True)
			return False
		w = int((pct/100.0)*self._progressWidth)
		self.getControl(310).setWidth(w)
		self.getControl(104).setLabel(self.headerTextFormat % message)
		return True
		
	def endProgress(self):
		#self.getControl(310).setVisible(False)
		self.getControl(104).setLabel(self._progMessageSave)
		
	def highlightTerms(self,FB,message):
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
		if self.search and not (self.search.startswith('@!RECENT') or self.search.startswith('@!UNREAD')):
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
		self.closed
		
	def onInit(self):
		pass
		
	def onAction(self,action):
		BaseWindowFunctions.onAction(self,action)
	
	def onClick(self,controlID):
		BaseWindowFunctions.onClick(self,controlID)
		
	def setProperty(self,key,value):
		self.externalWindow().setProperty(key,value)
		
	def _getExternalWindow(self):
		return xbmcgui.Window(xbmcgui.getCurrentWindowId())
		
class BaseWindowDialog(xbmcgui.WindowXMLDialog,BaseWindowFunctions):
	def __init__(self, *args, **kwargs):
		BaseWindowFunctions.__init__(self, *args, **kwargs)
		xbmcgui.WindowXMLDialog.__init__( self )
	
	def onInit(self):
		pass
		
	def onAction(self,action):
		BaseWindowFunctions.onAction(self,action)
	
	def onClick(self,controlID):
		BaseWindowFunctions.onClick(self,controlID)
		
	def setProperty(self,key,value):
		self.externalWindow().setProperty(key,value)
		
	def _getExternalWindow(self):
		return xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
	
class PageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.next = ''
		self.prev = ''
		self.pageData = None
		self._totalItems = kwargs.get('total_items',0)
		self.firstRun = True
		self._firstPage = util.T(32110)
		self._lastPage = util.T(32111)
		self._newestPage = None
		BaseWindow.__init__( self, *args, **kwargs )
		
	def setPageData(self,FB):
		self.pageData = FB.getPageData(total_items=self._totalItems)
		
	def onFocus( self, controlId ):
		self.controlId = controlId

	def onClick( self, controlID ):
		if controlID == 200 or controlID == 180:
			if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
		elif controlID == 202 or controlID == 181:
			if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
		if controlID == 203 or controlID == 182:
			if self.pageData.prev: self.gotoPage(self.pageData.getPageNumber(1))
		elif controlID == 204 or controlID == 183:
			if self.pageData.next: self.gotoPage(self.pageData.getPageNumber(-1))
		elif controlID == 105 or controlID == 184:
			self.pageMenu()
		elif controlID == 185:
			self.askPageNumber()
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
		options.append(util.T(32115))
		idx = dialogs.dialogSelect(util.T(32114),options)
		if idx < 0: return
		if options[idx] == self._firstPage: self.gotoPage(self.pageData.getPageNumber(1))
		elif options[idx] == self._lastPage: self.gotoPage(self.pageData.getPageNumber(-1))
		elif options[idx] == self._newestPage:
			self.firstRun = True #For replies window
			self.gotoPage(self.pageData.getPageNumber(-1))
		else: self.askPageNumber()
		
	def askPageNumber(self):
		page = xbmcgui.Dialog().numeric(0,util.T(32116))
		try: int(page)
		except: return
		self.gotoPage(self.pageData.getPageNumber(page))
		
	def setupPage(self,pageData):
		if pageData:
			self.pageData = pageData
		else:
			from lib.forumbrowser.forumbrowser import PageData
			pageData = PageData(None)
		self.getControl(200).setVisible(pageData.prev)
		self.getControl(202).setVisible(pageData.next)
		self.getControl(105).setLabel(pageData.getPageDisplay())
		
	def gotoPage(self,page): pass
	
######################################################################################
#
# WindowManager
#
######################################################################################
class WindowManager():
	def __init__(self):
		self.stack = []
		
	def start(self,window,xml,**kwargs):
		wd = self.nextWindow(WindowData().fromData(window,xml,kwargs))
		while wd:
			wd = self.nextWindow(wd)
		
	def nextWindow(self,wd):
		w = dialogs.openWindow(wd.nextWindow,wd.nextXML,return_window=True,data=wd.nextData,**wd.nextKWArgs)
		w._XML = wd.nextXML
		w._KWArgs = wd.nextKWArgs
		wd = self.windowDone(w)
		del w
		return wd
	
	def windowDone(self,w):
		if w._function:
			w._function(*w._funcArgs,**w._funcKWArgs)
			return WindowData(w)
		elif not w._nextWindow:
			if self.stack:
				wd = self.stack.pop()
				return WindowData().fromData(wd.window, wd.XML, wd.KWArgs, wd.data)
		else:
			wd = WindowData(w)
			if w._hop: return wd
			self.stack.append(wd)
			return wd

class WindowData():
	def __init__(self,window=None):
		self.data = window and window._data or None
		self.window = window and window.__class__ or None
		self.XML =  window and window._XML or None
		self.KWArgs =  window and window._KWArgs or {}
		self.nextWindow =  window and window._nextWindow or None
		self.nextXML =  window and window._nextXML or None
		self.nextKWArgs =  window and window._nextKWArgs or {}
		self.nextData = window and window._nextData or None
	
	def fromData(self,window,xml,kwargs,data=None):
		self.nextWindow = window
		self.nextXML = xml
		self.nextKWArgs = kwargs or {}
		self.nextData = data
		return self
	
VIEW_TYPES = ('FORUM','THREAD','POST','MESSAGE','EDITOR')
def setWindowSlideUp(up=None,view=None):
	if up == None:
		up = util.getSetting('window_slide_up', False)
		for v in VIEW_TYPES:
			u = util.getSetting('window_slide_up_%s' % v, False)
			dialogs.setGlobalSkinProperty('ForumBrowser_window_slide_up_%s' % v, u and '1' or '0')
	else:
		if view:
			util.setSetting('window_slide_up_%s' % view, up)
			dialogs.setGlobalSkinProperty('ForumBrowser_window_slide_up_%s' % view, up and '1' or '0')
		util.setSetting('window_slide_up', up)
	dialogs.setGlobalSkinProperty('ForumBrowser_window_slide_up', up and '1' or '0')

def setWindowColorsDark(dark=None,view=None):
	if dark == None:
		dark = util.getSetting('window_colors_dark', False)
		for v in VIEW_TYPES:
			d = util.getSetting('window_colors_dark_%s' % v, False)
			dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_dark_%s' % v, d and '1' or '0')
			if d:
				dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore_%s' % v, 'FFFFFFFF')
				dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back_%s' % v, 'FF000000')
			else:
				dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore_%s' % v, 'FF000000')
				dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back_%s' % v, 'FFFFFFFF')
	elif view:
		util.setSetting('window_colors_dark_%s' % view, dark)
		dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_dark_%s' % view, dark and '1' or '0')
		if dark:
			dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore_%s' % view, 'FFFFFFFF')
			dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back_%s' % view, 'FF000000')
		else:
			dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore_%s' % view, 'FF000000')
			dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back_%s' % view, 'FFFFFFFF')
	else:
		util.setSetting('window_colors_dark', dark)
		
	dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_dark', dark and '1' or '0')
	if dark:
		dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore', 'FFFFFFFF')
		dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back', 'FF000000')
	else:
		dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_fore', 'FF000000')
		dialogs.setGlobalSkinProperty('ForumBrowser_window_colors_back', 'FFFFFFFF')

def setWindowBackgroundImage(image=None,view=None,clear=False):
	if clear:
		util.setSetting('window_background_%s' % view, '')
		dialogs.setGlobalSkinProperty('ForumBrowser_window_background_%s' % view,'')
		return
	if image == None:
		for v in VIEW_TYPES:
			i = util.getSetting('window_background_%s' % v,'')
			dialogs.setGlobalSkinProperty('ForumBrowser_window_background_%s' % v,i)
	else:
		if view:
			util.setSetting('window_background_%s' % view, image)
			dialogs.setGlobalSkinProperty('ForumBrowser_window_background_%s' % view,image)
			
def setWindowBackgroundFades():
	for v in VIEW_TYPES:
		f = util.getSetting('background_fade_%s' % v, 50)
		val = hex(int((f/100.0)*255))[2:].upper()
		dialogs.setGlobalSkinProperty('ForumBrowser_window_background_fade_white_%s' % v,val + 'FFFFFF')
		dialogs.setGlobalSkinProperty('ForumBrowser_window_background_fade_black_%s' % v,val + '000000')
		
def setWindowSelectionColors(color=None,view=None):
	if not color:
		for v in VIEW_TYPES:
			sc = util.getSetting('selection_color_%s' % v, '802080FF')
			v_nf = dialogs.binascii.hexlify(chr(int(ord(dialogs.binascii.unhexlify(sc[:2])) / 4))) + sc[2:]
			dialogs.setGlobalSkinProperty('ForumBrowser_selection_color_%s' % v,sc)
			dialogs.setGlobalSkinProperty('ForumBrowser_selection_color_nofocus_%s' % v,v_nf)
	else:
		util.setSetting('selection_color_%s' % view, color)
		color_nf = dialogs.binascii.hexlify(chr(int(ord(dialogs.binascii.unhexlify(color[:2])) / 4))) + color[2:]
		dialogs.setGlobalSkinProperty('ForumBrowser_selection_color_%s' % view,color)
		dialogs.setGlobalSkinProperty('ForumBrowser_selection_color_nofocus_%s' % view,color_nf)
		
def setWindowProperties():
	setWindowSlideUp()
	setWindowColorsDark()
	setWindowBackgroundImage()
	setWindowBackgroundFades()
	setWindowSelectionColors()
	