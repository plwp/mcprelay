#!/usr/bin/env python3
"""
Test script for MCPRelay license validation and plugin system
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from mcprelay.license import LicenseManager
from mcprelay.plugins import PluginManager, init_plugin_manager


def test_license_generation():
    """Test demo license generation"""
    print("🔑 Testing License Generation...")
    
    # Generate demo licenses
    enterprise_license = LicenseManager.generate_demo_license("enterprise", "Test Customer")
    professional_license = LicenseManager.generate_demo_license("professional", "Test Customer")
    
    print(f"Enterprise License: {enterprise_license}")
    print(f"Professional License: {professional_license}")
    
    return enterprise_license, professional_license


def test_license_validation(license_key):
    """Test license validation"""
    print(f"\n🔍 Testing License Validation...")
    
    # Initialize license manager with demo license
    license_manager = LicenseManager(license_key=license_key)
    
    print(f"Is Enterprise: {license_manager.is_enterprise}")
    print(f"License Info: {license_manager.get_license_info()}")
    
    # Test specific features
    features_to_test = [
        "saml_auth",
        "oidc_auth", 
        "ldap_auth",
        "vault_integration",
        "advanced_monitoring",
        "clustering"
    ]
    
    print("\n📋 Feature Access:")
    for feature in features_to_test:
        has_access = license_manager.check_feature(feature)
        print(f"  {feature}: {'✅' if has_access else '❌'}")
    
    return license_manager


def test_plugin_manager(license_manager):
    """Test plugin manager initialization"""
    print(f"\n🔌 Testing Plugin Manager...")
    
    # Initialize plugin manager
    plugin_manager = init_plugin_manager(license_manager)
    
    print(f"Plugin Manager Initialized: {plugin_manager is not None}")
    print(f"Available Hooks: {list(plugin_manager.hooks.keys())}")
    
    # Test hook registration
    print("\n🪝 Testing Hook Registration...")
    try:
        def dummy_handler(config):
            return f"Handler executed with config: {config}"
        
        plugin_manager.register_hook("server_startup", dummy_handler)
        print("Hook registration successful")
    except Exception as e:
        print(f"Hook registration error: {e}")
    
    return plugin_manager


def test_plugin_discovery(plugin_manager):
    """Test plugin discovery"""
    print(f"\n🔍 Testing Plugin Discovery...")
    
    # Try to discover enterprise plugins (will fail gracefully if not installed)
    try:
        plugin_manager.discover_and_load_plugins(["mcprelay_enterprise.plugins"])
        print("Enterprise plugins discovery attempted")
    except Exception as e:
        print(f"Enterprise plugins not available (expected): {e}")
    
    # Check loaded plugins
    enabled_plugins = plugin_manager.get_enabled_plugins()
    print(f"Loaded Plugins: {[p.name for p in enabled_plugins]}")


def main():
    """Main test function"""
    print("🧪 MCPRelay License & Plugin System Test\n")
    
    # Test 1: License Generation
    enterprise_license, professional_license = test_license_generation()
    
    # Test 2: License Validation (Enterprise)
    license_manager = test_license_validation(enterprise_license)
    
    # Test 3: Plugin Manager
    plugin_manager = test_plugin_manager(license_manager)
    
    # Test 4: Plugin Discovery
    test_plugin_discovery(plugin_manager)
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    main()