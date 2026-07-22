<div align="center">

# Cloud AI Monitor — Architecture

### System Design & AI Model Documentation

</div>

---

## System Overview

Cloud AI Monitor is a **monolithic deployment** with clean internal separation of concerns. A single container serves the React frontend, FastAPI backend, AI engine, and background collectors.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                        DEPLOYMENT ARCHITECTURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────────────────────────────────────────┐
│              OpenShift Cluster (Red Hat Developer Sandbox)          │
│                                                                    │
│  ┌─────────────────┐     ┌──────────────────────────────────┐    │
│  │   PostgreSQL     │     │      cloud-ai-monitor Pod        │    │
│  │   (Deployment)   │◄───►│                                  │    │
│  │   + PVC (2Gi)    │     │  FastAPI (port 8080)             │    │
│  └─────────────────┘     │  ├── /api/* REST endpoints        │    │
│                           │  ├── /ws/live WebSocket           │    │
│                           │  └── /* React SPA (static)        │    │
│                           │                                  │    │
│                           │  Background Tasks:                │    │
│                           │  ├── APScheduler (collector 30s)  │    │
│                           │  ├── WS broadcast (3s)            │    │
│                           │  └── AI remediation engine        │    │
│                           └──────────────────────────────────┘    │
│                                         │                         │
│                           ┌─────────────┴──────────────┐         │
│                           │     Route (TLS edge)        │         │
│                           └─────────────────────────────┘         │
└────────────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
  ┌──────────────┐            ┌──────────────────┐
  │  OpenStack   │            │  External SMTP   │
  │  (Keystone,  │            │  (Gmail)         │
  │   Nova,      │            └──────────────────┘
  │   Cinder)    │
  └──────────────┘
```

---

## AI Engine — Three-Pillar AIOps Pipeline

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                      AI DECISION PIPELINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  Data Sources              AI Processing              Actions
  ──────────              ─────────────              ───────

  OpenShift API    ──┐
  (pods, metrics)    │    ┌───────────────┐
                     ├───►│ Build Vector  │
  OpenStack API    ──┤    │ A = [m, l, t] │
  (VMs, diagnostics) │    └───────┬───────┘
                     │            │
  Historical DB    ──┘            ▼
                          ┌───────────────┐
                          │ Health Decay   │     H = 100 × exp(-λ|A|²)
                          │ Score Model    │
                          └───────┬───────┘
                                  │
                                  ▼
                          ┌───────────────┐
                          │ Decision      │     score → tier
                          │ Engine        │
                          └───────┬───────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌──────────┐  ┌──────────┐  ┌──────────┐
            │ K8s PATCH│  │ OpenStack│  │  Email   │
            │ (scale)  │  │ (resize) │  │ (report) │
            └──────────┘  └──────────┘  └──────────┘
```

---

## Component Architecture

### Backend Modules

| Module | Responsibility |
|--------|---------------|
| `ai_agent.py` | Anomaly vector computation, health decay, decision engine |
| `remediation_agent.py` | Action selection, guardrails, execution, audit |
| `collector.py` | Periodic collection + database reconciliation |
| `predictions.py` | Linear regression forecasting (time-to-exhaustion) |
| `soft_quota.py` | Configurable quota thresholds (warning/critical/remediate) |
| `email_notifications.py` | SMTP incident reports with 3x retry |
| `openstack_client.py` | Keystone auth + Nova + Cinder (plug-and-play) |
| `openshift_client.py` | K8s API (list, patch, delete, scale) |
| `websocket_manager.py` | Real-time push to frontend every 3s |

### Data Flow

```
Every 30 seconds:

  Collector
     │
     ├── GET /api/v1/pods (OpenShift)
     ├── GET /compute/v2.1/servers (OpenStack)
     │
     ▼
  PostgreSQL (insert/update/DELETE stale)
     │
     ▼
  Alert Engine (threshold check)
     │
     ├── Pod Failed? → CRITICAL
     ├── Restarts >= 5? → WARNING
     ├── CPU > 90%? → CRITICAL
     ├── Quota > soft limit? → CRITICAL
     │
     ▼
  AI Agent (score + decide)
     │
     ├── Score >= threshold? → Remediation Agent
     │                            │
     │                            ├── PATCH deployment (scale CPU/RAM)
     │                            ├── DELETE pod (restart)
     │                            ├── DELETE stress-test (cleanup)
     │                            ├── Nova resize (OpenStack)
     │                            └── Cinder extend (OpenStack)
     │
     ▼
  Email Incident Report
     │
     ▼
  Audit Trail (database)
```

---

## Security Architecture

| Layer | Mechanism |
|-------|-----------|
| Authentication | JWT tokens (bcrypt password hashing) |
| Secrets | OpenShift Secrets (encrypted at rest) |
| Network | TLS edge termination (HTTPS) |
| Container | Non-root user, read-only filesystem |
| API access | Service account token (namespace-scoped) |
| AI guardrails | Max 5 actions/hour, protected resources list |
| CORS | Restricted to known origins |

### Protected Resources (Never Modified by AI)

```
cloud-ai-monitor    (the application itself)
postgresql          (the database)
```

---

## Prediction Engine

Uses linear regression on historical metrics to forecast resource exhaustion:

```
Example Output:

  Pod: cloud-ai-monitor
  Metric: RAM
  Current: 210 MB
  Trend: increasing (+5 MB/hour)
  Predicted exhaustion: 158 hours
  Confidence: 0.72
  Recommendation: No action needed

  Pod: stress-test-xyz
  Metric: CPU
  Current: 950m
  Trend: increasing (+200m/hour)
  Predicted exhaustion: 0.25 hours (15 minutes)
  Confidence: 0.89
  Recommendation: SCALE IMMEDIATELY
```

---

## Cost Model

Calculated from real collected metrics:

| Resource | Rate |
|----------|------|
| CPU | 0.045 EUR/core-hour |
| RAM | 0.006 EUR/GB-hour |
| Storage | 0.10 EUR/GB-month |
| Pod overhead | 0.003 EUR/pod-hour |
| VM base | 0.12 EUR/VM-hour |
| Incident (manual) | 180 EUR/incident |
| Downtime | 50 EUR/minute |

---

## Why Single Container?

| Factor | Single Container | Two Containers |
|--------|-----------------|----------------|
| Resource usage | Lower (1 pod) | Higher (2 pods) |
| Complexity | Simple | More networking |
| Developer Sandbox fit | Ideal | Tight on resources |
| Debugging | One log stream | Multiple streams |
| Deployment | One image, one route | Multiple services |

For an internship project on a free sandbox, single container is the correct architecture. Production would use microservices.
