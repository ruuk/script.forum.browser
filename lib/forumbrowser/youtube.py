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

#Modified from plugin.video.youtube
class VideoHandler:
	_formats = {
		'5': {'ext': 'flv', 'width': 400, 'height': 240},
		'6': {'ext': 'flv', 'width': 450, 'height': 270},
		'13': {'ext': '3gp'},
		'17': {'ext': '3gp', 'width': 176, 'height': 144},
		'18': {'ext': 'mp4', 'width': 640, 'height': 360},
		'22': {'ext': 'mp4', 'width': 1280, 'height': 720},
		'34': {'ext': 'flv', 'width': 640, 'height': 360},
		'35': {'ext': 'flv', 'width': 854, 'height': 480},
		'36': {'ext': '3gp', 'width': 320, 'height': 240},
		'37': {'ext': 'mp4', 'width': 1920, 'height': 1080},
		'38': {'ext': 'mp4', 'width': 4096, 'height': 3072},
		'43': {'ext': 'webm', 'width': 640, 'height': 360},
		'44': {'ext': 'webm', 'width': 854, 'height': 480},
		'45': {'ext': 'webm', 'width': 1280, 'height': 720},
		'46': {'ext': 'webm', 'width': 1920, 'height': 1080},


		# 3d videos
		'82': {'ext': 'mp4', 'height': 360, 'resolution': '360p', 'format_note': '3D', 'preference': -20},
		'83': {'ext': 'mp4', 'height': 480, 'resolution': '480p', 'format_note': '3D', 'preference': -20},
		'84': {'ext': 'mp4', 'height': 720, 'resolution': '720p', 'format_note': '3D', 'preference': -20},
		'85': {'ext': 'mp4', 'height': 1080, 'resolution': '1080p', 'format_note': '3D', 'preference': -20},
		'100': {'ext': 'webm', 'height': 360, 'resolution': '360p', 'format_note': '3D', 'preference': -20},
		'101': {'ext': 'webm', 'height': 480, 'resolution': '480p', 'format_note': '3D', 'preference': -20},
		'102': {'ext': 'webm', 'height': 720, 'resolution': '720p', 'format_note': '3D', 'preference': -20},

		# Apple HTTP Live Streaming
		'92': {'ext': 'mp4', 'height': 240, 'resolution': '240p', 'format_note': 'HLS', 'preference': -10},
		'93': {'ext': 'mp4', 'height': 360, 'resolution': '360p', 'format_note': 'HLS', 'preference': -10},
		'94': {'ext': 'mp4', 'height': 480, 'resolution': '480p', 'format_note': 'HLS', 'preference': -10},
		'95': {'ext': 'mp4', 'height': 720, 'resolution': '720p', 'format_note': 'HLS', 'preference': -10},
		'96': {'ext': 'mp4', 'height': 1080, 'resolution': '1080p', 'format_note': 'HLS', 'preference': -10},
		'132': {'ext': 'mp4', 'height': 240, 'resolution': '240p', 'format_note': 'HLS', 'preference': -10},
		'151': {'ext': 'mp4', 'height': 72, 'resolution': '72p', 'format_note': 'HLS', 'preference': -10},

		# DASH mp4 video
		'133': {'ext': 'mp4', 'height': 240, 'resolution': '240p', 'format_note': 'DASH video', 'preference': -40},
		'134': {'ext': 'mp4', 'height': 360, 'resolution': '360p', 'format_note': 'DASH video', 'preference': -40},
		'135': {'ext': 'mp4', 'height': 480, 'resolution': '480p', 'format_note': 'DASH video', 'preference': -40},
		'136': {'ext': 'mp4', 'height': 720, 'resolution': '720p', 'format_note': 'DASH video', 'preference': -40},
		'137': {'ext': 'mp4', 'height': 1080, 'resolution': '1080p', 'format_note': 'DASH video', 'preference': -40},
		'138': {'ext': 'mp4', 'height': 1081, 'resolution': '>1080p', 'format_note': 'DASH video', 'preference': -40},
		'160': {'ext': 'mp4', 'height': 192, 'resolution': '192p', 'format_note': 'DASH video', 'preference': -40},
		'264': {'ext': 'mp4', 'height': 1080, 'resolution': '1080p', 'format_note': 'DASH video', 'preference': -40},

		# Dash mp4 audio
		'139': {'ext': 'm4a', 'format_note': 'DASH audio', 'vcodec': 'none', 'abr': 48, 'preference': -50},
		'140': {'ext': 'm4a', 'format_note': 'DASH audio', 'vcodec': 'none', 'abr': 128, 'preference': -50},
		'141': {'ext': 'm4a', 'format_note': 'DASH audio', 'vcodec': 'none', 'abr': 256, 'preference': -50},

		# Dash webm
		'167': {'ext': 'webm', 'height': 360, 'width': 640, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'168': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'169': {'ext': 'webm', 'height': 720, 'width': 1280, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'170': {'ext': 'webm', 'height': 1080, 'width': 1920, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'218': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'219': {'ext': 'webm', 'height': 480, 'width': 854, 'format_note': 'DASH video', 'container': 'webm', 'vcodec': 'VP8', 'acodec': 'none', 'preference': -40},
		'242': {'ext': 'webm', 'height': 240, 'resolution': '240p', 'format_note': 'DASH webm', 'preference': -40},
		'243': {'ext': 'webm', 'height': 360, 'resolution': '360p', 'format_note': 'DASH webm', 'preference': -40},
		'244': {'ext': 'webm', 'height': 480, 'resolution': '480p', 'format_note': 'DASH webm', 'preference': -40},
		'245': {'ext': 'webm', 'height': 480, 'resolution': '480p', 'format_note': 'DASH webm', 'preference': -40},
		'246': {'ext': 'webm', 'height': 480, 'resolution': '480p', 'format_note': 'DASH webm', 'preference': -40},
		'247': {'ext': 'webm', 'height': 720, 'resolution': '720p', 'format_note': 'DASH webm', 'preference': -40},
		'248': {'ext': 'webm', 'height': 1080, 'resolution': '1080p', 'format_note': 'DASH webm', 'preference': -40},

		# Dash webm audio
		'171': {'ext': 'webm', 'vcodec': 'none', 'format_note': 'DASH webm audio', 'abr': 48, 'preference': -50},
		'172': {'ext': 'webm', 'vcodec': 'none', 'format_note': 'DASH webm audio', 'abr': 256, 'preference': -50},

		# RTMP (unnamed)
		'_rtmp': {'protocol': 'rtmp'},
	}
	
	fmt_value = {
		5: "240p h263 flv container",
		18: "360p h264 mp4 container | 270 for rtmpe?",
		22: "720p h264 mp4 container",
		26: "???",
		33: "???",
		34: "360p h264 flv container",
		35: "480p h264 flv container",
		37: "1080p h264 mp4 container",
		38: "720p vp8 webm container",
		43: "360p h264 flv container",
		44: "480p vp8 webm container",
		45: "720p vp8 webm container",
		46: "520p vp8 webm stereo",
		59: "480 for rtmpe",
		78: "seems to be around 400 for rtmpe",
		82: "360p h264 stereo",
		83: "240p h264 stereo",
		84: "720p h264 stereo",
		85: "520p h264 stereo",
		100: "360p vp8 webm stereo",
		101: "480p vp8 webm stereo",
		102: "720p vp8 webm stereo",
		120: "hd720",
		121: "hd1080"
		}

	# YouTube Playback Feeds
	urls = {}
	urls['video_stream'] = "https://www.youtube.com/watch?v=%s&gl=US&hl=en&has_verified=1"
	urls['embed_stream'] = "http://www.youtube.com/get_video_info?video_id=%s"
	urls['video_info'] = "http://gdata.youtube.com/feeds/api/videos/%s"
	
	def __init__(self,ID):
		self.ID = ID
		self.userAgent = 'Mozilla/5.0+(Windows+NT+6.2;+Win64;+x64;+rv:16.0.1)+Gecko/20121011+Firefox/16.0.1'
		self.session = requests.Session()
		
	def getVideoURL(self):
		html = self.getPageHTML()
		links = self.scrapeWebPageForVideoLinks(html)
		url = ''
		if len(links) != 0:
			url = self.selectVideoQuality(links)
		elif "hlsvp" in links:
			#hls selects the quality based on available bitrate (adaptive quality), no need to select it here
			url = links[u"hlsvp"]
		return url
		
	def getPageHTML(self):
		return self.session.get(self.urls['video_stream'] % self.ID,headers={'User-Agent':self.userAgent}).text
	
	def decryptSignature(self, s, age_gate=False):
		''' use decryption solution by Youtube-DL project '''
		if age_gate:
			# The videos with age protection use another player, so the
			# algorithms can be different.
			if len(s) == 86:
				return s[2:63] + s[82] + s[64:82] + s[63]

		if len(s) == 93:
			return s[86:29:-1] + s[88] + s[28:5:-1]
		elif len(s) == 92:
			return s[25] + s[3:25] + s[0] + s[26:42] + s[79] + s[43:79] + s[91] + s[80:83]
		elif len(s) == 91:
			return s[84:27:-1] + s[86] + s[26:5:-1]
		elif len(s) == 90:
			return s[25] + s[3:25] + s[2] + s[26:40] + s[77] + s[41:77] + s[89] + s[78:81]
		elif len(s) == 89:
			return s[84:78:-1] + s[87] + s[77:60:-1] + s[0] + s[59:3:-1]
		elif len(s) == 88:
			return s[7:28] + s[87] + s[29:45] + s[55] + s[46:55] + s[2] + s[56:87] + s[28]
		elif len(s) == 87:
			return s[6:27] + s[4] + s[28:39] + s[27] + s[40:59] + s[2] + s[60:]
		elif len(s) == 86:
			return s[80:72:-1] + s[16] + s[71:39:-1] + s[72] + s[38:16:-1] + s[82] + s[15::-1]
		elif len(s) == 85:
			return s[3:11] + s[0] + s[12:55] + s[84] + s[56:84]
		elif len(s) == 84:
			return s[78:70:-1] + s[14] + s[69:37:-1] + s[70] + s[36:14:-1] + s[80] + s[:14][::-1]
		elif len(s) == 83:
			return s[80:63:-1] + s[0] + s[62:0:-1] + s[63]
		elif len(s) == 82:
			return s[80:37:-1] + s[7] + s[36:7:-1] + s[0] + s[6:0:-1] + s[37]
		elif len(s) == 81:
			return s[56] + s[79:56:-1] + s[41] + s[55:41:-1] + s[80] + s[40:34:-1] + s[0] + s[33:29:-1] + s[34] + s[28:9:-1] + s[29] + s[8:0:-1] + s[9]
		elif len(s) == 80:
			return s[1:19] + s[0] + s[20:68] + s[19] + s[69:80]
		elif len(s) == 79:
			return s[54] + s[77:54:-1] + s[39] + s[53:39:-1] + s[78] + s[38:34:-1] + s[0] + s[33:29:-1] + s[34] + s[28:9:-1] + s[29] + s[8:0:-1] + s[9]
		else:
			LOG(u'Unable to decrypt signature, key length %d not supported; retrying might work' % (len(s)))
		return ''
		
	def removeAdditionalEndingDelimiter(self, data):
		pos = data.find("};")
		if pos != -1:
			LOG(u"found extra delimiter, removing")
			data = data[:pos + 1]
		return data
		
	def extractFlashVars(self, data):
		flashvars = {}
		found = False

		for line in data.split("\n"):
			if line.strip().find(";ytplayer.config = ") > 0:
				found = True
				p1 = line.find(";ytplayer.config = ") + len(";ytplayer.config = ") - 1
				p2 = line.rfind(";")
				if p1 <= 0 or p2 <= 0:
					continue
				data = line[p1 + 1:p2]
				break
		data = self.removeAdditionalEndingDelimiter(data)

		if found:
			import json
			data = json.loads(data)
			flashvars = data["args"]
		#LOG("Step2: " + repr(data))

		#LOG(u"flashvars: " + repr(flashvars))
		return flashvars
		
	def scrapeWebPageForVideoLinks(self, html):
		links = {}

		flashvars = self.extractFlashVars(html)
		if not flashvars.has_key(u"url_encoded_fmt_stream_map"):
			return links

		if flashvars.has_key(u"ttsurl"):
			links[u"ttsurl"] = flashvars[u"ttsurl"]

		if flashvars.has_key(u"hlsvp"):								  
			links[u"hlsvp"] = flashvars[u"hlsvp"]	 

		for url_desc in flashvars[u"url_encoded_fmt_stream_map"].split(u","):
			url_desc_map = urlparse.parse_qs(url_desc)
			if not (url_desc_map.has_key(u"url") or url_desc_map.has_key(u"stream")):
				continue

			key = int(url_desc_map[u"itag"][0])
			url = u""
			if url_desc_map.has_key(u"url"):
				url = urllib.unquote(url_desc_map[u"url"][0])
			elif url_desc_map.has_key(u"conn") and url_desc_map.has_key(u"stream"):
				url = urllib.unquote(url_desc_map[u"conn"][0])
				if url.rfind("/") < len(url) -1:
					url = url + "/"
				url = url + urllib.unquote(url_desc_map[u"stream"][0])
			elif url_desc_map.has_key(u"stream") and not url_desc_map.has_key(u"conn"):
				url = urllib.unquote(url_desc_map[u"stream"][0])

			if url_desc_map.has_key(u"sig"):
				url = url + u"&signature=" + url_desc_map[u"sig"][0]
			elif url_desc_map.has_key(u"s"):
				import re
				age_gate = re.search(r'player-age-gate-content">', html) is not None
				sig = url_desc_map[u"s"][0]
				url = url + u"&signature=" + self.decryptSignature(sig, age_gate)

			links[key] = url

		return links

	def selectVideoQuality(self, links):
		quality = util.getSetting('youtube_video_quality',1)
		minHeight = 0
		maxHeight = 480
		if quality > 1:
			minHeight = 721
			maxHeight = 1080
		elif quality > 0:
			minHeight = 481
			maxHeight = 720
			
		defFormat = None
		defMax = 0
		prefFormat = None
		prefMax = 0
		keys = sorted(links.keys())
		fallback = keys[0]
		for fmt in keys:
			if not str(fmt) in self._formats: continue
			fdata = self._formats[str(fmt)]
			if not 'height' in fdata: continue
			h = fdata['height']
			if h >= minHeight and h <= maxHeight:
				if h > prefMax:
					prefMax = h
					prefFormat = fmt
			elif h > defMax and h <= maxHeight:
				defMax = h
				defFormat = fmt
						
		LOG('Quality: {0}'.format(quality))
		if prefFormat:
			LOG('Using Preferred Format: {0} ({1}x{2})'.format(prefFormat,self._formats[str(prefFormat)].get('width','?'),prefMax))
			url = links[prefFormat]
		elif defFormat:
			LOG('Using Default Format: {0} ({1}x{2})'.format(defFormat,self._formats[str(defFormat)].get('width','?'),defMax))
			url = links[defFormat]
		LOG('Using Fallback Format: {0}'.format(fallback))
		url = links[fallback]
		
		if url.find("rtmp") == -1:
			url += '|' + urllib.urlencode({'User-Agent':self.userAgent})

		return url
		
	def selectVideoQualityOld(self, links):
		link = links.get
		video_url = ""

		hd_quality = util.getSetting('youtube_video_quality',1)

		# SD videos are default, but we go for the highest res
		if (link(35)):
			video_url = link(35)
		elif (link(59)):
			video_url = link(59)
		elif link(44):
			video_url = link(44)
		elif (link(78)):
			video_url = link(78)
		elif (link(34)):
			video_url = link(34)
		elif (link(43)):
			video_url = link(43)
		elif (link(26)):
			video_url = link(26)
		elif (link(18)):
			video_url = link(18)
		elif (link(33)):
			video_url = link(33)
		elif (link(5)):
			video_url = link(5)

		if hd_quality > 0:	# <-- 720p
			if (link(22)):
				video_url = link(22)
			elif (link(45)):
				video_url = link(45)
			elif link(120):
				video_url = link(120)
		if hd_quality > 1:
			if (link(37)):
				video_url = link(37)
			elif link(121):
				video_url = link(121)

		if link(38) and False:
			video_url = link(38)


		if not len(video_url) > 0:
			return video_url

		if video_url.find("rtmp") == -1:
			video_url += '|' + urllib.urlencode({'User-Agent':self.userAgent})

		return video_url



