"""
Client OpenShift — Kubernetes REST API avec Bearer token.
Lit pods, statuts, restarts et métriques via l'API metrics.k8s.io.
"""
import logging
import requests
import urllib3
from .config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {settings.KUBE_TOKEN}",
        "Accept": "application/json",
    })
    s.verify = settings.KUBE_VERIFY_SSL
    return s


def _url(path: str) -> str:
    return f"{settings.KUBE_API_URL}{path}"


# ─── Pods ─────────────────────────────────────────────────────────────────────

def list_pods(namespace: str = "") -> list[dict]:
    """
    Liste tous les pods de tous les namespaces (ou d'un namespace précis).
    GET /api/v1/pods  ou  GET /api/v1/namespaces/{ns}/pods
    """
    if namespace:
        path = f"/api/v1/namespaces/{namespace}/pods"
    else:
        path = "/api/v1/pods"

    resp = _session().get(_url(path), timeout=15)
    resp.raise_for_status()
    items = resp.json().get("items", [])
    logger.debug("OpenShift: fetched %d pods", len(items))
    return items


def list_nodes() -> list[dict]:
    """Liste les nodes Kubernetes/OpenShift."""
    resp = _session().get(_url("/api/v1/nodes"), timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def list_namespaces() -> list[dict]:
    """Liste les namespaces Kubernetes/OpenShift."""
    resp = _session().get(_url("/api/v1/namespaces"), timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def list_deployments(namespace: str = "") -> list[dict]:
    """Liste les deployments apps/v1."""
    path = f"/apis/apps/v1/namespaces/{namespace}/deployments" if namespace else "/apis/apps/v1/deployments"
    resp = _session().get(_url(path), timeout=15)
    resp.raise_for_status()
    return resp.json().get("items", [])


def list_pod_metrics() -> dict[str, dict]:
    """
    Métriques CPU/RAM via metrics-server (metrics.k8s.io/v1beta1).
    Retourne un dict  {namespace/name: {cpu_millicores, ram_mb}}
    """
    path = "/apis/metrics.k8s.io/v1beta1/pods"
    resp = _session().get(_url(path), timeout=15)
    if resp.status_code in (404, 503):
        # metrics-server non installé — on retourne vide
        logger.warning("metrics-server not available: %s", resp.status_code)
        return {}
    resp.raise_for_status()

    result = {}
    for item in resp.json().get("items", []):
        ns   = item["metadata"]["namespace"]
        name = item["metadata"]["name"]
        key  = f"{ns}/{name}"

        containers = item.get("containers", [])
        total_cpu_nano = 0
        total_ram_bytes = 0

        for c in containers:
            usage = c.get("usage", {})
            # CPU: "125m" (millicores) or "1500000n" (nanocores)
            cpu_str = usage.get("cpu", "0")
            if cpu_str.endswith("m"):
                total_cpu_nano += int(cpu_str[:-1]) * 1_000_000   # milli → nano
            elif cpu_str.endswith("n"):
                total_cpu_nano += int(cpu_str[:-1])
            else:
                total_cpu_nano += int(cpu_str) * 1_000_000_000    # cores → nano

            # RAM: "256Mi" or "1Gi" or bytes
            ram_str = usage.get("memory", "0")
            if ram_str.endswith("Ki"):
                total_ram_bytes += int(ram_str[:-2]) * 1024
            elif ram_str.endswith("Mi"):
                total_ram_bytes += int(ram_str[:-2]) * 1024 * 1024
            elif ram_str.endswith("Gi"):
                total_ram_bytes += int(ram_str[:-2]) * 1024 * 1024 * 1024
            else:
                total_ram_bytes += int(ram_str)

        result[key] = {
            "cpu_millicores": round(total_cpu_nano / 1_000_000, 2),
            "ram_mb":         round(total_ram_bytes / (1024 * 1024), 2),
        }

    return result


def delete_pod(pod_id: str) -> None:
    """Supprime un pod namespace/name; son controller le recréera si applicable."""
    if "/" not in pod_id:
        raise ValueError("pod_id must be in namespace/name format")
    namespace, name = pod_id.split("/", 1)
    path = f"/api/v1/namespaces/{namespace}/pods/{name}"
    resp = _session().delete(_url(path), timeout=15)
    if resp.status_code not in (200, 202):
        resp.raise_for_status()


def parse_pod(item: dict, metrics: dict) -> dict:
    """Construit un dict normalisé depuis les données brutes Kubernetes."""
    meta   = item.get("metadata", {})
    spec   = item.get("spec",     {})
    status = item.get("status",   {})

    ns   = meta.get("namespace", "")
    name = meta.get("name", "")
    key  = f"{ns}/{name}"

    # Phase: Running / Pending / Failed / Succeeded / Unknown
    phase = status.get("phase", "Unknown")

    # Restart count — somme de tous les containers
    restart_count = 0
    for cs in status.get("containerStatuses", []):
        restart_count += cs.get("restartCount", 0)

    # Image du premier container
    containers = spec.get("containers", [])
    image = containers[0].get("image", "") if containers else ""

    m = metrics.get(key, {})

    return {
        "id":            key,
        "name":          name,
        "namespace":     ns,
        "status":        phase,
        "node":          spec.get("nodeName", ""),
        "restart_count": restart_count,
        "image":         image,
        "cpu_millicores":m.get("cpu_millicores"),
        "ram_mb":        m.get("ram_mb"),
    }


def parse_node(item: dict) -> dict:
    meta = item.get("metadata", {})
    status = item.get("status", {})
    capacity = status.get("capacity", {})
    allocatable = status.get("allocatable", {})
    conditions = status.get("conditions", [])
    ready = next((c for c in conditions if c.get("type") == "Ready"), {})
    pressures = {
        c.get("type"): c.get("status")
        for c in conditions
        if c.get("type") in ("MemoryPressure", "DiskPressure", "PIDPressure", "NetworkUnavailable")
    }

    return {
        "name": meta.get("name", ""),
        "role": _node_role(meta.get("labels", {})),
        "status": "Ready" if ready.get("status") == "True" else "NotReady",
        "kubelet_version": status.get("nodeInfo", {}).get("kubeletVersion", ""),
        "os_image": status.get("nodeInfo", {}).get("osImage", ""),
        "cpu_capacity": capacity.get("cpu", "0"),
        "cpu_allocatable": allocatable.get("cpu", "0"),
        "memory_capacity": capacity.get("memory", "0"),
        "memory_allocatable": allocatable.get("memory", "0"),
        "pods_capacity": capacity.get("pods", "0"),
        "pods_allocatable": allocatable.get("pods", "0"),
        "pressures": pressures,
    }


def _node_role(labels: dict) -> str:
    for key in labels:
        if key.startswith("node-role.kubernetes.io/"):
            return key.rsplit("/", 1)[-1] or "worker"
    return "worker"
