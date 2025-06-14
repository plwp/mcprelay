#!/bin/bash

# MCPRelay Quick Start Script
echo "🚀 MCPRelay Quick Start"
echo "======================"

# Check if Python 3.11+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not installed."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.11"

if python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)"; then
    echo "✅ Python $PYTHON_VERSION found"
else
    echo "❌ Python $REQUIRED_VERSION+ required, found $PYTHON_VERSION"
    exit 1
fi

# Install MCPRelay
echo "📦 Installing MCPRelay..."
pip install -e .

# Create example config if it doesn't exist
if [ ! -f "config.yaml" ]; then
    echo "📝 Creating config.yaml from example..."
    cp config.example.yaml config.yaml
    echo "✅ Created config.yaml - edit this file to add your MCP servers"
else
    echo "✅ config.yaml already exists"
fi

# Validate configuration
echo "🔍 Validating configuration..."
mcprelay validate

# Show next steps
echo ""
echo "🎉 MCPRelay is ready!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml to add your MCP servers"
echo "2. Run: mcprelay serve"
echo "3. Visit: http://localhost:8080"
echo ""
echo "Quick commands:"
echo "  mcprelay serve          # Start the gateway"
echo "  mcprelay health         # Check backend health"
echo "  mcprelay validate       # Validate config"
echo ""
echo "Docker option:"
echo "  docker-compose up       # Full stack with monitoring"