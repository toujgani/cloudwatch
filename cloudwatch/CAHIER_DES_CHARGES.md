# Cahier des charges - CloudWatch

## 1. Presentation du projet

### 1.1 Nom du projet

CloudWatch - Plateforme de supervision d'infrastructure cloud.

### 1.2 Contexte

Les infrastructures cloud basees sur OpenStack et OpenShift contiennent plusieurs ressources critiques comme les machines virtuelles, les pods, les services applicatifs et les composants de monitoring. Leur supervision est essentielle pour detecter rapidement les incidents, suivre l'etat des ressources et ameliorer la disponibilite des services.

Le projet CloudWatch a pour objectif de fournir une application web permettant de visualiser l'etat global de l'infrastructure, de suivre les metriques importantes et de gerer les alertes operationnelles.

### 1.3 Problematique

Sans outil centralise, le suivi des VMs, pods et alertes peut devenir difficile. Les equipes techniques doivent consulter plusieurs interfaces ou commandes pour connaitre l'etat de l'infrastructure. Cela peut provoquer une perte de temps dans la detection et le traitement des incidents.

## 2. Objectifs du projet

### 2.1 Objectif principal

Developper une application web de supervision permettant de centraliser les informations OpenStack et OpenShift dans un tableau de bord clair, interactif et professionnel.

### 2.2 Objectifs specifiques

- Afficher les statistiques globales de l'infrastructure.
- Suivre les machines virtuelles OpenStack.
- Suivre les pods OpenShift/Kubernetes.
- Detecter automatiquement les alertes CPU, RAM, statut VM et statut pod.
- Permettre l'acquittement et la resolution des alertes.
- Generer des rapports operationnels.
- Exporter les donnees en CSV.
- Envoyer des notifications email lors de la creation d'alertes.
- Proposer une interface claire, blanche et professionnelle avec logo CIRES.

## 3. Perimetre du projet

### 3.1 Inclus dans le projet

- Backend API avec FastAPI.
- Frontend React avec TypeScript.
- Collecte des donnees OpenStack et OpenShift.
- Mode mock pour tester sans infrastructure reelle.
- Gestion des alertes.
- Dashboard de supervision.
- Pages VMs, pods, alertes et rapports.
- Export CSV.
- Notifications email via SMTP.

### 3.2 Non inclus dans la premiere version

- Authentification complete avec roles.
- Creation automatique de tickets incidents.
- Export PDF avance.
- Intelligence predictive avancee.
- Deploiement Docker/Kubernetes complet.

Ces elements peuvent etre ajoutes dans une version future.

## 4. Acteurs du systeme

### 4.1 Administrateur

Utilisateur responsable de la configuration de l'application et de la supervision globale.

### 4.2 Operateur

Utilisateur qui surveille les alertes, acquitte les incidents et effectue les actions de resolution.

### 4.3 Viewer

Utilisateur en lecture seule qui consulte les dashboards et rapports.

## 5. Fonctionnalites attendues

### 5.1 Dashboard principal

Le dashboard doit afficher :

- Nombre total de VMs.
- Nombre de VMs actives.
- Nombre total de pods.
- Nombre de pods running.
- Nombre de pods en erreur.
- Nombre d'alertes actives.
- Nombre d'alertes critiques.
- Graphiques de suivi CPU/RAM.
- Liste des alertes recentes.

### 5.2 Gestion des VMs

La page VMs doit permettre de :

- Afficher la liste des machines virtuelles.
- Voir le statut de chaque VM.
- Afficher les metriques CPU et RAM.
- Afficher l'historique des metriques.
- Identifier les VMs en etat critique.

### 5.3 Gestion des pods

La page Pods doit permettre de :

- Afficher les pods OpenShift/Kubernetes.
- Filtrer par namespace.
- Voir le statut des pods.
- Voir le nombre de redemarrages.
- Identifier les pods en erreur ou instables.

### 5.4 Gestion des alertes

Le systeme doit permettre de :

- Creer automatiquement des alertes selon des seuils.
- Afficher les alertes actives, resolues ou toutes les alertes.
- Acquitter une alerte.
- Ajouter un commentaire d'operateur.
- Resoudre une alerte.
- Afficher la severite : info, warning, critical.

### 5.5 Notifications email

Lorsqu'une nouvelle alerte est creee, le systeme peut envoyer un email si la configuration SMTP est activee.

L'email doit contenir :

- Titre de l'alerte.
- Severite.
- Ressource concernee.
- Valeur mesuree.
- Seuil depasse.
- Description de l'incident.
- Lien vers la page des alertes.

### 5.6 Rapports

La page Rapports doit afficher :

- Disponibilite des VMs.
- Disponibilite des pods.
- CPU moyen.
- RAM moyenne.
- Nombre d'alertes actives.
- Nombre d'alertes critiques.
- Nombre d'alertes acquittees.

### 5.7 Export CSV

L'application doit permettre d'exporter :

- Les alertes.
- Les machines virtuelles.
- Les pods.

## 6. Regles d'alertes

### 6.1 Alertes CPU

- CPU >= 70% : alerte warning.
- CPU >= 90% : alerte critical.

### 6.2 Alertes RAM

- RAM >= 75% : alerte warning.
- RAM >= 90% : alerte critical.

### 6.3 Alertes VM

- VM en statut ERROR : alerte critical.

### 6.4 Alertes pod

- Pod en statut Failed ou Unknown : alerte critical.
- Pod avec 5 redemarrages ou plus : alerte warning.

## 7. Exigences techniques

### 7.1 Backend

- Langage : Python.
- Framework : FastAPI.
- ORM : SQLAlchemy.
- Planification : APScheduler.
- Base de donnees : PostgreSQL en production, SQLite pour les tests locaux.
- Communication externe : APIs OpenStack et OpenShift/Kubernetes.

### 7.2 Frontend

- Framework : React.
- Langage : TypeScript.
- Build tool : Vite.
- Graphiques : Recharts.
- Appels API : Axios.
- Design : interface blanche, sobre et professionnelle.

### 7.3 Base de donnees

La base doit stocker :

- VMs.
- Metriques VMs.
- Pods.
- Metriques pods.
- Alertes.
- Informations d'acquittement et de resolution.

## 8. Exigences non fonctionnelles

### 8.1 Performance

L'application doit afficher rapidement les donnees principales du dashboard et limiter les appels inutiles.

### 8.2 Securite

Les informations sensibles doivent etre stockees dans `.env` et non dans le code source.

Exemples :

- Mots de passe OpenStack.
- Token OpenShift.
- Mot de passe SMTP.
- URL de base de donnees.

### 8.3 Maintenabilite

Le code doit etre organise en modules :

- `backend/routers`
- `backend/models.py`
- `backend/collector.py`
- `backend/alerts.py`
- `frontend/src/components`
- `frontend/src/api`

### 8.4 Ergonomie

L'interface doit etre simple, lisible et adaptee a une utilisation operationnelle.

## 9. Contraintes

### 9.1 Contraintes techniques

- Python 3.11 recommande.
- Node.js 18 ou plus.
- PostgreSQL pour les donnees reelles.
- Acces reseau aux APIs OpenStack et OpenShift.

### 9.2 Contraintes de configuration

Pour utiliser les donnees reelles, il faut remplir correctement le fichier `.env` et mettre :

```env
MOCK_MODE=false
```

Pour tester localement sans infrastructure reelle :

```env
MOCK_MODE=true
```

## 10. Architecture generale

```txt
Frontend React
     |
     | HTTP / Axios
     v
Backend FastAPI
     |
     | SQLAlchemy
     v
Base de donnees PostgreSQL / SQLite
     |
     +-- OpenStack API
     +-- OpenShift / Kubernetes API
     +-- SMTP Email
```

## 11. Livrables

- Code source backend.
- Code source frontend.
- Fichier `.env.example`.
- README d'installation.
- Dashboard web fonctionnel.
- API FastAPI documentee avec Swagger.
- Cahier des charges.

## 12. Planning previsionnel

| Phase | Description | Duree estimee |
|------|-------------|---------------|
| Analyse | Etude du besoin et definition des fonctionnalites | 2 jours |
| Backend | API, base de donnees, collecte, alertes | 5 jours |
| Frontend | Dashboard, pages VMs, pods, alertes | 5 jours |
| Rapports | Page rapports et exports CSV | 2 jours |
| Notifications | Envoi email des alertes | 1 jour |
| Tests | Tests fonctionnels et correction bugs | 2 jours |
| Documentation | README et cahier des charges | 1 jour |

## 13. Evolutions futures

- Authentification avec roles : Admin, Operateur, Viewer.
- Page parametres pour modifier les seuils depuis l'interface.
- Export PDF.
- Systeme de tickets incidents.
- Notifications Teams ou Slack.
- Deploiement Docker.
- Historique avance des incidents.
- Prediction simple des risques CPU/RAM.

## 14. Conclusion

CloudWatch est une application de supervision cloud permettant de centraliser le suivi des VMs, pods, metriques et alertes. Le projet apporte une valeur operationnelle en facilitant la detection des incidents, leur suivi, leur resolution et la generation de rapports. Grace a son architecture backend FastAPI et frontend React, il reste evolutif et peut etre enrichi progressivement avec des fonctionnalites de securite, de reporting et d'automatisation.
