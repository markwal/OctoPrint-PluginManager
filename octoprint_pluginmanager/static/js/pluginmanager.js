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

            var command = "toggle";
            var payload = {plugin: data.key};
            self._postCommand(command, payload, function() {self.requestData()});
        };

        self.installPlugin = function() {
            var url = self.installUrl();
            if (!url) return;

            var command = "install";
            var payload = {url: url};
            self._postCommand(command, payload, function() {self.requestData()});
        };

        self.uninstallPlugin = function(data) {
            if (data.bundled) return;
            if (data.key == "pluginmanager") return;

            var command = "uninstall";
            var payload = {plugin: data.key};
            self._postCommand(command, payload, function() {self.requestData()});
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

        self.onBeforeBinding = function() {
            self.settings = self.settingsViewModel.settings;
            self.requestData();
        };

        self.onDataUpdaterReconnect = function() {
            self.requestData();
        };
    }

    // view model class, parameters for constructor, container to bind to
    ADDITIONAL_VIEWMODELS.push([PluginManagerViewModel, ["loginStateViewModel", "settingsViewModel"], document.getElementById("settings_plugin_pluginmanager")]);
});
