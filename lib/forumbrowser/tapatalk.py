# -*- coding: utf-8 -*-

from lib.util import LOG, ERROR, DEBUG, getSetting
from lib import util
from lib import asyncconnections
asyncconnections.LOG = LOG
import xmlrpclib, httplib, re, time, os, urlparse, datetime
import cookielib, socket, errno
import urllib2
import iso8601, forumbrowser
from forumbrowser import FBData
from texttransform import BBMessageConverter, convertHTMLCodes, makeUnicode, messageToText

#import xbmc #@UnresolvedImport

def checkVersion(version1, version2):
	def normalize(v):
		return [int(x) for x in re.sub(r'(\.0+)*$','', v).split(".")]
	return cmp(normalize(version1), normalize(version2))

def testForum(forum):
	if 'proboards.com' in forum:
		url = forum
		if not url.startswith('http'): url = 'http://' + url
		if not '=tapatalk' in url:
			if not url.endswith('/'): url += '/'
			url += 'index.cgi?action=tapatalk3'
		urls = [url]
	else:
		urls = forumbrowser.getForumTestUrls(forum, 'mobiquo/mobiquo.php')
		urls += forumbrowser.getForumTestUrls(forum, 'mobiquo/mobiquo')

	for u in urls:
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
		self.lastCharset = 'utf-8'
		self._loggedIn = False
		self.FB = None
		self.lastCall = time.time()
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
		self._connection = None
		#retry request once if cached connection has gone cold
		#if now - self.lastCall < 0.1: time.sleep(0.1)
		for i in (0, 1):
			try:
				result = self.single_request(host, handler, request_body, verbose)
				self.lastCall = time.time()
				return result
			except socket.error, e:
				if i or e.errno not in (errno.ECONNRESET, errno.ECONNABORTED, errno.EPIPE):
					raise
			except httplib.BadStatusLine: #close after we sent request
				if i:
					raise
			except httplib.CannotSendRequest or httplib.ResponseNotReady:
				if i:
					raise
			LOG('xmlrpclib request error - retrying with a new connection...')
			self._connection = None #ADDED by ruuk - make new connection in case the old connection object is in a bad state
			time.sleep(0.5) #ADDED by ruuk - maybe this will help too

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

			try:
				self.lastCharset = dict(response.getheaders()).get('content-type','utf-8').split('charset=',1)[-1]
			except:
				LOG('Tapatalk: CookieTransport.single_request(): Failed to set lastCharset')

			headers = {}
			if DEBUG:
				LOG('DEBUG: xmlrpclib response headers:')
			for k,v in response.getheaders():
				#Mobiquo_is_login: false
				if DEBUG:
					LOG('  %s=%s' % (k,v))
				if self.FB.isProboards:
					if k.lower() == 'set-cookie':
						if 's_app=' in v or self.FB.user in v:
							self._loggedIn = True
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
		html = ''
		if (response.getheader("content-length", 0)):
			html = response.read()
		if response.status == httplib.MOVED_PERMANENTLY:
			raise forumbrowser.ForumMovedException(response.getheader('location'))
		elif response.status == httplib.NOT_FOUND:
			raise forumbrowser.ForumNotFoundException('Tapatalk')
		elif response.status == httplib.FORBIDDEN:
			LOG('FORBIDDEN ERROR - SLEEPING 0.1 SECOND')
			time.sleep(0.1)
			raise httplib.CannotSendRequest()
		else:
			if DEBUG:
				encoding = response.getheader("content-encoding")
				if encoding == 'gzip':
					try:
						import zlib
						html = zlib.decompress(html,16+zlib.MAX_WBITS)
					except:
						ERROR('Failed to decode gzipped response HTML')
						pass
				print repr(html)
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
			try:
				connection.endheaders(request_body)
			except util.StopRequestedException:
				LOG('CookieTransport.send_content() aborted due to StopRequestedException')
				return

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

################################################################################
# TapatalkDatabaseInterface
################################################################################
class TapatalkDatabaseInterface:
	searchURL = 'https://directory.tapatalk.com/search.php?search={terms}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'
	categoryURL = 'https://directory.tapatalk.com/get_forums_by_iab_category.php?cat_id={cat_id}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'
	categoryURL2 = 'https://s2directory.tapatalk.com/get_forums_by_iab_category.php?cat_id={cat_id}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'

	class ForumEntry(forumbrowser.ForumEntry):
		forumType = 'TT'
		def __init__(self,jobj):
			self.displayName = jobj.get('name','')
			self.description = jobj.get('description','ERROR')
			self.logo = jobj.get('logo','logo')
			url = jobj.get('url','') + '/'
			mobiquoDir = jobj.get('mobiquo_dir')
			if mobiquoDir: url += mobiquoDir + '/'
			self.url = url + 'mobiquo.php'
			name = forumbrowser.nameFromURL(url)
			self.name = name
			self.forumID = 'TT.' + name
			self.category = ''
			self.categoryID = ''
			cats = jobj.get('iab_cats')
			if cats and len(cats):
				self.category = cats[0].get('name','')
				self.categoryID = cats[0].get('id','')

	def search(self,terms,page=1,per_page=20,p_dialog=None):
		result = urllib2.urlopen(self.searchURL.format(terms=terms,page=page,per_page=per_page)).read()
		import json
		jobj = json.loads(result)
		return self.processForums(jobj)

	def categories(self,cat_id=0,page=1,per_page=20,p_dialog=None):
		if cat_id == 0:
			return {'cats':self.getCategories()}

		result = urllib2.urlopen(self.categoryURL.format(cat_id=cat_id,page=page,per_page=per_page)).read()
		import json
		jobj = json.loads(result)
		return {'forums':self.processForums(jobj)}

	def getCategories(self):
		iconBase = os.path.join(util.GENERIC_MEDIA_PATH,'TTCat-%s.png')
		ret = [		{'id':'231','name':'Technology & Computing'}, #Icon attribution: Public Domain
					{'id':'1','name':'Arts & Entertainment'}, #Icon attribution: Pete Fecteau, from The Noun Project
					{'id':'157','name':'Hobbies & Interests'}, #Icon attribution: Gary Wood, from The Noun Project
					{'id':'10','name':'Automotive'}, #Icon attribution: Simon Child, from The Noun Project
					{'id':'227','name':'Sports'}, #Icon attribution: ___Lo, from The Noun Project
					{'id':'35','name':'Business'}, #Icon attribution: jose luis garcia, from The Noun Project & Jardson Araújo, from The Noun Project
					{'id':'49','name':'Careers'}, #Icon attribution: Public Domain
					{'id':'215','name':'Pets'}, #Icon attribution: Anne Bittencourt, from The Noun Project
					{'id':'62','name':'Education'}, #Icon attribution: Thibault Geffroy, from The Noun Project
					{'id':'110','name':'Health & Fitness'}, #Icon attribution: Public Domain
					{'id':'79','name':'Family & Parenting'}, #Icon attribution: Public Domain
					{'id':'208','name':'News'}, #Icon attribution: The Noun Project
					{'id':'219','name':'Religion & Spirituality'}, #Icon attribution: Dan Codyre, from The Noun Project
					{'id':'221','name':'Science'}, #Icon attribution: Public Domain
					{'id':'233','name':'Travel'}, #Icon attribution: matthew hall, from The Noun Project
					{'id':'90','name':'Food & Drink'}, #Icon attribution: Amelia Wattenberger, from The Noun Project
					{'id':'213','name':'Personal Finance'}, #Icon attribution: Jules Quick, from The Noun Project
					{'id':'225','name':'Society'}, #Icon attribution: Nicholas Menghini, from The Noun Project
					{'id':'223','name':'Shopping'}, #Icon attribution: Juan Pablo Bravo, from The Noun Project
					{'id':'190','name':'Home & Garden'}, #Icon attribution: Erin Gillaspy, from The Noun Project & Gemma Garner, from The Noun Project
					{'id':'201','name':'Law Government & Politics'}, #Icon attribution: Márcio Duarte, from The Noun Project
					{'id':'229','name':'Style & Fashion'}, #Icon attribution: Diego Naive, from The Noun Project
					{'id':'217','name':'Real Estate'} #Icon attribution: Amelia Wattenberger, from The Noun Project
				]
		for r in ret: r['icon'] = iconBase % r['id']
		return ret

	def processForums(self,jobj):
		entries = []
		for f in jobj:
			entries.append(self.ForumEntry(f))
		return entries

################################################################################
# ProBoardsDatabaseInterface
################################################################################
class ProBoardsDatabaseInterface:
	xmlrpcURL = 'http://www.proboards.com/apps/xmlrpc.cgi'

	class ForumEntry(forumbrowser.ForumEntry):
		forumType = 'PB'
		urlTail = '/index.cgi?action=tapatalk3'
		def __init__(self,data):
			#{'list': [{'name': <xmlrpclib.Binary instance at 0x169ac20>, 'url': 'reptilerescues.freeforums.net', 'forum_name': <xmlrpclib.Binary instance at 0x169a8c0>, 'forum_id': '5369004', 'logo': 'http://s29004.prbrds.com/5369004/i/dbGq_udJUza0oRZB6SWw.png', 'id': '5369004'}], 'total_match_found': 1}
			self.displayName = data.get('name','ERROR')
			self.description = str(data.get('name','ERROR'))
			self.logo = data.get('logo','')
			self.url = 'http://' + data.get('url','') + self.urlTail
			name = forumbrowser.nameFromURL(data.get('url',''))
			self.name = name
			self.forumID = self.forumType + '.' + name
			self.category = ''
			self.categoryID = ''

	def __init__(self):
		self.client = None

	def getClient(self):
		if self.client is not None: return self.client
		self.client = xmlrpclib.ServerProxy(self.xmlrpcURL)
		return self.client

	def search(self,terms,page=1,per_page=20,p_dialog=None):
		client = self.getClient()
		try:
			result = client.search(xmlrpclib.Binary(terms))
		except:
			ERROR('ProboardsDatabaseInterface.search()')
			return []
		return self.processForums(result)

	def _get_directory(self,page,per_page,cat_id):
		return self.getClient().get_directory(page,per_page,cat_id,True,'DATE')

	def categories(self,cat_id=0,page=1,per_page=20,p_dialog=None):
		if cat_id == 0:
			return {'cats':self.getCategories()}

		data = self._get_directory(page, per_page, cat_id)
		return {'forums':self.processForums(data)}

	def _getCategories(self):
		return self.getClient().get_nested_category(1)

	def getCategories(self):
		try:
			res = self._getCategories()
			if not 'list' in res: return []
		except:
			return []
		cats = []
		for c in res.get('list',[]):
			count = c.get('public_num','?')
			cats.append({'id':c.get('category_id',-1),'name':'{0} ({1})'.format(str(c.get('category_name','ERROR')),count),'icon':c.get('icon_url',''),'bgcolor':'FF808080'})
		return cats

	def processForums(self,data):
		entries = []
		try:
			if not 'list' in data: return []
		except:
			return []
		for f in data['list']:
			entries.append(self.ForumEntry(f))
		return entries

################################################################################
# YukuDatabaseInterface
################################################################################
class YukuDatabaseInterface(ProBoardsDatabaseInterface):
	xmlrpcURL = 'http://www.yuku.com/mobiquo/directory'

	class ForumEntry(ProBoardsDatabaseInterface.ForumEntry):
		forumType = 'YK'
		urlTail = '/mobiquo/mobiquo'

	def _getCategories(self):
		return self.getClient().get_category(True)

	def _get_directory(self,page,per_page,cat_id):
		return self.getClient().get_directory(page,per_page,str(cat_id),True)

################################################################################
# ForumPost
################################################################################
class ForumPost(forumbrowser.ForumPost):
	def __init__(self,fb,pdict=None):
		forumbrowser.ForumPost.__init__(self,fb,pdict)

	def setVals(self,pdict):
		self.setPostID(pdict.get('post_id',''))
		if self.postId:
			date = str(pdict.get('post_time',''))
			if date:
				date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
				datetuple = iso8601.parse_date(date).timetuple()
				self.unixtime = time.mktime(datetuple)
				date = time.strftime('%I:%M %p - %A %B %d, %Y',datetuple)
			self.date = date
			self.userId = pdict.get('post_author_id','')
			self.userName = str(pdict.get('post_author_name') or 'UERROR')
			self.avatar = pdict.get('icon_url','')
			self.online = pdict.get('is_online',False)
			self.title = str(pdict.get('post_title',''))
			self.message = self.filterMessage(str(pdict.get('post_content',pdict.get('short_content',''))))
			self.signature = pdict.get('signature','') or self.signature #nothing
			self.setLikes(pdict.get('likes_info'))
			self._can_like = pdict.get('can_like')
			self._is_liked = pdict.get('is_liked')
			self.isShort = not pdict.get('post_content')
			self.fid = pdict.get('forum_id')
			self.tid = pdict.get('topic_id')
			self.topic = str(pdict.get('topic_title') or self.topic)
		else:
			self.isShort = True
			self.setPostID(pdict.get('msg_id',''))
			date = str(pdict.get('sent_date',''))
			if date:
				date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
				datetuple = iso8601.parse_date(date).timetuple()
				self.unixtime = time.mktime(datetuple)
				date = time.strftime('%I:%M %p - %A %B %d, %Y',datetuple)
			self.date = date
			if 'msg_from' in pdict:
				self.userName = str(pdict.get('msg_from') or 'UERROR')
			else:
				self.userName = str(str(pdict.get('msg_to',[{}])[0].get('username')) or 'UERROR')
				self.isSent = True
			self.avatar = pdict.get('icon_url','')
			self.online = pdict.get('is_online',False)
			self.title = str(pdict.get('msg_subject',''))
			self.message = str(pdict.get('short_content',''))
			self.boxid = pdict.get('boxid','')
			self._can_like = False
			self._is_liked = False
		self.processAttachements(pdict)
		self.numberImages()

	def update(self,data):
		self.setVals(data)

	def canLike(self): return self._can_like and not self._is_liked

	def canUnlike(self): return bool(self._is_liked)

	def like(self):
		if not self.canLike(): return False
		return self.FB.like(self)

	def unLike(self):
		if not self.canUnlike(): return False
		return self.FB.unLike(self)

	def setLikes(self,likes_info):
		if not likes_info:
			if 'like users' in self.extras: del self.extras['like users']
			if 'likes' in self.extras: del self.extras['likes']
			return
		users = []
		for l in likes_info:
			users.append(str(l.get('username','')))
		self.extras['like users'] = ', '.join(users)
		self.extras['likes'] = len(users)

	def processAttachements(self,pdict):
		if not 'attachments' in pdict: return
		for a in pdict['attachments']:
			if a.get('content_type') == 'image':
				self.message += '[img]{0}[/img]'.format(a.get('url'))

	def getDate(self,offset=0):
		if not self.unixtime: return self.date
		if time.daylight:
			offset -= (time.timezone - time.altzone)
		return time.strftime('%I:%M %p - %A %B %d, %Y',time.localtime(self.unixtime + offset))

	def getActivity(self,time_offset=0):
		activity = self.activity
		if not activity:
			if self.activityUnix:
				if self.online:
					activity = ''
				else:
					activity = 'Last Seen - '
			else:
				return ''
		else:
			activity += ' - '
		if not self.activityUnix: return activity
		now = time.time()
		if time.daylight:
			now += (time.timezone - time.altzone)
		#print  time.strftime('%b %d, %Y %H:%M',time.localtime(now))
		#print  time.strftime('%b %d, %Y %H:%M',time.gmtime(self.activityUnix))
		d = now - (self.activityUnix + time_offset)
		return activity + forumbrowser.durationToShortText(d) + ' ago'

	def setUserInfo(self,info):
		if not info: return
		#for k,v in info.items(): print '%s: %s' % (k,v)
		self.userInfo = info
		self.status = str(info.get('display_text',''))
		self.activity = str(info.get('current_action') or info.get('current_activity',''))
		self.online = info.get('is_online',False) or self.online
		self.postCount = info.get('post_count',0)
		date = str(info.get('reg_time',''))
		if date:
			date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
			date = time.strftime('%b %d, %Y',iso8601.parse_date(date).timetuple())
		date = str(info.get('last_activity_time',''))
		if date:
			date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
			date = time.mktime(iso8601.parse_date(date).timetuple())
		self.activityUnix = date
		for e in info.get('custom_fields_list',[]):
			name = str(e['name']).lower()
			val = str(e['value'])
			if name == 'signature':
				self.signature = val
			elif name.lower() == self.userName.lower() + '\'s signature' and not self.signature:
				self.signature = val
			else:
				if val: self.extras[name] = val

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
			if self.isPM:
				m = self.FB.server.get_message(self.getID(),self.boxid)
				self.message = str(m.get('text_body',self.message))
			else:
				self.FB.updatePost(self)
			self.isShort = False
			self.isRaw = True
			self.numberImages()
		elif raw and self.userName == self.FB.user and not self.isRaw:
			m = self.FB.server.get_raw_post(self.getID())
			self.message = str(m.get('post_content',self.message))
			self.isRaw = True
			self.numberImages()
		sig = ''
		if self.signature and not self.hideSignature: sig = '\n__________\n[COLOR FF808080]' + self.signature + '[/COLOR]'
		return makeUnicode(self.message) + makeUnicode(sig)

	def messageAsText(self):
		return messageToText(self.getMessage(True))

	def messageAsDisplay(self,short=False,raw=False,quote_wrap=80):
		if short:
			message = self.getShortMessage()
		else:
			message = self.getMessage(raw=raw)
		message = message.replace('\n','[CR]')
		#if self.isPM:
		#	return self.MC.parseCodes(message)
		#else:
		return self.MC.messageToDisplay(message,quote_wrap=quote_wrap)

	def messageAsQuote(self):
		if self.isPM:
			qp = self.FB.server.get_quote_pm(self.getID())
			return str(qp.get('text_body',''))
		else:
			qp = self.FB.server.get_quote_post(self.getID())
		#print qp.get('result_text')
			return str(qp.get('post_content',''))

	def imageURLs(self):
		return self.MC.imageFilter.findall(self.getMessage(True))

	def linkImageURLs(self):
		return re.findall('<a.+?href="(https?://.+?\.(?:jpg|jpeg|png|gif|bmp))".+?</a>',self.message)

	def linkURLs(self):
		return self.MC.linkFilter.finditer(self.getMessage(True))

	def link2URLs(self):
		if not self.MC.linkFilter2: return []
		return self.MC.linkFilter2.finditer(self.getMessage(True))

	def links(self):
		links = []
		for m in self.linkURLs(): links.append(self.FB.getPMLink(m))
		for m in self.link2URLs(): links.append(self.FB.getPMLink(m))
		return links

	def makeAvatarURL(self):
		base = self.FB.urls.get('avatar')
		if base and not self.avatar:
			self.avatar = base.replace('!USERID!',self.userId)
		return self.avatar

	def colorReplace(self,m):
		color = m.group(1)
		if color.startswith('#'):
			color = 'FF' + color[1:].upper()
		else:
			color = color.lower()
		return '[COLOR %s]' % color

	def filterMessage(self,message):
		message = message.replace('<b>','[b]').replace('</b>','[/b]').replace('<i>','[i]').replace('</i>','[/i]').replace('<u>','[u]').replace('</u>','[/u]')
		message = re.sub('<font color="([^"]+)">',self.colorReplace,message).replace('</font>','[/COLOR]') #r'[COLOR FF\1]',message)
		return convertHTMLCodes(message.replace('<br />\n','\n'))

################################################################################
# PageData
################################################################################
class PageData:
	def __init__(self,fb,data=None,current=0,per_page=20,total_items=0):
		data = data or {}
		self.fake = not bool(data)
		self.prev = current > 0
		self.current = current
		self.page = int((current + 1) / per_page) + 1
		self.perPage = per_page
		self.isReplies = data.get('total_post_num') and True or False
		self.totalitems = data.get('total_topic_num',data.get('total_post_num',total_items+1))
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
		self.searchID = None

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
				if self.fake:
					return -1
				page = self.totalPages
			else:
				page = self.totalPages
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
# ForumUser
######################################################################################
class ForumUser(forumbrowser.ForumUser):
	def __init__(self,ID,name,info):
		ID = ID or info.get('user_id','')
		name = name or str(info.get('username',''))
		forumbrowser.ForumUser.__init__(self,ID,name)
		self.avatar = info.get('icon_url','')
		self.status = str(info.get('display_text',''))
		self.activity = str(info.get('current_activity',''))
		self.online = info.get('is_online',False) or self.online
		self.postCount = info.get('post_count',0)
		date = str(info.get('reg_time',''))
		if date:
			date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
			date = time.strftime('%b %d, %Y',iso8601.parse_date(date).timetuple())
		self.joinDate = date
		date = str(info.get('last_activity_time',''))
		if date:
			date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
			date = time.strftime('%b %d, %Y %H:%M %p',iso8601.parse_date(date).timetuple())
		self.lastActivityDate = date
		extras = info.get('custom_fields_list')
		if extras:
			for e in extras:
				val = str(e['value'])
				if val: self.extras[str(e['name'])] = val

######################################################################################
# Forum Browser API for TapaTalk
######################################################################################
class TapatalkForumBrowser(forumbrowser.ForumBrowser):
	browserType = 'tapatalk'
	prefix = 'TT.'
	ForumPost = ForumPost
	PageData = PageData

	def __init__(self,forum,always_login=False,prefix='TT.'):
		self.prefix = prefix
		self.isProboards = prefix=='PB.'
		if self.isProboards:
			self.browserType = 'proboards'
		elif self.prefix == 'YK.':
			self.browserType = 'yuku'
		forumbrowser.ForumBrowser.__init__(self, forum, always_login,BBMessageConverter)
		self.forum = forum[3:]
		self._url = ''
		self.transport = None
		self.server = None
		self.forumConfig = {}
		self._siteSmilies = None
		self.needsLogin = True
		self.alwaysLogin = always_login
		self.lang = util.T
		self.loadForumFile()
		self.reloadForumData(self.forum)
		self.loginError = ''
		self.altQuoteStartFilter = '\[quote\](?P<user>[^:]+?),? \w+:( (?P<pid>\d+) said:)?'
		self.userInfoCache = {}
		self._userDataDisabled = False
		self.initialize()

	def isLoggedIn(self):
		#return self._loggedIn
		return self.transport.loggedIn()

	def loadForumFile(self):
		forum = self.getForumID()
		fname = os.path.join(util.FORUMS_PATH,forum)
		if not os.path.exists(fname):
			fname = os.path.join(util.FORUMS_STATIC_PATH,forum)
			if not os.path.exists(fname): return False
		self.loadForumData(fname)
		self._url = self.urls.get('tapatalk_server','')
		self.formats['quote'] = ''

	def reloadForumData(self,forum):
		if not self.setupClient(forum):
			self.forum = 'forum.kodi.tv'
			self.setupClient(self.forum)

	def setupClient(self,forum):
		self.needsLogin = True
		if not self._url:
			self._url = 'http://%s/mobiquo/mobiquo.php' % forum
		self.forum = forum
		self.transport = CookieTransport()
		self.transport.FB = self
		url = self._url
		#if getSetting('enable_ssl') == 'true':
		#	LOG('Enabling SSL')
		#	url = url.replace('http://','https://')
		#	self.SSL = True
		self.server = xmlrpclib.ServerProxy(url,transport=self.transport,allow_none=True)
		self.getForumConfig()
		return True

	def getForumConfig(self):
		try:
			self.forumConfig = self.server.get_config()
			self.isProboards = self.getConfigInfo('forum_software', '') == 'proboards'
			if self.isProboards:
				self.browserType = 'proboards'
			LOG('Forum Type: ' + self.getForumType())
			LOG('Forum Plugin Version: ' + self.getForumPluginVersion())
			LOG('Forum API Level: ' + self.forumConfig.get('api_level',''))
			if DEBUG:
				#LOG(self.forumConfig)
				for k,v in self.forumConfig.items():
					print '   %s: %s' % (k,v)
		except (forumbrowser.ForumMovedException, forumbrowser.ForumNotFoundException):
			raise
		except:
			ERROR('Failed to get forum config')
		encoding = self.transport.lastCharset #self.getConfigInfo('charset')
		if encoding:
			LOG('Forum Encoding: ' + encoding)
			self.updateEncoding(encoding,1,log_change=False)

	def getForumBrowserURLFromForumURL(self,url):
		if not self.getConfigInfo('get_id_by_url', False): return
		try:
			res = self.server.get_id_by_url(url)
			return util.createForumBrowserURL(self.getForumID(), forum=res.get('forum_id'), thread=res.get('topic_id'), post=res.get('post_id'))
		except:
			ERROR('FAILED')
			return ''


	def getStats(self):
		#{'total_threads': 148712, 'guest_online': 737, 'total_members': 140118, 'total_online': 1016, 'total_posts': 1390480}
		stats = self.server.get_board_stat()
		if isinstance(stats,dict) and 'total_threads' in stats:
			if not self.canGetOnlineUsers():
				del stats['total_online']
				del stats['guest_online']
			return stats
		return None

	def getSmilies(self):
		if self._siteSmilies is not None: return self._siteSmilies
		if not self.getConfigInfo('get_smilies', False): return None
		smilies = self.server.get_smilies()
		if not 'list' in smilies: return None
		url = self._url.split('mobiquo',1)[0]
		final = []
		for cat, slist in smilies['list'].items():
			for s in slist:
				final.append({'cat':cat,'url':urlparse.urljoin(url, s.get('url','')),'code':str(s.get('code','')),'title':str(s.get('title',''))})
		self._siteSmilies = final
		return self._siteSmilies

	def getConfigInfo(self,key,default=None):
		val = self.forumConfig.get(key)
		if val == None: return default
		if isinstance(default,bool):
			return val == '1'
		elif isinstance(default,int):
			try:
				return int(val)
			except:
				return default
		return str(self.forumConfig.get(key)) or default

	def apiOK(self,target):
		try:
			apiLevel = int(self.forumConfig.get('api_level',''))
		except:
			return False
		return apiLevel >= target

	def getForumInfo(self):
		return [	('name',self.getDisplayName()),
					('interface','Tapatalk'),
					('tapatalk_api_level',self.forumConfig.get('api_level','')),
					('tapatalk_plugin_version',self.getForumPluginVersion()),
					('forum_type',self.getForumTypeName() + ' v' + self.forumConfig.get('sys_version','')),
					('login_set',self.canLogin())
				]

	def getForumTypeName(self):
		return self.forumTypeNames.get(self.getForumType(),'Unknown')

	def guestOK(self):
		return self.forumConfig.get('guest_okay',True)

	def getForumType(self):
		return self.forumConfig.get('version','')[:2]

	def getForumPluginVersion(self):
		ver = self.forumConfig.get('version','').split('_')[-1]
		if not ver and self.isProboards: return 'proboards'
		return ver

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
			self.forumConfig.update(result)
			if DEBUG:
				LOG('LOGGED IN: ' + str(result.get('result_text','')))
			else:
				LOG ('LOGGED IN')
			self.loginError = ''
			self._loggedIn = True
			return True
		return False

	def checkLogin(self,callback=None,callback_percent=5):
		if self.loginError: return False
		if not self.user or not self.password: return False
		if not callback: callback = self.fakeCallback
		if self.needsLogin or not self.isLoggedIn():
			self.needsLogin = False
			if not callback(callback_percent,self.lang(32100)): return False
			if not self.login():
				return False
		return True

	def getPMBoxes(self,update=True,callback_percent=5):
		if not update and self.pmBoxes: return self.pmBoxes
		if not self.hasPM() and not self.hasConversation(): return None
		if not self.checkLogin(callback_percent=callback_percent): return None
		try:
			if self.getConfigInfo('conversation', False):
				result = self.server.get_conversations()
			else:
				result = self.server.get_box_info()
		except xmlrpclib.Fault,e:
			LOG("Failed to get_box_info() (XMLRPCLib Fault): {0}".format(e))
			return None
		if not result.get('result'):
			LOG('Failed to get PM boxes: ' + str(result.get('result_text')))
			return None
		self.pmBoxes = []
		defaultSet = False
		defType = "?"
		if self.getConfigInfo('conversation', False): defType = 'conversation'
		for b in result.get('list',[]):
			box = {	'id':b.get('box_id',b.get('conv_id','')),
					'name':str(b.get('box_name',str(b.get('conv_subject','?')))),
					'count':b.get('msg_count',0),
					'conv_count':b.get('reply_count',0),
					'unread':b.get('unread_count',b.get('new_post',False) and 1 or 0),
					'conv_unread':b.get('unread_count',0),
					'type':b.get('box_type','') or str(b.get('box_name',defType)).upper()
			}
			if self.getConfigInfo('conversation', False): box['count'] = 1
			if box.get('type') == 'INBOX' and not defaultSet:
				box['default'] = True
				defaultSet = True
			self.pmBoxes.append(box)
		if not defaultSet and self.pmBoxes: self.pmBoxes[0]['default'] = True
		return self.pmBoxes

	def getPMCounts(self,callback_percent=5):
# 		if self.getConfigInfo('conversation', False):
# 			LOG("Skipping PM counts - forum uses conversation PMs")
# 			return None
		boxes = self.getPMBoxes(callback_percent=callback_percent)
		if not boxes: return None
		unread = 0
		total = 0
		boxid = None
		for l in boxes:
			if l.get('type') in ('INBOX','CONVERSATION'):
				if l.get('default'): boxid = l.get('id')
				total += l.get('count',0)
				unread += l.get('unread',0)
		return {'unread':unread,'total':total,'boxid':boxid}

	def makeURL(self,url):
		#LOG('AVATAR: ' + url)
		return url

	def createForumDict(self,data,sub=False):
		data['forumid'] = data.get('forum_id')
		data['title'] = self.unicode(str(data.get('forum_name')))
		data['description'] = self.unicode(str(data.get('description','')))
		data['subscribed'] = data.get('is_subscribed',False)
		data['subforum'] = sub
		return data

	def getForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		#if not self.guestOK():
		self.checkLogin(callback, 5)
		logo = None
		while True:
			if not callback(20,self.lang(32102)): break

			try:
				if self.apiOK(4):
					try:
						flist = self.server.get_forum(True)
					except xmlrpclib.Fault:
						LOG('WARNING: API 4 reported but get_forum() failed with level 4 params')
						flist = self.server.get_forum()
				else:
					flist = self.server.get_forum()
			except:
				em = ERROR('ERROR GETTING FORUMS')
				#callback(-1,'%s' % em)
				return self.finish(FBData(error=em),donecallback)
			if 'result_text' in flist:
				em = unicode(str(flist.get('result_text')),'utf-8')
				#callback(-1,'%s' % em)
				return self.finish(FBData(error=em),donecallback)
			if not callback(40,self.lang(32103)): break
			forums = []
			for general in flist:
				if not general.get('sub_only'): forums.append(self.createForumDict(general))
				for forum in general.get('child',[]):
					if not forum.get('sub_only'): forums.append(self.createForumDict(forum))
					for sub in forum.get('child',[]):
						if not sub.get('sub_only'): forums.append(self.createForumDict(sub,True))
			if not callback(80,self.lang(32231)): break
			logo = self.urls.get('logo') or 'http://%s/favicon.ico' % self.domain()
			try:
				pm_counts = self.getPMCounts(80)
			except:
				ERROR('Failed to get PM Counts')
				pm_counts = None
			try:
				if not callback(80,self.lang(32545)): break
				stats = self.getStats()
			except:
				ERROR('Failed to get Forum stats')
				stats = None

			callback(100,self.lang(32052))

			return self.finish(FBData(forums,extra={'logo':logo,'pm_counts':pm_counts,'stats':stats}),donecallback)

		return self.finish(FBData(extra={'logo':logo},error='CANCEL'),donecallback)

	def getSubscribedForums(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		while True:
			if not callback(20,self.lang(32102)): break
			try:
				flist = self.server.get_subscribed_forum()
			except:
				em = ERROR('ERROR GETTING FORUM SUBSCRIPTIONS')
				#callback(-1,'%s' % em)
				return self.finish(FBData(error=em),donecallback)

			if not callback(40,self.lang(32103)): break
			forums = []
			for f in flist.get('forums',[]):
				f = self.createForumDict(f)
				f['subscribed'] = True
				forums.append(f)
			if not callback(80,self.lang(32231)): break

			return self.finish(FBData(forums),donecallback)

		return self.finish(FBData(error='CANCEL'),donecallback)

	def isForumSubscribed(self,fid,default=False):
		if default: return True
		if not self.isLoggedIn(): return False
		forums = self.getSubscribedForums(None, None)
		if not forums.data: return False
		for f in forums.data:
			if f.get('forumid') == fid: return True
		return False

	def isThreadSubscribed(self,tid,default=False):
		if default: return True
		if not self.isLoggedIn(): return False
		threads,pd = self._getSubscriptions() #@UnusedVariable
		for t in threads:
			if t.get('threadid') == tid: return True
		return False

	def createThreadDict(self,data,sticky=False):
		#for k,v in data.items(): print '%s: %s' % (k,v)
		#print '--------------------------'
		data['threadid'] = data.get('topic_id','')
		data['starter'] = self.unicode(str(data.get('topic_author_name',data.get('post_author_name',self.user))))
		data['title'] = self.unicode(str(data.get('topic_title','')))
		data['short_content'] = self.unicode(str(data.get('short_content','')))
		data['subscribed'] = data.get('is_subscribed',False)
		data['lastposter'] = self.unicode(str(data.get('last_reply_user') or data.get('last_reply_author_name','')))
		#data['forumid'] =
		data['sticky'] = sticky
		date = data.get('last_reply_time')
		if date:
			try:
				date = str(date)
				date = date[0:4] + '-' + date[4:6] + '-' + date[6:]
				now = datetime.datetime.now()
				yesterday = datetime.datetime.now() - datetime.timedelta(days=1)
				dateDT = iso8601.parse_date(date)
				if now.day == dateDT.day and now.month == dateDT.month and now.year == dateDT.year:
					date = dateDT.strftime('Today - %I:%M %p')
				elif yesterday.day == dateDT.day and yesterday.month == dateDT.month and yesterday.year == dateDT.year:
					date = dateDT.strftime('Yesterday - %I:%M %p')
				else:
					date = dateDT.strftime('%I:%M %p - %A %B %d, %Y')
				data['last_reply_time'] = date
			except:
				data['last_reply_time'] = 'ERROR'
		return data

	def _getThreads(self,forumid,topic_num,callback,donecallback):
		if not callback: callback = self.fakeCallback
		while True:
			if topic_num == 0:
				if not callback(10,self.lang(32102)): break
				announces = self.server.get_topic(forumid,0,49,'ANN').get('topics',[])
				if not callback(30,self.lang(32103)): break
				for a in announces: self.createThreadDict(a,True)
				if not callback(40,self.lang(32102)): break
				stickys = self.server.get_topic(forumid,0,49,'TOP').get('topics',[])
				if not callback(50,self.lang(32103)): break
				for s in stickys: self.createThreadDict(s,True)
			else:
				announces = stickys = []
			if not callback(60,self.lang(32102)): break
			topics = self.server.get_topic(forumid,topic_num,int(topic_num) + 19)
			if not callback(90,self.lang(32103)): break
			pd = self.getPageData(topics,topic_num)
			normal = topics.get('topics',[])
			for n in normal: self.createThreadDict(n)
			return announces + stickys + normal, pd

		if donecallback:
			donecallback(None,None)
		return (None,None)

	def _getSubscriptions(self,callback=None,donecallback=None):
		if not callback: callback = self.fakeCallback
		callback(20,self.lang(32102))
		sub = self.server.get_subscribed_topic()
		pd = self.getPageData({},0)
		#if not sub.get('result'):
		#	raise Exception(sub.get('result_text'))
		normal = sub.get('topics',[])
		if not callback(70,self.lang(32103)):
			if donecallback: donecallback(None,None)
			return (None,None)
		for n in normal: self.createThreadDict(n)
		normal = self.sortDictList(normal, 'post_time')
		return normal, pd

	def getUnreadThreads(self,page=0,sid='',callback=None,donecallback=None,page_data=None):
		if page_data.searchID: sid = page_data.searchID
		if not callback: callback = self.fakeCallback
		while True:
			result = self.server.get_unread_topic(page,int(page) + 19,sid)
			if not result.get('result'):
				err = str(result.get('result_text',''))
				LOG('Unread Threads: %s' % err)
				return self.finish(FBData(error=err),donecallback)
			if not callback(90,self.lang(32103)): break
			pd = self.getPageData(result,page)
			pd.searchID = result.get('search_id')
			threads = result.get('topics',[])
			for n in threads: self.createThreadDict(n)
			return self.finish(FBData(threads,pd),donecallback)

		if donecallback:
			donecallback(None,None)
		return (None,None)

	def searchThreads(self,terms,page=0,sid='',callback=None,donecallback=None,page_data=None):
		if page_data.searchID: sid = page_data.searchID
		if len(terms)  < self.getConfigInfo('min_search_length',3):
			return self.finish(FBData(error='Search string must be at least %s characters in length.' % self.getConfigInfo('min_search_length',3)),donecallback)
		if not callback: callback = self.fakeCallback
		while True:
			result = self.server.search_topic(xmlrpclib.Binary(terms),page,int(page) + 19,sid)
			if not result.get('result'):
				err = str(result.get('result_text',''))
				LOG('Search: %s' % err)
				return self.finish(FBData(error=err),donecallback)
			if not callback(90,self.lang(32103)): break
			pd = self.getPageData(result,page)
			pd.searchID = result.get('search_id')
			threads = result.get('topics',[])
			for n in threads: self.createThreadDict(n)
			return self.finish(FBData(threads,pd),donecallback)

		if donecallback:
			donecallback(None,None)
		return (None,None)

	def searchAdvanced(self,terms,page=0,sid='',callback=None,donecallback=None,page_data=None,fid=None,tid=None,uid=None,uname=None):
		if len(terms)  < self.getConfigInfo('min_search_length',3):
			return self.finish(FBData(error='Search string must be at least %s characters in length.' % self.getConfigInfo('min_search_length',3)),donecallback)
		if not callback: callback = self.fakeCallback
		sfilter = {}
		if fid:
			sfilter['forumid'] = fid
		elif tid:
			sfilter['threadid'] = tid
		if uid:
			sfilter['userid'] = uid
			sfilter['showposts'] = 1
		elif uname:
			sfilter['searchuser'] = uname
			sfilter['showposts'] = 1

		sfilter['keywords'] = xmlrpclib.Binary(terms)
		page = int(page or 0)
		sfilter['page'] = page
		sfilter['perpage'] = page + 19

		while True:
			result = self.server.search(sfilter)
			if not result.get('result'):
				err = str(result.get('result_text',''))
				LOG('Search: %s' % err)
				return self.finish(FBData(error=err),donecallback)
			pd = self.getPageData(result,page)
			pd.searchID = result.get('search_id')
			if not callback(90,self.lang(32103)): break
			if fid:
				normal = result.get('topics',[])
				for n in normal: self.createThreadDict(n)
				return self.finish(FBData(normal,pd),donecallback)
			else:
				replies = self.processThread(result, page, callback, donecallback)
				return self.finish(FBData(replies,pd),donecallback)

		if donecallback:
			donecallback(None,None)
		return (None,None)

	def getUserThreads(self,uname=None,page=None,uid=None,callback=None,donecallback=None,page_data=None):
		result = None
		if self.apiOK(4):
			if not uid: uid = self.getUserInfo(uid, uname).ID
			if uid: result = self.server.get_user_topic(xmlrpclib.Binary(''),uid)
		if not result: result = self.server.get_user_topic(xmlrpclib.Binary(uname))
		if 'result' in result and not result['result']:
			error = str(result.get('result_text'))
			LOG('Failed to get user threads: %s' % error)
			return self.finish(FBData(error=error),donecallback)
		for n in result: self.createThreadDict(n)
		pd = page_data or PageData(self)
		return self.finish(FBData(result,pd),donecallback)

	def getUserPosts(self,uname=None,page=None,uid=None,callback=None,donecallback=None,page_data=None):
		result = self.server.get_user_reply_post(xmlrpclib.Binary(uname))
		if 'result' in result and not result['result']:
			error = str(result.get('result_text'))
			LOG('Failed to get user posts: %s' % error)
			return self.finish(FBData(error=error),donecallback)
		replies = self.processThread({'posts':result}, 0, callback, donecallback)
		pd = page_data or PageData(self)
		return self.finish(FBData(replies,pd),donecallback)

	def getThreads(self,forumid,page=0,callback=None,donecallback=None,page_data=None):
		if not callback: callback = self.fakeCallback
		try:
			if forumid:
				threads,pd = self._getThreads(forumid,page or 0,callback,donecallback)
			else:
				threads,pd = self._getSubscriptions(callback,donecallback)
		except:
			em = ERROR('ERROR GETTING THREADS')
			#callback(-1,'%s' % em)
			return self.finish(FBData(error=em))

		callback(100,self.lang(32052))
		return self.finish(FBData(threads,pd),donecallback)

	def canGetUserPosts(self): return 50
	def canGetUserThreads(self): return 50

	def canGetUnreadThreads(self): return True

	def canSearch(self): return self.getConfigInfo('guest_search', True) or self.isLoggedIn()
	def canSearchPosts(self): return self.canSearch()
	def canSearchThreads(self): return self.canSearch() and not self.isProboards
	def canSearchAdvanced(self,stype=None): return self.canSearch() and self.getConfigInfo('advanced_search', False)

	def searchReplies(self,terms,page=0,sid='',callback=None,donecallback=None,page_data=None):
		if len(terms)  < self.getConfigInfo('min_search_length',3):
			return self.finish(FBData(error='Search string must be at least %s characters in length.' % self.getConfigInfo('min_search_length',3)),donecallback)
		return self.getReplies(terms, None, page=page, lastid=sid, callback=callback, donecallback=donecallback, page_data=page_data,search=True)

	def get_thread(self,threadid,start,end,return_html=True):
		if self.apiOK(4):
			return self.server.get_thread(threadid,start,end,return_html)
		else:
			return self.server.get_thread(threadid,start,end)

	def getReplies(self,threadid,forumid,page=0,lastid='',pid='',callback=None,donecallback=None,page_data=None,search=False):
		if not callback: callback = self.fakeCallback
		while True:
			try:
				page = int(page)
			except:
				page = 0
			if not callback(20,self.lang(32102)): break
			try:
				if pid:
					test = self.server.get_thread_by_post(pid,20)
					if test.get('position'):
						index = test.get('position')
						start = int((index - 1) / 20) * 20
						page = start
						thread = self.get_thread(threadid,start,start + 19,True)
					else:
						LOG('COULD NOT GET THREAD BY POST ID')
						pid = ''
						page = -1
				if search:
					if page_data and page_data.searchID: lastid = page_data.searchID
					thread = self.server.search_post(xmlrpclib.Binary(threadid),page,page + 19,lastid)
					if not thread.get('result'):
						err = str(thread.get('result_text',''))
						LOG('Search: %s' % err)
						return self.finish(FBData(error=err),donecallback)
				elif not pid:
					thread = None
					if page < 0:
						test = self.get_thread(threadid,0,19,True)
						page = self.getPageData(test,0).getPageNumber(-1)
						if page == 0: thread = test
					if not thread: thread = self.get_thread(threadid,page,page + 19,True)

				sreplies = self.processThread(thread,page,callback,donecallback)
				if not sreplies: break

			except xmlrpclib.Fault, e:
				LOG('ERROR GETTING POSTS: ' + e.faultString)
				raise forumbrowser.Error(e.faultString)
			except:
				em = ERROR('ERROR GETTING POSTS')
				#callback(-1,em)
				return self.finish(FBData(error=em),donecallback)

			if not callback(95,self.lang(32103)): break
			pd = self.getPageData(thread,page or 0)
			pd.searchID = thread.get('search_id')
			if not search: pd.tid = threadid
#Tried this for XBMCHub on 02-14-13 but didn't help
#			if self.apiOK(4) and str(self.forumConfig.get('mark_topic_read')) == '1':
#				try:
#					LOG('Marking topic as read: %s' % threadid)
#					self.server.mark_topic_read([threadid])
#				except:
#					ERROR('Failed to mark topic as read')
			callback(100,self.lang(32052))
			return self.finish(FBData(sreplies,pd),donecallback)

		return self.finish(FBData(error='CANCEL'),donecallback)

	def processThread(self,thread,page,callback,donecallback):
		sreplies = []
		posts = thread.get('posts')
		if not posts:
			#callback(-1,'NO POSTS')
			return self.finish(FBData(error='NO POSTS'),donecallback)
		if not callback(60,self.lang(32103)): return None
		ct = page + 1
		pct_ct = 1
		tot = len(posts)
		for p in posts:
			fp = self.getForumPost(p)
			fp.postNumber = ct
			fp.setUserInfo(self.getUserData(fp.userName))
			sreplies.append(fp)
			if not self.updateProgress(callback, 60, 35, pct_ct, tot, self.lang(32103)): break
			ct+=1
			pct_ct +=1
		return sreplies

	def hasPM(self):
		if self.getConfigInfo('conversation', False): return False
		return not self.forumConfig.get('disable_pm','0') == '1'

	def hasConversation(self):
		return self.getConfigInfo('conversation', False)

	def getPrivateMessages(self,callback=None,donecallback=None,boxid=None):
		if not callback: callback = self.fakeCallback

		while True:
			if not callback(20,self.lang(32102)): break
			if not boxid:
				try:
					pmInfo = self.getPMCounts(20)
				except:
					em = ERROR('ERROR GETTING PRIVATE MESSAGES - getPMCounts()')
					#callback(-1,'%s' % em)
					return self.finish(FBData(error=em),donecallback)
				if not pmInfo: break
				boxid = pmInfo.get('boxid')
			if not boxid: break
			if not callback(50,self.lang(32102)): break
			try:
				messages = self.server.get_box(boxid,0,49)
			except:
				em = ERROR('ERROR GETTING PRIVATE MESSAGES')
				#callback(-1,'%s' % em)
				return self.finish(FBData(error=em),donecallback)
			pms = []
			if not callback(80,self.lang(32103)): break
			infos = {}
			for p in messages.get('list',[]):
				p['boxid'] = boxid
				fp = self.getForumPost(p)
				fp.online = False #Because at least on sent items, we can't trust this value returned with the list
				if not fp.userName in infos:
					try:
						info = self.server.get_user_info(xmlrpclib.Binary(fp.userName))
						if info.get('is_online'): info['is_online'] = bool(info.get('current_activity'))
						infos[fp.userName] = info
					except:
						infos[fp.userName] = {}
						LOG('Failed to get user info for: %s' % fp.userName)
						if DEBUG: ERROR('ERROR:')
						break
				fp.setUserInfo(infos.get(fp.userName))
				fp.isPM = True
				pms.append(fp)

			callback(100,self.lang(32052))
			return self.finish(FBData(pms),donecallback)

		return self.finish(FBData(error='CANCEL'),donecallback)

	def hasSubscriptions(self):
		return True

	def hasForumSubscriptions(self):
		return True

	def getSubscriptions(self,page='',callback=None,donecallback=None,page_data=None):
		if not self.checkLogin(callback=callback): return self.finish(FBData(error='LOGIN FAILED'),donecallback)
		threads = self.getThreads(None, page, callback, None)
		if self.hasForumSubscriptions():
			forums = self.getSubscribedForums(callback, None)
			threads['forums'] = forums.data
			return self.finish(threads,donecallback)
		else:
			return self.finish(FBData(threads.data,threads.pageData),donecallback)

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
		callback(40,self.lang(32106))
		fid = post.fid
		if fid == 'subscriptions': fid = ''
		result = self.server.reply_post(fid or '',post.tid or '',xmlrpclib.Binary(post.title),xmlrpclib.Binary(post.message))
		callback(100,self.lang(32052))
		status = result.get('result',False)
		if not status:
			post.error = str(result.get('result_text'))
			LOG('Failed To Post: ' + post.error)
		post.pid = result.get('post_id',post.pid)
		return status

	def getPostForEdit(self,post):
		pid = post.postId
		result = self.server.get_raw_post(pid)
		if not result:
			LOG('Could not get raw post for editing')
			return None
		pm = forumbrowser.PostMessage(pid,isEdit=True)
		pm.setMessage(str(result.get('post_title','')),str(result.get('post_content','')))
		return pm

	def checkMyBBEditFix(self,pm):
		if self.getForumType() == 'mb' and checkVersion('2.0.0',self.getForumPluginVersion()) > -1:
			if getSetting('do_mybb_edit_bug_fix'):
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
			self.subscribeThread(pm.tid)
		return result.get('result',False)

	def canEditPost(self,user):
		if user == self.user: return True
		return False

	def doPrivateMessage(self,post,callback=None):
#		user_name 		yes 	To support sending message to multiple recipients, the app constructs an array and insert user_name for each recipient as an element inside the array. 	3
#		subject 	byte[] 	yes 		3
#		text_body 	byte[] 	yes 		3
#		action 	Int 		1 = REPLY to a message; 2 = FORWARD to a message. If this field is presented, the pm_id below also need to be provided. 	3
#		pm_id 	String 		It is used in conjunction with "action" parameter to indicate which PM is being replied or forwarded to.
		toArray = []
		for t in post.to.split(','): toArray.append(xmlrpclib.Binary(t))
		result = self.server.create_message(toArray,xmlrpclib.Binary(post.title),xmlrpclib.Binary(post.message))
		callback(100,self.lang(32052))
		if not result.get('result'):
			LOG('Failed to send PM: ' + str(result.get('result_text')))
			post.error = str(result.get('result_text'))
			return False
		return True

	def deletePrivateMessage(self,post,callback=None):
		boxid = post.boxid
		if not boxid:
			pmInfo = self.getPMCounts()
			boxid = pmInfo.get('boxid')
		if not boxid: return
		result = self.server.delete_message(post.pid,boxid)
		if not result.get('result'):
			post.error = str(result.get('result_text'))
			LOG('Failed to delete PM:' + post.error)
			return False
		return True

	def deletePost(self,post):
		if not self.checkLogin(): return False
		soft_hard = int(self.forumConfig.get('soft_delete','2'))
		result = self.server.m_delete_post(post.pid,soft_hard,xmlrpclib.Binary('Not Given'))
		if not result.get('result'):
			post.error = str(result.get('result_text'))
			LOG('Failed to delete post: %s (%s)' % (post.error,soft_hard == 1 and 'Soft' or 'Hard'))
			return False
		return True

	def canPost(self): return self.isLoggedIn()

	def canDelete(self,user,target='POST'):
		if self.isLoggedIn():
			if target == 'PM': return True
			if self.forumConfig.get('can_moderate'): return True
		return False

	def updatePost(self,post):
		thread = self.server.get_thread_by_post(post.pid,1)
		if not thread.get('position'):
			LOG('COULD NOT GET THREAD BY POST ID')
			return False
		posts = thread.get('posts')
		if not posts:
			LOG('FAILED TO UPDATE POST - NO POSTS')
			return False
		for p in posts:
			if p.get('post_id') == post.pid:
				post.update(p)
				return True
		LOG('FAILED TO UPDATE POST - NOT FOUND')
		return False

	def like(self,post):
		result = self.server.like_post(post.pid)
		if result.get('result'):
			self.updatePost(post)
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to like post: ' + text)
			return text

	def unLike(self,post):
		result = self.server.unlike_post(post.pid)
		if result.get('result'):
			self.updatePost(post)
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to unlike post: ' + text)
			return text

	def canSubscribeThread(self,tid): return self.isLoggedIn()
	def canSubscribeForum(self,fid): return self.isLoggedIn()
	def canUnSubscribeThread(self,tid): return self.isLoggedIn()
	def canUnSubscribeForum(self,fid): return self.isLoggedIn()

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

	def canCreateThread(self, fid): return self.isLoggedIn()

	def createThread(self,fid,title,message):
		result = self.server.new_topic(fid,xmlrpclib.Binary(title),xmlrpclib.Binary(message))
		if result.get('result'):
			return True
		else:
			text = result.get('result_text')
			LOG('Failed to create thread: ' + str(text))
			return text

	def canGetOnlineUsers(self): return self.getConfigInfo('get_online_users', True)

	def getOnlineUsers(self):
		result = self.server.get_online_users()
		if 'list' in result:
			ret = []
			dups = []
			for u in result.get('list',[]):
				name = str(u.get('user_name',''))
				if not name in dups: #because at least in MyBB v2 the list returns name duplicates with user ids of offline users
					ret.append({'user':name,'userid':u.get('user_id',''),'avatar':u.get('icon_url',''),'status':str(u.get('display_text',''))})
					dups.append(name)
			return ret
		else:
			text = str(result.get('result_text'))
			LOG('Failed to get online users: ' + text)
			return text

	def canGetUserInfo(self): return True

	def getUserInfo(self,uid=None,uname=None):
		result = self.server.get_user_info(xmlrpclib.Binary(uname))
		if not result.get('result_text'):
			return ForumUser(uid,uname,result)
		else:
			text = result.get('result_text')
			LOG('Failed to user info: ' + str(text))
			return None

	def getUserData(self,username):
		if self._userDataDisabled: return {}
		if username in self.userInfoCache:
			self.userInfoCache[username][0] = time.time()
			return self.userInfoCache[username][1]
		try:
			self.userInfoCache[username] = [time.time(),self.server.get_user_info(xmlrpclib.Binary(username))]
		except xmlrpclib.Fault,e:
			if 'login' in e.faultString: self._userDataDisabled = True
			self.userInfoCache[username] = [time.time(),{}]
			LOG('Failed to get user info for: %s' % username)
			if DEBUG: ERROR('ERROR:')
		except:
			self.userInfoCache[username] = [time.time(),{}]
			LOG('Failed to get user info for: %s' % username)
			if DEBUG: ERROR('ERROR:')
		if len(self.userInfoCache) > 110: #clear 10 out of the cache, putting it back to 100
			#LOG('LIMITING USER INFO CACHE')
			keys = self.userInfoCache.keys()
			keys.sort(key=lambda k: self.userInfoCache[k][0])
			for i in range(0,11): del self.userInfoCache[keys[i]]
		return self.userInfoCache[username][1]
