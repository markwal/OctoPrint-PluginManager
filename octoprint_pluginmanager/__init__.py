# coding=utf-8
from __future__ import absolute_import

__author__ = "Gina Häußge <osd@foosel.net>"
__license__ = 'GNU Affero General Public License http://www.gnu.org/licenses/agpl.html'
__copyright__ = "Copyright (C) 2014 The OctoPrint Project - Released under terms of the AGPLv3 License"


import octoprint.plugin
import octoprint.plugin.core

from octoprint.settings import valid_boolean_trues
from flask import jsonify, make_response

import logging
import sarge
import sys

class PluginManagerPlugin(octoprint.plugin.SimpleApiPlugin,
                          octoprint.plugin.TemplatePlugin,
                          octoprint.plugin.AssetPlugin,
                          octoprint.plugin.SettingsPlugin,
                          octoprint.plugin.StartupPlugin):

	def __init__(self):
		self._pending_enable = set()
		self._pending_disable = set()
		self._pending_install = set()
		self._pending_uninstall = set()

	def initialize(self):
		self._console_logger = logging.getLogger("octoprint.plugins.pluginmanager.console")

	##~~ StartupPlugin

	def on_startup(self, host, port):
		console_logging_handler = logging.handlers.RotatingFileHandler(self._settings.get_plugin_logfile_path(postfix="console"), maxBytes=2*1024*1024)
		console_logging_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
		console_logging_handler.setLevel(logging.DEBUG)

		self._console_logger.addHandler(console_logging_handler)
		self._console_logger.setLevel(logging.DEBUG)
		self._console_logger.propagate = False

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

		result = []
		for name, plugin in plugins.items():
			result.append(self._to_external_representation(plugin))

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

		elif command == "enable" or command == "disable":
			plugin_name = data["plugin"]
			if not plugin_name in self._plugin_manager.plugins:
				return make_response("Unknown plugin: %s" % plugin_name, 404)

			plugin = self._plugin_manager.plugins[plugin_name]
			return self.command_toggle(plugin, command)

	def command_install(self, url, force=False):
		# TODO need to solve issue of users externally modifying plugin folder, which could lead to more than
		# one plugin being found after installation of a package
		all_plugins_before = self._plugin_manager.plugins

		pip_args = ["install", sarge.shell_quote(url)]
		try:
			self._call_pip(pip_args)
		except:
			self._logger.exception("Could not install plugin from %s" % url)
			return make_response("Could not install plugin from url, see the log for more details", 500)
		else:
			if force:
				pip_args += ["--ignore-installed", "--force-reinstall", "--no-deps"]
				try:
					self._call_pip(pip_args)
				except:
					self._logger.exception("Could not install plugin from %s" % url)
					return make_response("Could not install plugin from url, see the log for more details", 500)

		self._plugin_manager.reload_plugins()
		all_plugins_after = self._plugin_manager.plugins

		new_plugins = set(all_plugins_after.keys()) - set(all_plugins_before.keys())
		if len(new_plugins) == 0 or len(new_plugins) > 1:
			# no new plugin or more than one new plugin? Something must have gone wrong...
			return make_response("Installed plugin, but could not find it afterwards", 500)

		new_plugin_key = new_plugins.pop()
		new_plugin = all_plugins_after[new_plugin_key]

		needs_restart = new_plugin.implementation and isinstance(new_plugin.implementation, octoprint.plugin.core.RestartNeedingPlugin)
		needs_refresh = new_plugin.implementation and isinstance(new_plugin.implementation, octoprint.plugin.ReloadNeedingPlugin)

		self._plugin_manager.log_all_plugins()

		result = dict(result=True, url=url, needs_restart=needs_restart, needs_refresh=needs_refresh, plugin=self._to_external_representation(new_plugin))
		self._send_result_notification("install", result)
		return jsonify(result)

	def command_uninstall(self, plugin):
		if plugin.key == "pluginmanager":
			return make_response("Can't uninstall Plugin Manager", 400)

		if plugin.bundled:
			return make_response("Bundled plugins cannot be uninstalled", 400)

		if plugin.origin[0] == "entry_point":
			# plugin is installed through entry point, need to use pip to uninstall it
			pip_args = ["uninstall", "--yes", plugin.origin[2]]
			self._call_pip(pip_args)

		elif plugin.origin[0] == "folder":
			# plugin is installed via a plugin folder, need to use rmtree to get rid of it
			self._log_stdout("Deleting plugin from {folder}".format(folder=plugin.location))
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
				result = dict(result=False, uninstalled=True, disabled=False, unloaded=False, reason=e.reason)
				self._send_result_notification("uninstall", result)
				return jsonify(result)

			try:
				self._plugin_manager.unload_plugin(plugin.key)
			except octoprint.plugin.core.PluginLifecycleException as e:
				self._logger.exception("Problem unloading plugin {name}".format(name=plugin.key))
				result = dict(result=False, uninstalled=True, disabled=True, unloaded=False, reason=e.reason)
				self._send_result_notification("uninstall", result)
				return jsonify(result)

		result = dict(result=True, needs_restart=needs_restart, needs_refresh=needs_refresh, plugin=self._to_external_representation(plugin))
		self._send_result_notification("uninstall", result)
		return jsonify(result)

	def command_toggle(self, plugin, command):
		if plugin.key == "pluginmanager":
			return make_response("Can't enable/disable Plugin Manager", 400)

		needs_restart = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.core.RestartNeedingPlugin)
		needs_refresh = plugin.implementation and isinstance(plugin.implementation, octoprint.plugin.ReloadNeedingPlugin)

		pending = ((command == "disable" and plugin.key in self._pending_enable) or (command == "enable" and plugin.key in self._pending_disable))
		needs_restart_api = needs_restart and not pending
		needs_refresh_api = needs_refresh and not pending

		try:
			if command == "disable":
				self._mark_plugin_disabled(plugin, needs_restart=needs_restart)
			elif command == "enable":
				self._mark_plugin_enabled(plugin, needs_restart=needs_restart)
		except octoprint.plugin.core.PluginLifecycleException as e:
			self._logger.exception("Problem toggling enabled state of {name}: {reason}".format(name=plugin.key, reason=e.reason))
			result = dict(result=False, reason=e.reason)
		except octoprint.plugin.core.RestartNeedingPlugin:
			result = dict(result=True, needs_restart=True, needs_refresh=True, plugin=self._to_external_representation(plugin))
		else:
			result = dict(result=True, needs_restart=needs_restart_api, needs_refresh=needs_refresh_api, plugin=self._to_external_representation(plugin))

		self._send_result_notification(command, result)
		return jsonify(result)

	def _send_result_notification(self, action, result):
		notification = dict(type="result", action=action)
		notification.update(result)
		self._plugin_manager.send_plugin_message(self._identifier, notification)

	def _call_pip(self, args):
		python = sys.executable

		command = [python, "-m", "pip"] + args

		self._logger.debug("Calling: {}".format(" ".join(command)))

		p = sarge.run(command, shell=True, async=True, stdout=sarge.Capture(), stderr=sarge.Capture())
		p.wait_events()

		try:
			while p.returncode is None:
				line = p.stderr.readline(timeout=0.5)
				if line:
					self._log_stderr(line)

				line = p.stdout.readline(timeout=0.5)
				if line:
					self._log_stdout(line)

				p.commands[0].poll()

		finally:
			p.close()

		stderr = p.stderr.text
		if stderr:
			self._log_stderr(*stderr.split("\n"))

		stdout = p.stdout.text
		if stdout:
			self._log_stdout(*stdout.split("\n"))

		return p.returncode

	def _log_stdout(self, *lines):
		self._log(lines, prefix=">", stream="stdout")

	def _log_stderr(self, *lines):
		self._log(lines, prefix="!", stream="stderr")

	def _log(self, lines, prefix=None, stream=None, strip=True):
		if strip:
			lines = map(lambda x: x.strip(), lines)

		self._plugin_manager.send_plugin_message(self._identifier, dict(type="loglines", loglines=[dict(line=line, stream=stream) for line in lines]))
		for line in lines:
			self._console_logger.debug("{prefix} {line}".format(**locals()))

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