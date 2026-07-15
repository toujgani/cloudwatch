# Cloud AI Monitor

**AIOps Infrastructure Supervision Platform for OpenStack & OpenShift**

A production-grade monitoring and intelligent remediation platform built for CIRES Technologies / Tanger Med. Monitors virtual machines (OpenStack) and container workloads (OpenShift/Kubernetes) with AI-powered anomaly detection and automated remediation.

## Features

- **Real-time Dashboard** — Live KPIs via WebSocket, health scoring, infrastructure overview
- **AI Decision Agent** — Anomaly vector analysis (metrics/logs/traces), dynamic health decay model
- **AIOps Remediation** — Automated incident response with guardrails and dry-run mode
- **Alert Engine** — Rule-based evaluation with auto-escalation and audit trail
- **Kubernetes Monitoring** — Node health, namespace metrics, pod lifecycle tracking
- **OpenStack Integration** — VM monitoring, diagnostics, compute management
- **Grafana Observability** — Metrics, logs, and traces visualization proxy
- **Audit Trail** — Complete operational history of all platform actions
- **Role-Based Access** — Admin, Operator, and Viewer roles

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Single Container (8080)                    │
├─────────────────────────────────────────────────────────────┤
│  React SPA (static)  ←→  FastAPI  ←→  PostgreSQL            │
│                            │                                 │
│                     ┌──────┼──────┐                          │
│                     │      │      │                          │
│               APScheduler  WS   AI Agent                     │
│               (collector) (live) (anomaly detection)         │
│                     │             │                          │
│               OpenStack    OpenShift                          │
│               (Nova API)   (K8s API)                         │
└─────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Recharts |
| Backend | FastAPI, SQLAlchemy, APScheduler |
| Database | PostgreSQL 15 |
| AI Engine | Custom anomaly vector model (no external LLM) |
| Deployment | OpenShift (Red Hat Developer Sandbox) |
| CI/CD | GitHub Actions → GHCR → OpenShift |

## Quick Start (Local Development)

```bash
# 1. Clone the repository
git clone https://github.com/red1intheocean/cloud-ai-monitor.git
cd cloud-ai-monitor

# 2. Copy environment template
cp backend/.env.example backend/.env
# Edit backend/.env with your values

# 3. Start with Docker Compose
docker compose up --build

# 4. Open browser
# http://localhost:8080
```

### Login Credentials (Demo)
| User | Password | Role |
|------|----------|------|
| admin | Admin@123 | Full access |
| operator | Operator@123 | Alert management |
| viewer | Viewer@123 | Read-only |

## Deployment to OpenShift

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for full instructions.

Quick version:
```bash
# Login to OpenShift
oc login --token=<YOUR_TOKEN> --server=<YOUR_SERVER>

# Deploy everything
./scripts/deploy.sh
```

## Project Structure

```
cloud-ai-monitor/
├── backend/                # FastAPI application
│   ├── routers/           # API route handlers
│   ├── ai_agent.py        # AI anomaly detection engine
│   ├── remediation_agent.py # Auto-remediation with guardrails
│   ├── collector.py       # APScheduler data collection
│   ├── config.py          # Pydantic settings
│   ├── database.py        # SQLAlchemy setup
│   ├── models.py          # ORM models
│   └── ...
├── frontend/              # React + TypeScript SPA
│   └── src/
│       ├── components/    # Page components
│       ├── api/           # API client
│       └── types/         # TypeScript interfaces
├── openshift/             # OpenShift/K8s manifests
│   ├── deployment.yaml    # App deployment + service + route
│   ├── postgresql.yaml    # Database deployment + PVC
│   ├── configmap.yaml     # Non-sensitive config
│   └── secrets.yaml       # Sensitive config template
├── scripts/               # Deployment automation
├── docs/                  # Documentation
├── .github/workflows/     # CI/CD pipeline
├── Dockerfile             # Multi-stage production build
├── docker-compose.yaml    # Local development stack
└── app.py                 # Application entry point
```

## Documentation

- [DEPLOYMENT.md](docs/DEPLOYMENT.md) — Full deployment guide
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — System design and decisions
- [LOCAL_SETUP.md](docs/LOCAL_SETUP.md) — Local development setup
- [OPENSHIFT.md](docs/OPENSHIFT.md) — OpenShift-specific guide
- [CI_CD.md](docs/CI_CD.md) — CI/CD pipeline documentation

## License

Internal project — CIRES Technologies / Tanger Med
