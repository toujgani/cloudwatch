<div align="center">

# Cloud AI Monitor — Deployment Guide

### OpenShift Developer Sandbox Deployment

</div>

---

## Prerequisites

| Tool | Purpose |
|------|---------|
| `oc` CLI | OpenShift command line |
| Podman or Docker | Build container images |
| Git | Version control |
| GitHub account | CI/CD + GHCR image registry |

---

## Architecture Decision: Single Container

FastAPI serves both the API and the React frontend as static files.

```
One Dockerfile → One Image → One Deployment → One Route → One URL
```

Why: Developer Sandbox has limited resources. One pod uses less quota than two.

---

## Step-by-Step Deployment

### 1. Build & Push Image

```bash
podman build -t ghcr.io/toujgani/cloud-ai-monitor:latest .
podman push ghcr.io/toujgani/cloud-ai-monitor:latest
```

### 2. Login to OpenShift

```bash
oc login --token=YOUR_TOKEN --server=https://api.rm2.thpm.p1.openshiftapps.com:6443
```

### 3. Deploy

```bash
oc apply -f openshift/secrets.yaml
oc apply -f openshift/configmap.yaml
oc apply -f openshift/postgresql.yaml
oc rollout status deployment/postgresql --timeout=90s
oc apply -f openshift/deployment.yaml
```

### 4. Access

```bash
oc get route cloud-ai-monitor -o jsonpath='{.spec.host}'
```

Open: `https://<that-url>`

---

## CI/CD (Automatic)

Every `git push` to `main` triggers:

```
Push → GitHub Actions → Build Image → Push GHCR → Deploy OpenShift
```

Required GitHub Secrets:
- `OPENSHIFT_SERVER`: `https://api.rm2.thpm.p1.openshiftapps.com:6443`
- `OPENSHIFT_TOKEN`: Service account token (expires 2057)

---

## If the App Goes Down

```bash
oc scale deployment/postgresql --replicas=1 -n red1intheocean-dev
oc scale deployment/cloud-ai-monitor --replicas=1 -n red1intheocean-dev
```

Wait 30 seconds. Both pods restart automatically.

---

## Updating Secrets

```bash
# SMTP password
oc patch secret cloudwatch-secrets -n red1intheocean-dev \
  -p '{"stringData":{"SMTP_PASSWORD":"your_password"}}'

# OpenStack password
oc patch secret cloudwatch-secrets -n red1intheocean-dev \
  -p '{"stringData":{"OS_PASSWORD":"your_password"}}'

# Restart to pick up changes
oc rollout restart deployment/cloud-ai-monitor -n red1intheocean-dev
```

---

## Troubleshooting

| Symptom | Command | Fix |
|---------|---------|-----|
| App not available | `oc get pods` | Scale up if 0/0 |
| Image pull error | Check GHCR package visibility | Make package public |
| Pod CrashLoopBackOff | `oc logs deployment/cloud-ai-monitor` | Read error, fix code |
| Database connection refused | `oc logs deployment/postgresql` | Check secrets match |
| Can't reach URL | `oc get route` | Wait for DNS (1-2 min) |
