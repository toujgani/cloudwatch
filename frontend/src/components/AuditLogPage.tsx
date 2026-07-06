import { useEffect, useState } from 'react'
import { getAuditLogs, getAuditStats } from '../api/client'
import type { AuditLogEntry } from '../types'

const ACTION_COLOR: Record<string, string> = {
  alert_created: 'var(--red)',
  alert_acknowledged: 'var(--yellow)',
  alert_assigned: 'var(--blue2)',
  alert_resolved: 'var(--green)',
  remediation_triggered: 'var(--yellow)',
  remediation_applied: 'var(--green)',
  remediation_blocked: 'var(--red)',
  ai_analysis: 'var(--teal2)',
  collector_error: 'var(--red)',
  login: 'var(--text3)',
  logout: 'var(--text3)',
  settings_changed: 'var(--yellow)',
}

export default function AuditLogPage() {
  const [logs, setLogs]   = useState<AuditLogEntry[]>([])
  const [stats, setStats] = useState<Record<string, number>>({})
  const [filter, setFilter] = useState('')
  const [limit, setLimit]   = useState(100)

  const load = () => {
    getAuditLogs(limit).then(setLogs)
    getAuditStats().then(setStats)
  }

  useEffect(() => {
    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [limit])

  const filtered = filter
    ? logs.filter(e =>
        e.action.includes(filter) ||
        e.actor.toLowerCase().includes(filter.toLowerCase()) ||
        (e.detail || '').toLowerCase().includes(filter.toLowerCase())
      )
    : logs

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Audit Trail</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>Traçabilité complète de toutes les actions plateforme.</div>
        </div>
        <select className="input" value={limit} onChange={e => setLimit(Number(e.target.value))} style={{ width: 120 }}>
          {[50, 100, 200, 500].map(n => <option key={n} value={n}>{n} entrées</option>)}
        </select>
        <input className="input" placeholder="Filtrer..." value={filter} onChange={e => setFilter(e.target.value)} style={{ width: 200 }} />
      </div>

      {/* Stats bar */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
        {Object.entries(stats).sort((a, b) => b[1] - a[1]).map(([action, count]) => (
          <div key={action} style={{
            padding: '5px 10px', borderRadius: 6, background: 'var(--bg3)',
            border: '1px solid var(--border)', fontSize: 11,
          }}>
            <span style={{ color: ACTION_COLOR[action] ?? 'var(--text2)', fontFamily: 'monospace' }}>{action}</span>
            <span style={{ color: 'var(--text3)', marginLeft: 6 }}>{count}</span>
          </div>
        ))}
      </div>

      <div className="panel" style={{ overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['ID', 'Action', 'Acteur', 'Ressource', 'Détail', 'Horodatage'].map(h => (
                <th key={h} style={{ padding: '10px 12px', textAlign: 'left', color: 'var(--text3)', fontWeight: 500, fontSize: 11, textTransform: 'uppercase' }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr><td colSpan={6} style={{ textAlign: 'center', padding: 32, color: 'var(--text3)' }}>Aucune entrée</td></tr>
            )}
            {filtered.map(entry => (
              <tr key={entry.id} style={{ borderTop: '1px solid rgba(99,130,255,0.06)' }}>
                <td style={{ padding: '9px 12px', color: 'var(--text3)', fontFamily: 'monospace' }}>#{entry.id}</td>
                <td style={{ padding: '9px 12px' }}>
                  <span style={{ color: ACTION_COLOR[entry.action] ?? 'var(--text2)', fontFamily: 'monospace', fontWeight: 600, fontSize: 11 }}>
                    {entry.action}
                  </span>
                </td>
                <td style={{ padding: '9px 12px', color: 'var(--text2)', fontWeight: 500 }}>{entry.actor}</td>
                <td style={{ padding: '9px 12px', color: 'var(--text3)' }}>
                  {entry.resource_type && <span>{entry.resource_type} <strong style={{ color: 'var(--text2)' }}>#{entry.resource_id}</strong></span>}
                </td>
                <td style={{ padding: '9px 12px', color: 'var(--text2)', maxWidth: 320 }}>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{entry.detail}</div>
                </td>
                <td style={{ padding: '9px 12px', color: 'var(--text3)', whiteSpace: 'nowrap' }}>
                  {new Date(entry.created_at).toLocaleString('fr-FR')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
