import { useEffect, useMemo, useState } from 'react'
import { getAlerts, getKubernetesCluster, getKubernetesNodes, getPods, getVMs } from '../api/client'
import type { Alert, KubernetesClusterOverview, KubernetesNode, Pod, VM } from '../types'

type NodeState = 'healthy' | 'warning' | 'critical' | 'offline'

interface MapNode {
  id: string
  label: string
  sub: string
  layer: string
  x: number
  y: number
  state: NodeState
  metric?: string
}

const stateColor: Record<NodeState, string> = {
  healthy: '#22c55e',
  warning: '#f59e0b',
  critical: '#ef4444',
  offline: '#64748b',
}

const stateBg: Record<NodeState, string> = {
  healthy: 'rgba(34,197,94,0.13)',
  warning: 'rgba(245,158,11,0.16)',
  critical: 'rgba(239,68,68,0.16)',
  offline: 'rgba(100,116,139,0.16)',
}

function vmState(vm: VM, alerts: Alert[]): NodeState {
  if (vm.status === 'ERROR') return 'critical'
  if (vm.status !== 'ACTIVE') return 'offline'
  if (alerts.some(a => a.vm_id === vm.id && a.severity === 'critical')) return 'critical'
  if ((vm.cpu_percent ?? 0) >= 85 || (vm.ram_percent ?? 0) >= 85) return 'warning'
  if (alerts.some(a => a.vm_id === vm.id)) return 'warning'
  return 'healthy'
}

function podState(pod: Pod, alerts: Alert[]): NodeState {
  if (pod.status === 'Failed' || pod.status === 'Unknown') return 'critical'
  if (pod.status !== 'Running') return 'warning'
  if (alerts.some(a => a.pod_id === pod.id && a.severity === 'critical')) return 'critical'
  if (pod.restart_count >= 5) return 'warning'
  return 'healthy'
}

function nodeState(node: KubernetesNode): NodeState {
  if (node.status !== 'Ready') return 'critical'
  if (node.disk_pressure || node.memory_pressure) return 'critical'
  if ((node.cpu_usage_percent ?? 0) >= 80 || (node.memory_usage_percent ?? 0) >= 80) return 'warning'
  return 'healthy'
}

function StatusPill({ state }: { state: NodeState }) {
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: 6,
      padding: '3px 7px',
      borderRadius: 999,
      fontSize: 10,
      fontWeight: 800,
      textTransform: 'uppercase',
      color: stateColor[state],
      background: stateBg[state],
      border: `1px solid ${stateColor[state]}44`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: 99, background: stateColor[state], boxShadow: `0 0 10px ${stateColor[state]}` }} />
      {state}
    </span>
  )
}

function InfraNode({ node }: { node: MapNode }) {
  return (
    <div style={{
      position: 'absolute',
      left: `${node.x}%`,
      top: `${node.y}%`,
      transform: 'translate(-50%, -50%)',
      width: 150,
      minHeight: 76,
      padding: '10px 11px',
      borderRadius: 10,
      background: 'linear-gradient(180deg, rgba(15,23,42,0.96), rgba(30,41,59,0.94))',
      border: `1px solid ${stateColor[node.state]}80`,
      boxShadow: `0 0 0 1px rgba(255,255,255,0.04), 0 14px 32px rgba(2,6,23,0.35), 0 0 24px ${stateColor[node.state]}22`,
      color: '#e5edf7',
      zIndex: 3,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start', marginBottom: 7 }}>
        <div style={{ fontSize: 12, fontWeight: 900, lineHeight: 1.15, wordBreak: 'break-word' }}>{node.label}</div>
        <span style={{ width: 10, height: 10, borderRadius: 99, flex: '0 0 auto', background: stateColor[node.state], boxShadow: `0 0 14px ${stateColor[node.state]}` }} />
      </div>
      <div style={{ fontSize: 10, color: '#94a3b8', marginBottom: 8, lineHeight: 1.25 }}>{node.sub}</div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
        <StatusPill state={node.state} />
        {node.metric && <span style={{ fontSize: 10, color: '#cbd5e1', fontWeight: 700 }}>{node.metric}</span>}
      </div>
    </div>
  )
}

function LinkLayer({ nodes }: { nodes: MapNode[] }) {
  const lines = [
    ['edge', 'openstack'],
    ['edge', 'kubernetes'],
    ['openstack', 'observability'],
    ['kubernetes', 'observability'],
    ['observability', 'noc'],
  ]

  const byLayer = nodes.reduce<Record<string, MapNode>>((acc, n) => {
    if (!acc[n.layer]) acc[n.layer] = n
    return acc
  }, {})

  return (
    <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', zIndex: 1, pointerEvents: 'none' }}>
      <defs>
        <linearGradient id="mapLine" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.15" />
          <stop offset="55%" stopColor="#22d3ee" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.15" />
        </linearGradient>
      </defs>
      {lines.map(([from, to]) => {
        const a = byLayer[from]
        const b = byLayer[to]
        if (!a || !b) return null
        const danger = a.state === 'critical' || b.state === 'critical'
        return (
          <line
            key={`${from}-${to}`}
            x1={`${a.x}%`}
            y1={`${a.y}%`}
            x2={`${b.x}%`}
            y2={`${b.y}%`}
            stroke={danger ? '#ef4444' : 'url(#mapLine)'}
            strokeWidth={danger ? 2.5 : 1.5}
            strokeDasharray={danger ? '6 5' : 'none'}
            opacity={danger ? 0.82 : 0.7}
          />
        )
      })}
    </svg>
  )
}

export default function InfrastructureMapPage() {
  const [vms, setVMs] = useState<VM[]>([])
  const [pods, setPods] = useState<Pod[]>([])
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [cluster, setCluster] = useState<KubernetesClusterOverview | null>(null)
  const [k8sNodes, setK8sNodes] = useState<KubernetesNode[]>([])

  const load = async () => {
    const [vmData, podData, alertData, clusterData, nodeData] = await Promise.all([
      getVMs(),
      getPods(),
      getAlerts('active'),
      getKubernetesCluster(),
      getKubernetesNodes(),
    ])
    setVMs(vmData)
    setPods(podData)
    setAlerts(alertData)
    setCluster(clusterData)
    setK8sNodes(nodeData)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [])

  const damaged = useMemo(() => {
    const vmItems = vms
      .map(vm => ({ type: 'VM', id: vm.id, name: vm.name, place: vm.host || 'compute inconnu', state: vmState(vm, alerts), detail: `${vm.cpu_percent?.toFixed(0) ?? 0}% CPU / ${vm.ram_percent?.toFixed(0) ?? 0}% RAM` }))
      .filter(i => i.state !== 'healthy')
    const podItems = pods
      .map(pod => ({ type: 'Pod', id: pod.id, name: pod.name, place: `${pod.namespace} / ${pod.node || 'node inconnu'}`, state: podState(pod, alerts), detail: `${pod.status}, ${pod.restart_count} restarts` }))
      .filter(i => i.state !== 'healthy')
    const nodeItems = k8sNodes
      .map(n => ({ type: 'Node', id: n.name, name: n.name, place: n.role, state: nodeState(n), detail: `${n.cpu_usage_percent ?? 0}% CPU / ${n.memory_usage_percent ?? 0}% RAM` }))
      .filter(i => i.state !== 'healthy')
    return [...nodeItems, ...vmItems, ...podItems].sort((a, b) => a.state === 'critical' ? -1 : b.state === 'critical' ? 1 : 0)
  }, [alerts, k8sNodes, pods, vms])

  const nodes = useMemo<MapNode[]>(() => {
    const criticalAlerts = alerts.filter(a => a.severity === 'critical').length
    const openStackState: NodeState = vms.some(vm => vmState(vm, alerts) === 'critical') ? 'critical' : vms.some(vm => vmState(vm, alerts) === 'warning') ? 'warning' : 'healthy'
    const k8sState: NodeState = (cluster?.risk.pressure_nodes ?? 0) > 0 || pods.some(p => podState(p, alerts) === 'critical') ? 'critical' : pods.some(p => podState(p, alerts) === 'warning') ? 'warning' : 'healthy'
    const obsState: NodeState = criticalAlerts > 0 ? 'critical' : alerts.length > 0 ? 'warning' : 'healthy'

    return [
      { id: 'edge', label: 'Acces & Users', sub: 'Entree services CIRES', layer: 'edge', x: 12, y: 45, state: 'healthy', metric: 'LIVE' },
      { id: 'openstack', label: 'OpenStack', sub: `${vms.filter(v => v.status === 'ACTIVE').length}/${vms.length} VMs actives`, layer: 'openstack', x: 33, y: 30, state: openStackState, metric: `${vms.filter(v => vmState(v, alerts) !== 'healthy').length} impact` },
      { id: 'kubernetes', label: 'Kubernetes', sub: `${cluster?.capacity.ready_nodes ?? 0}/${cluster?.capacity.nodes ?? 0} nodes ready`, layer: 'kubernetes', x: 33, y: 64, state: k8sState, metric: `${cluster?.workloads.failed ?? 0} pods KO` },
      { id: 'observability', label: 'Observability', sub: 'Grafana, logs, metrics, traces', layer: 'observability', x: 62, y: 47, state: obsState, metric: `${alerts.length} alertes` },
      { id: 'noc', label: 'NOC & AI Agent', sub: 'Decision, triage, remediation', layer: 'noc', x: 86, y: 47, state: obsState, metric: `${cluster?.cluster.health_score ?? 0}/100` },
    ]
  }, [alerts, cluster, pods, vms])

  const counts = {
    critical: damaged.filter(d => d.state === 'critical').length,
    warning: damaged.filter(d => d.state === 'warning').length,
    offline: damaged.filter(d => d.state === 'offline').length,
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>Vue globale de l'infrastructure</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>Schema des composants, emplacement des elements endommages et impact operationnel.</div>
        </div>
        <button className="btn" onClick={load}>Rafraichir</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, marginBottom: 16 }}>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Health Score</div><div style={{ fontSize: 26, fontWeight: 900, color: 'var(--blue2)' }}>{cluster?.cluster.health_score ?? 0}/100</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Critiques</div><div style={{ fontSize: 26, fontWeight: 900, color: 'var(--red)' }}>{counts.critical}</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Warnings</div><div style={{ fontSize: 26, fontWeight: 900, color: 'var(--yellow)' }}>{counts.warning}</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Hors service</div><div style={{ fontSize: 26, fontWeight: 900, color: 'var(--text2)' }}>{counts.offline}</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1.45fr) minmax(320px, 0.55fr)', gap: 14 }}>
        <section style={{
          position: 'relative',
          minHeight: 560,
          overflow: 'hidden',
          borderRadius: 10,
          border: '1px solid #1e293b',
          background: '#020617',
          boxShadow: '0 18px 50px rgba(2,6,23,0.22)',
        }}>
          <div style={{
            position: 'absolute',
            inset: 0,
            backgroundImage: 'linear-gradient(rgba(56,189,248,0.08) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.08) 1px, transparent 1px)',
            backgroundSize: '34px 34px',
            opacity: 0.75,
          }} />
          <div style={{ position: 'absolute', left: 18, top: 16, color: '#e2e8f0', zIndex: 4 }}>
            <div style={{ fontSize: 13, fontWeight: 900 }}>Infrastructure Map</div>
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 3 }}>{cluster?.cluster.provider ?? 'Cloud'} - {cluster?.cluster.mode ?? 'mock'}</div>
          </div>
          <LinkLayer nodes={nodes} />
          {nodes.map(node => <InfraNode key={node.id} node={node} />)}
          <div style={{ position: 'absolute', left: '26%', right: '28%', top: '13%', bottom: '16%', border: '1px dashed rgba(125,211,252,0.18)', borderRadius: 18, zIndex: 0 }} />
          <div style={{ position: 'absolute', right: 18, bottom: 16, display: 'flex', gap: 10, zIndex: 4 }}>
            {(['healthy', 'warning', 'critical', 'offline'] as NodeState[]).map(s => <StatusPill key={s} state={s} />)}
          </div>
        </section>

        <aside className="panel" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
            <div style={{ fontWeight: 900 }}>Composants endommages</div>
            <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 3 }}>Emplacement exact et etat courant</div>
          </div>
          <div style={{ maxHeight: 560, overflow: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
            {damaged.length === 0 && <div style={{ color: 'var(--text3)', textAlign: 'center', padding: 28 }}>Aucun composant endommage</div>}
            {damaged.map(item => (
              <div key={`${item.type}-${item.id}`} style={{ padding: 12, borderRadius: 8, border: `1px solid ${stateColor[item.state]}55`, background: stateBg[item.state] }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, alignItems: 'flex-start', marginBottom: 7 }}>
                  <div>
                    <div style={{ fontWeight: 900, fontSize: 13 }}>{item.name}</div>
                    <div style={{ color: 'var(--text3)', fontSize: 11 }}>{item.type} - {item.id}</div>
                  </div>
                  <StatusPill state={item.state} />
                </div>
                <div style={{ fontSize: 12, color: 'var(--text2)', marginBottom: 4 }}>Emplacement: <strong>{item.place}</strong></div>
                <div style={{ fontSize: 12, color: 'var(--text2)' }}>Mesure: <strong>{item.detail}</strong></div>
              </div>
            ))}
          </div>
        </aside>
      </div>
    </div>
  )
}
