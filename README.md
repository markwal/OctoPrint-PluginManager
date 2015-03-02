----

**Note**: This plugin is a work in progress and as of yet unreleased. Please do not use it until it's officially released. No support will be given if you do anyways.

----

# Plugin Manager plugin for OctoPrint

## Setup

Install the plugin like you would install any regular Python package from source:

    pip install https://github.com/OctoPrint/OctoPrint-PluginManager/archive/master.zip
    
Make sure you use the same Python environment that you installed OctoPrint under, otherwise the plugin
won't be able to satisfy its dependencies.

Restart OctoPrint. `octoprint.log` should show you that the plugin was successfully found and loaded:

    2015-01-26 14:13:28,286 - octoprint.plugin.core - INFO - Loading plugins from [...] and installed plugin packages...
    2015-01-26 14:13:28,973 - octoprint.plugin.core - INFO - Found 3 plugin(s): Plugin Manager (0.1), Discovery (0.1)

## Configuration

TODO
