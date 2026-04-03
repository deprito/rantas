#!/bin/bash
# RANTAS Docker Image Build Script for Private Registry
# Version: 4.0
#
# This script builds Docker images locally then pushes to your private registry
#
# Usage:
#   export REGISTRY_USERNAME=kontol
#   export REGISTRY_PASSWORD=memek
#
#   Build and push (default):
#   ./scripts/build-ghcr.sh
#
#   Build only:
#   ./scripts/build-ghcr.sh --build
#
#   Push only:
#   ./scripts/build-ghcr.sh --push

set -e  # Exit on error
set -u # Exit on unset
set -o pipefail # Exit on pipe failure

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Default values
IMAGE_VERSION="${IMAGE_VERSION:-latest}"
REGISTRY_USERNAME="${REGISTRY_USERNAME:-}"
REGISTRY_PASSWORD="${REGISTRY_PASSWORD:-}"

# Registry configuration - set to your registry (e.g., ghcr.io/your-org)
REGISTRY_HOST="${REGISTRY_HOST:-ghcr.io/your-org}"

# Production API URL baked into Next.js frontend at build time
PRODUCTION_API_URL="${PRODUCTION_API_URL:-http://localhost:9000/api}"

# Image names
BACKEND_IMAGE="${REGISTRY_HOST}/rantas-backend"
FRONTEND_IMAGE="${REGISTRY_HOST}/rantas-frontend"

# Platform
PLATFORMS="${PLATFORMS:-linux/amd64}"

# Flags
DO_BUILD=false
DO_PUSH=false

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case "$1" in
        build|--build)
            DO_BUILD=true
            ;;
        push|--push)
            DO_PUSH=true
            ;;
        *)
            echo -e "${RED}Error: Unknown option: $1${NC}"
            echo "Usage: $0 [--build] [--push]"
            echo "  --build    Build images only"
            echo "  --push     Push images only"
            echo "  (no flags)  Build and push (default)"
            exit 1
            ;;
    esac
    shift
done

# If no flags specified, do both
if [ "$DO_BUILD" = false ] && [ "$DO_PUSH" = false ]; then
    DO_BUILD=true
    DO_PUSH=true
fi

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
print_info "Registry Username: ${REGISTRY_USERNAME}"
print_info "Backend Image: ${BACKEND_IMAGE}:${IMAGE_VERSION}"
print_info "Frontend Image: ${FRONTEND_IMAGE}:${IMAGE_VERSION}"
print_info "Production API URL: ${PRODUCTION_API_URL}"
print_info "Platform: ${PLATFORMS}"
print_info "Build: ${DO_BUILD}"
print_info "Push: ${DO_PUSH}"
echo ""

# Login to private registry
print_step "Logging into ${REGISTRY_HOST}..."
echo "$REGISTRY_PASSWORD" | docker login "${REGISTRY_HOST}" -u "$REGISTRY_USERNAME" --password-stdin
if [ $? -ne 0 ]; then
    print_error "Login failed"
    exit 1
fi
print_info "Login successful"

# Build images
if [ "$DO_BUILD" = true ]; then
    print_step "Building Docker images..."

    # Build backend
    print_info "Building backend: ${BACKEND_IMAGE}:${IMAGE_VERSION} (${PLATFORMS})"
    docker build \
        --platform "${PLATFORMS}" \
        --tag "${BACKEND_IMAGE}:${IMAGE_VERSION}" \
        --tag "${BACKEND_IMAGE}:latest" \
        --file ./backend/Dockerfile \
        ./backend
    if [ $? -ne 0 ]; then
        print_error "Backend build failed"
        exit 1
    fi
    print_info "Backend build complete"

    # Build frontend with production API URL baked at build time
    print_info "Building frontend: ${FRONTEND_IMAGE}:${IMAGE_VERSION} (${PLATFORMS})"
    print_info "Baking NEXT_PUBLIC_API_URL=${PRODUCTION_API_URL} into frontend build"
    docker build \
        --platform "${PLATFORMS}" \
        --tag "${FRONTEND_IMAGE}:${IMAGE_VERSION}" \
        --tag "${FRONTEND_IMAGE}:latest" \
        --file ./frontend/Dockerfile \
        --build-arg "NEXT_PUBLIC_API_URL=${PRODUCTION_API_URL}" \
        ./frontend
    if [ $? -ne 0 ]; then
        print_error "Frontend build failed"
        exit 1
    fi
    print_info "Frontend build complete"
    echo ""
fi

# Push images
if [ "$DO_PUSH" = true ]; then
    print_step "Pushing images to ${REGISTRY_HOST}..."

    # Push backend tags
    print_info "Pushing ${BACKEND_IMAGE}:${IMAGE_VERSION}"
    docker push "${BACKEND_IMAGE}:${IMAGE_VERSION}"
    print_info "Pushing ${BACKEND_IMAGE}:latest"
    docker push "${BACKEND_IMAGE}:latest"

    # Push frontend tags
    print_info "Pushing ${FRONTEND_IMAGE}:${IMAGE_VERSION}"
    docker push "${FRONTEND_IMAGE}:${IMAGE_VERSION}"
    print_info "Pushing ${FRONTEND_IMAGE}:latest"
    docker push "${FRONTEND_IMAGE}:latest"

    if [ $? -ne 0 ]; then
        print_error "Push failed"
        exit 1
    fi

    print_info "Push complete"
    echo ""
fi

print_step "Summary"
echo "Images available:"
echo "  - ${BACKEND_IMAGE}:${IMAGE_VERSION}"
echo "  - ${BACKEND_IMAGE}:latest"
echo "  - ${FRONTEND_IMAGE}:${IMAGE_VERSION}"
echo "  - ${FRONTEND_IMAGE}:latest"
echo ""
print_info "To deploy: go to Portainer -> phishtrack stack -> Editor -> check 'Re-pull image' -> Update"
echo ""
