<div align="center">

# Cloud AI Monitor — CI/CD Pipeline

### Automated Build, Push & Deploy

</div>

---

## Pipeline Overview

```
Developer pushes to main
        │
        ▼
┌─────────────────────────┐
│    GitHub Actions        │
│                         │
│  1. Checkout code       │
│  2. Build Docker image  │   (multi-stage: Node + Python)
│  3. Push to GHCR        │   (tagged with commit SHA + latest)
│  4. Login to OpenShift  │   (service account token)
│  5. Apply manifests     │   (configmap, deployment)
│  6. Trigger rollout     │   (new pod with new image)
│  7. Verify health       │
└─────────────────────────┘
        │
        ▼
  Application updated
  (zero-downtime rolling update)
```

---

## Setup (One Time)

### GitHub Repository Secrets

Go to: Settings → Secrets → Actions → New repository secret

| Secret Name | Value |
|-------------|-------|
| `OPENSHIFT_SERVER` | `https://api.rm2.thpm.p1.openshiftapps.com:6443` |
| `OPENSHIFT_TOKEN` | Service account token (expires 2057) |

`GITHUB_TOKEN` is automatic (for GHCR push).

---

## Trigger

- **Automatic**: Every push to `main` branch
- **Manual**: Actions tab → Run workflow

---

## Image Registry

Images are stored at: `ghcr.io/toujgani/cloud-ai-monitor`

Tags:
- `latest` — most recent build
- `sha-<commit>` — specific version

The GHCR package must be **public** for OpenShift to pull without credentials.

---

## Workflow File

Location: `.github/workflows/deploy.yaml`

Key features:
- Docker Buildx with layer caching (fast rebuilds)
- Graceful rollout timeout (sandbox may be slow)
- Always prints the application URL at the end
