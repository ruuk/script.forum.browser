import xmlrpclib, sys

######################################################################################
# Forum Browser API for TapaTalk
######################################################################################
class TapatalkForumBrowser:
	def __init__(self,forum,always_login=False):
		self.forum = forum
		self._url = ''
		self.server = None
		self.needsLogin = True
		self.alwaysLogin = always_login
		self.__lang = sys.modules["__main__"].self.__language__
		self.LOG = sys.modules["__main__"].LOG
		self.reloadForumData(forum)
		
	def reloadForumData(self,forum):
		self.urls = {}
		self.filters = {}
		self.theme = {}
		self.forms = {}
		self.formats = {}
		self.smilies = {}
		
		if not self.loadForumData(forum):
			self.forum = 'forum.xbmc.org'
			self.loadForumData(self.forum)
		
	def loadForumData(self,forum):
		self.needsLogin = True
		self._url = 'http://%s/mobiquo/mobiquo.php' % forum
		self.forum = forum
		self.server = xmlrpclib.ServerProxy(self._url)
		return True
			
		
	def setLogin(self,user,password,always=False):
		self.user = user
		self.password = password
		self.alwaysLogin = always
			
	def login(self):
		self.LOG('LOGGING IN')
		return False
		
	def checkLogin(self,callback=None):
		if not callback: callback = self.fakeCallback
		if self.needsLogin:
			self.needsLogin = False
			if not callback(5,self.lang(30100)): return False
			if not self.login():
				return False
		return True
		
	def getPMCounts(self,html=''):
		pm_counts = None
		return None
		
	def createFourmDict(self,data,sub=False):
		data['forumid'] = data.get('forum_id')
		data['title'] = str(data.get('forum_name'))
		data['description'] = str(data.get('description'))
		data['subforum'] = sub
		return data
		
	def getForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		try:
			flist = self.server.get_forum()
		except:
			em = ERROR('ERROR GETTING FORUMS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		forums = []
		for general in flist:
			forums.append(self.createForumDict(general))
			for forum in general.get('child',[]):
				forums.append(self.createForumDict(forum))
				for sub in forum.get('child',[]):
					forums.append(self.createForumDict(sub,True))
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		logo = ''
		pm_counts = {}
		callback(100,self.lang(30052))
		if donecallback: donecallback(forums,logo,pm_counts)
		else: return forums, logo, pm_counts
		
	def getThreads(self,forumid,page='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		#get threads
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		callback(100,self.lang(30052))
		pd = None #pd = self.getPageData(html,page,page_type='threads')
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getReplies(self,threadid,forumid,page='',lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		#get replies
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		pd = None #pd = self.getPageData(html,page,page_type='replies')
		#pd.setThreadData(topic,threadid)
		callback(100,self.lang(30052))
		
		if donecallback: donecallback(sreplies, pd)
		else: return sreplies, pd
		
	def hasPM(self):
		return False
	
	def getPrivateMessages(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		pms = None
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		callback(100,self.lang(30052))
		
		if donecallback: donecallback(pms,None)
		else: return pms, None
	
	def hasSubscriptions(self):
		return False
	
	def getSubscriptions(self,page='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		#get threads
		if not html or not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		callback(100,self.lang(30052))
		pd = None #pd = self.getPageData(html,page,page_type='threads')
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getPageData(self,html,page,page_type=''):
		return None
		
	def getPageUrl(self,page,sub,pid='',tid='',fid='',lastid=''):
		return ''
		
	def getURL(self,name):
		return self._url + self.urls.get(name,'')
		
	def fakeCallback(self,pct,message=''): return True
	
	def post(self,post,callback=None):
		if not callback: callback = self.fakeCallback
		if not self.checkLogin(callback=callback): return False
		callback(40,self.lang(30105))
		#wait = int(self.forms.get('post_submit_wait',0))
		#if wait: callback(60,self.lang(30107) % wait)
		#time.sleep(wait) #or this will fail on some forums. I went round and round to find this out.
		callback(80,self.lang(30106))
		#post here
		callback(100,self.lang(30052))
		return True
		
	def doPrivateMessage(self,to,title,message,callback=None):
		pass
			
	def deletePrivateMessageViaIndex(self,pmidx,callback=None):
		pass
		
	def deletePost(self,post):
		if not self.checkLogin(): return False
		#delete here
		return True
			
	def canDelete(self,user):
		return False
	