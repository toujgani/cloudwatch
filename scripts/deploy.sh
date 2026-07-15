#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Cloud AI Monitor — Deploy to OpenShift Developer Sandbox
# Usage: ./scripts/deploy.sh
#
# Prerequisites:
#   1. oc CLI installed
#   2. Logged into OpenShift: oc login --token=<TOKEN> --server=<SERVER>
#   3. Docker image pushed to GHCR (or use oc new-build)
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

NAMESPACE="red1intheocean-dev"
IMAGE="ghcr.io/red1intheocean/cloud-ai-monitor:latest"

echo "═══════════════════════════════════════════════════════════════"
echo "  Cloud AI Monitor — Deploying to OpenShift"
echo "  Namespace: ${NAMESPACE}"
echo "═══════════════════════════════════════════════════════════════"

# Verify login
echo ""
echo "▶ Verifying OpenShift login..."
oc whoami || { echo "ERROR: Not logged in. Run: oc login --token=<TOKEN> --server=<SERVER>"; exit 1; }
oc project "${NAMESPACE}" || { echo "ERROR: Cannot switch to namespace ${NAMESPACE}"; exit 1; }

# Step 1: Secrets
echo ""
echo "▶ Step 1: Applying secrets..."
oc apply -f openshift/secrets.yaml -n "${NAMESPACE}"

# Step 2: ConfigMap
echo ""
echo "▶ Step 2: Applying ConfigMap..."
oc apply -f openshift/configmap.yaml -n "${NAMESPACE}"

# Step 3: PostgreSQL
echo ""
echo "▶ Step 3: Deploying PostgreSQL..."
oc apply -f openshift/postgresql.yaml -n "${NAMESPACE}"
echo "  Waiting for PostgreSQL..."
oc rollout status deployment/postgresql -n "${NAMESPACE}" --timeout=120s

# Step 4: Application
echo ""
echo "▶ Step 4: Deploying Cloud AI Monitor..."
oc apply -f openshift/deployment.yaml -n "${NAMESPACE}"
echo "  Waiting for application..."
oc rollout status deployment/cloud-ai-monitor -n "${NAMESPACE}" --timeout=180s

# Step 5: Get Route
echo ""
echo "▶ Step 5: Getting application URL..."
ROUTE=$(oc get route cloud-ai-monitor -n "${NAMESPACE}" -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [ -n "${ROUTE}" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✅ Deployment successful!"
    echo "  🌐 Application URL: https://${ROUTE}"
    echo "═══════════════════════════════════════════════════════════════"
else
    echo "  ⚠️  Route not found. Check: oc get routes -n ${NAMESPACE}"
fi
