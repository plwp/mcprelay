"""
MCPRelay FastAPI server implementation.
"""

import httpx
import structlog
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from .auth import AuthContext, get_current_user, init_auth_manager
from .config import MCPRelayConfig
from .license import init_license_manager, get_license_manager
from .load_balancer import LoadBalancer
from .mcp import MCPRequestValidator, MCPResponseSanitizer
from .plugins import init_plugin_manager, get_plugin_manager
from .rate_limit import init_rate_limiter, rate_limit_check
from .web_ui import router as web_ui_router

logger = structlog.get_logger()

# Metrics
REQUEST_COUNT = Counter(
    "mcprelay_requests_total", "Total requests", ["method", "endpoint", "status"]
)
REQUEST_DURATION = Histogram("mcprelay_request_duration_seconds", "Request duration")
ACTIVE_CONNECTIONS = Gauge("mcprelay_active_connections", "Active connections")
BACKEND_HEALTH = Gauge("mcprelay_backend_health", "Backend health status", ["backend"])


class MCPRelay:
    """Main MCPRelay application."""

    def __init__(self, config: MCPRelayConfig):
        self.config = config
        self.load_balancer = LoadBalancer(config.servers)
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20),
        )
        self.mcp_validator = MCPRequestValidator()
        self.mcp_sanitizer = MCPResponseSanitizer()

    async def proxy_request(
        self, request: Request, auth_context: AuthContext, path: str = ""
    ) -> Response:
        """Proxy an MCP request to backend server."""

        with REQUEST_DURATION.time():
            ACTIVE_CONNECTIONS.inc()

            try:
                # Execute pre-request hooks
                plugin_manager = get_plugin_manager()
                if plugin_manager:
                    await plugin_manager.execute_hook("pre_request", request, auth_context)
                # Get target server
                target_server = await self.load_balancer.get_server(
                    user_id=auth_context.user_id, path=path
                )

                if not target_server:
                    raise HTTPException(
                        status_code=503, detail="No healthy backend servers"
                    )

                # Read request body
                body = await request.body()

                # MCP Request Validation & Safeguards
                if self.config.mcp_safeguards_enabled:
                    try:
                        validated_body = await self.mcp_validator.validate_and_sanitize(
                            body, auth_context
                        )
                    except ValueError as e:
                        logger.warning(
                            "MCP request blocked",
                            error=str(e),
                            user=auth_context.user_id,
                        )
                        raise HTTPException(
                            status_code=400, detail=f"Request blocked: {e}"
                        )
                else:
                    validated_body = body

                # Prepare headers
                headers = dict(request.headers)
                headers["X-MCPRelay-User"] = auth_context.user_id
                headers["X-MCPRelay-Request-ID"] = auth_context.request_id

                # Make request to backend
                backend_url = f"{target_server.url.rstrip('/')}/{path.lstrip('/')}"

                logger.info(
                    "Proxying request",
                    user=auth_context.user_id,
                    method=request.method,
                    backend=target_server.name,
                    url=backend_url,
                )

                response = await self.client.request(
                    method=request.method,
                    url=backend_url,
                    content=validated_body,
                    headers=headers,
                    params=request.query_params,
                )

                # MCP Response Safeguards
                if self.config.mcp_safeguards_enabled:
                    sanitized_content = await self.mcp_sanitizer.sanitize_response(
                        response.content, auth_context
                    )
                else:
                    sanitized_content = response.content

                # Update metrics
                REQUEST_COUNT.labels(
                    method=request.method, endpoint=path, status=response.status_code
                ).inc()

                # Create response
                response_headers = dict(response.headers)
                response_headers["X-MCPRelay-Backend"] = target_server.name

                final_response = Response(
                    content=sanitized_content,
                    status_code=response.status_code,
                    headers=response_headers,
                )

                # Execute post-response hooks
                if plugin_manager:
                    await plugin_manager.execute_hook("post_response", final_response, auth_context)

                return final_response

            except httpx.RequestError as e:
                logger.error("Backend request failed", error=str(e))
                raise HTTPException(status_code=502, detail="Backend request failed")

            except Exception as e:
                logger.error("Unexpected error", error=str(e))
                raise HTTPException(status_code=500, detail="Internal server error")

            finally:
                ACTIVE_CONNECTIONS.dec()


def create_app(config: MCPRelayConfig) -> FastAPI:
    """Create and configure FastAPI application."""

    app = FastAPI(
        title="MCPRelay",
        description="Enterprise-grade MCP gateway",
        version="0.1.0",
        docs_url="/docs" if config.debug_mode else None,
        redoc_url="/redoc" if config.debug_mode else None,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize relay
    relay = MCPRelay(config)

    # Include web UI router
    app.include_router(web_ui_router)

    @app.on_event("startup")
    async def startup():
        """Application startup."""
        logger.info("MCPRelay starting up", config=config.model_dump())
        
        # Initialize license manager
        license_manager = init_license_manager(
            config.enterprise.license_key,
            config.enterprise.license_file
        )
        
        # Initialize plugin manager
        plugin_manager = init_plugin_manager(license_manager)
        
        # Load plugins if enabled
        if config.plugins.enabled:
            await plugin_manager.discover_and_load_plugins(config.plugins.plugin_packages)
        
        # Execute startup hooks
        await plugin_manager.execute_hook("server_startup", config)
        
        init_auth_manager(config)
        init_rate_limiter(config)
        await relay.load_balancer.start_health_checks()

    @app.on_event("shutdown")
    async def shutdown():
        """Application shutdown."""
        logger.info("MCPRelay shutting down")
        
        # Execute shutdown hooks
        plugin_manager = get_plugin_manager()
        if plugin_manager:
            await plugin_manager.execute_hook("server_shutdown")
            await plugin_manager.shutdown_all_plugins()
        
        await relay.client.aclose()
        await relay.load_balancer.stop_health_checks()

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        healthy_servers = await relay.load_balancer.get_healthy_servers()
        return {
            "status": "healthy" if healthy_servers else "degraded",
            "backend_servers": len(healthy_servers),
            "total_servers": len(config.servers),
        }

    # Metrics endpoint
    @app.get("/metrics")
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    # Main proxy endpoint with auth and rate limiting
    @app.api_route(
        "/mcp/{path:path}",
        methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"],
    )
    async def proxy_mcp(
        request: Request,
        path: str,
        auth_context: AuthContext = Depends(get_current_user),
        _rate_check=Depends(rate_limit_check),
    ):
        """Proxy MCP requests to backend servers."""
        return await relay.proxy_request(request, auth_context, path)

    # Root endpoint for basic MCP discovery
    @app.get("/")
    async def root():
        """Root endpoint with basic info."""
        return {
            "service": "MCPRelay",
            "version": "0.1.0",
            "mcp_endpoint": "/mcp/",
            "health": "/health",
            "metrics": "/metrics",
        }

    # Configuration endpoint (admin only)
    @app.get("/admin/config")
    async def get_config(auth_context: AuthContext = Depends(get_current_user)):
        """Get current configuration (admin only)."""
        if not auth_context.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        # Return config without sensitive data
        safe_config = config.model_dump()
        if "auth" in safe_config and "api_keys" in safe_config["auth"]:
            safe_config["auth"]["api_keys"] = {
                k: "***" for k in safe_config["auth"]["api_keys"]
            }
        if "enterprise" in safe_config and "license_key" in safe_config["enterprise"]:
            safe_config["enterprise"]["license_key"] = "***" if safe_config["enterprise"]["license_key"] else None

        return safe_config

    # License information endpoint (admin only)
    @app.get("/admin/license")
    async def get_license_info(auth_context: AuthContext = Depends(get_current_user)):
        """Get license information (admin only)."""
        if not auth_context.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        license_manager = get_license_manager()
        if not license_manager:
            return {"status": "no_license_manager"}

        return {
            "license_info": license_manager.get_license_info(),
            "feature_status": license_manager.get_feature_status(),
        }

    # Plugin status endpoint (admin only)
    @app.get("/admin/plugins")
    async def get_plugin_status(auth_context: AuthContext = Depends(get_current_user)):
        """Get plugin status (admin only)."""
        if not auth_context.is_admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        plugin_manager = get_plugin_manager()
        if not plugin_manager:
            return {"status": "no_plugin_manager"}

        plugins = plugin_manager.get_enabled_plugins()
        return {
            "enabled": len(plugins) > 0,
            "plugin_count": len(plugins),
            "plugins": [
                {
                    "name": p.name,
                    "enabled": p.enabled,
                    "required_features": p.get_required_features(),
                }
                for p in plugins
            ],
            "available_hooks": list(plugin_manager.hooks.keys()),
        }

    return app
