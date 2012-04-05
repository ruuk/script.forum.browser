import xmlrpclib, httplib, sys, re, time, os
import cookielib
import urllib, urllib2
import iso8601
#import xbmc #@UnresolvedImport

def testForum(forum):
	if forum.startswith('http://'):
		url = forum
		if not forum.endswith('/'): forum += '/'
		url2 = forum + 'mobiquo/mobiquo.php'
	else:
		if forum.startswith('/'): forum = forum[1:]
		if forum.endswith('/'): forum = forum[:-1]
		url = 'http://%s/mobiquo/mobiquo.php' % forum
		url2 = None
	
	try:
		server = xmlrpclib.ServerProxy(url,transport=CookieTransport())
		server.get_config()
		return url
	except:
		return None
	if not url2: return None
	try:
		server = xmlrpclib.ServerProxy(url2,transport=CookieTransport())
		server.get_config()
		return url2
	except:
		return None
	return None

class FBTTOnlineDatabase():
	def __init__(self):
		self.url = 'http://xbmc.2ndmind.net/forumbrowser/tapatalk.php'
	
	def postData(self,**data):
		enc = urllib.urlencode(data)
		try:
			result = urllib2.urlopen(self.url,enc).read()
			return result
		except:
			raise
			#sys.modules["__main__"].ERROR('TTOnlineDatabase.postData()')
			return None
			
	def addForum(self,name,url,logo='',desc=''):
		print self.postData(do='add',name=name,url=url,desc=desc,logo=logo)
		
	def getForumList(self):
		flist = self.postData(do='list')
		if not flist: return None
		flist = flist.split('\n')
		final = []
		for f in flist:
			if f:
				name, rest = f.split('=',1)
				url,desc,logo = rest.split('\r',2)
				final.append({'name':name,'url':url,'desc':desc,'logo':logo})
		return final
	
class HTMLPageInfo:
	def __init__(self,url):
		self.url = url
		base = url.rsplit('/',1)[0]
		if base.endswith(':/'):
			self.base = url
		else:
			self.base = base
		self.base += '/'
		self._getHTML()
		self.isValid = True
		
	def _getHTML(self):
		try:
			opener = urllib2.build_opener()
			o = opener.open(urllib2.Request(self.url,None,{'User-Agent':'Wget/1.12'}))
			self.html = o.read()
			o.close()
		except:
			self.isValid = False
			print 'HTMLPageInfo: FAILED'
		
	def title(self,default=''):
		try: return re.search('<title>(.*?)</title>',self.html).group(1) or ''
		except: return default
		
	def description(self,default=''):
		try: return re.search('<meta[^>]*?name="description"[^>]*?content="([^"]*?)"',self.html).group(1)
		except: return default
		
	def images(self):
		urlList = re.findall('<img[^>]*?src="([^"]+?)"[^>]*?>',self.html) #Image tags
		urlList2 = re.findall('<meta[^>]*?property="[^"]*image"[^>]*?content="([^"]*?)"',self.html) #Meta tag images
		final = []
		for u in urlList + urlList2:
			if u in final: continue
			if u.startswith('http'):
				final.append(u)
			elif u.startswith('.'):
				pass
			elif u.startswith('/'):
				pass
			else:
				final.append(self.base + u)
		return final
		
class CookieResponse:
	def __init__(self,response,url):
		self.response = response
		self.url = url
		
	def info(self):
		return self.response.msg
	
	def geturl(self):
		return self.url
	
class CookieTransport(xmlrpclib.Transport):
	def __init__(self):
		xmlrpclib.Transport.__init__(self)
		self._loggedIn = False
		self.jar = cookielib.CookieJar()

	def loggedIn(self):
		return self._loggedIn
	
	def single_request(self, host, handler, request_body, verbose=0):
		# issue XML-RPC request

		h = self.make_connection(host)
		if verbose:
			h.set_debuglevel(1)
		try:
			self.send_request(h, handler, request_body)
			req = urllib2.Request(host,request_body)
			if self.jar._cookies:
				cookval = []
				for c in self.jar: cookval.append('%s=%s' % (c.name,c.value))
				h.putheader('Cookie','; '.join(cookval))
			self.send_host(h, host)
			self.send_user_agent(h)
			self.send_content(h, request_body)
			response = h.getresponse(buffering=True)
			
			headers = {}
			for k,v in response.getheaders():
				#Mobiquo_is_login: false
				if k.lower() == 'mobiquo_is_login':
					#print '%s=%s' % (k,v)
					self._loggedIn = (v =='true')
				headers[k] = v
			req = urllib2.Request(host,request_body,headers)
			self.jar.extract_cookies(CookieResponse(response,host), req)
			
			if response.status == 200:
				self.verbose = verbose
				return self.parse_response(response)
		except xmlrpclib.Fault:
			raise
		except Exception:
			# All unexpected errors leave connection in
			# a strange state, so we clear it.
			self.close()
			raise

		#discard any response data and raise exception
		if (response.getheader("content-length", 0)):
			response.read()
			
		raise httplib.ProtocolError(
			host + handler,
			response.status, response.reason,
			response.msg,
			)

class PMLink:
	def __init__(self,match=None):
		self.FB = sys.modules["__main__"].FB
		self.MC = sys.modules["__main__"].MC
		self.url = ''
		self.text = ''
		self.pid = ''
		self.tid = ''
		self.fid = ''
		self._isImage = False
		
		if match:
			self.url = match.group('url')
			text = match.group('text')
		self.processURL()
			
	def processURL(self):
		if not self.url: return
		self._isImage = re.search('http://.+?\.(?:jpg|png|gif|bmp)',self.url) and True or False
		if self._isImage: return
		pm = re.search(self.FB.filters.get('post_link','@`%#@>-'),self.url)
		tm = re.search(self.FB.filters.get('thread_link','@`%#@>-'),self.url)
		if pm:
			d = pm.groupdict()
			self.pid = d.get('postid','')
			self.tid = d.get('threadid','')
		elif tm:
			d = tm.groupdict()
			self.tid = d.get('threadid','')
			
	def urlShow(self):
		if self.isPost(): return 'Post ID: %s' % self.pid
		elif self.isThread(): return 'Thread ID: %s' % self.tid
		return self.url
		
	def isImage(self):
		return self._isImage
		
	def isPost(self):
		return self.pid and True or False
		
	def isThread(self):
		return self.tid and not self.pid
	
################################################################################
# ForumPost
################################################################################
class ForumPost:
	def __init__(self,pdict=None):
		self.MC = sys.modules["__main__"].MC
		self.FB = sys.modules["__main__"].FB
		self.isShort = False
		self.isPM = False
		if pdict:
			self.setVals(pdict)
		else:
			self.postId,self.date,self.userId,self.userName,self.avatar,self.status,self.title,self.message,self.signature = ('','','','ERROR','','','ERROR','','')
			self.pid = ''
		self.translated = ''
		self.avatarFinal = ''
		self.tid = ''
		self.fid = ''
		self.boxid = ''
			
	def setVals(self,pdict):
		self.setPostID(pdict.get('post_id',''))
		if self.postId:
			date = str(pdict.get('post_time',''))
			if date:
				date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
				date = time.strftime('%I:%M %p - %A %B %d, %Y',iso8601.parse_date(date).timetuple())
			self.date = date
			self.userId = pdict.get('post_author_id','')
			self.userName = str(pdict.get('post_author_name') or 'UERROR')
			self.avatar = pdict.get('icon_url','')
			self.status = pdict.get('is_online','') and '[COLOR FF00AA00]Online[/COLOR]' or 'Offline'
			self.title = str(pdict.get('post_title',''))
			self.message = str(pdict.get('post_content',''))
			self.signature = pdict.get('signature','') or '' #nothing
		else:
			self.isShort = True
			self.setPostID('PM' + pdict.get('msg_id',''))
			date = str(pdict.get('sent_date',''))
			if date:
				date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
				date = time.strftime('%I:%M %p - %A %B %d, %Y',iso8601.parse_date(date).timetuple())
			self.date = date
			self.userName = str(pdict.get('msg_from') or 'UERROR')
			self.avatar = pdict.get('icon_url','')
			self.status = pdict.get('is_online','') and '[COLOR FF00AA00]Online[/COLOR]' or 'Offline'
			self.title = str(pdict.get('msg_subject',''))
			self.message = str(pdict.get('short_content',''))
			self.boxid = pdict.get('boxid','')
			self.signature = ''
			
	def setPostID(self,pid):
		self.postId = pid
		self.pid = pid
		self.isPM = pid.startswith('PM')
	
	def getID(self):
		if self.pid.startswith('PM'): return self.pid[2:]
		return self.pid
		
	def cleanUserName(self):
		return self.MC.tagFilter.sub('',self.userName)
		
	def getShortMessage(self):
		return self.getMessage(True)
	
	def getMessage(self,skip=False):
		if self.isShort and not skip:
			m = self.FB.server.get_message(self.getID(),self.boxid)
			self.message = str(m.get('text_body',self.message))
			self.isShort = False
		return self.message + self.signature
	
	def messageAsText(self):
		return sys.modules["__main__"].messageToText(self.getMessage())
		
	def messageAsDisplay(self,short=False):
		if short:
			message = self.getShortMessage()
		else:
			message = self.getMessage()
		message = message.replace('\n','[CR]')
		if self.isPM:
			return self.MC.parseCodes(message)
		else:
			return self.MC.messageToDisplay(message)
		
	def messageAsQuote(self):
		qp = self.FB.server.get_quote_post(self.getID())
		#print qp.get('result_text')
		return str(qp.get('post_content',''))
		
	def imageURLs(self):
		return self.MC.imageFilter.findall(self.getMessage(),re.S)
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.message,re.S)
		
	def linkURLs(self):
		return self.MC.linkFilter.finditer(self.getMessage(),re.S)
		
	def links(self):
		links = []
		for m in self.linkURLs(): links.append(PMLink(m))
		return links
		
	def makeAvatarURL(self):
		base = self.FB.urls.get('avatar')
		if base and not self.avatar:
			self.avatar = base.replace('!USERID!',self.userId)
		return self.avatar
	
################################################################################
# PageData
################################################################################
class PageData:
	def __init__(self,data={},current=0,per_page=20,total_items=0):
		self.prev = current > 0
		self.current = current
		self.page = int((current + 1) / per_page) + 1
		self.perPage = per_page
		self.isReplies = data.get('total_post_num') and True or False
		self.totalitems = data.get('total_topic_num',data.get('total_post_num',total_items + 1))
		self.next = current + per_page < self.totalitems
		self.totalPages = int(self.totalitems / per_page)
		self.totalPages += (self.totalitems % per_page) and 1 or 0 
		currentTotal = len(data.get('topics',data.get('posts',[])))
		self.pageDisplay = ''
		self.nextStart = current + currentTotal
		ps = current - per_page
		if ps < 0: ps = 0
		self.prevStart = ps
		self.topic = data.get('topic_title','')
		self.tid = ''
	
	def getPageNumber(self,page=None):
		if page == None: page = self.page
		try:
			page = int(page)
		except:
			page = 0
		if page <= 0:
			if self.isReplies:
				#ret = self.totalitems - self.perPage
				#if ret < 0: ret = 0
				#return ret
				page = self.totalPages
			else:
				return 0
		if page > self.totalPages: page = self.totalPages
		return int((page - 1) * self.perPage)
						
	def getNextPage(self):
		return self.nextStart
			
	def getPrevPage(self):
		return self.prevStart
				
	def getPageDisplay(self):
		if self.pageDisplay: return self.pageDisplay
		if self.page is not None and self.totalPages is not None:
			return 'Page %s of %s' % (self.page,self.totalPages)
		
######################################################################################
# Forum Browser API for TapaTalk
######################################################################################
class TapatalkForumBrowser:
	quoteFormats = 	{	'mb':"(?s)\[quote='(?P<user>[^']*?)' pid='(?P<pid>[^']*?)' dateline='(?P<date>[^']*?)'\](?P<quote>.*)\[/quote\]",
						'xf':'(?s)\[quote="(?P<user>[^"]*?), post: (?P<pid>[^"]*?), member: (?P<uid>[^"]*?)"\](?P<quote>.*)\[/quote\]',
						'vb':'\[QUOTE=(?P<user>\w+)(?:;\d+)*\](?P<quote>.+?)\[/QUOTE\](?is)'
					}
	
	PageData = PageData
	def __init__(self,forum,always_login=False):
		self.forum = forum[3:]
		self.prefix = 'TT.'
		self._url = ''
		self.transport = None
		self.server = None
		self.forumConfig = {}
		self.needsLogin = True
		self.alwaysLogin = always_login
		self.lang = sys.modules["__main__"].__language__
		self.LOG = sys.modules["__main__"].LOG
		self.ERROR = sys.modules["__main__"].ERROR
		self.loadForumFile()
		self.reloadForumData(self.forum)
		self._loggedIn = False
		
	def getForumID(self):
		return self.prefix + self.forum
	
	def isLoggedIn(self):
		#return self._loggedIn
		return self.transport.loggedIn()
	
	def resetBrowser(self): pass
	
	def loadForumFile(self):
		self.urls = {}
		self.filters = {}
		self.theme = {}
		self.forms = {}
		self.formats = {}
		self.smilies = {}
		forum = self.getForumID()
		self.needsLogin = True
		fname = os.path.join(sys.modules["__main__"].FORUMS_PATH,forum)
		if not os.path.exists(fname):
			fname = os.path.join(sys.modules["__main__"].FORUMS_STATIC_PATH,forum)
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
		self._url = self.urls.get('tapatalk_server','')
		self.formats['quote'] = ''
	
	def reloadForumData(self,forum):
		self.filters = {'quote':'\[QUOTE\](?P<quote>.*)\[/QUOTE\](?is)',
						'code':'\[CODE\](?P<code>.+?)\[/CODE\](?is)',
						'php':'\[PHP\](?P<php>.+?)\[/PHP\](?is)',
						'html':'\[HTML\](?P<html>.+?)\[/HTML\](?is)',
						'image':'\[IMG\](?P<url>.+?)\[/IMG\](?is)',
						'link':'\[url=(?P<url>[^\]]+?)\](?P<text>.+?)\[/url\](?is)',
						'link2':'\[url\](?P<text>(?P<url>.+?))\[/url\](?is)',
						'post_link':'(?:showpost.php|showthread.php)\?[^<>"]*?tid=(?P<threadid>\d+)[^<>"]*?pid=(?P<postid>\d+)',
						'thread_link':'showthread.php\?[^<>"]*?tid=(?P<threadid>\d+)'}
		
		if not self.loadForumData(forum):
			self.forum = 'forum.xbmc.org'
			self.loadForumData(self.forum)
		
	def loadForumData(self,forum):
		self.needsLogin = True
		if not self._url:
			self._url = 'http://%s/mobiquo/mobiquo.php' % forum
		self.forum = forum
		self.transport = CookieTransport()
		self.server = xmlrpclib.ServerProxy(self._url,transport=self.transport)
		self.getForumConfig()
		return True
			
	def getForumConfig(self):
		self.forumConfig = self.server.get_config()
		self.LOG('Forum Type: ' + self.getForumType())
		self.LOG('Forum API Level: ' + self.forumConfig.get('api_level',''))
		
	def getForumType(self):
		return self.forumConfig.get('version','')[:2]
	
	def getQuoteFormat(self):
		forumType = self.getForumType()
		return self.quoteFormats.get(forumType)
	
	def getRegURL(self):
		sub = self.forumConfig.get('reg_url','')
		if not sub: return ''
		return self._url.split('mobiquo/',1)[0] + sub
	
	def setLogin(self,user,password,always=False):
		self.user = user
		self.password = password
		self.alwaysLogin = always
			
	def login(self):
		self.LOG('LOGGING IN')
		result = self.server.login(xmlrpclib.Binary(self.user),xmlrpclib.Binary(self.password))
		if not result.get('result'):
			self.LOG('LOGIN FAILED: ' + str(result.get('result_text')))
			self._loggedIn = False
		else:
			self.LOG('LOGGED IN')
			self._loggedIn = True
			return True
		return False
		
	def checkLogin(self,callback=None):
		if not self.user or not self.password: return False
		if not callback: callback = self.fakeCallback
		if self.needsLogin or not self.isLoggedIn():
			self.needsLogin = False
			if not callback(5,self.lang(30100)): return False
			if not self.login():
				return False
		return True
		
	def getPMCounts(self):
		if not self.checkLogin(): return None
		result = self.server.get_box_info()
		if not result.get('result'): return None
		unread = 0
		total = 0
		boxid = None
		for l in result.get('list',[]):
			if l.get('box_type') == 'INBOX':
				if not boxid: boxid = l.get('box_id')
				total += l.get('msg_count',0)
				unread += l.get('unread_count',0)
		return {'unread':unread,'total':total,'boxid':boxid}
		
	def makeURL(self,url):
		#self.LOG('AVATAR: ' + url)
		return url
	
	def createForumDict(self,data,sub=False):
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
			em = self.ERROR('ERROR GETTING FORUMS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		
		forums = []
		for general in flist:
			if not general.get('sub_only'): forums.append(self.createForumDict(general))
			for forum in general.get('child',[]):
				if not forum.get('sub_only'): forums.append(self.createForumDict(forum))
				for sub in forum.get('child',[]):
					if not sub.get('sub_only'): forums.append(self.createForumDict(sub,True))
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None,None)
			return (None,None,None)
		logo = self.urls.get('logo') or 'http://%s/favicon.ico' % self.forum
		pm_counts = self.getPMCounts()
		callback(100,self.lang(30052))
		if donecallback: donecallback(forums,logo,pm_counts)
		else: return forums, logo, pm_counts
		
	def createThreadDict(self,data,sticky=False):
		data['threadid'] = data.get('topic_id','')
		data['starter'] = str(data.get('topic_author_name',self.user))
		data['title'] = str(data.get('topic_title',''))
		data['short_content'] = str(data.get('short_content',''))
		#data['lastposter'] = 
		#data['forumid'] = 
		data['sticky'] = sticky
		return data
	
	def _getThreads(self,forumid,topic_num):
		announces = self.server.get_topic(forumid,0,49,'ANN').get('topics',[])
		for a in announces: self.createThreadDict(a,True)
		stickys = self.server.get_topic(forumid,0,49,'TOP').get('topics',[])
		for s in stickys: self.createThreadDict(s,True)
		topics = self.server.get_topic(forumid,topic_num,int(topic_num) + 19)
		pd = PageData(topics,topic_num)
		normal = topics.get('topics',[])
		for n in normal: self.createThreadDict(n)
		return announces + stickys + normal, pd
	
	def _getSubscriptions(self):
		sub = self.server.get_subscribed_topic()
		pd = PageData({},0)
		#if not sub.get('result'):
		#	raise Exception(sub.get('result_text'))
		normal = sub.get('topics',[])
		for n in normal: self.createThreadDict(n)
		return normal, pd
	
	def getThreads(self,forumid,page=0,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		try:
			if forumid:
				threads,pd = self._getThreads(forumid,page or 0)
			else:
				threads,pd = self._getSubscriptions()
		except:
			em = self.ERROR('ERROR GETTING THREADS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		
		callback(100,self.lang(30052))
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getReplies(self,threadid,forumid,page=0,lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		try:
			page = int(page)
		except:
			page = 0
		if not callback: callback = self.fakeCallback
		try:
			sreplies = []
			if pid:
				test = self.server.get_thread_by_post(pid,20)
				index = test.get('position')
				start = int((index - 1) / 20) * 20
				thread = self.server.get_thread(threadid,start,start + 19)
			else:
				thread = self.server.get_thread(threadid,page,page + 19)
			posts = thread.get('posts')
			if not posts:
				callback(-1,'NO POSTS')
				if donecallback: donecallback(None,None)
				return (None,None)
			for p in posts: sreplies.append(ForumPost(p))
			sreplies.reverse()
		except:
			em = self.ERROR('ERROR GETTING POSTS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		pd = PageData(thread,page or 0)
		pd.tid = threadid
		callback(100,self.lang(30052))
		
		if donecallback: donecallback(sreplies, pd)
		else: return sreplies, pd
		
	def hasPM(self):
		return True
	
	def getPrivateMessages(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		pmInfo = self.getPMCounts()
		boxid = pmInfo.get('boxid')
		if not boxid:
			if donecallback: donecallback(None,None)
			return (None,None)
		
		try:
			messages = self.server.get_box(boxid,0,49)
		except:
			em = self.ERROR('ERROR GETTING PRIVATE MESSAGES')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		if not callback(80,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		pms = []
		for p in messages.get('list',[]):
			p['boxid'] = boxid
			pms.append(ForumPost(p))
		
		callback(100,self.lang(30052))
		
		if donecallback: donecallback(pms,None)
		else: return pms, None
	
	def hasSubscriptions(self):
		return True
	
	def getSubscriptions(self,page='',callback=None,donecallback=None):
		if not self.checkLogin(callback=callback): return (None,None)
		return self.getThreads(None, page, callback, donecallback)
		
	def getPageUrl(self,page,sub,pid='',tid='',fid='',lastid=''):
		return ''
		
	def getURL(self,name):
		return self._url + self.urls.get(name,'')
		
	def fakeCallback(self,pct,message=''): return True
	
	def post(self,post,callback=None):
		if not callback: callback = self.fakeCallback
		if not self.checkLogin(callback=callback): return False		
		callback(40,self.lang(30106))
		result = self.server.reply_post(post.fid,post.tid,xmlrpclib.Binary(post.title),xmlrpclib.Binary(post.message))
		callback(100,self.lang(30052))
		status = result.get('result',False)
		if not status:
			post.error = str(result.get('result_text'))
			self.LOG('Failed To Post: ' + post.error)
		return result.get('result',False)
		
	def doPrivateMessage(self,to,title,message,callback=None):
#		user_name 		yes 	To support sending message to multiple recipients, the app constructs an array and insert user_name for each recipient as an element inside the array. 	3
#		subject 	byte[] 	yes 		3
#		text_body 	byte[] 	yes 		3
#		action 	Int 		1 = REPLY to a message; 2 = FORWARD to a message. If this field is presented, the pm_id below also need to be provided. 	3
#		pm_id 	String 		It is used in conjunction with "action" parameter to indicate which PM is being replied or forwarded to.
		toArray = []
		for t in to.split(','): toArray.append(xmlrpclib.Binary(t))
		result = self.server.create_message(toArray,xmlrpclib.Binary(title),xmlrpclib.Binary(message))
		callback(100,self.lang(30052))
		return result.get('result') or False
		
	def deletePrivateMessageViaIndex(self,pmidx,callback=None):
		pmInfo = self.getPMCounts()
		boxid = pmInfo.get('boxid')
		if not boxid: return
		result = self.server.delete_message(pmidx,boxid)
		return result.get('result') or False
		
	def deletePost(self,post):
		if not self.checkLogin(): return False
		result = self.server.m_delete_post(post.pid,2,xmlrpclib.Binary(''))
		if not result.get('result'):
			post.error = str(result.get('result_text'))
		return post
			
	def canDelete(self,user):
		return True
	