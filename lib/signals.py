import xbmc, xbmcaddon

DEBUG = True

def LOG(msg): print 'FORUMBROWSER: %s' % msg
def ERROR(msg): LOG(msg)

SIGNAL_COUNTER = 0

class SignalHub(xbmc.Monitor): # @UndefinedVariable
	def __init__(self):
		self.currID = 0
		self.registry = {}
		self.settings = xbmcaddon.Addon(id='script.forum.browser')
		self._lastSignal = ''
		xbmc.Monitor.__init__(self)  # @UndefinedVariable
		
	def registerReceiver(self,signal,registrant,callback):
		if not hasattr(registrant,'__receiverID'):
			registrant.__receiverID = self.currID
			self.currID += 1
		if DEBUG: LOG('SignalHub registering signal %s: [%s] %s' % (signal,registrant.__receiverID,repr(registrant)))
		if signal in self.registry:
			self.registry[signal].append((registrant,callback))
		else:
			self.registry[signal] = [(registrant,callback)]
		
	def unRegister(self,signal,registrant):
		if not signal in self.registry: return
		i=0
		for reg, cb in self.registry[signal]:  # @UnusedVariable
			if reg.__receiverID == registrant.__receiverID:
				if DEBUG: LOG('SignalHub un-registering signal %s: [%s] %s' % (signal,registrant.__receiverID,repr(registrant)))
				self.registry[signal].pop(i)
				return
			i+=1 

	def getSignal(self):
		self.settings = xbmcaddon.Addon(id='script.forum.browser')
		signal = self.settings.getSetting('SignalHubSignal')
		if not signal or signal == self._lastSignal: return None
		return signal.split(':',1)[0]
	
	def onSettingsChanged(self):
		signal = self.getSignal()
		if not signal: return
		if not signal in self.registry: return
		for reg,cb in self.registry[signal]:  # @UnusedVariable
			if DEBUG: LOG('SignalHub: Callback in response to signal %s for [%s] %s' % (signal,reg.__receiverID,repr(reg)))
			try:
				cb(signal,None)
			except:
				ERROR('SignalHub: Callback Error')
				continue
			
def sendSignal(signal,data=''):
	global SIGNAL_COUNTER
	xbmcaddon.Addon(id='script.forum.browser').setSetting('SignalHubSignal',signal + ':' + str(SIGNAL_COUNTER))
	if DEBUG: LOG('SignalHub: Sending signal %s' % signal)
	SIGNAL_COUNTER+=1