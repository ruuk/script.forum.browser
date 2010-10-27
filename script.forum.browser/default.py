import urllib2, re, os
import xbmc, xbmcgui, xbmcaddon

__plugin__ = 'Forum Browser'
__author__ = 'ruuk (Rick Phillips)'
__url__ = 'http://code.google.com/p/forumbrowserxbmc/'
__date__ = '09-25-2010'
__version__ = '0.7.2'
__settings__ = xbmcaddon.Addon(id='script.forum.browser')
__language__ = __settings__.getLocalizedString

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

#href="forumdisplay.php?f=27&amp;order=desc&amp;page=171" title="Prev Page - Results 3,401 to 3,420 of 3,421">&lt;</a></td>
#href="forumdisplay.php?f=27&amp;order=desc&amp;page=2" title="Next Page - Results 21 to 40 of 3,421">&gt;</a></td>

class ForumPost:
		def __init__(self,post_tuple=None):
			if post_tuple:
				self.postId,self.date,self.userId,self.userName,self.avatar,self.topic,message = post_tuple
				self.message = messageToText(message)
			else:
				self.postId,self.date,self.userId,self.userName,self.avatar,self.topic,self.message = ('','','','ERROR','','ERROR','')
			
class ForumBrowser:
	def __init__(self,baseurl):
		self._url = baseurl
		self.browser = None
		
		self.urls = {}
		self.urls['forums'] = 'index.php'
		self.urls['threads'] = 'forumdisplay.php'
		self.urls['replies'] = 'showthread.php'
		
		self.urls['newpost'] = 'newreply.php'
		self.urls['deletepost'] = 'editpost.php'
		
		self.filters = {}
		self.filters['forums'] = '(?:(?<!\s/></a>)<a href="forumdisplay.php\?).*?f=(\d+)">(.*?)</a>.*?(?:(?:<div class="smallfont">(.*?)</div>)|,)'
		self.filters['threads'] = 'showthread.php\?.*?t=(\d+)"\sid="thread_title.*?>(.*?)</a>.*?window.open\(\'member.php\?.*?u=\d+\', \'_self\'\)">(.*?)</span.*?<a href="member.php.*?rel="nofollow">(.*?)</a>'
		#self.filters['replies'] = '<table id="post\d+.*?href="member.php.*?(\d+)">(.*?)</a>.*?<!-- message -->(.*?)<!-- / message -->'
		self.filters['replies'] = '<table\s.*?id="post\d+.*?<!-- / message -->'
		#this works for boxee but puts garbage for avatar url
		#self.filters['post'] = '<table\s.*?id="post(\d+).*?<!-- status icon and date -->.*?([\w\d-]+,\s\d+:\d+).*?<!-- / status icon and date -->.*?href="member.php.*?(\d+)">(\w+?)</a>(.*?)<!-- icon and title -->.*?(?:(?:<strong>(.*?)</strong>)|(?:</div>)).*?<!-- / icon and title -->.*?<!-- message -->(.*?)<!-- / message -->'
		self.filters['post'] = '<table\s.*?id="post(\d+).*?<!-- status icon and date -->.*?([\w\d-]+,\s\d+:\d+).*?<!-- / status icon and date -->.*?href="member.php.*?(\d+)">(.*?)</a>.*?src="((?:image.php?.*?u=\d+&amp;dateline=\d+)*|(?=.)*).*?<!-- icon and title -->.*?(?:(?:<strong>(.*?)</strong>)|(?:</div>)).*?<!-- / icon and title -->.*?<!-- message -->(.*?)<!-- / message -->'
		#Original for forum.xbmc.org
		#self.filters['post'] = '<table id="post(\d+).*?<!-- status icon and date -->.*?([\w\d-]+,\s\d+:\d+).*?<!-- / status icon and date -->.*?href="member.php.*?(\d+)">(.*?)</a>.*?src="((?:image.php?.*?u=\d+&amp;dateline=\d+)*|(?=.)*).*?<!-- icon and title -->.*?(?:(?:<strong>(.*?)</strong>)|(?:</div>)).*?<!-- / icon and title -->.*?<!-- message -->(.*?)<!-- / message -->'
		self.filters['next'] = 'Next\sPage\s-\sResults\s([\d,]+)\sto\s([\d,]+)\sof\s([\d,]+).*?(Next\sPage\s-\sResults\s[\d,]+\sto\s[\d,]+\sof\s[\d,]+)'
		self.filters['prev'] = 'Prev\sPage\s-\sResults\s([\d,]+)\sto\s([\d,]+)\sof\s([\d,]+).*?(Prev\sPage\s-\sResults\s[\d,]+\sto\s[\d,]+\sof\s[\d,]+)'
		self.filters['page'] = '>(Page\s\d+\sof\s\d+)<'
		#<img src="(image.php?u=\d+&amp;dateline=\d+)"
		#self.filters['next'] = 'href="forumdisplay.php?.*?f=(\d+)&amp;order=.*?page=.*?page=(\d+)"\stitle="(Next.*?)">'
		#self.filters['prev'] = 'href="forumdisplay.php?.*?f=(\d+)&amp;order=.*?(?:(?:page=.*?page=(\d+))|(?:sc))"\stitle="(Prev.*?)">'
		#self.filters['next_posts'] = 'href="showthread.php?.*?t=(\d+)&amp;.*?page=.*?page=(\d+)"\stitle="(Next.*?)">'
		#self.filters['prev_posts'] = 'href="showthread.php?.*?t=(\d+)(?:(?:&amp;page=(\d+)"\st)|(?:".*?\st))itle="(Prev.*?)">'
				
	def readURL(self,url):
		req = urllib2.urlopen(url)
		data = req.read()
		req.close()
		return data
		
	def makeURL(self,phppart):
		url = self._url + phppart
		return url.replace('&amp;','&')
		
	def getForums(self):
		html = self.readURL(self._url + self.urls['forums'])
		if not html: return None
		forums = re.findall(self.filters['forums'],re.sub('[\n\t\r]','',html))[1:]
		return forums
		
	def getThreads(self,forumid,page=''):
		if page: page = '&page=' + page
		html = self.readURL(self._url + self.urls['threads'] + '?f=%s' % (forumid) + page)
		if not html: return None
		threads = re.findall(self.filters['threads'],html,re.S)
		next_page = re.findall(self.filters['next'],html,re.S)
		prev_page= ''
		if page and page != '1':
			prev_page = re.findall(self.filters['prev'],html,re.S)
		if next_page: next_page = next_page[0]
		if prev_page: prev_page = prev_page[0]
		page_disp = re.findall(self.filters['page'],html)
		if page_disp: page_disp = page_disp[0]
		else: page_disp = ''
		return threads, prev_page, next_page, page_disp
		
	def getReplies(self,threadid,page=''):
		newpost = ''
		if page:
			if int(page) < 0:
				page = ''
				newpost = '&goto=newpost'
			else:
				page = '&page=' + page
		html = self.readURL(self._url + self.urls['replies'] + '?t=%s%s' % (threadid,newpost) + page)
		if not html: return None
		replies = re.findall(self.filters['replies'],html,re.S)
		sreplies = []
		for r in replies:
			try:
				post = ForumPost(re.findall(self.filters['post'],r,re.S)[0])
				sreplies.append(post)
			except:
				post = ForumPost()
				sreplies.append(post)
		next_page = re.findall(self.filters['next'],html,re.S)
		prev_page= ''
		if (page or newpost) and page != '1':
			prev_page = re.findall(self.filters['prev'],html,re.S)
		if next_page: next_page = next_page[0]
		if prev_page: prev_page = prev_page[0]
		page_disp = re.findall(self.filters['page'],html)
		if page_disp: page_disp = page_disp[0]
		else: page_disp = ''
		return sreplies, prev_page, next_page, page_disp
		
	def login(self,user,password):
		user = __settings__.getSetting('login_user')
		password = __settings__.getSetting('login_pass')
		import mechanize
		self.browser = mechanize.Browser()
		br = self.browser
		response = br.open(self._url)
		response.read()
		br.select_form(nr=0)
		br['vb_login_username'] = user
		br['vb_login_password'] = password
		response = br.submit()
		html = response.read()
		if re.search('<meta http-equiv="Refresh"',html): return True
		return False
		#<meta http-equiv="Refresh" content="2; URL=http://forum.xbmc.org/forumdisplay.php?f=27" />
		
	def checkLogin(self):
		if not self.browser:
			if not self.login('',''):
				print 'FORUM BROWSER: FAILED TO LOGIN'
				return False
		return True
		
	def post(self,post,title,message):
		if not self.checkLogin(): return False
		br = self.browser
		res = br.open(self._url + self.urls['newpost'] + '?do=newreply&noquote=1&p=%s' % post)
		res.read()
		selected = False
		try:
			br.select_form('vbform')
			selected = True
		except:
			if not self.login('',''): return False
			
		if not selected:
			try:
				br.select_form('vbform')
			except:
				return False
		
		try:
			br["title"] = title
			br["message"] = message
			br.submit()
		except:
			return False
			
		return True
		
		'''
		<a href="newreply.php?do=newreply&noquote=1&p=631419"
		
		<input type="text" class="bginput" name="title" value="" size="50" maxlength="85" tabindex="1" title="Optional" />
		<input type="hidden" name="s" value="" />
		<input type="hidden" name="securitytoken" value="1287945313-cf74dc14a706f8493b28ddd2bee830a5d18f6919" />
		<input type="hidden" name="do" value="postreply" />
		<input type="hidden" name="t" value="83499" />
		<input type="hidden" name="p" value="631291" />
		<input type="hidden" name="specifiedpost" value="1" />
		<input type="hidden" name="posthash" value="" />

		<input type="hidden" name="poststarttime" value="" />
		<input type="hidden" name="loggedinuser" value="8265" />
		<input type="hidden" name="multiquoteempty" id="multiquote_empty_input" value="" />
		<input type="submit" class="button" name="sbutton" id="vB_Editor_001_save" value="Submit Reply" accesskey="s" tabindex="1" />
		<input type="submit" class="button" name="preview" value="Preview Post" accesskey="r" tabindex="1" />
		
		<textarea name="message" id="vB_Editor_001_textarea" rows="10" cols="60" style="display:block; width:540px; height:250px" tabindex="1" dir="ltr">

		<input type="submit" class="button" name="sbutton" value="Submit Reply" accesskey="s" tabindex="1" />
		<input type="submit" class="button" name="preview" value="Preview Post" accesskey="r" tabindex="1" />
		'''
		
	def predicateDeletePost(self,formobj):
		if 'deletepost' in formobj.action: return True
		return False
		
	def deletePost(self,post):
		if not self.checkLogin(): return False
		br = self.browser
		res = br.open(self._url + self.urls['deletepost'] + '?do=editpost&p=%s' % post)
		html = res.read()
		selected = False
		#print html
		try:
			br.select_form(predicate=self.predicateDeletePost)
			selected = True
		except:
			#raise
			if not self.login('',''): return False
			
		if not selected:
			try:
				br.select_form(predicate=predicateDeletePost)
			except:
				return False
		
		try:
			br.find_control(name="deletepost").value = ["delete"]
			#br["reason"] = reason[:50]
			br.submit()
		except:
			return False
			
		return True
		#<a href="editpost.php?do=editpost&amp;p=631488" name="vB::QuickEdit::631488">
		
class PostDialog(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.post = kwargs.get('post')
		self.quote = kwargs.get('quote')
		self.quote_user = kwargs.get('quote_user')
		self.title = ''
		self.posted = False
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(122).setText(' ') #to remove scrollbar
		if self.quote: self.addLine('[QUOTE=%s]%s[/QUOTE]' % (self.quote_user,self.quote))
		
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
		disp = self.getOutput()
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
		
	
	def setTitle(self):
		keyboard = xbmc.Keyboard(self.title,'Enter Post Title')
		keyboard.doModal()
		if not keyboard.isConfirmed(): return
		title = keyboard.getText()
		self.getControl(104).setLabel(title)
		self.title = title
	
	def postReply(self):
		message = self.getOutput()
		prog = xbmcgui.DialogProgress()
		prog.create('Posting','Posting. Please wait...')
		prog.update(0)
		try:
			FB.post(self.post,self.title,message)
		except:
			prog.close()
			raise
		prog.close()
		self.posted = True
		self.close()
		
class BaseWindow(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		self.next = ''
		self.prev = ''
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
		
	def onClick( self, controlId ):
		pass
                       
	def onFocus( self, controlId ):
		self.controlId = controlId
		
	def onAction(self,action):
		if action == ACTION_SELECT_ITEM:
			if self.getFocusId() == 200:
				if self.prev: self.prevPage(self.prev)
			elif self.getFocusId() == 202:
				if self.next: self.nextPage(self.next)
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				if self.prev: self.prevPage(self.prev)
			elif self.getFocusId() == 202:
				if self.next: self.nextPage(self.next)
		elif action == ACTION_NEXT_ITEM:
			if self.next: self.nextPage(self.next)
		elif action == ACTION_PREV_ITEM:
			if self.prev: self.prevPage(self.prev)
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def setPrev(self,prev):
		self.prev = ''
		if prev:
			#item = xbmcgui.ListItem(label2=prev[-1])
			page = calculatePage(prev[0],prev[1],prev[2])
			if not page: page = '1'
			self.prev = page
			#item.setProperty("page",page)
			#item.setProperty("last",prev[-1])
			#self.getControl(120).addItem(item)
		self.getControl(200).setEnabled(self.prev != '')
		
	def setNext(self,next):
		self.next = ''
		if next:
			#item = xbmcgui.ListItem(label2=next[-1])
			page = calculatePage(next[0],next[1],next[2])
			if not page: page = '1'
			self.next = page
			#item.setProperty("page",page)
			#item.setProperty("last",next[-1])
			#self.getControl(120).addItem(item)
		self.getControl(202).setEnabled(self.next != '')
		
	def prevPage(self,page): pass
	def nextPage(self,page): pass

class RepliesWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.tid = kwargs.get('tid','')
		self.topic = kwargs.get('topic','')
		self.page = ''
		BaseWindow.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(104).setLabel(self.topic)
		self.fillRepliesList('-1')
		self.setFocus(self.getControl(120))
		
	def fillRepliesList(self,page=''):
		self.page = page
		self.getControl(120).reset()
		replies, prev, next, page_disp = FB.getReplies(self.tid,page)
		self.getControl(105).setLabel(page_disp)
		
		self.setPrev(prev)
		
		replies.reverse()
		for post in replies:
			topic = post.topic
			if not topic: topic = post.message[:68].replace('\n',' ') + '...'
			url = ''
			if post.avatar: url = FB.makeURL(post.avatar)
			item = xbmcgui.ListItem(label=re.sub('<.*?>','',post.userName),label2=post.date + ': ' + topic,thumbnailImage=url)
			if post.topic: item.setInfo('video',{'Genre':'bold'})
			item.setProperty('message',post.message)
			item.setProperty('post',post.postId)
			self.getControl(120).addItem(item)
			
		self.setNext(next)
			
	def postSelected(self):
		item = self.getControl(120).getSelectedItem()
		if item.getProperty('page'):
			self.fillRepliesList(item.getProperty('page'))
			return
		
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
		BaseWindow.onAction(self,action)
	
	def doMenu(self):
		dialog = xbmcgui.Dialog()
		idx = dialog.select('Options',['Quote','Delete Post'])
		if idx == 0: self.openPostDialog(quote=True)
		elif idx == 1: self.deletePost()
		
	def deletePost(self):
		item = self.getControl(120).getSelectedItem()
		post = item.getProperty('post')
		if not post: return
		prog = xbmcgui.DialogProgress()
		prog.create('Deleting','Deleting Post. Please wait...')
		prog.update(0)
		try:
			FB.deletePost(post)
		except:
			prog.close()
			raise
		prog.close()
		self.fillRepliesList(self.page)
		
	def openPostDialog(self,quote=False):
		if quote:
			item = self.getControl(120).getSelectedItem()
			quot = item.getProperty('message')
			user = item.getLabel() + ';' + item.getProperty('post')
		else:
			item = self.getControl(120).getListItem(0)
			quot = ''
			user=''
		if not item.getProperty('post'): item = self.getControl(120).getListItem(1)
		post = item.getProperty('post')
		w = PostDialog("script-forumbrowser-post.xml" , os.getcwd(), "Default",post=post,quote=quot,quote_user=user,parent=self)
		w.doModal()
		posted = w.posted
		del w
		if posted:
			self.fillRepliesList('-1')
	
	def prevPage(self,page):
		self.fillRepliesList(page)
		
	def nextPage(self,page):
		self.fillRepliesList(page)
		
class ThreadsWindow(BaseWindow):
	def __init__( self, *args, **kwargs ):
		self.fid = kwargs.get('fid','')
		self.topic = kwargs.get('topic','')
		self.me = 'ruuk'
		BaseWindow.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.getControl(104).setLabel(self.topic)
		self.fillThreadList()
		self.setFocus(self.getControl(120))
		
	def fillThreadList(self,page=''):
		self.getControl(120).reset()
		threads,prev,next,page_disp = FB.getThreads(self.fid,page)
		self.getControl(105).setLabel(page_disp)
		
		self.setPrev(prev)
		
		for tid, title, starter, last in threads:
			item = xbmcgui.ListItem(label=starter,label2=convertHTMLCodes(re.sub('<.*?>','',title)))
			if '<strong>' in title: item.setInfo('video',{"Genre":'bold'})
			if starter == self.me: item.setInfo('video',{"Director":'me'})
			if last == self.me: item.setInfo('video',{"Studio":'me'})
			item.setProperty("id",tid)
			item.setProperty("last",'Last Post By: ' + last)
			self.getControl(120).addItem(item)
			
		self.setNext(next)
			
	def openRepliesWindow(self):
		item = self.getControl(120).getSelectedItem()
		if item.getProperty('page'):
			self.fillThreadList(item.getProperty('page'))
			return
		tid = item.getProperty('id')
		topic = item.getLabel2()
		w = RepliesWindow("script-forumbrowser-replies.xml" , os.getcwd(), "Default",tid=tid,topic=topic,parent=self)
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
		BaseWindow.onAction(self,action)
		
	def prevPage(self,page):
		self.fillThreadList(page)
		
	def nextPage(self,page):
		self.fillThreadList(page)
		
class ForumsWindow(xbmcgui.WindowXMLDialog):
	def __init__( self, *args, **kwargs ):
		xbmcgui.WindowXML.__init__( self, *args, **kwargs )
	
	def onInit(self):
		self.fillForumList()
		self.setFocus(self.getControl(120))
		
	def fillForumList(self):
		forums = FB.getForums()
		#print forums
		for fid, title, desc in forums:
			if not desc:
				desc = 'Sub-Forum'
				title = ' -' + title
			item = xbmcgui.ListItem(label=re.sub('<.*?>','',title))
			if '<strong>' in title: item.setInfo('video',{"Genre":'bold'})
			item.setProperty("description",convertHTMLCodes(re.sub('<.*?>','',desc)))
			item.setProperty("id",fid)
			self.getControl(120).addItem(item)
			
	def openThreadsWindow(self):
		item = self.getControl(120).getSelectedItem()
		fid = item.getProperty('id')
		topic = item.getLabel()
		w = ThreadsWindow("script-forumbrowser-threads.xml" , os.getcwd(), "Default",fid=fid,topic=topic,parent=self)
		w.doModal()
		del w
		
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
				pass
			elif self.getFocusId() == 202:
				pass
			else:
				self.openThreadsWindow()
		elif action == ACTION_PARENT_DIR:
			action = ACTION_PREVIOUS_MENU
		elif action == ACTION_MOUSE_LEFT_CLICK:
			if self.getFocusId() == 200:
				self.openSettings()
			elif self.getFocusId() == 201:
				pass
			elif self.getFocusId() == 202:
				pass
			elif self.getFocusId() == 120:
				self.openThreadsWindow()
		xbmcgui.WindowXMLDialog.onAction(self,action)
		
	def openSettings(self):
		__settings__.openSettings()
		
def calculatePage(low,high,total):
	low = int(low.replace(',',''))
	high = int(high.replace(',',''))
	total = int(total.replace(',',''))
	if high == total: return -1
	return str(int(round(float(high)/((high-low)+1))))
	
def convertHTMLCodes(html):
	return html	.replace("&lt;", "<")\
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
		
FB = ForumBrowser('http://forum.xbmc.org/')
#FB = ForumBrowser('http://forums.boxee.tv/')

w = ForumsWindow("script-forumbrowser-forums.xml" , os.getcwd(), "Default")
w.doModal()
del w
sys.modules.clear()
