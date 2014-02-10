# -*- coding: utf-8 -*-
import os, sys, xbmc

if __name__ == '__main__':
	if sys.argv[-1].startswith('settings') or sys.argv[-1] == 'smilies':
		from lib import dialogs, util
		CACHE_PATH = xbmc.translatePath(os.path.join(util.__addon__.getAddonInfo('profile'),'cache'))
		dialogs.CACHE_PATH = CACHE_PATH
		if sys.argv[-1].startswith('settingshelp_'):
			dialogs.showHelp('settings-' + sys.argv[-1].split('_')[-1])
		if sys.argv[-1].startswith('settingsinfo_'):
			dialogs.showInfo(sys.argv[-1].split('_')[-1])
		elif sys.argv[-1] == 'smilies':
			dialogs.smiliesDialog()
	elif sys.argv[-1] == 'change_keyboard':
		from lib import mods,util
		mods.installKeyboardMod(change=True)
		util.setRefreshXBMCSkin()
	elif sys.argv[-1] == 'install_font':
		from lib import mods, util
		mods.toggleFontInstallation()
		util.setRefreshXBMCSkin()
	else:
		import main
		main.init()