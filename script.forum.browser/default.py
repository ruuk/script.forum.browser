import urllib2, re, os, sys, time, urlparse, urllib
import xbmc, xbmcgui, xbmcaddon

__plugin__ = 'Forum Browser'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/forumbrowserxbmc/'
__date__ = '11-10-2010'
__version__ = '0.7.4'
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
			self.signature = pdict.get('signature','') or ''
		else:
			self.postId,self.date,self.userId,self.userName,self.avatar,self.title,self.message,self.signature = ('','','','ERROR','','ERROR','','')
			
	def getMessage(self):
		return self.message + self.signature
	
	def messageAsText(self):
		return messageToText(self.getMessage())
		
	def messageAsDisplay(self):
		return MC.messageToDisplay(self.getMessage())
		
	def messageAsQuote(self):
		return MC.messageAsQuote(self.message)
		
	def imageURLs(self):
		return re.findall('<img\s.+?src="(http://.+?)".+?/>',self.message)
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.message,re.S)
		
	def linkURLs(self):
		return re.finditer('<a.+?href="(?P<url>.+?)".*?>(?P<text>.+?)</a>',self.getMessage(),re.S)
		
	def threadLinkURLs(self):
		if FB.filters.get('thread_link'): return re.finditer(FB.filters.get('thread_link'),self.getMessage(),re.S)
		return None
		
	def postLinkURLs(self):
		if FB.filters.get('post_link'): return re.finditer(FB.filters.get('post_link'),self.getMessage(),re.S)
		return None
			
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
		self.topic = ''
		self.tid = ''
		
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
	
	def setThreadData(self,topic,threadid):
		self.topic = topic
		self.tid = threadid
				
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
		
	def getReplies(self,threadid,forumid,page='',lastid='',pid=''):
		url = self.getPageUrl(page,'replies',tid=threadid,fid=forumid,lastid=lastid,pid=pid)
		print url
		html = self.readURL(url)
		if not html: return None
		replies = re.findall(self.filters['replies'],re.sub('[\n\r\t]','',html))
		topic = re.search(self.filters.get('thread_topic','%#@+%#@'),re.sub('[\n\r\t]','',html))
		if not threadid:
			threadid = re.search(self.filters.get('thread_id','%#@+%#@'),re.sub('[\n\r\t]','',html))
			threadid = threadid and threadid.group(1) or ''
		topic = topic and topic.group(1) or ''
		sreplies = []
		for r in replies:
			try:
				post = ForumPost(re.search(self.filters['post'],re.sub('[\n\r\t]','',r)))
				sreplies.append(post)
			except:
				post = ForumPost()
				sreplies.append(post)
		pd = self.getPageData(html,page)
		pd.setThreadData(topic,threadid)
		return sreplies, pd
		
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
		
	def getPageData(self,html,page):
		next_page = re.search(self.filters['next'],html,re.S)
		prev_page= None
		if page != '1':
			prev_page = re.search(self.filters['prev'],html,re.S)
		page_disp = re.search(self.filters['page'],html)
		return PageData(page_disp,next_page,prev_page)
		
	def getPageUrl(self,page,sub,pid='',tid='',fid='',lastid=''):
		if sub == 'replies' and page and int(page) < 0:
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
			url = url.replace('!POSTID!',post.pid).replace('!THREADID!',post.tid).replace('!FORUMID!',post.fid)
		else:
			url = url.replace('!POSTID!',pid).replace('!THREADID!',tid).replace('!FORUMID!',fid)
		#removes empty vars
		return re.sub('(?:\w+=&)|(?:\w+=$)','',url)
		
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
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if controlID == 200:
			if self.pageData.prev: self.gotoPage(self.pageData.getPrevPage())
		elif controlID == 202:
			if self.pageData.next: self.gotoPage(self.pageData.getNextPage())
		elif controlID == 105:
			self.pageMenu()
	
	def onAction(self,action):
		if action == ACTION_PARENT_DIR:
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
		page = xbmcgui.Dialog().numeric(0,'Enter Page Number')
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
			xbmcgui.lock()
			try:
				for line in format.replace('!USER!',self.post.quser).replace('!POSTID!',self.post.pid).replace('!QUOTE!',self.post.quote).split('\n'):
					self.addLine(line,emptyok=True)
			except:
				xbmcgui.unlock()
			else:
				xbmcgui.unlock()
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
		
	def onClick( self, controlID ):
		if controlID == 200:
			self.addLine()
		elif controlID == 201:
			self.addLineMulti()
		elif controlID == 202:
			self.postReply()
		elif controlID == 120:
			self.editLine()
		elif controlID == 104:
			self.setTitle()
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
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
		self.getControl(122).setText(self.parseCodes(disp).replace('\n','[CR]'))
			
	def addLine(self,line='',emptyok=False):
		if not line and not emptyok:
			keyboard = xbmc.Keyboard('','Enter Text')
			keyboard.doModal()
			if not keyboard.isConfirmed(): return False
			line = keyboard.getText()
		item = xbmcgui.ListItem(label=self.displayLine(line))
		#we set text separately so we can have the display be formatted...
		item.setProperty('text',line)
		self.getControl(120).addItem(item)
		self.getControl(120).selectItem(self.getControl(120).size()-1)
		self.updatePreview()
		return True
		
	def displayLine(self,line):
		return line	.replace('\n',' ')\
					.replace('[/B]','[/B ]')\
					.replace('[/I]','[/I ]')\
					.replace('[/B]','[/B ]')\
					.replace('[/COLOR]','[/COLOR ]')
					
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
		item.setLabel(self.displayLine(line))
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
		
	def parseCodes(self,text):
		text = re.sub('\[QUOTE=(?P<user>\w+)(?:;\d+)*\](?P<quote>.+?)\[/QUOTE\](?is)',MC.quoteConvert,text)
		text = re.sub('\[QUOTE\](?P<quote>.+?)\[(?P<user>)?/QUOTE\](?is)',MC.quoteConvert,text)
		text = re.sub('\[CODE\](?P<code>.+?)\[/CODE\](?is)',MC.codeReplace,text)
		text = re.sub('\[PHP\](?P<php>.+?)\[/PHP\](?is)',MC.phpReplace,text)
		text = re.sub('\[HTML\](?P<html>.+?)\[/HTML\](?is)',MC.htmlReplace,text)
		text = re.sub('\[IMG\](?P<url>.+?)\[/IMG\](?is)',MC.quoteImageReplace,text)
		text = re.sub('\[URL="(?P<url>.+?)"\](?P<text>.+?)\[/URL\](?is)',MC.linkReplace,text)
		return text

######################################################################################
# Replies Window
######################################################################################
class RepliesWindow(PageWindow):
	def __init__( self, *args, **kwargs ):
		PageWindow.__init__( self, *args, **kwargs )
		self.tid = kwargs.get('tid','')
		self.fid = kwargs.get('fid','')
		self.pid = ''
		self.topic = kwargs.get('topic','')
		self.lastid = kwargs.get('lastid','')
		self.parent = kwargs.get('parent')
		self._firstPage = 'Oldest Post'
		self._lastPage = 'Newest Post'
		self.me = self.parent.parent.getUsername()
		self.posts = {}
		
	
	def onInit(self):
		self.setTheme()
		self.getControl(201).setEnabled(self.parent.parent.hasLogin())
		self.showThread()
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
		
	def showThread(self,nopage=False):
		if nopage:
			page = ''
		else:
			page = '-1'
			if __addon__.getSetting('open_thread_to_oldest') == 'true': page = '1'
		
		self.fillRepliesList(page)
		
		title_fg = FB.theme.get('title_fg','FF000000')
		self.getControl(104).setLabel(TITLE_FORMAT % (title_fg,self.topic))
		self.pid = ''
		
	def fillRepliesList(self,page=''):
		xbmcgui.lock()
		try:
			self.getControl(120).reset()
			replies, pageData = FB.getReplies(self.tid,self.fid,page,lastid=self.lastid,pid=self.pid)
			if not self.topic: self.topic = pageData.topic
			if not self.tid: self.tid = pageData.tid
			self.setupPage(pageData)
			desc_base = '[COLOR '+FB.theme.get('desc_fg',FB.theme.get('title_fg','FF000000'))+']%s[/COLOR]\n \n'
			if __addon__.getSetting('show_oldest_post_top') != 'true': replies.reverse()
			self.posts = {}
			select = -1
			for post,idx in zip(replies,range(0,len(replies))):
				#print post.postId + ' ' + self.pid
				if post.postId == self.pid: select = idx
				self.posts[post.postId] = post
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
				item.setProperty('post',post.postId)
				self.getControl(120).addItem(item)
			if select > -1: self.getControl(120).selectItem(int(select))
		except:
			xbmcgui.unlock()
			raise
		xbmcgui.unlock()
			
	def makeLinksArray(self,miter):
		urls = []
		for m in miter:
			urls.append(m)
		return urls
		
	def postSelected(self):
		item = self.getControl(120).getSelectedItem()
		
	def onClick(self,controlID):
		if controlID == 201:
			self.openPostDialog()
		elif controlID == 120:
			self.postSelected()
		PageWindow.onClick(self,controlID)
		
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			self.doMenu()
		PageWindow.onAction(self,action)
	
	def doMenu(self):
		options = ['Quote']
		delete = None
		images = None
		link_images = None
		links = None
		thread_links = None
		post_links = None
		item = self.getControl(120).getSelectedItem()
		post = self.posts.get(item.getProperty('post'))
		img_urls = post.imageURLs()
		link_img_urls = post.linkImageURLs()
		link_urls = self.makeLinksArray(post.linkURLs())
		thread_link_urls = self.makeLinksArray(post.threadLinkURLs())
		post_link_urls = self.makeLinksArray(post.postLinkURLs())
		if img_urls:
			images = len(options)
			options.append('View Images')
		if link_img_urls:
			link_images = len(options)
			options.append('View Link Images')
		if thread_link_urls:
			thread_links = len(options)
			options.append('Follow Thread Link')
		if post_link_urls:
			post_links = len(options)
			options.append('Follow Post Link')
		if link_urls:
			links = len(options)
			options.append('Download A Link')
		if FB.canDelete(item.getLabel()):
			delete = len(options)
			options.append('Delete Post')
		idx = xbmcgui.Dialog().select('Options',options)
		if idx == 0: self.openPostDialog(quote=post.messageAsQuote())
		elif idx == images: self.showImages(img_urls)
		elif idx == link_images: self.showImages(link_img_urls)
		elif idx == thread_links: self.followThreadLink(thread_link_urls)
		elif idx == post_links: self.followPostLink(post_link_urls)
		elif idx == links: self.downloadLinks(link_urls)
		elif idx == delete: self.deletePost()
		
	def followPostLink(self,linkdatas):
		texts = []
		for m in linkdatas: texts.append('%s - (Post ID: %s)' % (m.group('text'),m.group('postid')))
		idx = xbmcgui.Dialog().select('Options',texts)
		if idx < 0: return
		postid = linkdatas[idx].group('postid')
		if postid:
			self.pid = postid
			self.tid = ''
			self.topic = ''
			self.showThread(nopage=True)
		
	def followThreadLink(self,linkdatas):
		texts = []
		for m in linkdatas: texts.append('%s - (Thread ID: %s)' % (m.group('text'),m.group('threadid')))
		idx = xbmcgui.Dialog().select('Options',texts)
		if idx < 0: return
		threadid = linkdatas[idx].group('threadid')
		if threadid:
			self.tid = threadid
			self.topic = ''
			self.showThread()
		
	def downloadLinks(self,links):
		texts = []
		for m in links: texts.append('%s - (%s)' % (m.group('text'),m.group('url')))
		idx = xbmcgui.Dialog().select('Options',texts)
		if idx < 0: return
		url = links[idx].group('url')
		base = xbmcgui.Dialog().browse(3,'Choose Target Directory','files')
		if not base: return
		fname,ftype = Downloader(message='Downloading File').downloadURL(base,url)
		if not fname: return
		xbmcgui.Dialog().ok('Done','Downloaded file: ',fname,'Type: %s' % ftype)
			
	def showImages(self,images):
		base = os.path.join(__addon__.getAddonInfo('profile'),'slideshow')
		if not os.path.exists(base): os.makedirs(base)
		clearDirFiles(base)
		image_files = Downloader(message='Downloading Images').downloadURLs(base,images,'.jpg')
		if not image_files: return
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
		
	def openPostDialog(self,quote=''):
		if quote:
			item = self.getControl(120).getSelectedItem()
			user = item.getLabel()
		else:
			item = self.getControl(120).getListItem(0)
			user=''
		if not item.getProperty('post'): item = self.getControl(120).getListItem(1)
		post = item.getProperty('post')
		pm = PostMessage(post,self.tid,self.fid)
		if quote: pm.setQuote(user,quote)
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
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
	
	def onClick( self, controlID ):
		if controlID == 120:
			self.openRepliesWindow()
		PageWindow.onClick(self,controlID)
	
	def onAction(self,action):
		if action == ACTION_CONTEXT_MENU:
			pass
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
		MC.resetRegex()
		self.resetForum()
		self.fillForumList()
		__addon__.setSetting('last_forum',FB.forum)
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onClick( self, controlID ):
		if controlID == 200:
			self.openSettings()
		elif controlID == 201:
			self.openSubscriptionsWindow()
		elif controlID == 202:
			self.changeForum()
		elif controlID == 120:
			self.openThreadsWindow()
	
	def onAction(self,action):
		#print "ACTION: " + str(action.getId()) + " FOCUS: " + str(self.getFocusId()) + " BC: " + str(action.getButtonCode())
		if action == ACTION_CONTEXT_MENU:
			pass
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def resetForum(self,hidelogo=True):
		FB.setLogin(self.getUsername(),self.getPassword())
		self.getControl(201).setEnabled(self.hasLogin())
		if hidelogo: self.getControl(250).setImage('')
		
	def openSettings(self):
		doSettings()
		self.resetForum(False)

######################################################################################
# Message Converter
######################################################################################
class MessageConverter:
	def __init__(self):
		self.resetOrdered(False)
		self.resetRegex()
		
		#static replacements
		self.quoteReplace = '\n_________________________\n[B]Quote:[/B]\nOriginally posted by: [B]%s[/B]\n[I]%s[/I]\n_________________________\n'
		self.aQuoteReplace = '\n_________________________\n[B]Quote:[/B]\n[I]%s[/I]\n_________________________\n'
		self.quoteImageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]A[/COLOR][COLOR FF0000FF]G[/COLOR][COLOR FFFF00FF]E[/COLOR]: \g<url>'
		self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]A[/COLOR][COLOR FF0000FF]G[/COLOR][COLOR FFFF00FF]E[/COLOR]: [I]\g<url>[/I]'
		self.linkReplace = '\g<text> (Link: [B]\g<url>[/B])'
		
		#static filters
		self.imageFilter = re.compile('<img[^<>]+?src="(?P<url>http://.+?)"[^<>]+?/>')
		self.linkFilter = re.compile('<a.+?href="(?P<url>.+?)".*?>(?P<text>.+?)</a>')
		self.ulFilter = re.compile('<ul>(.+?)</ul>')
		#<span style="text-decoration: underline">Underline</span>
		self.olFilter = re.compile('<ol.+?>(.+?)</ol>')
		self.brFilter = re.compile('<br[ /]{0,2}>')
		self.blockQuoteFilter = re.compile('<blockquote>(.+?)</blockquote>',re.S)
		self.colorFilter = re.compile('<font color="(.+?)">(.+?)</font>')
		self.colorFilter2 = re.compile('<span.*?style=".*?color: ?(.+?)".*?>(.+?)</span>')
		self.tagFilter = re.compile('<[^<>]+?>',re.S)
		
	def resetRegex(self):
		self.lineFilter = re.compile('[\n\r\t]')
		f = FB.filters.get('quote')
		self.quoteFilter = f and re.compile(f) or None
		f = FB.filters.get('code')
		self.codeFilter = f and re.compile(f) or None
		f = FB.filters.get('php')
		self.phpFilter = f and re.compile(f) or None
		f = FB.filters.get('html')
		self.htmlFilter = f and re.compile(f) or None
		f = FB.smilies.get('regex')
		self.smileyFilter = f and re.compile(f) or None
		
		#dynamic replacements
		self.codeReplace = '\n_________________________\n[B]Code:[/B]\n[COLOR '+FB.theme.get('post_code','FF999999')+']\g<code>[/COLOR]\n_________________________\n'
		self.phpReplace = '\n_________________________\n[B]PHP Code:[/B]\n[COLOR '+FB.theme.get('post_code','FF999999')+']\g<php>[/COLOR]\n_________________________\n'
		self.htmlReplace = '\n_________________________\n[B]HTML Code:[/B]\n[COLOR '+FB.theme.get('post_code','FF999999')+']\g<html>[/COLOR]\n_________________________\n'
		self.smileyReplace = '[COLOR '+FB.smilies.get('color','FF888888')+']%s[/COLOR]'
		
	def resetOrdered(self,ordered):
		self.ordered = ordered
		self.ordered_count = 0
		
	def messageToDisplay(self,html):
		html = self.lineFilter.sub('',html)
		
		if self.quoteFilter: html = self.quoteFilter.sub(self.quoteConvert,html)
		if self.codeFilter: html = self.codeFilter.sub(self.codeReplace,html)
		if self.phpFilter: html = self.phpFilter.sub(self.phpReplace,html)
		if self.htmlFilter: html = self.htmlFilter.sub(self.htmlReplace,html)
		if self.smileyFilter: html = self.smileyFilter.sub(self.smileyConvert,html)
		
		html = self.imageFilter.sub(self.imageReplace,html)
		html = self.linkFilter.sub(self.linkReplace,html)
		html = self.ulFilter.sub(self.processBulletedList,html)
		html = self.olFilter.sub(self.processOrderedList,html)
		html = self.colorFilter.sub(self.convertColor,html)
		html = self.colorFilter2.sub(self.convertColor,html)
		html = self.brFilter.sub('[CR]',html)
		html = self.blockQuoteFilter.sub(self.processIndent,html)
		html = html.replace('<b>','[B]').replace('</b>','[/B]')
		html = html.replace('<i>','[I]').replace('</i>','[/I]')
		html = html.replace('<u>','_').replace('</u>','_')
		html = html.replace('<strong>','[B]').replace('</strong>','[/B]')
		html = html.replace('<em>','[I]').replace('</em>','[/I]')
		html = html.replace('</table>','[CR][CR]')
		html = html.replace('</div></div>','[CR]') #to get rid of excessive new lines
		html = html.replace('</div>','[CR]')
		html = self.tagFilter.sub('',html)
		html = self.removeNested(html,'[B]','[/B]')
		return convertHTMLCodes(html).strip()

	def removeNested(self,html,start,end):
		out = ''
		u=html.split(end)
		if len(u) == 1: return html
		tot = len(u)
		u.append('')
		for s,i in zip(u,range(0,tot)):
			next = u[i+1]
			if start in s:
				parts = s.split(start,1)
				out += parts[0] + start + parts[1].replace(start,'')
			else:
				if not next: out += end
				out += s
			if start in next:
				out += end
		return out

	def messageAsQuote(self,html):
		html = re.sub('[\n\r\t]','',html)
		if self.quoteFilter: html = self.quoteFilter.sub('',html)
		if self.codeFilter: html = self.codeFilter.sub('[CODE]\g<code>[/CODE]',html)
		if self.phpFilter: html = self.phpFilter.sub('[PHP]\g<php>[/PHP]',html)
		if self.htmlFilter: html = self.htmlFilter.sub('[HTML]\g<html>[/HTML]',html)
		if self.smileyFilter: html = self.smileyFilter.sub(self.smileyConvert,html)
		html = self.linkFilter.sub('[URL="\g<url>"]\g<text>[/URL]',html)
		html = self.imageFilter.sub('[IMG]\g<url>[/IMG]',html)
		html = self.colorFilter.sub(self.convertColor,html)
		html = self.colorFilter2.sub(self.convertColor,html)
		html = html.replace('<b>','[B]').replace('</b>','[/B]')
		html = html.replace('<i>','[I]').replace('</i>','[/I]')
		html = html.replace('<u>','[U]').replace('</u>','[/U]')
		html = html.replace('<strong>','[B]').replace('</strong>','[/B]')
		html = html.replace('<em>','[I]').replace('</em>','[/I]')
		html = re.sub('<br[^<>]*?>','\n',html)
		html = html.replace('</table>','\n\n')
		html = html.replace('</div>','\n')
		html = re.sub('<[^<>]+?>','',html)
		return convertHTMLCodes(html).strip()
		
	def smileyRawConvert(self,m):
		return FB.smilies.get(m.group('smiley'),'')
		
	def smileyConvert(self,m):
		return self.smileyReplace % FB.smilies.get(m.group('smiley'),'')
		
	def quoteConvert(self,m):
		quote = self.imageFilter.sub(self.quoteImageReplace,m.group('quote'))
		if m.group('user'):
			return self.quoteReplace % (m.group('user'),quote)
		else:
			return self.aQuoteReplace % quote
			
	def processIndent(self,m):
		return '    ' + re.sub('\n','\n    ',m.group(1)) + '\n'
		
	def convertColor(self,m):
		if m.group(1).startswith('#'):
			color = 'FF' + m.group(1)[1:].upper()
		else:
			color = m.group(1).lower()
		return '[COLOR %s]%s[/COLOR]' % (color,m.group(2))

	def processBulletedList(self,m):
		self.resetOrdered(False)
		return self.processList(m.group(1))
		
	def processOrderedList(self,m):
		self.resetOrdered(True)
		return self.processList(m.group(1))
			
	def processList(self,html):
		return re.sub('<li>(.+?)</li>',self.processItem,html) + '\n'

	def processItem(self,m):
		self.ordered_count += 1
		if self.ordered: bullet = str(self.ordered_count) + '.'
		else: bullet = '*'
		return  '%s %s\n' % (bullet,m.group(1))
		
######################################################################################
# Functions
######################################################################################

def calculatePage(low,high,total):
	low = int(low.replace(',',''))
	high = int(high.replace(',',''))
	total = int(total.replace(',',''))
	if high == total: return -1
	return str(int(round(float(high)/((high-low)+1))))
	
def cConvert(m): return unichr(int(m.group(1)))
def convertHTMLCodes(html):
	return 		re.sub('&#(\d{1,3});',cConvert,html)\
				.replace("&lt;", "<")\
				.replace("&gt;", ">")\
				.replace("&amp;", "&")\
				.replace("&quot;",'"')\
				.replace("&apos;","'")\
				.replace("&nbsp;"," ")
				
def messageToText(html):
	html = re.sub('[\n\r\t]','',html)
	html = re.sub('<br.*?>','\n',html)
	html = html.replace('</table>','\n\n')
	html = html.replace('</div></div>','\n') #to get rid of excessive new lines
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
	req = urllib2.urlopen(url)
	open(target,'w').write(req.read())
	req.close()

class Downloader:
	def __init__(self,header='Downloading',message=''):
		self.message = message
		self.prog = xbmcgui.DialogProgress()
		self.prog.create(header,message)
		self.current = 0
		self.display = ''
		self.file_pct = 0
		
	def progCallback(self,read,total):
		if self.prog.iscanceled(): return False
		pct = ((float(read)/total) * (self.file_pct)) + (self.file_pct * self.current)
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
				file_list.append(fname)
				self.getUrlFile(url,fname,callback=self.progCallback)
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
			self.display = 'Downloading %s' % os.path.basename(path)
			self.prog.update(0,self.message,self.display)
			t,ftype = self.getUrlFile(url,path,callback=self.progCallback)
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
		outfile = open(target, 'wb')
		read = 0
		bs = 1024 * 8
		while 1:
			block = urlObj.read(bs)
			if block == "": break
			read += len(block)
			outfile.write(block)
			if not callback(read, size): raise Exception
		outfile.close()
		urlObj.close()
		return (target,ftype)
	
######################################################################################
# Startup
######################################################################################
if sys.argv[-1] == 'settings':
	doSettings()
else:
	FB = ForumBrowser(__addon__.getSetting('last_forum') or 'forum.xbmc.org')
	MC = MessageConverter()

	w = ForumsWindow("script-forumbrowser-forums.xml" , __addon__.getAddonInfo('path'), "Default")
	w.doModal()
	del w
	sys.modules.clear()
	