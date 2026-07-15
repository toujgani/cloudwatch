# CI/CD Pipeline

## Overview

The CI/CD pipeline uses GitHub Actions to automatically build, test, and deploy the application to OpenShift on every push to the `main` branch.

```
git push main
     │
     ▼
┌─────────────────┐
│ GitHub Actions   │
│                  │
│ 1. Build Docker  │
│    image         │
│                  │
│ 2. Push to GHCR  │
│                  │
│ 3. Deploy to     │
│    OpenShift     │
│                  │
│ 4. Rolling       │
│    update        │
└─────────────────┘
     │
     ▼
Application restarts
with new version
```

## Setup Instructions

### 1. Create GitHub Repository Secrets

Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Add these secrets:

| Secret Name | Value | How to Get It |
|-------------|-------|---------------|
| `OPENSHIFT_SERVER` | `https://api.rm2.thpm.p1.openshiftapps.com:6443` | From your `oc login` command |
| `OPENSHIFT_TOKEN` | `sha256~XXXXXXXX` | OpenShift web console → Copy login command → Display Token |

Note: `GITHUB_TOKEN` is automatically provided by GitHub Actions for GHCR access.

### 2. Enable GitHub Container Registry (GHCR)

1. Go to your GitHub profile → **Settings** → **Developer settings** → **Personal access tokens**
2. Ensure your repository has **Packages** write permission
3. The workflow uses `GITHUB_TOKEN` which has this by default

### 3. Make GHCR Package Public (Optional)

After the first image push:
1. Go to your GitHub profile → **Packages**
2. Find `cloud-ai-monitor`
3. Click **Package settings** → Change visibility to **Public**

This avoids needing image pull secrets in OpenShift.

### 4. Verify the Pipeline

1. Push a commit to `main`
2. Go to **Actions** tab in your GitHub repo
3. Watch the workflow run
4. Check the deployment step for the application URL

## Workflow File

Located at `.github/workflows/deploy.yaml`

### Jobs:

1. **build-and-push**: Builds the Docker image and pushes to GHCR
   - Uses Docker Buildx for efficient builds
   - Uses GitHub Actions cache for layer caching
   - Tags: `sha-<commit>` + `latest`

2. **deploy**: Deploys to OpenShift
   - Installs `oc` CLI
   - Logs into OpenShift
   - Applies manifests
   - Triggers rolling update
   - Waits for rollout completion

## Manual Trigger

You can also trigger the pipeline manually:
1. Go to **Actions** → **Build & Deploy to OpenShift**
2. Click **Run workflow** → **Run workflow**

## Refreshing the OpenShift Token

The Developer Sandbox token expires periodically. To refresh:

1. Log into the OpenShift web console
2. Copy the new token
3. Update the `OPENSHIFT_TOKEN` secret in GitHub

## Troubleshooting

### Pipeline fails at "Log in to OpenShift"
- Token expired → refresh it (see above)
- Server URL changed → update `OPENSHIFT_SERVER` secret

### Pipeline fails at "Deploy Application"
- Check if namespace exists: `oc get project red1intheocean-dev`
- Check resource quota: `oc describe resourcequota -n red1intheocean-dev`

### Image pull fails in OpenShift
- Make the GHCR package public, or
- Create an image pull secret (see DEPLOYMENT.md)
