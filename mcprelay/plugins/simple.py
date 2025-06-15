"""
Simple Plugin System for MCPRelay (Open Source)

License-agnostic plugin system that allows plugins to self-validate their requirements.
Enterprise plugins can implement their own license validation logic.
"""

import importlib
import inspect
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Type

import structlog

logger = structlog.get_logger()


class PluginHook:
    """Represents a hook point in the application."""
    
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.handlers: List[Callable] = []
    
    def register(self, handler: Callable) -> None:
        """Register a handler for this hook."""
        self.handlers.append(handler)
        logger.info("Plugin handler registered", hook=self.name, handler=handler.__name__)
    
    async def execute(self, *args, **kwargs) -> Any:
        """Execute all handlers for this hook."""
        results = []
        for handler in self.handlers:
            try:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(*args, **kwargs)
                else:
                    result = handler(*args, **kwargs)
                results.append(result)
            except Exception as e:
                logger.error("Plugin hook handler failed", 
                           hook=self.name, 
                           handler=handler.__name__, 
                           error=str(e))
        return results


class Plugin(ABC):
    """Base class for all MCPRelay plugins."""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.enabled = False
        self.config = {}
    
    @abstractmethod
    async def can_load(self) -> bool:
        """Check if this plugin can be loaded (e.g., license validation, dependencies)."""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """Initialize the plugin with configuration."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Cleanup plugin resources."""
        pass
    
    def register_hooks(self, plugin_manager: 'SimplePluginManager') -> None:
        """Register plugin hooks with the plugin manager."""
        pass


class SimplePluginManager:
    """Simple plugin manager without license dependencies."""
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.hooks: Dict[str, PluginHook] = {}
        self._register_core_hooks()
    
    def _register_core_hooks(self) -> None:
        """Register core application hooks."""
        core_hooks = [
            ("pre_auth", "Called before authentication processing"),
            ("post_auth", "Called after successful authentication"),
            ("pre_request", "Called before proxying request to backend"),
            ("post_response", "Called after receiving backend response"),
            ("metrics_collection", "Called during metrics collection"),
            ("config_validation", "Called during configuration validation"),
            ("server_startup", "Called during server startup"),
            ("server_shutdown", "Called during server shutdown"),
        ]
        
        for hook_name, description in core_hooks:
            self.hooks[hook_name] = PluginHook(hook_name, description)
    
    def register_hook(self, hook_name: str, handler: Callable) -> None:
        """Register a handler for a specific hook."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = PluginHook(hook_name)
        
        self.hooks[hook_name].register(handler)
    
    async def execute_hook(self, hook_name: str, *args, **kwargs) -> Any:
        """Execute all handlers for a hook."""
        if hook_name not in self.hooks:
            return []
        
        return await self.hooks[hook_name].execute(*args, **kwargs)
    
    async def load_plugin(self, plugin_class: Type[Plugin], config: Dict[str, Any] = None) -> bool:
        """Load and initialize a plugin."""
        try:
            plugin = plugin_class()
            
            # Let plugin validate its own requirements (including license)
            if not await plugin.can_load():
                logger.info("Plugin cannot be loaded", plugin=plugin.name)
                return False
            
            # Initialize plugin
            plugin_config = config or {}
            await plugin.initialize(plugin_config)
            
            # Register plugin hooks
            plugin.register_hooks(self)
            
            # Store plugin
            self.plugins[plugin.name] = plugin
            plugin.enabled = True
            
            logger.info("Plugin loaded successfully", plugin=plugin.name)
            return True
            
        except Exception as e:
            logger.error("Failed to load plugin", 
                        plugin=plugin_class.__name__, 
                        error=str(e))
            return False
    
    async def discover_and_load_plugins(self, plugin_packages: List[str]) -> None:
        """Discover and load plugins from specified packages."""
        for package_name in plugin_packages:
            try:
                package = importlib.import_module(package_name)
                
                # Look for plugin classes in the package
                for name in dir(package):
                    obj = getattr(package, name)
                    if (inspect.isclass(obj) and 
                        issubclass(obj, Plugin) and 
                        obj != Plugin):
                        await self.load_plugin(obj)
                        
            except ImportError as e:
                logger.debug("Plugin package not found", 
                           package=package_name, 
                           error=str(e))
            except Exception as e:
                logger.error("Error loading plugin package", 
                           package=package_name, 
                           error=str(e))
    
    async def shutdown_all_plugins(self) -> None:
        """Shutdown all loaded plugins."""
        for plugin in self.plugins.values():
            try:
                await plugin.cleanup()
                logger.info("Plugin shutdown complete", plugin=plugin.name)
            except Exception as e:
                logger.error("Plugin shutdown failed", 
                           plugin=plugin.name, 
                           error=str(e))
    
    def get_enabled_plugins(self) -> List[Plugin]:
        """Get list of all enabled plugins."""
        return [p for p in self.plugins.values() if p.enabled]
    
    def is_plugin_loaded(self, plugin_name: str) -> bool:
        """Check if a plugin is loaded and enabled."""
        return plugin_name in self.plugins and self.plugins[plugin_name].enabled


# Global plugin manager instance
plugin_manager: Optional[SimplePluginManager] = None


def init_plugin_manager() -> SimplePluginManager:
    """Initialize the global plugin manager."""
    global plugin_manager
    plugin_manager = SimplePluginManager()
    return plugin_manager


def get_plugin_manager() -> Optional[SimplePluginManager]:
    """Get the global plugin manager instance."""
    return plugin_manager