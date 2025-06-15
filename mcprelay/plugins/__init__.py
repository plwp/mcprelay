"""
MCPRelay Plugin System (Open Source)

Simple plugin system that delegates licensing and feature validation to plugins themselves.
Enterprise plugins can implement their own license validation logic.
"""

# Import the simple plugin system
from .simple import (
    Plugin,
    PluginHook,
    SimplePluginManager,
    get_plugin_manager,
    init_plugin_manager,
)
