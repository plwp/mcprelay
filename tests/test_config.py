"""Test configuration management."""

import pytest
from mcprelay.config import MCPRelayConfig, MCPServerConfig


def test_default_config():
    """Test default configuration is valid."""
    config = MCPRelayConfig()
    assert config.host == "0.0.0.0"
    assert config.port == 8080
    assert config.auth.enabled is True
    assert config.rate_limit.enabled is True


def test_server_config():
    """Test MCP server configuration."""
    server = MCPServerConfig(
        name="test-server",
        url="http://localhost:3000"
    )
    assert server.name == "test-server"
    assert server.url == "http://localhost:3000"
    assert server.timeout == 30
    assert server.weight == 1


def test_config_from_dict():
    """Test loading configuration from dictionary."""
    config_dict = {
        "host": "127.0.0.1",
        "port": 9000,
        "servers": [
            {
                "name": "test",
                "url": "http://test.com"
            }
        ]
    }
    config = MCPRelayConfig(**config_dict)
    assert config.host == "127.0.0.1"
    assert config.port == 9000
    assert len(config.servers) == 1
    assert config.servers[0].name == "test"