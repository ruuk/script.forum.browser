import sys, os
import forumbrowser, scraperbrowser, texttransform
from forumparsers import GeneralForumParser, GeneralThreadParser, GeneralPostParser
from forumbrowser import FBData

LOG = sys.modules["__main__"].LOG
ERROR = sys.modules["__main__"].ERROR
FORUMS_STATIC_PATH = sys.modules["__main__"].FORUMS_STATIC_PATH
__language__ = sys.modules["__main__"].__language__

	
class GenericParserForumBrowser(scraperbrowser.ScraperForumBrowser):
	browserType = 'GenericParserForumBrowser'
	
	def __init__(self,forum,always_login=False,ftype=None,url=''):
		forumbrowser.ForumBrowser.__init__(self, forum, always_login,message_converter=texttransform.BBMessageConverter)
		self.forum = 'general'
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
		self.urls = {}
		self.filters = {}
		self.forms = {}
		self.formats = {}
		
		self.urls['base'] = url
		self.filters.update({	'quote':'\[QUOTE\](?P<quote>.*)\[/QUOTE\](?is)',
								'code':'\[CODE\](?P<code>.+?)\[/CODE\](?is)',
								'php':'\[PHP\](?P<php>.+?)\[/PHP\](?is)',
								'html':'\[HTML\](?P<html>.+?)\[/HTML\](?is)',
								'image':'\[img\](?P<url>[^\[]+)\[/img\](?is)',
								'link':'\[url="?(?P<url>[^\]]+?)"?\](?P<text>.*?)\[/url\](?is)',
								'link2':'\[url\](?P<text>(?P<url>.+?))\[/url\](?is)',
								'post_link':'(?:showpost.php|showthread.php)\?[^<>"]*?tid=(?P<threadid>\d+)[^<>"]*?pid=(?P<postid>\d+)',
								'thread_link':'showthread.php\?[^<>"]*?tid=(?P<threadid>\d+)',
								'color_start':'\[color=?#?(?P<color>\w+)\]'
								})
		self.initialize()
		
	def getForumID(self):
		return 'general'
	
	def getDisplayName(self):
		name = self._url.split('://')[-1].split('/')[0]
		if name.startswith('www.'): name = name[4:]
		return name
	
	def getForumType(self):
		return self.forumType
	
	def isLoggedIn(self): return False
	
	def getQuoteStartFormat(self):
		forumType = self.getForumType()
		if forumType:
			return self.quoteStartFormats.get(forumType,'(?i)\[QUOTE[^\]]*?\]')
		else:
			return scraperbrowser.ScraperForumBrowser.getQuoteStartFormat(self)
	
	def doLoadForumData(self):
		path = os.path.join(FORUMS_STATIC_PATH,'general',self.forumParser.forumType)
		self.loadForumData(path)
			
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
		LOG('Detected Forum Type: ' + self.forumParser.forumType)
		self.doLoadForumData()
		for f in forums:
			f['subscribed'] = subs
			f['is_forum'] = True
		
		#logo = self.getLogo(html)
		logo = 'http://%s/favicon.ico' % self.urls.get('base','').split('://')[-1].split('/')[0]
		#pm_counts = self.getPMCounts(html)
		pm_counts = None
		callback(100,__language__(30052))
		
		return self.finish(FBData(forums,extra={'logo':logo,'pm_counts':pm_counts}),donecallback)
	
	def getThreads(self,forumid,page='',callback=None,donecallback=None,url=None,subs=False):
		if not callback: callback = self.fakeCallback
		url = None
		if self.forumParser.isGeneric:
			for f in self.forumParser.forums:
				if forumid == f.get('forumid'):
					url = f.get('url')
					if not url: break
					if not url.startswith('http'):
						if url.startswith('/'): url = url[1:]
						url = self._url + url
					break
					
		if not url: url = self.getPageUrl(page,'threads',fid=forumid)
		LOG('Forum URL: ' + url)
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
		pd = self.getPageInfo(html,page,page_type='threads')
		return self.finish(FBData(threads,pd,extra=extra),donecallback)
	
	def getReplies(self,threadid,forumid,page='',lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		url = None
		if self.threadParser.isGeneric:
			for f in self.threadParser.threads:
				if threadid == f.get('threadid'):
					url = f.get('url')
					if not url: break
					if not url.startswith('http'):
						if url.startswith('/'): url = url[1:]
						url = self._url + url
					break
		if not url: url = self.getPageUrl(page,'replies',tid=threadid,fid=forumid,lastid=lastid,pid=pid)
		LOG('Thread URL: ' + url)
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
				#print post.message.encode('ascii','replace')
				sreplies.append(post)
			except:
				ERROR('ERROR CREATING POST - Using blank post')
				post = self.getForumPost()
				sreplies.append(post)
		pd = self.getPageInfo(html,page,page_type='replies')
		if pd: pd.setThreadData('',threadid)
		callback(100,__language__(30052))
		
		return self.finish(FBData(sreplies,pd),donecallback)
	
	def subscribeThread(self,tid): return False
		
	def unSubscribeThread(self, tid): return False
		
	def subscribeForum(self, fid): return False
		
	def unSubscribeForum(self, fid): return False
		
	def canSubscribeThread(self, tid): return False
	
	def canSubscribeForum(self, fid): return False
	