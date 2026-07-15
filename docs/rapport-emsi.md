# Rapport EMSI - Projet CloudWatch Supervision Infrastructure

## 1. Introduction

Le projet **CloudWatch Supervision Infrastructure** est une plateforme web de supervision, d'analyse et d'aide a la decision pour une infrastructure cloud basee sur **OpenStack**, **OpenShift/Kubernetes**, **Grafana**, **Prometheus**, **Loki** et potentiellement **Tempo/Jaeger** pour les traces.

L'objectif principal du projet est de fournir a une equipe NOC/SRE une interface centralisee permettant de:

- surveiller les machines virtuelles OpenStack;
- surveiller les pods, nodes, namespaces et clusters Kubernetes/OpenShift;
- detecter automatiquement les alertes de saturation ou d'erreur;
- analyser les logs, metriques et traces;
- calculer un score global de sante de l'infrastructure;
- aider a la decision avec un agent IA;
- proposer ou executer des actions de remediation automatique;
- fournir des tableaux de bord operationnels, financiers et techniques.

Ce projet se positionne comme une solution de supervision proactive: il ne se limite pas a afficher des donnees, il interprete l'etat du systeme, priorise les incidents et propose des actions correctives.

---

## 2. Objectifs du projet

Les objectifs fonctionnels du projet sont:

- centraliser la supervision OpenStack et OpenShift/Kubernetes;
- afficher l'etat des VMs, pods, nodes, namespaces et clusters;
- generer automatiquement des alertes selon des seuils CPU/RAM/statut;
- ajouter un acquittement NOC avec commentaire;
- calculer un **Health Score** global de 0 a 100;
- fournir une vue schema de l'infrastructure;
- afficher les logs applicatifs et systeme;
- connecter Grafana pour les metriques, logs et traces;
- fournir un dashboard financier avec ROI visible;
- integrer un agent IA pour filtrer, scorer et prioriser les alertes;
- preparer une couche d'auto-remediation pour corriger certains incidents.

Les objectifs techniques sont:

- utiliser une architecture frontend/backend claire;
- exposer une API REST avec FastAPI;
- stocker les donnees dans PostgreSQL;
- fournir un mode mock pour les tests sans infrastructure reelle;
- permettre l'integration avec OpenStack, Kubernetes et Grafana;
- rendre l'interface simple, moderne et exploitable par une equipe NOC.

---

## 3. Technologies utilisees

### 3.1 Backend

Le backend est developpe avec **Python** et **FastAPI**.

Technologies principales:

- **FastAPI**: framework web pour exposer les APIs REST.
- **SQLAlchemy**: ORM pour manipuler les tables de base de donnees.
- **PostgreSQL**: base de donnees cible pour stocker les VMs, pods, metriques et alertes.
- **APScheduler**: planification de la collecte periodique.
- **Requests**: appels HTTP vers OpenStack, Kubernetes et Grafana.
- **Pydantic / pydantic-settings**: validation et chargement de configuration `.env`.
- **psycopg2-binary**: driver PostgreSQL.

Fichiers backend importants:

- `cloudwatch/backend/main.py`: point d'entree FastAPI.
- `cloudwatch/backend/config.py`: configuration globale du projet.
- `cloudwatch/backend/database.py`: connexion et initialisation base de donnees.
- `cloudwatch/backend/models.py`: modeles SQLAlchemy.
- `cloudwatch/backend/collector.py`: collecte periodique OpenStack/OpenShift.
- `cloudwatch/backend/alerts.py`: moteur de detection des alertes.
- `cloudwatch/backend/ai_agent.py`: agent IA de scoring et decision.
- `cloudwatch/backend/remediation_agent.py`: agent de remediation rapide.
- `cloudwatch/backend/grafana_client.py`: client API Grafana.
- `cloudwatch/backend/routers/`: routes API par domaine.

### 3.2 Frontend

Le frontend est developpe avec **React**, **TypeScript** et **Vite**.

Technologies principales:

- **React**: construction de l'interface utilisateur.
- **TypeScript**: typage strict des composants et donnees.
- **Vite**: serveur de developpement et build frontend.
- **Axios**: appels HTTP vers le backend.
- **React Router DOM**: navigation entre les pages.
- **Recharts**: graphiques et visualisations.
- **CSS custom properties**: theme graphique unifie.

Fichiers frontend importants:

- `cloudwatch/frontend/src/App.tsx`: routes principales.
- `cloudwatch/frontend/src/api/client.ts`: client API frontend.
- `cloudwatch/frontend/src/types/index.ts`: types TypeScript.
- `cloudwatch/frontend/src/components/Dashboard.tsx`: dashboard principal.
- `cloudwatch/frontend/src/components/AlertsPage.tsx`: gestion des alertes.
- `cloudwatch/frontend/src/components/LogsPage.tsx`: page logs.
- `cloudwatch/frontend/src/components/KubernetesPage.tsx`: dashboard Kubernetes.
- `cloudwatch/frontend/src/components/InfrastructureMapPage.tsx`: schema global infrastructure.
- `cloudwatch/frontend/src/components/ReportsPage.tsx`: rapports et ROI.

### 3.3 Services externes integres

Le projet est prevu pour se connecter a:

- **OpenStack Nova** pour les VMs et diagnostics;
- **OpenStack Cinder** dans une evolution future pour les volumes;
- **Kubernetes/OpenShift API** pour pods, nodes, namespaces et deployments;
- **Grafana API** pour interroger les datasources;
- **Prometheus** pour les metriques;
- **Loki** pour les logs;
- **Tempo/Jaeger** pour les traces;
- **SMTP** pour les notifications email.

---

## 4. Architecture generale

Le projet suit une architecture en trois couches:

1. **Frontend React**
   - Affichage des dashboards.
   - Navigation entre pages.
   - Visualisation des alertes, logs, VMs, pods, clusters.

2. **Backend FastAPI**
   - Exposition des endpoints REST.
   - Collecte des donnees.
   - Analyse des alertes.
   - Agents IA et remediation.
   - Connexion a OpenStack, Kubernetes et Grafana.

3. **Infrastructure externe**
   - OpenStack.
   - Kubernetes/OpenShift.
   - Grafana/Prometheus/Loki/Tempo.
   - PostgreSQL.

### Diagramme d'architecture

```mermaid
flowchart LR
    U[Utilisateur NOC / Admin] --> F[Frontend React + Vite]
    F --> API[Backend FastAPI]

    API --> DB[(PostgreSQL)]
    API --> OS[OpenStack API]
    API --> K8S[Kubernetes / OpenShift API]
    API --> G[Grafana API]

    G --> P[Prometheus Metrics]
    G --> L[Loki Logs]
    G --> T[Tempo / Jaeger Traces]

    API --> AI[Agent IA Decision]
    AI --> R[Agent Remediation]
    R --> OS
    R --> K8S
```

---

## 5. Fonctionnalites detaillees

## 5.1 Dashboard principal

Le dashboard principal donne une vue rapide de l'etat global de l'infrastructure.

Il affiche:

- nombre total de VMs;
- nombre de VMs actives;
- nombre de pods;
- nombre de pods running;
- alertes actives;
- alertes critiques;
- Health Score global;
- historique CPU;
- etat des pods;
- top VMs par consommation CPU;
- alertes actives recentes.

Le **Health Score** est un score de 0 a 100 qui resume l'etat global de l'infrastructure. Il prend en compte:

- disponibilite des VMs;
- disponibilite des pods;
- nombre d'alertes actives;
- nombre d'alertes critiques.

Plus le score est faible, plus l'infrastructure est degradee.

---

## 5.2 Gestion des machines virtuelles

La page VMs permet de visualiser les machines virtuelles OpenStack.

Informations affichees:

- identifiant VM;
- nom;
- statut;
- flavor;
- host compute;
- CPU;
- RAM;
- RAM utilisee;
- date de mise a jour.

Le backend recupere ces informations depuis:

- OpenStack Nova;
- diagnostics serveur;
- mode mock si l'infrastructure reelle n'est pas disponible.

Les metriques suivies sont:

- `cpu_percent`;
- `ram_percent`;
- `ram_used_mb`;
- `ram_total_mb`;
- `disk_read_mb`;
- `disk_write_mb`.

---

## 5.3 Gestion des pods OpenShift/Kubernetes

La page Pods permet de visualiser les workloads Kubernetes/OpenShift.

Informations affichees:

- nom du pod;
- namespace;
- statut;
- node;
- image;
- nombre de redemarrages;
- CPU en millicores;
- RAM en MB.

Le systeme detecte automatiquement:

- pods en `Failed`;
- pods en `Unknown`;
- pods avec redemarrages repetes;
- pods en attente.

Ces informations sont importantes pour identifier les problemes applicatifs dans un cluster Kubernetes.

---

## 5.4 Gestion Kubernetes / Clusters

Une page dediee Kubernetes a ete ajoutee pour rendre le projet plus professionnel.

Elle affiche:

- nom du cluster;
- fournisseur: Kubernetes/OpenShift;
- mode: mock ou reel;
- Health Score cluster;
- nombre de nodes;
- nodes Ready / NotReady;
- CPU total du cluster;
- RAM totale;
- slots pods;
- occupation des pods;
- CPU moyen;
- memoire moyenne;
- pression disque;
- pression memoire;
- nodes satures;
- namespaces;
- redemarrages containers.

### Mesures de pilotage

La page affiche des taux de mesure:

- disponibilite des nodes;
- CPU cluster moyen;
- memoire cluster moyenne;
- occupation des slots pods;
- namespaces en erreur;
- redemarrages containers.

Ces mesures permettent a l'equipe NOC de savoir si le cluster est stable ou s'il approche d'un etat critique.

---

## 5.5 Gestion des alertes

Le moteur d'alertes detecte automatiquement les problemes suivants:

- CPU VM warning;
- CPU VM critical;
- RAM VM warning;
- RAM VM critical;
- VM en statut ERROR;
- Pod en Failed;
- Pod en Unknown;
- Pod avec trop de redemarrages.

Chaque alerte contient:

- severite;
- statut;
- titre;
- description;
- regle declenchee;
- valeur mesuree;
- seuil;
- ressource concernee;
- date de declenchement;
- date de resolution;
- acquittement NOC;
- commentaire operateur;
- decision IA;
- remediation proposee ou executee.

### Acquittement NOC

Un operateur peut acquitter une alerte avec:

- son nom;
- un commentaire;
- la date d'acquittement.

Cela permet de tracer les actions humaines.

---

## 5.6 Agent IA de decision

Le fichier `ai_agent.py` implemente un agent IA deterministe et explicable.

Son role est de:

- analyser chaque alerte;
- calculer un score de gravite;
- classer l'alerte;
- proposer une decision;
- fournir une recommandation;
- calculer un niveau de confiance.

### Decisions possibles

L'agent peut produire:

- `escalate`: incident critique a escalader;
- `investigate`: investigation necessaire;
- `watch`: surveillance;
- `suppress`: bruit probable.

### Exemple

Si une VM depasse 90% CPU:

- severite: critical;
- score augmente fortement;
- categorie: compute;
- decision: escalate;
- recommandation: intervention rapide et escalation si le service est impacte.

### Fonctionnement interne

L'agent utilise plusieurs criteres:

- severite de l'alerte;
- depassement du seuil;
- type de regle;
- ressource concernee;
- recurrence d'alertes similaires;
- statut acquitte ou non.

```mermaid
flowchart TD
    A[Alerte detectee] --> B[Analyse severite]
    B --> C[Analyse seuil et metrique]
    C --> D[Analyse type ressource]
    D --> E[Recherche recurrence]
    E --> F[Calcul score IA]
    F --> G{Score}
    G -->|>= 80| H[Escalate]
    G -->|55-79| I[Investigate]
    G -->|35-54| J[Watch]
    G -->|< 35| K[Suppress]
```

---

## 5.7 Agent de remediation

Le fichier `remediation_agent.py` gere les actions correctives.

Son role est de choisir une action adaptee a l'alerte.

Actions possibles:

- `extend_storage`: ajouter du stockage;
- `scale_memory`: augmenter la memoire;
- `scale_compute`: augmenter CPU/vCPU;
- `restart_workload`: redemarrer un workload;
- `isolate_workload`: isoler un workload;
- `quarantine_vm`: quarantainer ou stopper une VM;
- `open_incident`: ouvrir un incident.

### Comportement actuel

Le systeme sait deja:

- proposer automatiquement une action;
- executer en mode mock;
- supprimer un pod pour provoquer son redemarrage par Kubernetes;
- stopper une VM OpenStack dans un cas de quarantaine.

Pour les actions avancees comme resize VM, extension volume ou migration, il faut encore ajouter:

- flavor cible;
- volume ID;
- policy de migration;
- verification de quotas;
- confirmation resize.

### Diagramme de remediation

```mermaid
flowchart TD
    A[Alerte critique] --> B[Agent IA score l'alerte]
    B --> C{Auto remediation active?}
    C -->|Non| D[Action recommandee seulement]
    C -->|Oui| E{Dry run?}
    E -->|Oui| F[Simulation et journalisation]
    E -->|Non| G{Action supportee?}
    G -->|Oui| H[Execution reelle]
    G -->|Non| I[Action bloquee proprement]
    H --> J[Acquittement automatique]
    I --> K[Escalation NOC]
```

---

## 5.8 Page Logs dediee

Une page Logs dediee a ete ajoutee.

Elle permet de:

- rechercher dans les logs;
- filtrer par niveau;
- filtrer par service, VM ou pod;
- choisir une periode;
- afficher les erreurs;
- afficher les warnings;
- identifier les services impactes;
- comprendre la cause d'une alerte.

### Role des logs

Les metriques disent qu'il y a un probleme.

Les logs expliquent pourquoi le probleme existe.

Exemple:

- metrique: CPU VM a 95%;
- log: requetes lentes vers `auth-service`;
- log: timeout upstream;
- conclusion: surcharge applicative ou dependance lente.

### Sources

La page utilise:

- Grafana/Loki si configure;
- logs mock de demonstration si Grafana n'est pas configure.

---

## 5.9 Vue globale de l'infrastructure

La page `Vue infrastructure` affiche un schema visuel de l'infrastructure.

Elle montre:

- couche utilisateurs;
- couche OpenStack;
- couche Kubernetes;
- couche Observability;
- couche NOC et AI Agent.

Les composants sont colores selon leur etat:

- vert: sain;
- jaune: warning;
- rouge: critique;
- gris: offline.

Le panneau lateral liste les composants endommages:

- VM avec host compute;
- Pod avec namespace et node;
- Node avec role et pression;
- niveau de criticite;
- metrique associee.

Cette page sert a localiser rapidement ou se trouve un incident.

---

## 5.10 Dashboard financier

La page Rapports contient une partie financiere.

Elle affiche:

- cout mensuel infrastructure;
- taux d'economie grace a l'automatisation;
- economie estimee;
- ROI;
- alertes resolues.

Cette partie permet de montrer la valeur business de la supervision:

- moins de temps perdu;
- moins d'incidents longs;
- meilleure disponibilite;
- ROI visible.

---

## 5.11 Rapports et exports

Le projet permet d'exporter:

- alertes;
- VMs;
- pods.

Les exports sont au format CSV.

Cela permet:

- reporting;
- audit;
- analyse externe;
- archivage;
- partage avec les equipes.

---

## 6. Modeles de donnees

### 6.1 VirtualMachine

Stocke:

- ID;
- nom;
- statut;
- flavor;
- host;
- tenant;
- date creation;
- date mise a jour.

### 6.2 VMMetric

Stocke:

- CPU;
- RAM;
- RAM utilisee;
- RAM totale;
- disque lu;
- disque ecrit;
- date de collecte.

### 6.3 Pod

Stocke:

- ID namespace/name;
- nom;
- namespace;
- statut;
- node;
- redemarrages;
- image.

### 6.4 PodMetric

Stocke:

- CPU millicores;
- RAM MB;
- redemarrages;
- date collecte.

### 6.5 Alert

Stocke:

- severite;
- statut;
- titre;
- description;
- regle;
- valeur;
- seuil;
- acquittement;
- commentaire;
- IA score;
- IA decision;
- IA recommandation;
- remediation;
- VM associee;
- pod associe;
- date declenchement;
- date resolution.

---

## 7. Diagrammes UML

### 7.1 Diagramme de cas d'utilisation

```mermaid
flowchart LR
    NOC[Operateur NOC]
    ADMIN[Administrateur]
    AI[Agent IA]

    NOC --> UC1[Consulter dashboard]
    NOC --> UC2[Consulter alertes]
    NOC --> UC3[Acquitter alerte]
    NOC --> UC4[Analyser logs]
    NOC --> UC5[Consulter schema infrastructure]
    NOC --> UC6[Exporter rapports]

    ADMIN --> UC7[Configurer OpenStack]
    ADMIN --> UC8[Configurer Kubernetes]
    ADMIN --> UC9[Configurer Grafana]
    ADMIN --> UC10[Activer remediation]

    AI --> UC11[Scorer alerte]
    AI --> UC12[Recommander action]
    AI --> UC13[Executer remediation]
```

### 7.2 Diagramme d'etats d'une alerte

```mermaid
stateDiagram-v2
    [*] --> Active
    Active --> Acknowledged: Acquittement NOC
    Active --> RemediationRecommended: Agent IA propose action
    RemediationRecommended --> RemediationDryRun: Simulation
    RemediationRecommended --> RemediationApplied: Execution reelle
    RemediationRecommended --> RemediationBlocked: Action non supportee
    Acknowledged --> Resolved: Resolution manuelle
    RemediationApplied --> Resolved: Probleme corrige
    RemediationBlocked --> Escalated: Escalade N2/N3
    Escalated --> Resolved: Correction humaine
    Resolved --> [*]
```

### 7.3 Sequence de detection d'incident

```mermaid
sequenceDiagram
    participant Scheduler
    participant Collector
    participant OpenStack
    participant Kubernetes
    participant DB
    participant AlertEngine
    participant AIAgent
    participant UI

    Scheduler->>Collector: Declenche collecte
    Collector->>OpenStack: Lire VMs et diagnostics
    Collector->>Kubernetes: Lire pods/nodes/metriques
    Collector->>DB: Enregistrer metriques
    Collector->>AlertEngine: Evaluer seuils
    AlertEngine->>DB: Creer alerte
    AlertEngine->>AIAgent: Analyser alerte
    AIAgent->>DB: Enregistrer score et decision
    UI->>DB: Afficher alerte et recommandation
```

### 7.4 Flux logs et diagnostic

```mermaid
flowchart TD
    A[Alerte detectee] --> B[Operateur ouvre page Logs]
    B --> C[Filtre par VM / Pod / Service]
    C --> D[Lecture erreurs et warnings]
    D --> E[Identification cause probable]
    E --> F[Decision remediation]
    F --> G[Action IA ou NOC]
```

---

## 8. Configuration du projet

Le fichier principal de configuration est:

`cloudwatch/backend/.env`

Variables importantes:

```env
DATABASE_URL=postgresql://cloudwatch:1289@localhost:5432/cloudwatch
MOCK_MODE=false

OS_AUTH_URL=http://openstack:5000/v3
OS_USERNAME=admin
OS_PASSWORD=password
OS_PROJECT_NAME=admin

KUBE_API_URL=https://openshift-api:6443
KUBE_TOKEN=token
KUBE_VERIFY_SSL=false

GRAFANA_URL=http://grafana:3000
GRAFANA_API_TOKEN=token
GRAFANA_METRICS_DATASOURCE_UID=prometheus_uid
GRAFANA_LOGS_DATASOURCE_UID=loki_uid
GRAFANA_TRACES_DATASOURCE_UID=tempo_uid

AUTO_REMEDIATION_ENABLED=true
AUTO_REMEDIATION_DRY_RUN=true
AUTO_REMEDIATION_MIN_SCORE=55
```

Pour utiliser de vraies valeurs:

- `MOCK_MODE=false`;
- PostgreSQL doit fonctionner;
- OpenStack doit etre accessible;
- Kubernetes API doit etre accessible;
- Grafana doit avoir un token et des datasources valides.

---

## 9. Fonctionnement global

1. Le backend demarre.
2. La base de donnees est initialisee.
3. Le scheduler APScheduler demarre.
4. Le collecteur recupere les donnees OpenStack et Kubernetes.
5. Les metriques sont stockees.
6. Le moteur d'alertes compare les valeurs aux seuils.
7. Une alerte est creee si un seuil est depasse.
8. L'agent IA analyse l'alerte.
9. L'agent de remediation propose ou execute une action.
10. Le frontend affiche les dashboards.
11. L'operateur NOC peut analyser, acquitter, resoudre ou exporter.

---

## 10. Avantages du projet

Les avantages principaux sont:

- centralisation de la supervision;
- interface moderne;
- integration OpenStack et Kubernetes;
- gestion des alertes;
- agent IA explicable;
- remediation automatique preparee;
- logs dedies;
- schema infrastructure;
- rapports CSV;
- ROI visible;
- mode mock pour demonstration;
- architecture extensible.

Le projet est interessant car il combine:

- monitoring;
- observability;
- IA decisionnelle;
- remediation;
- reporting;
- supervision multi-cloud/private cloud.

---

## 11. Limites actuelles

Certaines fonctions sont preparees mais pas encore totalement implementees en production.

Limites:

- resize VM OpenStack non complet;
- extension volume Cinder non complete;
- migration VM non complete;
- scaling deployment Kubernetes non complet;
- authentification utilisateur non encore ajoutee;
- RBAC non encore ajoute;
- historique complet des incidents a renforcer;
- mapping applicatif metier a enrichir;
- parser complet des logs Grafana/Loki a ameliorer;
- traces distribuees encore peu visualisees cote frontend.

Ces limites sont normales pour une premiere version. Elles peuvent devenir des evolutions futures.

---

## 12. Evolutions futures proposees

### 12.1 Runbooks automatiques

Ajouter des procedures automatiques par type d'alerte:

- CPU sature;
- RAM saturee;
- disque plein;
- pod CrashLoopBackOff;
- node NotReady;
- API lente.

### 12.2 Incident Timeline

Ajouter une timeline:

- detection;
- alerte;
- decision IA;
- logs associes;
- action;
- resolution.

### 12.3 Authentification et RBAC

Ajouter:

- login;
- roles Admin, NOC, Viewer;
- permissions sur remediation;
- audit utilisateur.

### 12.4 Auto-remediation avancee

Ajouter:

- resize OpenStack;
- extend Cinder volume;
- live migration;
- scale Kubernetes deployment;
- cordon/drain node;
- rollback si echec.

### 12.5 Prediction de saturation

Ajouter un module predictif:

- disque plein dans X heures;
- RAM critique dans X minutes;
- CPU anormal;
- prevision capacite cluster.

### 12.6 Notifications avancees

Ajouter:

- Slack;
- Microsoft Teams;
- webhook;
- SMS;
- creation ticket ServiceNow/Jira.

### 12.7 Cartographie applicative

Ajouter une topologie metier:

- frontend;
- API;
- base de donnees;
- cache;
- file de messages;
- stockage.

Cela permettrait de savoir quel service metier est impacte par une panne infrastructure.

---

## 13. Conclusion

Le projet CloudWatch Supervision Infrastructure est une solution complete de supervision moderne. Il couvre plusieurs dimensions importantes d'une infrastructure professionnelle:

- supervision compute;
- supervision Kubernetes;
- gestion d'alertes;
- logs;
- metriques;
- traces;
- agent IA;
- remediation;
- rapports;
- ROI;
- schema infrastructure.

Sa force principale est de ne pas se limiter a afficher des metriques. Le systeme interprete les alertes, calcule un score de sante, propose des actions et aide le NOC a prendre une decision plus rapidement.

Avec les evolutions proposees, le projet peut devenir une plateforme AIOps plus avancee, capable de detecter, diagnostiquer et corriger automatiquement certains incidents d'infrastructure.

