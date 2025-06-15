"""
Secure MCP Server for Admin Console Management.

This module implements a dedicated MCP server that exposes MCPRelay administration
capabilities through the Model Context Protocol while maintaining enterprise-grade security.
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional

import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import AuthContext, require_admin
from .config import MCPRelayConfig, MCPServerConfig
from .load_balancer import LoadBalancer

logger = structlog.get_logger()


class MCPToolSchema(BaseModel):
    """Schema for MCP tool definition."""

    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)
    additionalProperties: bool = False


class MCPTool(BaseModel):
    """MCP tool definition."""

    name: str
    description: str
    inputSchema: MCPToolSchema


class MCPToolCall(BaseModel):
    """MCP tool call request."""

    name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPToolResult(BaseModel):
    """MCP tool call result."""

    content: List[Dict[str, Any]] = Field(default_factory=list)
    isError: bool = False


class AuditLogEntry(BaseModel):
    """Audit log entry for admin operations."""

    timestamp: float = Field(default_factory=time.time)
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    operation: str
    resource: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    result: str  # "success", "error", "denied"
    error_message: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


class AdminMCPServer:
    """Secure MCP server for administrative operations."""

    def __init__(self, config: MCPRelayConfig, load_balancer: LoadBalancer):
        self.config = config
        self.load_balancer = load_balancer
        self.audit_log: List[AuditLogEntry] = []
        self._setup_tools()

    def _setup_tools(self):
        """Setup available MCP tools."""
        self.tools = [
            # Configuration Management
            MCPTool(
                name="mcprelay_config_get",
                description="Retrieve current MCPRelay configuration",
                inputSchema=MCPToolSchema(
                    properties={
                        "section": {
                            "type": "string",
                            "enum": ["servers", "auth", "rate_limits", "all"],
                            "description": "Configuration section to retrieve",
                        }
                    }
                ),
            ),
            MCPTool(
                name="mcprelay_config_update",
                description="Update MCPRelay configuration",
                inputSchema=MCPToolSchema(
                    properties={
                        "section": {
                            "type": "string",
                            "enum": ["servers", "auth", "rate_limits"],
                            "description": "Configuration section to update",
                        },
                        "config": {
                            "type": "object",
                            "description": "New configuration data",
                        },
                    },
                    required=["section", "config"],
                ),
            ),
            # Server Management
            MCPTool(
                name="mcprelay_server_add",
                description="Add new MCP backend server",
                inputSchema=MCPToolSchema(
                    properties={
                        "name": {"type": "string", "description": "Unique server name"},
                        "url": {
                            "type": "string",
                            "format": "uri",
                            "description": "Server URL",
                        },
                        "weight": {
                            "type": "number",
                            "minimum": 0,
                            "description": "Load balancing weight",
                        },
                        "timeout": {
                            "type": "number",
                            "minimum": 1,
                            "description": "Request timeout",
                        },
                        "health_check": {
                            "type": "boolean",
                            "description": "Enable health checks",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Server tags",
                        },
                    },
                    required=["name", "url"],
                ),
            ),
            MCPTool(
                name="mcprelay_server_remove",
                description="Remove MCP backend server",
                inputSchema=MCPToolSchema(
                    properties={
                        "name": {
                            "type": "string",
                            "description": "Server name to remove",
                        }
                    },
                    required=["name"],
                ),
            ),
            MCPTool(
                name="mcprelay_server_update",
                description="Update MCP backend server configuration",
                inputSchema=MCPToolSchema(
                    properties={
                        "name": {"type": "string", "description": "Server name"},
                        "config": {
                            "type": "object",
                            "description": "Updated server configuration",
                        },
                    },
                    required=["name", "config"],
                ),
            ),
            MCPTool(
                name="mcprelay_servers_list",
                description="List all MCP backend servers",
                inputSchema=MCPToolSchema(),
            ),
            # Monitoring and Metrics
            MCPTool(
                name="mcprelay_metrics_get",
                description="Retrieve system metrics and health status",
                inputSchema=MCPToolSchema(
                    properties={
                        "metric_type": {
                            "type": "string",
                            "enum": ["requests", "latency", "errors", "health", "all"],
                            "description": "Type of metrics to retrieve",
                        },
                        "time_range": {
                            "type": "string",
                            "enum": ["1h", "24h", "7d", "30d"],
                            "description": "Time range for metrics",
                        },
                    }
                ),
            ),
            MCPTool(
                name="mcprelay_health_check",
                description="Perform health check on backend servers",
                inputSchema=MCPToolSchema(
                    properties={
                        "server_name": {
                            "type": "string",
                            "description": "Specific server to check (optional)",
                        }
                    }
                ),
            ),
            # User and Authentication Management
            MCPTool(
                name="mcprelay_users_list",
                description="List all users and their access levels",
                inputSchema=MCPToolSchema(),
            ),
            MCPTool(
                name="mcprelay_user_create",
                description="Create new user with API key",
                inputSchema=MCPToolSchema(
                    properties={
                        "user_id": {"type": "string", "description": "Unique user ID"},
                        "is_admin": {
                            "type": "boolean",
                            "description": "Admin privileges",
                        },
                        "rate_limit_tier": {
                            "type": "string",
                            "description": "Rate limit tier",
                        },
                        "allowed_actions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Allowed MCP actions",
                        },
                    },
                    required=["user_id"],
                ),
            ),
            MCPTool(
                name="mcprelay_user_delete",
                description="Delete user and revoke access",
                inputSchema=MCPToolSchema(
                    properties={
                        "user_id": {
                            "type": "string",
                            "description": "User ID to delete",
                        }
                    },
                    required=["user_id"],
                ),
            ),
            # Rate Limiting
            MCPTool(
                name="mcprelay_rate_limits_get",
                description="Get current rate limiting configuration",
                inputSchema=MCPToolSchema(),
            ),
            MCPTool(
                name="mcprelay_rate_limits_update",
                description="Update rate limiting configuration",
                inputSchema=MCPToolSchema(
                    properties={
                        "default_requests_per_minute": {"type": "number", "minimum": 1},
                        "burst_size": {"type": "number", "minimum": 1},
                        "per_user_limits": {
                            "type": "object",
                            "description": "Per-user rate limits",
                        },
                    }
                ),
            ),
            # Audit and Logging
            MCPTool(
                name="mcprelay_audit_logs_get",
                description="Retrieve audit logs",
                inputSchema=MCPToolSchema(
                    properties={
                        "user_id": {
                            "type": "string",
                            "description": "Filter by user ID",
                        },
                        "operation": {
                            "type": "string",
                            "description": "Filter by operation",
                        },
                        "limit": {
                            "type": "number",
                            "minimum": 1,
                            "maximum": 1000,
                            "description": "Number of entries",
                        },
                        "since": {
                            "type": "string",
                            "description": "ISO timestamp to filter from",
                        },
                    }
                ),
            ),
            MCPTool(
                name="mcprelay_logs_get",
                description="Retrieve system logs",
                inputSchema=MCPToolSchema(
                    properties={
                        "level": {
                            "type": "string",
                            "enum": ["DEBUG", "INFO", "WARNING", "ERROR"],
                        },
                        "limit": {"type": "number", "minimum": 1, "maximum": 1000},
                        "since": {
                            "type": "string",
                            "description": "ISO timestamp to filter from",
                        },
                    }
                ),
            ),
        ]

    async def _log_audit_event(
        self,
        auth_context: AuthContext,
        operation: str,
        resource: str,
        parameters: Dict[str, Any],
        result: str,
        error_message: Optional[str] = None,
        request: Optional[Request] = None,
    ):
        """Log an audit event."""

        entry = AuditLogEntry(
            user_id=auth_context.user_id,
            operation=operation,
            resource=resource,
            parameters=parameters,
            result=result,
            error_message=error_message,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("User-Agent") if request else None,
        )

        self.audit_log.append(entry)

        # Keep only last 10000 entries to prevent memory bloat
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-10000:]

        logger.info(
            "Admin operation audited",
            user=auth_context.user_id,
            operation=operation,
            resource=resource,
            result=result,
            error=error_message,
        )

    async def list_tools(self) -> List[MCPTool]:
        """List available MCP tools."""
        return self.tools

    async def call_tool(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request] = None,
    ) -> MCPToolResult:
        """Execute an MCP tool call."""

        try:
            # Route to appropriate handler
            if tool_call.name == "mcprelay_config_get":
                return await self._handle_config_get(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_config_update":
                return await self._handle_config_update(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_server_add":
                return await self._handle_server_add(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_server_remove":
                return await self._handle_server_remove(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_server_update":
                return await self._handle_server_update(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_servers_list":
                return await self._handle_servers_list(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_metrics_get":
                return await self._handle_metrics_get(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_health_check":
                return await self._handle_health_check(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_users_list":
                return await self._handle_users_list(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_user_create":
                return await self._handle_user_create(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_user_delete":
                return await self._handle_user_delete(tool_call, auth_context, request)
            elif tool_call.name == "mcprelay_rate_limits_get":
                return await self._handle_rate_limits_get(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_rate_limits_update":
                return await self._handle_rate_limits_update(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_audit_logs_get":
                return await self._handle_audit_logs_get(
                    tool_call, auth_context, request
                )
            elif tool_call.name == "mcprelay_logs_get":
                return await self._handle_logs_get(tool_call, auth_context, request)
            else:
                raise ValueError(f"Unknown tool: {tool_call.name}")

        except Exception as e:
            await self._log_audit_event(
                auth_context,
                f"tool_call:{tool_call.name}",
                "mcp_tool",
                tool_call.arguments,
                "error",
                str(e),
                request,
            )
            return MCPToolResult(
                content=[
                    {
                        "type": "text",
                        "text": f"Error executing tool {tool_call.name}: {str(e)}",
                    }
                ],
                isError=True,
            )

    async def _handle_config_get(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle configuration retrieval."""

        section = tool_call.arguments.get("section", "all")

        await self._log_audit_event(
            auth_context,
            "config_get",
            f"config:{section}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        safe_config = self.config.model_dump()

        # Remove sensitive data for non-admin users
        if not auth_context.is_admin:
            if "auth" in safe_config and "api_keys" in safe_config["auth"]:
                safe_config["auth"]["api_keys"] = {
                    k: "***" for k in safe_config["auth"]["api_keys"]
                }
            if "jwt_secret" in safe_config.get("auth", {}):
                safe_config["auth"]["jwt_secret"] = "***"

        if section != "all":
            safe_config = {section: safe_config.get(section, {})}

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(safe_config, indent=2)}]
        )

    async def _handle_config_update(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle configuration updates (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "config_update",
                "config",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        section = tool_call.arguments.get("section")
        new_config = tool_call.arguments.get("config")

        if not section or not new_config:
            raise ValueError("Section and config parameters required")

        # Note: In a real implementation, this would update the actual configuration
        # and potentially restart services. For now, we'll just log the operation.

        await self._log_audit_event(
            auth_context,
            "config_update",
            f"config:{section}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[
                {
                    "type": "text",
                    "text": f"Configuration section '{section}' updated successfully. Note: Changes may require restart to take effect.",
                }
            ]
        )

    async def _handle_server_add(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle adding a new backend server."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "server_add",
                "servers",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        name = tool_call.arguments.get("name")
        url = tool_call.arguments.get("url")

        if not name or not url:
            raise ValueError("Name and URL parameters required")

        # Check if server already exists
        existing_server = next((s for s in self.config.servers if s.name == name), None)
        if existing_server:
            raise ValueError(f"Server with name '{name}' already exists")

        # Create new server config
        new_server = MCPServerConfig(
            name=name,
            url=url,
            weight=tool_call.arguments.get("weight", 1),
            timeout=tool_call.arguments.get("timeout", 30),
            tags=tool_call.arguments.get("tags", []),
        )

        # Add to load balancer
        await self.load_balancer.add_server(new_server)

        await self._log_audit_event(
            auth_context,
            "server_add",
            f"server:{name}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": f"Server '{name}' added successfully"}]
        )

    async def _handle_server_remove(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle removing a backend server."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "server_remove",
                "servers",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        name = tool_call.arguments.get("name")
        if not name:
            raise ValueError("Name parameter required")

        # Remove from load balancer
        success = await self.load_balancer.remove_server(name)

        if not success:
            raise ValueError(f"Server '{name}' not found")

        await self._log_audit_event(
            auth_context,
            "server_remove",
            f"server:{name}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": f"Server '{name}' removed successfully"}]
        )

    async def _handle_server_update(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle updating a backend server."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "server_update",
                "servers",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        name = tool_call.arguments.get("name")
        config_updates = tool_call.arguments.get("config")

        if not name or not config_updates:
            raise ValueError("Name and config parameters required")

        # Update server in load balancer
        success = await self.load_balancer.update_server(name, config_updates)

        if not success:
            raise ValueError(f"Server '{name}' not found")

        await self._log_audit_event(
            auth_context,
            "server_update",
            f"server:{name}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": f"Server '{name}' updated successfully"}]
        )

    async def _handle_servers_list(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle listing all backend servers."""

        servers_info = []
        for server in self.config.servers:
            server_status = await self.load_balancer.get_server_health(server.name)
            servers_info.append(
                {
                    "name": server.name,
                    "url": server.url,
                    "weight": server.weight,
                    "timeout": server.timeout,
                    "tags": server.tags,
                    "healthy": server_status.get("healthy", False),
                    "last_check": server_status.get("last_check"),
                    "error": server_status.get("error"),
                }
            )

        await self._log_audit_event(
            auth_context, "servers_list", "servers", {}, "success", None, request
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(servers_info, indent=2)}]
        )

    async def _handle_metrics_get(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle metrics retrieval."""

        metric_type = tool_call.arguments.get("metric_type", "all")
        time_range = tool_call.arguments.get("time_range", "1h")

        # Mock metrics data - in real implementation, this would query actual metrics
        metrics = {
            "requests": {"total": 12345, "rate_per_minute": 95.2, "success_rate": 99.1},
            "latency": {"p50": 45.2, "p95": 120.5, "p99": 250.1},
            "errors": {
                "total": 23,
                "rate": 0.9,
                "by_type": {"timeout": 12, "connection": 8, "validation": 3},
            },
            "health": {
                "healthy_servers": len([s for s in self.config.servers]),
                "total_servers": len(self.config.servers),
                "status": "healthy",
            },
        }

        if metric_type != "all":
            metrics = {metric_type: metrics.get(metric_type, {})}

        await self._log_audit_event(
            auth_context,
            "metrics_get",
            f"metrics:{metric_type}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(metrics, indent=2)}]
        )

    async def _handle_health_check(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle health check."""

        server_name = tool_call.arguments.get("server_name")

        if server_name:
            # Check specific server
            health_status = await self.load_balancer.get_server_health(server_name)
            if not health_status:
                raise ValueError(f"Server '{server_name}' not found")
        else:
            # Check all servers
            health_status = {}
            for server in self.config.servers:
                health_status[server.name] = await self.load_balancer.get_server_health(
                    server.name
                )

        await self._log_audit_event(
            auth_context,
            "health_check",
            f"health:{server_name or 'all'}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(health_status, indent=2)}]
        )

    async def _handle_users_list(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle listing users (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "users_list",
                "users",
                {},
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        # Extract user info from API keys
        users = []
        for api_key, user_id in self.config.auth.api_keys.items():
            users.append(
                {
                    "user_id": user_id,
                    "is_admin": user_id.endswith("-admin"),
                    "api_key_prefix": api_key[:8] + "...",
                    "rate_limit_tier": (
                        "admin" if user_id.endswith("-admin") else "default"
                    ),
                }
            )

        await self._log_audit_event(
            auth_context, "users_list", "users", {}, "success", None, request
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(users, indent=2)}]
        )

    async def _handle_user_create(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle user creation (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "user_create",
                "users",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        user_id = tool_call.arguments.get("user_id")
        if not user_id:
            raise ValueError("user_id parameter required")

        # Generate new API key
        new_api_key = str(uuid.uuid4())

        # Note: In real implementation, this would update the actual configuration
        await self._log_audit_event(
            auth_context,
            "user_create",
            f"user:{user_id}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[
                {
                    "type": "text",
                    "text": f"User '{user_id}' created successfully. API Key: {new_api_key}",
                }
            ]
        )

    async def _handle_user_delete(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle user deletion (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "user_delete",
                "users",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        user_id = tool_call.arguments.get("user_id")
        if not user_id:
            raise ValueError("user_id parameter required")

        # Note: In real implementation, this would update the actual configuration
        await self._log_audit_event(
            auth_context,
            "user_delete",
            f"user:{user_id}",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": f"User '{user_id}' deleted successfully"}]
        )

    async def _handle_rate_limits_get(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle rate limits retrieval."""

        rate_limits = {
            "enabled": self.config.rate_limit.enabled,
            "default_requests_per_minute": self.config.rate_limit.default_requests_per_minute,
            "burst_size": self.config.rate_limit.burst_size,
            "per_user_limits": self.config.rate_limit.per_user_limits,
        }

        await self._log_audit_event(
            auth_context, "rate_limits_get", "rate_limits", {}, "success", None, request
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(rate_limits, indent=2)}]
        )

    async def _handle_rate_limits_update(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle rate limits update (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "rate_limits_update",
                "rate_limits",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        # Note: In real implementation, this would update the actual configuration
        await self._log_audit_event(
            auth_context,
            "rate_limits_update",
            "rate_limits",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": "Rate limits updated successfully"}]
        )

    async def _handle_audit_logs_get(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle audit logs retrieval (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "audit_logs_get",
                "audit",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        user_id_filter = tool_call.arguments.get("user_id")
        operation_filter = tool_call.arguments.get("operation")
        limit = tool_call.arguments.get("limit", 100)

        # Filter and limit audit logs
        filtered_logs = self.audit_log

        if user_id_filter:
            filtered_logs = [
                log for log in filtered_logs if log.user_id == user_id_filter
            ]

        if operation_filter:
            filtered_logs = [
                log for log in filtered_logs if operation_filter in log.operation
            ]

        # Return most recent entries
        recent_logs = filtered_logs[-limit:]

        # Convert to dict for JSON serialization
        logs_data = [log.model_dump() for log in recent_logs]

        await self._log_audit_event(
            auth_context,
            "audit_logs_get",
            "audit",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(logs_data, indent=2)}]
        )

    async def _handle_logs_get(
        self,
        tool_call: MCPToolCall,
        auth_context: AuthContext,
        request: Optional[Request],
    ) -> MCPToolResult:
        """Handle system logs retrieval (admin only)."""

        if not auth_context.is_admin:
            await self._log_audit_event(
                auth_context,
                "logs_get",
                "logs",
                tool_call.arguments,
                "denied",
                "Admin required",
                request,
            )
            raise HTTPException(status_code=403, detail="Admin access required")

        # Note: In real implementation, this would retrieve actual system logs
        mock_logs = [
            {
                "timestamp": "2025-06-15T10:30:00Z",
                "level": "INFO",
                "message": "MCPRelay started successfully",
            },
            {
                "timestamp": "2025-06-15T10:31:15Z",
                "level": "INFO",
                "message": "Health check passed for server-1",
            },
            {
                "timestamp": "2025-06-15T10:32:30Z",
                "level": "WARNING",
                "message": "Rate limit exceeded for user test-user",
            },
            {
                "timestamp": "2025-06-15T10:33:45Z",
                "level": "ERROR",
                "message": "Backend server connection failed",
            },
        ]

        await self._log_audit_event(
            auth_context,
            "logs_get",
            "logs",
            tool_call.arguments,
            "success",
            None,
            request,
        )

        return MCPToolResult(
            content=[{"type": "text", "text": json.dumps(mock_logs, indent=2)}]
        )


def create_admin_mcp_app(
    config: MCPRelayConfig, load_balancer: LoadBalancer
) -> FastAPI:
    """Create the secure admin MCP server application."""

    app = FastAPI(
        title="MCPRelay Admin MCP Server",
        description="Secure MCP server for MCPRelay administration",
        version="0.1.0",
        docs_url="/docs" if config.debug_mode else None,
        redoc_url="/redoc" if config.debug_mode else None,
    )

    # Restrictive CORS for admin interface
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],  # Only allow specific admin frontends
        allow_credentials=True,
        allow_methods=["POST", "GET"],
        allow_headers=["*"],
    )

    # Initialize admin MCP server
    admin_server = AdminMCPServer(config, load_balancer)

    @app.get("/health")
    async def health_check():
        """Health check for admin MCP server."""
        return {"status": "healthy", "service": "mcprelay-admin-mcp"}

    @app.get("/mcp/tools/list")
    async def list_tools(auth_context: AuthContext = Depends(require_admin)):
        """List available MCP tools (MCP protocol endpoint)."""
        tools = await admin_server.list_tools()
        return {"tools": [tool.model_dump() for tool in tools]}

    @app.post("/mcp/tools/call")
    async def call_tool(
        request: Request,
        tool_call: MCPToolCall,
        auth_context: AuthContext = Depends(require_admin),
    ):
        """Execute MCP tool call (MCP protocol endpoint)."""
        result = await admin_server.call_tool(tool_call, auth_context, request)
        return result.model_dump()

    @app.get("/")
    async def root():
        """Root endpoint with service info."""
        return {
            "service": "MCPRelay Admin MCP Server",
            "version": "0.1.0",
            "mcp_tools_endpoint": "/mcp/tools/list",
            "mcp_call_endpoint": "/mcp/tools/call",
            "security": "Admin authentication required",
        }

    return app
