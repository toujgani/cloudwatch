"""
Runtime Environment Detection Module.
Detects where the application is running:
  - OpenStack VM (via metadata service)
  - OpenShift Pod (via mounted service account)
  - Local Development (fallback)

This is independent of monitoring targets.
The app can run on an OpenStack VM while still monitoring OpenShift clusters.
"""
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_SA_TOKEN_PATH = Path("/var/run/secrets/kubernetes.io/serviceaccount/token")
_OPENSTACK_METADATA_URL = "http://169.254.169.254/openstack/latest/meta_data.json"


@dataclass
class RuntimeEnvironment:
    """Describes where the application is currently executing."""
    environment: str  # "openstack_vm" | "openshift_pod" | "local"
    display_name: str  # Human-readable display
    hostname: str
    # OpenStack VM details (if running on OpenStack)
    vm_id: Optional[str] = None
    vm_name: Optional[str] = None
    project_id: Optional[str] = None
    availability_zone: Optional[str] = None
    # OpenShift pod details (if running in k8s)
    pod_name: Optional[str] = None
    pod_namespace: Optional[str] = None
    node_name: Optional[str] = None
    # Container info
    container_id: Optional[str] = None


def _detect_openshift() -> Optional[RuntimeEnvironment]:
    """Check if running inside an OpenShift/Kubernetes pod."""
    if _SA_TOKEN_PATH.exists() or os.getenv("KUBERNETES_SERVICE_HOST"):
        hostname = os.getenv("HOSTNAME", "unknown")
        namespace = ""
        try:
            ns_path = Path("/var/run/secrets/kubernetes.io/serviceaccount/namespace")
            if ns_path.exists():
                namespace = ns_path.read_text().strip()
        except Exception:
            namespace = os.getenv("KUBE_NAMESPACE", "")

        return RuntimeEnvironment(
            environment="openshift_pod",
            display_name="OpenShift Pod",
            hostname=hostname,
            pod_name=hostname,
            pod_namespace=namespace,
            node_name=os.getenv("NODE_NAME", ""),
        )
    return None


def _detect_openstack() -> Optional[RuntimeEnvironment]:
    """Check if running inside an OpenStack VM via metadata service."""
    try:
        resp = requests.get(_OPENSTACK_METADATA_URL, timeout=2)
        if resp.status_code == 200:
            meta = resp.json()
            return RuntimeEnvironment(
                environment="openstack_vm",
                display_name="OpenStack VM",
                hostname=meta.get("hostname", os.getenv("HOSTNAME", "unknown")),
                vm_id=meta.get("uuid"),
                vm_name=meta.get("name"),
                project_id=meta.get("project_id"),
                availability_zone=meta.get("availability_zone"),
            )
    except (requests.RequestException, ValueError):
        pass
    return None


def _detect_container() -> Optional[RuntimeEnvironment]:
    """Check if running inside a container (Docker/Podman) without k8s."""
    cgroup_path = Path("/proc/1/cgroup")
    if cgroup_path.exists():
        try:
            content = cgroup_path.read_text()
            if "docker" in content or "podman" in content or "containerd" in content:
                hostname = os.getenv("HOSTNAME", "unknown")
                return RuntimeEnvironment(
                    environment="container",
                    display_name="Container (Podman/Docker)",
                    hostname=hostname,
                    container_id=hostname,
                )
        except Exception:
            pass
    # Also check for .dockerenv file
    if Path("/.dockerenv").exists():
        hostname = os.getenv("HOSTNAME", "unknown")
        return RuntimeEnvironment(
            environment="container",
            display_name="Container (Podman/Docker)",
            hostname=hostname,
            container_id=hostname,
        )
    return None


def detect_runtime() -> RuntimeEnvironment:
    """
    Detect the current runtime environment.
    Priority: OpenShift > OpenStack VM > Container > Local
    """
    # Check OpenShift/Kubernetes first
    env = _detect_openshift()
    if env:
        logger.info("[Runtime] Detected: %s (pod=%s, ns=%s)",
                    env.display_name, env.pod_name, env.pod_namespace)
        return env

    # Check OpenStack VM
    env = _detect_openstack()
    if env:
        logger.info("[Runtime] Detected: %s (vm=%s, az=%s)",
                    env.display_name, env.vm_name, env.availability_zone)
        return env

    # Check container
    env = _detect_container()
    if env:
        logger.info("[Runtime] Detected: %s (id=%s)", env.display_name, env.container_id)
        return env

    # Fallback: local development
    import socket
    hostname = socket.gethostname()
    logger.info("[Runtime] Detected: Local Development (host=%s)", hostname)
    return RuntimeEnvironment(
        environment="local",
        display_name="Local Development",
        hostname=hostname,
    )


# Cached runtime info (detected once at startup)
_runtime_cache: Optional[RuntimeEnvironment] = None


def get_runtime() -> RuntimeEnvironment:
    """Get cached runtime environment (detected once)."""
    global _runtime_cache
    if _runtime_cache is None:
        _runtime_cache = detect_runtime()
    return _runtime_cache


def runtime_info_dict() -> dict:
    """Return runtime info as a serializable dict."""
    rt = get_runtime()
    result = {
        "environment": rt.environment,
        "display_name": rt.display_name,
        "hostname": rt.hostname,
    }
    if rt.vm_id:
        result["vm_id"] = rt.vm_id
        result["vm_name"] = rt.vm_name
        result["project_id"] = rt.project_id
        result["availability_zone"] = rt.availability_zone
    if rt.pod_name:
        result["pod_name"] = rt.pod_name
        result["pod_namespace"] = rt.pod_namespace
        result["node_name"] = rt.node_name
    if rt.container_id:
        result["container_id"] = rt.container_id
    return result
