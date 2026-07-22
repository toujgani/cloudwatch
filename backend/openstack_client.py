"""
Client OpenStack — authentification Keystone + collecte compute.
Utilise l'API REST directement (sans openstacksdk) pour rester léger.
"""
import logging
import requests
from datetime import datetime, timedelta
from .config import settings

logger = logging.getLogger(__name__)

_token_cache: dict = {"token": None, "expires": None, "catalog": {}}


# ─── Authentification Keystone ────────────────────────────────────────────────

def _get_token() -> str:
    """Retourne un token valide, le régénère si expiré."""
    now = datetime.utcnow()
    if _token_cache["token"] and _token_cache["expires"] and now < _token_cache["expires"]:
        return _token_cache["token"]

    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": settings.OS_USERNAME,
                        "domain": {"name": settings.OS_USER_DOMAIN_NAME},
                        "password": settings.OS_PASSWORD,
                    }
                },
            },
            "scope": {
                "project": {
                    "name": settings.OS_PROJECT_NAME,
                    "domain": {"name": settings.OS_PROJECT_DOMAIN_NAME},
                }
            },
        }
    }

    resp = requests.post(
        f"{settings.OS_AUTH_URL}/auth/tokens",
        json=payload,
        timeout=10,
    )
    resp.raise_for_status()

    token = resp.headers["X-Subject-Token"]
    body  = resp.json()

    # Parse expiry
    expires_str = body["token"]["expires_at"]  # e.g. "2025-06-01T12:00:00.000000Z"
    expires = datetime.strptime(expires_str[:19], "%Y-%m-%dT%H:%M:%S")

    # Build endpoint catalog
    catalog = {}
    for entry in body["token"].get("catalog", []):
        stype = entry["type"]
        for ep in entry.get("endpoints", []):
            if ep.get("interface") == "public":
                catalog[stype] = ep["url"]

    _token_cache.update({"token": token, "expires": expires - timedelta(minutes=5), "catalog": catalog})
    logger.info("OpenStack token renewed, expires %s", expires)
    return token


def _endpoint(service: str) -> str:
    """Get public endpoint URL for a service type."""
    _get_token()  # ensure catalog populated
    url = _token_cache["catalog"].get(service)
    if not url:
        raise RuntimeError(f"OpenStack endpoint '{service}' not found in catalog")
    return url


def _headers() -> dict:
    return {"X-Auth-Token": _get_token(), "Content-Type": "application/json"}


# ─── Compute (Nova) ───────────────────────────────────────────────────────────

def list_servers() -> list[dict]:
    """
    Retourne la liste de toutes les VMs du projet avec leurs détails.
    GET /compute/v2.1/servers/detail
    """
    url = f"{_endpoint('compute')}/servers/detail"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    servers = resp.json().get("servers", [])
    logger.debug("OpenStack: fetched %d servers", len(servers))
    return servers


def get_server_diagnostics(server_id: str) -> dict:
    """
    Diagnostics d'une VM: cpu_details, mem_details, disk_details.
    GET /compute/v2.1/servers/{id}/diagnostics
    Nécessite le rôle admin ou l'extension os-server-diagnostics.
    """
    url = f"{_endpoint('compute')}/servers/{server_id}/diagnostics"
    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


def stop_server(server_id: str) -> None:
    """Stoppe une VM OpenStack en urgence via Nova."""
    url = f"{_endpoint('compute')}/servers/{server_id}/action"
    resp = requests.post(url, headers=_headers(), json={"os-stop": None}, timeout=15)
    resp.raise_for_status()


def hard_reboot_server(server_id: str) -> None:
    """Force un reboot Nova quand une VM est bloquee."""
    url = f"{_endpoint('compute')}/servers/{server_id}/action"
    resp = requests.post(url, headers=_headers(), json={"reboot": {"type": "HARD"}}, timeout=20)
    resp.raise_for_status()


def live_migrate_server(server_id: str, host: str | None = None) -> None:
    """Demande une live migration Nova vers un autre compute si possible."""
    payload = {"os-migrateLive": {"block_migration": "auto", "host": host}}
    url = f"{_endpoint('compute')}/servers/{server_id}/action"
    resp = requests.post(url, headers=_headers(), json=payload, timeout=20)
    resp.raise_for_status()


def resize_server(server_id: str, flavor_ref: str) -> None:
    """Change le flavor d'une VM. Nova peut demander un confirm_resize ensuite."""
    url = f"{_endpoint('compute')}/servers/{server_id}/action"
    resp = requests.post(url, headers=_headers(), json={"resize": {"flavorRef": flavor_ref}}, timeout=20)
    resp.raise_for_status()


def get_server(server_id: str) -> dict:
    """Retourne le detail d'une VM Nova."""
    url = f"{_endpoint('compute')}/servers/{server_id}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("server", {})


def get_attached_volume_ids(server_id: str) -> list[str]:
    """Liste les volumes attaches a une VM via les donnees Nova."""
    server = get_server(server_id)
    attachments = server.get("os-extended-volumes:volumes_attached", [])
    return [item.get("id") for item in attachments if item.get("id")]


def get_volume(volume_id: str) -> dict:
    """Retourne le detail d'un volume Cinder."""
    try:
        base = _endpoint("volumev3")
    except RuntimeError:
        base = _endpoint("volume")
    url = f"{base}/volumes/{volume_id}"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("volume", {})


def extend_volume(volume_id: str, new_size_gb: int) -> None:
    """Augmente la taille d'un volume Cinder."""
    try:
        base = _endpoint("volumev3")
    except RuntimeError:
        base = _endpoint("volume")
    url = f"{base}/volumes/{volume_id}/action"
    resp = requests.post(
        url,
        headers=_headers(),
        json={"os-extend": {"new_size": int(new_size_gb)}},
        timeout=20,
    )
    resp.raise_for_status()


def parse_vm(server: dict, diagnostics: dict) -> dict:
    """
    Construit un dict normalisé à partir des données brutes OpenStack.
    cpu_percent est calculé depuis les diagnostics si disponibles.
    """
    # CPU — les diagnostics renvoient cpu0_time, cpu1_time … en nanosecondes
    cpu_times = [v for k, v in diagnostics.items() if k.startswith("cpu") and k.endswith("_time")]
    cpu_percent = None
    if cpu_times:
        # Valeur brute en ns — on la normalise sur 100 (estimation sur 1 vCPU)
        total_ns = sum(cpu_times)
        cpu_percent = min(round(total_ns / 1e9 / 100, 1), 100.0)

    # RAM
    mem_total = diagnostics.get("memory", 0)        # KB
    mem_actual = diagnostics.get("memory-actual", 0) # KB
    ram_percent = None
    ram_used_mb = None
    ram_total_mb = None
    if mem_total and mem_actual:
        ram_percent  = round((mem_actual / mem_total) * 100, 1)
        ram_used_mb  = round(mem_actual / 1024, 1)
        ram_total_mb = round(mem_total / 1024, 1)

    # Disk I/O
    disk_read  = sum(v for k, v in diagnostics.items() if "read_bytes"  in k) / (1024 * 1024)
    disk_write = sum(v for k, v in diagnostics.items() if "write_bytes" in k) / (1024 * 1024)

    flavor = server.get("flavor", {})

    return {
        "id":           server["id"],
        "name":         server.get("name", ""),
        "status":       server.get("status", "UNKNOWN"),
        "flavor":       flavor.get("original_name") or flavor.get("id", ""),
        "host":         server.get("OS-EXT-SRV-ATTR:host", ""),
        "tenant_id":    server.get("tenant_id", ""),
        "cpu_percent":  cpu_percent,
        "ram_percent":  ram_percent,
        "ram_used_mb":  ram_used_mb,
        "ram_total_mb": ram_total_mb,
        "disk_read_mb": round(disk_read, 2),
        "disk_write_mb":round(disk_write, 2),
    }


# ─── Nova: Hypervisors & Flavors & Quotas ─────────────────────────────────────

def list_hypervisors() -> list[dict]:
    """List all compute hypervisors. GET /compute/v2.1/os-hypervisors/detail"""
    url = f"{_endpoint('compute')}/os-hypervisors/detail"
    resp = requests.get(url, headers=_headers(), timeout=15)
    if resp.status_code == 403:
        logger.warning("OpenStack: no permission to list hypervisors")
        return []
    resp.raise_for_status()
    return resp.json().get("hypervisors", [])


def list_flavors() -> list[dict]:
    """List all flavors. GET /compute/v2.1/flavors/detail"""
    url = f"{_endpoint('compute')}/flavors/detail"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("flavors", [])


def get_compute_quotas() -> dict:
    """Get compute quotas for the current project."""
    project_id = None
    # Extract project_id from token if available
    try:
        token_data = requests.get(
            f"{settings.OS_AUTH_URL}/auth/tokens",
            headers={"X-Auth-Token": _get_token(), "X-Subject-Token": _get_token()},
            timeout=10,
        ).json()
        project_id = token_data.get("token", {}).get("project", {}).get("id")
    except Exception:
        pass

    if not project_id:
        return {}

    url = f"{_endpoint('compute')}/os-quota-sets/{project_id}"
    resp = requests.get(url, headers=_headers(), timeout=10)
    if resp.status_code != 200:
        return {}
    return resp.json().get("quota_set", {})


def get_compute_limits() -> dict:
    """Get absolute compute limits (used vs max)."""
    url = f"{_endpoint('compute')}/limits"
    resp = requests.get(url, headers=_headers(), timeout=10)
    resp.raise_for_status()
    return resp.json().get("limits", {}).get("absolute", {})


# ─── Neutron: Networks, Floating IPs, Security Groups, Routers ────────────────

def list_networks() -> list[dict]:
    """List all networks. GET /v2.0/networks"""
    try:
        url = f"{_endpoint('network')}/v2.0/networks"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("networks", [])


def list_subnets() -> list[dict]:
    """List all subnets."""
    try:
        url = f"{_endpoint('network')}/v2.0/subnets"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("subnets", [])


def list_routers() -> list[dict]:
    """List all routers."""
    try:
        url = f"{_endpoint('network')}/v2.0/routers"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("routers", [])


def list_floating_ips() -> list[dict]:
    """List all floating IPs."""
    try:
        url = f"{_endpoint('network')}/v2.0/floatingips"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("floatingips", [])


def list_security_groups() -> list[dict]:
    """List all security groups."""
    try:
        url = f"{_endpoint('network')}/v2.0/security-groups"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("security_groups", [])


def list_ports() -> list[dict]:
    """List all ports (interfaces)."""
    try:
        url = f"{_endpoint('network')}/v2.0/ports"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("ports", [])


# ─── Glance: Images ───────────────────────────────────────────────────────────

def list_images() -> list[dict]:
    """List all images. GET /v2/images"""
    try:
        url = f"{_endpoint('image')}/v2/images"
    except RuntimeError:
        return []
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("images", [])


# ─── Cinder: Volumes listing ──────────────────────────────────────────────────

def list_volumes() -> list[dict]:
    """List all block storage volumes."""
    try:
        base = _endpoint("volumev3")
    except RuntimeError:
        try:
            base = _endpoint("volume")
        except RuntimeError:
            return []
    url = f"{base}/volumes/detail"
    resp = requests.get(url, headers=_headers(), timeout=15)
    resp.raise_for_status()
    return resp.json().get("volumes", [])


# ─── Discovery: Full environment scan ─────────────────────────────────────────

def discover_environment() -> dict:
    """
    Full OpenStack environment discovery.
    Returns all discoverable resources in one call.
    Used by the frontend for the infrastructure overview.
    """
    result = {
        "authenticated": False,
        "services": [],
        "compute": {},
        "network": {},
        "storage": {},
        "images": {},
    }

    try:
        _get_token()
        result["authenticated"] = True
        result["services"] = list(_token_cache.get("catalog", {}).keys())
    except Exception as e:
        result["error"] = str(e)
        return result

    # Compute
    try:
        servers = list_servers()
        limits = get_compute_limits()
        result["compute"] = {
            "instances": len(servers),
            "instances_active": sum(1 for s in servers if s.get("status") == "ACTIVE"),
            "instances_shutoff": sum(1 for s in servers if s.get("status") == "SHUTOFF"),
            "instances_error": sum(1 for s in servers if s.get("status") == "ERROR"),
            "vcpus_used": limits.get("totalCoresUsed", 0),
            "vcpus_max": limits.get("maxTotalCores", 0),
            "ram_used_mb": limits.get("totalRAMUsed", 0),
            "ram_max_mb": limits.get("maxTotalRAMSize", 0),
            "instances_used": limits.get("totalInstancesUsed", 0),
            "instances_max": limits.get("maxTotalInstances", 0),
        }
    except Exception as e:
        result["compute"] = {"error": str(e)}

    # Hypervisors
    try:
        hypervisors = list_hypervisors()
        result["compute"]["hypervisors"] = len(hypervisors)
        result["compute"]["hypervisor_vcpus"] = sum(h.get("vcpus", 0) for h in hypervisors)
        result["compute"]["hypervisor_ram_gb"] = round(sum(h.get("memory_mb", 0) for h in hypervisors) / 1024, 1)
    except Exception:
        pass

    # Network
    try:
        networks = list_networks()
        floating_ips = list_floating_ips()
        security_groups = list_security_groups()
        routers = list_routers()
        result["network"] = {
            "networks": len(networks),
            "floating_ips": len(floating_ips),
            "floating_ips_active": sum(1 for f in floating_ips if f.get("status") == "ACTIVE"),
            "security_groups": len(security_groups),
            "routers": len(routers),
        }
    except Exception as e:
        result["network"] = {"error": str(e)}

    # Storage
    try:
        volumes = list_volumes()
        result["storage"] = {
            "volumes": len(volumes),
            "volumes_in_use": sum(1 for v in volumes if v.get("status") == "in-use"),
            "volumes_available": sum(1 for v in volumes if v.get("status") == "available"),
            "total_size_gb": sum(v.get("size", 0) for v in volumes),
        }
    except Exception as e:
        result["storage"] = {"error": str(e)}

    # Images
    try:
        images = list_images()
        result["images"] = {
            "count": len(images),
            "total_size_gb": round(sum(i.get("size", 0) for i in images) / (1024**3), 1),
        }
    except Exception as e:
        result["images"] = {"error": str(e)}

    return result
