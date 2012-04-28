import sys, re
import scraperbrowser
from forumparsers import VBForumParser,VBThreadParser, VBPostParser

ERROR = sys.modules["__main__"].ERROR
__language__ = sys.modules["__main__"].__language__



class ParserForumBrowser(scraperbrowser.ScraperForumBrowser):
	parsers = 	{	'vb':	{	'forums':VBForumParser,
								'threads':VBThreadParser,
								'posts':VBPostParser,
								'pmcountsre':r'class="notifications-number">.{,10}?>(\d+)',
								'filters':{	'quote':'\[QUOTE\](?P<quote>.*)\[/QUOTE\](?is)',
											'code':'\[CODE\](?P<code>.+?)\[/CODE\](?is)',
											'php':'\[PHP\](?P<php>.+?)\[/PHP\](?is)',
											'html':'\[HTML\](?P<html>.+?)\[/HTML\](?is)',
											'image':'\[img\](?P<url>[^\[]+)\[/img\](?is)',
											'link':'\[url="?(?P<url>[^\]]+?)"?\](?P<text>.+?)\[/url\](?is)',
											'link2':'\[url\](?P<text>(?P<url>.+?))\[/url\](?is)',
											'post_link':'(?:showpost.php|showthread.php)\?[^<>"]*?tid=(?P<threadid>\d+)[^<>"]*?pid=(?P<postid>\d+)',
											'thread_link':'showthread.php\?[^<>"]*?tid=(?P<threadid>\d+)'
											}
							}
				}
	
	def __init__(self,forum,always_login=False,ftype=None):
		scraperbrowser.MC = sys.modules["__main__"].MC
		scraperbrowser.ScraperForumBrowser.__init__(self, forum, always_login)
		if not ftype: ftype = self.formats.get('forum_type')
		self.forumType = ftype or ''
		parser = self.parsers.get(ftype,{})
		fp = parser.get('forums')
		self.forumParser = fp and fp() or None
		tp = parser.get('threads')
		self.threadParser = tp and tp() or None
		pp = parser.get('posts')
		self.postParser = pp and pp() or None
		self.pmCountsRE = parser.get('pmcountsre')
		self.filters.update(parser.get('filters',{}))
		
	def getForumType(self):
		return self.forumType
	
	def getQuoteStartFormat(self):
		forumType = self.getForumType()
		if forumType:
			return self.quoteStartFormats.get(forumType,'(?i)\[QUOTE[^\]]*?\]')
		else:
			return scraperbrowser.ScraperForumBrowser.getQuoteStartFormat(self)
	
	def getPMCounts(self,html=None):
		if not self.pmCountsRE: return scraperbrowser.ScraperForumBrowser.getPMCounts(self, html)
		if not html: html = self.lastHTML
		if not html: return None
		self.checkLogin()
		m = re.search(self.pmCountsRE,html)
		if not m: return {'unread':'0'}
		return {'unread':m.group(1)}
	
	def getForums(self,callback=None,donecallback=None):
		if not self.forumParser: return scraperbrowser.ScraperForumBrowser.getForums(self, callback, donecallback)
		if not callback: callback = self.fakeCallback
		try:
			self.checkLogin()
			html = self.readURL(self.getURL('forums'),callback=callback)
		except:
			em = ERROR('ERROR GETTING FORUMS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		if not html or not callback(80,__language__(30103)):
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		forums = self.forumParser.getList(html)
		logo = self.getLogo(html)
		pm_counts = self.getPMCounts(html)
		callback(100,__language__(30052))
		if donecallback: donecallback(forums,logo,pm_counts)
		else: return forums, logo, pm_counts

	def getThreads(self,forumid,page='',callback=None,donecallback=None,url=None):
		if not self.threadParser: return scraperbrowser.ScraperForumBrowser.getThreads(self, forumid, page, callback, donecallback)
		if not callback: callback = self.fakeCallback
		if url:
			forceLogin = True
		else:
			url = self.getPageUrl(page,'threads',fid=forumid)
			forceLogin = False
		html = self.readURL(url,callback=callback,force_login=forceLogin)
		if not html or not callback(80,__language__(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		if self.filters.get('threads_start_after'): html = html.split(self.filters.get('threads_start_after'),1)[-1]
		threads = self.threadParser.getList(html)
		callback(100,__language__(30052))
		pd = self.getPageData(html,page,page_type='threads')
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getSubscriptions(self,page='',callback=None,donecallback=None):
		url = self.getPageUrl(page,'subscriptions')
		self.getThreads(None, page, callback, donecallback,url=url)
		
	def getReplies(self,threadid,forumid,page='',lastid='',pid='',callback=None,donecallback=None):
		if not self.postParser: return scraperbrowser.ScraperForumBrowser.getReplies(self, threadid, forumid, page, lastid, pid, callback, donecallback)
		if not callback: callback = self.fakeCallback
		url = self.getPageUrl(page,'replies',tid=threadid,fid=forumid,lastid=lastid,pid=pid)
		html = self.readURL(url,callback=callback)
		if not html or not callback(80,__language__(30103)):
			if donecallback:
				donecallback(None,None)
				return
			else:
				return (None,None)
		replies = self.postParser.getList(html)
		topic = re.search(self.filters.get('thread_topic','%#@+%#@'),html)
		if not threadid:
			threadid = re.search(self.filters.get('thread_id','%#@+%#@'),html)
			threadid = threadid and threadid.group(1) or ''
		topic = topic and topic.group(1) or ''
		sreplies = []
		for r in replies:
			post = scraperbrowser.ForumPost(pdict=r)
			sreplies.append(post)
		pd = self.getPageData(html,page,page_type='replies')
		pd.setThreadData(topic,threadid)
		callback(100,__language__(30052))
		
		if donecallback: donecallback(sreplies, pd)
		else: return sreplies, pd