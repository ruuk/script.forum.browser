# -*- coding: utf-8 -*-
import os, time, urllib, urlparse, xbmc, xbmcgui
from lib import util
import forumbrowser
import requests2 as requests
import texttransform
import iso8601

def LOG(msg):
	util.LOG('YouTube: %s' % msg)
	
def ERROR(msg,hide_tb=False):
	util.ERROR('YouTube: %s' % msg,hide_tb=hide_tb)
	
def authorize(settings):
	try:
		api = YouTubeAPI()
		success = api.authorize()
	except:
		ERROR('Failed to authorize user')
		return False
	if success:
		LOG('User authorized')
	else:
		LOG('Not authorized: No Error')
	return False
	
def authorized():
	return bool(util.getSetting('youtube_access_token'))

def deepDictVal(adict,keys):
	if not adict: return ''
	for key in keys:
		if key in adict:
			adict = adict[key]
		else:
			return ''
	return adict

def getTVal(cdict,key):
	return (cdict.get(key) or {}).get('$t','')
		
class YouTubeAPISection:
	key = 'AIzaSyCdPQr0OBjSUdLqWoP29Z7oGp2NnBh5gNI'
	def __init__(self,api,base_url):
		self.api = api
		self.session = api.session
		self.baseURL = api.baseURL + base_url
		
	def list(self, **kwargs):
		params = kwargs
		
		if self.api.authorized():
			headers = {'Authorization': 'Bearer ' + self.api.getToken()}
			req = self.session.get(self.baseURL,params=params,headers=headers)
		else:
			params['key'] = self.key
			req = self.session.get(self.baseURL,params=params)
		return req.json()

class YouTubeAPI:
	clientID = '626473115622-i9l4ujmcdcn91cpqgq27imqt0l5e4muj.apps.googleusercontent.com'
	clientS = 'Epukfa1a5ObgsJjxwUG6veuY'
	baseURL = 'https://www.googleapis.com/youtube/v3/'
	auth1URL = 'https://accounts.google.com/o/oauth2/device/code'
	auth2URL = 'https://accounts.google.com/o/oauth2/token'
	authScope = 'https://www.googleapis.com/auth/youtube'
	grantType = 'http://oauth.net/grant_type/device/1.0'
	
	def __init__(self):
		self.session = requests.Session()
		self.GuideCategories = YouTubeAPISection(self, 'guideCategories')
		self.Search = YouTubeAPISection(self, 'search')
		self.Channels = YouTubeAPISection(self, 'channels')
		self.Playlists = YouTubeAPISection(self, 'playlists')
		self.PlaylistItems = YouTubeAPISection(self, 'playlistItems')
		self.Videos = YouTubeAPISection(self, 'videos')
		self.Subscriptions = YouTubeAPISection(self, 'subscriptions')
		self.authPollInterval = 5
		self.authExpires = int(time.time())
		self.deviceCode = ''
		self.verificationURL = 'http://www.google.com/device'
		self.loadToken()
		
	def loadToken(self):
		self.token = util.getSetting('youtube_access_token')
		self.tokenExpires = util.getSetting('youtube_expiration',0)
		if self.authorized(): LOG('AUTHORIZED')

	def getToken(self):
		if self.tokenExpires <= int(time.time()):
			return self.updateToken()
		return self.token
		
	def updateToken(self):
		LOG('REFRESHING TOKEN')
		data = {	'client_id':self.clientID,
					'client_secret':self.clientS,
					'refresh_token':util.getSetting('youtube_refresh_token'),
					'grant_type':'refresh_token'}
		json = self.session.post(self.auth2URL,data=data).json()
		if 'access_token' in json:
			self.saveData(json)
		else:
			LOG('Failed to update token')
		return self.token
		
#	client_id=21302922996.apps.googleusercontent.com&
#	client_secret=XTHhXh1SlUNgvyWGwDk1EjXB&
#	refresh_token=1/6BMfW9j53gdGImsixUH6kU5RsR4zwI9lUVX-tqf8JXQ&
#	grant_type=refresh_token
#	The authorization server returns a JSON object that contains a new access token:
#	
#	{
#	  "access_token":"1/fFAGRNJru1FTz70BzhT3Zg",
#	  "expires_in":3920,
#	  "token_type":"Bearer"
#	}
	
	def authorized(self):
		return bool(self.token)
		
	def Comments(self,video_id,url=None):
		url = url or 'https://gdata.youtube.com/feeds/api/videos/{0}/comments?orderby=published&alt=json'.format(video_id)
		req = self.session.get(url)
		try:
			return req.json()
		except:
			ERROR('Failed to get comments: {0}'.format(video_id),hide_tb=True)
			LOG(repr(req.text[:100]))
			return None
		
	def User(self,userID):
		if userID == 'UC__NO_YOUTUBE_ACCOUNT__': return None
		url = 'http://gdata.youtube.com/feeds/api/users/{0}?alt=json'.format(userID)
		req = self.session.get(url)
		try:
			return req.json().get('entry')
		except:
			ERROR('api.User() - json failed for ID: {0}'.format(userID),hide_tb=True)
			return None
			
	def Video(self,videoID):
		try:
			url = 'http://gdata.youtube.com/feeds/api/videos/{0}?alt=json'.format(videoID)
			req = self.session.get(url)
		except:
			ERROR('api.Video() - get failed for ID: {0}'.format(videoID),hide_tb=True)
			return None
		try:
			return req.json().get('entry')
		except:
			if req.text == 'Private video': return None
			ERROR('api.Video() - json failed for ID: {0}'.format(videoID),hide_tb=True)
			return None
		
	def authorize(self):
		userCode = self.getDeviceUserCode()
		if not userCode: return
		self.showUserCode(userCode)
		d = xbmcgui.DialogProgress()
		d.create('Waiting','Waiting for auth...')
		ct=0
		while True:
			d.update(ct,'Waiting for auth...')
			json = self.pollAuthServer()
			if 'access_token' in json: break
			if d.iscanceled(): return
			for x in range(0,self.authPollInterval):
				xbmc.sleep(1000)
				if d.iscanceled(): return
			ct+=1
		return self.saveData(json)
		
	def saveData(self,json):
		self.token = json.get('access_token','')
		refreshToken = json.get('refresh_token')
		self.tokenExpires = json.get('expires_in',3600) + int(time.time())
		util.setSetting('youtube_access_token',self.token)
		if refreshToken: util.setSetting('youtube_refresh_token',refreshToken)
		util.setSetting('youtube_expiration',self.tokenExpires)
		return self.token and refreshToken
		
	def pollAuthServer(self):
		json = self.session.post(self.auth2URL,data={	'client_id':self.clientID,
															'client_secret':self.clientS,
															'code':self.deviceCode,
															'grant_type':self.grantType
														}).json()
		if 'error' in json:
			if json['error'] == 'slow_down':
				self.authPollInterval += 1
		return json
#		{
#		  "access_token":"1/fFAGRNJru1FTz70BzhT3Zg",
#		  "expires_in":3920,
#		  "token_type":"Bearer",
#		  "refresh_token":"1/6BMfW9j53gdGImsixUH6kU5RsR4zwI9lUVX-tqf8JXQ"
#		}

	def showUserCode(self,user_code):
		xbmcgui.Dialog().ok('Authorization','Go to: ' + self.verificationURL,'Enter code: ' + user_code,'Click OK when done.')
		
	def getDeviceUserCode(self):
		json = self.session.post(self.auth1URL,data={'client_id':self.clientID,'scope':self.authScope}).json()
#		{
#		  "device_code" : "4/L9fTtLrhY96442SEuf1Rl3KLFg3y",
#		  "user_code" : "a9xfwk9c",
#		  "verification_url" : "http://www.google.com/device",
#		  "expires_in" : "1800"
#		  "interval" : 5,
#		}
		self.authPollInterval = json.get('interval',5)
		self.authExpires = json.get('expires_in',1800) + int(time.time())
		self.deviceCode = json.get('device_code','')
		self.verificationURL = json.get('verification_url',self.verificationURL)
		if 'error' in json:
			LOG('ERROR - YouTube getDeviceUserCode(): ' + json.get('error_description',''))
		return json.get('user_code','')
		
	def postComment(self,videoID,comment):
		infoURL = 'https://gdata.youtube.com/feeds/api/videos/%s?v=2&alt=json' % videoID
		json = self.session.get(infoURL).json()
		postURL = deepDictVal(json,('entry','gd$comments','gd$feedLink','href'))
		headers = {	'Content-Type': 'application/atom+xml',
						'Authorization': 'Bearer ' + self.getToken(),
						'GData-Version':'2',
						'X-GData-Key': 'key=' + 'AIzaSyCdPQr0OBjSUdLqWoP29Z7oGp2NnBh5gNI'
		}
		
		data = '''<?xml version="1.0" encoding="UTF-8"?>
		<entry xmlns="http://www.w3.org/2005/Atom"
		    xmlns:yt="http://gdata.youtube.com/schemas/2007">
		  <content>{0}</content>
		</entry>'''.format(comment)
		req = self.session.post(postURL,headers=headers,data=data)
		return self.responseOK(req)
		
	def deleteComment(self,commentURL):
		headers = {	'Content-Type': 'application/atom+xml',
						'Authorization': 'Bearer ' + self.getToken(),
						'GData-Version':'2',
						'X-GData-Key': 'key=' + 'AIzaSyCdPQr0OBjSUdLqWoP29Z7oGp2NnBh5gNI'
		}
		
		req = self.session.delete(commentURL,headers=headers)
		return self.responseOK(req)
		
	def responseOK(self,req):
		return req.status_code > 199 and req.status_code < 300

	
################################################################################
# YouTubeCategoryInterface
################################################################################
class YouTubeCategoryInterface:
	searchURL = 'https://directory.tapatalk.com/search.php?search={terms}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'
	categoryURL = 'https://directory.tapatalk.com/get_forums_by_iab_category.php?cat_id={cat_id}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'
	categoryURL2 = 'https://s2directory.tapatalk.com/get_forums_by_iab_category.php?cat_id={cat_id}&page={page}&per_page={per_page}&app_key=fGdHrdjlH755GdF3&app_id=5'
	
	class ForumEntry(forumbrowser.ForumEntry):
		forumType = 'YT'
		def __init__(self,jobj):
			snippet = jobj['snippet']
			self.displayName = snippet.get('title','')
			self.description = snippet.get('description','')
			if 'thumbnails' in snippet:
				self.logo = snippet['thumbnails'].get('default',{}).get('url')
			else:
				self.logo = ''
			self.url = deepDictVal(jobj,('snippet','resourceId','channelId')) or jobj['id']
			if isinstance(self.url,dict): self.url = self.url['channelId']
			self.name = 'youtube.' + self.displayName.replace(' ','_')
			self.forumID = 'YT.' + self.name
			self.category = ''
			self.categoryID = self.url
	
	def __init__(self):
		self.api = YouTubeAPI()
		self.initPageData()
		
	def initPageData(self):
		self.page = 1
		self.prev = None
		self.next = None
		
	def getPageToken(self,page):
		if page > self.page:
			return self.next
		elif page < self.page:
			return self.prev
		return None
		
	def setPageData(self,page,jobj):
		self.page = page
		self.next = jobj.get('nextPageToken')
		self.prev = jobj.get('prevPageToken')
		
	def search(self,terms,page=1,per_page=20,p_dialog=None):
		pageToken = self.getPageToken(page)
		if pageToken:
			channels = self.api.Search.list(part='id,snippet',type='channel',maxResults=per_page,q=terms,pageToken=pageToken)
		else:
			channels = self.api.Search.list(part='id,snippet',type='channel',maxResults=per_page,q=terms)
		return self.processChannels(page,channels)
	
	def categories(self,cat_id=0,page=1,per_page=20,p_dialog=None):
		if cat_id == 0:
			self.initPageData()
			return {'cats':self.getCategories()}
		pageToken = self.getPageToken(page)
		source = self.api.Channels
		extraKWArgs = {}
		if cat_id == 'subscriptions':
			source = self.api.Subscriptions
			extraKWArgs['mine'] = 'true'
		if pageToken:
			channels = source.list(part='id,snippet,contentDetails',maxResults=per_page,categoryId=cat_id,pageToken=pageToken,**extraKWArgs)
		else:
			channels = source.list(part='id,snippet,contentDetails',maxResults=per_page,categoryId=cat_id,**extraKWArgs)
		return {'forums':self.processChannels(page,channels)}
	
	def getCategories(self):
		ret = []
		cats = self.api.GuideCategories.list(part='id,snippet',regionCode='us')
		if self.api.authorized(): ret.append({'id':'subscriptions','name':'Subscriptions','icon':''})
		for i in cats['items']:
			ret.append({'id':i['id'],'name':i['snippet']['title'],'icon':''})
		return ret
		
	def processChannels(self,page,channels):
		self.setPageData(page,channels)
		entries = []
		if not 'items' in channels:
			return entries
		for i in channels['items']:
			entries.append(self.ForumEntry(i))
		return entries
		
################################################################################
# ForumPost
################################################################################
class ForumPost(forumbrowser.ForumPost):
	def __init__(self,fb,pdict=None):
		forumbrowser.ForumPost.__init__(self,fb,pdict)
			
	def setVals(self,pdict):
		self.setPostID(getTVal(pdict,'id'))
		date = getTVal(pdict,'published') or getTVal(pdict,'publishedAt')
		if date:
			datetuple = iso8601.parse_date(date).timetuple()
			self.unixtime = time.mktime(datetuple)
			date = time.strftime('%I:%M %p - %A %B %d, %Y',datetuple)
		self.date = date
		self.userId = getTVal(pdict,'yt$channelId') # getTVal('yt$googlePlusUserId')
		self.userName = getTVal(pdict.get('author')[0],'name')
		self.avatar = ''
		self.online = False
		self.title = getTVal(pdict,'title')
		self.message = getTVal(pdict,'content')
		self.signature = ''
		self.setLikes(None)
		self._can_like = False
		self._is_liked = False
		self.isShort = False
		self.fid = ''
		self.tid = getTVal(pdict,'yt$videoid')
		self.topic = ''
		
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
#		if not likes_info:
#			if 'like users' in self.extras: del self.extras['like users']
#			if 'likes' in self.extras: del self.extras['likes']
#			return
#		users = []
#		for l in likes_info:
#			users.append(str(l.get('username','')))
#		self.extras['like users'] = ', '.join(users)
#		self.extras['likes'] = len(users)
		pass
		
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
		return ''
	
	def setUserInfo(self,info):
		if not info: return
		return
		
	def setPostID(self,pid):
		pid = pid.replace('http://','https://')
		self.postId = pid
		self.pid = pid
		self.isPM = False
	
	def getID(self):
		return self.pid
		
	def cleanUserName(self):
		return self.userName
		
	def getShortMessage(self):
		return self.getMessage(True)
	
	def getMessage(self,skip=False,raw=False):
		return self.message
		return texttransform.makeUnicode(self.message)
	
	def messageAsText(self):
		return self.message
		
	def messageAsDisplay(self,short=False,raw=False,quote_wrap=80):
		return self.message
		
	def messageAsQuote(self):
		return self.message
		
	def imageURLs(self):
		return []
		
	def linkImageURLs(self):
		#return re.findall('<a.+?href="(https?://.+?\.(?:jpg|jpeg|png|gif|bmp))".+?</a>',self.message)
		return []
		
	def linkURLs(self):
		return []
	
	def link2URLs(self):
		return []
		
	def links(self):
		ret = []
		for m in self.MC.linkFilter.finditer(self.message): ret.append(self.FB.getPMLink(m))
		return ret
		
class VideoPost(ForumPost):
	def setVals(self,pdict):
		self.setPostID(pdict.get('id',''))
		snippet = pdict.get('snippet','')
		date = snippet.get('publishedAt','')
		if date:
			datetuple = iso8601.parse_date(date).timetuple()
			self.unixtime = time.mktime(datetuple)
			date = time.strftime('%I:%M %p - %A %B %d, %Y',datetuple)
		self.date = date
		self.userId = snippet.get('channelId','')
		self.userName = snippet.get('channelTitle','')
		self.avatar = ''
		self.online = False
		self.title = snippet.get('title','')
		self.message = snippet.get('description','')
		self.signature = ''
		self.setLikes(None)
		self._can_like = False
		self._is_liked = False
		self.isShort = False
		self.fid = ''
		self.tid = self.pid
		self.topic = pdict.get('channelTitle','')
		
	def links(self):
		ret = []
		for m in self.MC.linkFilter.finditer('http://www.youtube.com/watch?v=%s' % self.pid): ret.append(self.FB.getPMLink(m))
		for m in self.MC.linkFilter.finditer(self.message): ret.append(self.FB.getPMLink(m))
		return ret

class PMLink(forumbrowser.PMLink):
	def processURL(self):
		forumbrowser.PMLink.processURL(self)
		self.url = self.url.rstrip('!.,]);:')
		self.text = self.url

################################################################################
# PageData
################################################################################
class PageData:
	def __init__(self,fb,next_page=None,prev_page=None,total_items=0,per_page=50):
		self._next = next_page
		self._prev = prev_page
		self.next = bool(next_page)
		self.prev = bool(prev_page)
		self.totalItems = total_items
		self.perPage = per_page
		self.isReplies = False
	
	def getPageNumber(self,page=None):
		return 1
						
	def getNextPage(self):
		return self._next
			
	def getPrevPage(self):
		return self._prev
				
	def getPageDisplay(self):
		return ''
#		if self.pageDisplay: return self.pageDisplay
#		if self.page is not None and self.totalPages is not None:
#			return 'Page %s of %s' % (self.page,self.totalPages)
			
class YoutubeForumBrowser(forumbrowser.ForumBrowser):
	browserType = 'youtube'
	prefix = 'YT.'
	ForumPost = ForumPost
	PMLink = PMLink
	PageData = PageData
	
	def __init__(self,forum,always_login=False,message_converter=None):
		forumbrowser.ForumBrowser.__init__(self,forum,always_login=always_login,message_converter=texttransform.MessageConverter)
		self.forum = forum[3:]
		self.channelID = None
		self.logo = ''
		self.name = self.forum
		self.userName = ''
		self.userChannelID = ''
		self.googlePlusID = ''
		self.channelTitle = ''
		self.channelGooglePlusID = ''
		self.loadForumFile()
		self.api = YouTubeAPI()
		self.initialize()
		self.getUserData()
	
	def loadForumFile(self):
		forum = self.getForumID()
		fname = os.path.join(util.FORUMS_PATH,forum)
		if not os.path.exists(fname):
			fname = os.path.join(util.FORUMS_STATIC_PATH,forum)
			if not os.path.exists(fname): return False
		with open(fname,'r') as f:
			self.name = f.readline().strip('\n').lstrip('#')
		self.loadForumData(fname)
		self.channelID = self.urls.get('server','')
		self.logo = self.urls.get('logo','')
		self.formats['quote'] = ''
		
	def initFilters(self):
		self.filters.update({	'link':'(?P<text>(?P<url>https?://[^\s]+))(?:\s|$)'})
	
	def getDisplayName(self):
		return self.name
		
	def canSearch(self): return self.canSearchPosts() or self.canSearchThreads() or self.canSearchAdvanced()
	def canSearchPosts(self): return False
	def canSearchThreads(self): return False
	def canSearchAdvanced(self,stype=None): return False
	
	def canSubscribeThread(self,tid): return False
	def canUnSubscribeThread(self,tid): return False
	
	def subscribeThread(self,tid): return False
	def unSubscribeThread(self,tid): return False
	
	def subscribeForum(self,fid): return False
	def unSubscribeForum(self,fid): return False
	
	def canSubscribeForum(self,fid): return False
	def canUnSubscribeForum(self,fid): return False
	
	def canCreateThread(self,fid): return False
		
	def isForumSubscribed(self,fid,default=False): return default
	
	def isThreadSubscribed(self,tid,default=False): return default
	
	def hasSubscriptions(self):
		return bool(self.favoritesID)
	
	def canPost(self): return self.isLoggedIn()
		
	def canDelete(self,user,target='POST'):
		if self.userName != user and self.userName != self.channelTitle and self.googlePlusID != self.channelGooglePlusID: return False
		return target == 'POST' and self.isLoggedIn()
			
	def canEditPost(self,user): return False
					
	def canGetUserInfo(self): return False
	
	def getUserInfo(self,uid=None,uname=None): return None

	def canOpenLatest(self): return False
	
	def isLoggedIn(self):
		return self.api.authorized()
		
	def getUserData(self):
		if not self.isLoggedIn(): return
		channel = self.api.Channels.list(part='id,snippet,contentDetails',mine='true')['items'][0]
		self.userName = deepDictVal(channel,('snippet','title'))
		self.userChannelID = deepDictVal(channel,('snippet','channelId'))
		self.googlePlusID = deepDictVal(channel,('contentDetails','googlePlusUserId'))
		self.favoritesID = deepDictVal(channel,('contentDetails','relatedPlaylists','favorites'))
		LOG('USER: {0} ({1})'.format(self.userName,self.googlePlusID))
	
	def getVideoData(self,videoID):
		video = self.api.Videos.list(part='id,snippet',id=videoID)
		if not 'items' in video or not video['items']: return None
		return video['items'][0]
		
	def getChannelData(self,channelID):
		channel = self.api.Channels.list(part='id,snippet',id=channelID)
		if not 'items' in channel or not channel['items']: return None
		return channel['items'][0]
		
	def canViewVideo(self,item):
		if deepDictVal(item,('status','privacyStatus')) != 'private': return True
		if deepDictVal(item,('snippet','channelId')) == self.userChannelID: return True
		return False
	
	def getForums(self,callback=None,donecallback=None,token=None):
		if not callback: callback = self.fakeCallback
		channels = self.api.Channels.list(part='id,snippet,contentDetails,brandingSettings,statistics',id=self.channelID)
		channel = channels['items'][0]
		self.channelTitle = channel['snippet'].get('title')
		self.channelGooglePlusID = deepDictVal(channel,('contentDetails','googlePlusUserId'))
		subscribers = deepDictVal(channel,('statistics','subscriberCount'))
		videos = deepDictVal(channel,('statistics','videoCount'))
		comments = deepDictVal(channel,('statistics','commentCount'))
		stats = {'total_members': subscribers, 'total_threads':videos,'total_posts':comments}
#		"statistics": {
#	    "viewCount": "1598085378",
#	    "commentCount": "29994",
#	    "subscriberCount": "6321550",
#	    "hiddenSubscriberCount": false,
#	    "videoCount": "4279"
		baseIcon = '../../../media/forum-browser-%s.png'
		forums = []
		if not token:
			for name, ID in channel['contentDetails']['relatedPlaylists'].items():
				forums.append({'forumid':ID,'title':name.title(),'description':name.title(),'subscribed':False,'subforum':False,'logo_url':baseIcon % name})
		if token:
			lists = self.api.Playlists.list(part='id,snippet,contentDetails',maxResults=50,pageToken=token,channelId=self.channelID)
		else:
			lists = self.api.Playlists.list(part='id,snippet,contentDetails',maxResults=50,channelId=self.channelID)
		for i in lists['items']:
			vidCount = deepDictVal(i,('contentDetails','itemCount'))
			title = i['snippet'].get('title','').title()
			desc = i['snippet'].get('description','') or title
			title = '{0} ({1})'.format(title,vidCount)
			thumb = i['snippet']['thumbnails']['default']['url']
			forums.append({'forumid':i['id'],'title':title,'description':desc,'subscribed':False,'subforum':False,'logo_url':thumb,'thumb':thumb})
		if 'nextPageToken' in lists:
			forums.append({'forumid':'playlists-%s' % lists['nextPageToken'],'title':'More'})
		logo = deepDictVal(channel,('brandingSettings','image','bannerMobileImageUrl'))
		self.background = logo = deepDictVal(channel,('brandingSettings','image','bannerTvHighImageUrl'))
		return self.finish(forumbrowser.FBData(forums,extra={'logo':logo,'force':True,'pm_counts':None,'stats':stats}),donecallback)
	
	def createThreadDict(self,item,skip_video_data=False):
		snippet = item['snippet']
		data = {}
		data['threadid'] = snippet['resourceId']['videoId']
		if skip_video_data:
			data['starter'] = snippet.get('channelTitle','')
		else:
			video = self.api.Video(data['threadid'])
			if video:
				if 'author' in video: data['starter'] = getTVal(video['author'][0],'name')
				data['view_number'] = deepDictVal(video,('yt$statistics','viewCount'))
				data['reply_number'] = deepDictVal(video,('gd$comments','gd$feedLink','countHint'))
		data['title'] = snippet['title']
		data['short_content'] = snippet['description'].replace('\n',' | ')
		if 'thumbnails' in snippet:
			data['icon_url'] = data['thumb'] = snippet['thumbnails']['default']['url']
		data['subscribed'] = False
		data['lastposter'] = ''
		data['sticky'] = False
		return data
	
	def getThreads(self,forumid,page=0,callback=None,donecallback=None,page_data=None):
		if not callback: callback = self.fakeCallback
		if forumid.startswith('playlists-'):
			token = forumid.split('-',1)[-1]
			forums = self.getForums(None, None,token=token).data
			fbdata = forumbrowser.FBData([],None)
			fbdata['forums'] = forums
			return self.finish(fbdata,donecallback) 
		try:
			if not callback(20,''): return None
			if page and not str(page).isdigit():
				items = self.api.PlaylistItems.list(part='id,snippet,status',playlistId=forumid,maxResults='50',pageToken=page)
			else:
				items = self.api.PlaylistItems.list(part='id,snippet,status',playlistId=forumid,maxResults='50')
			if not callback(30,''): return None
			threads = []
			tot = len(items['items'])
			pct_ct=-1
			skip = True
			if forumid[:2] in ('FL','LL','WL','HL'): skip = False
			for item in items['items']:
				pct_ct+=1
				if not self.canViewVideo(item): continue
				threads.append(self.createThreadDict(item,skip_video_data=skip))
				if not self.updateProgress(callback, 30, 75, pct_ct, tot, 'Getting Video Data'): break
			pd = self.getPageData(	next_page = items.get('nextPageToken'),
										prev_page = items.get('prevPageToken'),
										total_items = items['pageInfo']['totalResults'],
										per_page = items['pageInfo']['resultsPerPage']
			)
		except:
			em = ERROR('ERROR GETTING CHANNELS')
			return self.finish(forumbrowser.FBData(error=em))
		
		callback(100,util.T(32052))
		return self.finish(forumbrowser.FBData(threads,pd),donecallback)
		
	def getSubscriptions(self,page='',callback=None,donecallback=None,page_data=None):
		threads = self.getThreads(self.favoritesID, page, callback, None)
		return self.finish(forumbrowser.FBData(threads.data,threads.pageData),donecallback)
			
	def getReplies(self,threadid,forumid,page=0,lastid='',pid='',callback=None,donecallback=None,page_data=None,search=False):
		if not callback: callback = self.fakeCallback
		video = self.getVideoData(threadid)
		if str(page).startswith('http'):
			comments = self.api.Comments(threadid,url=page)
		else:
			comments = self.api.Comments(threadid)
		vp = VideoPost(self,video)
		userData = self.api.User(vp.userId)
		vp.avatar = deepDictVal(userData,('media$thumbnail','url'))
		
		vp.postNumber = 1
		citems = [vp]
		ct=comments['feed']['openSearch$totalResults']['$t']+1
		pct_ct=0
		if 'entry' in comments['feed']:
			tot = len(comments['feed']['entry'])
			for entry in comments['feed']['entry']:
				fp = self.getForumPost(entry)
				userData = self.api.User(fp.userId)
				fp.avatar = deepDictVal(userData,('media$thumbnail','url'))
				fp.postNumber = ct
				citems.append(fp)
				if not self.updateProgress(callback, 20, 75, pct_ct, tot, util.T(32103)): break
				ct-=1
				pct_ct+=1
		data = {'next_page':None,'prev_page':None}
		for l in comments['feed']['link']:
			if l.get('rel') == 'next':
				data['next_page'] = l.get('href')
			elif l.get('rel') == 'previous':
				data['prev_page'] = l.get('href')
		pd = self.getPageData(	next_page = data.get('next_page'),
									prev_page = data.get('prev_page'),
									total_items = comments['feed'].get('openSearch$totalResults').get('$t'),
									per_page = comments['feed'].get('openSearch$itemsPerPage').get('$t')
		)
		
		return self.finish(forumbrowser.FBData(citems,pd),donecallback)
		
	def post(self,post,callback=None):
#		if post.isEdit: return self.editPost(post)
		LOG('Posting reply')
		if not post.message: return False
		if not callback: callback = self.fakeCallback
		callback(40,util.T(32106))
		success = self.api.postComment(post.tid,post.message)
		callback(100,util.T(32052))
		return success

	def deletePost(self,post):
		return self.api.deleteComment(post.pid)
		
def getYouTubeURL(videoID):
	from webviewer import video
	quality = util.getSetting('youtube_video_quality',1)
	return video.getVideoURL(videoID,quality)


