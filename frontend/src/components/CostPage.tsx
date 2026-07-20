import { useEffect, useState } from 'react'
import { BarChart, Bar, LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

// Attach token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cloudwatch-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface CostSummary {
  period_hours: number
  metrics_source: {
    pod_samples: number
    avg_cpu_cores: number
    avg_ram_gb: number
    active_pods: number
    active_vms: number
  }
  costs: {
    pod_cpu: number
    pod_ram: number
    pod_scheduling: number
    vm_base: number
    storage: number
    network: number
    total: number
  }
  savings: {
    incidents_resolved_by_ai: number
    total_alerts_period: number
    incident_cost_avoided: number
    downtime_minutes_avoided: number
    downtime_cost_avoided: number
    total_savings: number
  }
  projections: {
    monthly_cost: number
    yearly_cost: number
    monthly_savings: number
    yearly_savings: number
    roi_percent: number
  }
  pricing_model: Record<string, number>
}

interface TimelinePoint {
  time: string
  cost: number
  cpu_cost: number
  ram_cost: number
  pods: number
}

export default function CostPage() {
  const [summary, setSummary] = useState<CostSummary | null>(null)
  const [timeline, setTimeline] = useState<TimelinePoint[]>([])
  const [hours, setHours] = useState(168)

  useEffect(() => {
    api.get(`/costs/summary?hours=${hours}`).then(r => setSummary(r.data)).catch(() => {})
    api.get(`/costs/timeline?hours=${hours}`).then(r => setTimeline(r.data.timeline || [])).catch(() => {})
  }, [hours])

  const chartData = timeline.map(p => ({
    time: p.time ? new Date(p.time).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', hour: '2-digit' }) : '',
    cout: p.cost * 100, // scale for visibility (cents)
    cpu: p.cpu_cost * 100,
    ram: p.ram_cost * 100,
  }))

  const breakdown = summary ? [
    { name: 'CPU', cost: summary.costs.pod_cpu },
    { name: 'RAM', cost: summary.costs.pod_ram },
    { name: 'Orchestration', cost: summary.costs.pod_scheduling },
    { name: 'VMs', cost: summary.costs.vm_base },
    { name: 'Stockage', cost: summary.costs.storage },
    { name: 'Reseau', cost: summary.costs.network },
  ] : []

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
        <div>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Analyse des couts infrastructure</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>
            Calcul base sur les metriques reelles collectees (CPU/RAM pods + VMs) — tarification CIRES interne
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[
            { label: '24h', value: 24 },
            { label: '7j', value: 168 },
            { label: '30j', value: 720 },
            { label: '90j', value: 2160 },
            { label: '1 an', value: 8760 },
          ].map(opt => (
            <button key={opt.value}
              className={hours === opt.value ? 'btn btn-primary' : 'btn'}
              onClick={() => setHours(opt.value)}
              style={{ fontSize: 11, minHeight: 28, padding: '4px 10px' }}>
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* KPI row */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Cout total periode</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--red)' }}>{summary.costs.total.toFixed(2)}€</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>{summary.period_hours}h mesurees</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Projection mensuelle</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--yellow)' }}>{summary.projections.monthly_cost.toFixed(2)}€</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>estimation 30 jours</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Economies IA</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--green)' }}>{summary.savings.total_savings.toFixed(0)}€</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>{summary.savings.incidents_resolved_by_ai} incidents resolus</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>ROI automatisation</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: summary.projections.roi_percent > 0 ? 'var(--green)' : 'var(--text2)' }}>
              {summary.projections.roi_percent.toFixed(0)}%
            </div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>economies / cout</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Downtime evite</div>
            <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--teal2)' }}>{summary.savings.downtime_minutes_avoided} min</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>{summary.savings.downtime_cost_avoided.toFixed(0)}€ evites</div>
          </div>
        </div>
      )}

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 0.6fr', gap: 12, marginBottom: 20 }}>
        {/* Cost over time */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>Cout horaire dans le temps (centimes)</div>
          <ResponsiveContainer width="100%" height={220}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="var(--red)" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="var(--red)" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.08)" />
              <XAxis dataKey="time" tick={{ fill: 'var(--text3)', fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'var(--text3)', fontSize: 10 }} tickFormatter={v => `${v}c`} />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', fontSize: 11 }} formatter={(v: number) => [`${v.toFixed(2)} centimes`, '']} />
              <Area type="monotone" dataKey="cout" stroke="var(--red)" strokeWidth={2} fill="url(#costGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Breakdown bar chart */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 12 }}>Repartition</div>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={breakdown} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.08)" />
              <XAxis type="number" tick={{ fill: 'var(--text3)', fontSize: 10 }} tickFormatter={v => `${v}€`} />
              <YAxis type="category" dataKey="name" tick={{ fill: 'var(--text2)', fontSize: 11 }} width={80} />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', fontSize: 11 }} formatter={(v: number) => [`${v.toFixed(2)}€`, 'Cout']} />
              <Bar dataKey="cost" fill="var(--blue2)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Detailed pricing table */}
      {summary && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>Donnees sources (metriques reelles)</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {[
                  ['Echantillons pod', `${summary.metrics_source.pod_samples} mesures`],
                  ['CPU moyen', `${(summary.metrics_source.avg_cpu_cores * 1000).toFixed(0)} millicores`],
                  ['RAM moyen', `${(summary.metrics_source.avg_ram_gb * 1024).toFixed(0)} MB`],
                  ['Pods actifs', `${summary.metrics_source.active_pods}`],
                  ['VMs actives', `${summary.metrics_source.active_vms}`],
                  ['Alertes periode', `${summary.savings.total_alerts_period}`],
                  ['Resolues par IA', `${summary.savings.incidents_resolved_by_ai}`],
                ].map(([label, value]) => (
                  <tr key={label} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '8px 0', fontSize: 12, color: 'var(--text2)' }}>{label}</td>
                    <td style={{ padding: '8px 0', fontSize: 12, fontWeight: 600, textAlign: 'right' }}>{value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, marginBottom: 12 }}>Grille tarifaire CIRES</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <tbody>
                {summary.pricing_model && Object.entries(summary.pricing_model).map(([key, val]) => (
                  <tr key={key} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '6px 0', fontSize: 11, color: 'var(--text2)' }}>{key.replace(/_/g, ' ')}</td>
                    <td style={{ padding: '6px 0', fontSize: 11, fontWeight: 600, textAlign: 'right' }}>{val}€</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
