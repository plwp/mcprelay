# MCPRelay

Enterprise-grade gateway for Model Context Protocol (MCP) servers. Secure, scalable, and production-ready.

## Overview

MCPRelay is an open-source API gateway designed specifically for MCP (Model Context Protocol) servers. It provides enterprise-grade security, authentication, rate limiting, and monitoring capabilities for production MCP deployments.

## Features

- **Security First**: MCP-aware request validation and response sanitization
- **Authentication**: API key and JWT-based authentication with role-based access control
- **Rate Limiting**: Token bucket rate limiting with per-user tiers
- **Load Balancing**: Intelligent load balancing with health checks and failover
- **Monitoring**: Prometheus metrics, structured logging, and real-time dashboard
- **Easy Deployment**: Docker-based deployment with YAML configuration
- **Web Interface**: Modern admin dashboard for configuration and monitoring

## Quick Start

### Using the Quick Start Script

```bash
git clone https://github.com/plwp/mcprelay.git
cd mcprelay
./quickstart.sh
```

### Manual Installation

```bash
# Install dependencies
pip install -e .

# Create configuration
cp config.example.yaml config.yaml
# Edit config.yaml to add your MCP servers

# Start the gateway
mcprelay serve
```

### Docker Deployment

```bash
# Using Docker Compose (recommended)
docker-compose up -d

# Or run directly
docker run -p 8080:8080 -v ./config.yaml:/app/config.yaml mcprelay/mcprelay
```

## Configuration

MCPRelay uses YAML configuration. Here's a minimal example:

```yaml
# Basic server settings
host: "0.0.0.0"
port: 8080

# MCP servers to proxy to
servers:
  - name: "hue-server"
    url: "http://localhost:3000"
    weight: 1
    timeout: 30

# Authentication
auth:
  enabled: true
  method: "api_key"
  api_keys:
    admin: "your-admin-key"

# Rate limiting
rate_limit:
  enabled: true
  default_requests_per_minute: 60
  burst_size: 10

# Security
mcp_safeguards_enabled: true
```

## Architecture

```
AI Client → MCPRelay Gateway → MCP Server(s)
              ↓
        [Auth, Rate Limit, Load Balance, Monitor]
```

MCPRelay sits between your AI clients and MCP servers, providing:

- **Request Authentication**: Validates API keys or JWT tokens
- **Rate Limiting**: Prevents abuse with configurable limits
- **Load Balancing**: Distributes requests across healthy backend servers
- **Request Validation**: MCP-aware filtering of dangerous operations
- **Response Sanitization**: Strips sensitive data from responses
- **Monitoring**: Comprehensive metrics and logging

## API Endpoints

- `GET /health` - Health check endpoint
- `GET /metrics` - Prometheus metrics
- `POST /mcp/{path}` - Main proxy endpoint for MCP requests
- `GET /admin/` - Web administration interface

## Web Dashboard

MCPRelay includes a modern web interface for administration:

- **Dashboard**: Real-time statistics and recent activity
- **Server Management**: Add, remove, and monitor backend servers
- **Configuration**: Edit settings through the web UI
- **Logs**: View and filter system logs
- **Metrics**: Performance analytics and visualizations

Access the dashboard at `http://localhost:8080/admin/` (requires admin authentication).

## CLI Usage

```bash
# Start the server
mcprelay serve

# Validate configuration
mcprelay validate

# Check backend health
mcprelay health

# Show version
mcprelay version
```

## Security

MCPRelay provides multiple layers of security:

### MCP Safeguards
- Validates JSON-RPC requests for proper MCP format
- Blocks dangerous operations (file system access, code execution)
- Sanitizes responses to prevent data leakage

### Authentication
- API key authentication with configurable keys
- JWT token validation with proper claims checking
- Role-based access control (admin vs user permissions)

### Rate Limiting
- Token bucket algorithm with configurable rates
- Per-user rate limits
- Burst capacity for handling traffic spikes

## Monitoring

### Metrics
MCPRelay exports Prometheus metrics including:
- Request count and rate
- Response times and percentiles
- Backend server health status
- Error rates and types

### Logging
Structured JSON logging with configurable levels:
- Request/response logging
- Security event logging
- Performance metrics
- Error tracking

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/plwp/mcprelay/issues)
- **Discussions**: [GitHub Discussions](https://github.com/plwp/mcprelay/discussions)
- **Documentation**: [mcprelay.org](https://mcprelay.org)