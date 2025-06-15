"""
Load balancing and health checking for MCPRelay.
"""

import asyncio
import random
from typing import Dict, List, Optional

import httpx
import structlog

from .config import MCPServerConfig

logger = structlog.get_logger()


class ServerHealth:
    """Track health status of a server."""

    def __init__(self, server: MCPServerConfig):
        self.server = server
        self.is_healthy = True
        self.consecutive_failures = 0
        self.last_check = 0
        self.response_time = 0.0


class LoadBalancer:
    """Load balancer with health checking."""

    def __init__(self, servers: List[MCPServerConfig]):
        self.servers = {server.name: ServerHealth(server) for server in servers}
        self.current_index = 0
        self.health_check_task = None
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def start_health_checks(self):
        """Start health checking task."""
        if self.servers:
            self.health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info(f"Started health checks for {len(self.servers)} servers")

    async def stop_health_checks(self):
        """Stop health checking task."""
        if self.health_check_task:
            self.health_check_task.cancel()
            try:
                await self.health_check_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()

    async def get_server(
        self, user_id: Optional[str] = None, path: Optional[str] = None
    ) -> Optional[MCPServerConfig]:
        """Get next available server using load balancing."""

        healthy_servers = await self.get_healthy_servers()

        if not healthy_servers:
            logger.error("No healthy servers available")
            return None

        # Route based on tags if path is provided
        if path:
            tagged_servers = self._filter_by_tags(healthy_servers, path)
            if tagged_servers:
                healthy_servers = tagged_servers

        # Use weighted round-robin
        return self._weighted_round_robin(healthy_servers)

    async def get_healthy_servers(self) -> List[MCPServerConfig]:
        """Get list of healthy servers."""
        return [health.server for health in self.servers.values() if health.is_healthy]

    def _filter_by_tags(
        self, servers: List[MCPServerConfig], path: str
    ) -> List[MCPServerConfig]:
        """Filter servers by tags based on request path."""
        # Simple tag-based routing
        # You can extend this with more sophisticated routing logic

        if "smart-home" in path or "hue" in path:
            return [
                s for s in servers if "smart-home" in s.tags or "lighting" in s.tags
            ]
        elif "github" in path or "git" in path:
            return [s for s in servers if "development" in s.tags or "git" in s.tags]

        return servers

    def _weighted_round_robin(self, servers: List[MCPServerConfig]) -> MCPServerConfig:
        """Select server using weighted round-robin."""
        if len(servers) == 1:
            return servers[0]

        # Calculate total weight
        total_weight = sum(server.weight for server in servers)

        # Generate random number
        r = random.randint(1, total_weight)

        # Select server based on weight
        current_weight = 0
        for server in servers:
            current_weight += server.weight
            if r <= current_weight:
                return server

        # Fallback to first server
        return servers[0]

    async def _health_check_loop(self):
        """Periodic health check loop."""
        while True:
            try:
                await self._check_all_servers()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Health check error", error=str(e))
                await asyncio.sleep(30)

    async def _check_all_servers(self):
        """Check health of all servers."""
        tasks = [self._check_server_health(health) for health in self.servers.values()]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _check_server_health(self, server_health: ServerHealth):
        """Check health of a single server."""
        server = server_health.server

        try:
            start_time = asyncio.get_event_loop().time()

            response = await self.client.get(
                f"{server.url.rstrip('/')}{server.health_check_path}",
                timeout=server.timeout,
            )

            end_time = asyncio.get_event_loop().time()
            server_health.response_time = end_time - start_time

            if response.status_code == 200:
                if not server_health.is_healthy:
                    logger.info(f"Server {server.name} is now healthy")

                server_health.is_healthy = True
                server_health.consecutive_failures = 0
            else:
                self._mark_unhealthy(server_health, f"HTTP {response.status_code}")

        except Exception as e:
            self._mark_unhealthy(server_health, str(e))

    def _mark_unhealthy(self, server_health: ServerHealth, reason: str):
        """Mark server as unhealthy."""
        server_health.consecutive_failures += 1

        # Mark unhealthy after 3 consecutive failures
        if server_health.consecutive_failures >= 3:
            if server_health.is_healthy:
                logger.warning(
                    f"Server {server_health.server.name} marked unhealthy",
                    reason=reason,
                    failures=server_health.consecutive_failures,
                )
            server_health.is_healthy = False

    def get_server_stats(self) -> Dict:
        """Get server statistics."""
        stats = {}
        for name, health in self.servers.items():
            stats[name] = {
                "healthy": health.is_healthy,
                "consecutive_failures": health.consecutive_failures,
                "response_time": health.response_time,
                "url": health.server.url,
            }
        return stats
