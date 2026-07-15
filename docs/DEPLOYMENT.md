# Deployment Guide

## Overview

Cloud AI Monitor deploys as a single container serving both the React frontend and FastAPI backend, connected to a PostgreSQL database. All resources are deployed in the `red1intheocean-dev` namespace on the Red Hat OpenShift Developer Sandbox.

## Prerequisites

1. **Red Hat Developer Sandbox account** — [Sign up here](https://developers.redhat.com/developer-sandbox)
2. **oc CLI** — [Install guide](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html)
3. **Docker** (for building images locally) or rely on GitHub Actions
4. **GitHub account** (for GHCR image registry and CI/CD)

## Architecture Decision

We use **Option A: Single Container** where FastAPI serves both the API and the built React frontend as static files.

Why:
- Developer Sandbox has limited resources (7 GB RAM, 15 GB storage)
- One deployment = simpler to manage, debug, and monitor
- FastAPI already has built-in static file serving
- Single route, no complex ingress rules needed

## Step-by-Step Deployment

### Step 1: Get Your OpenShift Credentials

1. Log into [Red Hat OpenShift Developer Sandbox](https://console.redhat.com/openshift/sandbox)
2. Click your username (top right) → **Copy login command**
3. Click **Display Token**
4. Copy the `oc login` command — it looks like:
   ```bash
   oc login --token=sha256~XXXXXXXX --server=https://api.rm2.thpm.p1.openshiftapps.com:6443
   ```

### Step 2: Configure Secrets

Edit `openshift/secrets.yaml` and replace the placeholder values:

```yaml
stringData:
  DATABASE_URL: "postgresql://cloudwatch:YOUR_STRONG_PASSWORD@postgresql:5432/cloudwatch"
  POSTGRES_PASSWORD: "YOUR_STRONG_PASSWORD"
  SECRET_KEY: "your-random-32-char-secret-key-here"
```

Generate a secure password:
```bash
openssl rand -base64 24
```

### Step 3: Deploy via Script

```bash
# Login to OpenShift
oc login --token=sha256~YOUR_TOKEN --server=https://api.rm2.thpm.p1.openshiftapps.com:6443

# Run deployment
./scripts/deploy.sh
```

### Step 4: Verify

```bash
# Check pods are running
oc get pods -n red1intheocean-dev

# Check the route
oc get routes -n red1intheocean-dev

# View logs
oc logs deployment/cloud-ai-monitor -n red1intheocean-dev -f
```

## Manual Deployment (Without Script)

```bash
# 1. Login
oc login --token=sha256~YOUR_TOKEN --server=https://api.rm2.thpm.p1.openshiftapps.com:6443
oc project red1intheocean-dev

# 2. Create secrets
oc apply -f openshift/secrets.yaml

# 3. Create config
oc apply -f openshift/configmap.yaml

# 4. Deploy PostgreSQL
oc apply -f openshift/postgresql.yaml
oc rollout status deployment/postgresql --timeout=120s

# 5. Deploy application
oc apply -f openshift/deployment.yaml
oc rollout status deployment/cloud-ai-monitor --timeout=180s

# 6. Get URL
oc get route cloud-ai-monitor -o jsonpath='{.spec.host}'
```

## Deploying from the OpenShift Web Console

If you prefer the GUI:

1. Go to **Developer** perspective (top-left dropdown)
2. Click **+Add** in the left sidebar
3. Choose **Container images**
4. Image: `ghcr.io/red1intheocean/cloud-ai-monitor:latest`
5. Application name: `cloud-ai-monitor`
6. Resource type: **Deployment**
7. Target port: `8080`
8. Check **Create a Route**
9. Click **Create**

Then add the database:
1. Click **+Add** → **Database** → **PostgreSQL**
2. Set the same credentials as in your secrets

## CI/CD Automated Deployment

Once GitHub Actions is configured (see [CI_CD.md](CI_CD.md)), every push to `main` will automatically:
1. Build the Docker image
2. Push to GHCR
3. Deploy to OpenShift with a rolling update

## Troubleshooting

### Pod stuck in CrashLoopBackOff
```bash
oc logs deployment/cloud-ai-monitor --previous
```
Usually means DATABASE_URL is wrong or PostgreSQL isn't ready yet.

### Route not accessible
```bash
oc get route cloud-ai-monitor -o yaml
```
Check that TLS termination is set to `edge`.

### Database connection refused
```bash
oc get pods | grep postgresql
oc logs deployment/postgresql
```
Check if PostgreSQL pod is running and secrets match.

### Image pull errors
Make sure the GHCR image is public, or create an image pull secret:
```bash
oc create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=YOUR_GITHUB_USERNAME \
  --docker-password=YOUR_GITHUB_PAT \
  --docker-email=your@email.com

oc secrets link default ghcr-secret --for=pull
```
