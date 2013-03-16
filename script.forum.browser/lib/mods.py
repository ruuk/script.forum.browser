import os, sys, xbmc, xbmcgui, xbmcvfs, dialogs
from distutils.version import StrictVersion

DEBUG = None
LOG = None
ERROR = None
CACHE_PATH = None
getSetting = None
setSetting = None
__addon__ = sys.modules["__main__"].__addon__
__language__ = sys.modules["__main__"].__language__

def copyKeyboardModImages(skinPath):
	dst = os.path.join(skinPath,'media','forum-browser-keyboard')
	if os.path.exists(dst): return
	os.makedirs(dst)
	src = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'keyboard','images')
	for f in os.listdir(src):
		s = os.path.join(src,f)
		d = os.path.join(dst,f)
		if not os.path.exists(d) and not f.startswith('.'): xbmcvfs.copy(s,d)

def copyFont(sourceFontPath,skinPath):
	dst = os.path.join(skinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	if os.path.exists(dst): return
	xbmcvfs.copy(sourceFontPath,dst)
	
def copyTree2(source,target):
	try:
		import distutils.dir_util
		copyTree = distutils.dir_util.copy_tree
	except:
		import shutil
		copyTree = shutil.copytree
		
	copyTree(source, target)
		
def copyTree(source,target,dialog=None):
	pct = 0
	mod = 5
	if not source or not target: return
	if not os.path.isdir(source): return
	sourcelen = len(source)
	if not source.endswith(os.path.sep): sourcelen += 1
	for path, dirs, files in os.walk(source): #@UnusedVariable
		subpath = path[sourcelen:]
		xbmcvfs.mkdir(os.path.join(target,subpath))
		for f in files:
			if dialog: dialog.update(pct,'Copying files:',f)
			xbmcvfs.copy(os.path.join(path,f),os.path.join(target,subpath,f))
			pct += mod
			if pct > 100:
				pct = 95
				mod = -5
			elif pct < 0:
				pct = 5
				mod = 5

def getSkinVersion(skin_path):
	addon = os.path.join(skin_path,'addon.xml')
	if not os.path.exists(addon): return '0.0.0'
	acontent = open(addon,'r').read()
	return acontent.split('<addon',1)[-1].split('version="',1)[-1].split('"',1)[0]
	

def checkForSkinMods():
	skinPath = xbmc.translatePath('special://skin')
	if skinPath.endswith(os.path.sep): skinPath = skinPath[:-1]
	skinName = os.path.basename(skinPath)
	version = getSkinVersion(skinPath)
	LOG('XBMC Skin (In Use): %s %s' % (skinName,version))
	localAddonsPath = os.path.join(xbmc.translatePath('special://home'),'addons')
	localSkinPath = os.path.join(localAddonsPath,skinName)
	version2 = getSkinVersion(localSkinPath)
	LOG('XBMC Skin   (Home): %s %s' % (skinName,version2))
	if __addon__.getSetting('use_skin_mods') != 'true':
		LOG('Skin mods disabled')
		return			
	font = os.path.join(localSkinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	install = True
	if os.path.exists(font):
		if StrictVersion(version2) >= StrictVersion(version):
			fontsXmlFile = os.path.join(localSkinPath,'720p','Font.xml')
			if not os.path.exists(fontsXmlFile): fontsXmlFile = os.path.join(localSkinPath,'1080i','Font.xml')
			if os.path.exists(fontsXmlFile):
				contents = open(fontsXmlFile,'r').read()
				if 'Forum Browser' in contents:
					LOG('Fonts mod detected')
					install = False
	if not install and not getSetting('use_keyboard_mod',False):
		LOG('Keyboard mod disabled')
		return
	dialogPath = os.path.join(localSkinPath,'720p','DialogKeyboard.xml')
	if not os.path.exists(dialogPath): dialogPath = os.path.join(localSkinPath,'1080i','DialogKeyboard.xml')
	if os.path.exists(dialogPath):
		keyboardcontents = open(dialogPath,'r').read()
		if 'Forum Browser' in keyboardcontents:
			LOG('Keyboard mod detected')
			return
	
	dialogs.showInfo('skinmods')
	yes = xbmcgui.Dialog().yesno('Skin Mods','Recommended skin modifications not installed.','(Requires XBMC restart to take effect.)','Install now?')
	if not yes:
		__addon__.setSetting('use_skin_mods','false')
		dialogs.showMessage('Aborted','','Skin modifications were [B]NOT[/B] installed',"[CR]Enable 'Use skin modifications (Recommended)' in settings if you want to install them at a later time.")
		return
	LOG('Installing Skin Mods')
	installSkinMods()

def installSkinMods(update=False):
	if not getSetting('use_skin_mods',False): return
		
	#restart = False
	fbPath = xbmc.translatePath(__addon__.getAddonInfo('path'))
	localAddonsPath = os.path.join(xbmc.translatePath('special://home'),'addons')
	skinPath = xbmc.translatePath('special://skin')
	if skinPath.endswith(os.path.sep): skinPath = skinPath[:-1]
	currentSkin = os.path.basename(skinPath)
	localSkinPath = os.path.join(localAddonsPath,currentSkin)
	#LOG(localSkinPath)
	#LOG(skinPath)
	version = getSkinVersion(skinPath)
	version2 = getSkinVersion(localSkinPath)
	
	if not os.path.exists(localSkinPath) or StrictVersion(version2) < StrictVersion(version):
		yesno = xbmcgui.Dialog().yesno('Skin Mod Install',currentSkin + ' skin not installed in user path.','Click Yes to copy,','click No to Abort')
		#yesno = xbmcgui.Dialog().yesno('Skin Mod Install','Skin files need to be copied to user path.','Click Yes to copy,','click No to Abort')
		if not yesno: return
		dialog = xbmcgui.DialogProgress()
		dialog.create('Copying Files','Please wait...')
		try:
			copyTree(skinPath,localSkinPath,dialog)
		except:
			err = ERROR('Failed to copy skin to user directory')
			dialogs.showMessage('Error',err,'Failed to copy files, aborting.',error=True)
			return
		finally:
			dialog.close()
		#restart = True
		dialogs.showMessage('Success','Files copied.','XBMC needs to be restarted','for mod to take effect',success=True)
		
	skinPath = localSkinPath
	sourceFontXMLPath = os.path.join(fbPath,'keyboard','Font-720p.xml')
	sourceFontPath = os.path.join(fbPath,'keyboard','ForumBrowser-DejaVuSans.ttf')
	dialogPath = os.path.join(skinPath,'720p','DialogKeyboard.xml')
	backupPath = os.path.join(skinPath,'720p','DialogKeyboard.xml.FBbackup')
	fontPath = os.path.join(skinPath,'720p','Font.xml')
	fontBackupPath = os.path.join(skinPath,'720p','Font.xml.FBbackup')
	if not os.path.exists(dialogPath):
		dialogPath = dialogPath.replace('720p','1080i')
		backupPath = backupPath.replace('720p','1080i')
		fontPath = fontPath.replace('720p','1080i')
		fontBackupPath = fontBackupPath.replace('720p','1080i')
		sourceFontXMLPath = sourceFontXMLPath.replace('720p','1080i')
	
	LOG('Local Addons Path: %s' % localAddonsPath)
	LOG('Current skin: %s' % currentSkin)
	LOG('Skin path: %s' % skinPath)
	LOG('Keyboard target path: %s' % dialogPath)
	
	copyFont(sourceFontPath,skinPath)
	fontcontents = open(fontPath,'r').read()
	if not os.path.exists(fontBackupPath) or not 'Forum Browser' in fontcontents:
		LOG('Creating backup of original Font.xml file: ' + fontBackupPath)
		open(fontBackupPath,'w').write(fontcontents)
		
	if not 'Forum Browser' in fontcontents or update:
		LOG('Modifying contents of Font.xml with: ' + sourceFontXMLPath)
		original = open(fontPath,'r').read()
		modded = original.replace('<font>',open(sourceFontXMLPath,'r').read() + '<font>',1)
		open(fontPath,'w').write(modded)
	dialogs.showMessage('Done','','Font installed')
	
	if update and not getSetting('use_keyboard_mod',False): return
	
	yes = xbmcgui.Dialog().yesno('Keyboard Mod','Install keyboard skin mod?','THIS WILL REPLACE THE CURRENT XBMC KEYBOARD')
	setSetting('use_keyboard_mod',yes and 'true' or 'false')
	
	if yes:
		keyboardFile = chooseKeyboardFile(fbPath,currentSkin)
		if not keyboardFile: return
		sourcePath = os.path.join(fbPath,'keyboard',keyboardFile)
		LOG('Keyboard source path: %s' % sourcePath)
		copyKeyboardModImages(skinPath)
		keyboardcontents = open(dialogPath,'r').read()
		if not os.path.exists(backupPath) or not 'Forum Browser' in keyboardcontents:
			LOG('Creating backup of original DialogKeyboard.xml file: ' + backupPath)
			open(backupPath,'w').write(open(dialogPath,'r').read())
		
		if not 'Forum Browser' in keyboardcontents or update:
			LOG('Replacing DialogKeyboard.xml with: ' + sourcePath)
			os.remove(dialogPath)
			open(dialogPath,'w').write(open(sourcePath,'r').read())
		dialogs.showMessage('Done','','Keyboard installed')
	else:
		dialogs.showMessage('Aborted','','Keyboard [B]NOT[/B] installed',"[CR]Enable 'Use keyboard mod' in settings if you want to install it at a later time.")

def chooseKeyboardFile(fbPath,currentSkin):
	files = os.listdir(os.path.join(fbPath,'keyboard'))
	skins = []
	for f in files:
		if f.startswith('DialogKeyboard-'):
			skinName = f.split('-',1)[-1].rsplit('.',1)[0].lower()
			if skinName in currentSkin.lower() or skinName == 'generic': skins.append(skinName.title())
	idx = xbmcgui.Dialog().select('Select Skin',skins)
	if idx < 0: return None
	return 'DialogKeyboard-%s.xml' % skins[idx].lower()