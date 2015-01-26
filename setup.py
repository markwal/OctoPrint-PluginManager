# coding=utf-8
import setuptools

def package_data_dirs(source, sub_folders):
	import os
	dirs = []

	for d in sub_folders:
		for dirname, _, files in os.walk(os.path.join(source, d)):
			dirname = os.path.relpath(dirname, source)
			for f in files:
				dirs.append(os.path.join(dirname, f))

	return dirs

def params():
	name = "OctoPrint-PluginManager"
	version = "0.1"

	description = "TODO"
	author = "Gina Häußge"
	author_email = "osd@foosel.net"
	url = "http://octoprint.org"
	license = "AGPLv3"

	packages = setuptools.find_packages()
	package_data = {"octoprint_pluginmanager": package_data_dirs('octoprint_pluginmanager', ['static', 'templates', 'scripts'])}

	include_package_data = True
	zip_safe = False
	install_requires = open("requirements.txt").read().split("\n")

	entry_points = {
		"octoprint.plugin": [
			"pluginmanager = octoprint_pluginmanager"
		]
	}

	return locals()

setuptools.setup(**params())
