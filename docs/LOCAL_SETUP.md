# Local Development Setup

## Prerequisites

- **Docker** and **Docker Compose** (v2+)
- **Node.js** 18+ (for frontend development only)
- **Python** 3.11+ (for backend development only)
- **Git**

## Quick Start with Docker Compose

The fastest way to run the full stack locally:

```bash
# Clone and enter the project
git clone https://github.com/red1intheocean/cloud-ai-monitor.git
cd cloud-ai-monitor

# Copy environment template
cp backend/.env.example backend/.env

# Start everything (builds frontend + backend + PostgreSQL)
docker compose up --build
```

Open http://localhost:8080 in your browser.

## Development Mode (Hot Reload)

For active development with hot reloading on both frontend and backend:

### Terminal 1: PostgreSQL
```bash
docker compose up postgres
```

### Terminal 2: Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
uvicorn app:app --host 0.0.0.0 --port 8080 --reload
```

### Terminal 3: Frontend
```bash
cd frontend
npm install
npm run dev
```

Frontend runs on http://localhost:5173 with API calls proxied to http://localhost:8080.

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| DATABASE_URL | Yes | PostgreSQL connection string |
| SECRET_KEY | Yes | JWT signing key (any random string) |
| KUBE_API_URL | No | OpenShift API URL (leave empty for no monitoring) |
| KUBE_TOKEN | No | Service account token |
| OS_AUTH_URL | No | OpenStack Keystone URL (leave empty for no monitoring) |

When sources are not configured, the dashboard shows empty data — no errors.

## Running Without External Services

The application works fine without OpenStack or OpenShift connections:
- The collector will log "unavailable" and skip
- The dashboard will show zeros
- You can still use the AIOps simulator to inject test alerts

## Building the Production Image Locally

```bash
# Build
docker build -t cloud-ai-monitor:local .

# Run
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql://cloudwatch:localdev123@host.docker.internal:5432/cloudwatch \
  cloud-ai-monitor:local
```

## Useful Commands

```bash
# View application logs
docker compose logs app -f

# View database logs
docker compose logs postgres -f

# Reset database (delete all data)
docker compose down -v
docker compose up --build

# Run only the database
docker compose up postgres

# Rebuild without cache
docker compose build --no-cache
```
