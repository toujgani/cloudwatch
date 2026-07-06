import { useEffect, useMemo, useState } from 'react'
import { getGrafanaLogs } from '../api/client'
import type { LogEntry } from '../types'

const levelColor: Record<string, string> = {
  info: 'var(--blue2)',
  warning: 'var(--yellow)',
  error: 'var(--red)',
  critical: 'var(--red)',
}

function levelBadge(level: string) {
  const normalized = level.toLowerCase()
  return normalized === 'critical' ? 'critical' : normalized === 'error' ? 'critical' : normalized === 'warning' ? 'warning' : 'info'
}

export default function LogsPage() {
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [source, setSource] = useState('')
  const [message, setMessage] = useState('')
  const [hours, setHours] = useState(1)
  const [level, setLevel] = useState('')
  const [service, setService] = useState('')
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState(false)

  const load = async () => {
    setBusy(true)
    try {
      const response = await getGrafanaLogs(undefined, hours, level || undefined, service || undefined, 200)
      setSource(response.source)
      setMessage(response.message || '')
      setLogs(response.logs || [])
    } catch (error) {
      setSource('error')
      setMessage('Impossible de charger les logs depuis le backend.')
      setLogs([])
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [hours, level])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return logs
    return logs.filter(log =>
      `${log.level} ${log.service} ${log.location} ${log.message} ${log.context || ''}`.toLowerCase().includes(q)
    )
  }, [logs, query])

  const stats = {
    total: filtered.length,
    critical: filtered.filter(l => ['critical', 'error'].includes(l.level)).length,
    warning: filtered.filter(l => l.level === 'warning').length,
    services: new Set(filtered.map(l => l.service)).size,
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 800, marginBottom: 6 }}>Logs applicatifs & infrastructure</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>
            Recherche et analyse des erreurs par service, VM, pod, namespace ou node.
          </div>
        </div>
        <button className="btn btn-primary" disabled={busy} onClick={load}>{busy ? 'Chargement...' : 'Rafraichir'}</button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 12, marginBottom: 16 }}>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Logs affiches</div><div style={{ color: 'var(--blue2)', fontSize: 26, fontWeight: 900 }}>{stats.total}</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Erreurs</div><div style={{ color: 'var(--red)', fontSize: 26, fontWeight: 900 }}>{stats.critical}</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Warnings</div><div style={{ color: 'var(--yellow)', fontSize: 26, fontWeight: 900 }}>{stats.warning}</div></div>
        <div className="panel" style={{ padding: 14 }}><div style={{ color: 'var(--text3)', fontSize: 11 }}>Services</div><div style={{ color: 'var(--green)', fontSize: 26, fontWeight: 900 }}>{stats.services}</div></div>
      </div>

      <div className="panel" style={{ padding: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {[1, 6, 24].map(h => (
            <button key={h} className={hours === h ? 'btn btn-primary' : 'btn'} onClick={() => setHours(h)}>
              {h}h
            </button>
          ))}
          <select className="input" value={level} onChange={e => setLevel(e.target.value)}>
            <option value="">Tous niveaux</option>
            <option value="critical">Critical</option>
            <option value="error">Error</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
          <input className="input" value={service} onChange={e => setService(e.target.value)} onBlur={load} placeholder="Service, VM ou pod" style={{ minWidth: 190 }} />
          <input className="input" value={query} onChange={e => setQuery(e.target.value)} placeholder="Recherche texte" style={{ flex: 1, minWidth: 220 }} />
          <span className="badge badge-info">{source || 'source'}</span>
        </div>
        {message && <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 8 }}>{message}</div>}
      </div>

      <div className="panel" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontWeight: 800 }}>Flux des logs</div>
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {filtered.length === 0 && <div style={{ padding: 32, textAlign: 'center', color: 'var(--text3)' }}>Aucun log trouve</div>}
          {filtered.map((log, index) => (
            <div key={`${log.timestamp}-${index}`} style={{
              display: 'grid',
              gridTemplateColumns: '155px 95px minmax(150px, 220px) minmax(140px, 190px) 1fr',
              gap: 12,
              padding: '10px 14px',
              borderTop: index === 0 ? 'none' : '1px solid rgba(99,130,255,0.08)',
              alignItems: 'start',
              background: ['critical', 'error'].includes(log.level) ? 'rgba(220,38,38,0.035)' : 'transparent',
            }}>
              <div style={{ color: 'var(--text3)', fontSize: 11 }}>{new Date(log.timestamp).toLocaleString('fr-FR')}</div>
              <div><span className={`badge badge-${levelBadge(log.level)}`} style={{ color: levelColor[log.level] || undefined }}>{log.level}</span></div>
              <div style={{ fontWeight: 800, fontSize: 12, color: 'var(--text)' }}>{log.service}</div>
              <div style={{ color: 'var(--text2)', fontSize: 12 }}>{log.location}</div>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text)' }}>{log.message}</div>
                {log.context && <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 3 }}>{log.context}</div>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
