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

---

## Agents IA et agents automatiques inclus dans le projet

Le projet contient deux agents IA principaux et deux composants automatiques
qui alimentent ces agents. Le flux global est :

```text
Collector
  -> moteur d'alertes
  -> Agent IA de decision NOC
  -> Agent AIOps d'auto-remediation
  -> API + dashboard
```

### 1. Agent IA de decision NOC

Fichier : `backend/ai_agent.py`

Role :

- analyser chaque alerte creee par le moteur d'alertes ;
- calculer un score d'impact entre `0` et `100` ;
- classer l'alerte dans une categorie comme `compute`, `container` ou `infrastructure` ;
- donner une decision operationnelle : `escalate`, `investigate`, `watch` ou `suppress` ;
- produire une recommandation lisible pour l'operateur NOC ;
- enregistrer la confiance de l'analyse.

Fonctionnement detaille :

1. La fonction `analyze_alert(db, alert)` recoit une alerte.
2. Elle demarre avec un score de base de `20`.
3. Elle augmente le score selon la severite :
   - `critical` ajoute `45` points ;
   - `warning` ajoute `25` points ;
   - `info` ajoute `8` points.
4. Elle compare la valeur mesuree au seuil :
   - si la valeur depasse fortement le seuil, le score augmente ;
   - si elle depasse simplement le seuil, le score augmente moins.
5. Elle regarde le nom de la regle :
   - `vm.*` classe l'alerte en `compute` ;
   - `pod.*` classe l'alerte en `container` ;
   - une regle contenant `status` ajoute un risque d'etat anormal ;
   - une regle contenant `restarts` ajoute un risque de redemarrages repetes.
6. Elle verifie la ressource liee :
   - si la VM est en `ERROR`, le score augmente ;
   - si le pod est `Failed` ou `Unknown`, le score augmente.
7. Elle detecte les alertes repetees sur la derniere heure.
8. Elle reduit legerement le score si l'alerte est deja acquittee.
9. Elle limite le score final entre `0` et `100`.
10. Elle transforme le score en decision :
    - `>= 80` : `escalate` ;
    - `>= 55` : `investigate` ;
    - `>= 35` : `watch` ;
    - `< 35` : `suppress`.
11. La fonction `apply_decision(db, alert)` sauvegarde le resultat dans l'alerte :
    `ai_score`, `ai_decision`, `ai_category`, `ai_reason`,
    `ai_recommendation`, `ai_confidence`, `ai_updated_at`.

Exemple :

```text
Alerte: RAM critique sur VM app-01
Severite: critical
Valeur: 94 %
Seuil: 90 %

Resultat agent NOC:
score = 80+
decision = escalate
categorie = compute
recommandation = intervention rapide controlee
```

### 2. Agent AIOps d'auto-remediation

Fichier : `backend/remediation_agent.py`

Role :

- choisir automatiquement une action corrective ;
- construire un plan d'intervention explicable ;
- verifier les garde-fous avant execution ;
- simuler l'action en mode `dry-run` ;
- appliquer l'action reelle seulement si la configuration l'autorise ;
- garder une trace dans l'alerte : action, statut, message et date.

Fonctionnement detaille :

1. `execute_remediation(db, alert, operator, force)` est le point d'entree principal.
2. L'agent appelle d'abord `apply_decision()` pour recalculer l'analyse IA NOC.
3. `choose_action(alert)` choisit l'action selon le texte, la regle et la ressource :
   - disque, stockage, storage, espace -> `extend_storage` ;
   - RAM, memory, memoire -> `scale_memory` ;
   - CPU -> `scale_compute` ;
   - VM bloquee ou statut VM anormal -> `recover_vm` ;
   - pod en redemarrages repetes -> `restart_workload` ;
   - pod avec statut anormal -> `isolate_workload` ;
   - cas inconnu -> `open_incident`.
4. `build_plan(db, alert)` cree un plan avec :
   - l'action cible ;
   - la ressource concernee ;
   - le niveau de risque : `low`, `medium`, `high` ;
   - la raison ;
   - les etapes d'execution ;
   - l'impact estime ;
   - si une validation humaine est requise.
5. `_guardrails_allow(db, action)` bloque les boucles dangereuses :
   - l'agent compte les actions similaires executees sur la derniere heure ;
   - si le nombre depasse `REMEDIATION_MAX_ACTIONS_PER_HOUR`, l'action est bloquee.
6. L'action est autorisee seulement si :
   - l'alerte est active ;
   - les garde-fous sont OK ;
   - `AUTO_REMEDIATION_ENABLED=true` ;
   - le score IA est superieur ou egal a `AUTO_REMEDIATION_MIN_SCORE` ;
   - l'action ne demande pas de validation humaine ;
   - ou bien `force=true` est envoye par l'operateur.
7. Si `AUTO_REMEDIATION_DRY_RUN=true`, l'agent ne modifie pas l'infrastructure :
   il ecrit seulement le plan dans l'alerte avec le statut `dry_run`.
8. Si `AUTO_REMEDIATION_DRY_RUN=false`, `_run_real_action()` execute l'action reelle.

Actions reelles supportees :

| Action | Cas traite | Execution |
|--------|------------|-----------|
| `extend_storage` | stockage sature | trouve le premier volume attache, calcule la nouvelle taille, verifie `REMEDIATION_MAX_STORAGE_GB`, appelle Cinder `extend_volume` |
| `scale_memory` | RAM saturee | lit le flavor actuel, cherche le flavor cible dans `REMEDIATION_MEMORY_FLAVOR_MAP`, lance un resize Nova |
| `recover_vm` | VM bloquee ou en erreur | applique `hard_reboot`, `stop` ou `live_migrate` selon `REMEDIATION_VM_RECOVERY_ACTION` |
| `restart_workload` | pod instable | verifie que le namespace est autorise, supprime le pod pour que Kubernetes le recree |
| `quarantine_vm` | incident critique | stoppe la VM via OpenStack |
| `open_incident` | cas non automatise | recommande une intervention humaine |

Statuts possibles :

| Statut | Signification |
|--------|---------------|
| `recommended` | action conseillee mais non executee |
| `dry_run` | simulation executee, aucun changement reel |
| `applied_mock` | action simulee en mode mock |
| `applied` | action reelle executee |
| `blocked` | action refusee par manque de donnees, configuration ou garde-fou |

Exemple stockage :

```text
Alerte: stockage critique sur VM app-01
Action choisie: extend_storage
Plan:
1. verifier que l'alerte est active
2. identifier le volume attache
3. ajouter REMEDIATION_STORAGE_INCREMENT_GB
4. verifier la limite REMEDIATION_MAX_STORAGE_GB
5. executer l'extension Cinder
```

### 3. Agent collecteur d'infrastructure

Fichier : `backend/collector.py`

Ce composant n'est pas un agent IA, mais il alimente les agents IA avec les
donnees d'infrastructure.

Role :

- collecter les VMs OpenStack ;
- collecter les pods OpenShift/Kubernetes ;
- recuperer les metriques CPU, RAM, disque et redemarrages ;
- enregistrer les ressources et metriques en base ;
- declencher l'evaluation des alertes.

Fonctionnement :

1. `start_scheduler()` lance APScheduler.
2. Toutes les `COLLECT_INTERVAL_SECONDS`, la fonction `collect_all()` demarre.
3. `collect_openstack(db)` recupere les VMs :
   - en mode mock : utilise `mock_data.get_mock_vms()` ;
   - en mode reel : appelle OpenStack via `openstack_client.list_servers()`.
4. Pour chaque VM, le collecteur :
   - met a jour la table `virtual_machines` ;
   - ajoute une ligne dans `vm_metrics` ;
   - appelle `alert_engine.evaluate_vm()`.
5. `collect_openshift(db)` recupere les pods :
   - en mode mock : utilise `mock_data.get_mock_pods()` ;
   - en mode reel : appelle Kubernetes/OpenShift.
6. Pour chaque pod, le collecteur :
   - met a jour la table `pods` ;
   - ajoute une ligne dans `pod_metrics` ;
   - appelle `alert_engine.evaluate_pod()`.

### 4. Moteur d'alertes intelligent

Fichier : `backend/alerts.py`

Ce composant n'est pas un LLM, mais il connecte la supervision avec les agents IA.

Role :

- transformer les metriques en alertes ;
- eviter les doublons d'alertes actives ;
- resoudre automatiquement les alertes quand la metrique revient a la normale ;
- appeler l'agent IA NOC ;
- appeler l'agent AIOps si necessaire ;
- envoyer une notification email si configure.

Fonctionnement :

1. `evaluate_vm(db, vm, cpu, ram)` verifie les seuils VM :
   - CPU warning ;
   - CPU critical ;
   - RAM warning ;
   - RAM critical ;
   - VM en statut `ERROR`.
2. `evaluate_pod(db, pod, restart_count)` verifie les seuils pods :
   - pod `Failed` ou `Unknown` ;
   - redemarrages superieurs ou egaux a `5`.
3. Quand une condition est vraie, `_create_alert()` cree une alerte active.
4. Avant creation, `_find_active()` verifie qu'une alerte identique n'existe pas deja.
5. Apres creation, le moteur appelle :
   - `apply_decision(db, alert)` pour l'analyse IA ;
   - `auto_remediate_if_needed(db, alert)` pour l'auto-remediation ;
   - `send_alert_email(alert)` pour notifier.
6. Quand la condition n'est plus vraie, `_resolve_alert()` passe l'alerte en `resolved`.

### Resume du fonctionnement global

```text
1. Le collecteur lit OpenStack et OpenShift.
2. Les metriques sont stockees en base.
3. Le moteur d'alertes detecte CPU/RAM/VM/pod anormal.
4. L'agent IA NOC calcule le score et la decision.
5. L'agent AIOps choisit une action corrective.
6. Les garde-fous verifient le risque.
7. En dry-run, l'agent simule.
8. En mode reel, il execute via OpenStack ou Kubernetes.
9. Le dashboard affiche le score IA, la recommandation et le statut de remediation.
```
