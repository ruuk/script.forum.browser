import sys
import forumbrowser, scraperbrowser
from forumparsers import GeneralForumParser, GeneralThreadParser, GeneralPostParser
from forumbrowser import FBData

ERROR = sys.modules["__main__"].ERROR
__language__ = sys.modules["__main__"].__language__

	
class GenericParserForumBrowser(scraperbrowser.ScraperForumBrowser):
	browserType = 'GenericParserForumBrowser'
	
	def __init__(self,forum,always_login=False,ftype=None,url=''):
		forumbrowser.ForumBrowser.__init__(self, forum, always_login)
		self.urls['base'] = url
		self.forum = forum
		self._url = url
		self.browser = None
		self.mechanize = None
		self.needsLogin = True
		self.alwaysLogin = always_login
		self.lastHTML = ''
		#self.reloadForumData(forum)
		self.forumType = 'uk'
		self.forumParser = GeneralForumParser()
		self.threadParser = GeneralThreadParser()
		self.postParser = GeneralPostParser()
		self.initialize()
		
	def getForumType(self):
		return self.forumType
	
	def getQuoteStartFormat(self):
		forumType = self.getForumType()
		if forumType:
			return self.quoteStartFormats.get(forumType,'(?i)\[QUOTE[^\]]*?\]')
		else:
			return scraperbrowser.ScraperForumBrowser.getQuoteStartFormat(self)
	
	def setURLS(self):
		if self.forumParser.forumType == 'vb':
			self.urls['threads'] = 'forumdisplay.php?f=!FORUMID!'
			self.urls['replies'] = 'showthread.php?t=!THREADID!'
		elif self.forumParser.forumType == 'fb':
			self.urls['threads'] = 'viewforum.php?id=!FORUMID!'
			self.urls['replies'] = 'viewtopic.php?id=!THREADID!'
		elif self.forumParser.forumType == 'mb':
			self.urls['threads'] = 'forum-!FORUMID!.html'
			self.urls['replies'] = 'thread-!THREADID!.html'
			
	def getForums(self,callback=None,donecallback=None,url='',subs=False):
		if not callback: callback = self.fakeCallback
		try:
			self.checkLogin()
			html = self.readURL(url or self.urls.get('base',''),callback=callback,force_browser=True)
		except:
			em = ERROR('ERROR GETTING FORUMS')
			callback(-1,'%s' % em)
			return self.finish(FBData(error=em or 'ERROR'),donecallback)
		
		if not html or not callback(80,__language__(30103)):
			return self.finish(FBData(error=html and 'CANCEL' or 'EMPTY HTML'),donecallback)
		
		forums = self.forumParser.getForums(html)
		self.setURLS()
		for f in forums:
			f['subscribed'] = subs
			f['is_forum'] = True
		
		#logo = self.getLogo(html)
		logo = ''
		#pm_counts = self.getPMCounts(html)
		pm_counts = None
		callback(100,__language__(30052))
		
		return self.finish(FBData(forums,extra={'logo':logo,'pm_counts':pm_counts}),donecallback)
	
	def getThreads(self,forumid,page='',callback=None,donecallback=None,url=None,subs=False):
		if not callback: callback = self.fakeCallback
		url = self.getPageUrl(page,'threads',fid=forumid)
		print url
		html = self.readURL(url,callback=callback,force_browser=True)
		if not html or not callback(80,__language__(30103)):
			return self.finish(FBData(error=html and 'CANCEL' or 'EMPTY HTML'),donecallback)
		threads = self.threadParser.getThreads(html)
		#forums = self.forumParser.getList(html,in_threads=True)
		extra = None
		#if forums: extra = {'forums':forums}
		if subs:
			for t in threads: t['subscribed'] = True
		callback(100,__language__(30052))
		#pd = self.getPageInfo(html,page,page_type='threads')
		pd = None
		return self.finish(FBData(threads,pd,extra=extra),donecallback)
	
	def getReplies(self,threadid,forumid,page='',lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		url = self.getPageUrl(page,'replies',tid=threadid,fid=forumid,lastid=lastid,pid=pid)
		print url
		html = self.readURL(url,callback=callback,force_browser=True)
		if not html or not callback(80,__language__(30103)):
			return self.finish(FBData(error=html and 'CANCEL' or 'EMPTY HTML'),donecallback)
		replies = self.postParser.getPosts(html)
		#topic = re.search(self.filters.get('thread_topic','%#@+%#@'),html)
		#if not threadid:
		#	threadid = re.search(self.filters.get('thread_id','%#@+%#@'),html)
		#	threadid = threadid and threadid.group(1) or ''
		#topic = topic and topic.group(1) or ''
		sreplies = []
		for r in replies:
			try:
				post = self.getForumPost(r)
				sreplies.append(post)
			except:
				post = self.getForumPost()
				sreplies.append(post)
		#pd = self.getPageInfo(html,page,page_type='replies')
		#pd.setThreadData(topic,threadid)
		pd = None
		callback(100,__language__(30052))
		
		return self.finish(FBData(sreplies,pd),donecallback)
	
	def subscribeThread(self,tid): return False
		
	def unSubscribeThread(self, tid): return False
		
	def subscribeForum(self, fid): return False
		
	def unSubscribeForum(self, fid): return False
		
	def canSubscribeThread(self, tid): return False
	
	def canSubscribeForum(self, fid): return False
	