<div align="center">

<img src="frontend/public/cireslogo.png" alt="CIRES Technologies" width="80" />

# Cloud AI Monitor

### AI-Powered Hybrid Cloud Monitoring & Autonomous Remediation Platform

[![Internship](https://img.shields.io/badge/Project-Internship_Study-blue.svg)]()
[![Company](https://img.shields.io/badge/Company-CIRES_Technologies-orange.svg)]()
[![Platform](https://img.shields.io/badge/Platform-OpenShift_+_OpenStack-red.svg)]()
[![AI](https://img.shields.io/badge/Engine-AIOps_Autonomous-green.svg)]()
[![Date](https://img.shields.io/badge/Date-July_2026-lightgrey.svg)]()

---

*Towards an AI-Augmented Cloud Operations Platform*

*CIRES Technologies — Tanger Med*

</div>

---

## Overview

**Cloud AI Monitor** is a production-grade AIOps platform that monitors hybrid cloud infrastructure (OpenShift + OpenStack), detects anomalies using a mathematical AI model, predicts resource exhaustion, and executes autonomous remediation — all without human intervention.

> **Key Objective**: Build an autonomous platform capable of detecting, predicting, and remediating infrastructure incidents across multiple cloud providers.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Cloud AI Monitor                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    │
│   │ OpenShift│    │ OpenStack│    │  Grafana │    │  Future  │    │
│   │ Connector│    │ Connector│    │ Connector│    │  Clouds  │    │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘    └────┬─────┘    │
│        │               │               │               │          │
│        └───────────────┼───────────────┼───────────────┘          │
│                        │               │                           │
│                   ┌────▼───────────────▼────┐                      │
│                   │    Metrics Database      │                      │
│                   │      (PostgreSQL)        │                      │
│                   └────────────┬────────────┘                      │
│                                │                                    │
│                   ┌────────────▼────────────┐                      │
│                   │    AI Decision Engine    │                      │
│                   │  Anomaly Vector A=[m,l,t]│                      │
│                   │  Health Decay Model      │                      │
│                   │  Prediction Engine       │                      │
│                   └─────────┬───────────────┘                      │
│                             │                                       │
│              ┌──────────────┼──────────────┐                       │
│              │              │              │                        │
│     ┌────────▼───┐  ┌──────▼─────┐  ┌────▼────────┐              │
│     │  Dashboard │  │Remediation │  │   Email     │              │
│     │  (React)   │  │  Engine    │  │  Reports    │              │
│     └────────────┘  └────────────┘  └─────────────┘              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## AI Engine — Anomaly Detection & Autonomous Remediation

The core of the platform relies on a unified pipeline:

### 1. Ingestion Layer

Aggregates real infrastructure metrics every 30 seconds:
- CPU utilization, RAM usage, disk I/O
- Pod status, restart counts, CrashLoopBackOff detection
- Namespace-level quota monitoring

### 2. Anomaly Vector Model

Computes a three-dimensional anomaly vector:

```
A = [m, l, t]
```

Where:
- `m` = metrics signal (threshold breach severity, resource state, recurrence)
- `l` = logs signal (keyword correlation from knowledge base)
- `t` = traces signal (latency patterns, network anomalies)

### 3. Health Decay Model

Dynamic health scoring using exponential decay:

```
H = 100 × exp(-λ × |A|²)
```

Where λ is tuned per severity:
- Critical: λ = 2.8 (fast decay)
- Warning: λ = 1.4
- Info: λ = 0.5

### 4. Decision Engine

Maps the AI score to decision tiers:

| Score | Decision | Action |
|-------|----------|--------|
| >= 78 | Escalate | Immediate intervention |
| >= 52 | Investigate | Analyze and prepare |
| >= 32 | Watch | Monitor next cycle |
| < 32 | Suppress | Noise, ignore |

### 5. Autonomous Remediation

When the AI decides to act, it executes real infrastructure changes:

| Problem | Action | Target |
|---------|--------|--------|
| Namespace quota exceeded | Delete stress-test resources | OpenShift |
| Pod crashloop | Restart pod | OpenShift |
| High CPU usage | Increase CPU limits | OpenShift |
| High RAM usage | Increase memory limits | OpenShift |
| VM CPU critical | Resize flavor | OpenStack |
| VM storage full | Extend volume | OpenStack |
| VM blocked | Hard reboot / migrate | OpenStack |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite, Recharts |
| Backend | FastAPI, SQLAlchemy, APScheduler |
| Database | PostgreSQL 15 |
| AI Engine | Custom anomaly vector model (no external LLM) |
| Prediction | Linear regression on historical metrics |
| Deployment | OpenShift (Red Hat Developer Sandbox) |
| CI/CD | GitHub Actions → GHCR → OpenShift |
| Monitoring | OpenShift + OpenStack (plug-and-play) |
| Notifications | SMTP incident reports with retry |

---

## Features

| Feature | Status |
|---------|--------|
| Real-time dashboard with WebSocket | Done |
| OpenShift pod monitoring (CPU, RAM, restarts) | Done |
| OpenStack VM monitoring (plug-and-play) | Done |
| AI anomaly detection (vector model) | Done |
| Autonomous remediation (K8s PATCH API) | Done |
| Prediction engine (time-to-exhaustion) | Done |
| Soft quota system with thresholds | Done |
| Email incident reports (SMTP with retry) | Done |
| Stress test / chaos engineering | Done |
| Cost analysis from real metrics | Done |
| Dark mode | Done |
| CI/CD auto-deploy on push | Done |
| Role-based authentication (JWT) | Done |
| Audit trail | Done |
| Grafana integration (plug-and-play) | Ready |
| Multi-cloud support | Architecture ready |

---

## Quick Start

```bash
# Clone
git clone https://github.com/toujgani/cloudwatch.git
cd cloudwatch

# Local development
cp backend/.env.example backend/.env
docker compose up --build

# Open: http://localhost:8080
```

---

## Project Structure

```
cloud-ai-monitor/
├── backend/
│   ├── ai_agent.py            # Anomaly vector + decision engine
│   ├── remediation_agent.py   # Autonomous remediation with guardrails
│   ├── collector.py           # Periodic data collection + reconciliation
│   ├── predictions.py         # Linear regression forecasting
│   ├── soft_quota.py          # Configurable quota management
│   ├── email_notifications.py # SMTP incident reports
│   ├── openstack_client.py    # OpenStack Keystone + Nova + Cinder
│   ├── openshift_client.py    # Kubernetes API (pods, deployments, patch)
│   └── routers/               # FastAPI endpoints
├── frontend/
│   └── src/components/        # React dashboard pages
├── openshift/                 # Kubernetes deployment manifests
├── docs/                      # Technical documentation
├── .github/workflows/         # CI/CD pipeline
└── Dockerfile                 # Multi-stage production build
```

---

## Documentation

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design and AI model |
| [DEPLOYMENT.md](docs/DEPLOYMENT.md) | OpenShift deployment guide |
| [LOCAL_SETUP.md](docs/LOCAL_SETUP.md) | Local development setup |
| [OPENSHIFT.md](docs/OPENSHIFT.md) | OpenShift operations |
| [CI_CD.md](docs/CI_CD.md) | CI/CD pipeline |
| [PROGRESS.md](docs/PROGRESS.md) | Project timeline and decisions |

---

## Roadmap

| Status | Feature |
|--------|---------|
| Done | OpenShift monitoring |
| Done | AI remediation |
| Done | Grafana integration |
| Done | Cost analysis |
| Done | Email reports |
| Done | OpenStack connector |
| Planned | Multi-cluster federation |
| Planned | AWS CloudWatch integration |
| Planned | Azure Monitor integration |
| Planned | LLM-powered reasoning |
| Planned | Predictive auto-scaling |

---

## Authors

| Name | Role |
|------|------|
| **Redouane Meriche** | Software & Embedded Systems Engineering, INPT |
| **Farouk Toujgani** | Engineering, EMSI |

**Supervisor**: Mr. Ibrahim El Hannaoui

**Company**: CIRES Technologies — Tanger Med

**Date**: July 2026
