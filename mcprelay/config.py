"""Configuration management for MCPRelay."""

from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class MCPServerConfig(BaseModel):
    """Configuration for a single MCP server."""

    name: str = Field(..., description="Unique name for this MCP server")
    url: str = Field(..., description="URL of the MCP server")
    timeout: int = Field(30, description="Request timeout in seconds")
    max_retries: int = Field(3, description="Maximum number of retries")
    health_check_path: str = Field("/health", description="Health check endpoint")
    weight: int = Field(1, description="Load balancing weight")
    tags: List[str] = Field(default_factory=list, description="Server tags for routing")


class AuthConfig(BaseModel):
    """Authentication configuration."""

    enabled: bool = Field(True, description="Enable authentication")
    method: str = Field("api_key", description="Auth method: api_key, jwt, oauth")
    jwt_secret: Optional[str] = Field(None, description="JWT secret key")
    jwt_algorithm: str = Field("HS256", description="JWT algorithm")
    api_keys: Dict[str, str] = Field(
        default_factory=dict, description="API key to user mapping"
    )


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    enabled: bool = Field(True, description="Enable rate limiting")
    default_requests_per_minute: int = Field(
        60, description="Default requests per minute"
    )
    burst_size: int = Field(10, description="Burst size for rate limiting")
    per_user_limits: Dict[str, int] = Field(
        default_factory=dict, description="Per-user rate limits"
    )


class MetricsConfig(BaseModel):
    """Metrics and monitoring configuration."""

    enabled: bool = Field(True, description="Enable metrics collection")
    port: int = Field(9090, description="Metrics server port")
    path: str = Field("/metrics", description="Metrics endpoint path")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field("INFO", description="Log level")
    format: str = Field("json", description="Log format: json, text")
    access_log: bool = Field(True, description="Enable access logging")
    audit_log: bool = Field(True, description="Enable audit logging")


class RedisConfig(BaseModel):
    """Redis configuration for caching and rate limiting."""

    enabled: bool = Field(False, description="Enable Redis")
    url: str = Field("redis://localhost:6379", description="Redis connection URL")
    db: int = Field(0, description="Redis database number")
    prefix: str = Field("mcprelay:", description="Key prefix")


class PluginConfig(BaseModel):
    """Plugin system configuration."""

    enabled: bool = Field(True, description="Enable plugin system")
    enterprise_plugins: bool = Field(
        True, description="Load enterprise plugins if available"
    )
    plugin_packages: List[str] = Field(
        default_factory=lambda: ["mcprelay_enterprise.plugins"],
        description="Python packages to search for plugins",
    )
    plugin_configs: Dict[str, Dict] = Field(
        default_factory=dict, description="Per-plugin configuration"
    )


class EnterpriseConfig(BaseModel):
    """Enterprise license and feature configuration."""

    license_key: Optional[str] = Field(None, description="Enterprise license key")
    license_file: Optional[str] = Field(None, description="Path to license file")
    enabled_features: List[str] = Field(
        default_factory=list, description="Explicitly enabled enterprise features"
    )
    disabled_features: List[str] = Field(
        default_factory=list, description="Explicitly disabled enterprise features"
    )


class MCPRelayConfig(BaseSettings):
    """Main configuration for MCPRelay."""

    # Server settings
    host: str = Field("0.0.0.0", description="Server host")
    port: int = Field(8080, description="Server port")
    workers: int = Field(1, description="Number of worker processes")
    debug_mode: bool = Field(False, description="Enable debug mode")

    # Security settings
    mcp_safeguards_enabled: bool = Field(
        True, description="Enable MCP request/response safeguards"
    )
    allowed_origins: List[str] = Field(
        default_factory=lambda: ["*"], description="CORS allowed origins"
    )

    # MCP servers
    servers: List[MCPServerConfig] = Field(
        default_factory=list, description="MCP servers to proxy"
    )

    # Feature configurations
    auth: AuthConfig = Field(default_factory=lambda: AuthConfig())
    rate_limit: RateLimitConfig = Field(default_factory=lambda: RateLimitConfig())
    metrics: MetricsConfig = Field(default_factory=lambda: MetricsConfig())
    logging: LoggingConfig = Field(default_factory=lambda: LoggingConfig())
    redis: RedisConfig = Field(default_factory=lambda: RedisConfig())
    plugins: PluginConfig = Field(default_factory=lambda: PluginConfig())
    enterprise: EnterpriseConfig = Field(default_factory=lambda: EnterpriseConfig())

    # Load balancing
    load_balance_strategy: str = Field(
        "round_robin", description="Load balancing strategy"
    )
    health_check_interval: int = Field(
        30, description="Health check interval in seconds"
    )

    model_config = {
        "env_prefix": "MCPRELAY_",
        "env_file": ".env",
        "case_sensitive": False,
    }

    @classmethod
    def from_yaml(cls, file_path: str) -> "MCPRelayConfig":
        """Load configuration from YAML file."""
        with open(file_path, "r") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self, file_path: str) -> None:
        """Save configuration to YAML file."""
        with open(file_path, "w") as f:
            yaml.safe_dump(self.model_dump(), f, default_flow_style=False)
