import urllib2, re, os, sys, time, urlparse
import xbmc, xbmcgui, xbmcaddon #@UnresolvedImport
import threading
import forumbrowser

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
__date__ = '03-29-2012'
__version__ = '0.9.31'
__addon__ = xbmcaddon.Addon(id='script.forum.browser')
__language__ = __addon__.getLocalizedString

THEME = 'Default'
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

MEDIA_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins','default','media'))
FORUMS_STATIC_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'forums'))
FORUMS_PATH = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'forums'))
if not os.path.exists(FORUMS_PATH): os.makedirs(FORUMS_PATH)

def ERROR(message):
	LOG('ERROR: ' + message)
	import traceback #@Reimport
	traceback.print_exc()
	return str(sys.exc_info()[1])
	
def LOG(message):
	print 'FORUMBROWSER: %s' % message

LOG('Version: ' + __version__)
LOG('Python Version: ' + sys.version)
DEBUG = __addon__.getSetting('debug') == 'true'
if DEBUG: LOG('DEBUG LOGGING ON')
LOG('Skin: ' + THEME)

FB = None
MC = None
FBMODULE = None

import texttransform
from crypto import passmanager
import tapatalk

def getSetting(key,default=None):
	setting = __addon__.getSetting(key)
	if not setting: return default
	if isinstance(default,bool):
		return setting == 'true'
	elif isinstance(default,int):
		return int(float(setting))
	
	return setting

######################################################################################
# Base Window Classes
######################################################################################
class StoppableThread(threading.Thread):
	def __init__(self,group=None, target=None, name=None, args=(), kwargs={}):
		self._stop = threading.Event()
		threading.Thread.__init__(self,group=group, target=target, name=name, args=args, kwargs=kwargs)
		
	def stop(self):
		self._stop.set()
		
	def stopped(self):
		return self._stop.isSet()
		
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
		if self.stopped(): return False
		if self._progressCallback: self._progressHelper(self._progressCallback,*args,**kwargs)
		return True
		
	def finishedCallback(self,*args,**kwargs):
		if self.stopped(): return False
		if self._finishedCallback: self._finishedHelper(self._finishedCallback,*args,**kwargs)
		return True
	
	def errorCallback(self,error):
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
				self._function(*self._functionArgs,**self._functionKwargs)
				self._resetFunction()
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
		for t in threading.enumerate():
			if t != threading.currentThread(): t.join()
			
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
		
class BaseWindow(xbmcgui.WindowXMLDialog,ThreadWindow):
	def __init__( self, *args, **kwargs ):
		self._progMessageSave = ''		
		if __addon__.getSetting('use_forum_colors') == 'false':
			self._prog_format = '%s'
		else:
			self._prog_format = '[COLOR '+FB.theme.get('title_fg','FF000000')+']%s[/COLOR]'
		ThreadWindow.__init__(self)
		xbmcgui.WindowXMLDialog.__init__( self )
	
	def onClick( self, controlID ):
		return False
			
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		if ThreadWindow.onAction(self,action): return
		if action == ACTION_PREVIOUS_MENU: self.close()
		xbmcgui.WindowXML.onAction(self,action)
	
	def startProgress(self):
		self._progMessageSave = self.getControl(104).getLabel()
		#self.getControl(310).setVisible(True)
	
	def setProgress(self,pct,message=''):
		if pct<0:
			self.stop()
			xbmcgui.Dialog().ok('ERROR',message)
			return False
		w = int((pct/100.0)*self.getControl(300).getWidth())
		self.getControl(310).setWidth(w)
		self.getControl(104).setLabel(self._prog_format % message)
		return True
		
	def endProgress(self):
		#self.getControl(310).setVisible(False)
		self.getControl(104).setLabel(self._progMessageSave)
	
class PageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.next = ''
		self.prev = ''
		self.pageData = FB.PageData(total_items=kwargs.get('total_items',0))
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
		dialog = xbmcgui.Dialog()
		options = [self._firstPage,self._lastPage]
		if self._newestPage: options.append(self._newestPage)
		options.append(__language__(30115))
		idx = dialog.select(__language__(30114),options)
		if idx < 0: return
		if options[idx] == self._firstPage: self.gotoPage(self.pageData.getPageNumber(1))
		elif options[idx] == self._lastPage: self.gotoPage(self.pageData.getPageNumber(9999))
		elif options[idx] == self._newestPage: self.gotoPage(self.pageData.getPageNumber(-1))
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
			from scraperbrowser import PageData
			pageData = PageData()
		self.getControl(200).setVisible(pageData.prev)
		self.getControl(202).setVisible(pageData.next)
		if __addon__.getSetting('use_forum_colors') == 'false':
			self.getControl(105).setLabel(pageData.getPageDisplay())
		else:
			self.getControl(105).setLabel(pageData.getPageDisplay())
		
	def gotoPage(self,page): pass

######################################################################################
# Image Dialog
######################################################################################
class ImagesDialog(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		BaseWindow.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(200).setEnabled(len(self.images) > 1)
		self.getControl(202).setEnabled(len(self.images) > 1)
		self.showImage()

	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def showImage(self):
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
		if action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_NEXT_ITEM:
			self.nextImage()
		elif action == ACTION_PREV_ITEM:
			self.prevImage()
		elif action == ACTION_CONTEXT_MENU:
			self.doMenu()
		BaseWindow.onAction(self,action)
		
	def doMenu(self):
		d = ChoiceMenu('Options')
		d.addItem('save', 'Save Image')
		result = d.getResult()
		if not result: return
		if result == 'save':
			self.saveImage()
			
	def saveImage(self):
		#browse(type, heading, shares[, mask, useThumbs, treatAsFolder, default])
		source = self.images[self.index]
		filename = doKeyboard('Enter Filename', os.path.basename(source))
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
				filename = doKeyboard('Enter Filename', filename)
				original = filename
				if filename == None: return
			target = os.path.join(result,filename)
		import shutil
		shutil.copy(source, target)
		xbmcgui.Dialog().ok('Finished','File Saved Successfully: ',os.path.basename(target))
		
######################################################################################
# Post Dialog
######################################################################################
class PostDialog(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.title = self.post.title
		self.posted = False
		if __addon__.getSetting('use_forum_colors') == 'false':
			self.display_base = '%s\n \n'
		else:
			self.display_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']%s[/COLOR]\n \n'
		BaseWindow.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(122).setText(' ') #to remove scrollbar
		if self.post.quote:
			qformat = FB.formats.get('quote')
			pid = self.post.pid
			if qformat:
				#This won't work with other formats, need to do this better TODO
				if not pid or pid.startswith('PM'): qformat = qformat.replace(';!POSTID!','')
				for line in qformat.replace('!USER!',self.post.quser).replace('!POSTID!',self.post.pid).replace('!QUOTE!',self.post.quote).split('\n'):
					self.addQuote(line)
			else:
				for line in self.post.quote.split('\n'): self.addQuote(line)
		elif self.post.isEdit:
			for line in self.post.message.split('\n'): self.addQuote(line)
				
		self.updatePreview()
		self.setTheme()
	
	def setTheme(self):
		self.getControl(103).setLabel('Post Reply')
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
		BaseWindow.onAction(self,action)
		
	
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
		self.prog = xbmcgui.DialogProgress()
		self.prog.create(__language__(30126),__language__(30127))
		self.prog.update(0)
		self.post.setMessage(self.title,message)
		self.posted = True
		try:
			if self.post.isPM:
				FB.doPrivateMessage(self.post.to,self.title,message,callback=self.dialogCallback)
			else:
				if not FB.post(self.post,callback=self.dialogCallback):
					self.posted = False
					xbmcgui.Dialog().ok(__language__(30050),__language__(30227),self.post.error or '?')
		except:
			self.prog.close()
			self.posted = False
			raise
		self.prog.close()
		self.close()
		
	def parseCodes(self,text):
		return MC.parseCodes(text)
	
	def processQuote(self,m):
		gd = m.groupdict()
		quote = MC.imageFilter.sub(MC.quoteImageReplace,gd.get('quote',''))
		if gd.get('user'):
			ret = MC.quoteReplace % (gd.get('user',''),quote)
		else:
			ret = MC.aQuoteReplace % quote
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
			disp =  MC.messageToDisplay(disp.replace('\n','[CR]'))
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
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		PostDialog.onAction(self,action)
		
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30051),[__language__(30128),__language__(30122)])
		if idx == 0: self.addLineSingle(before=True)
		elif idx == 1: self.deleteLine()
		
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
	
	def doKeyboard(self,caption,text):
		if __addon__.getSetting('use_skin_mods') == 'true':
			return doModKeyboard(caption,text)
		else:
			return doKeyboard(caption,text)
			
	def addLineSingle(self,before=False,update=True):
		line = self.doKeyboard(__language__(30123),'')
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
		line = self.doKeyboard(__language__(30124),item.getLabel())
		if line == None: return False
		item.setProperty('text',line)
		item.setLabel(self.displayLine(line))
		self.updatePreview()
		#re.sub(q,'[QUOTE=\g<user>;\g<postid>]\g<quote>[/QUOTE]',MC.lineFilter.sub('',test3))

class TextPostDialog(PostDialog):
	def __init__( self, *args, **kwargs ):
		PostDialog.__init__( self, *args, **kwargs )
		self.buffer = ''
		self.cursor = '[COLOR red]|[/COLOR]'
		#self.cursor = '|'
		self.cursorPos = 0
		self.charsPerLine = 100
		self.linesPerPage = 12
		self.lastViewStart = 0
		self.posHint = -1
		self.editButton = None
		import string
		self.transTable = string.maketrans("`1234567890-=abcdefghijklmnopqrstuvwxyz[]\\;',./", "~!@#$%^&*()_+ABCDEFGHIJKLMNOPQRSTUVWXYZ{}|:\"<>?")
	
	def onInit(self):
		PostDialog.onInit(self)
		self.editButton = self.getControl(200)
		self.cursorPos = len(self.buffer)
		self.showBuffer()
	
	def addQuote(self,quote):
		self.buffer += quote + '\n'
		
	def getOutput(self):
		return self.buffer
	
	def onClick(self,controlID):
		PostDialog.onClick(self,controlID)
		
	def onAction(self,action):
		if self.checkKeys(action): return
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
			return
		PostDialog.onAction(self,action)
		
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select(__language__(30051),[__language__(30120),__language__(3008)])
		if idx == 0: self.setTitle()
		elif idx == 1: self.postReply()
		
	def checkKeys(self,action):
		#if not self.editButton.isSelected(): return False
		aid = action.getId()
		bc = action.getButtonCode()
		try:
			shift = False
			if bc & 0x00020000:
				#de-shift
				bc = bc ^ 0x00020000
				shift = True
			if not bc: bc = aid
			char = None
			if aid == ACTION_PARENT_DIR or aid == ACTION_PARENT_DIR2:
				self.backspace()
				return True
			#elif aid == 18:
			#	char = '\\'
			#	xbmc.executebuiltin('Action(fullscreen)')
			elif aid == 122:
				if bc == 61517:
					char = 'm'
				else:
					xbmc.executebuiltin('Action(previousmenu)')
					char = 's'
			#elif aid == 88:
			elif bc == 61627:
				char = '='
			#	else:
			#		char = '+'
			elif aid > 0 and aid < 5:
				self.moveCursor(aid)
				return True
			elif bc == 61453:
				char = '\n'
			elif bc == 61472:
				char = ' '
			elif bc == 61475:
				self.moveToEnd()
			elif bc == 61476:
				self.moveToStart()
			elif bc > 61504 and bc < 61531:
				#a-z
				char = chr(bc-61408)
			elif bc > 61535 and bc < 61546:
				#0-9
				char = chr(bc-61488)
			elif bc == 61626:
				char = ';'
			elif bc == 61632:
				char = '`'
			elif bc == 61678:
				char = "'"
			elif bc > 61626 and bc < 61678:
				char = chr(bc-61584)
			elif bc > 61726 and bc < 61823:
				char = chr(bc-61696)
			elif bc == 61473:
				#pgup
				self.pageUp()
			elif bc == 61474:
				#pgdn
				self.pageDown()
			elif bc == 127009:
				#ctrl-pgup
				xbmc.executebuiltin('PageUp(123)')
			elif bc == 127010:
				#ctrl-pgdn
				xbmc.executebuiltin('PageDown(123)')
			elif bc == 127138:
				char = '\\'
			
			if char:
				if shift: char = char.translate(self.transTable)
				self.addChar(char)
				self.posHint = -1
				return True
		except:
			raise
			return False
			
		return False
		
	def pageUp(self):
		for x in range(0,self.linesPerPage-1): #@UnusedVariable
			self.lastViewStart -= 1
			if self.lastViewStart < 0:
				self.lastViewStart = 0
				break
			self.moveCursor(61478)
		
	def pageDown(self):
		cmax = len(self.getWrapped()) - self.linesPerPage
		for x in range(0,self.linesPerPage-1): #@UnusedVariable
			self.lastViewStart += 1
			if self.lastViewStart > cmax:
				self.lastViewStart = cmax
				break
			self.moveCursor(61480)
	
	def moveCursor(self,bc):
		if bc == 1:
			#left
			self.posHint = -1
			self.cursorPos -= 1
			if self.cursorPos < 0: self.cursorPos = 0
		elif bc == 3:
			#up
			oldPos = self.cursorPos
			idx,pos,clen = self.getLinePos() #@UnusedVariable
			relPos = pos % self.charsPerLine
			if self.posHint < 0: self.posHint = relPos
			posOff = self.posHint - relPos
			if pos > self.charsPerLine-1:
				self.cursorPos -= (self.charsPerLine - posOff)
				if self.cursorPos < 0: self.cursorPos = 0
			else:
				line = self.getPreviousLine()
				llen = len(line)
				tail = llen % self.charsPerLine
				self.cursorPos -= (pos + 1)
				if tail > self.posHint: self.cursorPos -= (tail - self.posHint)
			#if self.cursorPos == -1 and line: self.cursorPos = 0
			if self.cursorPos < 0: self.cursorPos = oldPos
		elif bc == 2:
			#right
			self.posHint = -1
			self.cursorPos += 1
			if self.cursorPos > len(self.buffer): self.cursorPos = len(self.buffer)
		elif bc == 4:
			#down
			eol = self.buffer.find('\n',self.cursorPos)
			sol = self.buffer.rfind('\n',0,self.cursorPos)
			#if sol < 0: sol = 0
			if eol < 0:
				eol = len(self.buffer)
				if eol - sol < self.charsPerLine: return
			lpos = self.cursorPos - sol
			relPos = lpos % self.charsPerLine
			if self.posHint < 0: self.posHint = relPos - 1
			posOff = (self.posHint - relPos) + 1
			llen = eol - sol
			if lpos + self.charsPerLine < llen:
				self.cursorPos += self.charsPerLine + posOff
			elif lpos != eol and llen > self.charsPerLine and llen % self.charsPerLine and lpos + self.charsPerLine < llen + (self.charsPerLine - (llen % self.charsPerLine)):
				self.cursorPos = eol
			else:
				next_eol = self.buffer.find('\n',eol+1)
				if next_eol < 0: next_eol = len(self.buffer)
				off = (lpos % self.charsPerLine)
				newPos = eol + off + posOff
				#if llen > self.charsPerLine: newPos += 1
				if newPos > next_eol:
					if newPos >= len(self.buffer): return
					self.cursorPos = next_eol
				else:
					self.cursorPos = newPos
			if self.cursorPos > len(self.buffer): self.cursorPos = oldPos
		self.showBuffer(upPrev=False)
	
	def moveToEnd(self):
		self.posHint = -1
		eol = self.buffer.find('\n',self.cursorPos)
		if eol < 0:
			self.cursorPos = len(self.buffer)
		else:
			self.cursorPos = eol
		self.showBuffer()
		
	def moveToStart(self):
		self.posHint = -1
		sol = self.buffer.rfind('\n',0,self.cursorPos) + 1
		if sol:
			self.cursorPos = sol
		else:
			self.cursorPos = 0
		self.showBuffer()
		
	def getPreviousLine(self):
		lines = self.buffer.split('\n')
		ct=0
		lastline = ''
		for line in lines:
			ct += len(line) + 1
			if self.cursorPos < ct:
				return lastline
			lastline = line
			
	def getLinePos(self):
		lines = self.buffer.split('\n')
		ct=0
		lastct=0
		idx=0
		for line in lines:
			ct += len(line) + 1
			if self.cursorPos < ct:
				return (idx,self.cursorPos - lastct,len(line))
			lastct = ct
			idx += 1
		return (idx-1,len(line),len(line))
	
	def backspace(self):
		self.buffer = self.buffer[0:self.cursorPos-1] + self.buffer[self.cursorPos:]
		self.cursorPos -= 1
		self.showBuffer()
		
	def addChar(self,char):
		self.buffer = self.buffer[0:self.cursorPos] + char + self.buffer[self.cursorPos:]
		self.cursorPos += 1
		self.showBuffer()
				
	def showBuffer(self,upPrev=True):
		wrapped = self.getWrapped()
		cursor_idx = 0
		for w in wrapped:
			if '\r' in w: break
			cursor_idx += 1
		if cursor_idx < self.lastViewStart:
			self.lastViewStart = cursor_idx
		elif cursor_idx >= self.lastViewStart + self.linesPerPage:
			self.lastViewStart = (cursor_idx - self.linesPerPage) + 1
		show = wrapped[self.lastViewStart:self.lastViewStart + self.linesPerPage]
		self.getControl(120).setText('\n'.join(show).replace('\r',self.cursor))
		if upPrev: self.updatePreview()
		
	def getWrapped(self):
		buff = self.buffer[0:self.cursorPos]+'\r'+self.buffer[self.cursorPos:]
		lines = buff.split('\n')
		wrapped = []
		for line in lines:
			wrapped += self.splitLine(line)
		return wrapped
		
	def splitLine(self,line):
		llen = len(line)
		if llen <= self.charsPerLine: return [line]
		ct = 0
		lastct = 0
		out = []
		while ct < llen:
			ct += self.charsPerLine
			sub = line[lastct:ct]
			#Don't count cursor in line length
			if '\r' in sub:
				ct += 1
				sub = line[lastct:ct]
			out.append(sub)
			lastct = ct
		return out

######################################################################################
# Message Window
######################################################################################
class MessageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]%s[/COLOR]'
		self.imageReplace = 'IMG #%s'
		self.action = None
		self.started = False
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
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
		text = '%s[CR] [CR]' % self.post.messageAsDisplay(raw=True)
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
		for link in self.post.links():
			item = xbmcgui.ListItem(link.text or link.url,link.urlShow())
			if link.isImage():
				item.setIconImage(link.url)
			elif link.isPost():
				item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-post.png'))
			elif link.isThread():
				item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-thread.png'))
			else:
				item.setIconImage(os.path.join(MEDIA_PATH,'forum-browser-link.png'))
			ulist.addItem(item)

	def getImages(self):
		i=0
		for url in self.post.imageURLs():
			i+=1
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
	
	def linkSelected(self):
		idx = self.getControl(148).getSelectedPosition()
		if idx < 0: return
		links = self.post.links()
		if idx >= len(links): return
		link = links[idx]
		
		if link.isImage():
			self.showImage(link.url)
		elif link.isPost() or link.isThread():
			self.action = forumbrowser.PostMessage(tid=link.tid,pid=link.pid)
			self.close()
		else:
			try:
				webviewer.getWebResult(link.url,dialog=True)
			except:
				#We're in Boxee
				wvPath = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'webviewer'))
				webviewer.getWebResult(link.url,dialog=True,runFromSubDir=wvPath)
				#xbmc.executebuiltin('XBMC.RunScript(special://home/apps/script.web.viewer/default.py,%s)' % link.url)
			
#			base = xbmcgui.Dialog().browse(3,__language__(30144),'files')
#			if not base: return
#			fname,ftype = Downloader(message=__language__(30145)).downloadURL(base,link.url)
#			if not fname: return
#			xbmcgui.Dialog().ok(__language__(30052),__language__(30146),fname,__language__(30147) % ftype)
		
	def showImage(self,url):
		base = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('profile'),'slideshow'))
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		image_files = Downloader(message=__language__(30148)).downloadURLs(base,[url],'.jpg')
		if not image_files: return
		w = ImagesDialog("script-forumbrowser-imageviewer.xml" ,__addon__.getAddonInfo('path'),THEME,images=image_files,parent=self)
		w.doModal()
		del w
			
	def onAction(self,action):
		BaseWindow.onAction(self,action)
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		
	def doMenu(self):
		options = [__language__(30134)]
		delete = None
		edit = None
		if FB.canDelete(self.post.cleanUserName()):
			delete = len(options)
			options.append(__language__(30141))
		if FB.canEditPost(self.post.cleanUserName()):
			edit = len(options)
			options.append(__language__(30232))
		idx = xbmcgui.Dialog().select(__language__(30051),options)
		if idx == 0: self.openPostDialog(quote=True)
		elif idx == delete: self.deletePost()
		elif idx == edit:
			pm = FB.getPostForEdit(self.post.postId)
			pm.tid = self.post.tid
			if openPostDialog(editPM=pm):
				self.action = forumbrowser.Action('REFRESH')
				self.close()
			
	def deletePost(self):
		post = forumbrowser.PostMessage(self.post.pid,self.post.tid,self.post.fid)
		if not self.post.pid: return
		prog = xbmcgui.DialogProgress()
		prog.create(__language__(30149),__language__(30150))
		prog.update(0)
		try:
			FB.deletePost(post)
		except:
			prog.close()
			raise
		prog.close()
		self.action = forumbrowser.Action('REFRESH')
		self.close()
		
	def openPostDialog(self,quote=False):
		if openPostDialog(quote and self.post or None,tid=self.post.tid,fid=self.post.fid):
			self.action = forumbrowser.Action('REFRESH')
		
	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)

def openPostDialog(post=None,pid='',tid='',fid='',editPM=None):
	if editPM:
		pm = editPM
	else:
		pm = forumbrowser.PostMessage(pid,tid,fid,is_pm=(tid == 'private_messages'))
		if post: pm.setQuote(post.userName,post.messageAsQuote())
		if tid == 'private_messages':
			to = doKeyboard('Enter Receipient(s)')
			if not to: return
			pm.to = to
	if __addon__.getSetting('use_text_editor') == 'true':
		w = TextPostDialog(	"script-forumbrowser-post-text.xml" ,__addon__.getAddonInfo('path'),THEME,post=pm)
	else:
		w = LinePostDialog(	"script-forumbrowser-post.xml" ,__addon__.getAddonInfo('path'),THEME,post=pm)
	w.doModal()
	posted = w.posted
	del w
	return posted
		
######################################################################################
# Replies Window
######################################################################################
class RepliesWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		PageWindow.__init__( self,total_items=int(kwargs.get('reply_count',0)),*args, **kwargs )
		self.pageData.isReplies = True
		self.tid = kwargs.get('tid','')
		self.fid = kwargs.get('fid','')
		self.pid = ''
		self.topic = kwargs.get('topic','')
		self.lastid = kwargs.get('lastid','')
		self.threadItem = kwargs.get('item')
		self.parent = kwargs.get('parent')
		#self._firstPage = __language__(30113)
		self._newestPage = __language__(30112)
		self.me = self.parent.parent.getUsername()
		self.posts = {}
		self.empty = True
		self.desc_base = u'[CR]%s[CR] [CR]'
		self.started = False
	
	def onInit(self):
		if self.started: return
		self.started = True
		self.setLoggedIn()
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.postSelected()
		self.setTheme()
		self.getControl(201).setEnabled(self.parent.parent.hasLogin())
		self.showThread()
		self.setFocusId(120)
	
	def setTheme(self):
		mtype = self.tid == "private_messages" and __language__(30151) or __language__(30130)
		self.getControl(103).setLabel('[B]%s[/B]' % mtype)
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
		
	def showThread(self,nopage=False):
		if nopage:
			page = ''
		else:
			page = '1'
			if __addon__.getSetting('open_thread_to_newest') == 'true': page = '-1'
		self.fillRepliesList(self.pageData.getPageNumber(page))
		
	def errorCallback(self,error):
		xbmcgui.Dialog().ok(__language__(30050),__language__(30131),error.message)
	
	def fillRepliesList(self,page=''):
		#page = int(page)
		#if page < 0: raise Exception()
		if self.tid == 'private_messages':
			t = self.getThread(FB.getPrivateMessages,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='PRIVATE MESSAGES')
			t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		else:
			t = self.getThread(FB.getReplies,finishedCallback=self.doFillRepliesList,errorCallback=self.errorCallback,name='POSTS')
			t.setArgs(self.tid,self.fid,page,lastid=self.lastid,pid=self.pid,callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def setMessageProperty(self,post,item,short=False):
		title = post.title or ''
		item.setProperty('title',title)
		item.setProperty('message',post.messageAsDisplay(short))
		
	def doFillRepliesList(self,replies,pageData):
		if not replies:
			self.setFocusId(201)
			if replies == None:
				LOG('GET REPLIES ERROR')
				xbmcgui.Dialog().ok(__language__(30050),__language__(30131),__language__(30053))
			return
		self.empty = False
		defAvatar = xbmc.translatePath(os.path.join(__addon__.getAddonInfo('path'),'resources','skins',THEME,'media','forum-browser-avatar-none.png'))
		#xbmcgui.lock()
		try:
			self.getControl(120).reset()
			if not self.topic: self.topic = pageData.topic
			if not self.tid: self.tid = pageData.tid
			self.setupPage(pageData)
			if __addon__.getSetting('reverse_sort') != 'true' or self.tid == 'private_messages': replies.reverse()
			self.posts = {}
			select = -1
			for post,idx in zip(replies,range(0,len(replies))):
				if self.pid and post.postId == self.pid: select = idx
				self.posts[post.postId] = post
				url = defAvatar
				if post.avatar: url = FB.makeURL(post.avatar)
				post.avatarFinal = url
				user = re.sub('<.*?>','',post.userName)
				item = xbmcgui.ListItem(label=user)
				if user == self.me: item.setInfo('video',{"Director":'me'})
				self.setMessageProperty(post,item,True)
				item.setProperty('post',post.postId)
				item.setProperty('avatar',url)
				item.setProperty('status',texttransform.convertHTMLCodes(post.status))
				item.setProperty('date',post.date)
				item.setProperty('online',post.online and 'online' or '')
				item.setProperty('postcount',post.postCount and str(post.postCount) or '')
				item.setProperty('activity',post.activity)
				item.setProperty('postnumber',post.postNumber and str(post.postNumber) or '')
				item.setProperty('joindate',post.joinDate)
				
				self.getControl(120).addItem(item)
				self.setFocusId(120)
			if select > -1: self.getControl(120).selectItem(int(select))
		except:
			#xbmcgui.unlock()
			ERROR('FILL REPLIES ERROR')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30133))
			raise
		#xbmcgui.unlock()
		if select > -1: self.postSelected(itemindex=select)
		
		self.getControl(104).setLabel('[B]%s[/B]' % self.topic)
		self.pid = ''
		self.setLoggedIn()
			
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
		post.tid = self.tid
		post.fid = self.fid
		w = openWindow(MessageWindow,"script-forumbrowser-message.xml" ,return_window=True,post=post,parent=self)
		self.setMessageProperty(post,item)
		self.setFocusId(120)
		if w.action:
			if w.action.action == 'CHANGE':
				self.topic = ''
				self.pid = w.action.pid
				self.tid = w.action.tid
				if w.action.pid: self.showThread(nopage=True)
				else: self.showThread()
			elif w.action.action == 'REFRESH':
				self.fillRepliesList(self.pageData.getPageNumber())
		del w
		
	def onClick(self,controlID):
		if controlID == 201:
			self.stopThread()
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
	
	def doMenu(self):
		item = self.getControl(120).getSelectedItem()
		post = self.posts.get(item.getProperty('post'))
		d = ChoiceMenu(__language__(30051))
		d.addItem('quote',__language__(30134))
		d.addItem('refresh',__language__(30054))
		if FB.canDelete(item.getLabel()):
			d.addItem('delete',__language__(30141))
		if FB.canEditPost(item.getLabel()):
			d.addItem('edit',__language__(30232))
		if self.threadItem and self.threadItem.getProperty('subscribed'):
			d.addItem('unsubscribe',__language__(30240))
		else:
			if FB.canSubscribeThread(self.tid):
				d.addItem('subscribe',__language__(30236))
		result = d.getResult()
		if not result: return
		if result == 'quote':
			self.stopThread()
			self.openPostDialog(post)
		elif result == 'refresh':
			self.stopThread()
			self.fillRepliesList(self.pageData.getPageNumber())
		elif result == 'edit':
			pm = FB.getPostForEdit(post.postId)
			pm.tid = self.tid
			if openPostDialog(editPM=pm):
				self.fillRepliesList(self.pageData.getPageNumber())
		elif result == 'delete':
			self.stopThread()
			self.deletePost()
		elif result == 'subscribe':
			if subscribeThread(self.tid): self.threadItem.setProperty('subscribed','subscribed')
		elif result == 'unsubscribe':
			if unSubscribeThread(self.tid): self.threadItem.setProperty('subscribed','')
		if self.empty: self.fillRepliesList()
			
	def deletePost(self):
		item = self.getControl(120).getSelectedItem()
		pid = item.getProperty('post')
		if not pid: return
		prog = xbmcgui.DialogProgress()
		prog.create(__language__(30149),__language__(30150))
		prog.update(0)
		try:
			if self.tid == 'private_messages':
				FB.deletePrivateMessageViaIndex(pid[2:])
			else:
				post = forumbrowser.PostMessage(pid,self.tid,self.fid)
				post = FB.deletePost(post)
				if post.error:
					xbmcgui.Dialog().ok('Failed','Failed to delete post:',post.error)
		except:
			prog.close()
			raise
		prog.close()
		self.fillRepliesList(self.pageData.getPageNumber())
		
	def openPostDialog(self,post=None):
		if post:
			item = self.getControl(120).getSelectedItem()
		else:
			if self.tid == 'private_messages':
				item = None
			else:
				if not self.getControl(120).size(): return
				item = self.getControl(120).getListItem(0)
		#if not item.getProperty('post'): item = self.getControl(120).getListItem(1)
		if item:
			pid = item.getProperty('post')
		else:
			pid = 0
		if openPostDialog(post,pid,self.tid,self.fid):
			self.fillRepliesList(self.pageData.getPageNumber('-1'))
	
	def gotoPage(self,page):
		self.stopThread()
		self.fillRepliesList(page)
		
	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)

def subscribeThread(tid):
	result = FB.subscribeThread(tid)
	if result == True:
		xbmcgui.Dialog().ok('Success','Subscribed to thread.')
	else:
		xbmcgui.Dialog().ok('Failed','Failed to subscribed to thread:',str(result))
	return result
		
def unSubscribeThread(tid):
	result = FB.unSubscribeThread(tid)
	if result == True:
		xbmcgui.Dialog().ok('Success','Unsubscribed from thread.')
	else:
		xbmcgui.Dialog().ok('Failed','Failed to unsubscribed from thread:',str(result))
	return result
				
######################################################################################
# Threads Window
######################################################################################
class ThreadsWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.parent = kwargs.get('parent')
		self.me = self.parent.getUsername() or '?'
		self.empty = True
		self.textBase = '%s'
		self.newBase = '[B]%s[/B]'
		self.highBase = '%s'
		self.forum_desc_base = '[I]%s[/I]'
		self.started = False
		PageWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		if self.started: return
		self.started = True
		self.setLoggedIn()
		self.setupPage(None)
		self.setStopControl(self.getControl(106))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.setTheme()
		self.fillThreadList()
		self.setFocus(self.getControl(120))
		
	def setTheme(self):
		self.desc_base = unicode.encode(__language__(30162)+' %s','utf8')
		self.getControl(103).setLabel(__language__(30160))
		self.getControl(104).setLabel(self.topic)
	
	def errorCallback(self,error):
		xbmcgui.Dialog().ok(__language__(30050),__language__(30161),error.message)
		
	def fillThreadList(self,page=''):
		if self.fid == 'subscriptions':
			t = self.getThread(FB.getSubscriptions,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='SUBSCRIPTIONS')
			t.setArgs(page,callback=t.progressCallback,donecallback=t.finishedCallback)
		else:
			t = self.getThread(FB.getThreads,finishedCallback=self.doFillThreadList,errorCallback=self.errorCallback,name='THREADS')
			t.setArgs(self.fid,page,callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def doFillThreadList(self,threads,pageData):
		if threads is None:
			LOG('GET THREADS ERROR')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30161),__language__(30053))
			return
		
		if not threads:
			LOG('Empty Forum')
			xbmcgui.Dialog().ok(__language__(30229),__language__(30230))
			return
		
		self.empty = False
		#xbmcgui.lock()
		try:
			self.getControl(120).reset()
			self.setupPage(pageData)
			if type(threads) == type(()):
				LOG('Thread contains forums')
				self.addForums(threads[0])
				self.addThreads(threads[1])
			else:
				self.addThreads(threads)
		except:
			#xbmcgui.unlock()
			ERROR('FILL THREAD ERROR')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30163))
		#xbmcgui.unlock()
		self.setLoggedIn()
			
	def addThreads(self,threads):
		for t in threads:
			if hasattr(t,'groupdict'):
				tdict = t.groupdict()
			else:
				tdict = t
			tid = tdict.get('threadid','')
			starter = tdict.get('starter','Unknown')
			title = tdict.get('title','')
			title = texttransform.convertHTMLCodes(MC.tagFilter.sub('',title))
			last = tdict.get('lastposter','')
			fid = tdict.get('forumid','')
			sticky = tdict.get('sticky') and 'sticky' or ''
			reply_count = str(tdict.get('reply_number','0') or '0')
			if starter == self.me: starterbase = self.highBase
			else: starterbase = self.textBase
			#title = (tdict.get('new_post') and self.newBase or self.textBase) % title
			item = xbmcgui.ListItem(label=starterbase % starter,label2=title)
			if tdict.get('new_post'): item.setProperty('unread','unread')
			item.setInfo('video',{"Genre":sticky})
			item.setInfo('video',{"Director":starter == self.me and 'me' or ''})
			item.setInfo('video',{"Studio":last == self.me and 'me' or ''})
			item.setProperty("id",tid)
			item.setProperty("fid",fid)
			if last:
				last = self.desc_base % last
				short = tdict.get('short_content','')
				if short: last += '[CR]' + re.sub('<[^>]+?>','',texttransform.convertHTMLCodes(short))[:100]
			else:
				last = re.sub('<[^>]+?>','',texttransform.convertHTMLCodes(tdict.get('short_content','')))
			item.setProperty("last",last)
			item.setProperty("lastid",tdict.get('lastid',''))
			item.setProperty('title',title)
			item.setProperty('reply_count',reply_count)
			item.setProperty('subscribed',tdict.get('subscribed') and 'subscribed' or '')
			self.getControl(120).addItem(item)
			self.setFocusId(120)
			
	def addForums(self,forums):
		for f in forums:
			fdict = f.groupdict()
			fid = fdict.get('forumid','')
			title = fdict.get('title',__language__(30050))
			desc = fdict.get('description') or __language__(30172)
			text = self.textBase
			title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?')
			item = xbmcgui.ListItem(label=self.textBase % __language__(30164),label2=text % title)
			item.setInfo('video',{"Genre":'is_forum'})
			item.setProperty("last",self.forum_desc_base % texttransform.convertHTMLCodes(MC.tagFilter.sub('',MC.brFilter.sub(' ',desc))))
			item.setProperty("title",title)
			item.setProperty("id",fid)
			item.setProperty("fid",fid)
			item.setProperty("is_forum",'True')
			self.getControl(120).addItem(item)
				
	def openRepliesWindow(self):
		item = self.getControl(120).getSelectedItem()
		item.setProperty('unread','')
		tid = item.getProperty('id')
		fid = item.getProperty('fid') or self.fid
		lastid = item.getProperty('lastid')
		topic = item.getProperty('title')
		reply_count = item.getProperty('reply_count')
		if item.getProperty('is_forum') == 'True':
			self.fid = fid
			self.topic = topic
			self.setTheme()
			self.fillThreadList()
			self.setFocus(self.getControl(120))
		else:
			openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,tid=tid,fid=fid,lastid=lastid,topic=topic,reply_count=reply_count,item=item,parent=self)

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
		if self.getFocusId() != 120: return
		item = self.getControl(120).getSelectedItem()
		d = ChoiceMenu('Options')
		if item.getProperty('subscribed'):
			d.addItem('unsubscribe', __language__(30240))
		else:
			if FB.canSubscribeThread(item.getProperty('id')):
				d.addItem('subscribe', __language__(30236))
		
		result = d.getResult()
		if not result: return
		if result == 'subscribe':
			if subscribeThread(item.getProperty('id')): item.setProperty('subscribed','subscribed')
		elif result == 'unsubscribe':
			if unSubscribeThread(item.getProperty('id')): item.setProperty('subscribed','')
		
	def gotoPage(self,page):
		self.stopThread()
		self.fillThreadList(page)
		
	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)

######################################################################################
# Forums Window
######################################################################################
class ForumsWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		BaseWindow.__init__( self, *args, **kwargs )
		#FB.setLogin(self.getUsername(),self.getPassword(),always=__addon__.getSetting('always_login') == 'true')
		self.parent = self
		self.empty = True
		self.textBase = '%s'
		self.subTextBase = '[I]%s [/I]'
		self.desc_base = '%s'
		self.setAsMain()
		self.started = False
	
	def getUsername(self):
		return __addon__.getSetting('login_user_' + FB.getForumID().replace('.','_'))
		
	def getPassword(self):
		key = 'login_pass_' + FB.getForumID().replace('.','_')
		return passmanager.getPassword(key, self.getUsername())
		#return __addon__.getSetting('login_pass_' + FB.getForumID().replace('.','_'))
		
	def hasLogin(self):
		return self.getUsername() != '' and self.getPassword() != ''
		
	def onInit(self):
		self.setLoggedIn() #So every time we return to the window we check
		if self.started: return
		self.started = True
		self.getControl(112).setVisible(False)
		self.setStopControl(self.getControl(105))
		self.setProgressCommands(self.startProgress,self.setProgress,self.endProgress)
		self.resetForum()
		self.fillForumList(True)
		self.setFocusId(120)
		
	def setTheme(self):
		self.getControl(103).setLabel(__language__(30170))
		self.getControl(104).setLabel(FB.forum)
		
	def errorCallback(self,error):
		xbmcgui.Dialog().ok(__language__(30050),__language__(30171),error.message)
		self.setFocusId(202)
	
	def fillForumList(self,first=False):
		self.setTheme()
		if first and __addon__.getSetting('auto_thread_subscriptions_window') == 'true':
			if self.hasLogin() and FB.hasSubscriptions():
				FB.getForums(callback=self.setProgress,donecallback=self.doFillForumList)
				self.openSubscriptionsWindow()
				return
			
		t = self.getThread(FB.getForums,finishedCallback=self.doFillForumList,errorCallback=self.errorCallback,name='FORUMS')
		t.setArgs(callback=t.progressCallback,donecallback=t.finishedCallback)
		t.start()
		
	def doFillForumList(self,forums,logo,pm_counts):
		self.endProgress()
		if logo: self.getControl(250).setImage(logo)
		if not forums:
			xbmcgui.Dialog().ok(__language__(30050),__language__(30171),__language__(30053),'Bad Page Data')
			self.setFocusId(202)
			return
		self.empty = True
		
		try:
			#xbmcgui.lock()
			self.getControl(120).reset()
			self.setPMCounts(pm_counts)
			
			for f in forums:
				self.empty = False
				if hasattr(f,'groupdict'):
					fdict = f.groupdict()
				else:
					fdict = f
				fid = fdict.get('forumid','')
				title = fdict.get('title',__language__(30050))
				desc = fdict.get('description') or __language__(30172)
				sub = fdict.get('subforum')
				if sub:
					text = self.subTextBase
					desc = __language__(30173)
				else:
					text = self.textBase
				title = texttransform.convertHTMLCodes(re.sub('<[^<>]+?>','',title) or '?')
				item = xbmcgui.ListItem(label=text % title)
				item.setInfo('video',{"Genre":sub and 'sub' or ''})
				item.setProperty("description",self.desc_base % texttransform.convertHTMLCodes(MC.tagFilter.sub('',MC.brFilter.sub(' ',desc))))
				item.setProperty("topic",title)
				item.setProperty("id",fid)
				self.getControl(120).addItem(item)
				self.setFocusId(120)
		except:
			#xbmcgui.unlock()
			ERROR('FILL FORUMS ERROR')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30174))
			self.setFocusId(202)
		if self.empty: self.setFocusId(202)
		#xbmcgui.unlock()
		self.setLoggedIn()
			
	def setPMCounts(self,pm_counts=None):
		disp = ''
		if not pm_counts: pm_counts = FB.getPMCounts()
		if pm_counts: disp = ' (%s/%s)' % (pm_counts.get('unread','?'),pm_counts.get('total','?'))
		self.getControl(203).setLabel(__language__(3009) + disp)
		self.setLoggedIn()
		
	def openPMWindow(self):
		openWindow(RepliesWindow,"script-forumbrowser-replies.xml" ,tid='private_messages',topic=__language__(30176),parent=self)
		self.setPMCounts(FB.getPMCounts())
		
	def openThreadsWindow(self):
		item = self.getControl(120).getSelectedItem()
		if not item: return False
		fid = item.getProperty('id')
		topic = item.getProperty('topic')
		w = ThreadsWindow("script-forumbrowser-threads.xml" , __addon__.getAddonInfo('path'), THEME,fid=fid,topic=topic,parent=self)
		w.doModal()
		del w
		self.setPMCounts(FB.getPMCounts())
		return True
		
	def openSubscriptionsWindow(self):
		fid = 'subscriptions'
		topic = __language__(30175)
		w = ThreadsWindow("script-forumbrowser-threads.xml" , __addon__.getAddonInfo('path'), THEME,fid=fid,topic=topic,parent=self)
		w.doModal()
		del w
		self.setPMCounts(FB.getPMCounts())
		
	def changeForum(self):
		forum = askForum()
		if not forum: return False
		self.stopThread()
		LOG('------------------ CHANGING FORUM FROM: %s TO: %s' % (FB.getForumID(),forum)) 
		if not getForumBrowser(forum): return False
		if not FB: return
		self.resetForum()
		self.fillForumList()
		__addon__.setSetting('last_forum',FB.getForumID())
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
			if self.changeForum(): return
		elif controlID == 120:
			if not self.empty: self.stopThread()
			self.openThreadsWindow()
		elif controlID == 105:
			self.stopThread()
			return
		if BaseWindow.onClick(self, controlID): return
		if self.empty: self.fillForumList()
	
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			pass
		elif action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2:
			action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			if not self.preClose(): return
		BaseWindow.onAction(self,action)
		
	def preClose(self):
		if not __addon__.getSetting('ask_close_on_exit') == 'true': return True
		return xbmcgui.Dialog().yesno('Really Exit?','Really exit?')
		
	def resetForum(self,hidelogo=True):
		FB.setLogin(self.getUsername(),self.getPassword(),always=__addon__.getSetting('always_login') == 'true')
		self.getControl(201).setEnabled(self.hasLogin() and FB.hasSubscriptions())
		self.getControl(203).setEnabled(self.hasLogin() and FB.hasPM())
		if hidelogo: self.getControl(250).setImage('')
		__addon__.setSetting('last_forum',FB.getForumID())
		
	def setLoggedIn(self):
		if FB.isLoggedIn():
			self.getControl(111).setColorDiffuse('FF00FF00')
		else:
			self.getControl(111).setColorDiffuse('FF555555')
		self.getControl(160).setLabel(FB.loginError)
		self.getControl(112).setVisible(FB.SSL)
		
	def openSettings(self):
		mode = __addon__.getSetting('color_mode')
		oldLogin = self.getUsername() + self.getPassword()
		doSettings()
		if not oldLogin == self.getUsername() + self.getPassword():
			self.resetForum(False)
			self.setPMCounts()
		self.setLoggedIn()
		self.resetForum(False)
		if mode !=  __addon__.getSetting('color_mode'): self.fillForumList()

def openWindow(windowClass,xmlFilename,return_window=False,*args,**kwargs):
	theme = THEME
	path = __addon__.getAddonInfo('path')
	if not getSetting('use_skin_mods',True):
		theme = 'Current'
		src = os.path.join(path,'resources','skins',THEME,'720p',xmlFilename)
		path = __addon__.getAddonInfo('profile')
		skin = os.path.join(xbmc.translatePath(path),'resources','skins',theme,'720p')
		if not os.path.exists(skin): os.makedirs(skin)
		xml = open(src,'r').read()
		open(os.path.join(skin,xmlFilename),'w').write(xml.replace('ForumBrowser-font','font'))
	w = windowClass(xmlFilename,path,theme,*args,**kwargs)
	w.doModal()
	if return_window: return w
	del w
	return None


	
def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

def getForumPath(forumID):
	path = os.path.join(FORUMS_PATH,forumID)
	if os.path.exists(path): return path
	path = os.path.join(FORUMS_STATIC_PATH,forumID)
	if os.path.exists(path): return path
	return None
	
def askForum(just_added=False,just_favs=False,caption='Choose Forum'):
	favs = getFavorites()
	ft = os.listdir(FORUMS_STATIC_PATH)
	hidden = getHiddenForums()
	flist_tmp = []
	for f in ft:
		if not f in hidden: flist_tmp.append(f)
	flist2_tmp = os.listdir(FORUMS_PATH)
	rest = flist_tmp + flist2_tmp
	if favs:
		for f in favs:
			if f in rest: rest.pop(rest.index(f))
		favs.append('')
	if just_favs:
		if not favs: return None
		whole = favs[:-1]
	elif just_added:
		whole = flist2_tmp
	else:
		whole = favs + rest
	menu = ImageChoiceMenu(caption)
	for f in whole:
		if not f.startswith('.'):
			if not f:
				menu.addSep()
				continue
			path = getForumPath(f)
			if not path: continue
			ff = open(path,'r')
			name = ff.readline().strip('\n')[1:]
			desc = '[CR]' + ff.readline().strip('\n')[1:]
			line = ff.readline()
			if not 'url:logo=' in line: line = ff.readline()
			if not 'url:logo=' in line: line = ff.readline()
			logo = line.strip('\n').split('=')[-1]
			ff.close()
			menu.addItem(f, name,logo,desc)
	forum = menu.getResult('script-forumbrowser-forum-select.xml')
	return forum

def setLogins():
	forumID = askForum()
	if not forumID: return
	user = doKeyboard(__language__(30201),__addon__.getSetting('login_user_' + forumID.replace('.','_')))
	if user is None: return
	password = passmanager.getPassword('login_pass_' + forumID.replace('.','_'), __addon__.getSetting('login_user_' + forumID.replace('.','_')))
	password = doKeyboard(__language__(30202),password,True)
	if password is None: return
	__addon__.setSetting('login_user_' + forumID.replace('.','_'),user)
	key = 'login_pass_' + forumID.replace('.','_')
	if password:
		passmanager.savePassword(key, user, password)
	else:
		__addon__.setSetting(key,'')
	if not user and not password:
		xbmcgui.Dialog().ok('Login Cleared','Username and password cleared.')
	else:
		xbmcgui.Dialog().ok('Login Set','Username and password set.')
	
	
def doSettings():
	dialog = ChoiceMenu(__language__(30203))
	dialog.addItem('addfavorite',__language__(30223))
	dialog.addItem('removefavorite',__language__(30225))
	dialog.addItem('addcurrentonline',__language__(30241))
	dialog.addItem('addforum',__language__(30222))
	dialog.addItem('addonline',__language__(30226))
	dialog.addItem('removeforum',__language__(30224))
	dialog.addItem('setlogins',__language__(30204))
	dialog.addItem('settings',__language__(30203))
	result = dialog.getResult()
	if not result: return
	if result == 'addfavorite': addFavorite()
	elif result == 'removefavorite': removeFavorite()
	elif result == 'addcurrentonline': addTapatalkForum(current=True)
	elif result == 'addforum': addTapatalkForum()
	elif result == 'addonline': addForumFromOnline()
	elif result == 'removeforum': removeForum()
	elif result == 'setlogins': setLogins()
#	elif result == 'register': registerForum()
	elif result == 'settings':
		__addon__.openSettings()
		global DEBUG
		DEBUG = __addon__.getSetting('debug') == 'true'
		tapatalk.DEBUG = DEBUG
		MC.resetRegex()
		checkForSkinMods()
	
def registerForum():
	url = FB.getRegURL()
	LOG('Registering - URL: ' + url)
	webviewer.getWebResult(url,dialog=True)

def addFavorite():
	forum = FB.getForumID()
	favs = getFavorites()
	if forum in favs: return
	favs.append(forum)
	__addon__.setSetting('favorites','*:*'.join(favs))
	xbmcgui.Dialog().ok('Added','Current forum added to favorites!')
	
def removeFavorite():
	forum = askForum(just_favs=True)
	if not forum: return
	favs = getFavorites()
	if not forum in favs: return
	favs.pop(favs.index(forum))
	__addon__.setSetting('favorites','*:*'.join(favs))
	xbmcgui.Dialog().ok('Removed','Forum removed from favorites.')
	
def getFavorites():
	favs = __addon__.getSetting('favorites')
	if favs:
		favs = favs.split('*:*')
	else:
		favs = []
	return favs
	
def addTapatalkForum(current=False):
	dialog = xbmcgui.DialogProgress()
	dialog.create('Add Forum')
	dialog.update(0,'Enter Name/Address')
	try:
		if current:
			ftype = FB.prefix[:2]
			forum = FB.forum
			url = FB._url
			url = tapatalk.testForum(url)
			if url: pageURL = url.split('/mobiquo',1)[0]
			if not url:
				import forumrunner
				url = forumrunner.testForum(url)
			if url: pageURL = url.split('/forumrunner',1)[0]
			if not url:
				xbmcgui.Dialog().ok('Failed','Forum not found or not compatible')
				return
		else:
			forum = doKeyboard('Enter forum name or address')
			if forum == None: return
			dialog.update(10,'Testing Forum')
			
			url = tapatalk.testForum(forum)
			ftype = ''
			label = ''
			if url:
				ftype = 'TT'
				label = 'Tapatalk'
				pageURL = url.split('/mobiquo',1)[0]
			else:
				import forumrunner #@Reimport
				url = forumrunner.testForum(forum)
				if url:
					ftype = 'FR'
					label = 'Forumrunner'
					pageURL = url.split('/forumrunner',1)[0]
			
			if not url:
				xbmcgui.Dialog().ok('Failed','Forum not found or not compatible')
				return
		
			xbmcgui.Dialog().ok('Found','Forum %s found' % forum,'Type: ' + label,url)
			forum = url.split('http://',1)[-1].split('/',1)[0]
			
		dialog.update(20,'Getting Description And Images')
		info = forumbrowser.HTMLPageInfo(pageURL)
		images = []
		if info.isValid:
			tmp_desc = info.description(info.title(''))
			tmp_desc = texttransform.convertHTMLCodes(tmp_desc).strip()
			images = info.images()
		dialog.update(30,'Enter Description')
		desc = doKeyboard('Enter Description',default=tmp_desc)
		if not desc: desc = tmp_desc
		dialog.update(40,'Choose Logo')
		logo = chooseLogo(forum,images)
		LOG('Adding Forum: %s at URL: %s' % (forum,url))
		saveForum(ftype,ftype + '.' + forum,forum,desc,url,logo)
		dialog.update(60,'Add To Online Database')
		addForumToOnlineDatabase(forum,url,desc,logo,ftype,dialog=dialog)
	finally:
		dialog.close()
	
def saveForum(ftype,forumID,name,desc,url,logo):
	if ftype == 'TT':
		open(os.path.join(FORUMS_PATH,forumID),'w').write('#%s\n#%s\nurl:tapatalk_server=%s\nurl:logo=%s' % (name,desc,url,logo))
	else:
		open(os.path.join(FORUMS_PATH,forumID),'w').write('#%s\n#%s\nurl:forumrunner_server=%s\nurl:logo=%s' % (name,desc,url,logo))
	
def addForumFromOnline():
	odb = forumbrowser.FBOnlineDatabase()
	flist = odb.getForumList()
	menu = ImageChoiceMenu('Choose Forum')
	for f in flist:
		menu.addItem(f, f.get('name'), f.get('logo'), '[CR]' + f.get('desc'))
	for f in getHiddenForums():
		name = f
		if f.startswith('TT.') or f.startswith('FR.'): name = f[3:]
		menu.addItem(f,name,'','[CR]Hidden (Built-in)')
	f = menu.getResult('script-forumbrowser-forum-select.xml')
	if not f: return
	if not isinstance(f,dict):
		unHideForum(f)
		return
	saveForum(f['type'],f['type']+'.'+f['name'],f['name'],f.get('desc',''),f['url'],f.get('logo',''))
	xbmcgui.Dialog().ok('Added','Forum added: ' + f['name'])
	
def addForumToOnlineDatabase(name,url,desc,logo,ftype,dialog=None):
	if not xbmcgui.Dialog().yesno('Add To Database?','Share to the Forum Browser','online database?'): return
	LOG('Adding Forum To Online Database: %s at URL: %s' % (name,url))
	if dialog: dialog.update(80,'Saving To Database')
	odb = forumbrowser.FBOnlineDatabase()
	msg = odb.addForum(name, url, logo, desc, ftype)
	if msg == 'OK':
		xbmcgui.Dialog().ok('Added','Forum added successfully')
	else:
		xbmcgui.Dialog().ok('Not Added','Forum not added:',str(msg).title())
		LOG('Forum Not Added: ' + str(msg))
	
def chooseLogo(forum,image_urls):
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
	menu = ImageChoiceMenu('Choose Logo')
	for url in image_urls: menu.addItem(url, url, url)
	url = menu.getResult()
	return url or ''
	
def getHiddenForums():
	flist = __addon__.getSetting('hidden_static_forums')
	if flist: flist = flist.split('*:*')
	else: flist = []
	return flist

def unHideForum(forum):
	flist = getHiddenForums()
	if forum in flist: flist.pop(flist.index(forum))
	__addon__.setSetting('hidden_static_forums','*:*'.join(flist))
	
def removeForum():
	forum = askForum(caption='Choose Forum To Remove')
	if not forum: return
	path = os.path.join(FORUMS_STATIC_PATH,forum)
	if os.path.exists(path):
		flist = getHiddenForums()
		if not forum in flist: flist.append(forum)
		__addon__.setSetting('hidden_static_forums','*:*'.join(flist))
		return
	path = os.path.join(FORUMS_PATH,forum)
	if not os.path.exists(path): return
	os.remove(path)
	xbmcgui.Dialog().ok('Removed','Forum removed.')
	
class ImageChoiceDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.result = None
		self.items = kwargs.get('items')
		self.caption = kwargs.get('caption')
		xbmcgui.WindowXMLDialog.__init__( self )
	
	def onInit(self):
		clist = self.getControl(120)
		clist.reset()
		for i in self.items:
			item = xbmcgui.ListItem(label=i['disp'],label2=i['disp2'],thumbnailImage=i['icon'])
			if i['sep']: item.setProperty('SEPARATOR','SEPARATOR')
			clist.addItem(item)
			
		self.getControl(300).setLabel(self.caption)
		self.setFocus(clist)
		
	def onAction(self,action):
		if action == 92 or action == 10:
			self.close()
		elif action == 7:
			self.finish()
	
	def onClick( self, controlID ):
		if controlID == 120:
			self.finish()
			
	def finish(self):
		self.result = self.getControl(120).getSelectedPosition()
		self.close()
		
	def onFocus( self, controlId ): self.controlId = controlId
	
class ChoiceMenu():
	def __init__(self,caption):
		self.caption = caption
		self.items = []
		
	def addItem(self,ID,display,icon='',display2='',sep=False):
		if not ID: return self.addSep()
		self.items.append({'id':ID,'disp':display,'disp2':display2,'icon':icon,'sep':sep})
		
	def addSep(self):
		if self.items: self.items[-1]['sep'] = True
	
	def getChoiceIndex(self):
		options = []
		for i in self.items: options.append(i.get('disp'))
		return xbmcgui.Dialog().select(self.caption,options)
	
	def getResult(self):
		idx = self.getChoiceIndex()
		if idx < 0: return None
		return self.items[idx]['id']
		
class ImageChoiceMenu(ChoiceMenu):
	def getResult(self,windowFile='script-forumbrowser-image-dialog.xml'):
		w = ImageChoiceDialog(windowFile , xbmc.translatePath(__addon__.getAddonInfo('path')), 'Default',items=self.items,caption=self.caption)
		w.doModal()
		result = w.result
		del w
		if result == None: return None
		return self.items[result]['id']
	
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
	
def copyKeyboardModImages(skinPath):
	dst = os.path.join(skinPath,'media','forum-browser-keyboard')
	if os.path.exists(dst): return
	os.makedirs(dst)
	src = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'keyboard','images')
	import shutil
	for f in os.listdir(src):
		s = os.path.join(src,f)
		d = os.path.join(dst,f)
		if not os.path.exists(d) and not f.startswith('.'): shutil.copy(s,d)

def copyFont(sourceFontPath,skinPath):
	dst = os.path.join(skinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	if os.path.exists(dst): return
	import shutil
	shutil.copy(sourceFontPath,dst)
	
def copyTree(source,target):
	import shutil
	shutil.copytree(source, target)
		
def checkForSkinMods():
	if __addon__.getSetting('use_skin_mods') != 'true': return			
	skinPath = xbmc.translatePath('special://skin')
	font = os.path.join(skinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	if os.path.exists(font): return
	yes = xbmcgui.Dialog().yesno('Skin Mods','Recommended skin modifications not installed.','(Requires XBMC restart to take effect.)','Install now?')
	if not yes:
		__addon__.setSetting('user_skin_mods','false')	
		return
	LOG('Installing Skin Mods')
	doModKeyboard('',no_keyboard=True)

def doModKeyboard(prompt,default='',hidden=False,no_keyboard=False):
	#restart = False
	fbPath = xbmc.translatePath(__addon__.getAddonInfo('path'))
	localAddonsPath = os.path.join(xbmc.translatePath('special://home'),'addons')
	skinPath = xbmc.translatePath('special://skin')
	if skinPath.endswith(os.path.sep): skinPath = skinPath[:-1]
	currentSkin = os.path.basename(skinPath)
	localSkinPath = os.path.join(localAddonsPath,currentSkin)
	
	if not os.path.exists(localSkinPath):
		yesno = xbmcgui.Dialog().yesno('Skin Mod Install',currentSkin + ' skin not installed in user path.','Click Yes to copy,','click No to Abort')
		if not yesno: return
		dialog = xbmcgui.DialogProgress()
		dialog.create('Copying Files','Please wait...')
		try:
			
			copyTree(skinPath,localSkinPath)
		except:
			err = ERROR('Failed to copy skin to user directory')
			xbmcgui.Dialog().ok('Error',err,'Failed to copy files, aborting.')
			return
		finally:
			dialog.close()
		#restart = True
		xbmcgui.Dialog().ok('Success','Files copied.','XBMC needs to be restarted','for mod to take effect')
	skinPath = localSkinPath
	
	sourcePath = os.path.join(fbPath,'keyboard','DialogKeyboard.xml')
	sourceFontXMLPath = os.path.join(fbPath,'keyboard','Font-720p.xml')
	sourceFontPath = os.path.join(fbPath,'keyboard','ForumBrowser-DejaVuSans.ttf')
	
	dialogPath = os.path.join(skinPath,'720p','DialogKeyboard.xml')
	backupPath = os.path.join(skinPath,'720p','DialogKeyboard.xml.FBbackup')
	fontPath = os.path.join(skinPath,'720p','Font.xml')
	fontBackupPath = os.path.join(skinPath,'720p','Font.xml.FBbackup')
	if not os.path.exists(dialogPath):
		dialogPath = dialogPath.replace('720p','1080i')
		backupPath = backupPath.replace('720p','1080i')
		fontPath = fontPath.replace('720p','1080i')
		fontBackupPath = fontBackupPath.replace('720p','1080i')
		sourceFontXMLPath = sourceFontXMLPath.replace('720p','1080i')
	
	if DEBUG:
		LOG('Local Addons Path: %s' % localAddonsPath)
		LOG('Current skin: %s' % currentSkin)
		LOG('Skin path: %s' % skinPath)
		LOG('Target path: %s' % dialogPath)
		LOG('Source path: %s' % sourcePath)
	
	copyKeyboardModImages(skinPath)
	copyFont(sourceFontPath,skinPath)
	
	if not os.path.exists(backupPath):
		if DEBUG: LOG('Creating backup of original skin file: ' + backupPath)
		open(backupPath,'w').write(open(dialogPath,'r').read())
		
	if not os.path.exists(fontBackupPath):
		if DEBUG: LOG('Creating backup and replacing original skin file: ' + fontBackupPath)
		open(fontBackupPath,'w').write(open(fontPath,'r').read())
		original = open(fontPath,'r').read()
		modded = original.replace('<font>',open(sourceFontXMLPath,'r').read() + '<font>',1)
		open(fontPath,'w').write(modded)
	
	if no_keyboard: return
	
	os.remove(dialogPath)
	
	open(dialogPath,'w').write(open(sourcePath,'r').read())
	ret = doKeyboard(prompt,default,hidden)
	
	os.remove(dialogPath)
	open(dialogPath,'w').write(open(backupPath,'r').read())
	#Remove added files
	os.remove(backupPath)
	return ret

def getForumList():
	ft = os.listdir(FORUMS_STATIC_PATH)
	ft2 = os.listdir(FORUMS_PATH)
	flist = []
	for f in ft + ft2:
		if not f.startswith('.'):
			if not f in flist: flist.append(f)
	return flist

def checkPasswordEncryption():
	if __addon__.getSetting('passwords_encrypted') == 'true': return
	__addon__.setSetting('passwords_encrypted','true')
	flist = getForumList()
	for f in flist:
		key = 'login_pass_' + f.replace('.','_')
		user = __addon__.getSetting('login_user_' + f.replace('.','_'))
		if not user: continue
		password = __addon__.getSetting(key)
		if not password: continue
		LOG('Encrypting password for: ' + f)
		passmanager.savePassword(key, user, password)
	
def getForumBrowser(forum=None):
	if not forum: forum = __addon__.getSetting('last_forum') or 'TT.forum.xbmc.org'
	global FB
	global FBMODULE
	global MC
	if forum.startswith('TT.'):
		try:
			FB = tapatalk.TapatalkForumBrowser(forum,always_login=__addon__.getSetting('always_login') == 'true')
		except:
			err = ERROR('getForumBrowser(): Tapatalk')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30171),err)
			return False
		FBMODULE = tapatalk
	elif forum.startswith('FR.'):
		try:
			import forumrunner
			FB = forumrunner.ForumrunnerForumBrowser(forum,always_login=__addon__.getSetting('always_login') == 'true')
		except:
			err = ERROR('getForumBrowser(): Forumrunner')
			xbmcgui.Dialog().ok(__language__(30050),__language__(30171),err)
			return False
		FBMODULE = forumrunner
	else:
		import parserbrowser
		FB = parserbrowser.ParserForumBrowser(forum,always_login=__addon__.getSetting('always_login') == 'true')
		FBMODULE = parserbrowser.scraperbrowser
	MC = texttransform.MessageConverter(FB)
	FBMODULE.MC = MC
	FBMODULE.FB = FB
	return True

######################################################################################
# Startup
######################################################################################
if sys.argv[-1] == 'settings':
	doSettings()
else:
	checkForSkinMods()
	checkPasswordEncryption()
	
	getForumBrowser()

	TD = ThreadDownloader()
	
	w = ForumsWindow("script-forumbrowser-forums.xml" , __addon__.getAddonInfo('path'), THEME)
	w.doModal()
	del w
	#sys.modules.clear()
	