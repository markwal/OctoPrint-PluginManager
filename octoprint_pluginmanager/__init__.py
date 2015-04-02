# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import octoprint.plugin
import octoprint.plugin.core

from octoprint.settings import valid_boolean_trues
from flask import jsonify, make_response

class PluginManagerPlugin(octoprint.plugin.SimpleApiPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.AssetPlugin,
                          octoprint.plugin.SettingsPlugin):

	def __init__(self):
		self._pending_enable = set()
		self._pending_disable = set()
		self._pending_install = set()
		self._pending_uninstall = set()

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
			"enable": ["plugin"],
			"disable": ["plugin"]
		}

	def on_api_get(self, request):
		plugins = self._plugin_manager.plugins
		disabled_plugins = self._plugin_manager.disabled_plugins

		result = []
		for d in (plugins, disabled_plugins):
			for name, plugin in d.items():
				result.append(self._to_external_representation(plugin))

		return jsonify(plugins=result)

	def on_api_command(self, command, data):
		if command == "install":
			url = data["url"]
			return self.command_install(url, force="force" in data and data["force"] in valid_boolean_trues)

		elif command == "uninstall":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.all_plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)

			plugin = self._plugin_manager.all_plugins[plugin_name]
			return self.command_uninstall(plugin)

		elif command == "enable" or command == "disable":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.all_plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)

			plugin = self._plugin_manager.all_plugins[plugin_name]
			return self.command_toggle(plugin, command)

	def command_install(self, url, force=False):
		try:
			import pip as _pip
		except:
			return make_response("Could not instantiate pip, can't install that, sorry", 500)

		import pkg_resources

		def working_set_callback(distribution):
			self._logger.info("WOrking set changed: {!r}".format(distribution))
		pkg_resources.working_set.subscribe(working_set_callback)

		# TODO need to solve issue of users externally modifying plugin folder, which could lead to more than
		# one plugin being found after installation of a package
		all_plugins_before = self._plugin_manager.all_plugins

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

		self._plugin_manager.reload_plugins()
		all_plugins_after = self._plugin_manager.all_plugins

		new_plugins = set(all_plugins_after.keys()) - set(all_plugins_before.keys())
		if len(new_plugins) == 0 or len(new_plugins) > 1:
			# no new plugin or more than one new plugin? Something must have gone wrong...
			return make_response("Installed plugin, but could not find it afterwards", 500)

		new_plugin_key = new_plugins.pop()
		new_plugin = all_plugins_after[new_plugin_key]

		needs_restart = new_plugin.implementation and isinstance(new_plugin.implementation, octoprint.plugin.core.RestartNeedingPlugin)
		needs_refresh = new_plugin.implementation and isinstance(new_plugin.implementation, octoprint.plugin.ReloadNeedingPlugin)

		if not needs_restart:
			try:
				self._plugin_manager.enable_plugin(new_plugin_key, plugin=new_plugin)
			except octoprint.plugin.core.PluginLifecycleException as e:
				self._logger.exception("Problem enabling plugin {name}".format(name=new_plugin_key))
				return jsonify(result=False, installed=True, enabled=False, reason=e.reason)

		self._plugin_manager.log_all_plugins()

		return jsonify(dict(result=True, needs_restart=needs_restart, needs_refresh=needs_refresh, plugin=self._to_external_representation(new_plugin)))

	def command_uninstall(self, plugin):
		if plugin.key == "pluginmanager":
			return make_response("Can't uninstall Plugin Manager", 400)

		if plugin.bundled:
			return make_response("Bundled plugins cannot be uninstalled", 400)

		if plugin.origin[0] == "entry_point":
			try:
				import pip as _pip
			except:
				return make_response("Could not instantiate pip, can't install that, sorry", 500)

			# plugin is installed through entry point, need to use pip to uninstall it
			pip_args = ["uninstall", "--yes", plugin.origin[2]]
			_pip.main(pip_args)

		elif plugin.origin[0] == "folder":
			# plugin is installed via a plugin folder, need to use rmtree to get rid of it
			import shutil
			import os
			shutil.rmtree(os.path.realpath(plugin.location))

		needs_restart = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.core.RestartNeedingPlugin)
		needs_refresh = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.ReloadNeedingPlugin)

		if not needs_restart:
			try:
				self._plugin_manager.disable_plugin(plugin.key, plugin=plugin)
			except octoprint.plugin.core.PluginLifecycleException as e:
				self._logger.exception("Problem disabling plugin {name}".format(name=plugin.key))
				return jsonify(result=False, uninstalled=True, disabled=False, unloaded=False, reason=e.reason)

			try:
				self._plugin_manager.unload_plugin(plugin.key)
			except octoprint.plugin.core.PluginLifecycleException as e:
				self._logger.exception("Problem unloading plugin {name}".format(name=plugin.key))
				return jsonify(result=False, uninstalled=True, disabled=True, unloaded=False, reason=e.reason)

		return jsonify(result=True, needs_restart=needs_restart, needs_refresh=needs_refresh, plugin=self._to_external_representation(plugin))

	def command_toggle(self, plugin, command):
		if plugin.key == "pluginmanager":
			return make_response("Can't enable/disable Plugin Manager", 400)

		needs_restart = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.core.RestartNeedingPlugin)
		needs_refresh = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.ReloadNeedingPlugin)

		try:
			if command == "disable":
				self._mark_plugin_disabled(plugin, needs_restart=needs_restart)
			elif command == "enable":
				self._mark_plugin_enabled(plugin, needs_restart=needs_restart)
		except octoprint.plugin.core.PluginLifecycleException as e:
			self._logger.exception("Problem toggling enabled state of {name}: {reason}".format(name=plugin.key, reason=e.reason))
			return jsonify(result=False, reason=e.reason)
		except octoprint.plugin.core.RestartNeedingPlugin:
			return jsonify(result=True, needs_restart=True, needs_refresh=True, plugin=self._to_external_representation(plugin))
		else:
			return jsonify(result=True, needs_restart=needs_restart, needs_refresh=needs_refresh, plugin=self._to_external_representation(plugin))

	def _mark_plugin_enabled(self, plugin, needs_restart=False):
		disabled_list = list(self._settings.global_get(["plugins", "_disabled"]))
		if plugin.key in disabled_list:
			disabled_list.remove(plugin.key)
			self._settings.global_set(["plugins", "_disabled"], disabled_list)
			self._settings.save(force=True)

		if not needs_restart:
			self._plugin_manager.enable_plugin(plugin.key)
		else:
			if plugin.key in self._pending_disable:
				self._pending_disable.remove(plugin.key)
			elif not plugin.enabled and plugin.key not in self._pending_enable:
				self._pending_enable.add(plugin.key)

	def _mark_plugin_disabled(self, plugin, needs_restart=False):
		disabled_list = list(self._settings.global_get(["plugins", "_disabled"]))
		if not plugin.key in disabled_list:
			disabled_list.append(plugin.key)
			self._settings.global_set(["plugins", "_disabled"], disabled_list)
			self._settings.save(force=True)

		if not needs_restart:
			self._plugin_manager.disable_plugin(plugin.key)
		else:
			if plugin.key in self._pending_enable:
				self._pending_enable.remove(plugin.key)
			elif plugin.enabled and plugin.key not in self._pending_disable:
				self._pending_disable.add(plugin.key)

	def _to_external_representation(self, plugin):
		return dict(
			key=plugin.key,
			name=plugin.name,
			description=plugin.description,
			author=plugin.author,
			version=plugin.version,
			url=plugin.url,
			license=plugin.license,
			bundled=plugin.bundled,
			enabled=plugin.enabled,
			pending_enable=(not plugin.enabled and plugin.key in self._pending_enable),
			pending_disable=(plugin.enabled and plugin.key in self._pending_disable),
			pending_install=(plugin.key in self._pending_install),
			pending_uninstall=(plugin.key in self._pending_uninstall)
		)

__plugin_name__ = "Plugin Manager"
__plugin_implementation__ = PluginManagerPlugin()