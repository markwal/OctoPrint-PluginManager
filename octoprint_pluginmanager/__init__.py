# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


__plugin_name__ = "Plugin Manager"
__plugin_description__ = "The OctoPrint Plugin Manager allows managing OctoPrint plugins"
__plugin_version__ = "0.1"
__plugin_author__ = "The OctoPrint Project"
__plugin_url__ = "http://octoprint.org"

import octoprint.plugin

from octoprint.settings import valid_boolean_trues
from flask import jsonify, make_response

default_settings = dict()
s = octoprint.plugin.plugin_settings("plugin_manager", defaults=default_settings)

class PluginManagerPlugin(octoprint.plugin.SimpleApiPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.AssetPlugin):

	##~~ AssetPlugin

	def get_assets(self):
		return dict(
			js=["js/pluginmanager.js"],
			css=["css/pluginmanager.css"],
			less=["less/pluginmanager.less"]
		)

	##~~ TemplatePlugin

	def get_template_configs(self):
		return [
			dict(type="settings", template="pluginmanager_settings.jinja2", custom_bindings=True)
		]

	##~~ SimpleApiPlugin

	def get_api_commands(self):
		return {
			"install": ["url"],
			"uninstall": ["plugin"],
			"toggle": ["plugin"]
		}

	def on_api_get(self, request):
		plugins = self._plugin_manager.plugins
		disabled_plugins = self._plugin_manager.disabled_plugins

		result = []
		for d in (plugins, disabled_plugins):
			for name, plugin in d.items():
				result.append(dict(
					key=name,
					name=plugin.name,
					description=plugin.description,
					author=plugin.author,
					version=plugin.version,
					url=plugin.url,
					license=plugin.license,
					bundled=plugin.bundled,
					enabled=plugin.enabled
				))

		return jsonify(plugins=result)

	def on_api_command(self, command, data):
		if command == "install":
			url = data["url"]
			return self.command_install(url, force="force" in data and data["force"] in valid_boolean_trues)

		elif command == "uninstall":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)

			plugin = self._plugin_manager.plugins[plugin_name]
			return self.command_uninstall(plugin)

		elif command == "toggle":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)

			plugin = self._plugin_manager.plugins[plugin_name]
			return self.command_toggle(plugin)

	def command_install(self, url, force=False):
		try:
			import pip as _pip
		except:
			return make_response("Could not instantiate pip, can't install that, sorry", 500)

		pip_args = ["install", url]
		try:
			_pip.main(pip_args)
		except:
			self._logger.exception("Could not install plugin from %s" % url)
			return make_response("Could not install plugin from url, see the log for more details", 500)
		else:
			if force:
				pip_args += ["--ignore-installed", "--force-reinstall", "--no-deps"]
				try:
					_pip.main(pip_args)
				except:
					self._logger.exception("Could not install plugin from %s" % url)
					return make_response("Could not install plugin from url, see the log for more details", 500)

	def command_uninstall(self, plugin):
		if plugin.key == "pluginmanager":
			return make_response("Can't uninstall Plugin Manager", 400)

		try:
			import pip as _pip
		except:
			return make_response("Could not instantiate pip, can't install that, sorry", 500)

		if plugin.bundled:
			return make_response("Bundled plugins cannot be uninstalled", 400)

		if plugin.origin[0] == "entry_point":
			# plugin is installed through entry point, need to use pip to uninstall it
			pip_args = ["uninstall", "--yes", plugin.origin[2]]
			_pip.main(pip_args)

		elif plugin.origin[0] == "folder":
			# plugin is installed via a plugin folder, need to use rmtree to get rid of it
			import shutil
			import os
			shutil.rmtree(os.path.realpath(plugin.location))

	def command_toggle(self, plugin):
		if plugin.key == "pluginmanager":
			return make_response("Can't enable/disable Plugin Manager", 400)

		if plugin.enabled:
			# disabled plugin
			pass
		else:
			# enable plugin
			pass


__plugin_implementations__ = [PluginManagerPlugin()]