import sys, re
import forumbrowser, scraperbrowser, texttransform
from forumparsers import GeneralForumParser, GeneralThreadParser
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
		elif self.forumParser.forumType == 'pb':
			self.urls['threads'] = 'viewtopic.php?f=!FORUMID!'
		elif self.forumParser.forumType == 'mb':
			self.urls['threads'] = 'forum-!FORUMID!.html'
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
	
	def subscribeThread(self,tid): return False
		
	def unSubscribeThread(self, tid): return False
		
	def subscribeForum(self, fid): return False
		
	def unSubscribeForum(self, fid): return False
		
	def canSubscribeThread(self, tid): return False
	
	def canSubscribeForum(self, fid): return False
	