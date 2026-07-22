from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import Optional
from ..database import get_db
from ..models import VirtualMachine, VMMetric
from pydantic import BaseModel

router = APIRouter(prefix="/vms", tags=["Virtual Machines"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class VMOut(BaseModel):
    id: str
    name: str
    status: str
    flavor: Optional[str]
    host: Optional[str]
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    ram_used_mb: Optional[float]
    ram_total_mb: Optional[float]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MetricPoint(BaseModel):
    collected_at: datetime
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    disk_read_mb: Optional[float]
    disk_write_mb: Optional[float]

    model_config = {"from_attributes": True}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[VMOut])
def list_vms(db: Session = Depends(get_db)):
    """Liste toutes les VMs avec leur dernière métrique."""
    vms = db.query(VirtualMachine).order_by(VirtualMachine.name).all()
    result = []
    for vm in vms:
        latest = (
            db.query(VMMetric)
            .filter(VMMetric.vm_id == vm.id)
            .order_by(desc(VMMetric.collected_at))
            .first()
        )
        out = VMOut(
            id=vm.id, name=vm.name, status=vm.status,
            flavor=vm.flavor, host=vm.host,
            cpu_percent  = latest.cpu_percent   if latest else None,
            ram_percent  = latest.ram_percent   if latest else None,
            ram_used_mb  = latest.ram_used_mb   if latest else None,
            ram_total_mb = latest.ram_total_mb  if latest else None,
            updated_at   = vm.updated_at,
        )
        result.append(out)
    return result


@router.get("/{vm_id}", response_model=VMOut)
def get_vm(vm_id: str, db: Session = Depends(get_db)):
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="VM not found")
    latest = (
        db.query(VMMetric)
        .filter(VMMetric.vm_id == vm_id)
        .order_by(desc(VMMetric.collected_at))
        .first()
    )
    return VMOut(
        id=vm.id, name=vm.name, status=vm.status,
        flavor=vm.flavor, host=vm.host,
        cpu_percent  = latest.cpu_percent   if latest else None,
        ram_percent  = latest.ram_percent   if latest else None,
        ram_used_mb  = latest.ram_used_mb   if latest else None,
        ram_total_mb = latest.ram_total_mb  if latest else None,
        updated_at   = vm.updated_at,
    )


@router.get("/{vm_id}/metrics", response_model=list[MetricPoint])
def get_vm_metrics(
    vm_id: str,
    hours: int = Query(default=24, ge=1, le=87600),
    db: Session = Depends(get_db),
):
    """Historique des métriques d'une VM sur N heures (défaut: 24h)."""
    since = datetime.utcnow() - timedelta(hours=hours)
    metrics = (
        db.query(VMMetric)
        .filter(VMMetric.vm_id == vm_id, VMMetric.collected_at >= since)
        .order_by(VMMetric.collected_at)
        .all()
    )
    return metrics


@router.get("/summary/stats")
def vms_summary(db: Session = Depends(get_db)):
    """KPI rapide: total, actives, erreurs."""
    vms = db.query(VirtualMachine).all()
    return {
        "total":   len(vms),
        "active":  sum(1 for v in vms if v.status == "ACTIVE"),
        "shutoff": sum(1 for v in vms if v.status == "SHUTOFF"),
        "error":   sum(1 for v in vms if v.status == "ERROR"),
    }


@router.get("/openstack/status")
def openstack_status():
    """
    Returns the current OpenStack connection status.
    Used by the frontend to show Connected/Disconnected state.
    """
    from ..config import settings

    if not settings.OS_AUTH_URL:
        return {
            "connected": False,
            "status": "not_configured",
            "message": "OpenStack non configure. Ajouter OS_AUTH_URL dans la configuration.",
        }

    # Try to authenticate
    try:
        from .. import openstack_client
        token = openstack_client._get_token()
        if token:
            catalog = openstack_client._token_cache.get("catalog", {})
            return {
                "connected": True,
                "status": "connected",
                "auth_url": settings.OS_AUTH_URL,
                "project": settings.OS_PROJECT_NAME,
                "services": list(catalog.keys()),
                "message": f"Connecte a OpenStack ({settings.OS_AUTH_URL}). {len(catalog)} services disponibles.",
            }
    except Exception as e:
        return {
            "connected": False,
            "status": "error",
            "auth_url": settings.OS_AUTH_URL,
            "message": f"Connexion echouee: {str(e)[:200]}",
        }

    return {"connected": False, "status": "unknown", "message": "Etat inconnu."}


@router.get("/predictions")
def vm_predictions(db: Session = Depends(get_db)):
    """Get AI predictions for all VMs — predicts CPU/RAM exhaustion."""
    from ..predictions import predict_all_vms
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "predictions": predict_all_vms(db, hours=2),
    }


@router.get("/openstack/discovery")
def openstack_discovery():
    """
    Full OpenStack environment discovery.
    Returns all resources: VMs, networks, volumes, images, hypervisors, quotas.
    Used by the dashboard for infrastructure overview.
    """
    from .. import openstack_client
    from ..config import settings

    if not settings.OS_AUTH_URL:
        return {"connected": False, "message": "OpenStack non configure."}

    try:
        return openstack_client.discover_environment()
    except Exception as e:
        return {"connected": False, "error": str(e)[:300]}


@router.get("/openstack/hypervisors")
def openstack_hypervisors():
    """List all compute hypervisors with resource allocation."""
    from .. import openstack_client
    try:
        return openstack_client.list_hypervisors()
    except Exception as e:
        return []


@router.get("/openstack/networks")
def openstack_networks():
    """List all Neutron networks."""
    from .. import openstack_client
    try:
        return openstack_client.list_networks()
    except Exception as e:
        return []


@router.get("/openstack/volumes")
def openstack_volumes():
    """List all Cinder volumes."""
    from .. import openstack_client
    try:
        return openstack_client.list_volumes()
    except Exception as e:
        return []


@router.get("/openstack/images")
def openstack_images():
    """List all Glance images."""
    from .. import openstack_client
    try:
        return openstack_client.list_images()
    except Exception as e:
        return []


@router.get("/openstack/floating-ips")
def openstack_floating_ips():
    """List all Neutron floating IPs."""
    from .. import openstack_client
    try:
        return openstack_client.list_floating_ips()
    except Exception as e:
        return []


@router.get("/openstack/security-groups")
def openstack_security_groups():
    """List all Neutron security groups."""
    from .. import openstack_client
    try:
        return openstack_client.list_security_groups()
    except Exception as e:
        return []


@router.get("/openstack/subnets")
def openstack_subnets():
    """List all Neutron subnets."""
    from .. import openstack_client
    try:
        return openstack_client.list_subnets()
    except Exception as e:
        return []


@router.get("/openstack/routers")
def openstack_routers():
    """List all Neutron routers."""
    from .. import openstack_client
    try:
        return openstack_client.list_routers()
    except Exception as e:
        return []


@router.get("/openstack/environment")
def openstack_environment():
    """
    Full OpenStack environment discovery for infrastructure page.
    Returns projects, networks, subnets, routers, floating IPs, images,
    volumes, snapshots, hypervisors, availability zones, VM details.
    """
    from .. import openstack_client
    from ..config import settings

    if not settings.OS_AUTH_URL:
        return {"connected": False, "message": "OpenStack not configured."}

    try:
        env = openstack_client.discover_environment()
        # Enrich with detailed data for the frontend
        try:
            env["networks_detail"] = openstack_client.list_networks()
        except Exception:
            env["networks_detail"] = []
        try:
            env["subnets_detail"] = openstack_client.list_subnets()
        except Exception:
            env["subnets_detail"] = []
        try:
            env["routers_detail"] = openstack_client.list_routers()
        except Exception:
            env["routers_detail"] = []
        try:
            env["floating_ips_detail"] = openstack_client.list_floating_ips()
        except Exception:
            env["floating_ips_detail"] = []
        try:
            env["images_detail"] = openstack_client.list_images()
        except Exception:
            env["images_detail"] = []
        try:
            env["volumes_detail"] = openstack_client.list_volumes()
        except Exception:
            env["volumes_detail"] = []
        try:
            env["hypervisors_detail"] = openstack_client.list_hypervisors()
        except Exception:
            env["hypervisors_detail"] = []
        try:
            env["flavors_detail"] = openstack_client.list_flavors()
        except Exception:
            env["flavors_detail"] = []
        try:
            env["servers_detail"] = openstack_client.list_servers()
        except Exception:
            env["servers_detail"] = []
        return env
    except Exception as e:
        return {"connected": False, "error": str(e)[:300]}
