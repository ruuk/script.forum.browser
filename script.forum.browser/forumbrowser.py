#Forum browser common
import re, urllib, urllib2

class FBOnlineDatabase():
	def __init__(self):
		self.url = 'http://xbmc.2ndmind.net/forumbrowser/tapatalk.php'
	
	def postData(self,**data):
		enc = urllib.urlencode(data)
		try:
			result = urllib2.urlopen(self.url,enc).read()
			return result
		except:
			err = ERROR('FBTTOnlineDatabase.postData()')
			return 'ERROR: ' + err
			
	def addForum(self,name,url,logo='',desc='',ftype='TT'):
		return self.postData(do='add',name=name,url=url,desc=desc,logo=logo,type=ftype)
		
	def getForumList(self):
		flist = self.postData(do='list')
		if not flist: return None
		flist = flist.split('\n')
		final = []
		for f in flist:
			if f:
				name, rest = f.split('=',1)
				url,desc,logo,ftype = rest.split('\r',3)
				final.append({'name':name,'url':url,'desc':desc,'logo':logo,'type':ftype})
		return final

class HTMLPageInfo:
	def __init__(self,url):
		self.url = url
		
		self.base = url
		if not self.base.endswith('/'): self.base += '/'
		
		base2 = 'http://' + url.rsplit('://',1)[-1].split('/',1)[0]
		self.base2 = base2
		self.base2 += '/'
		
		self.isValid = True
		self._getHTML()
		
	def _getHTML(self):
		try:
			opener = urllib2.build_opener()
			o = opener.open(urllib2.Request(self.url,None,{'User-Agent':'Wget/1.12'}))
			self.html = o.read()
			o.close()
		except:
			self.isValid = False
			LOG('HTMLPageInfo 1: FAILED')
			
		if self.url == self.base2: return
		
		try:
			opener = urllib2.build_opener()
			o = opener.open(urllib2.Request(self.base2,None,{'User-Agent':'Wget/1.12'}))
			self.html2 = o.read()
			o.close()
			self.isValid = True
		except:
			LOG('HTMLPageInfo 2: FAILED')
		
	def title(self,default=''):
		try: return re.search('<title>(.*?)</title>',self.html).group(1) or ''
		except: pass
		try: return re.search('<title>(.*?)</title>',self.html2).group(1) or ''
		except: pass
		return ''
		
		
	def description(self,default=''):
		try: return re.search('<meta[^>]*?name="description"[^>]*?content="([^"]*?)"',self.html).group(1)
		except: pass
		try: return re.search('<meta[^>]*?name="description"[^>]*?content="([^"]*?)"',self.html2).group(1)
		except: pass
		return default
		
	def images(self):
		images = self._images(self.html, self.base)
		images += self._images(self.html2, self.base2)
		return images
		
	def _images(self,html,base):
		urlList = re.findall('<img[^>]*?src="([^"]+?)"[^>]*?>',html) #Image tags
		urlList2 = re.findall('<meta[^>]*?property="[^"]*image"[^>]*?content="([^"]*?)"',html) #Meta tag images
		final = []
		for u in urlList + urlList2:
			if u in final: continue
			if u.startswith('http'):
				final.append(u)
			elif u.startswith('./'):
				final.append(base + u[2:])
			elif u.startswith('.'):
				final.append(base + u[1:])
			elif u.startswith('/'):
				pass
			else:
				final.append(base + u)
		return final

################################################################################
# Action
################################################################################
class Action:
	def __init__(self,action=''):
		self.action = action

class PMLink:
	def __init__(self,match=None,post_filter=None,thread_filter=None):
		self.url = ''
		self.text = ''
		self.pid = ''
		self.tid = ''
		self.fid = ''
		self._isImage = False
		self.postFilter = post_filter
		self.threadFilter = thread_filter
		
		if match:
			self.url = match.group('url')
			text = match.group('text')
		self.processURL()
			
	def processURL(self):
		if not self.url: return
		self._isImage = re.search('http://.+?\.(?:jpg|png|gif|bmp)',self.url) and True or False
		if self._isImage: return
		pm = self.postFilter and re.search(self.postFilter,self.url) or None
		tm = self.threadFilter and re.search(self.threadFilter,self.url) or None
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
# PostMessage
################################################################################
class PostMessage(Action):
	def __init__(self,pid='',tid='',fid='',title='',message='',is_pm=False,isEdit=False):
		Action.__init__(self,'CHANGE')
		self.pid = pid
		self.tid = tid
		self.fid = fid
		self.title = title
		self.message = message
		self.quote = ''
		self.quser = ''
		self.to = ''
		self.isPM = is_pm
		self.isEdit = isEdit
		self.error = ''
		self.tagFilter = re.compile('<[^<>]+?>',re.S)
		
	def setQuote(self,user,quote):
		self.quser = self.tagFilter.sub('',user)
		self.quote = quote
		
	def setMessage(self,title,message):
		self.title = title
		self.message = message

################################################################################
# PageData
################################################################################
class PageData:
	def __init__(self,page=1,current=0,per_page=20,total_items=0,current_total=0,is_replies=False):
		self.current = current
		
		self.totalitems = total_items
		self.totalPages = int(self.totalitems / per_page)
		self.totalPages += (self.totalitems % per_page) and 1 or 0 
		
		if current > 0:
			self.pageMode= False
			self.page = int((current + 1) / per_page) + 1
			self.nextStart = current + current_total
			ps = current - per_page
			if ps < 0: ps = 0
			self.prevStart = ps
			self.prev = current > 0
		else:
			self.pageMode = True
			if page < 0: page = self.totalPages
			if page == 0: page = 1
			self.page = page
			current = (page - 1) * per_page
			self.nextStart = page + 1
			ps = page -1
			if ps < 1: ps = 1
			self.prevStart = ps
			self.prev = page > 1
			
		self.next = current + per_page < self.totalitems
			
		self.perPage = per_page
		self.prev = current > 0 or page > 1
		self.next = current + per_page < self.totalitems
		self.pageDisplay = ''
		self.topic = ''
		self.tid = ''
		self.isReplies = is_replies
	
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
		if self.pageMode: return page
		return int((page - 1) * self.perPage)
						
	def getNextPage(self):
		return self.nextStart
			
	def getPrevPage(self):
		return self.prevStart
				
	def getPageDisplay(self):
		if self.pageDisplay: return self.pageDisplay
		if self.page is not None and self.totalPages is not None:
			return 'Page %s of %s' % (self.page,self.totalPages)

################################################################################
# ForumPost
################################################################################
class ForumPost:
	def __init__(self,pdict=None):
		self.isShort = False
		self.isPM = False
		self.postId = ''
		self.date = ''
		self.userId = ''
		self.userName = ''
		self.avatar = ''
		self.status = ''
		self.title = ''
		self.message = ''
		self.signature = ''
		self.pid = ''
		self.translated = ''
		self.avatarFinal = ''
		self.tid = ''
		self.fid = ''
		self.boxid = ''
		self.status = ''
		self.activity = ''
		self.online = False
		self.postCount = 0
		self.postNumber = 0
		self.joinDate = ''
		self.userInfo = {}
		if pdict: self.setVals(pdict)
			
	def setVals(self,pdict): pass
			
	def setUserInfo(self,info): pass
		
	def setPostID(self,pid):
		self.postId = pid
		self.pid = pid
		self.isPM = pid.startswith('PM')
	
	def getID(self):
		if self.pid.startswith('PM'): return self.pid[2:]
		return self.pid
		
	def getShortMessage(self):
		return self.getMessage(True)
	
	def getMessage(self,skip=False,raw=False):
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
		return self.messageToDisplay(message)
		
	def messageToDisplay(self,message): return message
	
	def messageAsQuote(self): return ''
		
	def imageURLs(self): return []
		
	def linkImageURLs(self): return []
		
	def linkURLs(self): return []
	
	def link2URLs(self): return []
		
	def links(self):
		links = []
		for m in self.linkURLs(): links.append(PMLink(m))
		for m in self.link2URLs(): links.append(PMLink(m))
		return links
		
	def makeAvatarURL(self): return self.avatar
	
	def cleanUserName(self): return self.userName
			
######################################################################################
# Forum Browser API
######################################################################################
class ForumBrowser:
	quoteFormats = 	{	'mb':"(?s)\[quote='(?P<user>[^']*?)' pid='(?P<pid>[^']*?)' dateline='(?P<date>[^']*?)'\](?P<quote>.*)\[/quote\]",
						'xf':'(?s)\[quote="(?P<user>[^"]*?), post: (?P<pid>[^"]*?), member: (?P<uid>[^"]*?)"\](?P<quote>.*)\[/quote\]',
						'vb':'\[QUOTE=(?P<user>\w+)(?:;\d+)*\](?P<quote>.+?)\[/QUOTE\](?is)'
					}
	
	quoteReplace = 	{	'mb':"[quote='!USER!' pid='!POSTID!' dateline='!DATE!']!QUOTE![/quote]",
						'xf':'[quote="!USER!, post: !POSTID!, member: !USERID!"]!QUOTE![/quote]',
						'vb':'[QUOTE=!USER!;!POSTID!]!QUOTE![/QUOTE]'
					}
	
	def __init__(self,forum,always_login=False):
		self.forum = forum
		self.prefix = ''
		self._url = ''
		self.transport = None
		self.server = None
		self.forumConfig = {}
		self.needsLogin = True
		self.alwaysLogin = always_login
		self._loggedIn = False
		self.loginError = ''
		self.urls = {}
		self.filters = {}
		self.theme = {}
		self.forms = {}
		self.formats = {}
		self.smilies = {}
	
	def getForumID(self):
		return self.prefix + self.forum
	
	def resetBrowser(self): pass
		
	def loadForumData(self,fname):
		self.urls = {}
		self.filters = {'quote':'\[QUOTE\](?P<quote>.*)\[/QUOTE\](?is)',
						'code':'\[CODE\](?P<code>.+?)\[/CODE\](?is)',
						'php':'\[PHP\](?P<php>.+?)\[/PHP\](?is)',
						'html':'\[HTML\](?P<html>.+?)\[/HTML\](?is)',
						'image':'\[img\](?P<url>[^\[]+)\[/img\](?is)',
						'link':'\[url=(?P<url>[^\]]+?)\](?P<text>.+?)\[/url\](?is)',
						'link2':'\[url\](?P<text>(?P<url>.+?))\[/url\](?is)',
						'post_link':'(?:showpost.php|showthread.php)\?[^<>"]*?tid=(?P<threadid>\d+)[^<>"]*?pid=(?P<postid>\d+)',
						'thread_link':'showthread.php\?[^<>"]*?tid=(?P<threadid>\d+)'}
		
		self.theme = {}
		self.forms = {}
		self.formats = {}
		self.smilies = {}
		
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
	
	def getForumType(self): return ''

	def getQuoteFormat(self):
		forumType = self.getForumType()
		return self.quoteFormats.get(forumType,'\[QUOTE\](?P<quote>.*)\[/QUOTE\](?is)')
	
	def getQuoteReplace(self):
		forumType = self.getForumType()
		return self.quoteReplace.get(forumType,'[QUOTE]!QUOTE![/QUOTE]')
	
	def isLoggedIn(self): return False
	
	def setLogin(self,user,password,always=False):
		self.user = user
		self.password = password
		self.alwaysLogin = always
		
	def makeURL(self,url): return url
		
	
	def getPMCounts(self,pct=0): return None
	
	def canSubscribeThread(self,tid): return False
	
	def subscribeThread(self,tid): return False
	
	def canSubscribeForum(self,fid): return False
	
	def subscribeForum(self,tid): return False
	
	def hasPM(self): return False
	
	def hasSubscriptions(self): return False
	
	def canDelete(self,user): return False
	
	def canSubscribeThread(self,tid): return False
	
	def canEditPost(self,user): return False
	
	def fakeCallback(self,pct,message=''): return True
	
	
		