import { useEffect, useState } from 'react'
import { getPods, deletePod } from '../api/client'
import type { Pod } from '../types'

export default function PodsPage() {
  const [pods, setPods]           = useState<Pod[]>([])
  const [nsFilter, setNsFilter]   = useState('')
  const [search, setSearch]       = useState('')
  const [deleting, setDeleting]   = useState<string | null>(null)

  const loadPods = () => getPods().then(setPods)

  useEffect(() => {
    loadPods()
    const t = setInterval(loadPods, 30_000)
    return () => clearInterval(t)
  }, [])

  const handleDelete = async (podId: string, podName: string) => {
    if (!window.confirm(`Supprimer le pod "${podName}" ?\nLe controller le recreera si un Deployment existe.`)) return
    setDeleting(podId)
    try {
      await deletePod(podId)
      alert(`Pod "${podName}" supprime avec succes.`)
      loadPods()
    } catch (e: any) {
      alert(`Erreur: ${e?.response?.data?.detail || e.message}`)
    } finally {
      setDeleting(null)
    }
  }

  const namespaces = [...new Set(pods.map(p => p.namespace))].sort()

  const filtered = pods.filter(p =>
    (!nsFilter || p.namespace === nsFilter) &&
    (!search   || p.name.toLowerCase().includes(search.toLowerCase()))
  )

  const stats = {
    running: pods.filter(p => p.status === 'Running').length,
    pending: pods.filter(p => p.status === 'Pending').length,
    failed:  pods.filter(p => ['Failed','Unknown'].includes(p.status)).length,
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}> Pods OpenShift</h2>

      {/* Stats row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {[
          { l: 'Running', v: stats.running, c: 'var(--green)' },
          { l: 'Pending', v: stats.pending, c: 'var(--yellow)' },
          { l: 'Failed',  v: stats.failed,  c: 'var(--red)' },
          { l: 'Total',   v: pods.length,    c: 'var(--blue2)' },
        ].map(s => (
          <div key={s.l} style={{
            background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 8,
            padding: '10px 16px', minWidth: 90,
          }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.c }}>{s.v}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', letterSpacing: '0.8px' }}>{s.l}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14 }}>
        <input
          placeholder="Rechercher un pod…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          style={{
            background: 'var(--card)', border: '1px solid var(--border2)',
            color: 'var(--text)', borderRadius: 6, padding: '7px 12px', fontSize: 12, width: 220,
          }}
        />
        <select
          value={nsFilter}
          onChange={e => setNsFilter(e.target.value)}
          style={{
            background: 'var(--card)', border: '1px solid var(--border2)',
            color: 'var(--text)', borderRadius: 6, padding: '7px 12px', fontSize: 12,
          }}
        >
          <option value="">Tous les namespaces</option>
          {namespaces.map(ns => <option key={ns} value={ns}>{ns}</option>)}
        </select>
      </div>

      {/* Table */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Nom','Namespace','Statut','Noeud','Restarts','CPU (m)','RAM (MB)','Actions'].map(h => (
                <th key={h} style={{ fontSize: 11, color: 'var(--text3)', padding: '10px 12px', textAlign: 'left', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map(pod => (
              <tr key={pod.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                <td style={{ padding: '10px 12px', fontWeight: 500, color: 'var(--text)', fontSize: 12 }}>{pod.name}</td>
                <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text3)' }}>{pod.namespace}</td>
                <td style={{ padding: '10px 12px' }}>
                  <span className={`badge badge-${pod.status.toLowerCase()}`}>{pod.status}</span>
                </td>
                <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text3)' }}>{pod.node ?? '—'}</td>
                <td style={{ padding: '10px 12px', fontSize: 12,
                  color: pod.restart_count >= 5 ? 'var(--red)' : pod.restart_count > 0 ? 'var(--yellow)' : 'var(--text2)',
                  fontWeight: pod.restart_count >= 5 ? 700 : 400,
                }}>{pod.restart_count}</td>
                <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--teal2)' }}>
                  {pod.cpu_millicores != null ? pod.cpu_millicores.toFixed(0) : '—'}
                </td>
                <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--blue2)' }}>
                  {pod.ram_mb != null ? pod.ram_mb.toFixed(0) : '—'}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <button
                    className="btn"
                    disabled={deleting === pod.id}
                    onClick={() => handleDelete(pod.id, pod.name)}
                    style={{ fontSize: 10, padding: '4px 8px', color: 'var(--red)', borderColor: 'var(--red)' }}
                  >
                    {deleting === pod.id ? '...' : 'Supprimer'}
                  </button>
                </td>
              </tr>
            ))}
            {filtered.length === 0 && (
              <tr><td colSpan={8} style={{ padding: 24, textAlign: 'center', color: 'var(--text3)' }}>Aucun pod trouvé</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
