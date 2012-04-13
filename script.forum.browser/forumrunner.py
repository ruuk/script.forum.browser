import forumbrowser, json, urllib2, urllib, sys, os,re, time

DEBUG = sys.modules["__main__"].DEBUG
LOG = sys.modules["__main__"].LOG
ERROR = sys.modules["__main__"].ERROR
__addon__ = sys.modules["__main__"].__addon__

def testForum(forum):
	url3 = None
	if forum.startswith('http://'):
		url = forum
		if not forum.endswith('/'): forum += '/'
		url2 = forum + 'forumrunner/request.php'
	else:
		if forum.startswith('/'): forum = forum[1:]
		if forum.endswith('/'): forum = forum[:-1]
		url = 'http://%s/forumrunner/request.php' % forum
		url2 = None
		if '/' in forum: url3 = 'http://%s/forumrunner/request.php' % forum.split('/',1)[0]
	
	try:
		client = ForumrunnerClient(url)
		result = client.version()
		if result.get('version'): return url
	except:
		return None
	if not url2: return None
	try:
		client = ForumrunnerClient(url2)
		result = client.version()
		if result.get('version'): return url2
	except:
		return None
	return None

class ForumrunnerClient():
	def __init__(self,url):
		self.url = url
		if not self.url.endswith('/'): self.url += '/'
		self.cache = {}
		
	def __getattr__(self, method):
		if method.startswith('_'): return object.__getattr__(self,method)
		if method in self.cache:
			return self.cache[method]
				
		def handler(**args):
			try:
				return self._callMethod(method,**args)
			except:
				LOG('ForumrunnerClient.%s()' % method)
				raise
	
		handler.method = method
		
		self.cache[method] = handler
		return handler
	
	def _callMethod(self,method,**args):
		url = self.url + 'request.php?cmd=' + method
		url = '&'.join((url,urllib.urlencode(args)))
		obj = urllib.urlopen(url)
		data = obj.read()
		pyobj = json.loads(data)
		if pyobj.get('success'):
			return pyobj.get('data')
		else:
			return None

################################################################################
# ForumPost
################################################################################
class ForumPost(forumbrowser.ForumPost):
	def __init__(self,pdict):
		forumbrowser.ForumPost.__init__(self, pdict)
		self.MC = sys.modules["__main__"].MC
		self.FB = sys.modules["__main__"].FB
		
	def setVals(self,pdict):
		self.postId = pdict.get('post_id','')
		self.tid = pdict.get('thread_id','')
		self.userName = pdict.get('username','')
		self.userId = pdict.get('userid','')
		self.title = pdict.get('title','')
		self.message = pdict.get('text','')
		self.date = pdict.get('post_timestamp','')
		self.images = pdict.get('images',[])
		self.thumbs = pdict.get('image_thumbs',[])
		self.quotable = pdict.get('quotable','')
		self.avatar = pdict.get('avatarurl','')
		self.postCount = pdict.get('numposts',0)
		self.joinDate = pdict.get('joindate',0)
		self.status = pdict.get('usertitle',0)
		#print self.images
		#print self.thumbs
	
	def imageURLs(self):
		return self.MC.imageFilter.findall(self.getMessage(),re.S)
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.message,re.S)
	
	def linkURLs(self):
		return self.MC.linkFilter.finditer(self.getMessage(),re.S)
	
	def link2URLs(self):
		if not self.MC.linkFilter2: return []
		return self.MC.linkFilter2.finditer(self.getMessage(),re.S)
	
	def messageAsQuote(self): return '[quote]' + self.quotable + '[/quote]'
	
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
	
	def setupClient(self):
		self.needsLogin = True
		if not self._url:
			self._url = 'http://%s/forumrunner/request.php' % self.forum
		url = self._url
		#if __addon__.getSetting('enable_ssl'):
		#	LOG('Enabling SSL')
		#	url = url.replace('http://','https://')
		self.client = ForumrunnerClient(url)
	
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
				threads,pd = self._getSubscriptions(page,callback,donecallback)
		except:
			em = ERROR('ERROR GETTING THREADS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		
		callback(100,self.lang(30052))
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getOnlineUsers(self):
		#lets not hammer the server. Only get online user list every two minutes
		now = time.time()
		if now - self.lastOnlineCheck > 120:
			self.lastOnlineCheck = now
			try:
				oDict = {}
				online = self.client.online()
				for o in online.get('users',online.get('online_users',[])): #online_users is the documented key but not found in practice
					oDict[o.get('userid','?')] = o.get('username','?')
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
				if not callback(60,self.lang(30103)): break
				for p in posts:
					fp = ForumPost(p)
					fp.online = fp.userId in oDict
					sreplies.append(fp)
				sreplies.reverse()
			except:
				em = ERROR('ERROR GETTING POSTS')
				callback(-1,'%s' % em)
				if donecallback: donecallback(None,None)
				return (None,None)
			
			if not callback(80,self.lang(30103)): break
			total = int(thread.get('total_posts',1))
			current = len(thread.get('posts',[]))
			pd = self.PageData(page,current_total=current,total_items=total,per_page=10,is_replies=True)
			pd.tid = threadid
			callback(100,self.lang(30052))
			
			if donecallback: donecallback(sreplies, pd)
			return sreplies, pd
			
		if donecallback: donecallback(None,None)
		return (None,None)
		
	