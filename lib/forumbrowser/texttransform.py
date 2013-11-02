import re, textwrap, htmlentitydefs
from lib import util
from lib import chardet

DEBUG = util.DEBUG

T = util.T

def cUConvert(m): return unichr(int(m.group(1)))
def cTConvert(m): return unichr(htmlentitydefs.name2codepoint.get(m.group(1),32))

def convertHTMLCodes(html,FB=None,encoding=None):
	if not encoding:
		if FB:
			encoding = FB.getEncoding()
		else:
			encoding = 'utf-8'
	try:
		html = html.decode(encoding).encode('utf-8')
		return html
	except:
		detected_encoding = chardet.detect(html)
		if util.DEBUG: util.LOG(detected_encoding)
		try:
			html = html.decode(detected_encoding['encoding']).encode('utf-8')
			if FB: FB.updateEncoding(detected_encoding['encoding'],detected_encoding['confidence'])
		except:
			html = html.encode('utf-8','replace')
			
	try:
		html = re.sub('&#(\d{1,5});',cUConvert,html)
		html = re.sub('&(\w+?);',cTConvert,html)
	except:
		pass
	return html
	
######################################################################################
# Message Converter
######################################################################################
class MessageConverter:
	
	tagFilter = re.compile('<[^<>]+?>',re.S)
	brFilter = re.compile('<br[ /]{0,2}>')
	
	def __init__(self,fb):
		self.FB = fb
		self._currentFilter = None
		self.resetOrdered(False)
		self.textwrap = textwrap.TextWrapper(80)
		
		#static filters
		self.imageFilter = re.compile('<img[^>]+src="(?P<url>http://[^"]+)"[^>]*/>')
		self.linkFilter = re.compile('<a.+?href="(?P<url>.+?)".*?>(?P<text>.+?)</a>')
		self.ulFilter = re.compile('<ul>(.+?)</ul>')
		#<span style="text-decoration: underline">Underline</span>
		self.olFilter = re.compile('<ol.+?>(.+?)</ol>')
		self.brFilter = re.compile('<br[ /]{0,2}>')
		self.blockQuoteFilter = re.compile('<blockquote>(.+?)</blockquote>',re.S)
		self.colorFilter = re.compile('<font color="(.+?)">(.+?)</font>')
		self.colorFilter2 = re.compile('<span.*?style=".*?color: ?(.+?)".*?>(.+?)</span>')
		self.setReplaces()
		self.resetRegex()
		
	def prepareSmileyList(self):
		class SmiliesList(list):
			def get(self,key,default=None): return default
			
		new = SmiliesList()
		if util.getSetting('use_skin_mods',True):
			for f,r,x in self.FB.smiliesDefs: #@UnusedVariable
				f = '(?m)((?:^|\s|\[CR\]))'+ re.escape(f)
				if '[/COLOR]' in r:
					new.append((f,r))
				else:
					new.append((f,'[COLOR FFBBBB00]'+r+'[/COLOR]'))
		else:
			for f,r,x in self.FB.smiliesDefs: #@UnusedVariable
				f = '(?m)((?:^|\s))'+ re.escape(f)
				if '[/COLOR]' in x:
					new.append((f,x))
				else:
					new.append((f,'[COLOR FFBBBB00]'+x+'[/COLOR]'))
		self.FB.smilies = new
		
	def resetRegex(self):
		if not self.FB: return
		
		self.prepareSmileyList()

		self.lineFilter = re.compile('[\n\r\t]')
		f = self.FB.filters.get('quote')
		self.quoteFilter = f and re.compile(f) or None
		f = self.FB.filters.get('code')
		self.codeFilter = f and re.compile(f) or None
		f = self.FB.filters.get('php')
		self.phpFilter = f and re.compile(f) or None
		f = self.FB.filters.get('html')
		self.htmlFilter = f and re.compile(f) or None
		f = self.FB.smilies.get('regex')
		self.smileyFilter = f and re.compile(f) or None
		f = self.FB.filters.get('image')
		self.imageFilter = f and re.compile(f) or self.imageFilter
		f = self.FB.filters.get('link')
		self.linkFilter = f and re.compile(f) or self.linkFilter
		f = self.FB.filters.get('link2')
		self.linkFilter2 = f and re.compile(f) or None
		f = self.FB.getQuoteFormat()
		self.quoteFilter2 = f and re.compile(f) or None
		
		self.quoteStartFilter = re.compile(self.FB.getQuoteStartFormat())
		self.altQuoteStartFilter = re.compile(self.FB.altQuoteStartFilter)
		self.quoteEndFilter = re.compile('\[\/quote\](?i)')
		self.quoteEndOnLineFilter = re.compile('(?!<\n)\s*\[\/quote\](?i)')
		
		self.smileyReplace = '[COLOR '+self.FB.smilies.get('color','FF888888')+']%s[/COLOR]'
		
	def setReplaces(self):
		self.quoteReplace = unicode.encode('[CR]_________________________[CR][B]'+T(32180)+'[/B][CR]'+T(32181)+' [B]%s[/B][CR][I]%s[/I][CR]_________________________[CR][CR]','utf8')
		self.aQuoteReplace = unicode.encode('[CR]_________________________[CR][B]'+T(32180)+'[/B][CR][I]%s[/I][CR]_________________________[CR][CR]','utf8')
		self.quoteImageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]A[/COLOR][COLOR FF0000FF]G[/COLOR][COLOR FFFF00FF]E[/COLOR]: \g<url>'
		self.hrReplace = ('[B]_____________________________________________________________________________________[/B]').encode('utf8')
		#self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]{0}[/COLOR]: [I]{1}[/I] '
		#self.imageReplace = u'[COLOR FFFF0000]([/COLOR][COLOR FF00FF00]([/COLOR]{0}[COLOR FF0000FF])[/COLOR][COLOR FFFFFF00])[/COLOR]{1}'
		
		if util.getSetting('use_skin_mods',True):
			self.imageConvert = self.imageConvertMod
			self.imageConvertQuote = self.imageConvertModQuote
			self.imageReplace = u'[CR][COLOR FF808080]\u250c\u2500\u2500\u2500\u2510[/COLOR][CR]'
			if util.getSetting('hide_image_urls',True):
				self.imageReplace += u'[COLOR FF808080]\u2502[/COLOR]{0}[COLOR FF808080]\u2502[/COLOR][CR]'
			else:
				self.imageReplace += u'[COLOR FF808080]\u2502[/COLOR]{0}[COLOR FF808080]\u2502[/COLOR][COLOR FF00AAAA]{1}[/COLOR][CR]'
			self.imageReplaceQuote = u'\u2022\u2024{0}\u2022 '
			self.imageReplace += u'[COLOR FF808080]\u2514\u2500\u2500\u2500\u2518[/COLOR][CR]'
			if util.getSetting('hide_link_urls',True):
				self.linkReplace = u'[COLOR FF00AAAA]\u261B{0}[/COLOR]'
			else:
				self.linkReplace = u'[COLOR FF00AAAA]{0} (\u261B [B]{1}[/B])[/COLOR]'
			self.link2Replace = u'[COLOR FF00AAAA](\u261B [B]\g<url>[/B])[/COLOR]'
			self.quoteStartReplace = u'\u250c'+u'\u2500'*300+u'[CR][B]'+T(32180)+u' %s[/B]'
			self.quoteEndReplace = u'\u2514'+u'\u2500'*300+u'[CR]'
			self.quoteVert = u'\u2502'
			self.hrReplace = u'[COLOR FF808080][B]'+u'\u2500'*300+u'[/B][/COLOR]'
			self.codeStartReplace = u'\u250c'+u'\u2500'*300
			self.codeEndReplace = u'\u2514'+u'\u2500'*300
			self.bullet = u'\u2022'
		else:
			self.imageConvert = self.imageConvertNoMod
			self.imageConvertQuote = self.imageConvertNoModQuote
			self.imageReplaceQuote = 'IMG#{0} '
			if util.getSetting('hide_image_urls',True):
				self.imageReplace = self.imageReplaceQuote
			else:
				self.imageReplace = '[COLOR FFFF0000]I[/COLOR][COLOR FFFF8000]M[/COLOR][COLOR FF00FF00]G[/COLOR][COLOR FF0000FF]#[/COLOR][COLOR FFFF00FF]{0}[/COLOR]: [COLOR FF00AAAA][I]{1}[/I][/COLOR] '
			if util.getSetting('hide_link_urls',True):
				self.linkReplace = u'[COLOR cyan]{1} {0}[/COLOR]'.format('{0}',T(32182))
			else:
				self.linkReplace = u'[COLOR cyan]{0} ({2} [B]{1}[/B])[/COLOR]'.format('{0}','{1}',T(32182))
			self.link2Replace = u'[COLOR cyan]({0} [B]\g<url>[/B])[/COLOR]'.format(T(32182))
			self.quoteStartReplace = u','+u'-'*300+u'[CR][B]'+T(32180)+u' %s[/B]'
			self.quoteEndReplace = u'`'+u'-'*300+u'[CR]'
			self.quoteVert = u'|'
			self.hrReplace = u'[COLOR FF808080][B]'+u'_'*300+u'[/B][/COLOR]'
			self.codeStartReplace = u','+u'-'*300
			self.codeEndReplace = u'`'+u'-'*300
			self.bullet = u'*'
			
		self.codeReplace = self.codeStartReplace + '[CR][B][COLOR FF999999]'+T(32183)+r'[/COLOR][/B][CR]%s[CR]' + self.codeEndReplace
		self.phpReplace = self.codeStartReplace + '[CR][B][COLOR FF999999]'+T(32184)+r'[/COLOR][/B][CR]%s[CR]' + self.codeEndReplace
		self.htmlReplace = self.codeStartReplace + '[CR][B][COLOR FF999999]'+T(32185)+r'[/COLOR][/B][CR]%s[CR]' + self.codeEndReplace
		
	def codeConvert(self,m):
		code = self.textwrap.fill(m.group(1).replace('[CR]','\n'))
		code = self.quoteVert + '[COLOR FF999999]' + code.replace('\n','\n[/COLOR]'+self.quoteVert+'[COLOR FF999999]') + '[/COLOR]'
		return self.codeStartReplace + '[CR]'+self.quoteVert+'[B]'+T(32183)+r'[/B][CR]%s[CR]' % code + self.codeEndReplace

	def phpConvert(self,m):
		code = self.textwrap.fill(m.group(1).replace('[CR]','\n'))
		code = self.quoteVert + '[COLOR FF999999]' + code.replace('\n','\n[/COLOR]'+self.quoteVert+'[COLOR FF999999]') + '[/COLOR]'
		return self.codeStartReplace + '[CR]'+self.quoteVert+'[B]'+T(32184)+r'[/B][CR]%s[CR]' % code + self.codeEndReplace
	
	def htmlConvert(self,m):
		code = self.textwrap.fill(m.group(1).replace('[CR]','\n'))
		code = self.quoteVert + '[COLOR FF999999]' + code.replace('\n','\n[/COLOR]'+self.quoteVert+'[COLOR FF999999]') + '[/COLOR]'
		return self.codeStartReplace + '[CR]'+self.quoteVert+'[B]'+T(32185)+r'[/B][CR]%s[CR]' % code + self.codeEndReplace
	
	def indentConvert(self,m):
		code = self.textwrap.fill(m.group(1).replace('[CR]','\n'))
		return '    ' + code.replace('\n','\n    ')
	
	def resetOrdered(self,ordered):
		self.ordered = ordered
		self.ordered_count = 0
		
	def messageToDisplay(self,html):
		#html = self.lineFilter.sub('',html)
		html = re.sub('[_]{10,}',r'\n\g<0>\n',html)
		html = html.replace('[hr]','\n[hr]\n')
		html = self.formatQuotes(html)
		html = re.sub('[_]{10,}',self.hrReplace,html) #convert the pre-converted [hr]
		#html = self.quoteStartFilter.sub(self.quoteConvert,html)
		#html = self.quoteEndFilter.sub(self.quoteEndReplace,html)
		#if self.quoteFilter: html = self.quoteFilter.sub(self.quoteConvert,html)
		#if self.quoteFilter2: html = self.quoteFilter2.sub(self.quoteConvert,html)
		if self.codeFilter: html = self.codeFilter.sub(self.codeReplace,html)
		if self.phpFilter: html = self.phpFilter.sub(self.phpReplace,html)
		if self.htmlFilter: html = self.htmlFilter.sub(self.htmlReplace,html)
		if self.smileyFilter: html = self.smileyFilter.sub(self.smileyConvert,html)
		
		self.imageCount = 0
		self.imageNumber = 0
		html = self.linkFilter.sub(self.linkConvert,html)
		if self.linkFilter2: html = self.linkFilter2.sub(self.link2Replace,html)
		html = self.imageFilter.sub(self.imageConvert,html)
		html = self.ulFilter.sub(self.processBulletedList,html)
		html = self.olFilter.sub(self.processOrderedList,html)
		html = self.colorFilter.sub(self.convertColor,html)
		html = self.colorFilter2.sub(self.convertColor,html)
		html = self.brFilter.sub('[CR]',html)
		html = self.blockQuoteFilter.sub(self.processIndent,html)
		html = html.replace('<b>','[B]').replace('</b>','[/B]')
		html = html.replace('<i>','[I]').replace('</i>','[/I]')
		html = html.replace('<u>','_').replace('</u>','_')
		html = html.replace('<strong>','[B]').replace('</strong>','[/B]')
		html = html.replace('<em>','[I]').replace('</em>','[/I]')
		html = html.replace('</table>','[CR][CR]')
		html = html.replace('</div></div>','[CR]') #to get rid of excessive new lines
		html = html.replace('</div>','[CR]')
		html = html.replace('[hr]',self.hrReplace)
		html = self.tagFilter.sub('',html)
		html = self.removeNested(html,'\[/?B\]','[B]')
		html = self.removeNested(html,'\[/?I\]','[I]')
		html = html.replace('[CR]','\n').strip().replace('\n','[CR]') #TODO Make this unnecessary
		html = self.processSmilies(html)
		return convertHTMLCodes(html,self.FB)

	def formatQuotesOld(self,html):
		ct = 0
		ms = True
		me = True
		#2503
		while ms or me:
			ms = self.quoteStartFilter.search(html)
			me = self.quoteEndFilter.search(html)
			if ms:
				if me and ms.start() > me.start():
					rep = self.quoteEndReplace
					if ct == 1:
						rep += '[/COLOR]'
					elif ct > 1:
						if not ct % 2:
							rep += '[/COLOR][COLOR FF5555AA]'
						else:
							rep += '[/COLOR][COLOR FF55AA55]'
					html = self.quoteEndFilter.sub(rep,html,1)
					ct -= 1
				else:
					gd = ms.groupdict()
					rep = self.quoteStartReplace % (gd.get('user') or '')
					if ct == 0: rep = '[COLOR FF5555AA]' + rep
					elif ct > 0:
						if ct % 2:
							rep = '[/COLOR][COLOR FF55AA55]' + rep
						else:
							rep = '[/COLOR][COLOR FF5555AA]' + rep
					html = self.quoteStartFilter.sub(rep,html,1)
					ct += 1
			elif me:
				rep = self.quoteEndReplace
				if ct == 1: rep += '[/COLOR]'
				elif ct > 1:
					if not ct % 2:
						rep += '[/COLOR][COLOR FF5555AA]'
					else:
						rep += '[/COLOR][COLOR FF55AA55]'
				html = self.quoteEndFilter.sub(rep,html,1)
				ct -= 1
		return html
			
	def formatQuotes(self,html):
		if not isinstance(html,unicode): html = unicode(html,'utf8')
		ct = 0
		ms = None
		me = None
		vertL = []
		html = html.replace('[CR]','\n')
		html = html.replace('<br />','\n')
		html = self.quoteEndOnLineFilter.sub('\n[/quote]',html)
		html = re.sub(self.quoteStartFilter.pattern + '(?!\n)','\g<0>\n',html)
		lines = html.splitlines()
		out = ''
		justStarted = False
		oddVert = u'[COLOR FF55AA55]%s[/COLOR]' % self.quoteVert
		evenVert = u'[COLOR FF5555AA]%s[/COLOR]' % self.quoteVert
		
		for line in lines:
			if ct < 0: ct = 0
			ms = self.quoteStartFilter.search(line)
			startFilter = self.quoteStartFilter
			if not ms: me = self.quoteEndFilter.search(line) #dont search if we don't have to
			if ms:
				alts = self.altQuoteStartFilter.search(line)
				if alts:
					ms = alts
					startFilter = self.altQuoteStartFilter
				justStarted = True
				oldVert = ''.join(vertL)
				gd = ms.groupdict()
				rep = self.quoteStartReplace % (gd.get('user') or '')
				if ct == 0:
					rep = '[COLOR FF5555AA]' + rep
					vertL.append(evenVert)
				elif ct > 0:
					if ct % 2:
						rep = '[/COLOR][COLOR FF55AA55]' + rep
						vertL.append(oddVert)
					else:
						rep = '[/COLOR][COLOR FF5555AA]' + rep
						vertL.append(evenVert)
				vert = ''.join(vertL)
				out += oldVert + startFilter.sub(rep,line,1).replace('[CR]','[CR]' + vert) + '[CR]'
				ct += 1
			elif me:
				rep = self.quoteEndReplace
				if ct == 1: rep += '[/COLOR]'
				elif ct > 1:
					if not ct % 2:
						rep += '[/COLOR][COLOR FF5555AA]'
					else:
						rep += '[/COLOR][COLOR FF55AA55]'
				oldVert = ''.join(vertL)
				if vertL: vertL.pop()
				vert = ''.join(vertL)
				out += oldVert + self.quoteEndFilter.sub('[CR]' + rep,line,1).replace('[CR]','[CR]' + vert) + '[CR]'
				ct -= 1
			elif ct:
				if justStarted:
					out += vert + '[CR]'
				line = self.linkFilter.sub(r'\g<text> [B](Link)[/B]',line)
				if self.linkFilter2: line = self.linkFilter2.sub('[B](LINK)[/B]',line)
				wlines = self.textwrap.wrap(line)
				for l in wlines:
					out += vert + l + '[CR]'
			else:
				out += line + '[CR]'
			if not ms:
				justStarted = False
		return out
	
	def quoteConvert2(self,m):
		gd = m.groupdict()
		return self.quoteStartReplace % (gd.get('user') or '')
		
	def removeNested(self,html,regex,starttag):
		self.nStart = starttag
		self.nCounter = 0
		return re.sub(regex,self.nestedSub,html)
		
	def nestedSub(self,m):
		tag = m.group(0)
		if tag == self.nStart:
			self.nCounter += 1
			if self.nCounter == 1: return tag
		else:
			self.nCounter -= 1
			if self.nCounter < 0: self.nCounter = 0
			if self.nCounter == 0: return tag
		return ''
		
	def messageAsQuote(self,html):
		html = self.lineFilter.sub('',html)
		if self.quoteFilter: html = self.quoteFilter.sub('',html)
		if self.codeFilter: html = self.codeFilter.sub('[CODE]\g<code>[/CODE]',html)
		if self.phpFilter: html = self.phpFilter.sub('[PHP]\g<php>[/PHP]',html)
		if self.htmlFilter: html = self.htmlFilter.sub('[HTML]\g<html>[/HTML]',html)
		if self.smileyFilter: html = self.smileyFilter.sub(self.smileyConvert,html)
		html = self.linkFilter.sub('[URL="\g<url>"]\g<text>[/URL]',html)
		html = self.imageFilter.sub('[IMG]\g<url>[/IMG]',html)
		html = self.colorFilter.sub(self.convertColor,html)
		html = self.colorFilter2.sub(self.convertColor,html)
		html = html.replace('<b>','[B]').replace('</b>','[/B]')
		html = html.replace('<i>','[I]').replace('</i>','[/I]')
		html = html.replace('<u>','[U]').replace('</u>','[/U]')
		html = html.replace('<strong>','[B]').replace('</strong>','[/B]')
		html = html.replace('<em>','[I]').replace('</em>','[/I]')
		html = re.sub('<br[^<>]*?>','\n',html)
		html = html.replace('</table>','\n\n')
		html = html.replace('</div>','\n')
		html = re.sub('<[^<>]+?>','',html)
		return convertHTMLCodes(html,self.FB).strip()
	
	def linkConvert(self,m):
		if m.group(1) == m.group(2):
			return self.link2Replace.replace('\g<url>',m.group(1))
		
		return self.linkReplace.format(m.group(2),m.group(1))
	
	def imageConvertModQuote(self,m):
		count = self.getImageCount(m)
		disp = self.getMonoCharacterNumber(count)
		return self.imageReplaceQuote.format(disp,m.group('url'))
	
	def imageConvertNoModQuote(self,m):
		count = self.getImageCount(m)
		return self.imageReplaceQuote.format(count,m.group('url'))
	
	def imageConvertMod(self,m):
		count = self.getImageCount(m)
		disp = self.makeCamera(count)
		return self.imageReplace.format(disp,m.group('url'))
		
	def getImageCount(self,m):
		try:
			count = int(m.group('count'))
		except:
			self.imageCount += 1
			count = self.imageCount
		return count
	
	def getCharacterNumber(self,count):	
		if count <= 30:
			return u'[COLOR FF00FF00]{0}[/COLOR]'.format(unichr(10101 + count))
		elif count <=60:
			return u'[COLOR FFFF0000]{0}[/COLOR]'.format(unichr(10071 + count))
		elif count <=90:
			return u'[COLOR FF4444FF]{0}[/COLOR]'.format(unichr(10041 + count))
		else:
			return u'[COLOR FF4444FF]{0}[/COLOR]'.format(unichr(10060))
		
	def getMonoCharacterNumber(self,count):	
		if count <= 30:
			return unichr(10101 + count)
		elif count <=60:
			return unichr(10071 + count)
		elif count <=90:
			return unichr(10041 + count)
		else:
			return unichr(10060)
			
	def makeCamera(self,count):
		return u'[COLOR FFFFFFFF]\u205e[/COLOR][COLOR FF000033]\u205d[/COLOR][COLOR FF111111]\u2024[/COLOR][COLOR FFFFCCCC]\u2025[/COLOR]{0}'.format(self.getCharacterNumber(count))
		
	def imageConvertNoMod(self,m):
		count = self.getImageCount(m)
		return self.imageReplace.format(count,m.group('url'))

	imageConvert = imageConvertNoMod
	imageConvertQuote = imageConvertNoModQuote
	
	def imageNumberer(self,m):
		self.imageNumber+=1
		return m.group(0).lower().replace('img', '%simg' % self.imageNumber)
		
	def numberImages(self,html,image_count=0):
		self.imageNumber = image_count
		html = self.imageNumbererFilter.sub(self.imageNumberer,html)
		return html
		
	def processSmilies(self,text):
		if not isinstance(text,unicode): text = unicode(text,'utf8')
		if self.smileyFilter: return text
		for f,r in self.FB.smilies: text = re.sub(f,r'\1'+r,text)
		return text
	
	def smileyRawConvert(self,m):
		return self.FB.smilies.get(m.group('smiley'),'')
		
	def smileyConvert(self,m):
		return self.smileyReplace % self.FB.smilies.get(m.group('smiley'),'')
		
	def quoteConvert(self,m):
		gd = m.groupdict()
		#quote = self.imageFilter.sub(self.quoteImageReplace,gd.get('quote',''))
		return self.quoteStartReplace % (gd.get('user') or '')
			
	def processIndent(self,m):
		return '    ' + re.sub('\n','\n    ',m.group(1)) + '\n'
		
	def convertColor(self,m):
		if m.group(1).startswith('#'):
			color = 'FF' + m.group(1)[1:].upper()
		else:
			color = m.group(1).lower()
		return '[COLOR %s]%s[/COLOR]' % (color,m.group(2))

	def processBulletedList(self,m):
		self.resetOrdered(False)
		return self.processList(m.group(1))
		
	def processOrderedList(self,m):
		self.resetOrdered(True)
		return self.processList(m.group(1))
			
	def processList(self,html):
		return re.sub('<li>(.+?)</li>',self.processItem,html) + '\n'

	def processItem(self,m):
		self.ordered_count += 1
		if self.ordered: bullet = str(self.ordered_count) + '.'
		else: bullet = self.bullet
		return  '%s %s\n' % (bullet,m.group(1))
		
	def parseCodes(self,text):
		text = re.sub('\[QUOTE=(?P<user>\w+)(?:;\d+)*\](?P<quote>.+?)\[/QUOTE\](?is)',self.quoteConvert,text)
		text = re.sub('\[QUOTE\](?P<quote>.+?)\[(?P<user>)?/QUOTE\](?is)',self.quoteConvert,text)
		text = re.sub('\[CODE\](?P<code>.+?)\[/CODE\](?is)',self.codeReplace,text)
		text = re.sub('\[PHP\](?P<php>.+?)\[/PHP\](?is)',self.phpReplace,text)
		text = re.sub('\[HTML\](?P<html>.+?)\[/HTML\](?is)',self.htmlReplace,text)
		text = re.sub('\[IMG\](?P<url>.+?)\[/IMG\](?is)',self.quoteImageReplace,text)
		text = re.sub('\[URL="?(?P<url>[^\]]+?)"?\](?P<text>.+?)\[/URL\](?is)',self.linkReplace,text)
		text = re.sub('\[URL\](?P<text>(?P<url>.+?))\[/URL\](?is)',self.link2Replace,text)
		return text

######################################################################################
# BBMessage Converter
######################################################################################
class BBMessageConverter(MessageConverter):
	def __init__(self,fb):
		self.FB = fb
		self.smileyFilter = None
		self._currentFilter = None
		self.textwrap = textwrap.TextWrapper(80)
		self.textwrap.replace_whitespace = False
		self.boldFilter = re.compile('\[(/?)b\]')
		self.italicsFilter = re.compile('\[(/?)i\]')
		self.indentFilter = re.compile('\[indent\](.*?)\[/indent\](?is)')
		self.sizeTagFilter = re.compile('\[/?size(?:=[\w-]+)?\](?i)')
		self.numberedFilter = re.compile('\[list=\d\](.*?)\[/list\](?i)')
		self.bulletedFilter = re.compile('\[list\](.*?)\[/list\](?i)')
		self.kissingTagFilter = re.compile('(\[/\w+\])(\[\w+\])')
		self.listItemFilter1 = re.compile('\[\*\](.*?)($|\[CR\])')
		self.listItemFilter2 = re.compile('\[\*\]')
		self.underlineFilter = re.compile('\[/?u\](?i)')
		self.underlineBlockFilter = re.compile('\[u\](.*?)\[/u\](?is)')
		self.imageNumbererFilter = re.compile('\[img\](?i)')
		self.setReplaces()
		self.resetRegex()
		
	def resetRegex(self):		
		self.prepareSmileyList()

		self.lineFilter = re.compile('[\n\r\t]')
		f = self.FB.filters.get('code')
		self.codeFilter = f and re.compile(f) or None
		f = self.FB.filters.get('php')
		self.phpFilter = f and re.compile(f) or None
		f = self.FB.filters.get('html')
		self.htmlFilter = f and re.compile(f) or None
		f = self.FB.filters.get('image')
		self.imageFilter = f and re.compile(f) or self.imageFilter
		f = self.FB.filters.get('link')
		self.linkFilter = f and re.compile(f) or self.linkFilter
		f = self.FB.filters.get('link2')
		self.linkFilter2 = f and re.compile(f) or None
		f = self.FB.filters.get('color_start')
		self.colorStart = f and re.compile(f) or None
		f = self.FB.getQuoteFormat()
		self.quoteFilter2 = f and re.compile(f) or None
		
		self.quoteStartFilter = re.compile(self.FB.getQuoteStartFormat())
		self.altQuoteStartFilter = re.compile(self.FB.altQuoteStartFilter)
		self.quoteEndFilter = re.compile('\[\/quote\](?i)')
		self.quoteEndOnLineFilter = re.compile('(?!<\n)\s*\[\/quote\](?i)')
		self.fakeHrFilter = re.compile('[_]{10,}')
		
	def messageToDisplay(self,html,image_count=0):
		#import codecs
		#codecs.open('test.txt','w','utf8').write(html)
		html = html.replace('[CR]','\n')
		html = self.kissingTagFilter.sub(r'\1\n\2',html)

		html = self.numberImages(html, image_count)
		self.imageCount = self.imageNumber
		
		html = self.fakeHrFilter.sub(r'\n\g<0>\n',html)
		html = html.replace('[hr]','\n[hr]\n')
		html = self.formatQuotes(html)
		html = self.fakeHrFilter.sub(self.hrReplace,html) #convert the pre-converted [hr]
		
		html = self.boldFilter.sub(r'[\1B]',html)
		html = self.italicsFilter.sub(r'[\1I]',html)
		
		if self.codeFilter: html = self.codeFilter.sub(self.codeConvert,html)
		if self.phpFilter: html = self.phpFilter.sub(self.phpConvert,html)
		if self.htmlFilter: html = self.htmlFilter.sub(self.htmlConvert,html)
		html = self.indentFilter.sub(self.indentConvert,html)
		html = self.sizeTagFilter.sub('',html)
		
		if self.colorStart: html = self.colorStart.sub(r'[COLOR FF\1]',html)
		html = html.replace('[/color]','[/COLOR]')
		
		html = self.linkFilter.sub(self.linkConvert,html)
		if self.linkFilter2: html = self.linkFilter2.sub(self.link2Replace,html)
		html = self.imageFilter.sub(self.imageConvert,html)
		html = html.replace('[hr]',self.hrReplace)
		html = self.removeNested(html,'\[/?B\]','[B]')
		html = self.removeNested(html,'\[/?I\]','[I]')
		#html = self.underlineFilter.sub('_',html)
		html = self.underlineBlockFilter.sub(self.underlineConvert,html)
		html = self.bulletedFilter.sub(self.processBulletedList,html)
		html = self.numberedFilter.sub(self.processOrderedList,html)
		#html = html.replace('[CR]','\n').strip().replace('\n','[CR]') #TODO Make this unnecessary
		html = self.processSmilies(html)
		return convertHTMLCodes(html,self.FB)
		
	def underlineConvert(self,m):
		head = ''
		tail = ''
		parts = re.split('(\[[^\]\[]+\])',m.group(1).lstrip())
		i = True
		for x in range(len(parts)-1,-1,-1):
			if i:
				prstrip = parts[x].rstrip(' ')
				if prstrip:
					tail += ' ' * (len(parts[x]) - len(prstrip))
					parts[x] = prstrip
					break
				else:
					tail += parts[x]
					parts[x] = ''
			i = not i
		out = ''
		i = True
		textFound = False
		for x in parts:
			if i and x:
				if x.strip() or textFound: #this removes leading spaces even if after a tag
					if not textFound: x = x.lstrip()
					out += re.sub('.',u'\u2042\g<0>',x)
					textFound = True
			else:
				out += x
			i = not i
		return head + out + tail
		
	def formatQuotes(self,html):
		if not isinstance(html,unicode):
			try:
				html = unicode(html,'utf8')
			except UnicodeDecodeError:
				try:
					html = unicode(html,'latin_1')
				except:
					html = str(html).encode('string_escape')
					html = unicode(html)
			
		ct = 0
		ms = None
		me = None
		vertL = []
		html = html.replace('[CR]','\n')
		html = html.replace('<br />','\n')
		html = self.quoteEndOnLineFilter.sub('\n[/quote]',html)
		html = self.altQuoteStartFilter.sub(r"[quote='\1']",html)
		html = re.sub(self.quoteStartFilter.pattern + '(?!\n)','\g<0>\n',html)
		lines = html.splitlines()
		out = ''
		justStarted = False
		oddVert = u'[COLOR FF55AA55]%s[/COLOR]' % self.quoteVert
		evenVert = u'[COLOR FF5555AA]%s[/COLOR]' % self.quoteVert
		
		for line in lines:
			if ct < 0: ct = 0
			ms = self.quoteStartFilter.search(line)
			startFilter = self.quoteStartFilter
			if not ms: me = self.quoteEndFilter.search(line) #dont search if we don't have to
			if ms:
				justStarted = True
				oldVert = ''.join(vertL)
				gd = ms.groupdict()
				rep = self.quoteStartReplace % (gd.get('user') or '')
				if ct == 0:
					rep = '[COLOR FF5555AA]' + rep
					vertL.append(evenVert)
				elif ct > 0:
					if ct % 2:
						rep = '[/COLOR][COLOR FF55AA55]' + rep
						vertL.append(oddVert)
					else:
						rep = '[/COLOR][COLOR FF5555AA]' + rep
						vertL.append(evenVert)
				vert = ''.join(vertL)
				out += oldVert + startFilter.sub(rep,line,1).replace('[CR]','[CR]' + vert) + '[CR]'
				ct += 1
			elif me:
				rep = self.quoteEndReplace
				if ct == 1: rep += '[/COLOR]'
				elif ct > 1:
					if not ct % 2:
						rep += '[/COLOR][COLOR FF5555AA]'
					else:
						rep += '[/COLOR][COLOR FF55AA55]'
				oldVert = ''.join(vertL)
				if vertL: vertL.pop()
				vert = ''.join(vertL)
				out += oldVert + self.quoteEndFilter.sub('[CR]' + rep,line,1).replace('[CR]','[CR]' + vert) + '[CR]'
				ct -= 1
			elif ct:
				if justStarted:
					out += vert + '[CR]'
				line = self.linkFilter.sub(r'\g<text> [B](Link)[/B]',line)
				line = self.imageFilter.sub(self.imageConvertQuote,line)
				line = re.sub('\[code\](?i)','__________\nCODE:\n',line)
				line = re.sub('\[/code\](?i)','\n__________',line)
				line = re.sub('\[php\](?i)','__________\nPHP:\n',line)
				line = re.sub('\[/php\](?i)','\n__________',line)
				line = re.sub('\[html\](?i)','__________\nHTML:\n',line)
				line = re.sub('\[/html\](?i)','\n__________',line)
				if self.linkFilter2: line = self.linkFilter2.sub('[B](LINK)[/B]',line)
				wlines = self.textwrap.fill(line).splitlines()
				for l in wlines:
					out += vert + l + '[CR]'
			else:
				out += line + '[CR]'
			if not ms:
				justStarted = False
		return out
	
	def processList(self,html):
		html = self.listItemFilter1.sub(self.processItem1,html)
		return self.listItemFilter2.sub(self.processItem2,html)
	
	def processItem1(self,m):
		if not m.group(1).strip(): return ''
		self.ordered_count += 1
		if self.ordered: bullet = str(self.ordered_count) + '. '
		else: bullet = self.bullet + ' '
		return  bullet + m.group(1) + m.group(2)
	
	def processItem2(self,m):
		self.ordered_count += 1
		if self.ordered: bullet = str(self.ordered_count) + '. '
		else: bullet = self.bullet + ' '
		return  bullet

	def removeNested(self,html,regex,starttag):
		self.nStart = starttag
		self.nCounter = 0
		return re.sub(regex,self.nestedSub,html)
		
	def nestedSub(self,m):
		tag = m.group(0)
		if tag == self.nStart:
			self.nCounter += 1
			if self.nCounter == 1: return tag
		else:
			self.nCounter -= 1
			if self.nCounter < 0: self.nCounter = 0
			if self.nCounter == 0: return tag
		return ''
		
	def parseCodes(self,text):
		text = re.sub('\[QUOTE=(?P<user>\w+)(?:;\d+)*\](?P<quote>.+?)\[/QUOTE\](?is)',self.quoteConvert,text)
		text = re.sub('\[QUOTE\](?P<quote>.+?)\[(?P<user>)?/QUOTE\](?is)',self.quoteConvert,text)
		text = re.sub('\[CODE\](?P<code>.+?)\[/CODE\](?is)',self.codeReplace,text)
		text = re.sub('\[PHP\](?P<php>.+?)\[/PHP\](?is)',self.phpReplace,text)
		text = re.sub('\[HTML\](?P<html>.+?)\[/HTML\](?is)',self.htmlReplace,text)
		text = re.sub('\[IMG\](?P<url>.+?)\[/IMG\](?is)',self.quoteImageReplace,text)
		text = re.sub('\[URL="?(?P<url>[^\]]+?)"?\](?P<text>.+?)\[/URL\](?is)',self.linkReplace,text)
		text = re.sub('\[URL\](?P<text>(?P<url>.+?))\[/URL\](?is)',self.link2Replace,text)
		return text
	
######################################################################################
# Functions
######################################################################################
def makeUnicode(html):
	if not isinstance(html,unicode):
		try:
			html = unicode(html,'utf8')
		except UnicodeDecodeError:
			try:
				html = unicode(html,'latin_1')
			except:
				html = str(html).encode('string_escape')
				html = unicode(html)
	return html

def subTags(m): return '[%s]' % m.group(1).upper()

#def translateDisplay(message):
#	pre = re.sub('\[(/?(?:(?:COLOR(?: \w+)?)|CR|B|I))\]',r'<\1>',message).replace('> ','><space>').replace(' <','<space><')
#	message = TR.translate(pre,FB.formats.get('language','en'),getLanguage(),newline='<CR>',format='html')
#	message = convertHTMLCodes(message)
#	message = message.replace('> ','>').replace(' <','<').replace('<space>',' ')
#	message = re.sub('<(/?COLOR(?: \w+)?)>',r'[\1]',message)
#	message = re.sub('<([^<>]+?)>',subTags,message)
#	return message
		
def calculatePage(low,high,total):
	low = int(low.replace(',',''))
	high = int(high.replace(',',''))
	total = int(total.replace(',',''))
	if high == total: return -1
	return str(int(round(float(high)/((high-low)+1))))