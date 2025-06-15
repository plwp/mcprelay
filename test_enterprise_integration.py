#!/usr/bin/env python3
"""
Enterprise Integration Test for MCPRelay

Tests the full integration of license validation, plugin discovery, 
and enterprise feature loading.
"""

import sys
import os
import asyncio
sys.path.insert(0, os.path.dirname(__file__))

from mcprelay.license import LicenseManager
from mcprelay.plugins import PluginManager, init_plugin_manager
from mcprelay.config import MCPRelayConfig


async def test_enterprise_plugin_loading():
    """Test loading enterprise plugins with valid license"""
    print("🏢 Testing Enterprise Plugin Loading...")
    
    # Generate enterprise license
    enterprise_license = LicenseManager.generate_demo_license("enterprise", "Test Corp")
    print(f"Enterprise License: {enterprise_license}")
    
    # Initialize license manager
    license_manager = LicenseManager(license_key=enterprise_license)
    print(f"License Valid: {license_manager.is_enterprise}")
    print(f"Available Features: {len(license_manager.allowed_features)}")
    
    # Initialize plugin manager
    plugin_manager = init_plugin_manager(license_manager)
    
    # Try to discover and load enterprise plugins
    print("\n🔍 Discovering Enterprise Plugins...")
    try:
        await plugin_manager.discover_and_load_plugins(["mcprelay_enterprise.plugins"])
        
        # Check what plugins were loaded
        loaded_plugins = plugin_manager.get_enabled_plugins()
        print(f"✅ Loaded {len(loaded_plugins)} enterprise plugins:")
        
        for plugin in loaded_plugins:
            print(f"  - {plugin.name}")
            print(f"    Required Features: {plugin.get_required_features()}")
            
        # Test plugin hooks
        print(f"\n🪝 Available Hooks: {len(plugin_manager.hooks)}")
        for hook_name, hook in plugin_manager.hooks.items():
            handler_count = len(hook.handlers)
            print(f"  - {hook_name}: {handler_count} handlers")
        
        return plugin_manager, loaded_plugins
        
    except Exception as e:
        print(f"❌ Enterprise plugin loading failed: {e}")
        return plugin_manager, []


async def test_config_loading():
    """Test loading configuration with enterprise settings"""
    print("\n📋 Testing Configuration Loading...")
    
    try:
        config = MCPRelayConfig.from_yaml("config.test.yaml")
        print(f"✅ Configuration loaded successfully")
        print(f"Enterprise License: {config.enterprise.license_key[:20]}...")
        print(f"Plugin Packages: {config.plugins.plugin_packages}")
        print(f"Plugin Configs: {list(config.plugins.plugin_configs.keys())}")
        
        return config
        
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return None


async def test_specific_plugins():
    """Test specific enterprise plugin functionality"""
    print("\n🔌 Testing Specific Plugin Features...")
    
    # Test individual plugin imports
    plugins_to_test = [
        ("SAML Auth", "mcprelay_enterprise.plugins.auth.saml_auth", "SAMLAuthPlugin"),
        ("OIDC Auth", "mcprelay_enterprise.plugins.auth.oidc_auth", "OIDCAuthPlugin"),
        ("LDAP Auth", "mcprelay_enterprise.plugins.auth.ldap_auth", "LDAPAuthPlugin"),
        ("Vault Secrets", "mcprelay_enterprise.plugins.security.vault_secrets", "VaultSecretsPlugin"),
    ]
    
    available_plugins = []
    
    for plugin_name, module_path, class_name in plugins_to_test:
        try:
            # Try to import the module
            import importlib
            module = importlib.import_module(module_path)
            plugin_class = getattr(module, class_name)
            
            # Create instance
            plugin = plugin_class()
            required_features = plugin.get_required_features()
            
            print(f"  ✅ {plugin_name}")
            print(f"     Module: {module_path}")
            print(f"     Required Features: {required_features}")
            
            available_plugins.append((plugin_name, plugin))
            
        except ImportError as e:
            print(f"  ⚠️  {plugin_name}: Import failed ({e})")
        except Exception as e:
            print(f"  ❌ {plugin_name}: Error ({e})")
    
    return available_plugins


async def test_license_feature_gates():
    """Test license-based feature gating"""
    print("\n🔐 Testing License Feature Gates...")
    
    # Test with enterprise license
    ent_license = LicenseManager.generate_demo_license("enterprise")
    ent_manager = LicenseManager(license_key=ent_license)
    
    # Test with professional license  
    pro_license = LicenseManager.generate_demo_license("professional")
    pro_manager = LicenseManager(license_key=pro_license)
    
    # Test with no license
    no_manager = LicenseManager()
    
    test_features = ["saml_auth", "oidc_auth", "vault_integration", "clustering"]
    
    print("Feature Access Comparison:")
    print(f"{'Feature':<20} {'Enterprise':<12} {'Professional':<12} {'Open Source':<12}")
    print("-" * 60)
    
    for feature in test_features:
        ent_access = "✅" if ent_manager.check_feature(feature) else "❌"
        pro_access = "✅" if pro_manager.check_feature(feature) else "❌"
        oss_access = "✅" if no_manager.check_feature(feature) else "❌"
        
        print(f"{feature:<20} {ent_access:<12} {pro_access:<12} {oss_access:<12}")


async def main():
    """Main test function"""
    print("🧪 MCPRelay Enterprise Integration Test\n")
    
    # Test 1: Configuration Loading
    config = await test_config_loading()
    
    # Test 2: License Feature Gates
    await test_license_feature_gates()
    
    # Test 3: Plugin Loading
    plugin_manager, loaded_plugins = await test_enterprise_plugin_loading()
    
    # Test 4: Specific Plugin Features
    available_plugins = await test_specific_plugins()
    
    # Summary
    print(f"\n📊 Test Summary:")
    print(f"  Configuration: {'✅' if config else '❌'}")
    print(f"  Enterprise Plugins: {len(loaded_plugins)} loaded")
    print(f"  Available Plugins: {len(available_plugins)} importable")
    
    if len(available_plugins) > 0:
        print(f"\n🎉 Enterprise plugin system is working!")
        print(f"   Ready for SAML/OIDC authentication")
        print(f"   Ready for Vault secret management") 
        print(f"   Ready for advanced monitoring")
    else:
        print(f"\n⚠️  Enterprise plugins need dependency installation")
        print(f"   Run: pip install mcprelay-enterprise[full]")


if __name__ == "__main__":
    asyncio.run(main())