"""Command-line interface for MCPRelay."""

import os
from pathlib import Path

import click
import uvicorn

from .config import MCPRelayConfig
from .server import create_app


@click.group()
@click.version_option()
def cli():
    """MCPRelay - Enterprise MCP Gateway"""
    pass


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="config.yaml",
    help="Configuration file path",
)
@click.option("--host", default=None, help="Server host (overrides config)")
@click.option("--port", type=int, default=None, help="Server port (overrides config)")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(config: Path, host: str, port: int, reload: bool):
    """Start the MCPRelay server."""

    # Load configuration
    if config.exists():
        cfg = MCPRelayConfig.from_yaml(str(config))
    else:
        click.echo(f"Configuration file {config} not found, using defaults")
        cfg = MCPRelayConfig()

    # Override with CLI options and environment variables
    if host:
        cfg.host = host
    if port:
        cfg.port = port

    # Cloud Run sets PORT environment variable
    port_env = os.getenv("PORT")
    if port_env:
        cfg.port = int(port_env)

    # Ensure we bind to all interfaces in containerized environments
    if os.getenv("ENVIRONMENT") == "production":
        cfg.host = "0.0.0.0"

    # Create FastAPI app
    app = create_app(cfg)

    # Start server
    click.echo(f"Starting MCPRelay on {cfg.host}:{cfg.port}")
    if cfg.servers:
        click.echo(f"Proxying {len(cfg.servers)} MCP servers:")
        for server in cfg.servers:
            click.echo(f"  - {server.name}: {server.url}")
    else:
        click.echo("Warning: No MCP servers configured")

    uvicorn.run(
        app,
        host=cfg.host,
        port=cfg.port,
        reload=reload,
        access_log=cfg.logging.access_log,
    )


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="config.yaml",
    help="Output configuration file",
)
def init(output: Path):
    """Initialize a new configuration file."""

    if output.exists():
        click.confirm(
            f"Configuration file {output} already exists. Overwrite?", abort=True
        )

    # Create default config
    cfg = MCPRelayConfig()
    cfg.to_yaml(str(output))

    click.echo(f"Created configuration file: {output}")
    click.echo("Edit the file to add your MCP servers and customize settings.")


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="config.yaml",
    help="Configuration file to validate",
)
def validate(config: Path):
    """Validate configuration file."""

    try:
        cfg = MCPRelayConfig.from_yaml(str(config))
        click.echo(f"✓ Configuration file {config} is valid")
        click.echo(f"  - {len(cfg.servers)} MCP servers configured")
        click.echo(
            f"  - Authentication: {'enabled' if cfg.auth.enabled else 'disabled'}"
        )
        click.echo(
            f"  - Rate limiting: {'enabled' if cfg.rate_limit.enabled else 'disabled'}"
        )
        click.echo(f"  - Metrics: {'enabled' if cfg.metrics.enabled else 'disabled'}")
    except Exception as e:
        click.echo(f"✗ Configuration file {config} is invalid: {e}", err=True)
        raise click.Abort()


@cli.command()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    default="config.yaml",
    help="Configuration file",
)
def health(config: Path):
    """Check health of configured MCP servers."""

    import asyncio

    import httpx

    async def check_server_health(server):
        """Check health of a single server."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{server.url}{server.health_check_path}", timeout=server.timeout
                )
                if response.status_code == 200:
                    return f"✓ {server.name} ({server.url}) - OK"
                else:
                    return (
                        f"✗ {server.name} ({server.url}) - HTTP {response.status_code}"
                    )
        except Exception as e:
            return f"✗ {server.name} ({server.url}) - {str(e)}"

    async def check_all():
        cfg = MCPRelayConfig.from_yaml(str(config))
        if not cfg.servers:
            click.echo("No MCP servers configured")
            return

        click.echo("Checking MCP server health...")
        tasks = [check_server_health(server) for server in cfg.servers]
        results = await asyncio.gather(*tasks)

        for result in results:
            click.echo(result)

    asyncio.run(check_all())


def main():
    """Entry point for the CLI."""
    cli()
