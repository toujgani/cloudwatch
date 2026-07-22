<div align="center">

# Cloud AI Monitor — OpenShift Operations

### Red Hat Developer Sandbox Guide

</div>

---

## Sandbox Specifications (Verified)

| Resource | Limit | Our Usage |
|----------|-------|-----------|
| CPU requests | 3000m | ~200m |
| Memory requests | 30 Gi | ~512 Mi |
| CPU limits | 30 cores | ~1.5 cores |
| Memory limits | 30 Gi | ~1.5 Gi |
| PVCs | 10 max | 1 used |
| Storage | 80 Gi | 2 Gi |
| Pod lifetime | 12 hours (auto-restart) | Deployment recreates |

---

## Accessing the Sandbox

### Web Console

https://console-openshift-console.apps.rm2.thpm.p1.openshiftapps.com

### CLI (Long-Lived Token)

```bash
oc login --token=eyJhbG... --server=https://api.rm2.thpm.p1.openshiftapps.com:6443
```

This service account token expires in **2057**.

---

## Our Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | `cloud-ai-monitor` | Application (FastAPI + React) |
| Deployment | `postgresql` | Database |
| PVC | `postgresql-pvc` | 2Gi persistent storage |
| Service | `cloud-ai-monitor` | Internal port 8080 |
| Service | `postgresql` | Internal port 5432 |
| Route | `cloud-ai-monitor` | HTTPS external access |
| Secret | `cloudwatch-secrets` | Passwords, tokens |
| Secret | `postgresql-secret` | DB credentials |
| ConfigMap | `cloudwatch-config` | All settings |

---

## Common Operations

```bash
# See everything
oc get all -n red1intheocean-dev

# Pod status
oc get pods -n red1intheocean-dev

# Application logs
oc logs deployment/cloud-ai-monitor -n red1intheocean-dev -f

# Restart application
oc rollout restart deployment/cloud-ai-monitor -n red1intheocean-dev

# Scale down (save resources)
oc scale deployment/cloud-ai-monitor --replicas=0 -n red1intheocean-dev

# Scale up
oc scale deployment/cloud-ai-monitor --replicas=1 -n red1intheocean-dev
```

---

## Sandbox Behavior

| Behavior | Impact | Mitigation |
|----------|--------|-----------|
| Pods killed every 12h | ~10s downtime | Deployment auto-recreates |
| Idle timeout (scale to 0) | App goes down | UptimeRobot keeps it alive |
| 30-day expiry | Everything deleted | Redeploy from git |
| No cluster-admin | Can't see nodes | Namespace-scoped only |
| No custom operators | Limited extensions | Use native K8s APIs |
