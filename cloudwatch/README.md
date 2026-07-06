# CloudWatch — Supervision Infrastructure Cloud

Tableau de bord de supervision OpenStack & OpenShift pour Tanger Med Special Agency.

---

## Structure du projet

```
cloudwatch/
├── backend/
│   ├── main.py              ← FastAPI app + lifespan
│   ├── config.py            ← Variables d'environnement (.env)
│   ├── database.py          ← SQLAlchemy + PostgreSQL
│   ├── models.py            ← Tables: VMs, Pods, Métriques, Alertes
│   ├── collector.py         ← APScheduler — collecte toutes les 30s
│   ├── openstack_client.py  ← API REST OpenStack (Keystone + Nova)
│   ├── openshift_client.py  ← API Kubernetes / OpenShift
│   ├── alerts.py            ← Moteur de règles d'alertes
│   ├── routers/
│   │   ├── vms.py           ← GET /api/vms/
│   │   ├── pods.py          ← GET /api/pods/
│   │   └── alerts.py        ← GET /api/alerts/
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.tsx           ← Router principal
    │   ├── api/client.ts     ← Appels axios vers FastAPI
    │   ├── types/index.ts    ← Interfaces TypeScript
    │   └── components/
    │       ├── Sidebar.tsx
    │       ├── Dashboard.tsx ← Vue principale (KPIs, graphes)
    │       ├── VMsPage.tsx   ← Liste VMs + historique
    │       ├── PodsPage.tsx  ← Pods avec filtres
    │       └── AlertsPage.tsx← Alertes + résolution manuelle
    └── package.json
```

---

## Prérequis

- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Accès réseau à OpenStack et OpenShift

---

## Installation Backend

### 1. Créer la base de données PostgreSQL

```sql
CREATE USER cloudwatch WITH PASSWORD 'password';
CREATE DATABASE cloudwatch OWNER cloudwatch;
```

### 2. Configurer l'environnement

```bash
cd backend
cp .env.example .env
# Éditer .env avec vos paramètres OpenStack / OpenShift
```

Variables obligatoires à renseigner dans `.env` :

```env
DATABASE_URL=postgresql://cloudwatch:password@localhost:5432/cloudwatch

# OpenStack
OS_AUTH_URL=http://VOTRE_OPENSTACK:5000/v3
OS_USERNAME=admin
OS_PASSWORD=votre_mot_de_passe
OS_PROJECT_NAME=admin

# OpenShift
KUBE_API_URL=https://VOTRE_OPENSHIFT:6443
KUBE_TOKEN=votre_service_account_token
```

> **Obtenir le token OpenShift :**
> ```bash
> oc create serviceaccount cloudwatch -n default
> oc adm policy add-cluster-role-to-user cluster-reader -z cloudwatch -n default
> oc sa get-token cloudwatch -n default
> ```

### 3. Installer les dépendances Python

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Lancer le serveur FastAPI

```bash
# Depuis la racine du projet (pas depuis backend/)
uvicorn backend.main:app --reload --port 8000
```

L'API sera disponible sur : http://localhost:8000
Documentation Swagger : http://localhost:8000/docs

---

## Installation Frontend

```bash
cd frontend
npm install
npm run dev
```

Le dashboard sera disponible sur : http://localhost:5173

---

## Endpoints API

| Méthode | URL                          | Description                        |
|---------|------------------------------|------------------------------------|
| GET     | `/api/health`                | Santé de l'API                    |
| GET     | `/api/dashboard/stats`       | KPIs globaux (VMs, pods, alertes) |
| GET     | `/api/vms/`                  | Liste toutes les VMs              |
| GET     | `/api/vms/{id}`              | Détail d'une VM                   |
| GET     | `/api/vms/{id}/metrics`      | Historique métriques (24h)        |
| GET     | `/api/vms/summary/stats`     | Compteurs VMs                     |
| GET     | `/api/pods/`                 | Liste tous les pods               |
| GET     | `/api/pods/?namespace=prod`  | Pods filtrés par namespace        |
| GET     | `/api/pods/summary/stats`    | Compteurs pods                    |
| GET     | `/api/alerts/`               | Liste les alertes                 |
| GET     | `/api/alerts/?status=active` | Alertes actives seulement         |
| PATCH   | `/api/alerts/{id}/resolve`   | Résoudre une alerte manuellement  |

---

## Règles d'alertes configurables

Dans `.env` :

```env
ALERT_CPU_WARNING=70       # % CPU → WARNING
ALERT_CPU_CRITICAL=90      # % CPU → CRITICAL
ALERT_RAM_WARNING=75       # % RAM → WARNING
ALERT_RAM_CRITICAL=90      # % RAM → CRITICAL
```

Règles automatiques (non configurables) :
- VM en statut `ERROR` → alerte CRITICAL
- Pod en statut `Failed` ou `Unknown` → alerte CRITICAL
- Pod avec ≥ 5 redémarrages → alerte WARNING (CrashLoopBackOff)

---

## Fonctionnement du collecteur

1. Toutes les 30 secondes (configurable via `COLLECT_INTERVAL_SECONDS`)
2. Appelle OpenStack Nova API → récupère VMs + diagnostics
3. Appelle OpenShift/Kubernetes API → récupère pods + métriques
4. Persiste en base PostgreSQL (upsert)
5. Évalue les règles d'alertes → crée ou résout les alertes

---

## Technologies utilisées

| Couche       | Technologie              |
|--------------|--------------------------|
| Backend      | Python 3.11 + FastAPI    |
| Collecte     | APScheduler              |
| ORM          | SQLAlchemy 2.0           |
| Base données | PostgreSQL               |
| OpenStack    | API REST + Keystone auth |
| OpenShift    | Kubernetes Python client |
| Frontend     | React 18 + TypeScript    |
| Graphes      | Recharts                 |
| HTTP client  | Axios                    |
| Build tool   | Vite                     |

---

## Agent AIOps d'auto-remediation

L'agent analyse les alertes actives, choisit une action, construit un plan
explicable et applique l'action seulement si les garde-fous l'autorisent.

Actions supportees :

- stockage sature : extension du premier volume attache via Cinder ;
- RAM saturee : resize OpenStack selon `REMEDIATION_MEMORY_FLAVOR_MAP` ;
- VM bloquee ou en erreur : `hard_reboot`, `stop` ou `live_migrate` ;
- pod CrashLoop/restarts : suppression du pod si son namespace est autorise ;
- autres cas : recommandation operateur sans changement automatique.

Endpoints :

| Methode | URL                                  | Description                           |
|---------|--------------------------------------|---------------------------------------|
| POST    | `/api/alerts/{id}/remediate`         | Lance l'agent sur une alerte          |
| POST    | `/api/alerts/agent/remediate-active` | Lance l'agent sur les alertes actives |
| POST    | `/api/alerts/agent/reprocess`        | Recalcule les decisions IA            |

Variables principales :

```env
AUTO_REMEDIATION_ENABLED=true
AUTO_REMEDIATION_DRY_RUN=true
AUTO_REMEDIATION_MIN_SCORE=55
REMEDIATION_MAX_ACTIONS_PER_HOUR=5
REMEDIATION_STORAGE_INCREMENT_GB=20
REMEDIATION_MAX_STORAGE_GB=500
REMEDIATION_MEMORY_FLAVOR_MAP={"m1.small":"m1.medium","m1.medium":"m1.large"}
REMEDIATION_VM_RECOVERY_ACTION=hard_reboot
REMEDIATION_K8S_SAFE_NAMESPACES=default,apps
```

Pour une demo sure, garder `AUTO_REMEDIATION_DRY_RUN=true`. Pour appliquer
de vraies actions, passer a `false` apres validation des permissions OpenStack
et Kubernetes.
