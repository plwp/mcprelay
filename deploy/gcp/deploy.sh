#!/bin/bash

# MCPRelay GCP Deployment Script
set -e

# Configuration
PROJECT_ID=""
REGION="us-central1"
SERVICE_NAME="mcprelay"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 MCPRelay GCP Deployment${NC}"
echo "================================"

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}❌ gcloud CLI is not installed. Please install it first.${NC}"
    exit 1
fi

# Get project ID if not set
if [ -z "$PROJECT_ID" ]; then
    PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
    if [ -z "$PROJECT_ID" ]; then
        echo -e "${RED}❌ No GCP project set. Please run: gcloud config set project YOUR_PROJECT_ID${NC}"
        exit 1
    fi
fi

echo -e "${YELLOW}📋 Using project: $PROJECT_ID${NC}"
echo -e "${YELLOW}📍 Using region: $REGION${NC}"

# Enable required APIs
echo -e "${YELLOW}🔧 Enabling required GCP APIs...${NC}"
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    --project=$PROJECT_ID

# Build and deploy using Cloud Build
echo -e "${YELLOW}🏗️  Building and deploying with Cloud Build...${NC}"
gcloud builds submit \
    --config=deploy/gcp/cloudbuild.yaml \
    --project=$PROJECT_ID \
    .

# Get the service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION \
    --project=$PROJECT_ID \
    --format="value(status.url)")

echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo -e "${GREEN}🌐 Service URL: $SERVICE_URL${NC}"
echo -e "${GREEN}📊 Health Check: $SERVICE_URL/health${NC}"
echo -e "${GREEN}📈 Metrics: $SERVICE_URL/metrics${NC}"
echo -e "${GREEN}⚙️  Admin UI: $SERVICE_URL/admin${NC}"
echo ""
echo -e "${YELLOW}📝 Next steps:${NC}"
echo "1. Configure your MCP servers in the admin UI"
echo "2. Set up authentication (API keys)"
echo "3. Configure custom domain (optional)"
echo "4. Set up monitoring and alerting"
echo ""
echo -e "${YELLOW}💡 Useful commands:${NC}"
echo "gcloud run services describe $SERVICE_NAME --region=$REGION"
echo "gcloud run services update $SERVICE_NAME --region=$REGION --set-env-vars KEY=VALUE"
echo "gcloud logging read 'resource.type=\"cloud_run_revision\" resource.labels.service_name=\"$SERVICE_NAME\"' --limit=50"