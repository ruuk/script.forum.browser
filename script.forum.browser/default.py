import urllib2, re, os, sys, time
import xbmc, xbmcgui, xbmcaddon

__plugin__ = 'Forum Browser'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/forumbrowserxbmc/'
__date__ = '09-25-2010'
__version__ = '0.7.3'
__addon__ = xbmcaddon.Addon(id='script.forum.browser')
__language__ = __addon__.getLocalizedString

ACTION_MOVE_LEFT      = 1
ACTION_MOVE_RIGHT     = 2
ACTION_MOVE_UP        = 3
ACTION_MOVE_DOWN      = 4
ACTION_PAGE_UP        = 5
ACTION_PAGE_DOWN      = 6
ACTION_SELECT_ITEM    = 7
ACTION_HIGHLIGHT_ITEM = 8
ACTION_PARENT_DIR     = 9
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

TITLE_FORMAT = '[COLOR %s][B]%s[/B][/COLOR]'

#href="forumdisplay.php?f=27&amp;order=desc&amp;page=171" title="Prev Page - Results 3,401 to 3,420 of 3,421">&lt;</a></td>
#href="forumdisplay.php?f=27&amp;order=desc&amp;page=2" title="Next Page - Results 21 to 40 of 3,421">&gt;</a></td>

def ERROR(message):
	print 'FORUMBROWSER - %s::%s (%d) - %s' % (message,sys.exc_info()[2].tb_frame.f_code.co_name, sys.exc_info()[2].tb_lineno, sys.exc_info()[1])
	
def LOG(message):
	print 'FORUMBROWSER: %s' % message

######################################################################################
# Forum Browser Classes
######################################################################################

class ForumPost:
	def __init__(self,pmatch=None):
		if pmatch:
			pdict = pmatch.groupdict()
			self.postId = pdict.get('postid','')
			self.date = pdict.get('date','')
			self.userId = pdict.get('userid','')
			self.userName = pdict.get('user') or pdict.get('guest') or 'UERROR'
			self.avatar = pdict.get('avatar','')
			self.title = pdict.get('title','')
			self.message = pdict.get('message','')
		else:
			self.postId,self.date,self.userId,self.userName,self.avatar,self.title,self.message = ('','','','ERROR','','ERROR','')
	
	def messageAsText(self):
		return messageToText(self.message)
		
	def messageAsDisplay(self):
		return messageToDisplay(self.message)
		
	def messageAsQuote(self):
		return messageAsQuote(self.message)
		
	def imageURLs(self):
		return re.findall('<img\s.+?src="(http://.+?)".+?/>',self.message)
			
class PageData:
	def __init__(self,page_match,next_match,prev_match):
		self.next = False
		self.prev = False
		self.page = '1'
		self.totalPages = '1'
		self.pageDisplay = ''
		self.urlMode = 'PAGE'
		self.nextStart = '0'
		self.prevStart = '0'
		
		if page_match:
			pdict = page_match.groupdict()
			self.page = pdict.get('page','1')
			self.totalPages = pdict.get('total','1')
			self.pageDisplay = pdict.get('display','')
		if next_match:
			ndict = next_match.groupdict()
			page = ndict.get('page')
			start = ndict.get('start')
			if page:
				self.next = True
				self.urlMode = 'PAGE'
			elif start:
				self.next = True
				self.nextStart = start
				self.urlMode = 'START'
		if prev_match:
			pdict = prev_match.groupdict()
			page = pdict.get('page')
			start = pdict.get('start')
			if page:
				self.prev = True
				self.urlMode = 'PAGE'
			elif start:
				self.prev = True
				self.prevStart = start
				self.urlMode = 'START'
				
	def getNextPage(self):
		if self.urlMode == 'PAGE':
			try:
				return str(int(self.page) + 1)
			except:
				return '1'
		else:
			return self.nextStart
			
	def getPrevPage(self):
		if self.urlMode == 'PAGE':
			try:
				return str(int(self.page) - 1)
			except:
				return '1'
		else:
			return self.prevStart
				
	def getPageDisplay(self):
		if self.pageDisplay: return self.pageDisplay
		if self.page and self.totalPages:
			return 'Page %s of %s' % (self.page,self.totalPages)
			
class PostMessage:
	def __init__(self,pid='',tid='',fid='',title='',message=''):
		self.pid = pid
		self.tid = tid
		self.fid = fid
		self.title = title
		self.message = message
		self.quote = ''
		self.quser = ''
		
	def setQuote(self,user,quote):
		self.quser = user
		self.quote = quote
		
	def setMessage(self,title,message):
		self.title = title
		self.message = message
				
######################################################################################
# Forum Browser API
######################################################################################
class ForumBrowser:
	def __init__(self,forum):
		self.forum = forum
		self._url = ''
		self.browser = None
		self.mechanize = None
		
		self.reloadForumData(forum)
		
	def reloadForumData(self,forum):
		self.urls = {}
		self.filters = {}
		self.theme = {}
		self.forms = {}
		self.formats = {}
		self.smilies = {}
		
		self.loadForumData(forum)
		
	def loadForumData(self,forum):
		fname = xbmc.translatePath('special://home/addons/script.forum.browser/forums/%s' % forum)
		if not os.path.exists(fname): return False
		f = open(fname,'r')
		data = f.read()
		f.close()
		for line in data.splitlines():
			line = line.strip()
			if not line: continue
			if line.startswith('#'): continue
			dtype , rest = line.split(':',1)
			if dtype == 'import':
				self.loadForumData(rest)
			elif dtype == 'url':
				key,url = rest.split('=',1)
				if url.startswith('=='):
					dup = url.split('=')[-1]
					url = self.urls[dup]
				self.urls[key] = url
			elif dtype == 'filter':
				key,regex = rest.split('=',1)
				if regex.startswith('=='):
					dup = regex.split('=')[-1]
					regex = self.filters[dup]
				self.filters[key] = regex
			elif dtype == 'theme':
				key,color = rest.split('=',1)
				if color.startswith('=='):
					dup = color.split('=')[-1]
					color = self.theme[dup]
				self.theme[key] = color
			elif dtype == 'form':
				key,data = rest.split('=',1)
				if data.startswith('=='):
					dup = data.split('=')[-1]
					data = self.forms[dup]
				self.forms[key] = data
			elif dtype == 'format':
				key,data = rest.split('=',1)
				if data.startswith('=='):
					dup = data.split('=')[-1]
					data = self.formats[dup]
				self.formats[key] = data
			elif dtype == 'smilies':
				key,data = rest.split('=',1)
				if data.startswith('=='):
					dup = data.split('=')[-1]
					data = self.smilies[dup]
				self.smilies[key] = data
				
		self._url = self.urls.get('base','')
		self.forum = forum
		return True
			
		
	def setLogin(self,user,password):
		self.user = user
		self.password = password
				
	def readURL(self,url):
		req = urllib2.urlopen(url)
		data = req.read()
		req.close()
		return data
		
	def makeURL(self,phppart):
		url = self._url + phppart
		return url.replace('&amp;','&').replace('/./','/')
		
	def getForums(self):
		html = self.readURL(self.getURL('forums'))
		#open('/home/ruuk/test3.html','w').write(html)
		if not html: return None
		forums = re.finditer(self.filters['forums'],re.sub('[\n\t\r]','',html))
		logo = ''
		if self.filters.get('logo'): logo = re.findall(self.filters['logo'],html)[0]
		if logo: logo = self.makeURL(logo)
		return forums, logo
		
	def getThreads(self,forumid,page=''):
		url = self.getPageUrl(page,'threads',fid=forumid)
		html = self.readURL(url)
		if not html: return None
		threads = re.finditer(self.filters['threads'],re.sub('[\n\r\t]','',html))
		return threads,self.getPageData(html,page)
		
	def getReplies(self,threadid,forumid,page='',lastid=''):
		url = self.getPageUrl(page,'replies',tid=threadid,fid=forumid,lastid=lastid)
		html = self.readURL(url)
		if not html: return None
		replies = re.findall(self.filters['replies'],re.sub('[\n\r\t]','',html))
		sreplies = []
		for r in replies:
			try:
				post = ForumPost(re.search(self.filters['post'],re.sub('[\n\r\t]','',r)))
				sreplies.append(post)
			except:
				post = ForumPost()
				sreplies.append(post)
		return sreplies, self.getPageData(html,page)
		
	def getSubscriptions(self,page='',callback=None):
		if not callback: callback = self.fakeCallback
		callback(5,'Logging In')
		if not self.checkLogin(): return False
		url = self.getPageUrl(page,'subscriptions')
		html = self.readURL(url)
		callback(30,'Opening URL')
		response = self.browser.open(url)
		callback(55,'Reading Data')
		html = response.read()
		if self.forms.get('login_action','@%+#') in html:
			self.login()
			response = self.browser.open(self.getURL('subscriptions') + page)
			html = response.read()
			if self.forms.get('login_action','@%+#') in html:
				return None
		if not html: return None
		callback(80,'Parsing Data')
		threads = re.finditer(self.filters['subscriptions'],re.sub('[\n\r\t]','',html))
		callback(100,'Reading Data')
		return threads, self.getPageData(html,page)
		
	def getPageData(self,html,page,newpost=''):
		next_page = re.search(self.filters['next'],html,re.S)
		prev_page= None
		if (page or newpost) and page != '1':
			prev_page = re.search(self.filters['prev'],html,re.S)
		page_disp = re.search(self.filters['page'],html)
		return PageData(page_disp,next_page,prev_page)
		
	def getPageUrl(self,page,sub,pid='',tid='',fid='',lastid=''):
		if sub == 'replies' and int(page) < 0:
			gnp = self.urls.get('gotonewpost','')
			page = self.URLSubs(gnp,pid=lastid)
		else:
			per_page = self.formats.get('%s_per_page' % sub)
			if per_page and page:
				try:
					if int(page) < 0: page = 1000
					page = str((int(page) - 1) * int(per_page))
				except:
					ERROR('CALCULATE START PAGE ERROR - PAGE: %s' % page)
			if page: page = '&%s=%s' % (self.urls.get('page_arg',''),page)
		sub = self.URLSubs(self.urls[sub],pid=pid,tid=tid,fid=fid)
		return self._url + sub + page
		
	def getURL(self,name):
		return self._url + self.urls.get(name,'')
		
	def predicateLogin(self,formobj):
		return self.forms.get('login_action','@%+#') in formobj.action
		
	def login(self):
		LOG('LOGGING IN')
		if not self.mechanize:
			import mechanize
			self.mechanize = mechanize
		if not self.browser: self.browser = self.mechanize.Browser()
		response = self.browser.open(self.getURL('login'))
		html = response.read()
		self.browser.select_form(predicate=self.predicateLogin)
		self.browser[self.forms['login_user']] = self.user
		self.browser[self.forms['login_pass']] = self.password
		response = self.browser.submit()
		html = response.read()
		if not self.forms.get('login_action','@%+#') in html: return True
		LOG('FAILED TO LOGIN')
		return False
		
	def checkLogin(self):
		if not self.browser:
			if not self.login():
				return False
		return True
		
	def getForm(self,html,action,name):
		if not action: return None
		try:
			forms = self.mechanize.ParseString(''.join(re.findall('<form\saction="%s.*?</form>' % action,html,re.S)),self._url)
			if name:
				for f in forms:
					if f.name == name:
						return f
			for f in forms:
				if action in f.action:
					return f
			LOG('NO FORM 2')
		except:
			ERROR('PARSE ERROR')
			
	def URLSubs(self,url,pid='',tid='',fid='',post=None):
		if post:
			return url.replace('!POSTID!',post.pid).replace('!THREADID!',post.tid).replace('!FORUMID!',post.fid)
		else:
			return url.replace('!POSTID!',pid).replace('!THREADID!',tid).replace('!FORUMID!',fid)
		
	def postURL(self,post):
		return self.URLSubs(self.getURL('newpost'),post=post)
	
	def predicatePost(self,formobj):
		return self.forms.get('post_action','@%+#') in formobj.action
		
	def fakeCallback(self,pct,message=''): pass
	
	def post(self,post,callback=None):
		if not callback: callback = self.fakeCallback
		callback(5,'Logging In')
		if not self.checkLogin(): return False
		url = self.postURL(post)
		res = self.browser.open(url)
		html = res.read()
		if self.forms.get('login_action','@%+#') in html:
			if not self.login(): return False
			res = self.browser.open(url)
			html = res.read()
		callback(40,'Processing Form')
		selected = False
		try:
			if self.forms.get('post_name'):
				self.browser.select_form(self.forms.get('post_name'))
				LOG('FORM SELECTED BY NAME')
			else:
				self.browser.select_form(predicate=self.predicatePost)
				LOG('FORM SELECTED BY ACTION')
			selected = True
		except:
			ERROR('NO FORM 1')
			
		if not selected:
			form = self.getForm(html,self.forms.get('post_action',''),self.forms.get('post_name',''))
			if form:
				self.browser.form = form
			else:
				return False
		try:
			if post.title: self.browser[self.forms['post_title']] = post.title
			self.browser[self.forms['post_message']] = post.message
			self.setControls('post_controls%s')
			#print self.browser.form
			wait = int(self.forms.get('post_submit_wait',0))
			if wait: callback(60,'Wating %s seconds' % wait)
			time.sleep(wait) #or this will fail on some forums. I went round and round to find this out.
			callback(80,'Submitting Form')
			res = self.browser.submit(name=self.forms.get('post_submit_name'),label=self.forms.get('post_submit_value'))
			callback(100,'Done')
		except:
			ERROR('FORM ERROR')
			return False
			
		return True
		
	def predicateDeletePost(self,formobj):
		if self.forms.get('delete_action','@%+#') in formobj.action: return True
		return False
		
	def deletePost(self,post):
		if not self.checkLogin(): return False
		res = self.browser.open(self.URLSubs(self.getURL('deletepost'),post=post))
		html = res.read()
		
		if self.forms.get('login_action','@%+#') in html:
			if not self.login(): return False
			res = self.browser.open(self.URLSubs(self.getURL('deletepost'),post=post))
			html = res.read()
			
		selected = False
		#print html
		try:
			self.browser.select_form(predicate=self.predicateDeletePost)
			selected = True
		except:
			ERROR('DELETE NO FORM 1')
			
		if not selected:
			form = self.getForm(html,self.forms.get('delete_action',''),self.forms.get('delete_name',''))
			if form:
				self.browser.form = form
			else:
				LOG('DELETE NO FORM 2')
				return False
		
		try:
			#self.browser.find_control(name="deletepost").value = ["delete"]
			self.setControls('delete_control%s')
			#self.browser["reason"] = reason[:50]
			self.browser.submit()
		except:
			ERROR('DELETE NO CONTROL')
			return False
			
		return True
		#<a href="editpost.php?do=editpost&amp;p=631488" name="vB::QuickEdit::631488">
	
	def setControls(self,control_string):
		x=1
		#limit to 50 because while loops scare me :)
		while x<50:
			control = self.forms.get(control_string % x)
			if not control: return
			ctype,rest = control.split(':')
			if ctype == 'radio':
				name,value = rest.split('=')
				self.browser.find_control(name=name).value = [value]
			x+=1
			
	def canDelete(self,user):
		return self.user == user and self.urls.get('deletepost')

######################################################################################
# Base Window Classes
######################################################################################

class BaseWindow(xbmcgui.WindowXMLDialog):
	def startProgress(self):
		self._title_fg = FB.theme.get('title_fg','FF000000')
		self._progMessageSave = self.getControl(104).getLabel()
		self.getControl(310).setVisible(True)
		
	def setProgress(self,pct,message=''):
		w = (pct/100.0)*1060
		self.getControl(310).setWidth(w)
		self.getControl(104).setLabel(TITLE_FORMAT % (self._title_fg,message))
		
	def endProgress(self):
		self.getControl(310).setVisible(False)
		self.getControl(104).setLabel(self._progMessageSave)
	
class PageWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.next = ''
		self.prev = ''
		self.pageData = None
		self._firstPage = 'First Page'
		self._lastPage = 'Last Page'
		BaseWindow.__init__( self, *args, **kwargs )
		
	def onClick( self, controlId ):
		pass
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_SELECT_ITEM or action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
			elif self.getFocusId() == 202:
				if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
			elif self.getFocusId() == 105:
				self.pageMenu()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_NEXT_ITEM:
			if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
		elif action == ACTION_PREV_ITEM:
			if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def pageMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Go to ...',[self._firstPage,self._lastPage,'Goto page #'])
		if idx == 0: self.gotoPage(1)
		elif idx == 1: self.gotoPage(-1)
		elif idx == 2: self.askPageNumber()
		
	def askPageNumber(self):
		page = doKeyboard('Enter Page Number')
		try: int(page)
		except: return
		self.gotoPage(page)
		
	def setupPage(self,pageData):
		self.pageData = pageData
		self.getControl(200).setEnabled(pageData.prev)
		self.getControl(202).setEnabled(pageData.next)
		self.getControl(105).setLabel(TITLE_FORMAT % (FB.theme['title_fg'],pageData.getPageDisplay()))
		
	def gotoPage(self,page): pass

######################################################################################
# Image Dialog
######################################################################################
class ImagesDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.images = kwargs.get('images')
		self.index = 0
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.setTheme()
		self.getControl(200).setEnabled(len(self.images) > 1)
		self.getControl(202).setEnabled(len(self.images) > 1)
		self.showImage()
		
	def setTheme(self):
		xbmcgui.lock()
		try:
			self.getControl(101).setColorDiffuse(FB.theme.get('window_bg','FF222222')) #panel bg
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
		
	def onClick( self, controlId ):
		pass
                       
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
		
	def onAction(self,action):
		if action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 200:
				self.nextImage()
			elif self.getFocusId() == 202:
				self.prevImage()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				self.nextImage()
			elif self.getFocusId() == 202:
				self.prevImage()
		elif action == ACTION_NEXT_ITEM:
			self.nextImage()
		elif action == ACTION_PREV_ITEM:
			self.prevImage()
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
######################################################################################
# Post Dialog
######################################################################################
class PostDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.title = self.post.title
		self.posted = False
		self.display_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']%s[/COLOR]\n \n'
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(122).setText(' ') #to remove scrollbar
		if self.post.quote:
			format = FB.formats.get('quote')
			self.addLine(format.replace('!USER!',self.post.quser).replace('!POSTID!',self.post.pid).replace('!QUOTE!',self.post.quote))
		self.setTheme()
	
	def setTheme(self):
		xbmcgui.lock()
		try:
			title_bg = FB.theme.get('title_bg','FFFFFFFF')
			title_fg = FB.theme.get('title_fg','FF000000')
			self.getControl(251).setColorDiffuse(title_bg) #title bg
			self.getControl(300).setColorDiffuse(title_bg) #sep
			self.getControl(301).setColorDiffuse(title_bg) #sep
			self.getControl(302).setColorDiffuse(title_bg) #sep
			self.getControl(101).setColorDiffuse(FB.theme.get('window_bg','FF222222')) #panel bg
			self.getControl(351).setColorDiffuse(FB.theme.get('desc_bg',title_bg)) #desc bg
			self.getControl(103).setLabel(TITLE_FORMAT % (title_fg,'Post Reply'))
			self.getControl(104).setLabel('[B]Set Title[/B]',textColor=title_fg)
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
		
	def onClick( self, controlId ):
		pass
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 200:
				self.addLine()
			elif self.getFocusId() == 201:
				self.addLineMulti()
			elif self.getFocusId() == 202:
				self.postReply()
			elif self.getFocusId() == 120:
				self.editLine()
			elif self.getFocusId() == 104:
				self.setTitle()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				self.addLine()
			elif self.getFocusId() == 201:
				self.addLineMulti()
			elif self.getFocusId() == 202:
				self.postReply()
			elif self.getFocusId() == 120:
				self.editLine()
			elif self.getFocusId() == 104:
				self.setTitle()
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Options',['Delete Line'])
		if idx == 0: self.deleteLine()
		
	def getOutput(self):
		llist = self.getControl(120)
		out = ''
		for x in range(0,llist.size()):
			out += llist.getListItem(x).getProperty('text') + '\n'
		return out
		
	def updatePreview(self):
		disp = self.display_base % self.getOutput()
		self.getControl(122).reset()
		self.getControl(122).setText(disp)
			
	def addLine(self,line=''):
		if not line:
			keyboard = xbmc.Keyboard('','Enter Text')
			keyboard.doModal()
			if not keyboard.isConfirmed(): return False
			line = keyboard.getText()
		item = xbmcgui.ListItem(label=line.replace('\n',' '))
		#we set text separately so we can have the display be formatted...
		item.setProperty('text',line)
		self.getControl(120).addItem(item)
		self.getControl(120).selectItem(self.getControl(120).size()-1)
		self.updatePreview()
		return True
			
	def addLineMulti(self):
		while self.addLine(): pass
		
	def deleteLine(self):
		llist = self.getControl(120)
		pos = llist.getSelectedPosition()
		lines = []
		for x in range(0,llist.size()):
			if x != pos: lines.append(llist.getListItem(x).getProperty('text'))
		llist.reset()
		for line in lines:
			item = xbmcgui.ListItem(label=line)
			item.setProperty('text',line)
			llist.addItem(item)
		self.updatePreview()
	
	def editLine(self):
		item = self.getControl(120).getSelectedItem()
		keyboard = xbmc.Keyboard(item.getProperty('text'),'Edit Line')
		keyboard.doModal()
		if not keyboard.isConfirmed(): return
		line = keyboard.getText()
		item.setProperty('text',line)
		item.setLabel(line)
		self.updatePreview()
		#re.sub(q,'[QUOTE=\g<user>;\g<postid>]\g<quote>[/QUOTE]',re.sub('[\n\r\t]','',test3))
	
	def setTitle(self):
		keyboard = xbmc.Keyboard(self.title,'Enter Post Title')
		keyboard.doModal()
		if not keyboard.isConfirmed(): return
		title = keyboard.getText()
		self.getControl(104).setLabel('[B]%s[/B]' % title)
		self.title = title
	
	def dialogCallback(self,pct,message):
		self.prog.update(pct,message)
		
	def postReply(self):
		message = self.getOutput()
		self.prog = xbmcgui.DialogProgress()
		self.prog.create('Posting','Posting. Please wait...')
		self.prog.update(0)
		self.post.setMessage(self.title,message)
		try:
			FB.post(self.post,callback=self.dialogCallback)
		except:
			self.prog.close()
			raise
		self.prog.close()
		self.posted = True
		self.close()

######################################################################################
# Replies Window
######################################################################################
class RepliesWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		PageWindow.__init__( self, *args, **kwargs )
		self.tid = kwargs.get('tid','')
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.lastid = kwargs.get('lastid','')
		self.parent = kwargs.get('parent')
		self._firstPage = 'Oldest Post'
		self._lastPage = 'Newest Post'
		self.me = self.parent.parent.getUsername()
		
	
	def onInit(self):
		self.setTheme()
		self.getControl(201).setEnabled(self.parent.parent.hasLogin())
		page = '-1'
		if __addon__.getSetting('open_thread_to_oldest') == 'true': page = '1'
		self.fillRepliesList(page)
		self.setFocus(self.getControl(120))
	
	def setTheme(self):
		xbmcgui.lock()
		try:
			title_bg = FB.theme.get('title_bg','FFFFFFFF')
			title_fg = FB.theme.get('title_fg','FF000000')
			self.getControl(251).setColorDiffuse(title_bg) #title bg
			self.getControl(300).setColorDiffuse(title_bg) #sep
			self.getControl(301).setColorDiffuse(title_bg) #sep
			self.getControl(302).setColorDiffuse(title_bg) #sep
			self.getControl(101).setColorDiffuse(FB.theme.get('window_bg','FF222222')) #panel bg
			self.getControl(351).setColorDiffuse(FB.theme.get('desc_bg',title_bg)) #desc bg
			self.getControl(103).setLabel(TITLE_FORMAT % (title_fg,'Posts'))
			self.getControl(104).setLabel(TITLE_FORMAT % (title_fg,self.topic))
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
		
	def fillRepliesList(self,page=''):
		xbmcgui.lock()
		try:
			self.getControl(120).reset()
			replies, pageData = FB.getReplies(self.tid,self.fid,page,lastid=self.lastid)
			
			self.setupPage(pageData)
			desc_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']%s[/COLOR]\n \n'
			if __addon__.getSetting('show_oldest_post_top') != 'true': replies.reverse()
			for post in replies:
				title = post.title
				if not title: title = post.messageAsText()[:68].replace('\n',' ') + '...'
				url = ''
				if post.avatar: url = FB.makeURL(post.avatar)
				#print 'AVATAR: ' + url
				user = re.sub('<.*?>','',post.userName)
				item = xbmcgui.ListItem(label=user,label2=post.date + ': ' + title,iconImage=url)
				if post.title: item.setInfo('video',{'Genre':'bold'})
				if user == self.me: item.setInfo('video',{"Director":'me'})
				item.setProperty('message',desc_base % post.messageAsDisplay())
				item.setProperty('quotable',post.messageAsQuote())
				item.setProperty('post',post.postId)
				item.setProperty('images',','.join(post.imageURLs()))
				self.getControl(120).addItem(item)
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
			
	def postSelected(self):
		item = self.getControl(120).getSelectedItem()
		
	def onAction(self,action):
		#print "ACTION: " + str(action.getId()) + " FOCUS: " + str(self.getFocusId()) + " BC: " + str(action.getButtonCode())
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 201:
				self.openPostDialog()
			elif self.getFocusId() == 120:
				self.postSelected()
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 201:
				self.openPostDialog()
			elif self.getFocusId() == 120:
				self.postSelected()
		PageWindow.onAction(self,action)
	
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		options = ['Quote']
		delete = None
		images = None
		item = self.getControl(120).getSelectedItem()
		if item.getProperty('images'):
			images = len(options)
			options.append('View Images')
		if FB.canDelete(item.getLabel()):
			delete = len(options)
			options.append('Delete Post')
		idx = dialog.select('Options',options)
		if idx == 0: self.openPostDialog(quote=True)
		elif idx == images: self.showImages(item.getProperty('images'))
		elif idx == delete: self.deletePost()
		
	def showImages(self,imageliststring):
		images = imageliststring.split(',')
		base = os.path.join(__addon__.getAddonInfo('profile'),'slideshow')
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		image_files = []
		tot = len(images)
		prog = xbmcgui.DialogProgress()
		prog.create('Downloading','Downloading Images')
		try:
			for url,i in zip(images,range(0,len(images))):
				if prog.iscanceled(): break
				prog.update(int((i/float(tot))*100),'Downloading Images','File %s of %s' % (i+1,tot))
				fname = os.path.join(base,str(i) + '.jpg')
				image_files.append(fname)
				getFile(url,fname)
		except:
			ERROR('SHOW IMAGES DOWNLOAD ERROR')
			prog.close()
		prog.close()
		
		w = ImagesDialog("script-forumbrowser-imageviewer.xml" ,__addon__.getAddonInfo('path'),"Default",images=image_files,parent=self)
		w.doModal()
		del w
		#xbmc.executebuiltin('SlideShow('+base+')')
			
	def deletePost(self):
		item = self.getControl(120).getSelectedItem()
		post = PostMessage(item.getProperty('post'),self.tid,self.fid)
		if not post.pid: return
		prog = xbmcgui.DialogProgress()
		prog.create('Deleting','Deleting Post. Please wait...')
		prog.update(0)
		try:
			FB.deletePost(post)
		except:
			prog.close()
			raise
		prog.close()
		self.fillRepliesList(self.pageData.page)
		
	def openPostDialog(self,quote=False):
		if quote:
			item = self.getControl(120).getSelectedItem()
			quot = item.getProperty('quotable')
			user = item.getLabel()
		else:
			item = self.getControl(120).getListItem(0)
			quot = ''
			user=''
		if not item.getProperty('post'): item = self.getControl(120).getListItem(1)
		post = item.getProperty('post')
		pm = PostMessage(post,self.tid,self.fid)
		if quote: pm.setQuote(user,quot)
		w = PostDialog(	"script-forumbrowser-post.xml" ,__addon__.getAddonInfo('path'),"Default",post=pm,parent=self)
		w.doModal()
		posted = w.posted
		del w
		if posted:
			self.fillRepliesList('-1')
	
	def gotoPage(self,page):
		self.fillRepliesList(page)

######################################################################################
# Threads Window
######################################################################################
class ThreadsWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.parent = kwargs.get('parent')
		self.me = self.parent.getUsername()
		PageWindow.__init__( self, *args, **kwargs )
		
	def onInit(self):
		self.setTheme()
		self.fillThreadList()
		self.setFocus(self.getControl(120))
		
	def setTheme(self):
		try:
			xbmcgui.lock()
			title_bg = FB.theme.get('title_bg','FFFFFFFF')
			title_fg = FB.theme.get('title_fg','FF000000')
			self.getControl(251).setColorDiffuse(title_bg) #title bg
			self.getControl(300).setColorDiffuse(title_bg) #sep
			self.getControl(301).setColorDiffuse(title_bg) #sep
			self.getControl(302).setColorDiffuse(title_bg) #sep
			self.getControl(101).setColorDiffuse(FB.theme.get('window_bg','FF222222')) #panel bg
			#self.getControl(121).setColorDiffuse(title_bg) #scroll bar doesn't work
			self.getControl(351).setColorDiffuse(FB.theme.get('desc_bg',title_bg)) #desc bg
			self.getControl(103).setLabel(TITLE_FORMAT % (title_fg,'Threads'))
			self.getControl(104).setLabel(TITLE_FORMAT % (title_fg,self.topic))
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
		
	def fillThreadList(self,page=''):
		try:
			if self.fid == 'subscriptions':
				self.startProgress()
				threads,pageData = FB.getSubscriptions(page,callback=self.setProgress)
				self.endProgress()
			else:
				threads,pageData = FB.getThreads(self.fid,page)
			xbmcgui.lock()
			self.getControl(120).reset()
			self.setupPage(pageData)
			desc_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']Last Post By: %s[/COLOR]'
			desc_bold = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+'][B]Last Post By: %s[/B][/COLOR]'
			
			for t in threads:
				tdict = t.groupdict()
				starter = tdict.get('starter','Unknown')
				title = tdict.get('title','')
				last = tdict.get('lastposter','?')
				tid = tdict.get('threadid','')
				fid = tdict.get('forumid','')
				item = xbmcgui.ListItem(label=starter,label2=convertHTMLCodes(re.sub('<.*?>','',title)))
				if '<strong>' in title: item.setInfo('video',{"Genre":'bold'})
				if starter == self.me: item.setInfo('video',{"Director":'me'})
				#if last == self.me: item.setInfo('video',{"Studio":'me'})
				item.setProperty("id",tid)
				item.setProperty("fid",fid)
				if last == self.me:
					item.setProperty("last",desc_bold % last)
				else:
					item.setProperty("last",desc_base % last)
				item.setProperty("lastid",tdict.get('lastid',''))
				self.getControl(120).addItem(item)
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
						
	def openRepliesWindow(self):
		item = self.getControl(120).getSelectedItem()
		tid = item.getProperty('id')
		fid = item.getProperty('fid') or self.fid
		lastid = item.getProperty('lastid')
		topic = item.getLabel2()
		w = RepliesWindow("script-forumbrowser-replies.xml" , __addon__.getAddonInfo('path'), "Default",tid=tid,fid=fid,lastid=lastid,topic=topic,parent=self)
		w.doModal()
		del w
			
	def onClick( self, controlId ):
		pass
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			pass
		elif action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 120:
				self.openRepliesWindow()
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 120:
				self.openRepliesWindow()
		PageWindow.onAction(self,action)
		
	def gotoPage(self,page):
		self.fillThreadList(page)

######################################################################################
# Forums Window
######################################################################################
class ForumsWindow(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		FB.setLogin(self.getUsername(),self.getPassword())
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def getUsername(self):
		return __addon__.getSetting('login_user_' + FB.forum.replace('.','_'))
		
	def getPassword(self):
		return __addon__.getSetting('login_pass_' + FB.forum.replace('.','_'))
		
	def hasLogin(self):
		return self.getUsername() != '' and self.getPassword() != ''
		
	def onInit(self):
		self.fillForumList()
		self.setFocus(self.getControl(120))
		
	def fillForumList(self):
		try:
			xbmcgui.lock()
			title_bg = FB.theme.get('title_bg','FFFFFFFF')
			title_fg = FB.theme.get('title_fg','FF000000')
			self.getControl(251).setColorDiffuse(title_bg) #title bg
			self.getControl(300).setColorDiffuse(title_bg) #sep
			self.getControl(301).setColorDiffuse(title_bg) #sep
			self.getControl(302).setColorDiffuse(title_bg) #sep
			self.getControl(101).setColorDiffuse(FB.theme.get('window_bg','FF222222')) #panel bg
			self.getControl(351).setColorDiffuse(FB.theme.get('desc_bg',title_bg)) #desc bg
			self.getControl(103).setLabel(TITLE_FORMAT % (title_fg,'Forums'))
			self.getControl(104).setLabel(TITLE_FORMAT % (title_fg,FB.forum))
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
		forums, logo = FB.getForums()
		try:
			xbmcgui.lock()
			self.getControl(120).reset()
			self.getControl(250).setImage(logo)
			#print forums
			desc_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']%s[/COLOR]'
			for f in forums:
				#print f.group(0)
				fdict = f.groupdict()
				fid = fdict.get('forumid','')
				title = fdict.get('title','ERROR')
				desc = fdict.get('description') or 'No Description'
				sub = fdict.get('subforum')
				if sub:
					text = '[I][COLOR FFBBBBBB]%s[/COLOR][/I] '
					desc = 'Sub-Forum'
				else:
					text = '[B]%s[/B]'
				title = convertHTMLCodes(re.sub('<.*?>','',title))
				item = xbmcgui.ListItem(label=text % title)
				item.setProperty("description",desc_base % convertHTMLCodes(re.sub('<.*?>','',desc)))
				item.setProperty("topic",title)
				item.setProperty("id",fid)
				self.getControl(120).addItem(item)
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
			
	def openThreadsWindow(self):
		item = self.getControl(120).getSelectedItem()
		fid = item.getProperty('id')
		topic = item.getProperty('topic')
		w = ThreadsWindow("script-forumbrowser-threads.xml" , __addon__.getAddonInfo('path'), "Default",fid=fid,topic=topic,parent=self)
		w.doModal()
		del w
		
	def openSubscriptionsWindow(self):
		fid = 'subscriptions'
		topic = 'Subscriptions'
		w = ThreadsWindow("script-forumbrowser-threads.xml" , __addon__.getAddonInfo('path'), "Default",fid=fid,topic=topic,parent=self)
		w.doModal()
		del w
		
	def changeForum(self):
		fpath = xbmc.translatePath('special://home/addons/script.forum.browser/forums/')
		flist = os.listdir(fpath)
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Forums',flist)
		if idx < 0: return
		FB.reloadForumData(flist[idx])
		self.resetForum()
		self.fillForumList()
		__addon__.setSetting('last_forum',FB.forum)
		
	def onClick( self, controlId ):
		pass
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		#print "ACTION: " + str(action.getId()) + " FOCUS: " + str(self.getFocusId()) + " BC: " + str(action.getButtonCode())
		if action == ACTION_CONTEXT_MENU:
			pass
		elif action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 200:
				self.openSettings()
			elif self.getFocusId() == 201:
				self.openSubscriptionsWindow()
			elif self.getFocusId() == 202:
				self.changeForum()
			else:
				self.openThreadsWindow()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				self.openSettings()
			elif self.getFocusId() == 201:
				self.openSubscriptionsWindow()
			elif self.getFocusId() == 202:
				self.changeForum()
			elif self.getFocusId() == 120:
				self.openThreadsWindow()
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def resetForum(self,hidelogo=True):
		FB.setLogin(self.getUsername(),self.getPassword())
		self.getControl(201).setEnabled(self.hasLogin())
		if hidelogo: self.getControl(250).setImage('')
		
	def openSettings(self):
		doSettings()
		self.resetForum(False)

######################################################################################
# Functions
######################################################################################

def calculatePage(low,high,total):
	low = int(low.replace(',',''))
	high = int(high.replace(',',''))
	total = int(total.replace(',',''))
	if high == total: return -1
	return str(int(round(float(high)/((high-low)+1))))
	
def cConvert(m): return chr(int(m.group(1)))
def convertHTMLCodes(html):
	return 		re.sub('&#(\d{1,3});',cConvert,html)\
				.replace("&lt;", "<")\
				.replace("&gt;", ">")\
				.replace("&amp;", "&")\
				.replace("&quot;",'"')\
				.replace("&apos;","'")
				
def messageToText(html):
	html = re.sub('[\n\r\t]','',html)
	html = re.sub('<br.*?>','\n',html)
	html = html.replace('</table>','\n\n')
	html = html.replace('</div>','\n')
	html = re.sub('<.*?>','',html)
	return convertHTMLCodes(html).strip()
	
def messageToDisplay(html):
	html = re.sub('[\n\r\t]','',html)
	qfilter = FB.filters.get('quote')
	if qfilter:
		try:
			ureplace = '_________________________\nQuote:\nOriginally posted by: [B]%s\n[/B][I]%s[/I]\n_________________________\n'
			replace = '_________________________\n[B]Quote:[/B]\n[I]%s[/I]\n_________________________\n'
			for m in re.finditer(qfilter,html):
				#Convert images here so we can skip italics
				quote = re.sub('<img\s.+?src="(?P<url>http://.+?)".+?/>','[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]A[/COLOR][COLOR FF0000FF]G[/COLOR][COLOR FFFF00FF]E[/COLOR]: \g<url>',m.group('quote'))
				if m.group('user'):
					html = html.replace(m.group(0),ureplace % (m.group('user'),quote))
				else:
					html = html.replace(m.group(0),replace % quote)
		except:
			ERROR('POST QUOTE FORMATTING')
	cfilter = FB.filters.get('code')
	if cfilter:
		try:
			replace = '_________________________\n[B]Code:[/B]\n[COLOR '+FB.theme.get('post_code','FF999999')+']%s[/COLOR]\n_________________________\n'
			for m in re.finditer(cfilter,html):
				html = html.replace(m.group(0),replace % m.group('code'))
		except:
			ERROR('POST CODE FORMATTING')
	sfilter = FB.smilies.get('regex')
	if sfilter:
		try:
			color = FB.smilies.get('color','FF888888')
			for m in re.finditer(sfilter,html):
				html = html.replace(m.group(0),'[COLOR %s]%s[/COLOR]' % (color,FB.smilies.get(m.group('smiley'),'')))
		except:
			ERROR('SMILEY CONVERSION ERROR')
	html = re.sub('<img\s.+?src="(?P<url>http://.+?)".+?/>','[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]A[/COLOR][COLOR FF0000FF]G[/COLOR][COLOR FFFF00FF]E[/COLOR]: [I]\g<url>[/I]',html)
	html = re.sub('<a\shref="(?P<url>.+?)".*?>(?P<text>.+?)</a>','\g<text> (Link: [B]\g<url>[/B])',html)
	html = re.sub('<br.*?>','\n',html)
	html = html.replace('</table>','\n\n')
	html = html.replace('</div>','\n')
	html = re.sub('<.*?>','',html)
	return convertHTMLCodes(html).strip()
	
def messageAsQuote(html):
	html = re.sub('[\n\r\t]','',html)
	qfilter = FB.filters.get('quote')
	if qfilter:
		try:
			for m in re.finditer(qfilter,html):
				html = html.replace(m.group(0),'')
		except:
			ERROR('POST CODE REMOVAL')
	html = re.sub('<br.*?>','\n',html)
	html = html.replace('</table>','\n\n')
	html = html.replace('</div>','\n')
	html = re.sub('<.*?>','',html)
	return convertHTMLCodes(html).strip()
	
def doKeyboard(prompt,default='',hidden=False):
	keyboard = xbmc.Keyboard(default,prompt)
	keyboard.setHiddenInput(hidden)
	keyboard.doModal()
	if not keyboard.isConfirmed(): return ''
	return keyboard.getText()
			
def setLogins():
	fpath = xbmc.translatePath('special://home/addons/script.forum.browser/forums/')
	flist = os.listdir(fpath)
	dialog = xbmcgui.Dialog()
	idx = dialog.select('Select Forum',flist)
	if idx < 0: return
	forum = flist[idx]
	user = doKeyboard('Enter Username',__addon__.getSetting('login_user_' + forum.replace('.','_')))
	if not user: return
	password = doKeyboard('Enter Password',__addon__.getSetting('login_pass_' + forum.replace('.','_')),True)
	if not password: return
	__addon__.setSetting('login_user_' + forum.replace('.','_'),user)
	__addon__.setSetting('login_pass_' + forum.replace('.','_'),password)
	
def doSettings():
	dialog = xbmcgui.Dialog()
	idx = dialog.select('Settings',['Set Logins','Settings'])
	if idx < 0: return
	if idx == 0: setLogins()
	elif idx == 1: __addon__.openSettings()
	
def clearDirFiles(filepath):
	if not os.path.exists(filepath): return
	for f in os.listdir(filepath):
		f = os.path.join(filepath,f)
		if os.path.isfile(f): os.remove(f)
		
def getFile(url,target=None):
	if not target: return #do something else eventually if we need to
	print 'frog'
	req = urllib2.urlopen(url)
	open(target,'w').write(req.read())
	req.close()
	
######################################################################################
# Startup
######################################################################################
if sys.argv[-1] == 'settings':
	doSettings()
else:
	FB = ForumBrowser(__addon__.getSetting('last_forum') or 'forum.xbmc.org')

	w = ForumsWindow("script-forumbrowser-forums.xml" , __addon__.getAddonInfo('path'), "Default")
	w.doModal()
	del w
	sys.modules.clear()
	