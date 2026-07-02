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
  status: 'active' | 'resolved'
  title: string
  description?: string
  rule_name?: string
  metric_value?: number
  threshold?: number
  acknowledged: boolean
  acknowledged_by?: string
  acknowledged_at?: string
  operator_note?: string
  ai_score?: number
  ai_decision?: 'escalate' | 'investigate' | 'watch' | 'suppress' | string
  ai_category?: string
  ai_reason?: string
  ai_recommendation?: string
  ai_confidence?: number
  ai_updated_at?: string
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
