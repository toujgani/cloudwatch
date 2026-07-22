import { useEffect, useState } from 'react'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cloudwatch-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface UserEntry {
  id: number
  username: string
  role: string
  is_active: boolean
  created_at: string | null
}

interface AiHistoryEntry {
  alert_id: number
  title: string
  severity: string
  ai_score: number | null
  ai_decision: string | null
  ai_confidence: number | null
  remediation_action: string | null
  remediation_status: string | null
  remediation_message: string | null
  executed_at: string | null
}

interface AuditEntry {
  id: number
  action: string
  actor: string
  resource_type: string | null
  resource_id: string | null
  detail: string | null
  created_at: string | null
}

interface AdminStats {
  users: { total: number; active: number }
  alerts: { total: number; remediations_applied: number }
  audit: { total_entries: number }
  ai: { actions_today: number }
}

export default function AdminPage() {
  const [users, setUsers] = useState<UserEntry[]>([])
  const [aiHistory, setAiHistory] = useState<AiHistoryEntry[]>([])
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([])
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [tab, setTab] = useState<'overview' | 'users' | 'ai' | 'audit'>('overview')
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [s, u, ai, audit] = await Promise.all([
        api.get('/admin/stats'),
        api.get('/admin/users'),
        api.get('/admin/ai-history?limit=30'),
        api.get('/admin/audit?limit=50'),
      ])
      setStats(s.data)
      setUsers(u.data)
      setAiHistory(ai.data)
      setAuditLog(audit.data)
      setError('')
    } catch (e: any) {
      if (e?.response?.status === 403) setError('Acces refuse. Seuls les administrateurs peuvent voir cette page.')
      else setError('Erreur de chargement.')
    }
  }

  useEffect(() => { load() }, [])

  const changeRole = async (userId: number, role: string) => {
    await api.patch(`/admin/users/${userId}/role?role=${role}`)
    load()
  }

  const toggleActive = async (userId: number, active: boolean) => {
    await api.patch(`/admin/users/${userId}/${active ? 'enable' : 'disable'}`)
    load()
  }

  if (error) {
    return (
      <div style={{ padding: '40px 24px', textAlign: 'center' }}>
        <div style={{ fontSize: 16, color: 'var(--red)', fontWeight: 700 }}>{error}</div>
      </div>
    )
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Administration</h2>
      <div style={{ color: 'var(--text3)', fontSize: 12, marginBottom: 18 }}>
        Gestion des utilisateurs, historique IA, audit systeme
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {(['overview', 'users', 'ai', 'audit'] as const).map(t => (
          <button key={t} className={tab === t ? 'btn btn-primary' : 'btn'} onClick={() => setTab(t)} style={{ fontSize: 12 }}>
            {t === 'overview' ? 'Vue globale' : t === 'users' ? 'Utilisateurs' : t === 'ai' ? 'Historique IA' : 'Audit'}
          </button>
        ))}
      </div>

      {/* Overview */}
      {tab === 'overview' && stats && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Utilisateurs</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--blue2)' }}>{stats.users.active}/{stats.users.total}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>actifs</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Alertes totales</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--yellow)' }}>{stats.alerts.total}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>{stats.alerts.remediations_applied} remediees</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Actions IA (24h)</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--green)' }}>{stats.ai.actions_today}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>remediations automatiques</div>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase', marginBottom: 6 }}>Entrees audit</div>
            <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--teal2)' }}>{stats.audit.total_entries}</div>
            <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 4 }}>total enregistrees</div>
          </div>
        </div>
      )}

      {/* Users */}
      {tab === 'users' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['ID', 'Utilisateur', 'Role', 'Actif', 'Cree le', 'Actions'].map(h => (
                  <th key={h} style={{ fontSize: 11, color: 'var(--text3)', padding: '10px 12px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 12 }}>{u.id}</td>
                  <td style={{ padding: '10px 12px', fontSize: 12, fontWeight: 600 }}>{u.username}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <select value={u.role} onChange={e => changeRole(u.id, e.target.value)}
                      style={{ background: 'var(--bg3)', border: '1px solid var(--border2)', borderRadius: 4, padding: '3px 6px', fontSize: 11, color: 'var(--text)' }}>
                      <option value="admin">admin</option>
                      <option value="operator">operator</option>
                      <option value="viewer">viewer</option>
                    </select>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ color: u.is_active ? 'var(--green)' : 'var(--red)', fontWeight: 600, fontSize: 11 }}>
                      {u.is_active ? 'Actif' : 'Desactive'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text3)' }}>
                    {u.created_at ? new Date(u.created_at).toLocaleDateString('fr-FR') : '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <button className="btn" onClick={() => toggleActive(u.id, !u.is_active)}
                      style={{ fontSize: 10, padding: '3px 8px', color: u.is_active ? 'var(--red)' : 'var(--green)' }}>
                      {u.is_active ? 'Desactiver' : 'Activer'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* AI History */}
      {tab === 'ai' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['ID', 'Titre', 'Severite', 'Score', 'Decision', 'Action', 'Statut', 'Date'].map(h => (
                  <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '8px 10px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {aiHistory.map(a => (
                <tr key={a.alert_id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>#{a.alert_id}</td>
                  <td style={{ padding: '8px 10px', fontSize: 11, fontWeight: 500, maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: a.severity === 'critical' ? 'var(--red)' : a.severity === 'warning' ? 'var(--yellow)' : 'var(--text3)' }}>
                      {a.severity?.toUpperCase()}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 11, fontWeight: 700 }}>{a.ai_score ?? '—'}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10 }}>{a.ai_decision ?? '—'}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10 }}>{a.remediation_action ?? '—'}</td>
                  <td style={{ padding: '8px 10px' }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: a.remediation_status === 'applied' ? 'var(--green)' : a.remediation_status === 'blocked' ? 'var(--red)' : 'var(--text3)' }}>
                      {a.remediation_status ?? '—'}
                    </span>
                  </td>
                  <td style={{ padding: '8px 10px', fontSize: 10, color: 'var(--text3)' }}>
                    {a.executed_at ? new Date(a.executed_at).toLocaleString('fr-FR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Audit Log */}
      {tab === 'audit' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['ID', 'Action', 'Acteur', 'Ressource', 'Detail', 'Date'].map(h => (
                  <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '8px 10px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {auditLog.map(e => (
                <tr key={e.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>#{e.id}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10, fontWeight: 600, color: 'var(--blue2)' }}>{e.action}</td>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>{e.actor}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10, color: 'var(--text3)' }}>{e.resource_type ? `${e.resource_type}/${e.resource_id}` : '—'}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10, color: 'var(--text2)', maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.detail || '—'}</td>
                  <td style={{ padding: '8px 10px', fontSize: 10, color: 'var(--text3)' }}>
                    {e.created_at ? new Date(e.created_at).toLocaleString('fr-FR') : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
