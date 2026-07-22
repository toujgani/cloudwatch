<div align="center">

# Cloud AI Monitor — Local Development

### Run the Full Stack on Your Machine

</div>

---

## Quick Start (Docker Compose)

```bash
git clone https://github.com/toujgani/cloudwatch.git
cd cloudwatch
cp backend/.env.example backend/.env
docker compose up --build
```

Open: http://localhost:8080

---

## Development Mode (Hot Reload)

### Terminal 1: Database

```bash
docker compose up postgres
```

### Terminal 2: Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
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

Frontend: http://localhost:5173 (proxies API to 8080)

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `SECRET_KEY` | Yes | JWT signing key |
| `KUBE_API_URL` | No | OpenShift API (leave empty = skip) |
| `OS_AUTH_URL` | No | OpenStack API (leave empty = skip) |
| `COLLECT_INTERVAL_SECONDS` | No | Default: 30 |

When sources are not configured, the collector skips them gracefully. No errors.

---

## Useful Commands

```bash
# View logs
docker compose logs app -f

# Reset database
docker compose down -v && docker compose up --build

# Rebuild without cache
docker compose build --no-cache
```
