$(function() {
    function PluginManagerViewModel(parameters) {
        var self = this;

        self.loginState = parameters[0];
        self.settingsViewModel = parameters[1];

        self.plugins = new ItemListHelper(
            "plugins",
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

        self.installUrl = ko.observable();

        self.fromResponse = function(data) {
            self.plugins.updateItems(data.plugins);
        };

        self.requestData = function() {
            $.ajax({
                url: API_BASEURL + "plugin/pluginmanager",
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            });
        };

        self.togglePlugin = function(data) {
            if (data.key == "pluginmanager") return;

            var titleSuccess, textSuccess, textRestart, textReload, titleError, textError;
            var command;
            if (!data.enabled || data.pending_disable) {
                command = "enable";
                titleSuccess = _.sprintf(gettext("Plugin %(name)s enabled"), {name: data.name});
                textSuccess = gettext("The plugin was enabled successfully.");
                textRestart = gettext("The plugin was enabled successfully, however a restart of OctoPrint is needed for that to take effect.");
                textReload = gettext("The plugin was enabled successfully, however a reload of the page is needed for that to take effect.");
            } else if (data.enabled || data.pending_enable) {
                command = "disable";
                titleSuccess = _.sprintf(gettext("Plugin %(name)s disabled"), {name: data.name});
                textSuccess = gettext("The plugin was disabled successfully.");
                textRestart = gettext("The plugin was disabled successfully, however a restart of OctoPrint is needed for that to take effect.");
                textReload = gettext("The plugin was disabled successfully, however a reload of the page is needed for that to take effect.");
            } else {
                return;
            }

            titleError = gettext("Something went wrong");
            textError = gettext("Toggling the plugin failed, please see the log for details.");
            textErrorReason = gettext("Toggling the plugin failed: %(reason)s");

            var payload = {plugin: data.key};
            self._postCommand(command, payload, function(response) {
                if (!response.result && response.hasOwnProperty("reason") && response.reason) {
                    textError = _.sprintf(textErrorReason, {reason: response.reason});
                }

                self._displayNotification(response, titleSuccess, textSuccess, textRestart, textReload, titleError, textError);
                self.requestData();
            }, function() {
                new PNotify({
                    title: titleError,
                    text: textError,
                    type: "error",
                    hide: false
                })
            });
        };

        self.installPlugin = function() {
            var url = self.installUrl();
            if (!url) return;

            var titleSuccess, textSuccess, textRestart, textReload, titleError, textError, textErrorReason;
            titleSuccess = gettext("Plugin %(name)s installed");
            textSuccess = gettext("The plugin was installed successfully");
            textRestart = gettext("The plugin was installed successfully, however a restart of OctoPrint is needed for that to take effect.");
            textReload = gettext("The plugin was installed successfully, however a reload of the page is needed for that to take effect.");
            titleError = gettext("Something went wrong");
            textError = gettext("Installing the plugin from URL %(url)s failed, please see the log for details.");
            textErrorReason = gettext("Installing the plugin from URL %(url)s failed: %(reason)s");

            var command = "install";
            var payload = {url: url};
            self._postCommand(command, payload, function(response) {
                var name = (response.hasOwnProperty("plugin")) ? response.plugin.name : "Unknown";

                if (!response.result && response.hasOwnProperty("reason") && response.reason) {
                    textError = _.sprintf(textErrorReason, {url: url, reason: response.reason});
                } else {
                    textError = _.sprintf(textError, {url: url});
                }

                self._displayNotification(response, _.sprintf(titleSuccess, {name: name}), textSuccess, textRestart, textReload, titleError, textError);
                self.requestData();
            }, function() {
                new PNotify({
                    title: titleError,
                    text: textError,
                    type: "error",
                    hide: false
                })
            });
        };

        self.uninstallPlugin = function(data) {
            if (data.bundled) return;
            if (data.key == "pluginmanager") return;

            var titleSuccess, textSuccess, textRestart, textReload, titleError, textError, textErrorReason;

            titleSuccess = _.sprintf(gettext("Plugin %(name)s uninstalled"), {name: data.name});
            textSuccess = gettext("The plugin was uninstalled successfully");
            textRestart = gettext("The plugin was uninstalled successfully, however a restart of OctoPrint is needed for that to take effect.");
            textReload = gettext("The plugin was uninstalled successfully, however a reload of the page is needed for that to take effect.");
            titleError = gettext("Something went wrong");
            textError = gettext("Uninstalling the plugin failed, please see the log for details.");
            textErrorReason = gettext("Uninstalling the plugin failed: %(reason)s");

            var command = "uninstall";
            var payload = {plugin: data.key};
            self._postCommand(command, payload, function(response) {
                if (!response.result && response.hasOwnProperty("reason") && response.reason) {
                    textError = _.sprintf(textErrorReason, {reason: response.reason});
                }

                self._displayNotification(response, titleSuccess, textSuccess, textRestart, textReload, titleError, textError);
                self.requestData()
            }, function() {
                new PNotify({
                    title: titleError,
                    text: textError,
                    type: "error",
                    hide: false
                })
            });
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

        self.toggleButtonTitle = function(data) {
            return (!data.enabled || data.pending_disable) ? gettext("Enable Plugin") : gettext("Disable Plugin");
        };

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
            self.requestData();
        };

        self.onDataUpdaterReconnect = function() {
            self.requestData();
        };
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([PluginManagerViewModel, ["loginStateViewModel", "settingsViewModel"], "#settings_plugin_pluginmanager"]);
});
