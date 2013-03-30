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