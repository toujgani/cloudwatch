import axios from 'axios'
import type { VM, MetricPoint, Pod, Alert, DashboardStats, AlertsSummary, ReportSummary, KubernetesClusterOverview, KubernetesNode, KubernetesNamespace, KubernetesMeasurements, LogsResponse, GrafanaVisualizationResponse, AnomalyVectorSim, AIOpsInjectionResult, AIOpsKnowledgeEntry, AIOPSPipelineStatus } from '../types'

const TOKEN_KEY = 'cloudwatch-token'

const api = axios.create({ baseURL: '/api' })

export { api as apiClient }

// ── Token management ─────────────────────────────────────────────────────────
export function getStoredToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setStoredToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearStoredToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

// ── Axios interceptor: attach token to every request ─────────────────────────
api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Axios interceptor: handle 401 (expired token) ────────────────────────────
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearStoredToken()
      localStorage.removeItem('cloudwatch-auth-user')
      window.location.reload()
    }
    return Promise.reject(error)
  }
)

// ── Auth ─────────────────────────────────────────────────────────────────────
export interface LoginResponse {
  access_token: string
  token_type: string
  user: { name: string; role: string; baseRole: string }
}

export const login = (username: string, password: string) => {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  return api.post<LoginResponse>('/auth/login', formData, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  }).then(r => r.data)
}

export const getMe = () => api.get('/auth/me').then(r => r.data)

// ── Dashboard ────────────────────────────────────────────────────────────────
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
export const assignAlert        = (id: number, assignee: string, note?: string) =>
  api.patch<Alert>(`/alerts/${id}/assign`, { assignee, note }).then(r => r.data)
export const resolveAlert       = (id: number, operator = 'operator', note?: string) =>
  api.patch<Alert>(`/alerts/${id}/resolve`, { operator, note }).then(r => r.data)
export const reprocessAlertAgent = ()                      => api.post<Alert[]>('/alerts/agent/reprocess').then(r => r.data)
export const remediateAlert     = (id: number, operator = 'AI-Agent', force = false) =>
  api.post<Alert>(`/alerts/${id}/remediate`, { operator, force }).then(r => r.data)
export const remediateActiveAlerts = (operator = 'AI-Agent', force = false) =>
  api.post<Alert[]>('/alerts/agent/remediate-active', { operator, force }).then(r => r.data)

// ── AIOps Resolve All (one-click fix everything) ──
export const aiResolveAll = () => api.post('/aiops/resolve-all').then(r => r.data)

// ── Pod management ──
export const deletePod = (podId: string) => api.delete(`/pods/${encodeURIComponent(podId)}`).then(r => r.data)
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

// ── AIOps Simulator ──
export const simulateVector     = (m: number, l: number, t: number, severity = 'warning') =>
  api.post<AnomalyVectorSim>('/aiops/simulate/vector', { m, l, t, severity }).then(r => r.data)
export const injectAnomaly      = (payload: object)       => api.post<AIOpsInjectionResult>('/aiops/simulate/inject', payload).then(r => r.data)
export const simulateThresholds = (payload: object)       => api.post('/aiops/simulate/thresholds', payload).then(r => r.data)
export const getAIOpsKnowledgeBase = ()                   => api.get<AIOpsKnowledgeEntry[]>('/aiops/knowledge-base').then(r => r.data)
export const getAIOpsPipelineStatus = ()                  => api.get<AIOPSPipelineStatus>('/aiops/pipeline/status').then(r => r.data)

// ── Chaos / Stress Test ──
export const deployStressTest = (mode = 'both', intensity = 'medium', duration = 120) =>
  api.post('/aiops/chaos/deploy-stress', { mode, intensity, duration_seconds: duration }).then(r => r.data)
export const cleanupStressTest = () => api.delete('/aiops/chaos/cleanup').then(r => r.data)

// ── VM Stress Test (SSH-based) ──
export const deployVMStress = (payload: object) =>
  api.post('/aiops/chaos/vm-stress', payload).then(r => r.data)
export const cleanupVMStress = (vmIp: string) =>
  api.delete(`/aiops/chaos/vm-stress/${encodeURIComponent(vmIp)}`).then(r => r.data)
export const getActiveVMStress = () =>
  api.get('/aiops/chaos/vm-stress/active').then(r => r.data)

// ── OpenStack Extended ──
export const getOpenStackEnvironment = () => api.get('/vms/openstack/environment').then(r => r.data)
export const getOpenStackNetworks = () => api.get('/vms/openstack/networks').then(r => r.data)
export const getOpenStackVolumes = () => api.get('/vms/openstack/volumes').then(r => r.data)
export const getOpenStackImages = () => api.get('/vms/openstack/images').then(r => r.data)
export const getOpenStackHypervisors = () => api.get('/vms/openstack/hypervisors').then(r => r.data)
