#Forum browser common
import re

################################################################################
# Action
################################################################################
class Action:
	def __init__(self,action=''):
		self.action = action
		
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