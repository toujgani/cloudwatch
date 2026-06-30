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
