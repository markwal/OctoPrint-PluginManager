$(function() {
    function PluginManagerViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];

        self.plugins = new ItemListHelper(
            "plugin.pluginmanager.installedplugins",
            {
                "name": function (a, b) {
                    // sorts ascending
                    if (a["name"].toLocaleLowerCase() < b["name"].toLocaleLowerCase()) return -1;
                    if (a["name"].toLocaleLowerCase() > b["name"].toLocaleLowerCase()) return 1;
                    return 0;
                }
            },
            {
            },
            "name",
            [],
            [],
            5
        );

        self.repositoryplugins = new ItemListHelper(
            "plugin.pluginmanager.repositoryplugins",
            {
                "title": function (a, b) {
                    // sorts ascending
                    if (a["title"].toLocaleLowerCase() < b["title"].toLocaleLowerCase()) return -1;
                    if (a["title"].toLocaleLowerCase() > b["title"].toLocaleLowerCase()) return 1;
                    return 0;
                },
                "published": function (a, b) {
                    // sorts descending
                    if (a["published"].toLocaleLowerCase() > b["published"].toLocaleLowerCase()) return -1;
                    if (a["published"].toLocaleLowerCase() < b["published"].toLocaleLowerCase()) return 1;
                    return 0;
                }
            },
            {
                "filter_installed": function(plugin) {
                    return !self.installed(plugin);
                }
            },
            "title",
            ["filter_installed"],
            [],
            5
        );

        self.installUrl = ko.observable();
        self.loglines = ko.observableArray([]);
        self.installedPlugins = ko.observableArray([]);

        self.working = ko.observable(false);
        self.workingTitle = ko.observable();
        self.workingDialog = undefined;
        self.workingOutput = undefined;

        self.fromResponse = function(data) {
            self._fromPluginsResponse(data.plugins);
            self._fromRepositoryResponse(data.repository)
        };

        self._fromPluginsResponse = function(data) {
            var installedPlugins = [];
            _.each(data, function(plugin) {
                installedPlugins.push(plugin.key);
            });
            self.installedPlugins(installedPlugins);
            self.plugins.updateItems(data);
        };

        self._fromRepositoryResponse = function(data) {
            self.repositoryplugins.updateItems(data);
        };

        self.requestData = function(includeRepo) {
            $.ajax({
                url: API_BASEURL + "plugin/pluginmanager" + ((includeRepo) ? "?repository=true" : ""),
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            });
        };

        self.togglePlugin = function(data) {
            if (data.key == "pluginmanager") return;

            var command = self._getToggleCommand(data);

            var payload = {plugin: data.key};
            self._postCommand(command, payload, function(response) {
                self.requestData();
            }, function() {
                new PNotify({
                    title: gettext("Something went wrong"),
                    text: gettext("Please consult octoprint.log for details"),
                    type: "error",
                    hide: false
                })
            });
        };

        self.showRepository = function() {
            self.repositoryDialog.modal("show");
        };

        self.pluginDetails = function(data) {
            window.open(data.page);
        };

        self.installFromRepository = function(data) {
            self.installPlugin(data.archive);
        };

        self.installPlugin = function(url) {
            if (url === undefined) {
                url = self.installUrl();
            }
            if (!url) return;

            self._markWorking(gettext("Installing plugin..."), _.sprintf(gettext("Installing plugin from %(url)s..."), {url: url}));

            var command = "install";
            var payload = {url: url};
            self._postCommand(command, payload, function(response) {
                self.requestData();
                self._markDone();
                self.installUrl("");
            }, function() {
                new PNotify({
                    title: gettext("Something went wrong"),
                    text: gettext("Please consult octoprint.log for details"),
                    type: "error",
                    hide: false
                });
                self._markDone();
            });
        };

        self.uninstallPlugin = function(data) {
            if (data.bundled) return;
            if (data.key == "pluginmanager") return;

            self._markWorking(gettext("Uninstalling plugin..."), _.sprintf(gettext("Uninstalling plugin %(name)s"), {name: data.name}));

            var command = "uninstall";
            var payload = {plugin: data.key};
            self._postCommand(command, payload, function(response) {
                self.requestData();
                self._markDone();
            }, function() {
                new PNotify({
                    title: gettext("Something went wrong"),
                    text: gettext("Please consult octoprint.log for details"),
                    type: "error",
                    hide: false
                });
                self._markDone();
            });
        };

        self.refreshRepository = function() {
            self._postCommand("refresh_repository", {}, function(data) {
                self._fromRepositoryResponse(data.repository);
            })
        };

        self.installed = function(data) {
            return _.includes(self.installedPlugins(), data.id);
        };

        self._displayNotification = function(response, titleSuccess, textSuccess, textRestart, textReload, titleError, textError) {
            if (response.result) {
                if (response.needs_restart) {
                    new PNotify({
                        title: titleSuccess,
                        text: textRestart,
                        hide: false
                    });
                } else if (response.needs_refresh) {
                    new PNotify({
                        title: titleSuccess,
                        text: textReload,
                        confirm: {
                            confirm: true,
                            buttons: [{
                                text: gettext("Reload now"),
                                click: function () {
                                    location.reload(true);
                                }
                            }]
                        },
                        buttons: {
                            closer: false,
                            sticker: false
                        },
                        hide: false
                    })
                } else {
                    new PNotify({
                        title: titleSuccess,
                        text: textSuccess,
                        type: "success",
                        hide: false
                    })
                }
            } else {
                new PNotify({
                    title: gettext("Something went wrong"),
                    text: gettext("Toggling the plugin failed, please see the log for details"),
                    type: "error",
                    hide: false
                });
            }
        };

        self._postCommand = function (command, data, successCallback, failureCallback, alwaysCallback, timeout) {
            var payload = _.extend(data, {command: command});

            var params = {
                url: API_BASEURL + "plugin/pluginmanager",
                type: "POST",
                dataType: "json",
                data: JSON.stringify(payload),
                contentType: "application/json; charset=UTF-8",
                success: function(response) {
                    if (successCallback) successCallback(response);
                },
                error: function() {
                    if (failureCallback) failureCallback();
                },
                complete: function() {
                    if (alwaysCallback) alwaysCallback();
                }
            };

            if (timeout != undefined) {
                params.timeout = timeout;
            }

            $.ajax(params);
        };

        self._markWorking = function(title, line) {
            self.working(true);
            self.workingTitle(title);

            self.loglines.removeAll();
            self.loglines.push({line: line, stream: "message"});

            self.workingDialog.modal("show");
        };

        self._markDone = function() {
            self.working(false);
            self.loglines.push({line: gettext("Done!"), stream: "message"});
            self._scrollWorkingOutputToEnd();
        };

        self._scrollWorkingOutputToEnd = function() {
            self.workingOutput.scrollTop(self.workingOutput[0].scrollHeight - self.workingOutput.height());
        };

        self._getToggleCommand = function(data) {
            return ((!data.enabled || data.pending_disable) && !data.pending_enable) ? "enable" : "disable";
        };

        self.toggleButtonCss = function(data) {
            var icon = self._getToggleCommand(data) == "enable" ? "icon-circle-blank" : "icon-circle";
            var disabled = (data.key == "pluginmanager") ? " disabled" : "";

            return icon + disabled;
        };

        self.toggleButtonTitle = function(data) {
            return self._getToggleCommand(data) == "enable" ? gettext("Enable Plugin") : gettext("Disable Plugin");
        };

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
        };

        self.onUserLoggedIn = function(user) {
            if (user.admin) {
                self.requestData(true);
            }
        };

        self.onStartup = function() {
            self.workingDialog = $("#settings_plugin_pluginmanager_workingdialog");
            self.workingOutput = $("#settings_plugin_pluginmanager_workingdialog_output");
            self.repositoryDialog = $("#settings_plugin_pluginmanager_repositorydialog");

            $("#settings_plugin_pluginmanager_repositorydialog_list").slimScroll({
                height: "306px",
                size: "5px",
                distance: "0",
                railVisible: true,
                alwaysVisible: true,
                scrollBy: "102px"
            });
        };

        self.onDataUpdaterPluginMessage = function(plugin, data) {
            if (plugin != "pluginmanager") {
                return;
            }

            if (!data.hasOwnProperty("type")) {
                return;
            }

            var messageType = data.type;

            if (messageType == "loglines" && self.working()) {
                _.each(data.loglines, function(line) {
                    self.loglines.push(line);
                });
                self._scrollWorkingOutputToEnd();
            } else if (messageType == "result") {
                var titleSuccess, textSuccess, textRestart, textReload, titleError, textError;
                var action = data.action;

                var name = "Unknown";
                if (action == "install") {
                    if (data.hasOwnProperty("plugin")) {
                        name = data.plugin.name;
                    }

                    titleSuccess = _.sprintf(gettext("Plugin %(name)s installed"), {name: name});
                    textSuccess = gettext("The plugin was installed successfully");
                    textRestart = gettext("The plugin was installed successfully, however a restart of OctoPrint is needed for that to take effect.");
                    textReload = gettext("The plugin was installed successfully, however a reload of the page is needed for that to take effect.");

                    titleError = gettext("Something went wrong");
                    var url = "unknown";
                    if (data.hasOwnProperty("url")) {
                        url = data.url;
                    }

                    if (data.hasOwnProperty("reason")) {
                        textError = _.sprintf(gettext("Installing the plugin from URL \"%(url)s\" failed: %(reason)s"), {reason: data.reason, url: url});
                    } else {
                        textError = _.sprintf(gettext("Installing the plugin from URL \"%(url)s\" failed, please see the log for details."), {url: url});
                    }

                } else if (action == "uninstall") {
                    if (data.hasOwnProperty("plugin")) {
                        name = data.plugin.name;
                    }

                    titleSuccess = _.sprintf(gettext("Plugin %(name)s uninstalled"), {name: name});
                    textSuccess = gettext("The plugin was uninstalled successfully");
                    textRestart = gettext("The plugin was uninstalled successfully, however a restart of OctoPrint is needed for that to take effect.");
                    textReload = gettext("The plugin was uninstalled successfully, however a reload of the page is needed for that to take effect.");

                    titleError = gettext("Something went wrong");
                    if (data.hasOwnProperty("reason")) {
                        textError = _.sprintf(gettext("Uninstalling the plugin failed: %(reason)s"), {reason: data.reason});
                    } else {
                        textError = gettext("Uninstalling the plugin failed, please see the log for details.");
                    }

                } else if (action == "enable") {
                    if (data.hasOwnProperty("plugin")) {
                        name = data.plugin.name;
                    }

                    titleSuccess = _.sprintf(gettext("Plugin %(name)s enabled"), {name: name});
                    textSuccess = gettext("The plugin was enabled successfully.");
                    textRestart = gettext("The plugin was enabled successfully, however a restart of OctoPrint is needed for that to take effect.");
                    textReload = gettext("The plugin was enabled successfully, however a reload of the page is needed for that to take effect.");

                    titleError = gettext("Something went wrong");
                    if (data.hasOwnProperty("reason")) {
                        textError = _.sprintf(gettext("Toggling the plugin failed: %(reason)s"), {reason: data.reason});
                    } else {
                        textError = gettext("Toggling the plugin failed, please see the log for details.");
                    }

                } else if (action == "disable") {
                    if (data.hasOwnProperty("plugin")) {
                        name = data.plugin.name;
                    }

                    titleSuccess = _.sprintf(gettext("Plugin %(name)s disabled"), {name: name});
                    textSuccess = gettext("The plugin was disabled successfully.");
                    textRestart = gettext("The plugin was disabled successfully, however a restart of OctoPrint is needed for that to take effect.");
                    textReload = gettext("The plugin was disabled successfully, however a reload of the page is needed for that to take effect.");

                    titleError = gettext("Something went wrong");
                    if (data.hasOwnProperty("reason")) {
                        textError = _.sprintf(gettext("Toggling the plugin failed: %(reason)s"), {reason: data.reason});
                    } else {
                        textError = gettext("Toggling the plugin failed, please see the log for details.");
                    }

                } else {
                    return;
                }

                self._displayNotification(data, titleSuccess, textSuccess, textRestart, textReload, titleError, textError);
                self.requestData();
            }
        };
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([PluginManagerViewModel, ["loginStateViewModel", "settingsViewModel"], "#settings_plugin_pluginmanager"]);
});
