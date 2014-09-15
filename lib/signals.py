import xbmc, xbmcaddon, os, json
from util import LOG, ERROR

DEBUG = False

SIGNAL_COUNTER = 0

SIGNAL_CACHE_PATH = os.path.join(xbmc.translatePath(xbmcaddon.Addon(id='script.forum.browser').getAddonInfo('profile')),'cache','signals')

class SignalHub(xbmc.Monitor): # @UndefinedVariable
	def __init__(self):
		self.currID = 0
		self.registry = {}
		xbmc.Monitor.__init__(self)  # @UndefinedVariable
		
	def registerReceiver(self,signal,registrant,callback):
		self.setRegistrantID(registrant)
		if DEBUG: LOG('SignalHub registering signal %s: [%s] %s' % (signal,registrant._receiverID,registrant.__class__.__name__))
		if signal in self.registry:
			self.registry[signal].append((registrant,callback))
		else:
			self.registry[signal] = [(registrant,callback)]
			
	def registerSelfReceiver(self,signal,registrant,callback):
		self.setRegistrantID(registrant)
		signal = signal + '.' + str(registrant._receiverID)
		return self.registerReceiver(signal, registrant, callback)
	
	def setRegistrantID(self,registrant):
		if not hasattr(registrant,'_receiverID'):
			registrant._receiverID = self.currID
			self.currID += 1
		
	def unRegister(self,signal,registrant):
		if signal and not signal in self.registry: return
		if signal:
			signals = [signal]
		else:
			signals = self.registry.keys()
			
		for signal in signals:
			i=0
			for reg, cb in self.registry[signal]:  # @UnusedVariable
				if reg._receiverID == registrant._receiverID:
					if DEBUG: LOG('SignalHub un-registering signal %s: [%s] %s' % (signal,registrant._receiverID,registrant.__class__.__name__))
					self.registry[signal].pop(i)
					break
				i+=1

	def unSelfRegister(self,signal,registrant):
		signal = signal + '.' + str(registrant._receiverID)
		return self.unRegister(signal, registrant)
	
	def onNotification(self, sender, method, data):
		if not sender == 'script.forum.browser.SIGNAL': return
		signal = method.split('.',1)[-1]
		if data:
			args = json.loads(data)
			if args:
				data = args.get('data')
				
		if DEBUG:
			import threading
			LOG('SignalHub: Thread: %s' % str(threading.currentThread().getName()))

		
		if not signal in self.registry: return
		for reg,cb in self.registry[signal]:  # @UnusedVariable
			if DEBUG: LOG('SignalHub: Callback in response to signal %s for [%s] %s (%s)' % (signal,reg._receiverID,reg.__class__.__name__,data))
			try:
				cb(signal,data)
			except:
				ERROR('SignalHub: Callback Error')
				continue
	
def sendSignal(signal,data=''):
	command = 'XBMC.NotifyAll(script.forum.browser.SIGNAL,{0},"{{\\"data\\":\\"{1}\\"}}")'.format(signal,data)
	xbmc.executebuiltin(command)
	if DEBUG: LOG('SignalHub: Sending signal %s (%s)' % (signal,data))
	
def sendSelfSignal(sender,signal,data=''):
	if not hasattr(sender,'_receiverID'): return
	signal = signal + '.' + str(sender._receiverID)
	return sendSignal(signal,data)
