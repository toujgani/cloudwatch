"""
Mode Mock — génère des données réalistes sans OpenStack/OpenShift.
Activé via MOCK_MODE=true dans le .env
"""
import random
from datetime import datetime

# ─── VMs fictives ─────────────────────────────────────────────────────────────

_VMS = [
    {"id": "vm-001", "name": "vm-prod-web-01",  "flavor": "m1.large",  "host": "compute-01", "status": "ACTIVE"},
    {"id": "vm-002", "name": "vm-prod-web-02",  "flavor": "m1.large",  "host": "compute-01", "status": "ACTIVE"},
    {"id": "vm-003", "name": "vm-prod-api-01",  "flavor": "m1.xlarge", "host": "compute-02", "status": "ACTIVE"},
    {"id": "vm-004", "name": "vm-prod-api-02",  "flavor": "m1.xlarge", "host": "compute-02", "status": "ACTIVE"},
    {"id": "vm-005", "name": "vm-db-primary",   "flavor": "m1.xxlarge","host": "compute-03", "status": "ACTIVE"},
    {"id": "vm-006", "name": "vm-db-replica",   "flavor": "m1.xxlarge","host": "compute-03", "status": "ACTIVE"},
    {"id": "vm-007", "name": "vm-stg-web-01",   "flavor": "m1.medium", "host": "compute-04", "status": "ACTIVE"},
    {"id": "vm-008", "name": "vm-stg-api-01",   "flavor": "m1.medium", "host": "compute-04", "status": "SHUTOFF"},
    {"id": "vm-009", "name": "vm-monitoring",   "flavor": "m1.small",  "host": "compute-01", "status": "ACTIVE"},
    {"id": "vm-010", "name": "vm-backup-01",    "flavor": "m1.large",  "host": "compute-05", "status": "ACTIVE"},
]

# Valeurs de base CPU/RAM par VM — évolueront légèrement à chaque collecte
_vm_state: dict[str, dict] = {
    vm["id"]: {
        "cpu": random.uniform(20, 60),
        "ram": random.uniform(30, 70),
    }
    for vm in _VMS
}

# vm-003 démarre toujours haut pour déclencher des alertes
_vm_state["vm-003"]["cpu"] = 88.0
_vm_state["vm-005"]["ram"] = 82.0


def get_mock_vms() -> list[dict]:
    """Retourne la liste des VMs avec métriques légèrement aléatoires."""
    result = []
    for vm in _VMS:
        state = _vm_state[vm["id"]]

        if vm["status"] == "SHUTOFF":
            cpu, ram = 0.0, 0.0
        else:
            # Petite variation ±5% à chaque appel
            state["cpu"] = max(1.0,  min(99.0, state["cpu"] + random.uniform(-5, 5)))
            state["ram"] = max(5.0,  min(99.0, state["ram"] + random.uniform(-3, 3)))
            cpu = round(state["cpu"], 1)
            ram = round(state["ram"], 1)

        ram_total = 8192.0  # 8 GB par défaut
        result.append({
            "id":           vm["id"],
            "name":         vm["name"],
            "status":       vm["status"],
            "flavor":       vm["flavor"],
            "host":         vm["host"],
            "tenant_id":    "mock-tenant-001",
            "cpu_percent":  cpu,
            "ram_percent":  ram,
            "ram_used_mb":  round(ram_total * ram / 100, 0),
            "ram_total_mb": ram_total,
            "disk_read_mb": round(random.uniform(0, 50), 2),
            "disk_write_mb":round(random.uniform(0, 30), 2),
        })
    return result


# ─── Pods fictifs ─────────────────────────────────────────────────────────────

_PODS = [
    {"id": "production/api-gateway",      "name": "api-gateway",      "namespace": "production", "status": "Running",  "node": "worker-01", "restarts": 0,  "image": "nginx:1.25"},
    {"id": "production/auth-service",     "name": "auth-service",     "namespace": "production", "status": "Running",  "node": "worker-01", "restarts": 1,  "image": "auth:2.1.0"},
    {"id": "production/user-service",     "name": "user-service",     "namespace": "production", "status": "Running",  "node": "worker-02", "restarts": 0,  "image": "user:1.8.3"},
    {"id": "production/payment-service",  "name": "payment-service",  "namespace": "production", "status": "Running",  "node": "worker-02", "restarts": 2,  "image": "payment:3.0.1"},
    {"id": "production/notification-svc", "name": "notification-svc", "namespace": "production", "status": "Pending",  "node": "worker-03", "restarts": 0,  "image": "notify:1.2.0"},
    {"id": "production/report-gen",       "name": "report-gen",       "namespace": "production", "status": "Running",  "node": "worker-03", "restarts": 0,  "image": "reports:2.0.0"},
    {"id": "data/scraper-openstack",      "name": "scraper-openstack","namespace": "data",       "status": "Running",  "node": "worker-01", "restarts": 3,  "image": "scraper:1.0.0"},
    {"id": "data/scraper-logs",           "name": "scraper-logs",     "namespace": "data",       "status": "Running",  "node": "worker-02", "restarts": 0,  "image": "scraper:1.0.1"},
    {"id": "data/etl-pipeline",           "name": "etl-pipeline",     "namespace": "data",       "status": "Failed",   "node": "worker-04", "restarts": 7,  "image": "etl:0.9.5"},
    {"id": "data/data-cleaner",           "name": "data-cleaner",     "namespace": "data",       "status": "Running",  "node": "worker-04", "restarts": 0,  "image": "cleaner:1.1.0"},
    {"id": "infra/prometheus",            "name": "prometheus",       "namespace": "infra",      "status": "Running",  "node": "worker-01", "restarts": 0,  "image": "prom:2.50.0"},
    {"id": "infra/log-aggregator",        "name": "log-aggregator",   "namespace": "infra",      "status": "Running",  "node": "worker-02", "restarts": 1,  "image": "fluentd:1.16"},
    {"id": "infra/backup-controller",     "name": "backup-controller","namespace": "infra",      "status": "Running",  "node": "worker-03", "restarts": 0,  "image": "backup:2.3.0"},
    {"id": "staging/web-front",           "name": "web-front",        "namespace": "staging",    "status": "Running",  "node": "worker-05", "restarts": 0,  "image": "front:dev-latest"},
    {"id": "staging/api-mock",            "name": "api-mock",         "namespace": "staging",    "status": "Running",  "node": "worker-05", "restarts": 4,  "image": "mock:1.0.0"},
    {"id": "staging/db-test",             "name": "db-test",          "namespace": "staging",    "status": "Unknown",  "node": "worker-05", "restarts": 9,  "image": "postgres:15"},
]

_pod_state: dict[str, dict] = {
    p["id"]: {
        "cpu": random.uniform(10, 200),
        "ram": random.uniform(50, 400),
        "restarts": p["restarts"],
    }
    for p in _PODS
}


def get_mock_pods() -> list[dict]:
    """Retourne la liste des pods avec métriques légèrement aléatoires."""
    result = []
    for pod in _PODS:
        state = _pod_state[pod["id"]]

        if pod["status"] not in ("Running",):
            cpu, ram = 0.0, 0.0
        else:
            state["cpu"] = max(1.0, min(500.0, state["cpu"] + random.uniform(-10, 10)))
            state["ram"] = max(10.0, min(800.0, state["ram"] + random.uniform(-20, 20)))
            cpu = round(state["cpu"], 1)
            ram = round(state["ram"], 1)

        result.append({
            "id":            pod["id"],
            "name":          pod["name"],
            "namespace":     pod["namespace"],
            "status":        pod["status"],
            "node":          pod["node"],
            "restart_count": state["restarts"],
            "image":         pod["image"],
            "cpu_millicores":cpu,
            "ram_mb":        ram,
        })
    return result


def get_mock_cluster_nodes() -> list[dict]:
    """Inventaire mock de nodes Kubernetes/OpenShift avec taux d'utilisation."""
    nodes = [
        ("master-01", "control-plane", "Ready", 4, 8, 110, 31, 54, 18),
        ("master-02", "control-plane", "Ready", 4, 8, 110, 28, 51, 15),
        ("master-03", "control-plane", "Ready", 4, 8, 110, 34, 57, 20),
        ("worker-01", "worker", "Ready", 16, 64, 250, 67, 72, 88),
        ("worker-02", "worker", "Ready", 16, 64, 250, 61, 69, 82),
        ("worker-03", "worker", "Ready", 16, 64, 250, 77, 81, 96),
        ("worker-04", "worker", "Ready", 16, 64, 250, 84, 86, 103),
        ("worker-05", "worker", "NotReady", 8, 32, 150, 12, 18, 21),
    ]
    return [
        {
            "name": name,
            "role": role,
            "status": status,
            "kubelet_version": "v1.29.4",
            "os_image": "Red Hat Enterprise Linux CoreOS",
            "cpu_capacity": cpu,
            "memory_capacity_gb": memory,
            "pods_capacity": pods_capacity,
            "cpu_usage_percent": cpu_usage,
            "memory_usage_percent": memory_usage,
            "pods_used": pods_used,
            "disk_pressure": name == "worker-04",
            "memory_pressure": memory_usage >= 85,
        }
        for name, role, status, cpu, memory, pods_capacity, cpu_usage, memory_usage, pods_used in nodes
    ]
