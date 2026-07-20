import { useEffect, useState } from 'react'
import { LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { getDashboardStats, getVMs, getAlerts, getVMMetrics, getReportSummary, getPods, getGrafanaVisualizations } from '../api/client'
import type { DashboardStats, VM, Alert, ReportSummary, Pod, GrafanaVisualizationResponse } from '../types'

function KpiCard({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10,
      padding: '16px 18px', position: 'relative', overflow: 'hidden',
    }}>
      <div style={{ position: 'absolute', top: 0, left: 0, right: 0, height: 2, background: `linear-gradient(90deg,${color},transparent)` }} />
      <div style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.8px', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 700, letterSpacing: -1, color }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 6 }}>{sub}</div>
    </div>
  )
}

function cpuColor(v?: number) {
  if (!v) return 'fill-ok'
  if (v >= 90) return 'fill-crit'
  if (v >= 70) return 'fill-warn'
  return 'fill-ok'
}

export default function Dashboard() {
  const [stats, setStats]   = useState<DashboardStats | null>(null)
  const [vms, setVMs]       = useState<VM[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [chart, setChart]   = useState<{ time: string; avg: number }[]>([])
  const [hours, setHours]   = useState(24)
  const [finance, setFinance] = useState<ReportSummary['financial'] | null>(null)
  const [pods, setPods]     = useState<Pod[]>([])
  const [costTimeline, setCostTimeline] = useState<{time: string; cost: number}[]>([])
  const [grafana, setGrafana] = useState<GrafanaVisualizationResponse | null>(null)

  const load = async () => {
    const [s, v, a, r, p] = await Promise.all([getDashboardStats(), getVMs(), getAlerts('active'), getReportSummary(hours), getPods()])
    setStats(s); setVMs(v); setAlerts(a.slice(0, 6)); setPods(p)
    if (r?.financial) setFinance(r.financial)
    // Load cost timeline + grafana
    try {
      const costRes = await fetch('/api/costs/timeline?hours=' + hours, { headers: { Authorization: `Bearer ${localStorage.getItem('cloudwatch-token') || ''}` } })
      const costData = await costRes.json()
      setCostTimeline((costData.timeline || []).map((p: any) => ({
        time: p.time ? new Date(p.time).toLocaleDateString('fr-FR', { day: '2-digit', hour: '2-digit' }) : '',
        cost: p.cost * 100,
      })))
    } catch {}
    try { setGrafana(await getGrafanaVisualizations(hours)) } catch {}

    // Build CPU chart from first VM metrics
    if (v.length > 0) {
      const pts = await getVMMetrics(v[0].id, hours)
      setChart(pts.map(p => ({
        time: new Date(p.collected_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
        avg: p.cpu_percent ?? 0,
      })))
    }
  }

  useEffect(() => { load(); const t = setInterval(load, 30_000); return () => clearInterval(t) }, [hours])

  const PIE_DATA = stats ? [
    { name: 'Running', value: stats.pods.running,                             color: 'var(--green)' },
    { name: 'Failed',  value: stats.pods.failed,                              color: 'var(--red)'   },
    { name: 'Other',   value: stats.pods.total - stats.pods.running - stats.pods.failed, color: 'var(--yellow)' },
  ] : []

  return (
    <div style={{ padding: '20px 24px' }}>
      {/* Time range selector */}
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14, gap: 6 }}>
        {[
          { label: '6h', value: 6 },
          { label: '12h', value: 12 },
          { label: '24h', value: 24 },
          { label: '7j', value: 168 },
          { label: '30j', value: 720 },
          { label: '6 mois', value: 4380 },
          { label: '1 an', value: 8760 },
          { label: 'Tout', value: 87600 },
        ].map(opt => (
          <button key={opt.value}
            className={hours === opt.value ? 'btn btn-primary' : 'btn'}
            onClick={() => setHours(opt.value)}
            style={{ fontSize: 11, minHeight: 28, padding: '4px 10px' }}>
            {opt.label}
          </button>
        ))}
      </div>

      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12, marginBottom: 20 }}>
        <KpiCard label="Machines virtuelles" value={stats?.vms.total ?? '—'} sub={`${stats?.vms.active ?? 0} actives`} color="var(--blue2)" />
        <KpiCard label="Pods OpenShift"       value={stats?.pods.total ?? '—'} sub={`${stats?.pods.running ?? 0} running`}  color="var(--teal2)" />
        <KpiCard label="Alertes actives"      value={stats?.alerts.total_active ?? '—'} sub={`${stats?.alerts.critical ?? 0} critiques`} color="var(--red)" />
        <KpiCard label="Health Score"         value={stats ? `${stats.health_score}/100` : '—'} sub="sante globale infra" color="var(--yellow)" />
        <KpiCard label="Économies IA" value={finance ? `${finance.estimated_period_savings.toFixed(0)}€` : '—'} sub={finance ? `ROI ${finance.roi_percent.toFixed(0)}% · ${finance.resolved_alerts} alertes résolues` : 'calcul en cours'} color="var(--green)" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 20 }}>
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}> CPU — Historique {hours <= 24 ? '24h' : hours <= 168 ? '7 jours' : hours <= 720 ? '30 jours' : hours <= 8760 ? '1 an' : 'complet'}</div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chart}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.06)" />
              <XAxis dataKey="time" tick={{ fill: 'var(--text3)', fontSize: 10 }} interval="preserveStartEnd" />
              <YAxis domain={[0,100]} tick={{ fill: 'var(--text3)', fontSize: 10 }} tickFormatter={v => v+'%'} />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)' }} />
              <Line type="monotone" dataKey="avg" stroke="var(--blue2)" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}> État des pods</div>
          <ResponsiveContainer width="100%" height={140}>
            <PieChart>
              <Pie data={PIE_DATA} cx="50%" cy="50%" innerRadius={40} outerRadius={60} dataKey="value" paddingAngle={3}>
                {PIE_DATA.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)' }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap', marginTop: 6 }}>
            {PIE_DATA.map(d => (
              <span key={d.name} style={{ fontSize: 11, color: 'var(--text2)', display: 'flex', alignItems: 'center', gap: 4 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: d.color, display: 'inline-block' }} />
                {d.name} {d.value}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Grafana Performance (plug-and-play: shows data until real Grafana connected) */}
      {grafana && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1.2fr 0.8fr', gap: 12, marginBottom: 20 }}>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 14 }}>Performance temps reel</div>
            <div style={{ display: 'flex', justifyContent: 'space-around', alignItems: 'center' }}>
              {[
                { label: 'CPU', value: Math.round(grafana.latest?.cpu || 0), color: '#22c55e' },
                { label: 'RAM', value: Math.round(grafana.latest?.memory || 0), color: '#2563eb' },
                { label: 'Disk', value: Math.round(grafana.latest?.disk || 0), color: '#f59e0b' },
              ].map(g => (
                <div key={g.label} style={{ textAlign: 'center' }}>
                  <div style={{ width: 64, height: 64, borderRadius: '50%', border: `5px solid ${g.color}`, display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 6px' }}>
                    <span style={{ fontSize: 16, fontWeight: 700 }}>{g.value}%</span>
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text3)' }}>{g.label}</div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10 }}>Memoire — Tendance</div>
            <ResponsiveContainer width="100%" height={130}>
              <AreaChart data={(grafana.series || []).map(p => ({ t: new Date(p.time).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }), v: p.memory || 0 }))}>
                <CartesianGrid stroke="rgba(99,130,255,0.06)" />
                <XAxis dataKey="t" tick={{ fill: 'var(--text3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis tick={{ fill: 'var(--text3)', fontSize: 9 }} domain={[0, 100]} />
                <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', fontSize: 11 }} />
                <Area type="monotone" dataKey="v" stroke="#ea580c" strokeWidth={2} fill="rgba(234,88,12,0.1)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10 }}>Infrastructure</div>
            <div style={{ display: 'grid', gap: 10 }}>
              {[
                { label: 'Containers', value: String(Math.round(grafana.latest?.containers || 0)), color: 'var(--green)' },
                { label: 'Network In', value: `${Math.round(grafana.latest?.network_in || 0)} MB/s`, color: 'var(--blue2)' },
                { label: 'Network Out', value: `${Math.round(grafana.latest?.network_out || 0)} MB/s`, color: 'var(--teal2)' },
              ].map(s => (
                <div key={s.label} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 10px', borderRadius: 6, background: 'var(--bg3)' }}>
                  <span style={{ fontSize: 11, color: 'var(--text2)' }}>{s.label}</span>
                  <span style={{ fontSize: 14, fontWeight: 700, color: s.color }}>{s.value}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Cost trend + Utilization */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 20 }}>
        {/* Cost over time mini chart */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10 }}>Cout infrastructure (centimes/heure)</div>
          <ResponsiveContainer width="100%" height={120}>
            <AreaChart data={costTimeline}>
              <CartesianGrid stroke="rgba(99,130,255,0.06)" />
              <XAxis dataKey="time" tick={{ fill: 'var(--text3)', fontSize: 9 }} interval="preserveStartEnd" />
              <YAxis tick={{ fill: 'var(--text3)', fontSize: 9 }} />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', fontSize: 11 }} />
              <Area type="monotone" dataKey="cost" stroke="var(--red)" strokeWidth={2} fill="rgba(255,77,109,0.1)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Savings summary */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
          <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10 }}>Impact financier IA</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Economies</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--green)', marginTop: 4 }}>
                {finance ? `${finance.estimated_period_savings.toFixed(0)}€` : '—'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>ROI</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--green)', marginTop: 4 }}>
                {finance ? `${finance.roi_percent.toFixed(0)}%` : '—'}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Alertes resolues</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--blue2)', marginTop: 4 }}>
                {finance?.resolved_alerts ?? 0}
              </div>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Cout infra/mois</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--yellow)', marginTop: 4 }}>
                {finance ? `${finance.monthly_infra_cost.toLocaleString()}€` : '—'}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Utilization — Resource Usage Summary */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px', marginBottom: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div style={{ fontWeight: 600 }}>Utilisation des ressources</div>
          <span style={{ fontSize: 11, color: 'var(--text3)' }}>Namespace: red1intheocean-dev</span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
          {(() => {
            const totalCpu = pods.reduce((sum, p) => sum + (p.cpu_millicores ?? 0), 0)
            const totalRam = pods.reduce((sum, p) => sum + (p.ram_mb ?? 0), 0)
            const cpuQuota = 3000 // from ResourceQuota
            const ramQuota = 30 * 1024 // 30Gi in MB
            const storageUsed = 2 // 2Gi PVC
            const storageQuota = 80
            return [
              { label: 'CPU Total', value: `${totalCpu.toFixed(0)}m`, pct: (totalCpu / cpuQuota) * 100, quota: `${cpuQuota}m quota`, color: 'var(--blue2)' },
              { label: 'Mémoire', value: `${totalRam.toFixed(0)} Mi`, pct: (totalRam / ramQuota) * 100, quota: `${(ramQuota/1024).toFixed(0)} Gi quota`, color: 'var(--teal2)' },
              { label: 'Stockage PVC', value: `${storageUsed} Gi`, pct: (storageUsed / storageQuota) * 100, quota: `${storageQuota} Gi quota`, color: 'var(--yellow)' },
              { label: 'Pods actifs', value: `${pods.length}`, pct: Math.min(pods.length * 10, 100), quota: `capacité disponible`, color: 'var(--green)' },
            ].map(item => (
              <div key={item.label}>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 6 }}>{item.label}</div>
                <div style={{ fontSize: 22, fontWeight: 700, color: item.color }}>{item.value}</div>
                <div className="progress-bar" style={{ marginTop: 6, height: 6 }}>
                  <div className="progress-fill" style={{ width: `${Math.min(item.pct, 100)}%`, background: item.color }} />
                </div>
                <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>/ {item.quota}</div>
              </div>
            ))
          })()}
        </div>
      </div>

      {/* VMs + Alerts */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {/* VM Table */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 600 }}> Top VMs par CPU</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['VM','Statut','CPU','RAM'].map(h => (
                  <th key={h} style={{ fontSize: 11, color: 'var(--text3)', padding: '8px 12px', textAlign: 'left', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vms.sort((a,b) => (b.cpu_percent??0)-(a.cpu_percent??0)).slice(0,6).map(vm => (
                <tr key={vm.id} style={{ borderTop: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 500, color: 'var(--text)', fontSize: 12 }}>{vm.name}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge badge-${vm.status.toLowerCase()}`}>{vm.status}</span>
                  </td>
                  <td style={{ padding: '10px 12px', minWidth: 100 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div className="progress-bar" style={{ flex: 1 }}>
                        <div className={`progress-fill ${cpuColor(vm.cpu_percent)}`} style={{ width: `${vm.cpu_percent ?? 0}%` }} />
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 600, minWidth: 34, color: (vm.cpu_percent??0)>=90?'var(--red)':(vm.cpu_percent??0)>=70?'var(--yellow)':'var(--teal2)' }}>
                        {vm.cpu_percent?.toFixed(0) ?? '—'}%
                      </span>
                    </div>
                  </td>
                  <td style={{ padding: '10px 12px', minWidth: 100 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                      <div className="progress-bar" style={{ flex: 1 }}>
                        <div className={`progress-fill ${cpuColor(vm.ram_percent)}`} style={{ width: `${vm.ram_percent ?? 0}%` }} />
                      </div>
                      <span style={{ fontSize: 11, fontWeight: 600, minWidth: 34, color: (vm.ram_percent??0)>=90?'var(--red)':(vm.ram_percent??0)>=75?'var(--yellow)':'var(--teal2)' }}>
                        {vm.ram_percent?.toFixed(0) ?? '—'}%
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Alerts */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 600 }}>Alertes actives</div>
          <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {alerts.length === 0 && <div style={{ color: 'var(--text3)', fontSize: 12, textAlign: 'center', padding: 20 }}>Aucune alerte active</div>}
            {alerts.map(a => (
              <div key={a.id} style={{
                padding: '10px 12px', borderRadius: 8, border: '1px solid',
                background: a.severity === 'critical' ? 'rgba(255,77,109,0.06)' : a.severity === 'warning' ? 'rgba(255,209,102,0.06)' : 'rgba(79,127,255,0.06)',
                borderColor: a.severity === 'critical' ? 'rgba(255,77,109,0.2)' : a.severity === 'warning' ? 'rgba(255,209,102,0.2)' : 'rgba(79,127,255,0.2)',
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 12, fontWeight: 700, color: a.severity === 'critical' ? 'var(--red)' : a.severity === 'warning' ? 'var(--yellow)' : 'var(--blue2)' }}>
                    {a.severity.toUpperCase()}
                  </span>
                  <div>
                    <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text)', marginBottom: 2 }}>{a.title}</div>
                    <div style={{ fontSize: 11, color: 'var(--text2)' }}>{a.description}</div>
                    <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 3 }}>
                      {new Date(a.triggered_at).toLocaleString('fr-FR')}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
