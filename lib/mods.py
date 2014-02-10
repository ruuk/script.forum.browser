import os, re, xbmc, xbmcgui, xbmcvfs, dialogs
from distutils.version import StrictVersion
from util import ERROR, LOG, getSetting, setSetting, __addon__, T

DEBUG = None
CACHE_PATH = None

def copyKeyboardModImages(skinPath):
	dst = os.path.join(skinPath,'media','forum-browser-keyboard')
	#if os.path.exists(dst): return
	if not os.path.exists(dst): os.makedirs(dst)
	src = os.path.join(xbmc.translatePath(__addon__.getAddonInfo('path')),'keyboard','images')
	for f in os.listdir(src):
		s = os.path.join(src,f)
		d = os.path.join(dst,f)
		if not os.path.exists(d) and not f.startswith('.'): xbmcvfs.copy(s,d)

def copyFont(sourceFontPath,skinPath):
	dst = os.path.join(skinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	if os.path.exists(dst): xbmcvfs.delete(dst)
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
			if dialog: dialog.update(pct,T(32478),f)
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
	

def getSkinFilePath(skinPath,skinFile):
	skinPath = os.path.join(skinPath,'720p',skinFile)
	if not os.path.exists(skinPath): skinPath = os.path.join(skinPath,'1080i',skinFile)
	if not os.path.exists(skinPath): return None
	return skinPath
	
def checkKBModRemove(skinPath):
		backupPath = getSkinFilePath(skinPath,'DialogKeyboard.xml.FBbackup')
		dialogPath = getSkinFilePath(skinPath,'DialogKeyboard.xml')
		if backupPath and dialogPath:
			xbmcvfs.delete(dialogPath)
			xbmcvfs.rename(backupPath,dialogPath)
			setSetting('keyboard_installed',False)
			dialogs.showMessage(T(32476),T(32476),' ',T(32477))
			return True

def ensureLocalSkin(paths=None):
	paths = paths or getPaths()
	version = getSkinVersion(paths.skinPath)
	version2 = getSkinVersion(paths.localSkinPath)

	if not os.path.exists(paths.localSkinPath) or StrictVersion(version2) < StrictVersion(version):
		yesno = xbmcgui.Dialog().yesno(T(32486),T(32487).format(paths.currentSkin),T(32488),T(32489))
		if not yesno: return
		dialog = xbmcgui.DialogProgress()
		dialog.create(T(32490),T(32491))
		try:
			copyTree(paths.skinPath,paths.localSkinPath,dialog)
		except:
			err = ERROR('Failed to copy skin to user directory')
			dialogs.showMessage(T(32050),err,T(32492),error=True)
			return
		finally:
			dialog.close()
		#restart = True
		dialogs.showMessage(T(32304),T(32493),T(32494),success=True)
		return getPaths()
	else:
		return paths
		
def fontInstalled(paths=None):
	paths = paths or getPaths()
	
	font = os.path.join(paths.skinPath,'fonts','ForumBrowser-DejaVuSans.ttf')
	installed = False
	if os.path.exists(font):
		if StrictVersion(paths.versionLocal) >= StrictVersion(paths.versionUsed):
			if os.path.exists(paths.fontPath):
				contents = open(paths.fontPath,'r').read()
				if 'Forum Browser' in contents:
					LOG('Fonts mod detected')
					installed = True
	setSetting('font_installed',installed)
	return installed
	
def keyboardInstalled(paths=None):
	paths = paths or getPaths()
	if os.path.exists(paths.dialogPath):
		keyboardcontents = open(paths.dialogPath,'r').read()
		if 'Forum Browser' in keyboardcontents:
			LOG('Keyboard mod detected')
			setSetting('keyboard_installed',True)
			return True
	return False
			
def checkForSkinMods():
	paths = getPaths()
	skinName = os.path.basename(paths.skinPath)
	LOG('XBMC Skin (In Use): %s %s' % (skinName,paths.versionUsed))
	LOG('XBMC Skin   (Home): %s %s' % (skinName,paths.versionLocal))
	update = False
	
	if not fontInstalled(paths) and getSetting('font_installed',False):
		installFont()
		LOG('Restoring missing font installation')
		update = True
	
	if not keyboardInstalled(paths) and getSetting('keyboard_installed',False):
		installKeyboardMod(update=False,paths=paths)
		LOG('Restoring missing keyboard mod installation')
		update = True
		
	return update
		
def installFont(paths=None,update=False):
	paths = ensureLocalSkin(paths)
	copyFont(paths.sourceFontPath,paths.localSkinPath)
	fontcontents = open(paths.fontPath,'r').read()
	if not os.path.exists(paths.fontBackupPath) or not 'Forum Browser' in fontcontents:
		LOG('Creating backup of original Font.xml file: ' + paths.fontBackupPath)
		open(paths.fontBackupPath,'w').write(fontcontents)
		
	if not 'Forum Browser' in fontcontents or update:
		LOG('Modifying contents of Font.xml with: ' + paths.sourceFontXMLPath)
		if os.path.exists(paths.fontBackupPath): #because we're updating
			original = open(paths.fontBackupPath,'r').read()
		else:
			original = open(paths.fontPath,'r').read()
		modded = original.replace('<font>',open(paths.sourceFontXMLPath,'r').read() + '<font>',1)
		open(paths.fontPath,'w').write(modded)
	dialogs.showMessage(T(32052),'',T(32495))
	
def unInstallFont(paths=None):
	paths = paths or getPaths()
	if not os.path.exists(paths.fontBackupPath): return False
	if os.path.exists(paths.fontPath): xbmcvfs.delete(paths.fontPath)
	xbmcvfs.rename(paths.fontBackupPath,paths.fontPath)
	dialogs.showMessage(T(32417),T(32590))
	return True
			
def toggleFontInstallation():
	if fontInstalled():
		yes = dialogs.dialogYesNo(T(32466),T(32588),'',T(32466))
		if yes:
			unInstallFont()
			setSetting('font_installed',False)
	else:
		yes = dialogs.dialogYesNo(T(32482),T(32589),'',T(32482))
		if yes:
			installFont()
			setSetting('font_installed',True)

def installKeyboardMod(update=True,paths=None,change=False):
	paths = ensureLocalSkin(paths)
	if change:
		yes = True
	else:
		yes = xbmcgui.Dialog().yesno(T(32496),T(32497),T(32498))
	
	if yes:
		keyboardFile = chooseKeyboardFile(paths.fbPath,paths.currentSkin)
		if not keyboardFile: return True
		sourcePath = os.path.join(paths.fbPath,'keyboard',keyboardFile)
		LOG('Keyboard source path: %s' % sourcePath)
		copyKeyboardModImages(paths.localSkinPath)
		keyboardcontents = open(paths.dialogPath,'r').read()
		if not os.path.exists(paths.backupPath) or not 'Forum Browser' in keyboardcontents:
			LOG('Creating backup of original DialogKeyboard.xml file: ' + paths.backupPath)
			open(paths.backupPath,'w').write(open(paths.dialogPath,'r').read())
		
		if not 'Forum Browser' in keyboardcontents or update:
			LOG('Replacing DialogKeyboard.xml with: ' + sourcePath)
			os.remove(paths.dialogPath)
			open(paths.dialogPath,'w').write(open(sourcePath,'r').read())
		#if getSetting('FBIsRunning',True) and FBrunning:
		#	dialogs.showMessage(T(32052),'',T(32499) + '[CR][CR]' + T(32477))
		#else:
		dialogs.showMessage(T(32052),'',T(32499))
	else:
		dialogs.showMessage(T(32483),T(32521),' ',T(32522))
	return True

def getPaths():
	class paths:
		fbPath = xbmc.translatePath(__addon__.getAddonInfo('path'))
		localAddonsPath = os.path.join(xbmc.translatePath('special://home'),'addons')
		skinPath = xbmc.translatePath('special://skin')
		if skinPath.endswith(os.path.sep): skinPath = skinPath[:-1]
		currentSkin = os.path.basename(skinPath)
		localSkinPath = os.path.join(localAddonsPath,currentSkin)
		sourceFontXMLPath = os.path.join(fbPath,'keyboard','Font-720p.txt')
		sourceFontPath = os.path.join(fbPath,'keyboard','ForumBrowser-DejaVuSans.ttf')
		dialogPath = os.path.join(localSkinPath,'720p','DialogKeyboard.xml')
		backupPath = os.path.join(localSkinPath,'720p','DialogKeyboard.xml.FBbackup')
		fontPath = os.path.join(localSkinPath,'720p','Font.xml')
		fontBackupPath = os.path.join(localSkinPath,'720p','Font.xml.FBbackup')
		if not os.path.exists(dialogPath):
			dialogPath = dialogPath.replace('720p','1080i')
			backupPath = backupPath.replace('720p','1080i')
			fontPath = fontPath.replace('720p','1080i')
			fontBackupPath = fontBackupPath.replace('720p','1080i')
			sourceFontXMLPath = sourceFontXMLPath.replace('720p','1080i')
		versionUsed = getSkinVersion(skinPath)
		versionLocal = getSkinVersion(localSkinPath)
	return paths
	
def chooseKeyboardFile(fbPath,currentSkin):
	files = os.listdir(os.path.join(fbPath,'keyboard'))
	skins = []
	for f in files:
		if f.startswith('DialogKeyboard-'):
			skinName = f.split('-',1)[-1].rsplit('.',1)[0].lower()
			if skinName in currentSkin.lower() or skinName == 'generic' or skinName == 'video': skins.append(skinName.title())
	remove = None
	if keyboardInstalled():
		remove = len(skins)
		skins.append('Remove')
	idx = xbmcgui.Dialog().select(T(32523),skins)
	if idx < 0: return None
	if remove and idx == remove:
		checkKBModRemove(getPaths().skinPath)
		if not keyboardInstalled():
			setSetting('keyboard_installed',False) #Checks and resets the installed setting
			setSetting('current_keyboard_mod','')
		return None
	skin = skins[idx]
	setSetting('current_keyboard_mod',skin)
	return 'DialogKeyboard-%s.xml' % skin.lower()

FTT = None
IS_1080 = False
FONT_SIZES = ((10,12),(12,16),(13,20),(30,30))
FONT_SIZES_1080 = ((10,18),(12,24),(13,30),(30,40))
def createFontsTranslationTable():
	global FTT
	if FTT: return FTT
	FTT = {10:'',12:'',13:'',30:''}
	xbmcSkinFonts = getFontList()
	for name_size, fsize in IS_1080 and FONT_SIZES_1080 or FONT_SIZES:
		closest = 99
		for font, name, size in xbmcSkinFonts:
			test = name.lower() + font.lower()
			if 'cap' in test or 'bold' in test: continue
			try:
				size = int(size)
			except:
				continue
			if fsize == size:
				FTT[name_size] = name
				break
			elif abs(fsize - size) < closest:
				FTT[name_size] = name
				closest = abs(fsize - size)
				
def replaceFonts(xml,is_1080=False):
	createFontsTranslationTable()
	print FTT
	for name_size,fsize in IS_1080 and FONT_SIZES_1080 or FONT_SIZES:  # @UnusedVariable
		xml = xml.replace('ForumBrowser-font%s' % name_size,FTT[name_size])
	return xml

def getFontList():
	with open(getFontXMLPath(),'r') as f: xml = f.read()
	return re.findall('(<font>.*?<name>(.*?)</name>.*?<size>(.*?)</size>.*?</font>)(?is)',xml.split('</fontset>',1)[0])
	
def getDefaultFont(size=12,flist=None):
	size = str(size)
	flist = flist or getFontList()
	for f in flist:
		if size in f and not 'cap' in f.lower(): return f
	return 'font%s' % size
		
def getFontXMLPath():
	skinPath = xbmc.translatePath('special://skin')
	global IS_1080
	res = '720p'
	IS_1080 = False
	if not os.path.exists(os.path.join(skinPath,res)):
		res = '1080i'
		IS_1080 = True
	return os.path.join(skinPath,res,'Font.xml')