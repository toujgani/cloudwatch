export type UserRole = 'admin' | 'operator' | 'viewer'

export interface AuthUser {
  name: string
  role: UserRole
  baseRole: UserRole
}

export interface VM {
  id: string
  name: string
  status: string
  flavor?: string
  host?: string
  cpu_percent?: number
  ram_percent?: number
  ram_used_mb?: number
  ram_total_mb?: number
  updated_at?: string
}

export interface MetricPoint {
  collected_at: string
  cpu_percent?: number
  ram_percent?: number
  disk_read_mb?: number
  disk_write_mb?: number
}

export interface Pod {
  id: string
  name: string
  namespace: string
  status: string
  node?: string
  restart_count: number
  image?: string
  cpu_millicores?: number
  ram_mb?: number
  updated_at?: string
}

export interface Alert {
  id: number
  severity: 'info' | 'warning' | 'critical'
  status: 'active' | 'acknowledged' | 'assigned' | 'resolved'
  title: string
  description?: string
  rule_name?: string
  metric_value?: number
  threshold?: number
  acknowledged: boolean
  acknowledged_by?: string
  acknowledged_at?: string
  assigned_to?: string
  assigned_at?: string
  operator_note?: string
  ai_score?: number
  ai_decision?: 'escalate' | 'investigate' | 'watch' | 'suppress' | string
  ai_category?: string
  ai_reason?: string
  ai_recommendation?: string
  ai_confidence?: number
  ai_updated_at?: string
  anomaly_m?: number
  anomaly_l?: number
  anomaly_t?: number
  anomaly_vector_norm?: number
  remediation_action?: string
  remediation_status?: string
  remediation_message?: string
  remediation_updated_at?: string
  vm_id?: string
  pod_id?: string
  triggered_at: string
  resolved_at?: string
}

export interface DashboardStats {
  vms:    { total: number; active: number }
  pods:   { total: number; running: number; failed: number }
  alerts: { total_active: number; critical: number }
  health_score: number
}

export interface AlertsSummary {
  total_active: number
  critical: number
  warning: number
  info: number
  acknowledged: number
}

export interface ReportSummary {
  period_hours: number
  generated_at: string
  inventory: { vms: number; pods: number }
  availability: { active_vms: number; running_pods: number; failed_pods: number }
  metrics: { avg_vm_cpu: number; avg_vm_ram: number; avg_pod_ram_mb: number }
  alerts: {
    active: number
    critical_active: number
    warning_active: number
    triggered_in_period: number
    acknowledged_active: number
  }
  financial: {
    monthly_infra_cost: number
    automation_savings_rate: number
    estimated_period_savings: number
    resolved_alerts: number
    roi_percent: number
  }
}

export interface KubernetesClusterOverview {
  cluster: { name: string; provider: string; mode: string; health_score: number }
  capacity: {
    nodes: number; ready_nodes: number; cpu_cores: number
    memory_gb: number; pod_slots: number; pods_used: number
    pod_slot_usage_percent: number; avg_cpu_usage_percent: number
    avg_memory_usage_percent: number
  }
  workloads: {
    pods: number; running: number; pending: number
    failed: number; namespaces: number; restart_total: number
  }
  risk: {
    pressure_nodes: number; disk_pressure_nodes: number
    memory_pressure_nodes: number; saturated_nodes: number
  }
}

export interface KubernetesNode {
  name: string; role: string; status: string; kubelet_version: string
  os_image: string; cpu_capacity: number; memory_capacity_gb: number
  pods_capacity: number; cpu_usage_percent?: number
  memory_usage_percent?: number; pods_used: number
  disk_pressure: boolean; memory_pressure: boolean
}

export interface KubernetesNamespace {
  name: string; pods: number; running: number
  failed: number; pending: number; cpu_millicores: number
  memory_mb: number; restart_total: number
}

export interface KubernetesMeasurements {
  period_hours: number
  rates: { name: string; value: number; unit: string; target: number }[]
  by_namespace: KubernetesNamespace[]
}

export interface LogEntry {
  timestamp: string
  level: 'info' | 'warning' | 'error' | 'critical' | string
  service: string; location: string; message: string
  context?: string; source?: string
}

export interface LogsResponse {
  source: string; message?: string
  logs?: LogEntry[]; data?: unknown
}

export interface GrafanaVisualizationPoint {
  time: string; cpu?: number; memory?: number; disk?: number
  containers?: number; network_in?: number; network_out?: number
}

export interface GrafanaVisualizationResponse {
  source: string; message?: string; period_hours: number
  series: GrafanaVisualizationPoint[]; latest: GrafanaVisualizationPoint
  distribution: { name: string; value: number }[]
  capacity: { name: string; used: number; free: number }[]
}

export interface AnomalyVectorSim {
  vector: { m: number; l: number; t: number }
  norm: number; lambda: number; health_score: number
  ai_score: number; decision: string; formula: string
  decay_curve: { norm: number; health: number }[]
}

export interface AIOpsInjectionResult {
  id: number; severity: string; status: string; title: string
  ai_score?: number; ai_decision?: string; ai_category?: string
  ai_reason?: string; ai_recommendation?: string; ai_confidence?: number
  anomaly_m?: number; anomaly_l?: number; anomaly_t?: number
  anomaly_vector_norm?: number; remediation_action?: string
  remediation_status?: string; remediation_message?: string
  triggered_at: string
}

export interface AIOpsKnowledgeEntry {
  keyword: string; log_weight: number; trace_weight: number
  score_bonus: number; category: string
}

export interface AIOPSPipelineStatus {
  pipeline: string; ts: string; active_alerts: number
  ai_scored: number; avg_ai_score: number; avg_anomaly_norm: number
  decision_distribution: Record<string, number>
  remediation_stats: Record<string, number>
  last_audit_action?: string; last_audit_ts?: string
  lambda_config: Record<string, number>
}

export interface RuntimeInfo {
  environment: string; display_name: string; hostname: string
  vm_id?: string; vm_name?: string; project_id?: string
  availability_zone?: string; pod_name?: string
  pod_namespace?: string; node_name?: string; container_id?: string
}

export interface WsSnapshot {
  type: 'snapshot'
  ts: string
  kpis: {
    vms: { total: number; active: number }
    pods: { total: number; running: number; failed: number }
    alerts: { total_active: number; critical: number }
    health_score: number
  }
  anomaly_aggregate: { m: number; l: number; t: number }
  top_alerts: {
    id: number; severity: string; title: string
    ai_score?: number; ai_decision?: string
    anomaly_m?: number; anomaly_l?: number; anomaly_t?: number
    anomaly_vector_norm?: number; remediation_status?: string
  }[]
  runtime?: RuntimeInfo
}
