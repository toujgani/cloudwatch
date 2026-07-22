import { useEffect, useState } from 'react'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cloudwatch-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface SessionEntry {
  id: number
  username: string
  role: string
  ip_address: string | null
  user_agent: string | null
  login_at: string | null
  is_active: boolean
}

interface UserEntry {
  id: number
  username: string
  role: string
  is_active: boolean
}

interface AiHistoryEntry {
  alert_id: number
  title: string
  severity: string
  ai_score: number | null
  ai_decision: string | null
  remediation_action: string | null
  remediation_status: string | null
  executed_at: string | null
}

export default function AdminPage() {
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [users, setUsers] = useState<UserEntry[]>([])
  const [aiHistory, setAiHistory] = useState<AiHistoryEntry[]>([])
  const [tab, setTab] = useState<'sessions' | 'users' | 'ai'>('sessions')
  const [error, setError] = useState('')

  const load = async () => {
    try {
      const [sess, u, ai] = await Promise.all([
        api.get('/admin/sessions?limit=50'),
        api.get('/admin/users'),
        api.get('/admin/ai-history?limit=20'),
      ])
      setSessions(sess.data)
      setUsers(u.data)
      setAiHistory(ai.data)
      setError('')
    } catch (e: any) {
      if (e?.response?.status === 403) setError('Acces refuse. Seuls les administrateurs peuvent voir cette page.')
      else setError('Erreur de chargement.')
    }
  }

  useEffect(() => { load() }, [])

  const toggleActive = async (userId: number, active: boolean) => {
    try {
      await api.patch(`/admin/users/${userId}/${active ? 'enable' : 'disable'}`)
      load()
    } catch (e: any) {
      alert(e?.response?.data?.detail || 'Erreur')
    }
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
        Sessions actives, gestion utilisateurs, historique IA
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {(['sessions', 'users', 'ai'] as const).map(t => (
          <button key={t} className={tab === t ? 'btn btn-primary' : 'btn'} onClick={() => setTab(t)} style={{ fontSize: 12 }}>
            {t === 'sessions' ? 'Sessions actives' : t === 'users' ? 'Utilisateurs' : 'Historique IA'}
          </button>
        ))}
      </div>

      {/* Sessions */}
      {tab === 'sessions' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Utilisateur', 'Role', 'Adresse IP', 'Navigateur', 'Connexion', 'Statut'].map(h => (
                  <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '10px 12px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sessions.map(s => (
                <tr key={s.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 12, fontWeight: 600 }}>{s.username}</td>
                  <td style={{ padding: '10px 12px', fontSize: 11 }}>{s.role}</td>
                  <td style={{ padding: '10px 12px', fontSize: 11, fontFamily: 'monospace' }}>{s.ip_address || '—'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 10, color: 'var(--text3)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {s.user_agent?.substring(0, 60) || '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 10, color: 'var(--text3)' }}>
                    {s.login_at ? new Date(s.login_at).toLocaleString('fr-FR') : '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: s.is_active ? 'var(--green)' : 'var(--text3)' }}>
                      {s.is_active ? 'Active' : 'Terminee'}
                    </span>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr><td colSpan={6} style={{ padding: 20, textAlign: 'center', color: 'var(--text3)', fontSize: 12 }}>Aucune session enregistree. Les sessions apparaissent apres connexion.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Users */}
      {tab === 'users' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['ID', 'Utilisateur', 'Role', 'Statut', 'Actions'].map(h => (
                  <th key={h} style={{ fontSize: 11, color: 'var(--text3)', padding: '10px 12px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '10px 12px', fontSize: 12 }}>{u.id}</td>
                  <td style={{ padding: '10px 12px', fontSize: 12, fontWeight: 600 }}>{u.username}</td>
                  <td style={{ padding: '10px 12px', fontSize: 11 }}>{u.role}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: u.is_active ? 'var(--green)' : 'var(--red)' }}>
                      {u.is_active ? 'Actif' : 'Desactive'}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    {u.role !== 'admin' && (
                      <button className="btn" onClick={() => toggleActive(u.id, !u.is_active)}
                        style={{ fontSize: 10, padding: '3px 8px', color: u.is_active ? 'var(--red)' : 'var(--green)' }}>
                        {u.is_active ? 'Desactiver' : 'Activer'}
                      </button>
                    )}
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
                {['ID', 'Titre', 'Severite', 'Score IA', 'Decision', 'Action', 'Statut', 'Date'].map(h => (
                  <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '8px 10px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {aiHistory.map(a => (
                <tr key={a.alert_id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                  <td style={{ padding: '8px 10px', fontSize: 11 }}>#{a.alert_id}</td>
                  <td style={{ padding: '8px 10px', fontSize: 11, fontWeight: 500, maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{a.title}</td>
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
              {aiHistory.length === 0 && (
                <tr><td colSpan={8} style={{ padding: 20, textAlign: 'center', color: 'var(--text3)', fontSize: 12 }}>Aucune action IA enregistree.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
