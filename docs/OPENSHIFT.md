# OpenShift Deployment Guide

## About Red Hat Developer Sandbox

The [Red Hat Developer Sandbox](https://developers.redhat.com/developer-sandbox) provides a free OpenShift cluster with:
- 7 GB RAM
- 15 GB storage
- Pre-configured namespace: `red1intheocean-dev`
- 30-day session (renewable)
- TLS routes included

## Accessing the Sandbox

### Web Console
URL: https://console-openshift-console.apps.rm2.thpm.p1.openshiftapps.com

1. Log in with your Red Hat account
2. Select **Developer** perspective (dropdown top-left)
3. Your namespace `red1intheocean-dev` is pre-selected

### CLI Access
1. In the web console, click your username (top-right) → **Copy login command**
2. Click **Display Token**
3. Run the copied command:
```bash
oc login --token=sha256~XXXXX --server=https://api.rm2.thpm.p1.openshiftapps.com:6443
```

## Resource Manifests

All OpenShift manifests are in `openshift/`:

| File | Resources |
|------|-----------|
| `secrets.yaml` | Database credentials, API keys |
| `configmap.yaml` | Non-sensitive configuration |
| `postgresql.yaml` | Database Deployment + PVC + Service |
| `deployment.yaml` | App Deployment + Service + Route |

## Deployment Order

Resources must be applied in this order (due to dependencies):

```
1. secrets.yaml        (needed by both PostgreSQL and app)
2. configmap.yaml      (needed by app)
3. postgresql.yaml     (needed by app at startup)
4. deployment.yaml     (depends on all above)
```

## Using the Service Account Token

For monitoring its own namespace, the app can use the auto-mounted service account token:

```yaml
# In the deployment, set:
KUBE_API_URL: "https://kubernetes.default.svc"
KUBE_TOKEN: ""  # Will use mounted token at /var/run/secrets/kubernetes.io/serviceaccount/token
```

To enable this, update `openshift_client.py` to read the mounted token when `KUBE_TOKEN` is empty.

## Monitoring Your Deployment

### From Web Console
1. Go to **Topology** view to see all resources
2. Click a pod to see logs, events, and metrics
3. Use **Observe** → **Metrics** for resource usage

### From CLI
```bash
# All resources
oc get all -n red1intheocean-dev

# Pod status
oc get pods -n red1intheocean-dev

# Logs
oc logs deployment/cloud-ai-monitor -f

# Resource usage
oc adm top pods -n red1intheocean-dev

# Events (useful for debugging)
oc get events --sort-by='.lastTimestamp' -n red1intheocean-dev
```

## Scaling

The Developer Sandbox has limited resources, but you can adjust:

```bash
# Scale down (save resources)
oc scale deployment/cloud-ai-monitor --replicas=0

# Scale up
oc scale deployment/cloud-ai-monitor --replicas=1
```

## Updating the Application

After pushing a new image:
```bash
# Trigger a new rollout
oc rollout restart deployment/cloud-ai-monitor

# Or update the image directly
oc set image deployment/cloud-ai-monitor \
  cloud-ai-monitor=ghcr.io/red1intheocean/cloud-ai-monitor:new-tag
```

## Cleanup

To remove all resources:
```bash
oc delete deployment cloud-ai-monitor postgresql -n red1intheocean-dev
oc delete service cloud-ai-monitor postgresql -n red1intheocean-dev
oc delete route cloud-ai-monitor -n red1intheocean-dev
oc delete pvc postgresql-pvc -n red1intheocean-dev
oc delete configmap cloudwatch-config -n red1intheocean-dev
oc delete secret cloudwatch-secrets postgresql-secret -n red1intheocean-dev
```

## Sandbox Limitations

- No cluster-admin access
- Cannot create namespaces
- Limited to assigned quota
- Session expires after 30 days of inactivity
- No custom operators
- Rate limiting on API calls
