FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy all application code
COPY . ./

# Copy production config
COPY deploy/gcp/config.production.yaml ./config.yaml

# Install the package
RUN pip install --no-cache-dir .

# Create non-root user
RUN groupadd -r mcprelay && useradd -r -g mcprelay mcprelay
RUN chown -R mcprelay:mcprelay /app
USER mcprelay

# Expose ports
EXPOSE 8080 9090

# Health check using python
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Default command
CMD ["mcprelay", "serve"]