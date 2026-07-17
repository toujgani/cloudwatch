"""
Client OpenShift — Kubernetes REST API avec Bearer token.
Lit pods, statuts, restarts et métriques via l'API metrics.k8s.io.
Supports both external token (from .env) and auto-mounted service account token.
"""
import logging
import os
from pathlib import Path
import requests
import urllib3
from .config import settings

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# Service account token path (auto-mounted inside OpenShift pods)
_SA_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_SA_CA_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/ca.crt")


def _get_token() -> str:
    """Get bearer token: prefer env var, fallback to mounted service account."""
    if settings.KUBE_TOKEN:
        return settings.KUBE_TOKEN
    if _SA_TOKEN_PATH.exists():
        return _SA_TOKEN_PATH.read_text().strip()
    return ""


def _get_api_url() -> str:
    """Get API URL: prefer env var, fallback to in-cluster default."""
    if settings.KUBE_API_URL:
        return settings.KUBE_API_URL
    # In-cluster detection
    host = os.getenv("KUBERNETES_SERVICE_HOST", "")
    port = os.getenv("KUBERNETES_SERVICE_PORT", "443")
    if host:
        return f"https://{host}:{port}"
    return "https://kubernetes.default.svc"


def _session() -> requests.Session:
    s = requests.Session()
    token = _get_token()
    if token:
        s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })
    s.verify = settings.KUBE_VERIFY_SSL
    # If using in-cluster CA
    if not settings.KUBE_VERIFY_SSL and _SA_CA_PATH.exists():
        s.verify = str(_SA_CA_PATH)
    return s


def _url(path: str) -> str:
    return f"{_get_api_url()}{path}"


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
    Tries namespace-scoped first (sandbox-friendly), falls back to cluster-wide.
    Retourne un dict  {namespace/name: {cpu_millicores, ram_mb}}
    """
    from .config import settings
    namespace = getattr(settings, 'KUBE_NAMESPACE', '') or ''
    
    # Try namespace-scoped first (works in sandbox)
    if namespace:
        path = f"/apis/metrics.k8s.io/v1beta1/namespaces/{namespace}/pods"
    else:
        path = "/apis/metrics.k8s.io/v1beta1/pods"
    
    resp = _session().get(_url(path), timeout=15)
    if resp.status_code in (404, 503, 403):
        # Try cluster-wide as fallback
        if namespace:
            resp2 = _session().get(_url("/apis/metrics.k8s.io/v1beta1/pods"), timeout=15)
            if resp2.status_code in (404, 503, 403):
                logger.warning("metrics-server not available: %s / %s", resp.status_code, resp2.status_code)
                return {}
            resp = resp2
        else:
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


# ─── Remediation Actions (Patch Deployments) ─────────────────────────────────

def _get_deployment_for_pod(pod_id: str) -> tuple[str, str, dict] | None:
    """
    Find the Deployment that owns a pod.
    Returns (namespace, deployment_name, deployment_object) or None.
    """
    if "/" not in pod_id:
        return None
    namespace, pod_name = pod_id.split("/", 1)

    # Get the pod to find its owner
    path = f"/api/v1/namespaces/{namespace}/pods/{pod_name}"
    resp = _session().get(_url(path), timeout=15)
    if resp.status_code != 200:
        return None

    pod = resp.json()
    owner_refs = pod.get("metadata", {}).get("ownerReferences", [])

    # Pod → ReplicaSet → Deployment
    for ref in owner_refs:
        if ref.get("kind") == "ReplicaSet":
            rs_name = ref["name"]
            # Get the ReplicaSet to find the Deployment
            rs_path = f"/apis/apps/v1/namespaces/{namespace}/replicasets/{rs_name}"
            rs_resp = _session().get(_url(rs_path), timeout=15)
            if rs_resp.status_code != 200:
                continue
            rs = rs_resp.json()
            rs_owners = rs.get("metadata", {}).get("ownerReferences", [])
            for rs_ref in rs_owners:
                if rs_ref.get("kind") == "Deployment":
                    deploy_name = rs_ref["name"]
                    # Get the actual deployment
                    deploy_path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{deploy_name}"
                    deploy_resp = _session().get(_url(deploy_path), timeout=15)
                    if deploy_resp.status_code == 200:
                        return namespace, deploy_name, deploy_resp.json()
    return None


def patch_deployment_resources(
    pod_id: str,
    cpu_limit: str | None = None,
    memory_limit: str | None = None,
    cpu_request: str | None = None,
    memory_request: str | None = None,
) -> dict:
    """
    Patch a Deployment's container resource limits/requests.
    This triggers a rolling update — Kubernetes recreates pods with new limits.

    Args:
        pod_id: "namespace/pod-name" — we find the parent Deployment automatically
        cpu_limit: e.g. "1000m" or "2000m"
        memory_limit: e.g. "512Mi" or "1Gi"
        cpu_request: e.g. "100m" or "200m"
        memory_request: e.g. "256Mi" or "512Mi"

    Returns: the patched deployment spec
    """
    result = _get_deployment_for_pod(pod_id)
    if not result:
        raise RuntimeError(f"Cannot find Deployment for pod {pod_id}")

    namespace, deploy_name, deployment = result

    # Build the resource patch for the first container
    resources_patch = {}
    limits = {}
    requests = {}

    if cpu_limit:
        limits["cpu"] = cpu_limit
    if memory_limit:
        limits["memory"] = memory_limit
    if cpu_request:
        requests["cpu"] = cpu_request
    if memory_request:
        requests["memory"] = memory_request

    if limits:
        resources_patch["limits"] = limits
    if requests:
        resources_patch["requests"] = requests

    if not resources_patch:
        raise ValueError("No resource changes specified")

    # Strategic merge patch on the deployment
    patch_body = {
        "spec": {
            "template": {
                "spec": {
                    "containers": [
                        {
                            "name": deployment["spec"]["template"]["spec"]["containers"][0]["name"],
                            "resources": resources_patch,
                        }
                    ]
                }
            }
        }
    }

    path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{deploy_name}"
    s = _session()
    s.headers.update({"Content-Type": "application/strategic-merge-patch+json"})
    resp = s.patch(_url(path), json=patch_body, timeout=20)
    resp.raise_for_status()

    logger.info("Patched deployment %s/%s resources: %s", namespace, deploy_name, resources_patch)
    return resp.json()


def scale_deployment(pod_id: str, replicas: int) -> dict:
    """
    Scale a Deployment's replica count.
    Used when the AI decides more instances are needed for availability.
    """
    result = _get_deployment_for_pod(pod_id)
    if not result:
        raise RuntimeError(f"Cannot find Deployment for pod {pod_id}")

    namespace, deploy_name, _ = result

    patch_body = {"spec": {"replicas": replicas}}

    path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{deploy_name}"
    s = _session()
    s.headers.update({"Content-Type": "application/strategic-merge-patch+json"})
    resp = s.patch(_url(path), json=patch_body, timeout=15)
    resp.raise_for_status()

    logger.info("Scaled deployment %s/%s to %d replicas", namespace, deploy_name, replicas)
    return resp.json()


def rollout_restart(pod_id: str) -> dict:
    """
    Trigger a rolling restart of a Deployment (equivalent to oc rollout restart).
    Patches the pod template annotation to force new pods.
    """
    import time
    result = _get_deployment_for_pod(pod_id)
    if not result:
        raise RuntimeError(f"Cannot find Deployment for pod {pod_id}")

    namespace, deploy_name, _ = result

    patch_body = {
        "spec": {
            "template": {
                "metadata": {
                    "annotations": {
                        "cloudwatch.ai/restartedAt": str(int(time.time()))
                    }
                }
            }
        }
    }

    path = f"/apis/apps/v1/namespaces/{namespace}/deployments/{deploy_name}"
    s = _session()
    s.headers.update({"Content-Type": "application/strategic-merge-patch+json"})
    resp = s.patch(_url(path), json=patch_body, timeout=15)
    resp.raise_for_status()

    logger.info("Rollout restart triggered for %s/%s", namespace, deploy_name)
    return resp.json()


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
