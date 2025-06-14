"""
Web UI for MCPRelay configuration and monitoring.
"""

from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any
import json
from pathlib import Path

from .auth import require_admin, AuthContext
from .config import MCPRelayConfig, MCPServerConfig

# Setup templates
templates_dir = Path(__file__).parent / "templates"
templates_dir.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_dir))

router = APIRouter(prefix="/admin", tags=["Web UI"])


@router.get("/", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    auth_context: AuthContext = Depends(require_admin)
):
    """Admin dashboard."""
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": auth_context.user_id
    })


@router.get("/servers", response_class=HTMLResponse)
async def manage_servers(
    request: Request,
    auth_context: AuthContext = Depends(require_admin)
):
    """Manage MCP servers."""
    # Get current config
    config = MCPRelayConfig()
    return templates.TemplateResponse("servers.html", {
        "request": request,
        "servers": config.servers,
        "user": auth_context.user_id
    })


@router.post("/servers/add")
async def add_server(
    name: str = Form(...),
    url: str = Form(...),
    timeout: int = Form(30),
    weight: int = Form(1),
    tags: str = Form(""),
    auth_context: AuthContext = Depends(require_admin)
):
    """Add new MCP server."""
    # Parse tags
    tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
    
    # Create new server config
    new_server = MCPServerConfig(
        name=name,
        url=url,
        timeout=timeout,
        weight=weight,
        tags=tag_list
    )
    
    # TODO: Add to config and save
    # For now, just redirect back
    return RedirectResponse(url="/admin/servers", status_code=303)


@router.get("/config", response_class=HTMLResponse)
async def config_editor(
    request: Request,
    auth_context: AuthContext = Depends(require_admin)
):
    """Configuration editor."""
    config = MCPRelayConfig()
    return templates.TemplateResponse("config.html", {
        "request": request,
        "config": config.model_dump(),
        "user": auth_context.user_id
    })


@router.get("/logs", response_class=HTMLResponse)
async def view_logs(
    request: Request,
    auth_context: AuthContext = Depends(require_admin)
):
    """View system logs."""
    # TODO: Implement log viewing
    return templates.TemplateResponse("logs.html", {
        "request": request,
        "logs": [],
        "user": auth_context.user_id
    })


@router.get("/metrics", response_class=HTMLResponse)
async def metrics_dashboard(
    request: Request,
    auth_context: AuthContext = Depends(require_admin)
):
    """Metrics dashboard."""
    return templates.TemplateResponse("metrics.html", {
        "request": request,
        "user": auth_context.user_id
    })