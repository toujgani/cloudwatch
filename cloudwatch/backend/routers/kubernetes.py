from fastapi import APIRouter, Query
from ..config import settings
from .. import mock_data
from .. import openshift_client as k8s_client

router = APIRouter(prefix="/kubernetes", tags=["Kubernetes"])


def _percent(value: float, total: float) -> float:
    return round((value / max(total, 1)) * 100, 1)


def _parse_cpu(value) -> float:
    raw = str(value or "0")
    if raw.endswith("m"):
        return round(float(raw[:-1]) / 1000, 2)
    return float(raw)


def _parse_memory_gb(value) -> float:
    raw = str(value or "0")
    if raw.endswith("Ki"):
        return round(float(raw[:-2]) / 1024 / 1024, 2)
    if raw.endswith("Mi"):
        return round(float(raw[:-2]) / 1024, 2)
    if raw.endswith("Gi"):
        return round(float(raw[:-2]), 2)
    return round(float(raw) / 1024 / 1024 / 1024, 2)


def _mock_nodes():
    return mock_data.get_mock_cluster_nodes()


def _real_nodes():
    nodes = []
    pods = k8s_client.list_pods()
    pod_count_by_node = {}
    for item in pods:
        node_name = item.get("spec", {}).get("nodeName", "")
        if node_name:
            pod_count_by_node[node_name] = pod_count_by_node.get(node_name, 0) + 1

    for item in k8s_client.list_nodes():
        parsed = k8s_client.parse_node(item)
        cpu_capacity = _parse_cpu(parsed["cpu_capacity"])
        memory_capacity_gb = _parse_memory_gb(parsed["memory_capacity"])
        pods_capacity = int(parsed["pods_capacity"] or 0)
        pods_used = pod_count_by_node.get(parsed["name"], 0)
        pressures = parsed.get("pressures", {})
        nodes.append({
            "name": parsed["name"],
            "role": parsed["role"],
            "status": parsed["status"],
            "kubelet_version": parsed["kubelet_version"],
            "os_image": parsed["os_image"],
            "cpu_capacity": cpu_capacity,
            "memory_capacity_gb": memory_capacity_gb,
            "pods_capacity": pods_capacity,
            "cpu_usage_percent": None,
            "memory_usage_percent": None,
            "pods_used": pods_used,
            "disk_pressure": pressures.get("DiskPressure") == "True",
            "memory_pressure": pressures.get("MemoryPressure") == "True",
        })
    return nodes


def _pods():
    if settings.MOCK_MODE:
        return mock_data.get_mock_pods()
    metrics = k8s_client.list_pod_metrics()
    return [k8s_client.parse_pod(item, metrics) for item in k8s_client.list_pods()]


def _nodes():
    return _mock_nodes() if settings.MOCK_MODE else _real_nodes()


@router.get("/cluster")
def cluster_overview():
    nodes = _nodes()
    pods = _pods()
    namespaces = sorted({p["namespace"] for p in pods})
    total_cpu = sum(float(n["cpu_capacity"]) for n in nodes)
    total_memory = sum(float(n["memory_capacity_gb"]) for n in nodes)
    total_pod_slots = sum(int(n["pods_capacity"]) for n in nodes)
    pods_used = sum(int(n["pods_used"]) for n in nodes)
    ready_nodes = sum(1 for n in nodes if n["status"] == "Ready")
    running_pods = sum(1 for p in pods if p["status"] == "Running")
    failed_pods = sum(1 for p in pods if p["status"] in ("Failed", "Unknown"))
    pending_pods = sum(1 for p in pods if p["status"] == "Pending")
    cpu_values = [n["cpu_usage_percent"] for n in nodes if n["cpu_usage_percent"] is not None]
    memory_values = [n["memory_usage_percent"] for n in nodes if n["memory_usage_percent"] is not None]
    avg_cpu = round(sum(cpu_values) / max(len(cpu_values), 1), 1)
    avg_memory = round(sum(memory_values) / max(len(memory_values), 1), 1)
    pressure_nodes = sum(1 for n in nodes if n["disk_pressure"] or n["memory_pressure"])
    restart_total = sum(int(p["restart_count"]) for p in pods)
    health_score = max(0, min(100, round(
        (_percent(ready_nodes, len(nodes)) * 0.35)
        + (_percent(running_pods, len(pods)) * 0.25)
        + ((100 - avg_cpu) * 0.15)
        + ((100 - avg_memory) * 0.15)
        + ((100 - _percent(pressure_nodes, len(nodes))) * 0.10)
        - min(restart_total, 30)
    )))

    return {
        "cluster": {
            "name": "openshift-main" if not settings.MOCK_MODE else "mock-openshift-main",
            "provider": "OpenShift/Kubernetes",
            "mode": "mock" if settings.MOCK_MODE else "real",
            "health_score": health_score,
        },
        "capacity": {
            "nodes": len(nodes),
            "ready_nodes": ready_nodes,
            "cpu_cores": round(total_cpu, 1),
            "memory_gb": round(total_memory, 1),
            "pod_slots": total_pod_slots,
            "pods_used": pods_used,
            "pod_slot_usage_percent": _percent(pods_used, total_pod_slots),
            "avg_cpu_usage_percent": avg_cpu,
            "avg_memory_usage_percent": avg_memory,
        },
        "workloads": {
            "pods": len(pods),
            "running": running_pods,
            "pending": pending_pods,
            "failed": failed_pods,
            "namespaces": len(namespaces),
            "restart_total": restart_total,
        },
        "risk": {
            "pressure_nodes": pressure_nodes,
            "disk_pressure_nodes": sum(1 for n in nodes if n["disk_pressure"]),
            "memory_pressure_nodes": sum(1 for n in nodes if n["memory_pressure"]),
            "saturated_nodes": sum(1 for n in nodes if (n["cpu_usage_percent"] or 0) >= 80 or (n["memory_usage_percent"] or 0) >= 80),
        },
    }


@router.get("/nodes")
def nodes():
    return _nodes()


@router.get("/namespaces")
def namespaces():
    pods = _pods()
    result = []
    for namespace in sorted({p["namespace"] for p in pods}):
        items = [p for p in pods if p["namespace"] == namespace]
        restarts = sum(int(p["restart_count"]) for p in items)
        result.append({
            "name": namespace,
            "pods": len(items),
            "running": sum(1 for p in items if p["status"] == "Running"),
            "failed": sum(1 for p in items if p["status"] in ("Failed", "Unknown")),
            "pending": sum(1 for p in items if p["status"] == "Pending"),
            "cpu_millicores": round(sum(float(p.get("cpu_millicores") or 0) for p in items), 1),
            "memory_mb": round(sum(float(p.get("ram_mb") or 0) for p in items), 1),
            "restart_total": restarts,
        })
    return result


@router.get("/measurements")
def measurements(hours: int = Query(default=24, ge=1, le=168)):
    nodes = _nodes()
    namespaces_data = namespaces()
    return {
        "period_hours": hours,
        "rates": [
            {"name": "Disponibilite nodes", "value": _percent(sum(1 for n in nodes if n["status"] == "Ready"), len(nodes)), "unit": "%", "target": 99},
            {"name": "CPU cluster moyen", "value": round(sum((n["cpu_usage_percent"] or 0) for n in nodes) / max(len(nodes), 1), 1), "unit": "%", "target": 75},
            {"name": "Memoire cluster moyenne", "value": round(sum((n["memory_usage_percent"] or 0) for n in nodes) / max(len(nodes), 1), 1), "unit": "%", "target": 80},
            {"name": "Occupation slots pods", "value": _percent(sum(int(n["pods_used"]) for n in nodes), sum(int(n["pods_capacity"]) for n in nodes)), "unit": "%", "target": 70},
            {"name": "Namespaces en erreur", "value": sum(1 for n in namespaces_data if n["failed"] > 0), "unit": "ns", "target": 0},
            {"name": "Redemarrages containers", "value": sum(int(n["restart_total"]) for n in namespaces_data), "unit": "restart", "target": 5},
        ],
        "by_namespace": namespaces_data,
    }
