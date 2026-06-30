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
