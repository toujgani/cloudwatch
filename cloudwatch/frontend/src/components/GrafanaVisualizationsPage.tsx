import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getGrafanaVisualizations } from '../api/client'
import type { GrafanaVisualizationPoint, GrafanaVisualizationResponse } from '../types'

const panelStyle = {
  background: '#ffffff',
  border: '1px solid #dfe6ee',
  borderRadius: 6,
  boxShadow: '0 1px 4px rgba(15,23,42,0.08)',
}

function fmtTime(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
}

function Panel({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <section style={{ ...panelStyle, overflow: 'hidden' }}>
      <div style={{
        height: 36,
        padding: '0 12px',
        borderBottom: '1px solid #e5eaf0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        background: '#fbfdff',
      }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: '#1f2937' }}>{title}</div>
        {action || <span style={{ fontSize: 10, color: '#94a3b8' }}>panel</span>}
      </div>
      {children}
    </section>
  )
}

function Gauge({ label, value, color, sub }: { label: string; value: number; color: string; sub: string }) {
  const safeValue = Math.max(0, Math.min(100, Math.round(value || 0)))
  const chartData = [{ name: label, value: safeValue, fill: color }]

  return (
    <div style={{ minWidth: 0, textAlign: 'center' }}>
      <ResponsiveContainer width="100%" height={104}>
        <RadialBarChart
          cx="50%"
          cy="76%"
          innerRadius="72%"
          outerRadius="100%"
          startAngle={180}
          endAngle={0}
          data={chartData}
        >
          <RadialBar dataKey="value" cornerRadius={8} background={{ fill: '#eef2f7' }} />
        </RadialBarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: -42, fontSize: 28, fontWeight: 900, color: '#1f2937' }}>{safeValue}</div>
      <div style={{ marginTop: 5, fontSize: 12, fontWeight: 800, color: '#334155' }}>{label}</div>
      <div style={{ marginTop: 2, fontSize: 10, color: '#64748b' }}>{sub}</div>
    </div>
  )
}

function MiniStat({ label, value, color }: { label: string; value: string | number; color: string }) {
  return (
    <div style={{ ...panelStyle, padding: '10px 12px', minHeight: 68 }}>
      <div style={{ fontSize: 11, color: '#64748b', marginBottom: 6, fontWeight: 700 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 900, color }}>{value}</div>
    </div>
  )
}

export default function GrafanaVisualizationsPage() {
  const [hours, setHours] = useState(24)
  const [data, setData] = useState<GrafanaVisualizationResponse | null>(null)
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setBusy(true)
    try {
      setData(await getGrafanaVisualizations(hours))
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [hours])

  const series = useMemo(() => (data?.series || []).map(point => ({
    ...point,
    label: fmtTime(point.time),
    cpuBar: Math.round(point.cpu || 0),
    containersBar: Math.round((point.containers || 0) / 2),
  })), [data])

  const latest: GrafanaVisualizationPoint = data?.latest || { time: '' }
  const cpu = Math.round(latest.cpu || 0)
  const memory = Math.round(latest.memory || 0)
  const disk = Math.round(latest.disk || 0)
  const containers = Math.round(latest.containers || 0)
  const networkIn = Math.round(latest.network_in || 0)
  const networkOut = Math.round(latest.network_out || 0)

  const pie = data?.distribution.length ? data.distribution : [
    { name: 'CPU', value: cpu },
    { name: 'RAM', value: memory },
    { name: 'Disque', value: disk },
  ]
  const pieColors = ['#2563eb', '#0f766e', '#f59e0b', '#dc2626', '#15803d']

  return (
    <div style={{ padding: 20, background: '#eef2f7', minHeight: 'calc(100vh - 60px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 14 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 900, marginBottom: 4, color: '#111827' }}>Server Performance - Visualisations Grafana</h2>
          <div style={{ color: '#64748b', fontSize: 12 }}>Vue principale claire des metriques Prometheus via Grafana: CPU, RAM, disque, containers et reseau.</div>
        </div>
        <span style={{ padding: '5px 9px', borderRadius: 4, background: data?.source === 'grafana' ? '#dcfce7' : '#e0f2fe', color: data?.source === 'grafana' ? '#15803d' : '#0369a1', fontSize: 11, fontWeight: 900 }}>
          {data?.source || 'loading'}
        </span>
        {[6, 24, 72].map(h => (
          <button key={h} className={hours === h ? 'btn btn-primary' : 'btn'} onClick={() => setHours(h)}>
            {h === 6 ? '6h' : h === 24 ? '24h' : '3j'}
          </button>
        ))}
        <button className="btn" disabled={busy} onClick={load}>{busy ? 'Chargement...' : 'Rafraichir'}</button>
      </div>

      {data?.message && (
        <div style={{ marginBottom: 12, padding: '8px 10px', borderRadius: 6, background: '#fff7ed', border: '1px solid #fed7aa', color: '#9a3412', fontSize: 12 }}>
          {data.message}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1.15fr', gap: 12, marginBottom: 12 }}>
        <Panel title="Server Performance">
          <div style={{ padding: 12 }}>
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="perfFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f97316" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#f97316" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e7edf4" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={18} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#111827' }} />
                <Area type="monotone" dataKey="memory" name="Memory" stroke="#ea580c" strokeWidth={2} fill="url(#perfFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Realtime Routable Metrics">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, padding: '18px 12px 10px' }}>
            <Gauge label="CPU" value={cpu} color={cpu >= 85 ? '#ef4444' : cpu >= 70 ? '#f59e0b' : '#22c55e'} sub="utilisation" />
            <Gauge label="RAM" value={memory} color={memory >= 85 ? '#ef4444' : memory >= 70 ? '#f59e0b' : '#22c55e'} sub="memoire" />
            <Gauge label="Disk" value={disk} color={disk >= 85 ? '#ef4444' : disk >= 70 ? '#f59e0b' : '#22c55e'} sub="stockage" />
          </div>
        </Panel>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginBottom: 12 }}>
        <MiniStat label="CPU actuel" value={`${cpu}%`} color="#2563eb" />
        <MiniStat label="Memoire actuelle" value={`${memory}%`} color="#0f766e" />
        <MiniStat label="Disque actuel" value={`${disk}%`} color="#dc2626" />
        <MiniStat label="Containers" value={containers} color="#15803d" />
        <MiniStat label="Network MB/s" value={`${networkIn}/${networkOut}`} color="#7c3aed" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <Panel title="CPU">
          <div style={{ padding: 12 }}>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={series}>
                <CartesianGrid stroke="#e7edf4" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={22} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#111827' }} />
                <Bar dataKey="cpuBar" name="CPU %" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Panel>

        <Panel title="Ferteric Line - Throughput">
          <div style={{ padding: 12 }}>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={series}>
                <CartesianGrid stroke="#e7edf4" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={22} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#111827' }} />
                <Line type="monotone" dataKey="network_in" name="Network in" stroke="#22c55e" strokeWidth={2} dot={false} />
                <Line type="monotone" dataKey="network_out" name="Network out" stroke="#f97316" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '0.9fr 1.1fr', gap: 12 }}>
        <Panel title="Asset Global">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 8, padding: 12 }}>
            <Gauge label="CPU" value={cpu} color="#22c55e" sub="rate" />
            <Gauge label="RAM" value={memory} color="#2563eb" sub="capacity" />
            <Gauge label="Abuse" value={disk} color="#ef4444" sub="storage" />
          </div>
        </Panel>

        <Panel title="Datadump / Containers">
          <div style={{ display: 'grid', gridTemplateColumns: '0.62fr 1.38fr', gap: 12, padding: 12 }}>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={pie} dataKey="value" cx="50%" cy="50%" innerRadius={44} outerRadius={74} paddingAngle={3}>
                  {pie.map((_, i) => <Cell key={i} fill={pieColors[i % pieColors.length]} />)}
                </Pie>
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#111827' }} />
              </PieChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={series}>
                <defs>
                  <linearGradient id="containerFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#e7edf4" />
                <XAxis dataKey="label" tick={{ fill: '#64748b', fontSize: 10 }} minTickGap={22} />
                <YAxis tick={{ fill: '#64748b', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#111827' }} />
                <Area type="monotone" dataKey="containers" name="Containers" stroke="#2563eb" fill="url(#containerFill)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Panel>
      </div>
    </div>
  )
}
