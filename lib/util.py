import sys, xbmcaddon

__addon__ = xbmcaddon.Addon(id='script.forum.browser')

def ERROR(message,hide_tb=False):
	LOG('ERROR: ' + message)
	short = str(sys.exc_info()[1])
	if hide_tb:
		LOG('ERROR Message: ' + short)
	else:
		import traceback #@Reimport
		traceback.print_exc()
		if getSetting('debug_show_traceback_dialog',False):
			import dialogs #import dialogs here so we can import this module into dialogs
			dialogs.showText('Traceback', traceback.format_exc())
	return short
	
def LOG(message):
	print 'FORUMBROWSER: %s' % message

def getSetting(key,default=None):
	setting = __addon__.getSetting(key)
	return _processSetting(setting,default)

def _processSetting(setting,default):
	if not setting: return default
	if isinstance(default,bool):
		return setting == 'true'
	elif isinstance(default,int):
		return int(float(setting or 0))
	elif isinstance(default,list):
		if setting: return setting.split(':!,!:')
		else: return default
	
	return setting

def setSetting(key,value):
	if isinstance(value,list):
		value = ':!,!:'.join(value)
	elif isinstance(value,bool):
		value = value and 'true' or 'false'
	__addon__.setSetting(key,value)
	
def parseForumBrowserURL(url):
	if not url.startswith('forumbrowser://'):
		return {'forumID':url}
	parts = url.split('://',1)[-1].split('/',4)
	elements = {}
	elements['forumID'] = parts[0]
	if len(parts) > 1: elements['section'] = parts[1]
	if len(parts) > 2: elements['forum'] = parts[2]
	if len(parts) > 3: elements['thread'] = parts[3]
	if len(parts) > 4: elements['post'] = parts[4]
	return elements

def createForumBrowserURL(forumID,section='',forum='',thread='',post=''):
	ret = 'forumbrowser://%s/%s/%s/%s/%s' % (forumID,section,forum,thread,post)
	return ret.strip('/')
	
def getListItemByProperty(clist,prop,value):
	for idx in range(0,clist.size()):
		item = clist.getListItem(idx)
		if item.getProperty(prop) == value: return item
	return None
	
def selectListItemByProperty(clist,prop,value):
	for idx in range(0,clist.size()):
		item = clist.getListItem(idx)
		if item.getProperty(prop) == value:
			clist.selectItem(idx)
			return item
	return None