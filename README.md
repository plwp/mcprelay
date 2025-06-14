# MCPRelay

Enterprise-grade MCP gateway for secure, scalable Model Context Protocol deployments.

## Vision

Build the "nginx for MCP" - essential infrastructure that every company needs to safely deploy MCP servers in production.

## Market Opportunity

- **Security gap**: MCP servers currently deployed with no enterprise controls
- **First-mover advantage**: No existing enterprise MCP gateway solutions  
- **Large market**: Every company using AI needs secure MCP deployment
- **Proven model**: Start open source, monetize enterprise features

## Core Features

### Phase 1: Open Source MVP (Weeks 1-2)
- [ ] API key authentication & management
- [ ] Rate limiting (per user/API key)
- [ ] Request/response logging
- [ ] Load balancing across MCP server instances
- [ ] Health checks & circuit breakers
- [ ] Docker deployment with YAML config

### Phase 2: Production Ready (Weeks 3-4)
- [ ] JWT token validation
- [ ] IP whitelisting/blacklisting
- [ ] Request signing & verification
- [ ] Prometheus metrics integration
- [ ] Basic web dashboard
- [ ] CLI for management

### Phase 3: Enterprise Features (Month 2)
- [ ] SSO integration (SAML, OIDC)
- [ ] Advanced RBAC
- [ ] Audit logging
- [ ] SLA monitoring
- [ ] Enterprise dashboard
- [ ] Managed hosting option

### Phase 4: Platform (Month 3)
- [ ] Multi-tenant deployment
- [ ] Auto-scaling
- [ ] Advanced analytics
- [ ] Support & SLA tiers

## Tech Stack

- **Core**: Go (performance + enterprise adoption)
- **Config**: YAML-based configuration
- **Metrics**: Prometheus + Grafana
- **Storage**: PostgreSQL (audit logs), Redis (caching)
- **Deployment**: Docker, Kubernetes ready
- **Frontend**: Next.js dashboard (when needed)

## Revenue Model

### Open Source (Free)
- Core gateway functionality
- Basic authentication & rate limiting
- Community support

### Enterprise ($500-5000/month)
- SSO integration
- Advanced RBAC & audit logging
- SLA & dedicated support
- Managed hosting option

## Getting Started

```bash
# Download latest release
wget https://github.com/plwp/mcprelay/releases/latest/mcprelay

# Run with config
./mcprelay --config config.yaml

# Or with Docker
docker run -p 8080:8080 -v ./config.yaml:/config.yaml mcprelay/mcprelay
```

## Architecture

```
AI Client → MCPRelay Gateway → MCP Server(s)
              ↓
        [Auth, Rate Limit, Load Balance, Monitor]
```

MCPRelay sits between your AI clients and MCP servers, providing enterprise-grade security and observability without requiring changes to existing MCP servers.

## Project Structure

```
├── cmd/              # CLI application entry points
├── internal/         # Private application code
│   ├── gateway/      # Core gateway logic
│   ├── auth/         # Authentication providers
│   ├── config/       # Configuration management
│   └── metrics/      # Observability
├── pkg/              # Public libraries
├── deployments/      # Docker, K8s manifests
└── docs/             # Documentation
```