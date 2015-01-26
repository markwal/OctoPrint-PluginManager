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

        self.fromResponse = function(data) {
            self.plugins.updateItems(data.plugins);
        };

        self.requestData = function() {
            $.ajax({
                url: API_BASEURL + "plugin/plugin_manager",
                type: "GET",
                dataType: "json",
                success: self.fromResponse
            });
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
    ADDITIONAL_VIEWMODELS.push([PluginManagerViewModel, ["loginStateViewModel", "settingsViewModel"], document.getElementById("settings_plugin_plugin_manager")]);
});
