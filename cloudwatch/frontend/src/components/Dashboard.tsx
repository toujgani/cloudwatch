import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'
import { getDashboardStats, getVMs, getAlerts, getVMMetrics } from '../api/client'
import type { DashboardStats, VM, Alert } from '../types'

const SEV_COLOR: Record<string, string> = {
  critical: 'var(--red)', warning: 'var(--yellow)', info: 'var(--blue2)',
}

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

  const load = async () => {
    const [s, v, a] = await Promise.all([getDashboardStats(), getVMs(), getAlerts('active')])
    setStats(s); setVMs(v); setAlerts(a.slice(0, 6))

    // Build CPU chart from first VM metrics
    if (v.length > 0) {
      const pts = await getVMMetrics(v[0].id, 24)
      setChart(pts.map(p => ({
        time: new Date(p.collected_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
        avg: p.cpu_percent ?? 0,
      })))
    }
  }

  useEffect(() => { load(); const t = setInterval(load, 30_000); return () => clearInterval(t) }, [])

  const PIE_DATA = stats ? [
    { name: 'Running', value: stats.pods.running,                             color: 'var(--green)' },
    { name: 'Failed',  value: stats.pods.failed,                              color: 'var(--red)'   },
    { name: 'Other',   value: stats.pods.total - stats.pods.running - stats.pods.failed, color: 'var(--yellow)' },
  ] : []

  return (
    <div style={{ padding: '20px 24px' }}>
      {/* KPIs */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12, marginBottom: 20 }}>
        <KpiCard label="Machines virtuelles" value={stats?.vms.total ?? '—'} sub={`${stats?.vms.active ?? 0} actives`} color="var(--blue2)" />
        <KpiCard label="Pods OpenShift"       value={stats?.pods.total ?? '—'} sub={`${stats?.pods.running ?? 0} running`}  color="var(--teal2)" />
        <KpiCard label="Alertes actives"      value={stats?.alerts.total_active ?? '—'} sub={`${stats?.alerts.critical ?? 0} critiques`} color="var(--red)" />
        <KpiCard label="VMs actives"          value={stats ? `${Math.round((stats.vms.active/Math.max(stats.vms.total,1))*100)}%` : '—'} sub="disponibilité" color="var(--yellow)" />
      </div>

      {/* Charts row */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: 12, marginBottom: 20 }}>
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}> CPU — Historique 24h</div>
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
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 600 }}>🔔 Alertes actives</div>
          <div style={{ padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {alerts.length === 0 && <div style={{ color: 'var(--text3)', fontSize: 12, textAlign: 'center', padding: 20 }}>✅ Aucune alerte active</div>}
            {alerts.map(a => (
              <div key={a.id} style={{
                padding: '10px 12px', borderRadius: 8, border: '1px solid',
                background: a.severity === 'critical' ? 'rgba(255,77,109,0.06)' : a.severity === 'warning' ? 'rgba(255,209,102,0.06)' : 'rgba(79,127,255,0.06)',
                borderColor: a.severity === 'critical' ? 'rgba(255,77,109,0.2)' : a.severity === 'warning' ? 'rgba(255,209,102,0.2)' : 'rgba(79,127,255,0.2)',
              }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                  <span style={{ fontSize: 15 }}>{a.severity === 'critical' ? '🔴' : a.severity === 'warning' ? '⚠️' : '🔵'}</span>
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
