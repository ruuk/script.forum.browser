import forumbrowser, json, urllib2, urllib, sys, os,re, time, codecs

DEBUG = sys.modules["__main__"].DEBUG
LOG = sys.modules["__main__"].LOG
ERROR = sys.modules["__main__"].ERROR
__addon__ = sys.modules["__main__"].__addon__

def testForum(forum):
	url3 = None
	url2 = None
	if forum.startswith('http://'):
		url = forum
		if not forum.endswith('/'): forum += '/'
		if not forum.endswith('.php/'): url2 = forum + 'forumrunner/request.php'
	else:
		if forum.startswith('/'): forum = forum[1:]
		if forum.endswith('/'): forum = forum[:-1]
		url = 'http://%s/forumrunner/request.php' % forum
		url2 = None
		if '/' in forum: url3 = 'http://%s/forumrunner/request.php' % forum.split('/',1)[0]
	
	for u in (url,url2,url3):
		if not u: continue
		try:
			client = ForumrunnerClient(u)
			result = client.version()
			if result.get('version'): return u
		except:
			continue
	return None

class FRCFail:
	def __init__(self,result={}):
		self.result = result
		self.message = result.get('message','') or ''
		
	def __nonzero__(self):
		return False
	
class ForumrunnerClient():
	def __init__(self,url):
		self.url = url
		if not self.url.endswith('/'): self.url += '/'
		self.cache = {}
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor)
		#urllib2.install_opener(self.opener)
		
	def __getattr__(self, method):
		if method.startswith('_'): return object.__getattr__(self,method)
		if method in self.cache:
			return self.cache[method]
				
		def handler(**args):
			try:
				return self._callMethod(method,**args)
			except:
				LOG('Failed: ForumrunnerClient.%s()' % method)
				raise
	
		handler.method = method
		
		self.cache[method] = handler
		return handler
	
	def _callMethod(self,method,**args):
		url = self.url + 'request.php?cmd=' + method
		#url = '&'.join((url,urllib.urlencode(args)))
		encArgs = urllib.urlencode(args)
		obj = self.opener.open(url,encArgs)
		if DEBUG: LOG('Response Headers: ' + str(obj.info()))
		encoding = obj.info().get('content-type').split('charset=')[-1]
		if '/' in encoding: encoding = 'utf8'
		data = unicode(obj.read(),encoding)
		pyobj = None
		try:
			pyobj = json.loads(data)
		except:
			pass
		if not pyobj: pyobj = json.loads(re.sub(r'\\u[\d\w]+','?',data),strict=False)
		if pyobj.get('success'):
			return pyobj.get('data')
		else:
			return FRCFail(pyobj)

################################################################################
# ForumPost
################################################################################
class ForumPost(forumbrowser.ForumPost):
	def __init__(self,pdict):
		forumbrowser.ForumPost.__init__(self, pdict)
		self.MC = sys.modules["__main__"].MC
		self.FB = sys.modules["__main__"].FB
		
	def setVals(self,pdict):
		self.postId = pdict.get('post_id',pdict.get('id',''))
		self.tid = pdict.get('thread_id','')
		self.userName = pdict.get('username','')
		self.userId = pdict.get('userid','')
		self.title = pdict.get('title','')
		self.message = pdict.get('edittext',pdict.get('text',pdict.get('message','')))
		self.date = pdict.get('post_timestamp',pdict.get('pm_timestamp',''))
		self.images = pdict.get('images',[])
		self.thumbs = pdict.get('image_thumbs',[])
		self.quotable = pdict.get('quotable','')
		self.avatar = pdict.get('avatarurl','')
		self.postCount = pdict.get('numposts',0)
		self.joinDate = pdict.get('joindate',0)
		self.status = pdict.get('usertitle','')
		#print self.images
		#print self.thumbs
	
	def imageURLs(self):
		return self.MC.imageFilter.findall(self.getMessage())
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.message)
	
	def linkURLs(self):
		return self.MC.linkFilter.finditer(self.getMessage())
	
	def link2URLs(self):
		if not self.MC.linkFilter2: return []
		return self.MC.linkFilter2.finditer(self.getMessage())
	
	def messageAsQuote(self):
		qr = self.FB.getQuoteReplace()
		return qr.replace('!USER!',self.userName).replace('!POSTID!',self.postId).replace('!USERID!',self.userId).replace('!DATE!',str(int(time.time()))).replace('!QUOTE!',self.quotable)
	
	def messageToDisplay(self,message):
		return self.MC.messageToDisplay(message)
	
	
class ForumrunnerForumBrowser(forumbrowser.ForumBrowser):
	
	PageData = forumbrowser.PageData
	
	def __init__(self,forum,always_login=False):
		forumbrowser.ForumBrowser.__init__(self, forum, always_login)
		self.forum = forum[3:]
		self.prefix = 'FR.'
		self.lang = sys.modules["__main__"].__language__
		self.online = {}
		self.lastOnlineCheck = 0
		self.loadForumFile()
		self.setupClient()
		self.setFilters()
	
	def setupClient(self):
		self.needsLogin = True
		if not self._url:
			self._url = 'http://%s/forumrunner/request.php' % self.forum
		url = self._url
		if __addon__.getSetting('enable_ssl'):
			LOG('Enabling SSL')
			url = url.replace('http://','https://')
		self.client = ForumrunnerClient(url)
		try:
			result = self.client.version()
			self.SSL = True
		except urllib2.URLError:
			LOG('Falling back to normal http')
			self.client = ForumrunnerClient(self._url)
			result = self.client.version()
			self.SSL = False
			
		self.platform = result.get('platform')
		self.charset = result.get('charset')
		
		LOG('Forum Type: ' + self.platform)
		LOG('Plugin Version: ' + result.get('version'))
		
	def setFilters(self):
		self.filters['quote'] = self.getQuoteFormat()
	
	def getForumType(self):
		text = re.sub('\d','',self.platform)
		if text == 'vb': return 'vb'
		elif text == 'phpbb': return 'pb' #don't know if this is right
		elif text == 'xen': return 'xf'
		elif text == 'mybb': return 'mb'
		elif text == 'ipb': return 'ip' #don't know if this is right
		return text
	
	def loadForumFile(self):
		forum = self.getForumID()
		fname = os.path.join(sys.modules["__main__"].FORUMS_PATH,forum)
		if not os.path.exists(fname):
			fname = os.path.join(sys.modules["__main__"].FORUMS_STATIC_PATH,forum)
			if not os.path.exists(fname): return False
		self.loadForumData(fname)
		self._url = self.urls.get('forumrunner_server','')
		self.formats['quote'] = ''
			
	def createForumDict(self,data,sub=False):
		data['forumid'] = data.get('id')
		data['title'] = str(data.get('name'))
		data['description'] = str(data.get('desc'))
		data['subforum'] = sub
		return data
	
	def isLoggedIn(self): return self._loggedIn
	
	def login(self):
		LOG('LOGGING IN')
		result = self.client.login(username=self.user,password=self.password)
		if not result.get('authenticated'):
			error = str(result.get('requires_authentication',''))
			LOG('LOGIN FAILED: ' + error)
			self.loginError = error
			self._loggedIn = False
		else:
			if DEBUG:
				LOG('LOGGED IN: ' + str(result.get('requires_authentication','')))
			else:
				LOG ('LOGGED IN')
			self.loginError = ''
			self._loggedIn = True
			return True
		return False
		
	def checkLogin(self,callback=None,callback_percent=5):
		if not self.user or not self.password: return False
		if not callback: callback = self.fakeCallback
		if self.needsLogin or not self.isLoggedIn():
			self.needsLogin = False
			if not callback(callback_percent,self.lang(30100)): return False
			if not self.login():
				return False
		return True
	
	def getForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		logo = None
		while True:
			if not callback(20,self.lang(30102)): break
			try:
				data = self.client.get_forum()
				base = data.get('forums')
				flist = []
				for forum in base:
					sub = False
					data = self.client.get_forum(forumid=forum.get('id'))
					f = data.get('forums')
					t = data.get('threads')
					if t: flist.append((forum,False))
					for ff in f:
						flist.append((ff,sub))
			except:
				em = ERROR('ERROR GETTING FORUMS')
				callback(-1,'%s' % em)
				if donecallback: donecallback(None,None,None)
				return (None,None,None)
			if not callback(40,self.lang(30103)): break
			forums = []
			for forum,sub in flist:
				forums.append(self.createForumDict(forum,sub))
			if not callback(80,self.lang(30231)): break
			logo = self.urls.get('logo') or 'http://%s/favicon.ico' % self.forum
			try:
				pm_counts = self.getPMCounts(80)
			except:
				ERROR('Failed to get PM Counts')
				pm_counts = None
			callback(100,self.lang(30052))
			if donecallback: donecallback(forums,logo,pm_counts)
			return forums, logo, pm_counts
			
		if donecallback: donecallback(None,logo,None)
		return None,logo,None

	def createThreadDict(self,data,sticky=False):
		data['threadid'] = data.get('thread_id','')
		data['starter'] = data.get('post_username',self.user)
		data['title'] = data.get('thread_title','')
		data['short_content'] = re.sub('[\t\r\n]','',data.get('thread_preview',''))
		data['forumid'] = data.get('forum_id','')
		data['sticky'] = sticky
		return data
	
	def _getThreads(self,forumid,page,callback,donecallback):
		if not callback: callback = self.fakeCallback
		while True:
			threads = []
			if not callback(20,self.lang(30102)): break
			data = self.client.get_forum(forumid=forumid,page=page,perpage=20)
			if not callback(40,self.lang(30103)): break
			for s in data.get('threads_sticky'): threads.append(self.createThreadDict(s,True))
			if not callback(60,self.lang(30102)): break
			for t in data.get('threads'): threads.append(self.createThreadDict(t))
			if not callback(80,self.lang(30103)): break
			total = int(data.get('total_threads',1))
			current = len(data.get('threads',[]))
			pd = self.PageData(page=page,total_items=total,current_total=current)
			return threads, pd
			
		if donecallback:
			donecallback(None,None)
		return (None,None)
	
	def hasSubscriptions(self): return True
	
	def getSubscriptions(self,page='',callback=None,donecallback=None):
		if not self.checkLogin(callback=callback): return (None,None)
		return self.getThreads(None, page, callback, donecallback)
	
	def _getSubscriptions(self,page,callback,donecallback):
		callback(20,self.lang(30102))
		sub = self.client.get_subscriptions(page=page,perpage=20)
		total = int(sub.get('total_threads',1))
		current = len(sub.get('threads',[]))
		pd = self.PageData(page=page,total_items=total,current_total=current)
		normal = sub.get('threads',[])
		if not callback(70,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		for n in normal: self.createThreadDict(n)
		return normal, pd
	
	def getThreads(self,forumid,page=1,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		try:
			if forumid:
				threads,pd = self._getThreads(forumid,page or 1,callback,donecallback)
			else:
				threads,pd = self._getSubscriptions(page or 1,callback,donecallback)
		except:
			em = ERROR('ERROR GETTING THREADS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		
		callback(100,self.lang(30052))
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getOnlineUsers(self):
		#lets not hammer the server. Only get online user list every five minutes
		now = time.time()
		if now - self.lastOnlineCheck > 300:
			self.lastOnlineCheck = now
			try:
				oDict = {}
				online = self.client.online()
				for o in online.get('users',online.get('online_users',[])): #online_users is the documented key but not found in practice
					oDict[o.get('username','?')] = o.get('userid','?')
				self.online = oDict
				#print self.online
			except:
				ERROR('Error getting online users')
		return self.online
	
	def getReplies(self,threadid,forumid,page=1,lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		while True:
			try: page = int(page)
			except: page = 1
			
			if not callback(20,self.lang(30102)): break
			oDict = self.getOnlineUsers()
			if not callback(40,self.lang(30102)): break
			try:
				sreplies = []
				if pid:
					#test = self.server.get_thread_by_post(pid,20)
					#index = test.get('position')
					#start = int((index - 1) / 20) * 20
					#thread = self.server.get_thread(threadid,start,start + 19)
					pass
				else:
					thread = self.client.get_thread(threadid=threadid,page=page,perpage=10)
				posts = thread.get('posts')
				if not posts:
					callback(-1,'NO POSTS')
					if donecallback: donecallback(None,None)
					return (None,None)
				total = int(thread.get('total_posts',1))
				current = len(thread.get('posts',[]))
				pd = self.PageData(page,current_total=current,total_items=total,per_page=10,is_replies=True)
				if not callback(60,self.lang(30103)): break
				ct = pd.current + 1
				for p in posts:
					fp = ForumPost(p)
					fp.postNumber = ct
					fp.online = fp.userName in oDict
					sreplies.append(fp)
					ct+=1
				sreplies.reverse()
			except:
				em = ERROR('ERROR GETTING POSTS')
				callback(-1,'%s' % em)
				if donecallback: donecallback(None,None)
				return (None,None)
			
			if not callback(80,self.lang(30103)): break
			
			pd.tid = threadid
			callback(100,self.lang(30052))
			
			if donecallback: donecallback(sreplies, pd)
			return sreplies, pd
			
		if donecallback: donecallback(None,None)
		return (None,None)
	
	def getPMCounts(self,callback_percent=5):
		if not self.hasPM(): return None
		if not self.checkLogin(callback_percent=callback_percent): return None
		#folders = self.client.get_pm_folders()
		#print folders
		#return None
		pms = self.client.get_pms(page=1,perpage=50)
		if not pms:
			ERROR('Failed to get PM counts')
			return None
		return {'unread':int(pms.get('unread_pms',0)),'total':int(pms.get('total_pms',0)),'boxid':'0'}
	
	def hasPM(self): return True
		
	def getPrivateMessages(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		
		while True:
			oDict = self.getOnlineUsers()
			if not callback(30,self.lang(30102)): break
			try:
				messages = self.client.get_pms(page=1,perpage=50)
			except:
				em = ERROR('ERROR GETTING PRIVATE MESSAGES')
				callback(-1,'%s' % em)
				break
			pms = []
			if not callback(80,self.lang(30103)): break
			for p in messages.get('pms',[]):
				fp = ForumPost(p)
				fp.online = fp.userName in oDict
				pms.append(fp)
			
			callback(100,self.lang(30052))
			if donecallback: donecallback(pms,None)
			return pms, None
		
		if donecallback: donecallback(None,None)
		return (None,None)

	def post(self,post,callback=None):
		if post.isEdit:
			return self.editPost(post)
		LOG('Posting reply')
		if not callback: callback = self.fakeCallback
		if not self.checkLogin(callback=callback): return False
		callback(40,self.lang(30106))
		result = self.client.post_reply(threadid=post.tid,message=post.message,title=post.title)
		callback(100,self.lang(30052))
		if not result:
			LOG('Failed To Post: ' + result.message)
			post.error = result.message
		return bool(result)
	
	def getPostForEdit(self,pid):
		result = self.client.get_post(postid=pid)
		if not result:
			LOG('Could not get raw post for editing')
			return None
		pm = forumbrowser.PostMessage(pid,isEdit=True)
		pm.setMessage(title=result.get('title',''), message=result.get('edittext',''))
		return pm
	
	def editPost(self,pm):
		LOG('Saving edited post')
		result = self.client.post_edit(postid=pm.pid,message=pm.message,title=pm.title)
		if not result:
			LOG('Failed to edit post: ' + result.message)
			pm.error = result.message
		return bool(result)
	
	def canSubscribeThread(self,tid): return True
	
	def subscribeThread(self,tid):
		result = self.client.subscribe_thread(threadid=str(tid))
		if not result:
			LOG('Failed to subscribe to thread: ' + result.message)
			return result.message
		return True
		
	def canEditPost(self,user):
		if user == self.user: return True
		return False
	