<div align="center">

# Cloud AI Monitor — Project Progress

### Engineering Timeline & Technical Decisions

</div>

---

## Timeline

```
Week 1    Architecture & Core Development
  │
  ├── React frontend (13 pages, role-based routing)
  ├── FastAPI backend (8 routers, WebSocket)
  ├── AI Agent (anomaly vector, health decay model)
  ├── Remediation Agent (guardrails, action engine)
  │
Week 2    Integration & Monitoring
  │
  ├── OpenShift connector (pods, metrics, PATCH API)
  ├── OpenStack connector (Keystone, Nova, Cinder)
  ├── APScheduler collector (30s intervals)
  ├── Alert engine (threshold rules, auto-resolve)
  │
Week 3    Production Deployment
  │
  ├── Multi-stage Dockerfile (non-root, optimized)
  ├── OpenShift manifests (Deployment, PVC, Route)
  ├── CI/CD pipeline (GitHub Actions → GHCR → OpenShift)
  ├── Server-side JWT authentication
  ├── PostgreSQL on OpenShift with persistent storage
  │
Week 4    AIOps & Intelligence
  │
  ├── Soft quota system (configurable thresholds)
  ├── Namespace reconciliation (database sync)
  ├── Autonomous cleanup (stress-test removal)
  ├── Prediction engine (linear regression)
  ├── Cost analysis from real metrics
  ├── SMTP incident reports (retry, structured)
  ├── Chaos engineering / stress test system
  ├── Dark mode
  └── OpenStack credentials integration
```

---

## Key Technical Decisions

| Challenge | Decision | Rationale |
|-----------|----------|-----------|
| Frontend + Backend | Single container | Sandbox has limited resources |
| Authentication | Server-side JWT + bcrypt | No hardcoded credentials |
| Database | PostgreSQL with PVC | Data persists across pod restarts |
| OpenStack unreachable from cloud | Graceful skip | App works with or without OpenStack |
| Sandbox kills pods every 12h | Deployment controller recreates | UptimeRobot prevents idle timeout |
| Stale database entries | Collector reconciliation | Every cycle syncs DB with K8s reality |
| AI actions need K8s permissions | Service account with PATCH access | Confirmed: `patch deployments = yes` |
| Email delivery | SMTP with 3x retry | Never crashes app on failure |
| Secrets management | OpenShift Secrets (encrypted) | Never in git, never in ConfigMap |

---

## Sandbox Resource Usage

| Resource | Quota | Our Usage | Utilization |
|----------|-------|-----------|-------------|
| CPU requests | 3000m | ~200m | 7% |
| Memory requests | 30 Gi | ~512 Mi | 1.7% |
| PVCs | 10 | 1 | 10% |
| Storage | 80 Gi | 2 Gi | 2.5% |

---

## AI Remediation Actions (Verified Working)

| Action | Target | How |
|--------|--------|-----|
| Restart pod | OpenShift | `DELETE /api/v1/namespaces/{ns}/pods/{name}` |
| Scale CPU | OpenShift | `PATCH /apis/apps/v1/.../deployments/{name}` |
| Scale RAM | OpenShift | Same PATCH, different field |
| Cleanup namespace | OpenShift | Delete stress-test + CrashLoop pods |
| Resize VM | OpenStack | `POST /compute/v2.1/servers/{id}/action` |
| Extend volume | OpenStack | `POST /volumes/{id}/action` |
| Hard reboot VM | OpenStack | Same action endpoint |

---

## What's Plug-and-Play

| Integration | Current State | To Activate |
|-------------|---------------|-------------|
| OpenShift | Connected, live | Already working |
| OpenStack | Connector ready | Add credentials + deploy on CIRES network |
| Grafana | Connector ready | Add `GRAFANA_URL` + `GRAFANA_API_TOKEN` |
| AWS | Architecture ready | Build connector module |
| Azure | Architecture ready | Build connector module |
