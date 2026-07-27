"""
Mock data generators for OpenStack and OpenShift.
Used when MOCK_OPENSTACK=true or MOCK_OPENSHIFT=true.
Generates realistic-looking infrastructure data for demos.
"""
import random
import hashlib
from datetime import datetime


# ─── OpenStack Mock ───────────────────────────────────────────────────────────

_MOCK_VMS = [
    {"name": "web-prod-01", "flavor": "m1.large", "status": "ACTIVE"},
    {"name": "web-prod-02", "flavor": "m1.large", "status": "ACTIVE"},
    {"name": "db-master", "flavor": "m1.xlarge", "status": "ACTIVE"},
    {"name": "db-replica-01", "flavor": "m1.xlarge", "status": "ACTIVE"},
    {"name": "cache-redis-01", "flavor": "m1.medium", "status": "ACTIVE"},
    {"name": "worker-batch-01", "flavor": "m1.large", "status": "ACTIVE"},
    {"name": "monitoring-grafana", "flavor": "m1.medium", "status": "ACTIVE"},
    {"name": "ci-runner-01", "flavor": "m1.large", "status": "SHUTOFF"},
]


def _vm_id(name: str) -> str:
    return hashlib.md5(name.encode()).hexdigest()[:8] + "-" + hashlib.md5(name.encode()).hexdigest()[8:12] + "-4" + hashlib.md5(name.encode()).hexdigest()[13:16] + "-a" + hashlib.md5(name.encode()).hexdigest()[17:20] + "-" + hashlib.md5(name.encode()).hexdigest()[20:32]


def mock_openstack_vms() -> list[dict]:
    """Generate mock VM data similar to openstack_client.parse_vm output."""
    results = []
    for vm_def in _MOCK_VMS:
        vm_id = _vm_id(vm_def["name"])
        is_active = vm_def["status"] == "ACTIVE"

        cpu = round(random.uniform(15, 85), 1) if is_active else 0
        ram = round(random.uniform(30, 78), 1) if is_active else 0
        ram_total = 8192 if "xlarge" in vm_def["flavor"] else 4096 if "large" in vm_def["flavor"] else 2048
        ram_used = round(ram_total * ram / 100, 1)

        results.append({
            "id": vm_id,
            "name": vm_def["name"],
            "status": vm_def["status"],
            "flavor": vm_def["flavor"],
            "host": f"compute-{random.randint(1, 3):02d}",
            "tenant_id": "mock-tenant-001",
            "cpu_percent": cpu,
            "ram_percent": ram,
            "ram_used_mb": ram_used,
            "ram_total_mb": ram_total,
            "disk_read_mb": round(random.uniform(0.1, 50), 2),
            "disk_write_mb": round(random.uniform(0.1, 30), 2),
        })
    return results


# ─── OpenShift Mock ───────────────────────────────────────────────────────────

_MOCK_PODS = [
    {"name": "cloud-ai-monitor", "ns": "cloudwatch-prod", "status": "Running", "image": "ghcr.io/toujgani/cloud-ai-monitor:latest"},
    {"name": "postgresql-0", "ns": "cloudwatch-prod", "status": "Running", "image": "postgres:15-alpine"},
    {"name": "nginx-ingress-controller", "ns": "ingress", "status": "Running", "image": "nginx/nginx-ingress:3.4"},
    {"name": "grafana-7f8b4c", "ns": "monitoring", "status": "Running", "image": "grafana/grafana:10.2"},
    {"name": "prometheus-server-0", "ns": "monitoring", "status": "Running", "image": "prom/prometheus:v2.48"},
    {"name": "redis-cache-5d9f", "ns": "cloudwatch-prod", "status": "Running", "image": "redis:7-alpine"},
    {"name": "worker-batch-7c4a", "ns": "cloudwatch-prod", "status": "Running", "image": "ghcr.io/toujgani/worker:latest"},
    {"name": "cert-manager-6b8f", "ns": "cert-manager", "status": "Running", "image": "quay.io/jetstack/cert-manager:v1.13"},
]


def mock_openshift_pods() -> list[dict]:
    """Generate mock pod data similar to openshift_client.parse_pod output."""
    results = []
    for pod_def in _MOCK_PODS:
        pod_id = f"{pod_def['ns']}/{pod_def['name']}"
        is_running = pod_def["status"] == "Running"

        results.append({
            "id": pod_id,
            "name": pod_def["name"],
            "namespace": pod_def["ns"],
            "status": pod_def["status"],
            "node": f"worker-{random.randint(1, 3)}",
            "restart_count": random.randint(0, 2) if is_running else random.randint(3, 10),
            "image": pod_def["image"],
            "cpu_millicores": round(random.uniform(20, 450), 2) if is_running else 0,
            "ram_mb": round(random.uniform(64, 512), 2) if is_running else 0,
        })
    return results
