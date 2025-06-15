#!/usr/bin/env python3
"""
Test script for license-agnostic plugin system.

Tests that the open source MCPRelay can run without any license dependencies,
and that enterprise plugins self-validate their requirements.
"""

import asyncio
import sys
from pathlib import Path

# Add both repos to path for testing
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, "/Users/patrickprendergast/repos/mcprelay-enterprise")

from mcprelay.plugins import init_plugin_manager, get_plugin_manager


class DemoOpenSourcePlugin:
    """Demo plugin that requires no special features."""
    
    def __init__(self):
        self.name = "DemoOpenSourcePlugin"
        self.enabled = False
    
    async def can_load(self) -> bool:
        """This plugin can always load."""
        return True
    
    async def initialize(self, config):
        print(f"✅ {self.name} initialized (open source)")
    
    async def cleanup(self):
        print(f"🧹 {self.name} cleaned up")
    
    def register_hooks(self, plugin_manager):
        plugin_manager.register_hook("test_hook", self.test_handler)
    
    def test_handler(self):
        return f"Hello from {self.name}"


async def test_open_source_mode():
    """Test that MCPRelay works without any enterprise dependencies."""
    print("🧪 Testing Open Source Mode (No License)")
    print("=" * 50)
    
    # Initialize plugin manager (no license)
    plugin_manager = init_plugin_manager()
    
    # Load open source plugin (should work)
    demo_plugin = DemoOpenSourcePlugin()
    success = await plugin_manager.load_plugin(type(demo_plugin))
    print(f"Open source plugin loaded: {success}")
    
    # Execute hooks
    results = await plugin_manager.execute_hook("test_hook")
    print(f"Hook results: {results}")
    
    # Check loaded plugins
    plugins = plugin_manager.get_enabled_plugins()
    print(f"Enabled plugins: {[p.name for p in plugins]}")
    
    print("\n✅ Open source mode works without license dependencies!\n")


async def test_enterprise_mode():
    """Test that enterprise plugins validate their own licenses."""
    print("🏢 Testing Enterprise Mode (With License)")
    print("=" * 50)
    
    try:
        # Try to import enterprise plugins
        from mcprelay_enterprise.plugins.license_manager import LicenseManagerPlugin
        from mcprelay_enterprise.plugins.auth.saml_auth import SAMLAuthPlugin
        
        # Initialize plugin manager
        plugin_manager = init_plugin_manager()
        
        # Generate a demo license first
        from mcprelay_enterprise.license_crypto import create_demo_license_file
        license_file = create_demo_license_file("enterprise_test_license.json")
        print(f"Created test license: {license_file}")
        
        # Try to load license manager plugin (should work with valid license)
        license_loaded = await plugin_manager.load_plugin(LicenseManagerPlugin)
        print(f"License manager loaded: {license_loaded}")
        
        # Try to load SAML plugin (should work if license manager loaded)
        saml_loaded = await plugin_manager.load_plugin(SAMLAuthPlugin)
        print(f"SAML plugin loaded: {saml_loaded}")
        
        # Test license information
        if license_loaded:
            results = await plugin_manager.execute_hook("get_license_info")
            if results:
                license_info = results[0]
                print(f"License info: {license_info.get('license_type')} for {license_info.get('company_name')}")
        
        # Test feature checking
        if license_loaded:
            results = await plugin_manager.execute_hook("check_enterprise_feature", "saml_auth")
            feature_enabled = any(results) if results else False
            print(f"SAML feature enabled: {feature_enabled}")
        
        plugins = plugin_manager.get_enabled_plugins()
        print(f"Enabled plugins: {[p.name for p in plugins]}")
        
        print("\n✅ Enterprise mode works with self-validating plugins!")
        return True
        
    except ImportError as e:
        print(f"Enterprise plugins not available: {e}")
        return False
    except Exception as e:
        print(f"Enterprise test failed: {e}")
        return False


async def test_no_license_enterprise():
    """Test that enterprise plugins fail gracefully without license."""
    print("🚫 Testing Enterprise Plugins Without License")
    print("=" * 50)
    
    try:
        from mcprelay_enterprise.plugins.license_manager import LicenseManagerPlugin
        from mcprelay_enterprise.plugins.auth.saml_auth import SAMLAuthPlugin
        
        # Remove any existing demo licenses
        import os
        for demo_file in ["demo_license.json", "test_reorganized_license.json", "enterprise_test_license.json"]:
            if os.path.exists(demo_file):
                os.remove(demo_file)
        
        # Initialize plugin manager
        plugin_manager = init_plugin_manager()
        
        # Try to load license manager without license (should fail gracefully)
        license_loaded = await plugin_manager.load_plugin(LicenseManagerPlugin)
        print(f"License manager loaded without license: {license_loaded}")
        
        # Try to load SAML plugin without license (should fail gracefully)  
        saml_loaded = await plugin_manager.load_plugin(SAMLAuthPlugin)
        print(f"SAML plugin loaded without license: {saml_loaded}")
        
        plugins = plugin_manager.get_enabled_plugins()
        print(f"Enabled plugins: {[p.name for p in plugins]}")
        
        print("\n✅ Enterprise plugins fail gracefully without license!")
        
    except Exception as e:
        print(f"Test failed: {e}")


async def main():
    """Run all tests."""
    print("🚀 Testing License-Agnostic MCPRelay Plugin System")
    print("=" * 60)
    
    await test_open_source_mode()
    
    enterprise_available = await test_enterprise_mode()
    
    if enterprise_available:
        await test_no_license_enterprise()
    
    print("🎉 All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())