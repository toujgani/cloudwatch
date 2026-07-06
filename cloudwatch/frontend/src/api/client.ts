import axios from 'axios'
import type { VM, MetricPoint, Pod, Alert, DashboardStats, AlertsSummary, ReportSummary, KubernetesClusterOverview, KubernetesNode, KubernetesNamespace, KubernetesMeasurements, LogsResponse, GrafanaVisualizationResponse } from '../types'

const api = axios.create({ baseURL: '/api' })

export const getDashboardStats  = ()                      => api.get<DashboardStats>('/dashboard/stats').then(r => r.data)
export const getVMs             = ()                      => api.get<VM[]>('/vms/').then(r => r.data)
export const getVM              = (id: string)            => api.get<VM>(`/vms/${id}`).then(r => r.data)
export const getVMMetrics       = (id: string, hours = 24)=> api.get<MetricPoint[]>(`/vms/${id}/metrics?hours=${hours}`).then(r => r.data)
export const getVMsSummary      = ()                      => api.get('/vms/summary/stats').then(r => r.data)
export const getPods            = (ns?: string)           => api.get<Pod[]>(`/pods/${ns ? `?namespace=${ns}` : ''}`).then(r => r.data)
export const getPodsSummary     = ()                      => api.get('/pods/summary/stats').then(r => r.data)
export const getAlerts          = (status?: string)       => api.get<Alert[]>(`/alerts/${status ? `?status=${status}` : ''}`).then(r => r.data)
export const getAlertsSummary   = ()                      => api.get<AlertsSummary>('/alerts/summary/stats').then(r => r.data)
export const acknowledgeAlert   = (id: number, operator = 'operator', note?: string) =>
  api.patch<Alert>(`/alerts/${id}/acknowledge`, { operator, note }).then(r => r.data)
export const resolveAlert       = (id: number, operator = 'operator', note?: string) =>
  api.patch<Alert>(`/alerts/${id}/resolve`, { operator, note }).then(r => r.data)
export const reprocessAlertAgent = ()                      => api.post<Alert[]>('/alerts/agent/reprocess').then(r => r.data)
export const remediateAlert     = (id: number, operator = 'AI-Agent', force = false) =>
  api.post<Alert>(`/alerts/${id}/remediate`, { operator, force }).then(r => r.data)
export const remediateActiveAlerts = (operator = 'AI-Agent', force = false) =>
  api.post<Alert[]>('/alerts/agent/remediate-active', { operator, force }).then(r => r.data)
export const getGrafanaHealth   = ()                      => api.get('/observability/grafana/health').then(r => r.data)
export const getInfraMetrics    = (hours = 1)             => api.get(`/observability/metrics/infra?hours=${hours}`).then(r => r.data)
export const getGrafanaVisualizations = (hours = 24)      => api.get<GrafanaVisualizationResponse>(`/observability/visualizations/main?hours=${hours}`).then(r => r.data)
export const getGrafanaLogs     = (selector?: string, hours = 1, level?: string, service?: string, limit = 100) =>
  api.get<LogsResponse>(`/observability/logs?hours=${hours}&limit=${limit}${selector ? `&selector=${encodeURIComponent(selector)}` : ''}${level ? `&level=${encodeURIComponent(level)}` : ''}${service ? `&service=${encodeURIComponent(service)}` : ''}`).then(r => r.data)
export const getGrafanaTraces   = (service?: string, hours = 1) =>
  api.get(`/observability/traces?hours=${hours}${service ? `&service=${encodeURIComponent(service)}` : ''}`).then(r => r.data)
export const getReportSummary   = (hours = 24)            => api.get<ReportSummary>(`/reports/summary?hours=${hours}`).then(r => r.data)
export const getKubernetesCluster = ()                    => api.get<KubernetesClusterOverview>('/kubernetes/cluster').then(r => r.data)
export const getKubernetesNodes   = ()                    => api.get<KubernetesNode[]>('/kubernetes/nodes').then(r => r.data)
export const getKubernetesNamespaces = ()                 => api.get<KubernetesNamespace[]>('/kubernetes/namespaces').then(r => r.data)
export const getKubernetesMeasurements = (hours = 24)     => api.get<KubernetesMeasurements>(`/kubernetes/measurements?hours=${hours}`).then(r => r.data)
export const exportUrl          = (kind: 'alerts'|'vms'|'pods', status?: string) =>
  `/api/reports/export/${kind}${status ? `?status=${status}` : ''}`
