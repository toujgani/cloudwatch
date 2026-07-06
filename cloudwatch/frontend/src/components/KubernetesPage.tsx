import { useEffect, useMemo, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getKubernetesCluster, getKubernetesMeasurements, getKubernetesNodes } from '../api/client'
import type { KubernetesClusterOverview, KubernetesMeasurements, KubernetesNode } from '../types'

function Metric({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  return (
    <div className="panel" style={{ padding: '14px 16px', minHeight: 92 }}>
      <div style={{ color: 'var(--text3)', fontSize: 11, textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
      <div style={{ color, fontSize: 26, fontWeight: 800 }}>{value}</div>
      <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 6 }}>{sub}</div>
    </div>
  )
}

function fill(v?: number) {
  if (v == null) return 'fill-ok'
  if (v >= 85) return 'fill-crit'
  if (v >= 70) return 'fill-warn'
  return 'fill-ok'
}

export default function KubernetesPage() {
  const [overview, setOverview] = useState<KubernetesClusterOverview | null>(null)
  const [nodes, setNodes] = useState<KubernetesNode[]>([])
  const [measurements, setMeasurements] = useState<KubernetesMeasurements | null>(null)
  const [hours, setHours] = useState(24)

  const load = async () => {
    const [cluster, nodeList, measure] = await Promise.all([
      getKubernetesCluster(),
      getKubernetesNodes(),
      getKubernetesMeasurements(hours),
    ])
    setOverview(cluster)
    setNodes(nodeList)
    setMeasurements(measure)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [hours])

  const nodeStatus = useMemo(() => {
    const ready = nodes.filter(n => n.status === 'Ready').length
    return [
      { name: 'Ready', value: ready, color: 'var(--green)' },
      { name: 'NotReady', value: Math.max(nodes.length - ready, 0), color: 'var(--red)' },
    ]
  }, [nodes])

  const nodeBars = nodes.map(n => ({
    name: n.name.replace('worker-', 'w-').replace('master-', 'm-'),
    cpu: n.cpu_usage_percent ?? 0,
    mem: n.memory_usage_percent ?? 0,
    pods: Math.round((n.pods_used / Math.max(n.pods_capacity, 1)) * 100),
  }))

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>Gestion Kubernetes & Clusters</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>
            Capacite, disponibilite, pression ressources, namespaces et taux de mesure operationnels.
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[24, 72, 168].map(h => (
            <button key={h} className={hours === h ? 'btn btn-primary' : 'btn'} onClick={() => setHours(h)}>
              {h === 24 ? '24h' : h === 72 ? '3j' : '7j'}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginBottom: 18 }}>
        <Metric label="Health cluster" value={`${overview?.cluster.health_score ?? 0}/100`} sub={overview?.cluster.name ?? 'cluster'} color="var(--blue2)" />
        <Metric label="Nodes ready" value={`${overview?.capacity.ready_nodes ?? 0}/${overview?.capacity.nodes ?? 0}`} sub="etat du cluster" color="var(--green)" />
        <Metric label="CPU moyen" value={`${overview?.capacity.avg_cpu_usage_percent ?? 0}%`} sub={`${overview?.capacity.cpu_cores ?? 0} cores`} color="var(--yellow)" />
        <Metric label="Memoire moyenne" value={`${overview?.capacity.avg_memory_usage_percent ?? 0}%`} sub={`${overview?.capacity.memory_gb ?? 0} GB`} color="var(--teal2)" />
        <Metric label="Pods" value={overview?.workloads.pods ?? 0} sub={`${overview?.workloads.failed ?? 0} en erreur`} color="var(--red)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.45fr 0.75fr', gap: 12, marginBottom: 18 }}>
        <div className="panel" style={{ padding: 18 }}>
          <div style={{ fontWeight: 800, marginBottom: 14 }}>Taux par node</div>
          <ResponsiveContainer width="100%" height={230}>
            <BarChart data={nodeBars}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.08)" />
              <XAxis dataKey="name" tick={{ fill: 'var(--text3)', fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: 'var(--text3)', fontSize: 10 }} tickFormatter={v => `${v}%`} />
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)' }} />
              <Bar dataKey="cpu" fill="var(--yellow)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="mem" fill="var(--teal2)" radius={[4, 4, 0, 0]} />
              <Bar dataKey="pods" fill="var(--blue2)" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <div style={{ fontWeight: 800, marginBottom: 14 }}>Disponibilite nodes</div>
          <ResponsiveContainer width="100%" height={150}>
            <PieChart>
              <Pie data={nodeStatus} cx="50%" cy="50%" innerRadius={42} outerRadius={64} dataKey="value" paddingAngle={3}>
                {nodeStatus.map((d, i) => <Cell key={i} fill={d.color} />)}
              </Pie>
              <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)' }} />
            </PieChart>
          </ResponsiveContainer>
          <div style={{ display: 'grid', gap: 8 }}>
            {nodeStatus.map(d => (
              <div key={d.name} style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text2)', fontSize: 12 }}>
                <span>{d.name}</span><strong>{d.value}</strong>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '0.85fr 1.15fr', gap: 12 }}>
        <div className="panel" style={{ padding: 18 }}>
          <div style={{ fontWeight: 800, marginBottom: 14 }}>Mesures de pilotage</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {measurements?.rates.map(rate => {
              const critical = rate.unit === '%' ? rate.value >= rate.target && rate.name !== 'Disponibilite nodes' : rate.value > rate.target
              const okAvailability = rate.name === 'Disponibilite nodes' && rate.value >= rate.target
              const color = okAvailability ? 'var(--green)' : critical ? 'var(--red)' : 'var(--blue2)'
              return (
                <div key={rate.name}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: 'var(--text2)', marginBottom: 5 }}>
                    <span>{rate.name}</span>
                    <strong style={{ color }}>{rate.value}{rate.unit}</strong>
                  </div>
                  <div className="progress-bar" style={{ height: 6 }}>
                    <div className="progress-fill" style={{ width: `${Math.min(rate.value, 100)}%`, background: color }} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        <div className="panel" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '14px 18px', borderBottom: '1px solid var(--border)', fontWeight: 800 }}>Nodes du cluster</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                {['Node', 'Role', 'Status', 'CPU', 'RAM', 'Pods', 'Pression'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', fontSize: 11, color: 'var(--text3)', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {nodes.map(n => (
                <tr key={n.name} style={{ borderTop: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '10px 12px', fontWeight: 700, fontSize: 12 }}>{n.name}</td>
                  <td style={{ padding: '10px 12px', color: 'var(--text2)', fontSize: 12 }}>{n.role}</td>
                  <td style={{ padding: '10px 12px' }}><span className={`badge badge-${n.status === 'Ready' ? 'running' : 'critical'}`}>{n.status}</span></td>
                  <td style={{ padding: '10px 12px', minWidth: 92 }}>
                    <div className="progress-bar"><div className={`progress-fill ${fill(n.cpu_usage_percent)}`} style={{ width: `${n.cpu_usage_percent ?? 0}%` }} /></div>
                  </td>
                  <td style={{ padding: '10px 12px', minWidth: 92 }}>
                    <div className="progress-bar"><div className={`progress-fill ${fill(n.memory_usage_percent)}`} style={{ width: `${n.memory_usage_percent ?? 0}%` }} /></div>
                  </td>
                  <td style={{ padding: '10px 12px', color: 'var(--text2)', fontSize: 12 }}>{n.pods_used}/{n.pods_capacity}</td>
                  <td style={{ padding: '10px 12px', fontSize: 12 }}>
                    {n.disk_pressure || n.memory_pressure ? <span className="badge badge-warning">pression</span> : <span className="badge badge-running">normal</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
