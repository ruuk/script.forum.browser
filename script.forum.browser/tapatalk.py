import xmlrpclib, httplib, sys, re, time, os
import cookielib, socket, errno
import urllib2
import iso8601, forumbrowser
#import xbmc #@UnresolvedImport

DEBUG = sys.modules["__main__"].DEBUG
LOG = sys.modules["__main__"].LOG
ERROR = sys.modules["__main__"].ERROR
__addon__ = sys.modules["__main__"].__addon__

def checkVersion(version1, version2):
	def normalize(v):
		return [int(x) for x in re.sub(r'(\.0+)*$','', v).split(".")]
	return cmp(normalize(version1), normalize(version2))

def testForum(forum):
	url2 = None
	url3 = None
	if forum.startswith('http://'):
		url = forum
		if not forum.endswith('/') and not forum.endswith('.php'): forum += '/'
		if not forum.endswith('.php/'): url2 = forum + 'mobiquo/mobiquo.php'
	else:
		if forum.startswith('/'): forum = forum[1:]
		if forum.endswith('/'): forum = forum[:-1]
		url = 'http://%s/mobiquo/mobiquo.php' % forum
		url2 = None
		if '/' in forum: url3 = 'http://%s/mobiquo/mobiquo.php' % forum.split('/',1)[0]
	
	for u in (url,url2,url3):
		if not u: continue
		try:
			server = xmlrpclib.ServerProxy(u,transport=CookieTransport())
			server.get_config()
			return u
		except:
			continue
	return None
			
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
		self.endheadersTakesOneArg = httplib.HTTPConnection.endheaders.func_code.co_argcount < 2 #@UndefinedVariable
		self.getresponseTakesOneArg = httplib.HTTPConnection.getresponse.func_code.co_argcount < 2 #@UndefinedVariable
		try:
			import gzip
		except ImportError:
			gzip = None
		self.gzip = gzip

	def loggedIn(self):
		return self._loggedIn
	
	def request(self, host, handler, request_body, verbose=0):
		#retry request once if cached connection has gone cold
		for i in (0, 1):
			try:
				return self.single_request(host, handler, request_body, verbose)
			except socket.error, e:
				if i or e.errno not in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
					raise
			except httplib.BadStatusLine: #close after we sent request
				if i:
					raise

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
			#For older python verions
			if self.getresponseTakesOneArg:
				response = h.getresponse()
			else:
				response = h.getresponse(buffering=True)
			
			headers = {}
			if DEBUG:
				LOG('DEBUG: xmlrpclib response headers:')
			for k,v in response.getheaders():
				#Mobiquo_is_login: false
				if DEBUG:
					LOG('  %s=%s' % (k,v))
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
			if hasattr(self,'close'): self.close()
			raise

		#discard any response data and raise exception
		if (response.getheader("content-length", 0)):
			response.read()
			
		raise httplib.HTTPException(response.reason)
	
	def send_content(self, connection, request_body):
		connection.putheader("Content-Type", "text/xml")

		#optionally encode the request
		if (self.encode_threshold is not None and
			self.encode_threshold < len(request_body) and
			self.gzip):
			import gzip
			connection.putheader("Content-Encoding", "gzip")
			request_body = self.gzip_encode(request_body,gzip)

		connection.putheader("Content-Length", str(len(request_body)))
		#For older python verions
		if self.endheadersTakesOneArg:
			connection.endheaders()
			if request_body: connection.send(request_body)
		else:
			connection.endheaders(request_body)
			
	def gzip_encode(self,data,gzip):
		import StringIO
		"""data -> gzip encoded data
	
		Encode data using the gzip content encoding as described in RFC 1952
		"""
		if not gzip:
			raise NotImplementedError
		f = StringIO.StringIO()
		gzf = gzip.GzipFile(mode="wb", fileobj=f, compresslevel=1)
		gzf.write(data)
		gzf.close()
		encoded = f.getvalue()
		f.close()
		return encoded
			

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
			self.text = match.group('text')
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
class ForumPost(forumbrowser.ForumPost):
	def __init__(self,pdict=None):
		forumbrowser.ForumPost.__init__(self, pdict)
		self.MC = sys.modules["__main__"].MC
		self.FB = sys.modules["__main__"].FB
			
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
			self.online = pdict.get('is_online',False)
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
			self.online = pdict.get('is_online',False)
			self.title = str(pdict.get('msg_subject',''))
			self.message = str(pdict.get('short_content',''))
			self.boxid = pdict.get('boxid','')
			self.signature = ''
			
	def setUserInfo(self,info):
		self.userInfo = info
		self.status = str(info.get('display_text',''))
		self.activity = str(info.get('current_activity',''))
		self.postCount = info.get('post_count',0)
		date = str(info.get('reg_time',''))
		if date:
			date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
			date = time.strftime('%b %d, %Y',iso8601.parse_date(date).timetuple())
		self.joinDate = date
		
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
	
	def getMessage(self,skip=False,raw=False):
		if self.isShort and not skip:
			m = self.FB.server.get_message(self.getID(),self.boxid)
			self.message = str(m.get('text_body',self.message))
			self.isShort = False
		elif raw and self.userName == self.FB.user:
			m = self.FB.server.get_raw_post(self.getID())
			self.message = str(m.get('post_content',self.message))
		return self.message + self.signature
	
	def messageAsText(self):
		return sys.modules["__main__"].messageToText(self.getMessage())
		
	def messageAsDisplay(self,short=False,raw=False):
		if short:
			message = self.getShortMessage()
		else:
			message = self.getMessage(raw=raw)
		message = message.replace('\n','[CR]')
		message = re.sub('\[(/?)b\]',r'[\1B]',message)
		message = re.sub('\[(/?)i\]',r'[\1I]',message)
		if self.isPM:
			return self.MC.parseCodes(message)
		else:
			return self.MC.messageToDisplay(message)
		
	def messageAsQuote(self):
		qp = self.FB.server.get_quote_post(self.getID())
		#print qp.get('result_text')
		return str(qp.get('post_content',''))
		
	def imageURLs(self):
		return self.MC.imageFilter.findall(self.getMessage())
		
	def linkImageURLs(self):
		return re.findall('<a.+?href="(http://.+?\.(?:jpg|png|gif|bmp))".+?</a>',self.message,re.S)
		
	def linkURLs(self):
		return self.MC.linkFilter.finditer(self.getMessage(),re.S)
	
	def link2URLs(self):
		if not self.MC.linkFilter2: return []
		return self.MC.linkFilter2.finditer(self.getMessage(),re.S)
		
	def links(self):
		links = []
		for m in self.linkURLs(): links.append(PMLink(m))
		for m in self.link2URLs(): links.append(PMLink(m))
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
class TapatalkForumBrowser(forumbrowser.ForumBrowser):
	browserType = 'tapatalk'
	PageData = PageData
	
	def __init__(self,forum,always_login=False):
		forumbrowser.ForumBrowser.__init__(self, forum, always_login)
		self.forum = forum[3:]
		self.prefix = 'TT.'
		self._url = ''
		self.transport = None
		self.server = None
		self.forumConfig = {}
		self.needsLogin = True
		self.alwaysLogin = always_login
		self.lang = sys.modules["__main__"].__language__
		self.loadForumFile()
		self.reloadForumData(self.forum)
		self.loginError = ''
		self.altQuoteStartFilter = '\[quote\](?P<user>[^:]+?) \w+:'
	
	def isLoggedIn(self):
		#return self._loggedIn
		return self.transport.loggedIn()
	
	def loadForumFile(self):
		forum = self.getForumID()
		fname = os.path.join(sys.modules["__main__"].FORUMS_PATH,forum)
		if not os.path.exists(fname):
			fname = os.path.join(sys.modules["__main__"].FORUMS_STATIC_PATH,forum)
			if not os.path.exists(fname): return False
		self.loadForumData(fname)
		self._url = self.urls.get('tapatalk_server','')
		self.formats['quote'] = ''
	
	def reloadForumData(self,forum):
		if not self.setupClient(forum):
			self.forum = 'forum.xbmc.org'
			self.setupClient(self.forum)
		
	def setupClient(self,forum):
		self.needsLogin = True
		if not self._url:
			self._url = 'http://%s/mobiquo/mobiquo.php' % forum
		self.forum = forum
		self.transport = CookieTransport()
		url = self._url
		if __addon__.getSetting('enable_ssl'):
			LOG('Enabling SSL')
			url = url.replace('http://','https://')
			self.SSL = True
		self.server = xmlrpclib.ServerProxy(url,transport=self.transport)
		self.getForumConfig()
		return True
			
	def getForumConfig(self):
		try:
			self.forumConfig = self.server.get_config()
			LOG('Forum Type: ' + self.getForumType())
			LOG('Forum Plugin Version: ' + self.getForumPluginVersion())
			LOG('Forum API Level: ' + self.forumConfig.get('api_level',''))
			if DEBUG: print self.forumConfig
		except:
			ERROR('Failed to get forum config')
		
	def guestOK(self):
		return self.forumConfig.get('guest_okay',True)
	
	def getForumType(self):
		return self.forumConfig.get('version','')[:2]
	
	def getForumPluginVersion(self):
		return self.forumConfig.get('version','').split('_')[-1]
	
	def getRegURL(self):
		sub = self.forumConfig.get('reg_url','')
		if not sub: return ''
		return self._url.split('mobiquo/',1)[0] + sub
			
	def getPassword(self):
		if self.forumConfig.get('support_md5') == '1':
			import hashlib
			if self.getForumType() == 'sm':
				LOG('Sending sha1 hashed password')
				m = hashlib.new('sha1')
				m.update(self.password)
				return m.hexdigest()
			else:
				LOG('Sending md5 hashed password')
				m = hashlib.md5(self.password)
				return m.hexdigest()
		return self.password
			
	def login(self):
		LOG('LOGGING IN')
		result = self.server.login(xmlrpclib.Binary(self.user),xmlrpclib.Binary(self.getPassword()))
		if not result.get('result'):
			error = str(result.get('result_text',''))
			LOG('LOGIN FAILED: ' + error)
			self.loginError = error
			self._loggedIn = False
		else:
			if DEBUG:
				LOG('LOGGED IN: ' + str(result.get('result_text','')))
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
		
	def getPMCounts(self,callback_percent=5):
		if not self.hasPM(): return None
		if not self.checkLogin(callback_percent=callback_percent): return None
		result = self.server.get_box_info()
		if not result.get('result'):
			LOG('Failed to get PM counts: ' + str(result.get('result_text')))
			return None
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
		#LOG('AVATAR: ' + url)
		return url
	
	def createForumDict(self,data,sub=False):
		data['forumid'] = data.get('forum_id')
		data['title'] = str(data.get('forum_name'))
		data['description'] = str(data.get('description'))
		data['subscribed'] = data.get('is_subscribed',False)
		data['subforum'] = sub
		return data
		
	def getForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		logo = None
		while True:
			if not callback(20,self.lang(30102)): break
			try:
				flist = self.server.get_forum()
			except:
				em = ERROR('ERROR GETTING FORUMS')
				callback(-1,'%s' % em)
				if donecallback: donecallback(None,None,None)
				return (None,None,None)
			if not callback(40,self.lang(30103)): break
			forums = []
			for general in flist:
				if not general.get('sub_only'): forums.append(self.createForumDict(general))
				for forum in general.get('child',[]):
					if not forum.get('sub_only'): forums.append(self.createForumDict(forum))
					for sub in forum.get('child',[]):
						if not sub.get('sub_only'): forums.append(self.createForumDict(sub,True))
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
	
	def getSubscribedForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		while True:
			if not callback(20,self.lang(30102)): break
			try:
				flist = self.server.get_subscribed_forum()
			except:
				em = ERROR('ERROR GETTING FORUM SUBSCRIPTIONS')
				callback(-1,'%s' % em)
				if donecallback: donecallback(None,None,None)
				return (None,None,None)
			if not callback(40,self.lang(30103)): break
			forums = []
			for f in flist.get('forums',[]):
				f = self.createForumDict(f)
				f['subscribed'] = True
				forums.append(f)
			if not callback(80,self.lang(30231)): break
			if donecallback: donecallback(forums)
			return forums
			
		if donecallback: donecallback(None)
		return None
		
	def isForumSubscribed(self,fid):
		forums = self.getSubscribedForums(None, None)
		for f in forums:
			if f.get('forumid') == fid: return True
		return False
	
	def createThreadDict(self,data,sticky=False):
		data['threadid'] = data.get('topic_id','')
		data['starter'] = str(data.get('topic_author_name',self.user))
		data['title'] = str(data.get('topic_title',''))
		data['short_content'] = str(data.get('short_content',''))
		data['subscribed'] = data.get('is_subscribed',False)
		data['lastposter'] = str(data.get('last_reply_user',''))
		#data['forumid'] = 
		data['sticky'] = sticky
		return data
	
	def _getThreads(self,forumid,topic_num,callback,donecallback):
		if not callback: callback = self.fakeCallback
		while True:
			if not callback(10,self.lang(30102)): break
			announces = self.server.get_topic(forumid,0,49,'ANN').get('topics',[])
			if not callback(30,self.lang(30103)): break
			for a in announces: self.createThreadDict(a,True)
			if not callback(40,self.lang(30102)): break
			stickys = self.server.get_topic(forumid,0,49,'TOP').get('topics',[])
			if not callback(60,self.lang(30103)): break
			for s in stickys: self.createThreadDict(s,True)
			if not callback(70,self.lang(30102)): break
			topics = self.server.get_topic(forumid,topic_num,int(topic_num) + 19)
			if not callback(90,self.lang(30103)): break
			pd = PageData(topics,topic_num)
			normal = topics.get('topics',[])
			for n in normal: self.createThreadDict(n)
			return announces + stickys + normal, pd
			
		if donecallback:
			donecallback(None,None)
		return (None,None)
	
	def _getSubscriptions(self,callback,donecallback):
		callback(20,self.lang(30102))
		sub = self.server.get_subscribed_topic()
		pd = PageData({},0)
		#if not sub.get('result'):
		#	raise Exception(sub.get('result_text'))
		normal = sub.get('topics',[])
		if not callback(70,self.lang(30103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		for n in normal: self.createThreadDict(n)
		return normal, pd
	
	def getThreads(self,forumid,page=0,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		try:
			if forumid:
				threads,pd = self._getThreads(forumid,page or 0,callback,donecallback)
			else:
				threads,pd = self._getSubscriptions(callback,donecallback)
		except:
			em = ERROR('ERROR GETTING THREADS')
			callback(-1,'%s' % em)
			if donecallback: donecallback(None,None)
			return (None,None)
		
		callback(100,self.lang(30052))
		if donecallback: donecallback(threads,pd)
		else: return threads,pd
		
	def getReplies(self,threadid,forumid,page=0,lastid='',pid='',callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		while True:
			try:
				page = int(page)
			except:
				page = 0
			if not callback(20,self.lang(30102)): break
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
				if not callback(60,self.lang(30103)): break
				infos = {}
				ct = page + 1
				for p in posts:
					fp = ForumPost(p)
					fp.postNumber = ct
					if not fp.userName in infos:
						infos[fp.userName] = self.server.get_user_info(xmlrpclib.Binary(fp.userName))
					fp.setUserInfo(infos[fp.userName])
					sreplies.append(fp)
					ct += 1
				sreplies.reverse()
			except xmlrpclib.Fault, e:
				LOG('ERROR GETTING POSTS: ' + e.faultString)
				raise forumbrowser.Error(e.faultString)
			except:
				em = ERROR('ERROR GETTING POSTS')
				callback(-1,em)
				if donecallback: donecallback(None,None)
				return (None,None)
			
			if not callback(80,self.lang(30103)): break
			pd = PageData(thread,page or 0)
			pd.tid = threadid
			callback(100,self.lang(30052))
			
			if donecallback: donecallback(sreplies, pd)
			return sreplies, pd
			
		if donecallback: donecallback(None,None)
		return (None,None)
		
	def hasPM(self):
		return not self.forumConfig.get('disable_pm','0') == '1'
	
	def getPrivateMessages(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		
		while True:
			if not callback(20,self.lang(30102)): break
			pmInfo = self.getPMCounts(20)
			if not pmInfo: break
			boxid = pmInfo.get('boxid')
			if not boxid: break
			if not callback(50,self.lang(30102)): break
			try:
				messages = self.server.get_box(boxid,0,49)
			except:
				em = ERROR('ERROR GETTING PRIVATE MESSAGES')
				callback(-1,'%s' % em)
				break
			pms = []
			if not callback(80,self.lang(30103)): break
			infos = {}
			for p in messages.get('list',[]):
				p['boxid'] = boxid
				fp = ForumPost(p)
				if not fp.userName in infos:
					infos[fp.userName] = self.server.get_user_info(xmlrpclib.Binary(fp.userName))
				fp.setUserInfo(infos[fp.userName])
				pms.append(fp)
			
			callback(100,self.lang(30052))
			if donecallback: donecallback(pms,None)
			return pms, None
		
		if donecallback: donecallback(None,None)
		return (None,None)
	
	def hasSubscriptions(self):
		return True
	
	def hasForumSubscriptions(self):
		return True
	
	def getSubscriptions(self,page='',callback=None,donecallback=None):
		if not self.checkLogin(callback=callback): return (None,None)
		threads = self.getThreads(None, page, callback, None)
		if self.hasForumSubscriptions():
			forums = self.getSubscribedForums(callback, None)
			donecallback((forums,threads[0]),threads[1])
			return (forums,threads[0]),threads[1]
		else:
			donecallback(threads[0],threads[1])
			return threads
		
	def getPageUrl(self,page,sub,pid='',tid='',fid='',lastid=''):
		return ''
		
	def getURL(self,name):
		return self._url + self.urls.get(name,'')
	
	def post(self,post,callback=None):
		if post.isEdit:
			return self.editPost(post)
		LOG('Posting reply')
		if not callback: callback = self.fakeCallback
		if not self.checkLogin(callback=callback): return False
		callback(40,self.lang(30106))
		result = self.server.reply_post(post.fid,post.tid,xmlrpclib.Binary(post.title),xmlrpclib.Binary(post.message))
		callback(100,self.lang(30052))
		status = result.get('result',False)
		if not status:
			post.error = str(result.get('result_text'))
			LOG('Failed To Post: ' + post.error)
		return status
		
	def getPostForEdit(self,pid):
		result = self.server.get_raw_post(pid)
		if not result:
			LOG('Could not get raw post for editing')
			return None
		pm = forumbrowser.PostMessage(pid,isEdit=True)
		pm.setMessage(str(result.get('post_title','')),str(result.get('post_content','')))
		return pm
		
	def checkMyBBEditFix(self,pm):
		if self.getForumType() == 'mb' and checkVersion('2.0.0',self.getForumPluginVersion()) > -1:
			if __addon__.getSetting('do_mybb_edit_bug_fix'):
				if pm.tid:
					try:
						sub = self.server.get_subscribed_topic()
					except:
						ERROR('Error getting subscribed threads in checkMyBBEditFix()')
						return False
					for s in sub.get('topics',[]):
						if s.get('topic_id') == pm.tid:
							return True
		return False
	
	def editPost(self,pm):
		LOG('Saving edited post')
		fix = self.checkMyBBEditFix(pm)
		result = self.server.save_raw_post(pm.pid,xmlrpclib.Binary(pm.title),xmlrpclib.Binary(pm.message))
		if fix:
			LOG('Using MyBB edit post bug fix')
			self.subscribeToThread(pm.tid)
		return result.get('result',False)
	
	def subscribeToThread(self,tid):
		result = self.server.subscribe_topic(str(tid))
		if not result.get('result',False):
			LOG('Failed to subscribe to thread: ' + str(result.get('result_text')))
			return False
		return True
		
	def canEditPost(self,user):
		if user == self.user: return True
		return False
	
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
		soft_hard = int(self.forumConfig.get('soft_delete','2'))
		result = self.server.m_delete_post(post.pid,soft_hard,xmlrpclib.Binary('Not Given'))
		if not result.get('result'):
			post.error = str(result.get('result_text'))
			LOG('Failed to delete post: %s (%s)' % (post.error,soft_hard == 1 and 'Soft' or 'Hard'))
		return post
			
	def canDelete(self,user):
		if user == self.user: return True
		return False
	
	def canSubscribeThread(self,tid):
		return True
	
	def subscribeThread(self,tid):
		result = self.server.subscribe_topic(tid)
		if result.get('result'):
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to subscribe to thread: ' + text)
			return text
		
	def unSubscribeThread(self,tid):
		result = self.server.unsubscribe_topic(tid)
		if result.get('result'):
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to unsubscribe from thread: ' + text)
			return text
	
	def subscribeForum(self,fid):
		result = self.server.subscribe_forum(fid)
		if result.get('result'):
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to subscribe to forum: ' + text)
			return text
		
	def unSubscribeForum(self,fid):
		result = self.server.unsubscribe_forum(fid)
		if result.get('result'):
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to unsubscribe from forum: ' + text)
			return text
	