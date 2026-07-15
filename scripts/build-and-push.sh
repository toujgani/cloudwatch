#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Cloud AI Monitor — Build and Push Docker Image to GHCR
# Usage: ./scripts/build-and-push.sh [tag]
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

TAG="${1:-latest}"
IMAGE="ghcr.io/red1intheocean/cloud-ai-monitor:${TAG}"

echo "═══════════════════════════════════════════════════════════════"
echo "  Building: ${IMAGE}"
echo "═══════════════════════════════════════════════════════════════"

# Build
docker build -t "${IMAGE}" .

# Also tag as latest
docker tag "${IMAGE}" "ghcr.io/red1intheocean/cloud-ai-monitor:latest"

echo ""
echo "▶ Pushing to GHCR..."
docker push "${IMAGE}"
docker push "ghcr.io/red1intheocean/cloud-ai-monitor:latest"

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ Image pushed: ${IMAGE}"
echo "═══════════════════════════════════════════════════════════════"
