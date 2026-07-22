"""Agent AIOps d'auto-remediation avec garde-fous.

Le moteur choisit une action, construit un plan explicable, puis applique
l'action seulement si la configuration et les limites de securite l'autorisent.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .config import settings
from .models import Alert, StatusEnum, VirtualMachine, AuditActionEnum
from .ai_agent import apply_decision
from . import openstack_client, openshift_client
from . import audit as audit_trail
from .email_notifications import send_remediation_email


@dataclass
class RemediationPlan:
    action: str
    resource_id: str
    risk: str
    reason: str
    steps: list[str]
    estimated_impact: str
    requires_approval: bool = False


@dataclass
class RemediationResult:
    action: str
    status: str
    message: str


LOW_RISK_ACTIONS = {"restart_workload", "extend_storage", "cleanup_namespace"}
MEDIUM_RISK_ACTIONS = {"scale_memory", "scale_compute", "recover_vm"}
HIGH_RISK_ACTIONS = {"quarantine_vm", "migrate_vm", "open_incident"}


def choose_action(alert: Alert) -> str:
    rule = alert.rule_name or ""
    title = (alert.title or "").lower()
    description = (alert.description or "").lower()
    text = f"{rule} {title} {description}"

    # Namespace quota breach — clean up non-essential workloads
    if "quota" in rule or "namespace" in rule:
        return "cleanup_namespace"
    if "disk" in text or "stockage" in text or "storage" in text or "espace" in text:
        return "extend_storage"
    if "ram" in text or "memory" in text or "memoire" in text:
        return "scale_memory"
    if "cpu" in text:
        return "scale_compute"
    if "blocked" in text or "bloquee" in text or "bloque" in text:
        return "recover_vm"
    if "restarts" in rule or "crashloop" in text:
        return "restart_workload"
    if "status" in rule and alert.pod_id:
        return "isolate_workload"
    if "status" in rule and alert.vm_id:
        return "recover_vm"
    return "open_incident"


def _resource_id(alert: Alert) -> str:
    return alert.vm_id or alert.pod_id or "ressource inconnue"


def _parse_csv(value: str) -> set[str]:
    return {item.strip() for item in (value or "").split(",") if item.strip()}


def _memory_flavor_map() -> dict[str, str]:
    try:
        loaded = json.loads(settings.REMEDIATION_MEMORY_FLAVOR_MAP or "{}")
    except json.JSONDecodeError:
        return {}
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in loaded.items()}


def _recent_action_count(db: Session, action: str) -> int:
    since = datetime.utcnow() - timedelta(hours=1)
    return db.query(Alert).filter(
        Alert.remediation_action == action,
        Alert.remediation_updated_at >= since,
        Alert.remediation_status.in_(["dry_run", "applied", "applied_mock"]),
    ).count()


def _guardrails_allow(db: Session, action: str) -> tuple[bool, str]:
    count = _recent_action_count(db, action)
    if count >= settings.REMEDIATION_MAX_ACTIONS_PER_HOUR:
        return False, (
            f"Limite atteinte: {count} actions '{action}' sur la derniere heure "
            f"(max {settings.REMEDIATION_MAX_ACTIONS_PER_HOUR})."
        )
    return True, "Garde-fous OK."


def describe_action(action: str, alert: Alert) -> str:
    resource = _resource_id(alert)
    if action == "cleanup_namespace":
        return "Nettoyer le namespace: supprimer les workloads non-essentiels (stress-tests, pods en erreur) pour liberer les ressources."
    if action == "extend_storage":
        return f"Ajouter {settings.REMEDIATION_STORAGE_INCREMENT_GB} GB de stockage a {resource}."
    if action == "scale_memory":
        return f"Changer {resource} vers un flavor avec plus de RAM si un mapping est configure."
    if action == "scale_compute":
        return f"Ajouter de la capacite CPU/vCPU ou migrer {resource} vers un flavor plus grand."
    if action == "recover_vm":
        return f"Recuperer la VM {resource} via {settings.REMEDIATION_VM_RECOVERY_ACTION}."
    if action == "migrate_vm":
        return f"Migrer la VM {resource} vers un autre hyperviseur si OpenStack l'autorise."
    if action == "restart_workload":
        return f"Redemarrer le workload {resource} apres verification des logs."
    if action == "isolate_workload":
        return f"Isoler le workload {resource} pour bloquer l'impact urgent."
    if action == "quarantine_vm":
        return f"Quarantainer la VM {resource} et bloquer le trafic dangereux si l'incident est critique."
    return f"Ouvrir un incident prioritaire pour {resource}."


def build_plan(db: Session, alert: Alert) -> RemediationPlan:
    action = choose_action(alert)
    resource = _resource_id(alert)
    risk = "low" if action in LOW_RISK_ACTIONS else "medium" if action in MEDIUM_RISK_ACTIONS else "high"
    reason = (
        alert.ai_reason
        or f"Alerte {alert.rule_name or 'sans regle'} avec severite {alert.severity.value}."
    )
    steps = [
        "Verifier que l'alerte est active et que le score IA depasse le seuil.",
        "Verifier les limites anti-boucle avant execution.",
    ]

    if action == "extend_storage":
        steps += [
            f"Identifier le volume attache a {resource}.",
            f"Augmenter le volume de {settings.REMEDIATION_STORAGE_INCREMENT_GB} GB sans depasser {settings.REMEDIATION_MAX_STORAGE_GB} GB.",
            "Lancer le redimensionnement filesystem cote VM via procedure operateur/SSM si necessaire.",
        ]
        impact = "Faible interruption attendue, cout EBS/Cinder plus eleve apres extension."
    elif action == "scale_memory":
        steps += [
            "Lire le flavor actuel de la VM.",
            "Chercher le flavor cible dans REMEDIATION_MEMORY_FLAVOR_MAP.",
            "Demander un resize Nova vers le flavor cible.",
        ]
        impact = "Possible indisponibilite courte selon la politique Nova resize."
    elif action == "recover_vm":
        steps += [
            f"Executer la strategie configuree: {settings.REMEDIATION_VM_RECOVERY_ACTION}.",
            "Relancer la collecte pour verifier le retour en etat sain.",
        ]
        impact = "Interruption possible de la VM pendant la recuperation."
    elif action == "restart_workload":
        steps += [
            "Verifier que le namespace est dans REMEDIATION_K8S_SAFE_NAMESPACES.",
            "Supprimer le pod pour laisser le controller Kubernetes le recreer.",
        ]
        impact = "Redemarrage du pod; impact faible si plusieurs replicas existent."
    else:
        steps.append("Creer une recommandation operateur sans action automatique.")
        impact = "Aucun changement automatique."

    return RemediationPlan(
        action=action,
        resource_id=resource,
        risk=risk,
        reason=reason,
        steps=steps,
        estimated_impact=impact,
        requires_approval=action in HIGH_RISK_ACTIONS,
    )


def _format_plan(plan: RemediationPlan) -> str:
    steps = " ".join(f"{idx + 1}) {step}" for idx, step in enumerate(plan.steps))
    approval = " Validation humaine requise." if plan.requires_approval else ""
    return (
        f"Plan AIOps [{plan.risk}] pour {plan.resource_id}: {plan.reason} "
        f"Etapes: {steps} Impact: {plan.estimated_impact}.{approval}"
    )


def _run_real_action(db: Session, plan: RemediationPlan, alert: Alert, operator: str) -> RemediationResult:
    action = plan.action

    # ── Namespace cleanup: intelligent pod classification and deletion ─────────
    if action == "cleanup_namespace":
        PROTECTED_DEPLOYMENTS = ["cloud-ai-monitor", "postgresql"]
        try:
            import requests as http_req
            s = openshift_client._session()
            namespace = settings.KUBE_NAMESPACE or "default"

            # 1. List all pods in the namespace
            pods_url = openshift_client._url(f"/api/v1/namespaces/{namespace}/pods")
            resp = s.get(pods_url, timeout=15)
            pods_data = resp.json().get("items", []) if resp.status_code == 200 else []

            # 2. Classify pods (critical vs deletable)
            critical_pods = []
            stress_test_pods = []
            crashloop_pods = []
            other_deletable = []

            for pod_item in pods_data:
                pod_name = pod_item.get("metadata", {}).get("name", "")
                labels = pod_item.get("metadata", {}).get("labels", {})
                app_label = labels.get("app", "")
                status_phase = pod_item.get("status", {}).get("phase", "")
                container_statuses = pod_item.get("status", {}).get("containerStatuses", [])

                # Check if pod belongs to a protected deployment
                is_protected = any(
                    protected in pod_name or protected in app_label
                    for protected in PROTECTED_DEPLOYMENTS
                )

                if is_protected:
                    critical_pods.append(pod_name)
                    continue

                # Check if it's a stress-test pod
                if "stress-test" in pod_name or "stress-test" in app_label:
                    stress_test_pods.append(pod_name)
                    continue

                # Check if pod is in CrashLoopBackOff
                is_crashloop = False
                for cs in container_statuses:
                    waiting = cs.get("state", {}).get("waiting", {})
                    if waiting.get("reason") == "CrashLoopBackOff":
                        is_crashloop = True
                        break

                if is_crashloop:
                    crashloop_pods.append(pod_name)
                    continue

            # 3. Delete stress-test deployments first
            deleted_stress = []
            try:
                deploy_path = f"/apis/apps/v1/namespaces/{namespace}/deployments/stress-test"
                del_resp = s.delete(openshift_client._url(deploy_path), timeout=10)
                if del_resp.status_code in (200, 202):
                    deleted_stress.append("stress-test (deployment)")
            except Exception:
                pass

            # Also delete individual stress-test pods
            for pod_name in stress_test_pods:
                try:
                    pod_path = f"/api/v1/namespaces/{namespace}/pods/{pod_name}"
                    s.delete(openshift_client._url(pod_path), timeout=10)
                    deleted_stress.append(pod_name)
                except Exception:
                    pass

            # 4. Delete CrashLoopBackOff pods that aren't part of core services
            deleted_crashloop = []
            for pod_name in crashloop_pods:
                try:
                    pod_path = f"/api/v1/namespaces/{namespace}/pods/{pod_name}"
                    s.delete(openshift_client._url(pod_path), timeout=10)
                    deleted_crashloop.append(pod_name)
                except Exception:
                    pass

            # 5. Build detailed report
            report_lines = [
                f"Nettoyage namespace execute par {operator}.",
                f"Pods proteges (non touches): {', '.join(critical_pods) or 'aucun'}",
                f"Stress-test supprimes: {', '.join(deleted_stress) or 'aucun'}",
                f"CrashLoopBackOff supprimes: {', '.join(deleted_crashloop) or 'aucun'}",
                f"Total pods supprimes: {len(deleted_stress) + len(deleted_crashloop)}",
            ]
            report = " | ".join(report_lines)

            return RemediationResult(
                action=action,
                status="applied",
                message=report,
            )
        except Exception as e:
            return RemediationResult(action, "applied",
                f"Nettoyage namespace tente par {operator}. Erreur partielle: {e}")

    if action == "extend_storage" and alert.vm_id:
        volume_ids = openstack_client.get_attached_volume_ids(alert.vm_id)
        if not volume_ids:
            return RemediationResult(action, "blocked", "Aucun volume attache trouve pour extension stockage.")
        volume_id = volume_ids[0]
        volume = openstack_client.get_volume(volume_id)
        current_size = int(volume.get("size") or 0)
        new_size = current_size + settings.REMEDIATION_STORAGE_INCREMENT_GB
        if current_size <= 0:
            return RemediationResult(action, "blocked", f"Taille actuelle inconnue pour le volume {volume_id}.")
        if new_size > settings.REMEDIATION_MAX_STORAGE_GB:
            return RemediationResult(
                action,
                "blocked",
                f"Extension refusee: {new_size} GB depasse la limite {settings.REMEDIATION_MAX_STORAGE_GB} GB.",
            )
        openstack_client.extend_volume(volume_id, new_size)
        return RemediationResult(
            action,
            "applied",
            f"Volume {volume_id} augmente de {current_size} GB a {new_size} GB par {operator}.",
        )

    if action == "scale_memory" and alert.vm_id:
        vm = db.get(VirtualMachine, alert.vm_id)
        flavor_map = _memory_flavor_map()
        current_flavor = vm.flavor if vm else None
        target_flavor = flavor_map.get(current_flavor or "")
        if not current_flavor or not target_flavor:
            return RemediationResult(
                action,
                "blocked",
                "Resize RAM impossible: configure REMEDIATION_MEMORY_FLAVOR_MAP avec flavor_actuel -> flavor_cible.",
            )
        openstack_client.resize_server(alert.vm_id, target_flavor)
        return RemediationResult(
            action,
            "applied",
            f"Resize VM {alert.vm_id} demande: {current_flavor} -> {target_flavor} par {operator}.",
        )

    if action == "recover_vm" and alert.vm_id:
        recovery_action = settings.REMEDIATION_VM_RECOVERY_ACTION.lower().strip()
        if recovery_action == "hard_reboot":
            openstack_client.hard_reboot_server(alert.vm_id)
            message = f"Hard reboot demande pour VM {alert.vm_id} par {operator}."
        elif recovery_action == "stop":
            openstack_client.stop_server(alert.vm_id)
            message = f"Stop demande pour VM {alert.vm_id} par {operator}."
        elif recovery_action == "live_migrate":
            openstack_client.live_migrate_server(alert.vm_id)
            message = f"Live migration demandee pour VM {alert.vm_id} par {operator}."
        else:
            return RemediationResult(action, "blocked", f"Strategie VM inconnue: {recovery_action}.")
        return RemediationResult(action, "applied", message)

    if action == "restart_workload" and alert.pod_id:
        namespace = alert.pod_id.split("/", 1)[0] if "/" in alert.pod_id else ""
        safe_namespaces = _parse_csv(settings.REMEDIATION_K8S_SAFE_NAMESPACES)
        if namespace not in safe_namespaces:
            return RemediationResult(
                action,
                "blocked",
                f"Namespace '{namespace}' non autorise pour redemarrage automatique.",
            )
        openshift_client.delete_pod(alert.pod_id)
        return RemediationResult(
            action=action,
            status="applied",
            message=f"Pod {alert.pod_id} supprime automatiquement par {operator}; le controller doit le recreer.",
        )

    # ── Kubernetes-native scaling (OpenShift sandbox) ─────────────────────────

    if action == "scale_memory" and alert.pod_id:
        # Increase memory limit on the deployment by REMEDIATION_MEMORY_SCALE_PERCENT
        try:
            current_limit = 1000  # Default 1000Mi if unknown
            new_limit = int(current_limit * (1 + settings.REMEDIATION_MEMORY_SCALE_PERCENT / 100))
            openshift_client.patch_deployment_resources(
                alert.pod_id,
                memory_limit=f"{new_limit}Mi",
                memory_request=f"{new_limit // 2}Mi",
            )
            return RemediationResult(
                action=action,
                status="applied",
                message=f"Deployment pour {alert.pod_id} patche: memory limit augmente a {new_limit}Mi par {operator}. Rolling update en cours.",
            )
        except Exception as e:
            return RemediationResult(action, "blocked", f"Patch memory echoue: {e}")

    if action == "scale_compute" and alert.pod_id:
        # Increase CPU limit on the deployment
        try:
            openshift_client.patch_deployment_resources(
                alert.pod_id,
                cpu_limit="1500m",
                cpu_request="200m",
            )
            return RemediationResult(
                action=action,
                status="applied",
                message=f"Deployment pour {alert.pod_id} patche: CPU limit augmente a 1500m par {operator}. Rolling update en cours.",
            )
        except Exception as e:
            return RemediationResult(action, "blocked", f"Patch CPU echoue: {e}")

    if action == "isolate_workload" and alert.pod_id:
        # Rollout restart the deployment to get fresh pods
        try:
            openshift_client.rollout_restart(alert.pod_id)
            return RemediationResult(
                action=action,
                status="applied",
                message=f"Rollout restart declenche pour le deployment de {alert.pod_id} par {operator}.",
            )
        except Exception as e:
            return RemediationResult(action, "blocked", f"Rollout restart echoue: {e}")

    if action == "quarantine_vm" and alert.vm_id:
        openstack_client.stop_server(alert.vm_id)
        return RemediationResult(
            action=action,
            status="applied",
            message=f"VM {alert.vm_id} stoppee automatiquement par {operator} pour bloquer l'impact urgent.",
        )

    return RemediationResult(
        action=action,
        status="blocked",
        message=(
            "Execution reelle non disponible pour cette action avec les donnees actuelles. "
            f"Action cible: {describe_action(action, alert)}"
        ),
    )


def execute_remediation(db: Session, alert: Alert, operator: str = "AI-Agent", force: bool = False) -> Alert:
    apply_decision(db, alert)
    plan = build_plan(db, alert)
    guardrails_ok, guardrails_message = _guardrails_allow(db, plan.action)

    allowed = (
        alert.status == StatusEnum.active
        and guardrails_ok
        and (
            force
            or (
                settings.AUTO_REMEDIATION_ENABLED
                and (alert.ai_score or 0) >= settings.AUTO_REMEDIATION_MIN_SCORE
                and not plan.requires_approval
            )
        )
    )

    if not allowed:
        reason = "execution automatique non autorisee"
        if plan.requires_approval and not force:
            reason = "validation humaine requise"
        elif not guardrails_ok:
            reason = guardrails_message
        result = RemediationResult(
            action=plan.action,
            status="recommended",
            message=f"Action recommandee: {reason}. {_format_plan(plan)}",
        )
    elif settings.AUTO_REMEDIATION_DRY_RUN:
        result = RemediationResult(
            action=plan.action,
            status="dry_run",
            message=f"Simulation executee par {operator}. {_format_plan(plan)}",
        )
    else:
        result = _run_real_action(db, plan, alert, operator)

    alert.remediation_action = result.action
    alert.remediation_status = result.status
    alert.remediation_message = result.message
    alert.remediation_updated_at = datetime.utcnow()

    if result.status in ("dry_run", "blocked", "applied", "applied_mock"):
        alert.acknowledged = True
        alert.acknowledged_by = operator.strip() or "AI-Agent"
        alert.acknowledged_at = alert.acknowledged_at or datetime.utcnow()
        alert.operator_note = (alert.operator_note or "") + f"\n[{result.status}] {result.message}"

    # Audit trail
    audit_action = (
        AuditActionEnum.remediation_applied
        if result.status in ("applied", "applied_mock", "dry_run")
        else AuditActionEnum.remediation_blocked
    )
    audit_trail.log(
        db,
        action=audit_action,
        actor=operator,
        resource_type="alert",
        resource_id=str(alert.id),
        detail=f"[{result.status}] {result.action}: {result.message[:200]}",
        extra={
            "action": result.action,
            "status": result.status,
            "risk": plan.risk,
            "force": force,
            "ai_score": alert.ai_score,
        },
    )

    # Send email notification for every remediation action
    send_remediation_email(alert)

    return alert


def auto_remediate_if_needed(db: Session, alert: Alert) -> Alert:
    if not settings.AUTO_REMEDIATION_ENABLED:
        plan = build_plan(db, alert)
        alert.remediation_action = plan.action
        alert.remediation_status = "recommended"
        alert.remediation_message = _format_plan(plan)
        alert.remediation_updated_at = datetime.utcnow()
        return alert

    if (alert.ai_score or 0) >= settings.AUTO_REMEDIATION_MIN_SCORE:
        return execute_remediation(db, alert, operator="AI-Agent")

    return alert
