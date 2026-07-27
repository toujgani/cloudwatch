from fastapi import APIRouter, Query
from .. import openshift_client as k8s_client
from ..config import settings

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
    metrics = k8s_client.list_pod_metrics()
    return [k8s_client.parse_pod(item, metrics) for item in k8s_client.list_pods()]


@router.get("/cluster")
def cluster_overview():
    if settings.MOCK_KUBERNETES:
        from ..mock_data import mock_kubernetes_cluster, mock_kubernetes_nodes, mock_kubernetes_namespaces
        cluster = mock_kubernetes_cluster()
        nodes_data = mock_kubernetes_nodes()
        return {
            "cluster": {
                "name": "openshift-main",
                "provider": "OpenShift/Kubernetes",
                "mode": "mock",
                "health_score": cluster["health_score"],
            },
            "capacity": {
                "nodes": cluster["nodes_total"],
                "ready_nodes": cluster["nodes_ready"],
                "cpu_cores": cluster["cpu_cores_total"],
                "memory_gb": cluster["ram_gb_total"],
                "pod_slots": cluster["nodes_total"] * 110,
                "pods_used": cluster["pods_total"],
                "pod_slot_usage_percent": round(cluster["pods_total"] / (cluster["nodes_total"] * 110) * 100, 1),
                "avg_cpu_usage_percent": cluster["cpu_percent_avg"],
                "avg_memory_usage_percent": cluster["ram_percent_avg"],
            },
            "workloads": {
                "pods": cluster["pods_total"],
                "running": cluster["pods_total"] - cluster["pods_failed"],
                "pending": 0,
                "failed": cluster["pods_failed"],
                "namespaces": cluster["namespaces"],
                "restart_total": 3,
            },
            "risk": {
                "pressure_nodes": 0,
                "disk_pressure_nodes": 0,
                "memory_pressure_nodes": 0,
                "saturated_nodes": sum(1 for n in nodes_data if n["cpu_percent"] >= 80),
            },
        }

    nodes = _real_nodes()
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
            "name": "openshift-main",
            "provider": "OpenShift/Kubernetes",
            "mode": "real",
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
    if settings.MOCK_KUBERNETES:
        from ..mock_data import mock_kubernetes_nodes
        return [{
            "name": n["name"], "role": n["role"], "status": n["status"],
            "kubelet_version": n["kubelet_version"], "os_image": n["os_image"],
            "cpu_capacity": int(n["cpu_capacity"]), "memory_capacity_gb": 32 if "32" in n["memory_capacity"] else 16,
            "pods_capacity": int(n["pods_capacity"]),
            "cpu_usage_percent": n["cpu_percent"], "memory_usage_percent": n["ram_percent"],
            "pods_used": n["pods_running"],
            "disk_pressure": False, "memory_pressure": False,
        } for n in mock_kubernetes_nodes()]
    return _real_nodes()


@router.get("/namespaces")
def namespaces():
    if settings.MOCK_KUBERNETES:
        from ..mock_data import mock_kubernetes_namespaces
        return [{
            "name": ns["name"], "pods": ns["pods"], "running": ns["pods"],
            "failed": 0, "pending": 0,
            "cpu_millicores": float(ns["cpu_usage"].replace("m", "")),
            "memory_mb": float(ns["ram_usage"].replace("Gi", "")) * 1024 if "Gi" in ns["ram_usage"] else float(ns["ram_usage"].replace("Mi", "")),
            "restart_total": 0,
        } for ns in mock_kubernetes_namespaces()]

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
    if settings.MOCK_KUBERNETES:
        mock_nodes = nodes()
        mock_ns = namespaces()
        return {
            "period_hours": hours,
            "rates": [
                {"name": "Disponibilite nodes", "value": 100.0, "unit": "%", "target": 99},
                {"name": "CPU cluster moyen", "value": round(sum(n.get("cpu_usage_percent", 0) or 0 for n in mock_nodes) / max(len(mock_nodes), 1), 1), "unit": "%", "target": 75},
                {"name": "Memoire cluster moyenne", "value": round(sum(n.get("memory_usage_percent", 0) or 0 for n in mock_nodes) / max(len(mock_nodes), 1), 1), "unit": "%", "target": 80},
                {"name": "Occupation slots pods", "value": round(sum(n.get("pods_used", 0) for n in mock_nodes) / max(sum(n.get("pods_capacity", 110) for n in mock_nodes), 1) * 100, 1), "unit": "%", "target": 70},
                {"name": "Namespaces en erreur", "value": 0, "unit": "ns", "target": 0},
                {"name": "Redemarrages containers", "value": 3, "unit": "restart", "target": 5},
            ],
            "by_namespace": mock_ns,
        }

    nodes_data = _real_nodes()
    namespaces_data = namespaces()
    return {
        "period_hours": hours,
        "rates": [
            {"name": "Disponibilite nodes", "value": _percent(sum(1 for n in nodes_data if n["status"] == "Ready"), len(nodes_data)), "unit": "%", "target": 99},
            {"name": "CPU cluster moyen", "value": round(sum((n["cpu_usage_percent"] or 0) for n in nodes_data) / max(len(nodes_data), 1), 1), "unit": "%", "target": 75},
            {"name": "Memoire cluster moyenne", "value": round(sum((n["memory_usage_percent"] or 0) for n in nodes_data) / max(len(nodes_data), 1), 1), "unit": "%", "target": 80},
            {"name": "Occupation slots pods", "value": _percent(sum(int(n["pods_used"]) for n in nodes_data), sum(int(n["pods_capacity"]) for n in nodes_data)), "unit": "%", "target": 70},
            {"name": "Namespaces en erreur", "value": sum(1 for n in namespaces_data if n["failed"] > 0), "unit": "ns", "target": 0},
            {"name": "Redemarrages containers", "value": sum(int(n["restart_total"]) for n in namespaces_data), "unit": "restart", "target": 5},
        ],
        "by_namespace": namespaces_data,
    }
