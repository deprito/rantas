#!/bin/bash
# RANTAS Frontend Docker Image Build Script
# Version: 2.0
#
# This is a convenience wrapper that builds ONLY the frontend image.
# For building both backend + frontend, use the main script: ../scripts/build-ghcr.sh
#
# Usage:
#   cd frontend
#   ./scripts/build-ghcr.sh
#
# Or from project root:
#   ./frontend/scripts/build-ghcr.sh

set -e
set -u
set -o pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Default values
IMAGE_VERSION="${IMAGE_VERSION:-latest}"
REGISTRY_HOST="${REGISTRY_HOST:-ghcr.io/your-org}"
REGISTRY_USERNAME="${REGISTRY_USERNAME:-}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:-}"
PRODUCTION_API_URL="${PRODUCTION_API_URL:-http://localhost:9000/api}"
PLATFORMS="${PLATFORMS:-linux/amd64}"

# Image name
FRONTEND_IMAGE="${REGISTRY_HOST}/rantas-frontend"

# Determine frontend directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

# Prompt for missing variables
if [ -z "$REGISTRY_USERNAME" ]; then
    read -p "Enter Registry Username: " REGISTRY_USERNAME
fi

if [ -z "$REGISTRY_PASSWORD" ]; then
    echo -n "Enter Registry Password: "
    read -s REGISTRY_PASSWORD
    echo ""
fi

print_step "Configuration"
print_info "Registry: ${REGISTRY_HOST}"
print_info "Frontend Image: ${FRONTEND_IMAGE}:${IMAGE_VERSION}"
print_info "Production API URL: ${PRODUCTION_API_URL}"
print_info "Platform: ${PLATFORMS}"
print_info "Frontend Dir: ${FRONTEND_DIR}"
echo ""

# Login to registry
print_step "Logging into ${REGISTRY_HOST}..."
echo "$REGISTRY_PASSWORD" | docker login "${REGISTRY_HOST}" -u "$REGISTRY_USERNAME" --password-stdin
if [ $? -ne 0 ]; then
    print_error "Login failed"
    exit 1
fi
print_info "Login successful"

# Build frontend
print_step "Building frontend image..."
print_info "Baking NEXT_PUBLIC_API_URL=${PRODUCTION_API_URL} into build"
docker build \
    --platform "${PLATFORMS}" \
    --tag "${FRONTEND_IMAGE}:${IMAGE_VERSION}" \
    --tag "${FRONTEND_IMAGE}:latest" \
    --file "${FRONTEND_DIR}/Dockerfile" \
    --build-arg "NEXT_PUBLIC_API_URL=${PRODUCTION_API_URL}" \
    "${FRONTEND_DIR}"
if [ $? -ne 0 ]; then
    print_error "Frontend build failed"
    exit 1
fi
print_info "Frontend build complete"

# Push
print_step "Pushing images to ${REGISTRY_HOST}..."
docker push "${FRONTEND_IMAGE}:${IMAGE_VERSION}"
docker push "${FRONTEND_IMAGE}:latest"
print_info "Push complete"

echo ""
print_step "Summary"
echo "Images available:"
echo "  - ${FRONTEND_IMAGE}:${IMAGE_VERSION}"
echo "  - ${FRONTEND_IMAGE}:latest"
echo ""
