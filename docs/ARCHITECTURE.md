# Architecture

## System Overview

Cloud AI Monitor follows a monolithic deployment pattern (single container) with clean internal separation of concerns.

```
┌────────────────────────────────────────────────────────────────────────┐
│                          OpenShift Cluster                              │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │                  red1intheocean-dev namespace                     │  │
│  │                                                                   │  │
│  │  ┌─────────────────┐     ┌──────────────────────────────────┐   │  │
│  │  │   PostgreSQL     │     │      cloud-ai-monitor Pod        │   │  │
│  │  │   (Deployment)   │◄───►│                                  │   │  │
│  │  │   + PVC (1Gi)    │     │  FastAPI (port 8080)             │   │  │
│  │  └─────────────────┘     │  ├── /api/* → REST endpoints     │   │  │
│  │                           │  ├── /ws/live → WebSocket         │   │  │
│  │                           │  └── /* → React SPA (static)     │   │  │
│  │                           │                                  │   │  │
│  │                           │  Background Tasks:                │   │  │
│  │                           │  ├── APScheduler (collector)      │   │  │
│  │                           │  └── WS broadcast loop            │   │  │
│  │                           └──────────────────────────────────┘   │  │
│  │                                         │                         │  │
│  │                           ┌─────────────┴──────────────┐         │  │
│  │                           │        Route (TLS)          │         │  │
│  │                           │ cloud-ai-monitor-red1...    │         │  │
│  │                           └─────────────────────────────┘         │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                       │
                          External: OpenStack API
                          External: Grafana API
```

## Component Architecture

### Backend (FastAPI)

```
backend/
├── main.py              # App factory, middleware, lifespan
├── config.py            # Pydantic settings (from env vars)
├── database.py          # SQLAlchemy engine + sessions
├── models.py            # ORM: VM, Pod, Alert, AuditLog
├── collector.py         # APScheduler: periodic data collection
├── alerts.py            # Rule engine: threshold evaluation
├── ai_agent.py          # Anomaly vector + decision engine
├── remediation_agent.py # Auto-remediation with guardrails
├── audit.py             # Audit trail writer
├── websocket_manager.py # Real-time push (WS broadcast)
├── openstack_client.py  # OpenStack REST API (Keystone + Nova)
├── openshift_client.py  # Kubernetes REST API (pods, nodes, metrics)
├── grafana_client.py    # Grafana API proxy
├── email_notifications.py
└── routers/
    ├── vms.py           # /api/vms/*
    ├── pods.py          # /api/pods/*
    ├── alerts.py        # /api/alerts/*
    ├── reports.py       # /api/reports/*
    ├── observability.py # /api/observability/*
    ├── kubernetes.py    # /api/kubernetes/*
    ├── audit.py         # /api/audit/*
    └── aiops.py         # /api/aiops/*
```

### Frontend (React)

Single-page application with:
- **Routing**: React Router with role-based access control
- **State**: Local state + WebSocket real-time updates
- **API Layer**: Axios client with baseURL `/api`
- **Visualization**: Recharts for all graphs

### AI Engine

The AI Agent uses a three-pillar approach (no external LLM required):

1. **Anomaly Vector** `A = [m, l, t]`
   - `m` = metrics signal (CPU, RAM, thresholds)
   - `l` = logs signal (keyword matching, recurrence)
   - `t` = traces signal (latency, network patterns)

2. **Health Decay Model**
   ```
   H = 100 × exp(−λ × |A|²)
   ```
   Where λ varies by severity (critical=2.8, warning=1.4, info=0.5)

3. **Decision Tiers**
   - Score ≥ 78 → Escalate
   - Score ≥ 52 → Investigate
   - Score ≥ 32 → Watch
   - Score < 32 → Suppress

## Data Flow

```
                    Every 30-60s
OpenStack API  ────────────────►  Collector
OpenShift API  ────────────────►  (APScheduler)
                                      │
                                      ▼
                              ┌───────────────┐
                              │  Alert Engine  │
                              │  (threshold    │
                              │   evaluation)  │
                              └───────┬───────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │   AI Agent    │
                              │  (vector +    │
                              │   scoring)    │
                              └───────┬───────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │  Remediation  │
                              │  Agent        │
                              │  (guardrails) │
                              └───────┬───────┘
                                      │
                              ┌───────┴───────┐
                              │  PostgreSQL   │
                              └───────┬───────┘
                                      │
                               Every 3s (WS)
                                      │
                                      ▼
                              ┌───────────────┐
                              │   Frontend    │
                              │   (React)     │
                              └───────────────┘
```

## Security Decisions

1. **Authentication**: Client-side only (demo/internal tool). For production with external access, add server-side JWT middleware.
2. **Secrets**: All sensitive values in OpenShift Secrets, never in code or ConfigMaps.
3. **TLS**: OpenShift Route handles TLS termination (edge).
4. **CORS**: Restricted to known origins in production.
5. **Non-root container**: Required by OpenShift, good security practice.
6. **Remediation guardrails**: Max actions/hour, dry-run mode, safe namespace whitelist.

## Why Single Container?

| Factor | Single Container | Two Containers |
|--------|-----------------|----------------|
| Resource usage | Lower (1 pod) | Higher (2 pods) |
| Complexity | Simple | More networking |
| Scaling | Adequate for this use case | Independent scaling |
| Developer Sandbox fit | Perfect | Tight on resources |
| Debugging | One log stream | Multiple streams |

For this project's scale (< 1000 users, internal tool), single container is the right choice.
