# Project Progress — Cloud AI Monitor

## How We Got Here

### Week 1-2: Architecture & Development

Built the platform from scratch:
- React + TypeScript frontend with role-based UI
- FastAPI backend with APScheduler for periodic data collection
- AI Agent: anomaly vector model A=[m,l,t] + health decay formula
- Remediation Agent: automated actions with guardrails
- OpenStack integration (VM monitoring)
- OpenShift integration (Pod monitoring)
- WebSocket real-time push

### Week 3: Productionization & Deployment

**Problem:** App worked locally but needed to run on Red Hat OpenShift Developer Sandbox.

**Steps taken:**

1. **Repository Audit** — Removed dead code, mock data, duplicate files, unused dependencies
2. **Server-side Authentication** — Replaced hardcoded frontend credentials with JWT + bcrypt + PostgreSQL users
3. **Docker Multi-stage Build** — Single container serves React + FastAPI (smaller image, simpler deployment)
4. **OpenShift Manifests** — Created YAML for Deployment, Service, Route, PVC, ConfigMap, Secrets
5. **PostgreSQL on OpenShift** — Deployed with PersistentVolumeClaim (data survives pod restarts)
6. **CI/CD Pipeline** — GitHub Actions: push to main → build → push to GHCR → deploy to OpenShift
7. **Service Account Token** — Created long-lived token (expires 2057) for both CI/CD and in-app monitoring

### Key Decisions & Workarounds

| Challenge | Solution |
|-----------|----------|
| Sandbox kills pods every 12h | Deployment controller auto-recreates; UptimeRobot keeps it alive |
| `registry.redhat.io` needs pull secret | Switched to `docker.io/postgres:15-alpine` (public) |
| `passlib` + `bcrypt 5.x` incompatible | Pinned `bcrypt==4.1.3` |
| Podman caches old layers | Used `--no-cache` flag for critical rebuilds |
| Sandbox can't create RBAC roles | Service account already has `patch deployments` permission — no workaround needed |
| OpenStack unavailable in sandbox | Collector skips gracefully, focuses on OpenShift pods |
| Need AI to scale resources | Used Kubernetes PATCH API on Deployments (allowed by sandbox RBAC) |

### AI Remediation Capabilities on OpenShift Sandbox

| Detection | AI Action | How It Works Technically |
|-----------|-----------|------------------------|
| Pod crash / Failed status | Restart workload | `DELETE /api/v1/namespaces/{ns}/pods/{name}` — controller recreates |
| High memory usage | Scale memory | `PATCH /apis/apps/v1/.../deployments/{name}` — increases memory limit |
| High CPU usage | Scale CPU | `PATCH /apis/apps/v1/.../deployments/{name}` — increases CPU limit |
| Repeated restarts | Rollout restart | Patches annotation → triggers rolling update |
| Any anomaly | Audit + Email | Logs to DB + sends email notification |

### Architecture (What's Actually Running)

```
OpenShift Namespace: red1intheocean-dev
├── cloud-ai-monitor (Deployment)
│   └── Container: FastAPI + React + AI Agent + Collector
│       - Collects pod data every 60s
│       - AI scores anomalies
│       - Patches deployments when thresholds crossed
│       - Sends email alerts
│       - Serves web UI
├── postgresql (Deployment)
│   └── Container: PostgreSQL 15
│       - PVC: 2Gi (persistent across restarts)
│       - Stores: users, alerts, metrics, audit trail
├── Route: cloud-ai-monitor-red1intheocean-dev.apps.rm2.thpm.p1.openshiftapps.com
└── Service Account: cloud-ai-monitor-sa (token valid until 2057)
```

### CI/CD Flow

```
Developer pushes to main
  → GitHub Actions triggers
  → Builds Docker image (multi-stage: Node + Python)
  → Pushes to ghcr.io/red1intheocean/cloud-ai-monitor
  → Logs into OpenShift with service account token
  → Triggers rolling update
  → New pod starts with latest code
```

### Sandbox Quotas Used

| Resource | Limit | Our Usage | % Used |
|----------|-------|-----------|--------|
| Memory requests | 30Gi | 512Mi | 1.7% |
| CPU requests | 3000m | 200m | 6.7% |
| PVCs | 10 | 1 | 10% |
| Storage | 80Gi | 2Gi | 2.5% |

### Timeline

| Date | Milestone |
|------|-----------|
| Jul 8 | Sandbox namespace created |
| Jul 15 | First successful deployment |
| Jul 16 | Fixed bcrypt issue, app stable |
| Jul 17 | Enabled live AI remediation + email alerts |
| Jul 17 | Implemented Kubernetes-native scaling (patch deployments) |
| Jul 17 | CI/CD pipeline active (GitHub Actions) |

---

*CIRES Technologies — Tanger Med — July 2026*
