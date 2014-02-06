import os, sys, re, fnmatch, binascii, xbmc, xbmcgui
import util, asyncconnections, mods
from xbmcconstants import *  # @UnusedWildImport
from lib.forumbrowser import forumbrowser

DEBUG = None
CACHE_PATH = None
GLOBAL_WINDOW = None

def clearDirFiles(filepath):
	if not os.path.exists(filepath): return
	for f in os.listdir(filepath):
		f = os.path.join(filepath,f)
		if os.path.isfile(f): os.remove(f)
				
def doKeyboard(prompt,default='',hidden=False,mod=False,smilies=False):
	if mod: setGlobalSkinProperty('ForumBrowser_modKeyboard','1') #I set the home window, because that's the only way I know to get it to work before the window displays
	if smilies is not False:
		if smilies: saveSmilies(smilies)
		setGlobalSkinProperty('FB_smiley_0',forumbrowser.getSmiley(':)')[0])
		setGlobalSkinProperty('FB_smiley_1',forumbrowser.getSmiley(':(')[0])
		setGlobalSkinProperty('FB_smiley_2',forumbrowser.getSmiley(';)')[0])
		setGlobalSkinProperty('FB_smiley_3',forumbrowser.getSmiley(':D')[0])
		setGlobalSkinProperty('FB_smiley_4',forumbrowser.getSmiley(':P')[0])
		setGlobalSkinProperty('FB_smiley_5',forumbrowser.getSmiley(':o')[0])
		setGlobalSkinProperty('FB_smiley_6',forumbrowser.getSmiley(':-/')[0])
		setGlobalSkinProperty('FB_smiley_7',forumbrowser.getSmiley('8-)')[0])
	else:
		setGlobalSkinProperty('FB_smiley_0','')
		
	setGlobalSkinProperty('ForumBrowser_siteSmilies',smilies and '1' or '')
		
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	setGlobalSkinProperty('ForumBrowser_modKeyboard','0') #I set the home window, because that's the only way I know to get it to work before the window displays
	if not keyboard.isConfirmed(): return None
	return keyboard.getText()

def openWindow(windowClass,xmlFilename,return_window=False,modal=True,theme=None,*args,**kwargs):
	setGlobalSkinProperty('ForumBrowser_hidePNP',util.getSetting('hide_pnp',False) and '1' or '0') #I set the home window, because that's the only way I know to get it to work before the window displays
	if util.getSetting('hide_pnp',False):
		setGlobalSkinProperty('ForumBrowser_slideUpOnVideo','0')
	else:
		setGlobalSkinProperty('ForumBrowser_slideUpOnVideo',util.getSetting('slide_up_on_video',False) and '1' or '0') #I set the home window, because that's the only way I know to get it to work before the window displays
		
	THEME = util.getSavedTheme(get_current=True)
	path = util.__addon__.getAddonInfo('path')
	res = '720p'
	src = os.path.join(path,'resources','skins',THEME,res,xmlFilename)
	src2 = os.path.join(path,'resources','skins',theme or THEME,res,xmlFilename)
	if os.path.exists(src):
		theme = THEME
	elif not os.path.exists(src2):
		theme = 'Sequel'
		res = '720p'
	rightAlign = util.getSetting('current_right_align',False)
	
	if not util.getSetting('use_skin_mods',True):
		src = os.path.join(path,'resources','skins',theme,res,xmlFilename)
		skin = os.path.join(xbmc.translatePath(path),'resources','skins',theme,res)
		xml = open(src,'r').read()
		xmlFilename = 'script-forumbrowser-current.xml'
		if rightAlign: xml = rightAlignXML(xml)
		open(os.path.join(skin,xmlFilename),'w').write(mods.replaceFonts(xml))
	elif rightAlign:
		src = os.path.join(path,'resources','skins',theme,res,xmlFilename)
		skin = os.path.join(xbmc.translatePath(path),'resources','skins',theme,res)
		xml = open(src,'r').read()
		xmlFilename = 'script-forumbrowser-current.xml'
		open(os.path.join(skin,xmlFilename),'w').write(rightAlignXML(xml))
		
	w = windowClass(xmlFilename,path,theme,*args,**kwargs)
	if modal:
		w.doModal()
	else:
		w.show()
	if return_window: return w
	del w
	return None

def alignChanged():
	if util.getSetting('current_right_align',False) != util.getSetting('last_right_align',False):
		util.setSetting('last_right_align',util.getSetting('current_right_align',False))
		return True
	return False

def rightAlignXML(xml):
	if 'IGNORE_RIGHT_ALIGN' in xml: return xml
	from BeautifulSoup import BeautifulStoneSoup  # @UnresolvedImport
	BeautifulStoneSoup.NESTABLE_TAGS['control']=[]
	soup = BeautifulStoneSoup(xml)
	for control in soup.findAll('control',attrs={'type':['label','textbox']}):
		align = control.find('align')
		if align and align.contents[0] == 'left':
			try:
				align.contents[0].replaceWith('right')
				if control['type'] == 'label':
					width = int(control.find('width').contents[0])
					posx = int(control.find('posx').contents[0])
					posx += width
					control.find('posx').contents[0].replaceWith(str(posx))
			except:
				print 'ERROR'
	return unicode(soup)
			
def showMessage(caption,text,text2='',text3='',error=False,success=None,scroll=False):
	if text2: text += '[CR]' + text2
	if text3: text += '[CR]' + text3
	xmlFilename = 'script-forumbrowser-message-dialog.xml'
	THEME = util.getSavedTheme(get_current=True)
	path = xbmc.translatePath(util.__addon__.getAddonInfo('path'))
	theme = 'Default'
	if os.path.exists(os.path.join(path,'resources','skins',THEME,'720p',xmlFilename)): theme = THEME
	w = MessageDialog(xmlFilename ,path,theme,caption=caption,text=text,error=error,success=success,scroll=scroll)
	if util.getSetting('video_pause_on_dialog',True): util.PLAYER.pauseStack()
	w.doModal()
	del w
	if util.getSetting('video_pause_on_dialog',True): util.PLAYER.resumeStack()

def showMessageSilent(caption,text,text2='',text3='',error=False,success=None,scroll=False): pass

def loadHelp(helpfile,as_list=False):
	lang = xbmc.getLanguage().split(' ',1)[0]
	addonPath = xbmc.translatePath(util.__addon__.getAddonInfo('path'))
	helpfilefull = os.path.join(addonPath,'resources','language',lang,helpfile)
	if not os.path.exists(helpfilefull):
		helpfilefull = os.path.join(addonPath,'resources','language','English',helpfile)
	if not os.path.exists(helpfilefull): return {}
	data = open(helpfilefull,'r').read()
	items = data.split('\n@item:')
	caption = items.pop(0)
	if as_list:
		ret = []
		for i in items:
			if not i: continue
			key, val = i.split('\n',1)
			name = ''
			if '=' in key: key,name = key.split('=')
			ret.append({'id':key,'name':name,'help':val})
		return caption,ret
	else:
		ret = {}
		for i in items:
			if not i: continue
			key, val = i.split('\n',1)
			name = ''
			if '=' in key: key,name = key.split('=')
			ret[key] = val
			if name: ret[key + '.name'] = name
		return ret

def showText(caption,text,text_is_file=False):
	if text_is_file:
		lang = xbmc.getLanguage().split(' ',1)[0]
		addonPath = xbmc.translatePath(util.__addon__.getAddonInfo('path'))
		textfilefull = os.path.join(addonPath,'resources','language',lang,text)
		if not os.path.exists(textfilefull):
			textfilefull = os.path.join(addonPath,'resources','language','English',text)
		if not os.path.exists(textfilefull): return None
		f = open(textfilefull,'r')
		text = f.read()
		f.close()
	openWindow(TextDialog,'script-forumbrowser-text-dialog.xml',theme='Default',caption=caption,text=text)
	
def showHelp(helptype):
	helptype += '.help'
	caption, helplist = loadHelp(helptype,True)
	dialog = OptionsChoiceMenu(caption)
	for h in helplist:
		if h['id'] == 'sep':
			dialog.addSep()
		else:
			dialog.addItem(h['id'],h['name'],'../../../media/forum-browser-info.png',h['help'])
	result = dialog.getResult()
	if result == 'changelog':
		addonPath = xbmc.translatePath(util.__addon__.getAddonInfo('path'))
		changelogPath = os.path.join(addonPath,'changelog.txt')
		showText('Changelog',open(changelogPath,'r').read().replace('\t','    '))

def showInfo(infotype):
	infotype += '.info'
	lang = xbmc.getLanguage().split(' ',1)[0]
	addonPath = xbmc.translatePath(util.__addon__.getAddonInfo('path'))
	infofilefull = os.path.join(addonPath,'resources','language',lang,infotype)
	if not os.path.exists(infofilefull):
		infofilefull = os.path.join(addonPath,'resources','language','English',infotype)
	if not os.path.exists(infofilefull): return None
	showText('Info',open(infofilefull,'r').read())
	

class BaseDialog(xbmcgui.WindowXMLDialog):
	def __init__(self, *args, **kwargs):
		self._externalWindow = None
		xbmcgui.WindowXMLDialog.__init__( self )
		
	def externalWindow(self):
		if not self._externalWindow: self._externalWindow = self._getExternalWindow()
		return self._externalWindow
			
	def setProperty(self,key,value):
		self.externalWindow().setProperty(key,value)
		
	def _getExternalWindow(self):
		return xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
	
class MessageDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.text = kwargs.get('text') or ''
		self.caption = kwargs.get('caption') or ''
		self.error = kwargs.get('error')
		self.success = kwargs.get('success')
		self.scroll = kwargs.get('scroll')
		self.started = False
		BaseDialog.__init__( self )
	
	def onInit(self):
		if self.started: return
		self.started = True
		self.setProperties()
		
	def setProperties(self):
		self.setProperty('caption',self.caption)
		self.setProperty('message',self.text)
		if self.error:
			self.setProperty('error','error')
		elif self.success is not None:
			if self.success:
				self.setProperty('error','success')
			else:
				self.setProperty('error','warning')
		if self.scroll and not util.getSetting('message_dialog_always_show_ok',False):
			self.setProperty('hidebutton','hidebutton')
		
	def onAction(self,action):
		if action == 92 or action == 10:
			self.close()
		
	def onFocus( self, controlId ): self.controlId = controlId

class TextDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.text = kwargs.get('text') or ''
		self.caption = kwargs.get('caption') or ''
		BaseDialog.__init__( self )
	
	def onInit(self):
		self.setProperty('caption', self.caption)
		self.setProperty('text', self.text)
		#self.getControl(104).setLabel(self.caption)
		#textbox = self.getControl(122)
		#textbox.reset()
		#textbox.setText(self.text)
		
	def onAction(self,action):
		if action == 92 or action == 10:
			self.close()
			
class ImageChoiceDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.result = None
		self.items = kwargs.get('items')
		self.caption = kwargs.get('caption')
		self.select = kwargs.get('select')
		self.menu = kwargs.get('menu')
		self.filtering = kwargs.get('filtering',False)
		self.keepColors = kwargs.get('keep_colors',False)
		self._selectFirstOnBack = kwargs.get('selectFirstOnBack',False)
		self.terms = ''
		self.filter = None
		self.filterType = 'terms'
		self.started = False
		self.gifReplace = chr(255)*6
		self.colorsDir = os.path.join(CACHE_PATH,'colors')
		self.colorGif = os.path.join(xbmc.translatePath(util.__addon__.getAddonInfo('path')),'resources','media','white1px.gif')
		BaseDialog.__init__( self )
	
	def onInit(self):
		if self.started: return
		self.started = True
		self.showItems()
		
	def removeItem(self,item):
		if item in self.items:
			idx = self.items.index(item)
			self.items.pop(idx)
			self.showItems()
			return idx
		return None
			
	def showItems(self):
		clist = self.getControl(120)
		clist.reset()
		colors = {}
		if not os.path.exists(self.colorsDir): os.makedirs(self.colorsDir)
		
		for i in self.items:
			if self.filter:
				text = i['disp'] + ' ' + i['disp2']
				if self.filterType == 'terms':
					matched = False
					text = (i['disp'] + ' ' + i['disp2']).lower()
					for f in self.filter:
						if not f.search(text):
							break
					else:
						matched = True
						
					if not matched: continue
				else:
					if not fnmatch.fnmatch(text.lower(), self.filter): continue
					
			item = xbmcgui.ListItem(label=i['disp'],label2=i['disp2'],thumbnailImage=i['icon'])
			if i['sep']: item.setProperty('SEPARATOR','SEPARATOR')
			item.setProperty('bgcolor',i['bgcolor'])
			item.setProperty('disabled',str(bool(i['disabled'])))
			color = i['bgcolor'].upper()[2:]
			if color in colors:
				path = colors[color]
			else:
				path = self.makeColorFile(color, self.colorsDir)
				colors[color] = path
			item.setProperty('bgfile',path)
			for k,v in i.get('extras',{}).items():
				item.setProperty(k,v)
			clist.addItem(item)
		self.getControl(300).setLabel('[B]%s[/B]' % self.caption)
		self.setProperty('caption',self.caption)
		self.setFocus(clist)
		if self.select:
			idx=0
			for i in self.items:
				if i['id'] == self.select:
					clist.selectItem(idx)
					break
				idx+=1
		
	def doFilter(self):
		self.getControl(199).setVisible(False)
		try:
			terms = doKeyboard(util.T(32517),self.terms)
			self.terms = terms or ''
			if '*' in terms or '?' in terms:
				self.filter = terms.lower()
				self.filterType = 'wild'
			else:
				terms = terms.strip().split()
				self.filter = []
				for t in terms: self.filter.append(re.compile(r'\b%s\b' % t,re.I))
				self.filterType = 'terms'
				
			self.showItems()
		except:
			util.ERROR('Error handling search terms')
		finally:
			self.getControl(199).setVisible(True)
	
	def makeColorFile(self,color,path):
		try:
			replace = binascii.unhexlify(color)
		except:
			replace = chr(255)
		replace += replace
		target = os.path.join(path,color + '.gif')
		open(target,'w').write(open(self.colorGif,'r').read().replace(self.gifReplace,replace))
		return target
		
	def onAction(self,action):
		if action == 10:
			self.doClose()
		elif action == 92 or action == 9:
			if self._selectFirstOnBack:
				if self.getControl(120).size():
					self.getControl(120).selectItem(0)
					xbmc.executebuiltin('Action(Select)')
			else:
				self.doClose()
		elif action == 7:
			pass
			#self.finish()
		elif action == ACTION_CONTEXT_MENU:
			self.doMenu()
	
	def doClose(self):
		if not self.keepColors: clearDirFiles(self.colorsDir)
		self.close()
		
	def onClick( self, controlID ):
		if controlID == 120:
			self.finish()
		
	def doMenu(self):
		if self.menu.contextCallback:
			pos = self.getControl(120).getSelectedPosition()
			if pos < 0: return
			if self.menu.closeContext: self.close()
			self.menu.contextCallback(self,self.items[pos])
		elif self.filtering:
			self.doFilter()
			
	def finish(self):
		item = self.getControl(120).getSelectedItem()
		if item and item.getProperty('disabled') == 'True': return
		self.result = self.getControl(120).getSelectedPosition()
		self.doClose()
		
	def onFocus( self, controlId ): self.controlId = controlId
		
class ActivitySplashWindow(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.caption = kwargs.get('caption')
		self.cancelStopsConnections = kwargs.get('cancel_stops_connections')
		self.modal_callback = kwargs.get('modal_callback')
		self.canceled = False
		xbmcgui.WindowXMLDialog.__init__(self)
		
	def onInit(self):
		self.getControl(100).setLabel(self.caption)
		if self.modal_callback:
			callback, args, kwargs = self.modal_callback
			args = args or []
			kwargs = kwargs = {} 
			callback(self,*args,**kwargs)
		
	def update(self,message):
		self.getControl(100).setLabel(message)
		return not self.canceled
		
	def onAction(self,action):
		if action == ACTION_PARENT_DIR or action == ACTION_PARENT_DIR2: action = ACTION_PREVIOUS_MENU
		if action == ACTION_PREVIOUS_MENU:
			self.cancel()
			
	def cancel(self):
		self.canceled = True
		if self.cancelStopsConnections:
			asyncconnections.StopConnection()
	
	def onClick(self,controlID):
		if controlID == 200:
			self.cancel()
	
class ActivitySplash():
	def __init__(self,caption=util.T(32248),cancel_stops_connections=False,modal_callback=None):
		self.splash = openWindow(ActivitySplashWindow,'script-forumbrowser-loading-splash.xml',return_window=True,modal=bool(modal_callback),theme='Default',caption=caption,cancel_stops_connections=cancel_stops_connections,modal_callback=modal_callback)
		self.splash.show()
		
	def __enter__(self):
		return self
	
	def __exit__(self,etype, evalue, traceback):
		self.close()
		
	def update(self,pct,message):
		self.splash.update(message)

	def close(self):
		if not self.splash: return
		self.splash.close()
		del self.splash
		self.splash = None

class FakeActivitySplash():
	def __init__(self,caption=''):
		pass
		
	def update(self,pct,message):
		pass

	def close(self):
		pass
		
def showActivitySplash(caption=util.T(32248),cancel_stops_connections=False,modal_callback=None):
	if util.getSetting('hide_activity_splash',False):
		s = FakeActivitySplash(caption)
	else:
		s = ActivitySplash(caption,cancel_stops_connections=cancel_stops_connections,modal_callback=modal_callback)
	s.update(0,caption)
	return s

class DialogYesNo(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.caption = kwargs.get('caption','')
		self.yesLabel = kwargs.get('yes_label','')
		self.noLabel = kwargs.get('no_label','')
		self.text = kwargs.get('text','')
		self.yesno = None
		BaseDialog.__init__(self)
		
	def onInit(self):
		self.setProperty('caption',self.caption)
		self.setProperty('yes_label',self.yesLabel or xbmc.getLocalizedString(107))
		self.setProperty('no_label',self.noLabel or xbmc.getLocalizedString(106))
		self.setProperty('text', self.text)
		
	def onClick(self,controlID):
		if controlID == 110:
			self.yesno = True
			self.close()
		elif controlID == 111:
			self.yesno = False
			self.close()
		
def dialogYesNo(heading, line1='', line2='', line3='', no_label='', yes_label=''):
	text = '[CR]'.join(filter(bool,(line1,line2,line3)))
	w = openWindow(DialogYesNo,'script-forumbrowser-dialog-yesno.xml',return_window=True,caption=heading,text=text,no_label=no_label,yes_label=yes_label)
	yesno = w.yesno
	del w
	return yesno
	
class DialogSelect(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.caption = kwargs.get('caption','')
		self.select = kwargs.get('select',[])
		self.choice = None
		xbmcgui.WindowXMLDialog.__init__(self)
		
	def onInit(self):
		window = xbmcgui.Window(xbmcgui.getCurrentWindowDialogId())
		window.setProperty('caption',self.caption)
		items = []
		for i in self.select:
			items.append(xbmcgui.ListItem(i))
		self.getControl(111).addItems(items)
		self.setFocusId(111)
			
	def onClick(self,controlID):
		if controlID == 111:
			pos = self.getControl(111).getSelectedPosition()
			if pos < 0: return
			self.choice = pos
			self.close()
		
class ChoiceMenu():
	def __init__(self,caption,with_splash=False):
		self.caption = caption
		self.items = []
		self.splash = None
		self.contextCallback = None
		self.closeContext = True
		if with_splash: self.showSplash()
		
	def setContextCallback(self,callback):
		self.contextCallback = callback
		
	def isEmpty(self):
		return not self.items
	
	def showSplash(self):
		self.splash = showActivitySplash()
		
	def hideSplash(self):
		if not self.splash: return
		self.splash.close()
		
	def cancel(self):
		self.hideSplash()
		
	def addItem(self,ID,display,icon='',display2='',sep=False,disabled=False,bgcolor='FFFFFFFF',update=False,**kwargs):
		if ID is None: return self.addSep()
		if disabled:
			disabledText = 'DISABLED'
			if not disabled == True: disabledText = disabled
			display = "[COLOR FF444444]%s[/COLOR]" % display
			display2 = "[COLOR FF880000][B]%s[/B][/COLOR][CR][CR][COLOR FF444444]%s[/COLOR]" % (disabledText,display2)
		if not update:
			return self.items.append({'id':ID,'disp':display,'disp2':display2,'icon':icon,'sep':sep,'disabled':bool(disabled),'bgcolor':bgcolor,'extras':kwargs})
		
		for i in self.items:
			if ID == i.get('id'):
				i.update({'id':ID,'disp':display,'disp2':display2,'icon':icon,'sep':sep,'disabled':bool(disabled),'bgcolor':bgcolor,'extras':kwargs})
		
	def addSep(self):
		if self.items: self.items[-1]['sep'] = True
	
	def getChoiceIndex(self,xml_file):
		xml_file = xml_file or 'script-forumbrowser-dialog-select.xml'
		options = []
		for i in self.items: options.append(i.get('disp'))
		w = openWindow(DialogSelect,xml_file,return_window=True,caption=self.caption,select=options)
		idx = w.choice
		del w
		return idx
		#return xbmcgui.Dialog().select(self.caption,options)
	
	def getResult(self,close_on_context=True,xml_file=None):
		self.closeContext = close_on_context
		self.hideSplash()
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.pauseStack()
		idx = self.getChoiceIndex(xml_file)
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.resumeStack()
		if idx < 0: return None
		if self.items[idx]['disabled']: return None
		return self.items[idx]['id']

def dialogSelect(heading,ilist,autoclose=0):
	if util.getSetting('video_pause_on_dialog',True): util.PLAYER.pauseStack()
	c = ChoiceMenu(heading)
	i=0
	for disp in ilist:
		c.addItem(i,disp)
		i+=1
	result = c.getResult()
	#result =  xbmcgui.Dialog().select(heading,ilist,autoclose)
	if util.getSetting('video_pause_on_dialog',True): util.PLAYER.resumeStack()
	return result
	
class SmiliesDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.result = None
		self.items = kwargs.get('items')
		self.caption = kwargs.get('caption')
		self.started = False
		BaseDialog.__init__( self )
	
	def onInit(self):
		if self.started: return
		self.started = True
		self.setProperty('caption',self.caption)
		self.showItems()
		self.setFocusId(111)
		
	def showItems(self):
		clist = self.getControl(111)
		clist.reset()
		items = []
		for i in self.items:
			items.append(xbmcgui.ListItem(label=i['disp'],label2=i['disp2'],thumbnailImage=i['icon']))
		clist.addItems(items)
		
	def onAction(self,action):
		if action == 92 or action == 10:
			self.doClose()
	
	def doClose(self):
		self.close()
			
	def onClick(self,controlID):
		if controlID == 111:
			self.finish()
			
	def finish(self):
		item = self.getControl(111).getSelectedItem()
		if not item: return
		self.result = self.getControl(111).getSelectedPosition()
		self.doClose()
		
def smiliesDialog(heading=util.T(32540),smilies=None):
	if not smilies: smilies = loadSmilies() 
	if not smilies: return
	menu = SmiliesChoiceMenu(heading)
	for s in smilies:
		menu.addItem(s['code'],s['title'],s['url'])
	code = menu.getResult()
	if not code: return
	cmap = {')':48,'!':49,'@':50,'#':51,'$':52,'%':53,'^':54,'&':55,'*':56,'(':57,'[':65,']':66,'{':67,'}':68,'-':69,'_':70,'=':71,'+':72,';':73,':':74,"'":75,'"':76,',':77,'.':78,'<':79,'>':80,'/':81,'?':82,'\\':83,'|':84,'`':85,'~':86}
	clicks = [304,90,8]
	for c in list(code):
		val = ord(c)
		if val > 64 and val < 91:
			clicks += (302,val)
		elif val > 96 and val < 123:
			clicks.append(val-32)
		elif c in cmap:
			clicks += (304,cmap[c])
	for c in clicks:
		cmd = 'SendClick(virtualkeyboard,%s)' % c
		#print cmd
		xbmc.executebuiltin(cmd)
	
def loadSmilies():
	sfile = os.path.join(CACHE_PATH,'smilies')
	if not os.path.exists(sfile): return None
	with open(sfile,'r') as f: data = f.read()
	smilies = []
	for line in data.split('\n'):
		smiley = line.split('\r',2)
		if len(smiley) != 3: continue
		smilies.append({'code':smiley[0],'title':smiley[1],'url':smiley[2]})
	return smilies

def saveSmilies(smilies):
	out = []
	for s in smilies:
		out.append(s['code'] + '\r' + s['title'] + '\r' + s['url'])
	with open(os.path.join(CACHE_PATH,'smilies'),'w') as f:
		f.write('\n'.join(out))

class SmiliesChoiceMenu(ChoiceMenu):
	def getResult(self,windowFile='script-forumbrowser-dialog-smilies.xml'):
		w = openWindow(SmiliesDialog,windowFile ,return_window=True,menu=self,items=self.items,caption=self.caption)
		result = w.result
		del w
		if result == None: return None
		return self.items[result]['id']
	
class OptionsChoiceMenu(ChoiceMenu):
	def getResult(self,windowFile='script-forumbrowser-options-dialog.xml',select=None,close_on_context=True):
		self.closeContext = close_on_context
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.pauseStack()
		w = openWindow(ImageChoiceDialog,windowFile,return_window=True,theme='Default',menu=self,items=self.items,caption=self.caption,select=select)
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.resumeStack()
		result = w.result
		del w
		if result == None: return None
		if self.items[result]['disabled']: return None
		return self.items[result]['id']
		
class ImageChoiceMenu(ChoiceMenu):
	def getResult(self,windowFile='script-forumbrowser-image-dialog.xml',select=None,filtering=False,keep_colors=False,selectFirstOnBack=False):
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.pauseStack()
		w = openWindow(ImageChoiceDialog,windowFile ,return_window=True,theme='Default',menu=self,items=self.items,caption=self.caption,select=select,filtering=filtering,keep_colors=keep_colors,selectFirstOnBack=selectFirstOnBack)
		if util.getSetting('video_pause_on_dialog',True): util.PLAYER.resumeStack()
		result = w.result
		del w
		if result == None: return None
		return self.items[result]['id']

class xbmcDialogProgress:
	def __init__(self,heading,line1='',line2='',line3=''):
		self.heading = heading
		self.line1 = line1
		self.line2 = line2
		self.line3 = line3
		self.lastPercent = 0
		self.setRange()
		self.dialog = xbmcgui.DialogProgress()
	
	def __enter__(self):
		self.create(self.heading,self.line1,self.line2,self.line3)
		self.update(0,self.line1,self.line2,self.line3)
		return self
	
	def __exit__(self,etype, evalue, traceback):
		self.close()
		if etype == util.StopRequestedException: return True
	
	def setRange(self,start=0,end=100):
		self.start = start
		self.end = end
		self.range = end - start
		
	def recalculatePercent(self,pct):
		#print '%s - %s %s %s' % (pct,self.start,self.range,self.start + int((pct/100.0) * self.range))
		return self.start + int((pct/100.0) * self.range)

	def create(self,heading,line1='',line2='',line3=''):
		self.dialog.create(heading,line1,line2,line3)
		
	def update(self,pct,line1='',line2='',line3=''):
		if self.dialog.iscanceled():
			asyncconnections.StopConnection()
			return False
		pct = self.recalculatePercent(pct)
		if pct < self.lastPercent: pct = self.lastPercent
		self.lastPercent = pct
		self.dialog.update(pct,line1,line2,line3)
		return True
	
	def iscanceled(self):
		return self.dialog.iscanceled()
	
	def close(self):
		self.dialog.close()
		
class FadeDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		self.viewType = kwargs.get('view_type')
		self.startVal = util.getSetting('background_fade_%s' % self.viewType, 50)
		self.slider = None
	
	def onInit(self):
		self.slider = self.getControl(100)
		self.slider.setPercent(self.startVal)
		
	def onAction(self,action):
		try:
			pct = self.slider.getPercent()
			val = hex(int((pct/100.0)*255))[2:].upper()
			setGlobalSkinProperty('ForumBrowser_window_background_fade_white_%s' % self.viewType,val + 'FFFFFF')
			setGlobalSkinProperty('ForumBrowser_window_background_fade_black_%s' % self.viewType,val + '000000')
			if action == 92 or action == 10 or action == 7:
				util.setSetting('background_fade_%s' % self.viewType, pct)
			if action == 7: self.close()
		except:
			util.ERROR('ERROR')

		BaseDialog.onAction(self,action)
		
def showFadeDialog(view_type):
	openWindow(FadeDialog,'script-forumbrowser-fade-dialog.xml',view_type=view_type)
	
class Slider:
	def __init__(self,window,back_id,back2_id,nib_id,button_id,max_val,start):
		self.back = window.getControl(back_id)
		self.back2 = back2_id and window.getControl(back2_id) or None
		self.nib = window.getControl(nib_id)
		self.button = window.getControl(button_id)
		self.ID = button_id
		self.max = max_val
		self.start, self.y = self.back.getPosition()
		self.start -= int(self.nib.getWidth()/2)
		self.width = self.back.getWidth()
		self.val = start
		self.placeNib()
		
	def moveLeft(self):
		self.val -= 1
		if self.val < 0:
			self.val = 0
			return
		self.placeNib()
	
	def moveRight(self):
		self.val += 1
		if self.val > self.max:
			self.val = self.max
			return
		self.placeNib()
	
	def updateVal(self,val):
		self.val = val
		self.placeNib()
		
	def placeNib(self):
		pos = int((self.val/float(self.max))*(self.width-1))
		self.nib.setPosition(self.start + pos,self.y)
		
	def setBacks(self,hex1,hex2):
		self.back.setColorDiffuse(hex1)
		self.back2.setColorDiffuse(hex2)
	
	
class AlphaColorDialog(BaseDialog):
	def __init__( self, *args, **kwargs ):
		BaseDialog.__init__(self)
		self.hex = kwargs.get('start_color','FF808080') or 'FF808080'
		self.defaultColor = kwargs.get('default_color','802080FF') or '802080FF'
		self.previewImage = kwargs.get('preview_image','')
		self.fade = kwargs.get('fade') or 'A0'
		self.mode = kwargs.get('mode') or 0
		self.startColor = self.hex
		self.rSlider = None
		self.gSlider = None
		self.bSlider = None
		self.vSlider = None
		self.sSlider = None
		self.aSlider = None
		self.vLastRGB = (0,0,0)
		self.sLastRGB = (0,0,0)
		self.sliders = {}
	
	def onInit(self):
		self.rSlider = Slider(self,200,300,201,202,255,int(self.hex[6:],16))
		self.gSlider = Slider(self,203,303,204,205,255,int(self.hex[4:6],16))
		self.bSlider = Slider(self,206,306,207,208,255,int(self.hex[2:4],16))
		self.vSlider = Slider(self,209,309,210,211,255,0)
		self.sSlider = Slider(self,212,312,213,214,255,0)
		self.aSlider = Slider(self,215,None,216,217,255,int(self.hex[:2],16))
		self.sliders[self.rSlider.ID] = self.rSlider
		self.sliders[self.gSlider.ID] = self.gSlider
		self.sliders[self.bSlider.ID] = self.bSlider
		self.sliders[self.vSlider.ID] = self.vSlider
		self.sliders[self.sSlider.ID] = self.sSlider
		self.sliders[self.aSlider.ID] = self.aSlider
		
		self.vLastRGB = self.getRGB()
		self.sLastRGB = self.getRGB()
		
		self.preview = self.getControl(100)
		self.hexButton = self.getControl(101)
		self.colorBox = self.getControl(102)
		self.previewBack = self.getControl(103)
		self.backFadeLight = self.getControl(104)
		self.backFadeDark = self.getControl(105)
		if self.previewImage: self.setProperty('preview_image',self.previewImage)
		self.backFadeLight.setColorDiffuse(self.fade + 'FFFFFF')
		self.backFadeDark.setColorDiffuse(self.fade + '000000')
		self.setMode()
		self.updatePreview()
		
	def setMode(self):
		self.setProperty('mode',str(self.mode))
		if self.mode == 1:
			self.setProperty('default_button',util.T(32942))
		else:
			self.setProperty('default_button',util.T(32563))

		
	def onClick(self,controlID):
		if controlID == 101:
			self.askHexColor()
		elif controlID == 110:
			if self.mode == 1:
				self.autoColor()
			else:
				self.updateColors(self.defaultColor)
			self.updatePreview()
		elif controlID == 111:
			self.updateColors(self.startColor)
			self.updatePreview()
		elif controlID > 120 and controlID < 127:
			self.setPrimaryColor(controlID)
			
	def setPrimaryColor(self,controlID):
		idx = controlID - 121
		color = ('FF000000','FF7F7F7F','FFFFFFFF','FFFF0000','FF00FF00','FF0000FF')[idx]
		self.updateColors(color)
		self.updatePreview() 
			
	def onAction(self,action):
		try:
			currentID = self.getFocusId()
			if action == ACTION_MOVE_LEFT:
				if currentID in self.sliders:
					self.sliders[currentID].moveLeft()
					self.onSliderMove(currentID)
					self.updatePreview(currentID)
					
			elif action == ACTION_MOVE_RIGHT:
				if currentID in self.sliders:
					self.sliders[currentID].moveRight()
					self.onSliderMove(currentID)
					self.updatePreview(currentID)
			#setGlobalSkinProperty('ForumBrowser_window_background_fade_black_%s' % self.viewType,val + '000000')
			#if action == 92 or action == 10 or action == 7:
				#util.setSetting('background_fade_%s' % self.viewType, pct)
		except:
			util.ERROR('ERROR')

		BaseDialog.onAction(self,action)
		
	def updateColors(self,new=None):
		if new: self.hex = new
		self.rSlider.updateVal(int(self.hex[2:4],16))
		self.gSlider.updateVal(int(self.hex[4:6],16))
		self.bSlider.updateVal(int(self.hex[6:],16))
		self.aSlider.updateVal(int(self.hex[:2],16))
		self.vLastRGB = self.getRGB()
		self.sLastRGB = self.getRGB()
		
	def getRGB(self):
		return (self.rSlider.val,self.gSlider.val,self.bSlider.val)
	
	def onSliderMove(self,sliderID):
		if sliderID == self.vSlider.ID:
			self.processValueSliderMove()
			rgb = self.getRGB()
			if not max(rgb): rgb = (1,1,1)
			self.sLastRGB = rgb
		elif sliderID == self.sSlider.ID:
			self.processSaturationSliderMove()
			rgb = self.getRGB()
			if not max(rgb): rgb = (1,1,1)
			self.vLastRGB = rgb
		else:
			rgb = self.getRGB()
			if not max(rgb): rgb = (1,1,1)
			self.sLastRGB = self.vLastRGB = rgb
		
	def processValueSliderMove(self):
		v = self.vSlider.val
		r,g,b = self.vLastRGB
		maxC = float(max(r,g,b))
		self.rSlider.updateVal(int((r/maxC)*v))
		self.gSlider.updateVal(int((g/maxC)*v))
		self.bSlider.updateVal(int((b/maxC)*v))
				
	def processSaturationSliderMove(self):
		s = self.sSlider.val
		r,g,b = self.sLastRGB
		top = max(self.sLastRGB)
		bottom = min(self.sLastRGB)
		if top == bottom: return
		sRange = top - bottom
		sMax = self.sSlider.max * (sRange / float(top))
		satFraction = s/float(sMax)
		r = top - int(satFraction * (top - r))
		g = top - int(satFraction * (top - g))
		b = top - int(satFraction * (top - b))
		self.rSlider.updateVal(r)
		self.gSlider.updateVal(g)
		self.bSlider.updateVal(b)
	
	def updateFades(self,currentID):
		r,g,b = self.rSlider.val,self.gSlider.val,self.bSlider.val
		if currentID == self.vSlider.ID:
			pass
		self.rSlider.setBacks(self.hexFromRGB(255, g, b), self.hexFromRGB(0, g, b))
		self.gSlider.setBacks(self.hexFromRGB(r, 255, b), self.hexFromRGB(r, 0, b))
		self.bSlider.setBacks(self.hexFromRGB(r, g, 255), self.hexFromRGB(r, g, 0))
		if currentID != self.vSlider.ID:
			self.vSlider.updateVal(max(self.rSlider.val,self.gSlider.val,self.bSlider.val))
			self.vSlider.setBacks(self.hexFromRGB(*self.calculateLevelTop()), self.hexFromRGB(0, 0, 0))
		if currentID != self.sSlider.ID:
			self.updateSaturationSlider()
		
	def updateSaturationSlider(self):
		top = max(self.rSlider.val,self.gSlider.val,self.bSlider.val)
		bottom = min(self.rSlider.val,self.gSlider.val,self.bSlider.val)
		
		satFraction = top/(float(top - bottom) or 1)
		r = top - int(round(satFraction * (top - self.rSlider.val)))
		g = top - int(round(satFraction * (top - self.gSlider.val)))
		b = top - int(round(satFraction * (top - self.bSlider.val)))
		
		self.sSlider.updateVal(self.sSlider.max - int((bottom/float(top or 1)*self.sSlider.max)))
		self.sSlider.setBacks(self.hexFromRGB(r,g,b), self.hexFromRGB(top,top,top))
	
	def calculateLevelTop(self):
		level = self.vSlider.val
		levelMax = self.vSlider.max
		levelFraction = levelMax/(float(level) or 1)
		r = int(round(levelFraction * self.rSlider.val))
		g = int(round(levelFraction * self.gSlider.val))
		b = int(round(levelFraction * self.bSlider.val))
		if not (r + g + b):
			return 255,255,255
		else:
			return r,g,b
	
	def hexFromRGB(self,r,g,b):
		hexR = binascii.hexlify(chr(r)).upper()
		hexG = binascii.hexlify(chr(g)).upper()
		hexB = binascii.hexlify(chr(b)).upper()
		return 'FF' + hexR+hexG+hexB
	
	def askHexColor(self):
		hexc = getHexColor(self.hex,hlen=8)
		if len(hexc) < 8: hexc = 'FF' + hexc
		self.updateColors(hexc)
		self.updatePreview()
		
	def autoColor(self):
		if not self.previewImage: return
		import urllib2
		#print self.previewImage
		if os.path.exists(self.previewImage):
			tmp_file = self.image
		else:
			tmp_file = os.path.join(util.CACHE_PATH,'temp_logo')
			try:
				open(tmp_file,'wb').write(urllib2.urlopen(self.previewImage).read())
			except:
				util.ERROR('autoColor(): Failed to get image')
				return
		rgb = util.getImageBackgroundColor(tmp_file)
		os.remove(tmp_file)
		if not rgb: return
		self.updateColors(self.hexFromRGB(*rgb))
		
	def updatePreview(self,currentID=None):
		self.updateFades(currentID)
		hexR = binascii.hexlify(chr(self.rSlider.val)).upper()
		hexG = binascii.hexlify(chr(self.gSlider.val)).upper()
		hexB = binascii.hexlify(chr(self.bSlider.val)).upper()
		hexA = binascii.hexlify(chr(self.aSlider.val)).upper()
		self.hex = hexA+hexR+hexG+hexB
		opaque = 'FF' + hexR+hexG+hexB
		self.colorBox.setColorDiffuse(opaque)
		self.preview.setColorDiffuse(self.hex)
		self.hexButton.setLabel(self.hex)
		self.setProperty('opaque',opaque)
		
def showSelectionColorDialog(start_color=None,preview_image=None,fade=None,mode=None):
	w = openWindow(AlphaColorDialog,'script-forumbrowser-alpha-color-dialog.xml',modal=False,return_window=True,start_color=start_color,preview_image=preview_image,fade=fade,mode=mode)
	w.doModal()
	hexC = w.hex
	del w
	if not dialogYesNo(util.T(32579),util.T(32579)): return None
	return hexC
	
def getHexColor(hexc=None,hlen=6):
	hexc = doKeyboard(util.T(32475),default=hexc)
	if not hexc: return None
	while (len(hexc) != 6 and len(hexc) != hlen) or re.search('[^1234567890abcdef](?i)',hexc):
		showMessage(util.T(32050),util.T(32474))
		hexc = doKeyboard(util.T(32475),default=hexc)
		if not hexc: return None
	return hexc.upper()

class ColorDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.image = kwargs.get('image')
		self.hexc = kwargs.get('hexcolor','FFFFFF') or 'FFFFFF'
		self.r = 127
		self.g = 127
		self.b = 127
		self.closed = False
		xbmcgui.WindowXMLDialog.__init__( self )
		
	def onInit(self):
		if self.image: self.getControl(300).setImage(self.image)
		self.setHexColor(self.hexc)
		self.showColor()
		
	def onClick(self,controlID):
		if   controlID == 150: self.changeR(-1)
		elif controlID == 151: self.changeR(1)
		elif controlID == 152: self.changeG(-1)
		elif controlID == 153: self.changeG(1)
		elif controlID == 154: self.changeB(-1)
		elif controlID == 155: self.changeB(1)
		elif controlID == 156: self.changeAll(-1)
		elif controlID == 157: self.changeAll(1)
		elif controlID == 158: self.setHexColor()
		elif controlID == 113: self.autoColor()
		elif controlID == 170: self.setHexColor('FFFFFF')
		elif controlID == 171: self.setHexColor('000000')
		elif controlID == 172: self.setHexColor('7E7E7E')
		elif controlID == 173: self.setHexColor('FF0000')
		elif controlID == 174: self.setHexColor('00FF00')
		elif controlID == 175: self.setHexColor('0000FF')
		elif controlID == 111: return self.close()
		
		#print str(self.r) + ' ' +str(self.g) + ' ' +str(self.b)
		self.showColor()
		
	def showColor(self):
		hexR = binascii.hexlify(chr(self.r)).upper()
		hexG = binascii.hexlify(chr(self.g)).upper()
		hexB = binascii.hexlify(chr(self.b)).upper()
		hexc = hexR+hexG+hexB
		self.getControl(160).setColorDiffuse('FF' + hexc)
		self.getControl(200).setLabel(str(self.r))
		self.getControl(201).setLabel(hexR)
		self.getControl(202).setLabel(str(self.g))
		self.getControl(203).setLabel(hexG)
		self.getControl(204).setLabel(str(self.b))
		self.getControl(205).setLabel(hexB)
		self.getControl(158).setLabel('#'+hexc)
		
	def changeR(self,mod):
		self.r += mod
		if self.r < 0: self.r = 255
		elif self.r > 255: self.r = 0
		
	def changeG(self,mod):
		self.g += mod
		if self.g < 0: self.g = 255
		elif self.g > 255: self.g = 0
		
	def changeB(self,mod):
		self.b += mod
		if self.b < 0: self.b = 255
		elif self.b > 255: self.b = 0
		
	def changeAll(self,mod):
		self.r += mod
		if self.r < 0: self.r = 0
		elif self.r > 255: self.r = 255
		self.g += mod
		if self.g < 0: self.g = 0
		elif self.g > 255: self.g = 255
		self.b += mod
		if self.b < 0: self.b = 0
		elif self.b > 255: self.b = 255
		
	def setHexColor(self,hexc=None):
		if not hexc: hexc = getHexColor(self.hexValue())
		if not hexc: return
		self.r = int(hexc[:2],16)
		self.g = int(hexc[2:4],16)
		self.b = int(hexc[4:],16)
		self.showColor()
		
	def autoColor(self):
		if not self.image: return
		import urllib2
		print self.image
		if os.path.exists(self.image):
			tmp_file = self.image
		else:
			tmp_file = os.path.join(util.CACHE_PATH,'temp_logo')
			try:
				open(tmp_file,'wb').write(urllib2.urlopen(self.image).read())
			except:
				util.ERROR('autoColor(): Failed to get image')
				return
		rgb = util.getImageBackgroundColor(tmp_file)
		os.remove(tmp_file)
		self.r = rgb[0]
		self.g = rgb[1]
		self.b = rgb[2]
		self.showColor()
	
	def hexValue(self):
		if self.closed: return None
		hexR = binascii.hexlify(chr(self.r)).upper()
		hexG = binascii.hexlify(chr(self.g)).upper()
		hexB = binascii.hexlify(chr(self.b)).upper()
		hexc = hexR+hexG+hexB
		return hexc
		
	def onAction(self,action):
		if action == 92 or action == 10:
			self.closed = True
			self.close()

def setGlobalSkinProperty(key,val):
	window = GLOBAL_WINDOW or xbmcgui.Window(10000)
	window.setProperty(key,val)
	
###################################################################	
## Bookmarks
###################################################################			
def bookmarks():
	bookmarks = util.loadBookmarks()
	menu = ImageChoiceMenu(util.T(32554))
	menu.setContextCallback(bookmarksRemoveCallback)
	menu.closeContext = False
	for b in bookmarks:
		elements = util.parseForumBrowserURL(b[0])
		f = elements.get('forumID')
		path = util.getForumPath(f,just_path=True)
		fdata = forumbrowser.ForumData(f,path)
		bgcolor = 'FF' + fdata.theme.get('header_color','FFFFFF')
		logo = fdata.urls.get('logo','')
		exists, logopath = util.getCachedLogo(logo,f)
		if exists: logo = logopath
		menu.addItem(b[0], b[1], logo,bgcolor=bgcolor)
	result = menu.getResult('script-forumbrowser-forum-select.xml')
	if not result: return
	return result

def bookmarksRemoveCallback(menu,item):
	submenu = ChoiceMenu('Options')
	submenu.addItem('remove', 'Remove')
	result = submenu.getResult(xml_file='script-forumbrowser-dialog-select-small.xml')
	if not result: return
	if result == 'remove':
		idx = menu.removeItem(item)
		util.removeBookmark(idx)

def addBookmark(FB,page=None,name='',page_disp=''):
	if not FB: return
	elements = util.parseForumBrowserURL(FB.appURL)
	if elements.get('forum'): elements['section'] = None
	url = None
	if elements.get('post'):
		url = util.createForumBrowserURL(elements)
		if elements.get('section') == 'PM':
			name = 'PM' + ': ' + name
		else:
			name = 'Post' + ': ' + name
	elif elements.get('thread'):
		menu = ChoiceMenu('Add Bookmark')
		if page: menu.addItem('thread','Bookmark Thread (This Page)')
		menu.addItem('threadlast','Bookmark Thread (Last Page)')
		menu.addItem('threadfirst','Bookmark Thread (First Page)')
		result = menu.getResult()
		if not result: return
		if result == 'thread':
			url = util.createForumBrowserURL(elements,args={'page':page})
			name = 'Thread (' + 'Page' + ' %s' % page_disp + '): ' + name
		elif result == 'threadlast':
			elements['post'] = 'last'
			url = util.createForumBrowserURL(elements)
			name = 'Thread (' + 'Last' + '): ' + name
		elif result == 'threadfirst':
			elements['post'] = 'first'
			url = util.createForumBrowserURL(elements)
			name = 'Thread (' + 'First' + '): ' + name
	elif elements.get('forum'):
		url = util.createForumBrowserURL(elements)
		name = 'Forum' + ': ' + name
	elif elements.get('section'):
		url = util.createForumBrowserURL(elements)
		if elements['section'] == 'SUBSCRIPTIONS':
			name = '%s: %s' % (FB.getDisplayName(),'Subscriptions')
		else:
			name = '%s: %s' % (FB.getDisplayName(),'PMs')
	if not url: return
	name = doKeyboard('Enter Bookmark Name',name)
	if not name: return
	util.addBookmark(url, name)
	