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

from flask import jsonify, make_response

default_settings = dict()
s = octoprint.plugin.plugin_settings("plugin_manager", defaults=default_settings)

class PluginManagerPlugin(octoprint.plugin.SimpleApiPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.AssetPlugin):

	##~~ AssetPlugin

	def get_assets(self):
		return dict(
			js=["js/plugin_manager.js"],
			css=["css/plugin_manager.css"],
			less=["less/plugin_manager.less"]
		)

	##~~ TemplatePlugin

	def get_template_configs(self):
		return [
			dict(type="settings", template="plugin_manager_settings.jinja2", custom_bindings=True)
		]

	##~~ SimpleApiPlugin

	def get_api_commands(self):
		return {
			"install": ["url"],
			"uninstall": ["plugin"]
		}

	def on_api_get(self, request):
		plugins = self._plugin_manager.plugins

		result = []
		for name, plugin in plugins.items():
			result.append(dict(key=name, name=plugin.name, description=plugin.description, author=plugin.author, version=plugin.version, url=plugin.url))

		return jsonify(plugins=result)

	def on_api_command(self, command, data):
		try:
			import pip as _pip
		except:
			return make_response("Could not instantiate pip, can't install that, sorry", 500)

		if command == "uninstall":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)
			plugin = self._plugin_manager.plugins[plugin_name]
			origin_type, origin_location = plugin.origin

			if origin_type == "entry_point":
				# plugin is installed through entry point, need to use pip to uninstall it
				pip_args = ["uninstall", plugin.identifier]
				_pip.main(pip_args)

			elif origin_type == "folder":
				# plugin is installed via a plugin folder, need to use rmtree to get rid of it

				# first make sure that the plugin folder is our custom one!
				global s
				if not origin_location.startswith(s.globalGetBaseFolder("plugins")):
					return make_response("Only user installed plugins are allowed to be uninstalled", 400)

				# all clear, remove it
				import shutil
				import os
				shutil.rmtree(os.path.realpath(plugin.location))


__plugin_implementations__ = [PluginManagerPlugin()]