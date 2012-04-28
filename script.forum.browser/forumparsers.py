import HTMLParser, re, htmlentitydefs

def cUConvert(m): return unichr(int(m.group(1)))
def cTConvert(m): return unichr(htmlentitydefs.name2codepoint.get(m.group(1),32))
def convertHTMLCodes(html):
	if not isinstance(html,unicode):
		html = unicode(html,'utf8','replace')
	try:
		html = re.sub('&#(\d{1,5});',cUConvert,html)
		html = re.sub('&(\w+?);',cTConvert,html)
	except:
		pass
	return html

def test(url):
	import urllib2
	p = VBForumParser()
	html = urllib2.urlopen(url).read()
	p.feed(html)
	for a in p.all:
		if a.get('subforum'): print ' ',a.get('title',''),a.get('forumid','')
		else: print a.get('title',''),a.get('forumid','')
	return p

def testT(url):
	import urllib2
	p = VBThreadParser()
	html = urllib2.urlopen(url).read()
	p.feed(html)
	for a in p.all:
		print a.get('title',''),a.get('threadid','')
	return p

def testP(url):
	import urllib2
	p = VBPostParser()
	html = urllib2.urlopen(url).read()
	p.feed(html)
	for a in p.all:
		print a#.get('postid')
	return p
	
class BaseParser(HTMLParser.HTMLParser):
	def __init__(self):
		self.all = []
		self.revertCodesRE = re.compile(r'(%)([\w\d]+;)')
		self.imgSrcRE = re.compile(r'src="([^"]*?)"')
		self.aHrefRE = re.compile(r'href="([^"]*?)"')
		self.tagRE = re.compile(r'<[^>]*?>')
		self.commentRE = re.compile(r"<\![^>]*?>")
		self.tagFixRE1 = re.compile(r'(="[^"]*?)"(?! )([^"]*?" )')
		self.tagFixRE2 = re.compile(r'(="[^"]*?" )([^"]*?)(?<!=)"(\w+=)(\w+)')
		self.tagFixRE3 = re.compile(r"(='[^']*?)'([^'=]*?' )")
		self.tagFixRE4 = re.compile(r'(")(\w+=")')
		self.tagFixRE5 = re.compile(r'(?<!=)"" ')
		self.resetCurrent(False)
		HTMLParser.HTMLParser.__init__(self)
		
	def badQuoteFix(self,m):
		w = m.group(0)
		new = re.sub(r'( \w+=")',r'"\1',w)
		if new == w: new = m.group(1) + m.group(2)
		return new
	
	def cleanTag(self,m):
		data = m.group(0)
		data = self.tagFixRE1.sub(self.badQuoteFix,data)
		data = self.tagFixRE2.sub(r'\1\2\3"\4',data)
		data = self.tagFixRE3.sub(r'\1&#39;\2',data)
		data = self.tagFixRE4.sub(r'\1 \2',data)
		data = self.tagFixRE5.sub('" ',data)
		return data
	
	def feed(self,data):
		#open('/home/ruuk/test2.text','w').write(data)
		data = self.commentRE.sub('',data)
		data = self.tagRE.sub(self.cleanTag,data)
		data = re.sub(r"(&)([\w\d]+;)(?=[^<]*?<)",r'%\2',data)
		#open('/home/ruuk/test.text','w').write(data)
		HTMLParser.HTMLParser.feed(self,data)
	
	def revertCodes(self,data):
		return convertHTMLCodes(self.revertCodesRE.sub(r'&\2',data))
	
	def resetCurrent(self,add=True):
		if add:
			if self.current:
				#print self.current
				self.all.append(self.current)
		self.mode = None
		self.subMode = None
		self.depth = 0
		self.current = {}
		
	def getAttr(self,name,attrs):
		for a in attrs:
			if a[0] == name:
				return a[1]
		return ''
		
	def getList(self,data):
		self.all = []
		self.feed(data)
		self.reset()
		return self.all
	
	def extractID(self,pre,var,data):
		m = re.search(pre + '(?:\?|/)(?:[^"]*?'+var+'=)?(?P<id>\d+)',data)
		if m: return m.groupdict().get('id')
		
	def check_for_whole_start_tag_save(self, i):
		rawdata = self.rawdata
		m = HTMLParser.locatestarttagend.match(rawdata, i)
		if m:
			j = m.end()
			next = rawdata[j:j+1] #@ReservedAssignment
			if next == ">":
				return j + 1
			if next == "/":
				if rawdata.startswith("/>", j):
					return j + 2
				if rawdata.startswith("/", j):
					# buffer boundary
					return -1
				# else bogus input
				self.updatepos(i, j + 1)
				self.error("malformed empty start tag")
			if next == "":
				# end of input
				return -1
			if next in ("abcdefghijklmnopqrstuvwxyz=/"
						"ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
				# end of input in or before attribute value, or we have the
				# '/' from a '/>' ending
				return -1
			self.updatepos(i, j)
			#self.error("malformed start tag")
			return
		raise AssertionError("we should not get here!")

#	def unknown_decl(self,data):
#		print data

class VBPostParser(BaseParser):
	def __init__(self):
		self.pidRE = re.compile(r'#post(\d+)')
		self.postTag = None
		self.currentStat = ''
		self.currentQuote = ''
		self.quoteMode = ''
		self.currentTag = None
		self.currentDepth = 0
		self.resetContent()
		BaseParser.__init__(self)
		
	def resetContent(self):
		self.contentDepth = 0
		self.contentTag = ''
		self.subMode = None
		self.quoteMode = None
		self.currentQuote = ''
		self.currentStat = ''
		
	def feed(self,data):
		data = data.split('<!-- closing div for above_body -->')[-1].split('<!-- closing div for body_wrapper -->')[0]
		BaseParser.feed(self, data)
		
	def setPID(self,data,ret=False):
		if not data: return ''
		m = self.pidRE.search(data)
		if m:
			if ret: return m.group(1) or ''
			self.current['postid'] = m.group(1)
	
	def setUID(self,data):
		if not data: return
		uid = self.extractID('member.php', 'u', data)
		if uid: self.current['userid'] = uid
	
	def setCurrentTag(self,tag):
		self.currentTag = tag
		self.currentDepth = 0
	
	def checkCurrentTag(self,tag):
		if self.currentTag == tag:
			self.currentDepth += 1
			
	def checkEndTag(self,tag):
		if self.currentTag == tag:
			self.currentDepth -= 1
			if self.currentDepth < 1:
				self.currentTag = None
				self.currentDepth = 0
				self.subMode = None
				
	def handle_starttag(self,tag,attrs):
		className = self.getAttr('class', attrs)
		#print tag, self.subMode, className, self.getAttr('src', attrs)
		if className:
			if 'postbit' in className.split(' ') or (tag == 'li' and 'postbit' in className):
				self.mode = 'POST'
				self.postTag = tag
			elif self.subMode == 'CONTENT' and 'bbcode' in className:
				self.quoteMode = 'START'
				self.currentQuote = '[quote='
				#timmins;246901]
			elif self.subMode == 'CONTENT' and 'message' in className:
				self.quoteMode = 'QUOTE'
				#timmins;246901]
			elif 'date' in className.split(' '):
				self.subMode = 'DATE'
			elif 'time' in className: 
				self.subMode = 'TIME'
			elif self.mode == 'POST' and ('posttitle' in className or (tag == 'h2' and 'title' in className)):
				self.subMode = 'TITLE'
				self.setCurrentTag(tag)
			elif 'postcounter' in className:
				self.subMode = 'POSTNUMBER'
				href = self.getAttr('href', attrs)
				self.setPID(href)
			elif 'usertitle' in className:
				self.subMode = 'USERTITLE'
			elif 'onlinestatus' in className:
				src = self.getAttr('src', attrs)
				self.current['online'] = src and 'online' in src
			elif tag == 'dl' and ('userstats' in className or 'userinfo' in className):
				self.subMode = 'STATS'
			elif self.subMode != 'CONTENT' and 'content' in className.split(' '):
				#print '-----------------------------------START'
				self.contentTag = tag
				self.contentDepth = 0
				self.subMode = 'CONTENT'
				self.current['message'] = ''
			elif 'signaturecontainer' in className:
				self.subMode = 'SIGNATURE'
				self.contentTag = tag
				self.current['signature'] = ''
			elif tag == 'a' and 'avatar' in className:
				self.subMode = 'AVATAR'
			elif tag == 'a' and 'username' in className:
				self.subMode = 'USER1'
				self.setUID(self.getAttr('href', attrs))
				
		elif self.subMode == 'CONTENT' and (tag == 'img' or tag == 'a' or tag == 'b' or tag == 'i'):
			conv = ''
			if tag == 'a':
				m = self.aHrefRE.search(self.get_starttag_text())
				if m: conv = '[url="%s"]' % m.group(1)
			elif tag == 'img':
				m = self.imgSrcRE.search(self.get_starttag_text())
				if m: conv = '[img]%s[/img]' % m.group(1)
			elif tag == 'b':
				conv = '[b]'
			elif tag == 'i':
				conv = '[i]'
			if self.quoteMode:
				if self.quoteMode == 'QUOTE': self.currentQuote += conv
			else:
				self.current['message'] += conv
			
				
		if self.subMode == 'AVATAR' and tag == 'img':
			self.current['avatar'] = self.revertCodes(self.getAttr('src', attrs)).strip()
				
		if self.mode == 'POST':
			if tag == self.postTag: self.depth += 1
			if self.subMode == 'CONTENT' and tag == self.contentTag: self.contentDepth += 1
			
			if self.subMode == 'CONTENT' and tag == 'img' and 'quote' in self.getAttr('src', attrs):
				self.quoteMode = 'USER1'
			elif self.subMode == 'CONTENT' and self.quoteMode == 'USER1' and tag == 'strong':
				self.quoteMode = 'USER2'
			elif self.subMode == 'CONTENT' and self.quoteMode == 'POSTID' and tag == 'a':
				href = self.getAttr('href', attrs)
				self.currentQuote += ';' + self.setPID(href, True) + ']<br />'
				self.quoteMode = 'WAIT'
		
		self.checkCurrentTag(tag)
	
	def handle_data(self,data):
		#if data.strip(): print self.quoteMode, self.mode, self.subMode, self.postTag, data.strip()
		if self.mode == 'POST':
			if self.subMode == 'DATE':
				self.current['date'] = self.revertCodes(data).strip()
			elif self.subMode == 'TIME':
				if not 'date' in self.current: self.current['date'] = ''
				self.current['date'] += ' ' + self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'USER1':
				self.current['user'] = self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'USERTITLE':
				self.current['status'] = self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'POSTNUMBER':
				self.current['postnumber'] = data.strip().replace('#','')
				self.subMode = None
			elif self.subMode == 'TITLE':
				title = self.revertCodes(data).strip()
				if title:
					self.current['title'] = title
					self.subMode = None
			elif self.subMode == 'STATS':
				if self.currentStat:
					stat = self.revertCodes(data).strip()
					if stat:
						self.current[self.currentStat] = stat
						self.currentStat = None
				elif 'Join Date' in data:
					self.currentStat = 'joindate'
				elif 'Location' in data:
					self.currentStat = 'location'
				elif 'Posts' in data:
					self.currentStat = 'postcount'
			elif self.subMode == 'CONTENT' and self.quoteMode == 'USER2':
				self.currentQuote += self.revertCodes(data).strip()
				self.quoteMode = 'POSTID'
			elif self.subMode == 'CONTENT' and self.quoteMode == 'QUOTE':
				self.currentQuote += self.revertCodes(data).strip()
			elif self.subMode == 'CONTENT' and not self.quoteMode:
				self.current['message'] += self.revertCodes(data).strip()
			elif self.subMode == 'SIGNATURE':
				self.current['signature'] += self.revertCodes(data).strip()
			
	
	def handle_endtag(self,tag):
		self.checkEndTag(tag)
		if self.subMode == 'CONTENT':
			if tag == 'br' or tag == 'div':
				if self.quoteMode == 'QUOTE':
					self.currentQuote  += '<br />'
				else:
					self.current['message'] += '<br />'
			if tag == 'div' and self.quoteMode == 'QUOTE':
				self.quoteMode = None
				self.currentQuote += '[/quote]'
				self.current['message'] += self.currentQuote
				self.currentQuote = ''
			if tag == 'a' or tag == 'b' or tag == 'i':
				if tag == 'a':
					conv = '[/url]'
				elif tag == 'b':
					conv = '[/b]'
				elif tag == 'i':
					conv = '[/i]'
				if self.quoteMode:
					if self.quoteMode == 'QUOTE':
						self.currentQuote += conv
				else:
					self.current['message'] += conv
		if tag == self.postTag:
			if self.mode == 'POST':
				self.depth -= 1
				if self.depth < 1:
					self.resetCurrent()
		if (self.subMode == 'CONTENT' or self.subMode == 'SIGNATURE') and tag == self.contentTag:
			self.contentDepth -= 1
			if self.contentDepth < 1:
				self.resetContent()		
				#print '-----------------------------------END'
		elif tag == 'dl':
				self.subMode = None
				self.currentStat = None
		
class VBThreadParser(BaseParser):
	def __init__(self):
		BaseParser.__init__(self)
		
	def feed(self,data):
		data = data.split('<!-- closing div for above_body -->')[-1].split('<!-- closing div for body_wrapper -->')[0]
		BaseParser.feed(self, data)
		
	def setTID(self,data):
		ID = self.extractID('showthread.php','t',data)
		if id: self.current['threadid'] = ID
	
	def handle_starttag(self,tag,attrs):
		className = self.getAttr('class', attrs)
		if className:
			if 'threadbit' in className:
				self.mode = 'THREAD'
				return
			elif not self.subMode and (tag == 'img' and 'sticky' in self.getAttr('src', attrs)):
				self.current['sticky'] = True
			elif 'title' in className.split(' '):
				self.subMode = 'TITLE'
				href = self.getAttr('href', attrs)
				if 'showthread.php' in href:
					self.setTID(href)
				if 'unread' in className:
					self.current['new_post'] = True
			elif 'author' in className:
				self.subMode = 'AUTHOR'
			elif self.subMode == 'AUTHOR' and 'username' in className:
				self.subMode = 'STARTER'
			elif 'lastpostby' in className:
				self.subMode = 'LASTAUTHOR'
			elif self.subMode == 'LASTAUTHOR' and 'username' in className:
				self.subMode = 'LASTPOSTER'
				href = self.getAttr('href', attrs)
				if href:
					self.current['lastid'] = self.extractID('member.php', 'u', href)
		if self.mode == 'THREAD' and tag == 'div':
			self.depth += 1
		
	
	def handle_data(self,data):
		if data.strip(): self.mode, self.subMode, data.strip()
		if self.mode == 'THREAD':
			if not self.subMode:
				if data.strip() == 'Sticky:':
					self.current['sticky'] = True
			elif self.subMode == 'TITLE':
				self.current['title'] = self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'STARTER':
				self.current['starter'] = self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'LASTPOSTER':
				self.current['lastposter'] = self.revertCodes(data).strip()
				self.subMode = None
			
	
	def handle_endtag(self,tag):
		if tag == 'div':
			if self.mode == 'THREAD':
				self.depth -= 1
				if self.depth < 1:
					self.resetCurrent()

class VBForumParser(BaseParser):
	def __init__(self):
		BaseParser.__init__(self)
		self.handle_starttag = self.normalStarttag
		self.handle_endtag = self.normalEndtag
		self.parseMode = 'NORMAL'
		self.error = ''
	
	def feed(self,data):
		data = data.split('<!-- main -->',1)[-1].split('<!-- /main -->',1)[0]
		if not 'forumrow table' in data:
			self.handle_starttag = self.tableStarttag
			self.handle_endtag = self.tableEndtag
			self.parseMode = 'TABLE'
		BaseParser.feed(self,data)
		
	def tableStarttag(self,tag,attrs):
		if tag == 'tr':
			self.depth += 1
		href = self.getAttr('href', attrs)
		if href and 'forumdisplay.php' in href:
			if self.mode == 'FORUM':
				self.resetCurrent()
				self.mode = 'FORUM'
				self.subMode = 'TITLE'
				self.current['subforum'] = True
				self.setFID(href)
			else:
				self.mode = 'FORUM'
				self.subMode = 'TITLE'
				self.setFID(href)
		
		className = self.getAttr('class', attrs)
		if className and 'error' in className:
			self.mode = 'ERROR'
			self.depth = 1
			return
	
	def tableEndtag(self,tag):
		if tag == 'tr':
			self.depth -= 1
			if self.depth < 1:
				self.resetCurrent()
				self.mode = None
		elif self.mode == 'ERROR' and tag == 'div':
				self.depth -= 1
				if self.depth < 1:
					print 'ERROR' + self.error
					error = self.error.split('Message')[-1]
					raise Exception(error.strip())
			
	def normalStarttag(self,tag,attrs):
		if tag == 'div':
			className = self.getAttr('class', attrs)
			if className:
				if className == 'forumrow table':
					self.mode = 'FORUM'
					self.depth += 1
					return
				elif 'forumhead' in className:
					self.resetCurrent(False)
				
			if self.mode == 'FORUM' or self.mode == 'ERROR': self.depth += 1
		if self.mode == 'FORUM':
			className = self.getAttr('class', attrs)
			if className == 'forumtitle' and not tag == 'a':
				self.subMode = 'TITLE'
			elif className == 'forumdescription':
				self.subMode = 'DESC'
			elif className == 'subforum':
				self.resetCurrent()
				self.mode = 'SUBFORUM'
				self.current['subforum'] = True
			elif tag == 'a' and self.subMode == 'TITLE':
				href = self.getAttr('href', attrs)
				if 'forumdisplay' in href:
					self.setFID(href)
					
		elif self.mode == "SUBFORUM":
			if not self.subMode:
				className = self.getAttr('class', attrs)
				if className == 'subforum':
					self.mode = 'SUBFORUM'
					self.current['subforum'] = True
			if tag == 'a':
				href = self.getAttr('href', attrs)
				if 'forumdisplay' in href:
					self.setFID(href)
					self.subMode = 'TITLE'
					
	
	def handle_data(self,data):
		if self.mode == 'FORUM':
			if self.subMode == 'TITLE':
				self.current['title'] = self.revertCodes(data).strip()
				if self.parseMode == 'TABLE':
					if self.current.get('subforum'):
						self.subMode = None
					else:
						self.subMode = 'DESC'
				else:
					self.subMode = None
			elif self.subMode == 'DESC':
				desc = self.revertCodes(data).strip()
				if desc:
					self.current['description'] = desc
					self.subMode = None
		elif self.mode == 'SUBFORUM' and self.subMode == 'TITLE':
			self.current['title'] = self.revertCodes(data).strip()
			self.resetCurrent()
			self.mode = 'SUBFORUM'
		elif self.mode == 'ERROR':
			self.error += self.revertCodes(data).strip() + ' '
			
	
	def normalEndtag(self,tag):
		if tag == 'div':
			if self.mode == 'FORUM':
				self.depth -= 1
				if self.depth < 1:
					self.resetCurrent()
				
	def setFID(self,data):
		ID = self.extractID('forumdisplay.php','f',data)
		if ID: self.current['forumid'] = ID
			