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
		print a #.get('postid')
	return p
	
class DoneException(Exception): pass
	
class BaseParser(HTMLParser.HTMLParser):
	def __init__(self):
		self.all = []
		self.revertCodesRE = re.compile(r'(%)(#?[\w\d]+;)')
		self.imgSrcRE = re.compile(r'src="([^"]*?)"')
		self.aHrefRE = re.compile(r'href="([^"]*?)"')
		self.tagRE = re.compile(r'<[^>]*?>')
		self.badCommentRE = re.compile(r"<\!(?!-)[^>]*?>")
		self.tagFixRE1 = re.compile(r'(="[^"]*?)"(?! )([^"]*?" )')
		self.tagFixRE2 = re.compile(r'(="[^"]*?" )([^"]*?)(?<!=)"(\w+=)(\w+)')
		self.tagFixRE3 = re.compile(r"(='[^']*?)'([^'=]*?' )")
		self.tagFixRE4 = re.compile(r'(")(\w+=")')
		self.tagFixRE5 = re.compile(r'(?<!=)"" ')
		self.badTagRE = re.compile(r'<(?P<tag>\w{2,})(?: |>)(?:[^>]*?>)?.*?</(?P=tag)(?!>)')
		self.scriptRemover = re.compile(r'<script[^>]*?>.*?</script>(?s)')
		self.styleRemover = re.compile(r'<style[^>]*?>.*?</style>(?s)')
		self.bodyTagRE = re.compile(r'<body[^>]*?>(?i)')
		self.bodyEndTagRE = re.compile(r'</body>(?i)')
		self.emptyTagRE = re.compile(r'(<(?:area|base|basefont|br|col|frame|hr|img|input|isindex|link|meta|param)[^>]*?(?<!/))(>)')
		self.current = None
		self.mode = None
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
	
	def done(self):
		raise DoneException()
	
	def feed(self,data):
		#open('/home/ruuk/test2.txt','w').write(data.encode('ascii','replace'))
		data = self.bodyEndTagRE.split(self.bodyTagRE.split(data,1)[-1],1)[0]
		data = self.badCommentRE.sub('',data)
		data = self.badTagRE.sub(r'\g<0>>',data)
		data = self.tagRE.sub(self.cleanTag,data)
		data = self.scriptRemover.sub('',data)
		data = self.styleRemover.sub('',data)
		data = re.sub(r"(&)(#?[\w\d]+;)(?=[^<]*?<)",r'%\2',data)
		data = self.emptyTagRE.sub(r'\1/\2',data)
		#open('/home/ruuk/test.txt','w').write(data.encode('ascii','replace'))
		HTMLParser.HTMLParser.feed(self,data)
	
	def revertCodes(self,data):
		return convertHTMLCodes(self.revertCodesRE.sub(r'&\2',data))
	
	def resetCurrent(self,add=True):
		if add:
			if self.current:				
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
		
	def getList(self,data,*args,**kwargs):
		if not isinstance(data,unicode): data = unicode(data,'utf8','replace')
		self.resetCurrent()
		self.all = []
		try:
			self.feed(data,*args,**kwargs)
		except DoneException:
			print 'PB HTMLParser terminated early'
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
		self.pidRE2 = re.compile(r'p=(\d+)')
		self.postTag = None
		self.currentStat = ''
		self.currentQuote = ''
		self.quoteMode = ''
		self.lastFont = ''
		self.parseMode = None
		self.parseTag = ''
		self.currentTag = None
		self.currentDepth = 0
		self.resetContent()
		self.lastStart = ''
		BaseParser.__init__(self)
		
	def resetContent(self):
		self.contentDepth = 0
		self.contentTag = ''
		self.subMode = None
		self.quoteMode = None
		self.currentQuote = ''
		self.currentStat = ''
		self.lastFont = ''
	
	def feed(self,data):
		data = data.split('<!-- closing div for above_body -->',1)[-1].split('<!-- closing div for body_wrapper -->',1)[0]
		data = data.split('<!-- controls above postbits -->',1)[-1].split('<!-- controls below postbits -->',1)[0]
		
		m = re.search('[\'" ]postbit[\'" ]',data)	
		if not m or m.start() < 0:
			print 'PB HTMLParser - Posts Table Mode'
			self.parseMode = 'TABLE'
			self.parseTag = 'tr'
		BaseParser.feed(self, data)
		
	def setPID(self,data,ret=False):
		if not data: return ''
		m = self.pidRE.search(data)
		if not m: m = self.pidRE2.search(data)
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
		
	def handle_comment(self,data):
		data = data.strip()
		#print data
		if self.parseMode == 'TABLE':
			if data == 'message':
				self.subMode = 'CONTENT'
				self.current['message'] = ''
			elif data == '/ message':
				self.resetContent()
			elif data == 'icon and title':
				self.subMode = 'TITLE'
			elif data == '/icon and title':
				self.subMode = None
			
	def handle_starttag(self,tag,attrs):
		className = self.getAttr('class', attrs)
		idName = self.getAttr('id', attrs)
		if self.parseMode == 'TABLE':
			if tag == 'tr':
				self.mode = 'POST'
		if className:
			if 'postbit' in className.split(' ') or (tag == 'li' and 'postbit' in className):
				self.mode = 'POST'
				self.postTag = tag
			elif self.subMode == 'CONTENT' and 'bbcode_quote' in className:
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
			elif self.subMode == 'CONTENT' and 'bbcode_description' in className:
				self.subMode = 'BLOCK'
		elif idName:
			if self.parseMode == 'TABLE' and 'postcount' in idName:
				name = self.getAttr('name', attrs)
				if name.isdigit():
					self.current['postnumber'] = name
					#print name
				else:
					self.subMode = 'POSTNUMBER'
				href = self.getAttr('href', attrs)
				self.setPID(href)
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
		elif self.subMode == 'CONTENT' and tag == 'font':
			color = self.getAttr('color', attrs)
			tag = ''
			if color:
				tag = '[color=%s]' % color
				self.lastFont = '[/color]'
			else:
				size = self.getAttr('size', attrs)
				if size:
					tag = '[size=%s]' % size
					self.lastFont = '[/size]'
			if self.quoteMode:
				if self.quoteMode == 'QUOTE': self.currentQuote += tag
			else:
				self.current['message'] += tag
			
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
				self.currentQuote += ';' + self.setPID(href, True) + ']\n'
				self.quoteMode = 'WAIT'
		
		self.checkCurrentTag(tag)
	
	def handle_data(self,data):
		dstrip = data.strip()
		if not dstrip: return
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
				self.current['postnumber'] = dstrip.replace('#','')
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
			elif (self.subMode == 'BLOCK' or (dstrip in ('HTML Code:','PHP Code:','Code:'))) and not self.quoteMode:
				if not self.subMode == 'BLOCK':
					tag = '\n'
				else:
					tag = ''
				self.subMode = 'BLOCK'
				if 'html' in data.lower():
					self.quoteMode = '[/html]'
					tag += '[html]'
				elif 'php' in data.lower():
					self.quoteMode = '[/php]'
					tag += '[php]'
				elif 'code' in data.lower():
					self.quoteMode = '[/code]'
					tag += '[code]'
				self.current['message'] += tag
			elif (self.subMode == 'CONTENT' and not self.quoteMode) or self.subMode == 'BLOCK':
				self.current['message'] += self.revertCodes(data).strip()
			elif self.subMode == 'SIGNATURE':
				self.current['signature'] += self.revertCodes(data).strip()
					
	def handle_endtag(self,tag):
		self.checkEndTag(tag)
		if self.subMode == 'CONTENT':
			if tag == 'br' or tag == 'div':
				if self.quoteMode == 'QUOTE':
					self.currentQuote  += '\n'
				else:
					self.current['message'] += '\n'
			elif tag == 'a' or tag == 'b' or tag == 'i' or tag == 'font':
				if tag == 'a':
					conv = '[/url]'
				elif tag == 'b':
					conv = '[/b]'
				elif tag == 'i':
					conv = '[/i]'
				elif tag == 'font':
					conv = self.lastFont
					self.lastFont = ''
				if not self.subMode == 'BLOCK' and self.quoteMode:
					if self.quoteMode == 'QUOTE':
						self.currentQuote += conv
				else:
					self.current['message'] += conv
			if tag == 'div' and self.quoteMode == 'QUOTE':
				self.quoteMode = None
				self.currentQuote += '[/quote]'
				self.current['message'] += self.currentQuote
				self.currentQuote = ''
		elif self.subMode == 'BLOCK':
			if tag == 'br':
				self.current['message'] += '\n'
		if self.parseMode == 'TABLE' and tag == self.parseTag:
			if self.current.get('postid') and self.current.get('message'):
				self.resetCurrent()
		elif tag == self.postTag:
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
				
		if self.subMode == 'BLOCK' and (tag == 'pre' or tag =='code'):
			if self.quoteMode:
				self.current['message'] += self.quoteMode
				self.subMode = 'CONTENT'
				self.quoteMode = None
		
class VBThreadParser(BaseParser):
	def __init__(self):
		BaseParser.__init__(self)
		self.parseMode = 'NORMAL'
		
	def feed(self,data):
		data = data.split('<!-- closing div for above_body -->',1)[-1].split('<!-- closing div for body_wrapper -->',1)[0]
		data = data.split('<!-- / controls above thread list -->',1)[-1].split('<!-- controls below thread list -->',1)[0]
		data = data.split('<!-- show threads -->',1)[-1]
		m = re.search('[\'" ]threadbit[\'" ]',data)	
		if not m or m.start() < 0:
			#print 'PB HTMLParser - No Threads'
			#return
			print 'PB HTMLParser - Threads Table Mode'
			self.parseMode = 'TABLE'
			self.parseTag = 'tr'
		BaseParser.feed(self, data)
		
	def setTID(self,data):
		ID = self.extractID('showthread.php','t',data)
		if id: self.current['threadid'] = ID
	
	def handle_starttag(self,tag,attrs):
		className = self.getAttr('class', attrs)
		if self.parseMode == 'TABLE':
			if tag == 'tr':
				self.mode = 'THREAD'
				return
			elif self.mode == 'THREAD':
				attrsStr =  str(attrs)
				if tag == 'a':
					href = self.getAttr('href', attrs)
					if 'showthread.php' in href and not 'goto' in href and not self.current.get('threadid'):
						self.setTID(href)
						self.subMode = 'TITLE'
				if 'member.php' in attrsStr:
					if not 'lastposter' in attrsStr:
						self.subMode = 'STARTER'
					else:
						self.subMode = 'LASTPOSTER'
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
		
		if self.mode == 'THREAD':
			if tag == 'div':
				self.depth += 1
			elif self.subMode == 'SUBSCRIBED' and tag == 'img':
					src = self.getAttr('src', attrs)
					if src and 'subscribed' in src: self.current['subscribed'] = True
		
	
	def handle_data(self,data):
		if self.mode == 'THREAD':
			if not self.subMode:
				if data.strip() == 'Sticky:':
					self.current['sticky'] = True
			elif self.subMode == 'TITLE':
				self.current['title'] = self.revertCodes(data).strip()
				self.subMode = None
			elif self.subMode == 'STARTER':
				self.current['starter'] = self.revertCodes(data).strip()
				self.subMode = 'SUBSCRIBED'
			elif self.subMode == 'LASTPOSTER':
				self.current['lastposter'] = self.revertCodes(data).strip()
				self.subMode = None
			
	
	def handle_endtag(self,tag):
		if self.parseMode == 'TABLE':
			if tag == 'tr':
				if self.mode == 'THREAD':
					#print self.current
					self.resetCurrent()
		elif tag == 'div':
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
		self.someFound = False
		self.setDelimeters()
	
	def setDelimeters(self):
		self.forumDelimeter = 'forumrow'
		
	def feed(self,data,in_threads=False):
		self.someFound = False
		data = data.split('<!-- main -->',1)[-1].split('<!-- /main -->',1)[0]
		data = data.split('<!-- closing div for above_body -->')[-1].split('<!-- closing div for body_wrapper -->')[0]
		#open('/home/ruuk/test.txt','w').write(data)
		if not 'forumrow' in data:
			if in_threads: return 
			self.handle_starttag = self.tableStarttag
			self.handle_endtag = self.tableEndtag
			self.parseMode = 'TABLE'
			print 'PB HTMLParser - Forums Table Mode'
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
		if self.someFound and (tag == 'form' or tag == 'input'):
			self.done()
		if tag == 'div':
			className = self.getAttr('class', attrs)
			if className:
				if self.forumDelimeter in className:
					self.mode = 'FORUM'
					self.depth += 1
					self.someFound = True
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
			elif not self.subMode:
				if tag == 'a':
					href = self.getAttr('href', attrs)
					if href and 'removesubscription' in href:
						self.current['subscribed'] = True
						
					
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
			if self.mode == 'FORUM' or self.mode == 'ERROR':
				self.depth -= 1
				if self.depth < 1:
					self.resetCurrent()
				
	def setFID(self,data):
		ID = self.extractID('forumdisplay.php','f',data)
		if ID: self.current['forumid'] = ID
		
class HTMLData(unicode):
	def __new__(self,value,tag):
		return unicode.__new__(self, value)
		
	def __init__(self,value,tag):
		self.tag = tag
		
class HTMLTag:
	revertCodesRE = re.compile(r'(%)(#?[\w\d]+;)')
	def __init__(self,tag,tag_text,attrs):
		self.tag = tag
		self.endtag = ''
		self.tagText = tag_text
		self.attrsList = attrs
		self.attrs = None
		self.depth = 0
		self.parent = None
		self.data = ''
		self.dataStack = []
		self.tagStack = []
		self.stack = []
		self.callback = None
		self.main = False
		self.postID = None
		self.startIndex = -1
		self.endIndex = -1
		self.sequenceIndex = 0
		
	def __str__(self):
		return self.tag
	
	def __repr__(self):
		return self.tagText
	
	def processAttrs(self):
		self.attrs = {}
		for a in self.attrsList: self.attrs[a[0]] = self.revertCodes(a[1])
		
	def getAttr(self,attr):
		if self.attrs == None: self.processAttrs()
		return self.attrs.get(attr,'')
	
	def getClasses(self):
		cls = self.getAttr('class')
		if not cls: return []
		return cls.split(' ')

	def revertCodes(self, data):
		return self.revertCodesRE.sub(r'&\2', data or '')

class HTMLEndTag:
	def __init__(self,start):
		self.tag = start.tag
		self.startTag = start
		
	def __repr__(self):
		return '</' + self.tag + '>'
	
class OrderedDict(dict): #Very simple. Will probably break if using some non overidden methods
	def __new__(self, *args, **kwargs):
		return dict.__new__(self, *args, **kwargs)
	
	def __init__(self, *args, **kwargs):
		self.orderedKeys = []
		dict.__init__(self, *args, **kwargs)
		
	def __setitem__(self,k,v):
		if not k in self.orderedKeys: self.orderedKeys.append(k)
		dict.__setitem__(self,k,v)
		
	def __delitem__(self, k):
		if k in self.orderedKeys:  del self.orderedKeys[self.orderedKeys.index(k)]
		return dict.__delitem__(self, k)
	
	def items(self):
		ret = []
		for k in self.orderedKeys:
			ret.append((k,self[k]))
		return ret
		
class ListSlice(list):
	def __new__(self, *args, **kwargs):
		return list.__new__(self, *args, **kwargs)
	
	def __init__(self,wlist,s,e):
		self.wlist = wlist
		self.start = s
		self.end = e
		self._isSet = False
		
	def _setSelf(self):
		if self._isSet: return
		self += self.wlist[self.start:self.end]
		self._isSet = True
		
	def __getitem__(self, *args, **kwargs):
		self._setSelf()
		return list.__getitem__(self, *args, **kwargs)
	
	def __getslice__(self, *args, **kwargs):
		self._setSelf()
		return list.__getslice__(self, *args, **kwargs)
	
	def __iter__(self, *args, **kwargs):
		if self._isSet: return list.__iter__(self)
		return self.customIter()
		
	def customIter(self):
		for i in range(self.start,self.end):
			yield self.wlist[i]
		
	def __len__(self):
		return self.end - self.start
	
	def __contains__(self, val):
		if self._isSet: return list.__contains__(self,val)
		
		for i in range(self.start,self.end):
			if self.wlist[i] == val: return True
		return False
	
	def index(self, *args, **kwargs):
		self._setSelf()
		return list.index(self, *args, **kwargs)
	
class AdvancedParser(BaseParser):
	def __init__(self):
		BaseParser.__init__(self)
		self.lastTag = None
		self.stack = []
		self.sequence = []
		self.linkRE = None
		self.forumType = 'u0'
		self.isGeneric = False
		self.dataCleanerRE = re.compile('[\n\r\t]')
		self.tagIndex = 0
	
	def getForumType(self):
		if self.forumType[-1].isdigit(): return 'u0'
		return self.forumType
	
	def getRE(self,html):
		mx = 0
		pick = None
		ftpick = 'u0'
		for ft,r in self.linkREs.items():
			ct = len(r.findall(html) or [])
			if ct > mx:
				mx = ct
				pick = r
				ftpick = ft
		if not pick:
			for ft,r in self.genericLinkREs.items():
				ct = len(r.findall(html) or [])
				if ct > mx:
					mx = ct
					pick = r
					ftpick = ft
		self.linkRE = pick
		self.forumType = ftpick[:2]
		self.isGeneric = self.forumType[1].isdigit()
		
	def handle_starttag(self,tag,attrs):
		tag = HTMLTag(tag,self.get_starttag_text(),attrs)
		tag.startIndex = self.tagIndex
		tag.sequenceIndex = len(self.sequence)
		self.tagIndex += 1
		if self.stack: tag.parent = self.stack[-1]
		self.stack.append(tag)
		tag.depth = len(self.stack)
		self.sequence.append(tag)
		self.handleStartTag(tag)
	
	def handle_data(self,data):
		if not data.strip(): return
		data = self.dataCleanerRE.sub('',self.revertCodes(data))
		tag = self.stack and self.stack[-1] or None
		data = HTMLData(data,tag)
		self.sequence.append(data)
		if tag:
			tag.data = HTMLData(tag.data + data,tag)
		#	tag.stack.append(data)
			tag.dataStack.append(data)
		self.handleData(tag, data)
	
	def handle_endtag(self,tag):
		if not self.stack: return
		endTag = self.stack.pop()
		endTag.endtag = tag
		endT = HTMLEndTag(endTag)
		endTag.stack = ListSlice(self.sequence,endTag.sequenceIndex+1,len(self.sequence))
		self.sequence.append(endT)
		#print repr(endTag)
#		if not endTag.tag == tag:
#			print 'UNMATCHED ENDTAGS AT (INDEX: ' + str(self.tagIndex) + ') - GOT: ' + tag + ' EXPECTED: ' + endTag.tag
#			if self.stack and self.stack[-1].tag == tag:
#				self.handle_broken_endtag(tag)
#			else:
#				self.stack.append(endTag)
#				return
			
			#if self.stack: self.stack.pop()
		endTag.endIndex = self.tagIndex
		self.tagIndex += 1
		if endTag.parent:
			#print 'parent ' + repr(endTag.parent)
			endTag.parent.dataStack += endTag.dataStack
			endTag.parent.tagStack.append(endTag)
			endTag.parent.tagStack += endTag.tagStack
			#endTag.parent.stack.append(endTag)
			#endTag.parent.stack += endTag.stack
			#endTag.parent.stack.append(endT)
		if endTag.callback: endTag.callback(endTag)
		self.handleEndTag(endTag)
		self.lastTag = endTag
		
	def handle_broken_endtag(self,tag):
		if not self.stack: return
		endTag = self.stack.pop()
		if not endTag.tag == tag:
			print '2nd UNMATCHED ENDTAGS AT (INDEX: ' + str(self.tagIndex) + ') - GOT: ' + tag + ' EXPECTED: ' + endTag.tag
#			if self.stack:
#				print self.stack[-1].tag
#				self.stack.pop()
		endTag.endIndex = self.tagIndex
		self.tagIndex += 1
		if endTag.parent:
			endTag.parent.dataStack += endTag.dataStack
			endTag.parent.tagStack.append(endTag)
			endTag.parent.tagStack += endTag.tagStack
			endTag.parent.stack.append(endTag)
			endTag.parent.stack += endTag.stack
			endTag.parent.stack.append(HTMLEndTag(endTag.tag))
		if endTag.callback: endTag.callback(endTag)
		self.handleEndTag(endTag)
		self.lastTag = endTag
	
	def handleStartTag(self,tag):
		pass
	
	def handleEndTag(self,tag):
		pass
	
	def handleData(self,tag,data):
		pass
	
class GeneralForumParser(AdvancedParser):
	def __init__(self):
		AdvancedParser.__init__(self)
		self.lastForumTag = None
		self.lastForum = None
		self.forumDepth = 0
		self.maxForumDepth = 0
		self.subsSet = False
		self.forums = []
		self.linkREs = {	'vb': re.compile('(?:^|")(?:forumdisplay.php|forums)(?:\?|/)(?:[^"\']*?f=)?(?P<id>\d+)'),
							'fb': re.compile('(?:^|")viewforum.php?[^"\']*?(?<!;)(?:f|id)=?(?P<id>\d+)'),
							'mb': re.compile('(?:^|")forum-(?P<id>\d+).html'),
							'pb': re.compile('(?:^|")(?:\W+)?viewforum.php?[^"\']*?f=?(?P<id>\d+)'),
							'ip': re.compile('/forum/(?P<id>\d+)-[^"\']*?(?:"|\'|$)')
						}
		
		self.splits = {	'vb':[ (re.compile('<!--[^>]*?SUBSCRIBED FORUMS[^>]*?-->(?i)'),re.compile('<!--[^>]*?END SUBSCRIBED FORUMS[^>]*?-->(?i)')) ]
					}
		
		self.genericLinkREs = {	'u0':re.compile('(?:^|"|\')(?P<url>[^"\']*?forum\w*\.php\?[^"\']*?(?:f|id|forumid|fid)=(?P<id>\d+)[^"\']*?)(?:$|"|\')') }
		self.linkRE = None
	
	def splitHTML(self,html):
		splits = self.splits.get(self.getForumType(),[])
		for s,e in splits:
			html = e.split(s.split(html,1)[-1],1)[0]	
		return html
	
	def getForums(self,html):
		if not isinstance(html,unicode): html = unicode(html,'utf8','replace')
		self.forums = []
		self.reset()
		self.getRE(html)
		html = self.splitHTML(html)
		self.feed(html)
		self.reset()
		if self.subsSet: return self.forums
		if self.maxForumDepth == 0: return self.forums
		keepAll = False
		if self.isGeneric:
			keepAll = True
		forums = []
		for f in self.forums:
			if self.maxForumDepth - f['depth'] < 2 or keepAll:
				if f['depth'] == self.maxForumDepth: f['subforum'] = True
				del f['depth']
				forums.append(f)
		return forums
		
	def handleStartTag(self,tag):
		pass
	
	def handleData(self,tag,data):
		pass
				
	def handleEndTag(self,tag):
		if tag and tag.tag == 'a':
			href = tag.getAttr('href')
			if href:
				m = self.linkRE.search(href)
				if m:
					mdict = m.groupdict()
					forum = {'forumid':mdict.get('id',''),'title':''.join(tag.dataStack),'depth':self.forumDepth,'url':mdict.get('url',''),'tag':tag}
					for t in reversed(self.stack):
						if t.tag in ('td','li','div'):
							t.callback = self.checkDesc
							break
					if 'sub' in tag.getAttr('class') or (self.lastTag and 'sub' in self.lastTag.getAttr('class')):
							forum['subforum'] = True
							self.subsSet = True
					for t in reversed(self.stack):
						if 'subforum' in t.getAttr('class'):
							forum['subforum'] = True
						if t.tag in ('td','li','div'):
							if 'forum' in t.getAttr('class'):
								t.callback = self.checkDesc
								if 'sub' in t.getAttr('class') or t.main:
									forum['subforum'] = True
									self.subsSet = True
								t.main = True
							if self.lastForumTag and self.lastForumTag.depth + 1 < tag.depth:
								#forum['subforum'] = True
								self.forumDepth +=1
								if self.forumDepth > self.maxForumDepth:
									self.maxForumDepth = self.forumDepth
							elif self.lastForumTag and self.lastForumTag.depth - 1 > tag.depth: 
								#forum['subforum'] = True
								self.forumDepth -=1
							forum['depth'] = self.forumDepth
							break
					self.lastForumTag = tag
					self.lastForum = forum
					self.forums.append(forum)
					#print tag.depth, forum
	
	def checkDesc(self,tag):
		if len(tag.dataStack) > 1 and not self.lastForum['tag'] == tag:
			self.lastForum['description'] = tag.dataStack[1]

class GeneralThreadParser(AdvancedParser):
	def __init__(self):
		AdvancedParser.__init__(self)
		self.linkREs = {	'vb':re.compile('(?:^|")(?:showthread.php|threads)(?:\?|/)(?:[^"]*?t=)?(?P<id>\d+)'),
							'fb':re.compile('(?:^|")viewtopic.php?[^"]*?(?<!;|p)(?:f|id)=?(?P<id>\d+)'),
							'mb':re.compile('(?:^|")thread-(?P<id>\d+).html'),
							'pb':re.compile('(?:^|")(?:\W+)?viewtopic.php?[^"\']*?f=(?P<fid>\d+)[^"\']*?t=(?P<id>\d+)'),
							'ip':re.compile('/topic/(?P<id>\d+)-[^"\']*?(?:"|\'|$)')
						}
		
		self.genericLinkREs = {	'u0':re.compile('(?:^|"|\')(?P<url>[^"\']*?(?:thread|topic)\w*\.php\?[^"\']*?(?:t|id|threadid|tid)=(?P<id>\d+)[^"\']*?)(?:$|"|\')') }
		self.linkRE = None
		self.pages = {}
		
	def setDefaults(self):
		self.threads = []
		self.ids = {}
		self.sticky = False
		self.stickyTag = None
		self.pages = None
	
	def getPages(self,url,html):
		if not url: return
		url = url.rsplit('/',1)[-1]
		self.pages = {}
		for p in re.finditer('<a[^>]*?href="(?P<url>[^"]*?%s[^"]*?)"[^>]*?>[^<\d]*?(?P<page>\d+)[^<\d]*?</a>' % re.escape(url),html):
			p = p.groupdict()
			self.pages[p.get('page')] = p.get('url')
	
	def getThreads(self,html,url=''):
		if not isinstance(html,unicode): html = unicode(html,'utf8','replace')
		self.setDefaults()
		self.reset()
		self.getPages(url, html)
		#if self.reVB.search(html): pass
		#elif self.reFluxBB.search(html): self.linkRE = self.reFluxBB
		#elif self.reMyBB.search(html): self.linkRE = self.reMyBB
		self.getRE(html)
		self.feed(html)
		self.reset()
		return self.threads
		
	def setUsers(self,dstrip):
		if not dstrip: return
		if dstrip.lower().startswith('view') or dstrip.lower().endswith('profile'): return
		if self.threads:
			t = self.threads[-1]
			if not t.get('starter'):
				t['starter'] = dstrip.split('by ')[-1]
			elif not t.get('lastposter'):
				t['lastposter'] = dstrip.split('by ')[-1]
				
	def handleStartTag(self,tag):
		if re.search('(?:^|\W|_)sticky',tag.getAttr('class')):
			self.stickyTag = tag
	
	def handleData(self,tag,data):
		dstrip = data.strip()
		if not dstrip: return
		if dstrip.lower() == 'sticky:' or dstrip.lower() == 'pinned': #pinned for ipboard
			self.sticky = True
		elif 'by ' in dstrip:
			self.setUsers(dstrip)
		else:
			if self.threads:
				t = self.threads[-1]
				if not t.get('title'): t['title'] = dstrip
				
	def handleEndTag(self,tag):
		if tag == self.stickyTag:
			thread = self.getLastThread()
			if thread and not thread.get('sticky'):
				ttag = thread.get('tag')
				for s in self.stickyTag.stack:
					#print repr(s), repr(ttag), ' -'
					if s == ttag:
						thread['sticky'] = True
						break
			self.stickyTag = None
		if tag and tag.tag == 'a':
			href = tag.getAttr('href')
			if href:
				m = self.linkRE.search(href)
				if m:
					mdict = m.groupdict()
					ID = mdict.get('id')
					if not ID in self.ids:
						self.ids[ID] = 1
						thread = {'threadid':ID,'title':''.join(tag.dataStack),'sticky':self.sticky,'tag':tag,'url':mdict.get('url')}
						self.sticky = False
						#self.stickyTag = None
						self.threads.append(thread)
						#print tag.depth, forum
					elif self.isGeneric:
						if self.threads:
							ds = ''.join(tag.dataStack)
							if re.search('\w',ds) and not re.match('^[\d|W]+$',ds):
								#print ds.encode('ascii','replace')
								self.threads[-1]['title'] += ds
				elif 'member' in href or 'user' in href:
					self.setUsers(''.join(tag.dataStack).strip())
		else:
			onclick = tag.getAttr('onclick')
			if 'member' in onclick or 'user' in onclick:
				self.setUsers(''.join(tag.dataStack).strip())
	
	def getLastThread(self):
		if self.threads: return self.threads[-1]
		
	def show(self,tag):
		if len(tag.dataStack) > 1:
			self.lastForum['description'] = tag.dataStack[1]
			
class GeneralPostParser(AdvancedParser):
	def __init__(self):
		AdvancedParser.__init__(self)
		self.setDefaults()
		
		self.wsRE = re.compile('[\r\t]')
		self.excessiveNL = re.compile('\n{2,}')
		self.numberRE = re.compile('^([\d,]+)$')
		self.pidModeRE = re.compile('["\'\(](\w*?)(\d+)["\'\)]')
		
		self.linkREs = {	'vb': re.compile('(?:^|")showpost\.php(?:\?|/)(?:[^"\']*?p=)?(?P<id>\d+)'), # threads/70389-Name-Changes?p=1134465&amp;viewfull=1#post1134465
							'vb2': re.compile('(?:^|")(?:showthread\.php\?(?:t=)?|threads/)\d+[^"\']*?p=(?P<id>\d+)'),
							'fb': re.compile('(?:^|")viewtopic\.php?[^"\']*?(?<!;)pid=(?P<id>\d+)'),
							'mb': re.compile('(?:^|")thread-\d+-post-(?P<id>\d+)\.html'),
							'pb': re.compile('(?:^|")#p(?P<id>\d+)'),
							'ip':re.compile('/topic/\d+-[^"\']*?/#entry(?P<id>\d+)(?:"|\'|$)')
						}
		self.genericLinkREs = {}
#		self.genericLinkREs = { 'u0':re.compile('(?:^|"|\')(?P<url>[^"\']*?post\w*\.php\?[^"\']*?(?:p|id|postid|pid)=(?P<id>\d+)[^"\']*?)(?:$|"|\')'),
#								'u1':re.compile('(?:^|"|\')(?P<url>[^"\']*?member\.php\?\w=\d+[^"\']*?)(?:$|"|\')'),
#								'u2':re.compile('(?:^|"|\')(?P<url>[^"\']*?pm\.php\?\w=\d+[^"\']*?)(?:$|"|\')')
#						}
		
		self.postREs = [	#(None,re.compile('^#?\d+$')),
							('postnumber',re.compile('^#?(\d+)?$')),
							(None,re.compile('^by$')),
							#(None,re.compile('^#$')),
							('joindate',re.compile('^(?:joined|registered|join date)(?! user):?( .+)?(?i)')),
							('labeledstatus',re.compile('^group:?( .+)?(?i)')),
							('date',re.compile('\d+-\d+-\d+')),
							('date',re.compile('\d+(?:\w\w), \d{4}')),
							('date',re.compile('\w+ \d{1,2}:\d{2}')),
							('date',re.compile('\d{1,2}:\d{2} \wm(?i)')),
							('date',re.compile('[\d\w]+ \w+ ago$(?i)')),
							('date',re.compile('\d{1,2}\w\w \w+ \d+')),
							('date',re.compile('\w+ \d{1,2}(?:\w{2})?, \d{4}')),
							('date',re.compile('\w+day, \d{1,2}:\d{1,2}')),
							(None,re.compile('^post:(?i)')),
							('user',re.compile('^.*\w.*$')),
							('postcount',re.compile('^posts:?( [\d,]+)?(?i)')),
							('postcount',re.compile('^([\d,]+) posts(?i)')),
							('location',re.compile('^(?:location|from):?( .+)?(?i)')),
							('reputation',re.compile('^reputation:( \d+)?(?i)')),
							('status',re.compile('^group:?( .+)?(?i)')),
							('status',re.compile('(^.{1,40}$)')),
							('postcount',re.compile('\w+: ([\d,]+)(?i)')),
							('title',re.compile('^re: (?i)'))
						]
		
	def setDefaults(self):
		self.posts = []
		self.linkRE = None
		self.ids = {}
		self.lastPost = None
		self.bottom = 999
		self.bottomTag = None
		self.bottomTagTag = ''
		self.lastStack = []
		self.forumType = 'u0'
		self.lastUnset = ''
		self.mode = 'NORMAL'
		self.pidTags = OrderedDict()
		
	def getPosts(self,html):
		if not isinstance(html,unicode): html = unicode(html,'utf8','replace')
		self.setDefaults()
		self.reset()
		#if self.reVB.search(html): pass
		#elif self.reFluxBB.search(html): self.linkRE = self.reFluxBB
		#elif self.reMyBB.search(html): self.linkRE = self.reMyBB
		self.getRE(html)
		if not self.linkRE: self.mode = 'PID'
		print 'Post Parsing Mode: ' + self.mode
		print 'Post Forum Type: ' + self.forumType
		self.feed(html)
		if self.mode == 'PID':
			return self.getPIDPosts()
		if not self.posts:
			raise Exception('Couldn\'t parse any posts')
		if not self.posts[-1].get('data'):
			self.getLastData(self.posts[-1])
		for p in self.posts:
			data = self.setDatas(p)
			p['message'] = data and self.excessiveNL.sub('\n\n',self.wsRE.sub('',''.join(data)).strip())
			if 'data' in p: del p['data']
			
		self.reset()
		return self.posts
		
	def getPIDPosts(self):
		maxct = 0
		for k,v in self.pidTags.items():
			#print k + ': ' + str(len(v))
			#print v
			ct = len(v)
			if ct > maxct: maxct = ct
		for k,v in self.pidTags.items():
			ct = len(v)
			if ct + 1 >= maxct:
				tags = []
				for t in v:
					if not t in tags: tags.append(t)
				self.posts.append({'postid':k,'tags':tags})
		for p in self.posts:
			tags = p['tags']
			#print tags
			new = []
			for t in tags:
				parent = t
				while not parent.tag in ['div','tr','dl','li']:
					if not parent.parent:
						parent = None
						break
					parent = parent.parent
				else:
					t = parent
				new.append(t)
			newnew = []
			for t in new:
				for s in t.stack:
					for n in new:
						if not t in newnew and n == s:
							#print t
							newnew.append(t)
							break
							break
					
			p['data'] = []
			for t in newnew: p['data'] += t.stack
			#print p['tags']
			#for t in p['data']: print repr(t)
			#print repr(t)
			#print t.stack
			data = self.setDatas(p)
			p['message'] = data and self.excessiveNL.sub('\n\n',self.wsRE.sub('',''.join(data)).strip())
			del p['tags']
			del p['data']
			#print '--------------------------------------------------------------------'		
					
		return self.posts
			
	def getLastData(self,p):
		tag = p.get('tag')
		if p['bottom'].tag in ['dl','li','table']:
			p['data'] = p['bottom'].stack
			return
		stack = p['bottom'].stack
		ct = stack.index(tag)
		point = 0
		while ct > 0:
			s = stack[ct]
			if hasattr(s,'depth') and s.depth <= self.bottom:
				#print repr(s) + ' ' + str(s.depth)
				point = ct
				break
			ct -= 1
		bottom = stack[point]
		#print repr(bottom)
		while not hasattr(bottom,'stack'):
			point += 1
			bottom = stack[point]
			#print repr(bottom)
		p['data'] = bottom.stack
		#print bottom.depth
		#print '- ' + repr(bottom) + ' ' + bottom.endtag
#		if not tag: return
#		last = None
#		while False #self.lastStack:
#			t = self.lastStack.pop()
#			print t.stack.index(tag)
#			if last and t.stack and tag in t.stack and t.stack.index(tag) > 12:
#				#print "TESF"
#				#if last: print last.dataStack
#				p['data'] = last.stack
#				break
#			last = t
	
	def setDatas(self,p):
		dREs = self.postREs[:]
		if self.forumType == 'pb': dREs.pop(0)
		newData = []
		last = ''
		self.lastUnset = ''
		for d in p.get('data',[]):
			newData,last = self.handleDataItem(d, p, dREs, newData,last)
		return newData
					
	def handleDataItem(self,d,p,dREs,newData, last):
		if isinstance(d,HTMLTag):
			if d.tag == 'img':
				src = d.getAttr('src')
				if 'avatar' in repr(d).lower():
					p['avatar'] = src or ''
				elif 'offline' in repr(d):
					p['online'] = False
				elif 'online' in src:
					p['online'] = True
				elif src.startswith('http'):
					newData.append(' [img]'+src+'[/img] ')
			elif d.tag == 'embed':
				src = d.getAttr('src')
				if src: newData.append('[url='+src+']'+(d.data or 'EMBED')+'[/url]')
			elif d.tag in ('div','tr','table','ul','ol','blockquote','pre'):
				newData.append('\n')
			elif d.tag == 'li':
				newData.append('    * ') 
				
#			for x in d.stack:
#				newData,last = self.handleDataItem(x, p, dREs, newData, last)
		elif isinstance(d,HTMLEndTag):
			if d.tag in ('div','tr','table','ul','ol','blockquote','pre','br'):
				newData.append('\n')
		else:
			if d.strip():
				if d.tag == p.get('usedtag'): return newData, last
				#print d.encode('ascii','replace')
				for i in range(0,len(dREs)):
					val,dre = dREs[i]
					dstrip = d.strip()
					m = dre.search(dstrip)
					if m:
						#print d.encode('ascii','replace')
						if not val:
							#print 'n ' + d.encode('ascii','replace')
							d = ''
							last = ''
						elif val == 'status':
							#print 's ' + d.encode('ascii','replace')
							if m.group(1):
								user = m.group(1).strip()
								if last == 'user' and re.search('\w',d) and not d.tag.tag == 'a' and user != p.get('user',''):
									#print user.encode('ascii','replace') + ' : ' + p.get('user','').encode('ascii','replace')
									if user: p[val] = user
								else:
									if user == p.get('user') and not p.get('status'):
										last = 'user'
										break
									continue
						elif val == 'labeledstatus':
							if m.group(1):
								status = m.group(1).strip()
								if status: p['status'] = status
						elif val == 'date':
							#print 'd ' + d.encode('ascii','replace')
							if not val in p:
								p[val] = dstrip
							elif p[val].endswith(','):
								p[val] += dstrip
							elif self.lastUnset:
								p[self.lastUnset] = dstrip
								self.lastUnset = None
							else:
								if p[val] == dstrip:
									last = val
									break
								else:
									newData.append(d)
							last = val
							break #leave the re to skip other dates
						elif val == 'postnumber' and val in p:
							if self.lastUnset:
								p[self.lastUnset] = dstrip
								self.lastUnset = None
							else:
								break #Eat the postnumber if already set and don't remove in case we just got #
						elif m.groups():
							#print 'g ' + d.encode('ascii','replace')
							if not val in p:
								mg1 = m.group(1)
								if mg1: mg1 = mg1.strip()
								p[val] = mg1
								if not p[val]: last = val
								if not mg1: self.lastUnset = val
							else:
								continue
						else:
							#print 'ng ' + d.encode('ascii','replace')
							if not val in p:
								p[val] = dstrip
							else:
								continue
						
						dREs.pop(i)
						#if self.forumType != 'pb': newData = []
						#print d.encode('ascii','replace')
						last = val
						break
				else:
					if self.lastUnset:
							#print 'd ' + d.encode('ascii','replace')
						#print d.encode('ascii','replace') + self.lastUnset
						p[self.lastUnset] = dstrip
						self.lastUnset = ''
					elif d.tag.tag.startswith('h') or d.tag.tag == 'strong':
						if not p.get('title'):
							p['title'] = dstrip
							#if self.forumType != 'pb': newData = []
						else:
							newData.append(d)
					elif d.tag.tag == 'embed':
						pass
					elif d.lower() == 'offline':
						p['online'] = False
					elif d.lower() == 'online':
						p['online'] = True
					elif d.tag.tag == 'a':
						href = d.tag.getAttr('href')
						if href and not 'javascript:' in href and not href.startswith('#'):
							newData.append('[url='+href+']'+d+'[/url]')
					elif d.tag.tag == 'li':
						newData.append(d + '\n')
					else:
						newData.append(d)	
		return newData, last
		
	def handleStartTag(self,tag):
		pass
	
	def handleData(self,tag,data):
		pass
				
	def checkPost(self,tag):
		href = tag.getAttr('href')
		if href:
			m = self.linkRE.search(href)
			if m:
				ID = m.group(1)
				if not ID in self.ids:
					usedTag = None
					postnumber = ''.join(tag.dataStack)
					title = postnumber
					if not '#' in postnumber and not postnumber.isdigit():
						postnumber = ''.join(self.lastTag.dataStack)
					if not '#' in postnumber and not postnumber.isdigit():
						if self.forumType != 'pb' and not self.isGeneric: return
						if not title:
							title = postnumber
							usedTag = self.lastTag
						else:
							usedTag = tag
						postnumber = ''
							
					post = {'postid':ID,'postnumber':postnumber.replace('#',''),'usedtag':usedTag,'tag':tag}
					if title and not postnumber: post['title'] = title
					if self.forumType == 'pb': post['status'] = ' '
					self.lastStack = self.stack[:]
					self.ids[ID] = post
					self.posts.append(post)
					if self.lastPost:
						bottomTag = self.lastPost['bottom']
						#print bottomTag.depth
						if bottomTag.depth < self.bottom: self.bottom = bottomTag.depth
						self.lastPost['data'] = bottomTag.stack
						#print '- ' + repr(bottomTag) + ' ' + bottomTag.endtag
					self.lastPost = post
					return
				
	def handleEndTag(self,tag):
		if self.mode == 'NORMAL':
			self.normalHandleEndTag(tag)
		else:
			self.pidHandleEndTag(tag)
			
	def normalHandleEndTag(self,tag):
		if tag and tag.tag == 'a':
			self.checkPost(tag)
		elif self.lastPost:
			if tag.tag in ['div','tr','dl','li','table'] and self.lastPost['tag'] in tag.stack:
				#print repr(tag)
				bottom = self.lastPost.get('bottom')
				if not bottom or not bottom.tag in ['dl','li','table']: self.lastPost['bottom'] = tag
			
	
	def pidHandleEndTag(self,tag):
		for w,pid in self.pidModeRE.findall(repr(tag)):
			if pid in self.pidTags:
				self.pidTags[pid].append(tag)
			else:
				self.pidTags[pid] = [tag]
			if w == 'p': self.pidTags[pid].append(tag)
	
	def show(self,tag):
		if len(tag.dataStack) > 1:
			self.lastForum['description'] = tag.dataStack[1]