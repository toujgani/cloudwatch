import { useEffect, useState } from 'react'
import axios from 'axios'

const api = axios.create({ baseURL: '/api' })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('cloudwatch-token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

interface UserEntry {
  id: number; username: string; role: string; is_active: boolean
  is_locked: boolean; force_password_change: boolean; failed_login_count: number
  last_login_at: string | null; last_activity_at: string | null
  created_at: string | null; active_sessions: number
  last_ip: string | null; last_browser: string | null; last_os: string | null
}

interface SessionEntry {
  id: number; username: string; role: string; ip_address: string | null
  user_agent: string | null; browser: string | null; os: string | null
  login_at: string | null; last_activity: string | null; is_active: boolean
}

type Tab = 'users' | 'sessions'

export default function AdminPage() {
  const [users, setUsers] = useState<UserEntry[]>([])
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [tab, setTab] = useState<Tab>('users')
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [passwordResult, setPasswordResult] = useState<any>(null)

  const load = async () => {
    try {
      const [u, sess] = await Promise.allSettled([
        api.get('/admin/users'),
        api.get('/admin/sessions?limit=50'),
      ])
      if (u.status === 'rejected' && u.reason?.response?.status === 403) {
        setError('Acces refuse. Admin uniquement.')
        return
      }
      if (u.status === 'fulfilled') setUsers(u.value.data)
      if (sess.status === 'fulfilled') setSessions(sess.value.data)
      setError('')
    } catch {
      setError('Erreur de chargement.')
    }
  }

  useEffect(() => { load() }, [])

  const createUser = async (username: string, role: string) => {
    try {
      const res = await api.post('/admin/users', { username, role })
      setPasswordResult(res.data); load()
    } catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const deleteUser = async (id: number) => {
    if (!confirm('Supprimer cet utilisateur?')) return
    try { await api.delete(`/admin/users/${id}`); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const toggleActive = async (id: number, active: boolean) => {
    try {
      await api.patch(`/admin/users/${id}/${active ? 'enable' : 'disable'}`)
      load()
    } catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const unlockUser = async (id: number) => {
    try { await api.patch(`/admin/users/${id}/unlock`); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const changeRole = async (id: number, role: string) => {
    try { await api.patch(`/admin/users/${id}/role`, { role }); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const resetPassword = async (id: number) => {
    try {
      const res = await api.patch(`/admin/users/${id}/password`, { force_change: true })
      setPasswordResult(res.data)
    } catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  if (error) return (
    <div style={{ padding: '40px 24px', textAlign: 'center' }}>
      <div style={{ fontSize: 16, color: 'var(--red)', fontWeight: 700 }}>{error}</div>
    </div>
  )

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>Administration</h2>
        <div style={{ color: 'var(--text3)', fontSize: 12 }}>
          Gestion des utilisateurs et sessions actives
        </div>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 18 }}>
        {([['users', 'Utilisateurs'], ['sessions', 'Sessions actives']] as const).map(([t, label]) => (
          <button key={t} className={tab === t ? 'btn btn-primary' : 'btn'} onClick={() => setTab(t)} style={{ fontSize: 12 }}>
            {label}
          </button>
        ))}
      </div>

      {/* Password Result Modal */}
      {passwordResult && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--card)', borderRadius: 12, padding: 24, maxWidth: 400, width: '90%', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: 12, fontSize: 16, fontWeight: 700 }}>Identifiants</h3>
            <div style={{ marginBottom: 8, fontSize: 13 }}>
              <strong>Utilisateur:</strong> {passwordResult.username}
            </div>
            <div style={{ marginBottom: 8, fontSize: 13 }}>
              <strong>Mot de passe:</strong>{' '}
              <code style={{ background: 'var(--bg3)', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>
                {passwordResult.temporary_password}
              </code>
            </div>
            <div style={{ marginBottom: 12, fontSize: 11, color: 'var(--text3)' }}>
              L'utilisateur devra changer son mot de passe a la prochaine connexion.
            </div>
            <button className="btn btn-primary" onClick={() => {
              navigator.clipboard.writeText(passwordResult.temporary_password || '')
              setPasswordResult(null)
            }}>Copier & Fermer</button>
          </div>
        </div>
      )}

      {/* Users Tab */}
      {tab === 'users' && (
        <div>
          <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
            <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)} style={{ fontSize: 12 }}>
              + Creer un utilisateur
            </button>
          </div>
          {showCreate && <CreateUserForm onCreate={createUser} onClose={() => setShowCreate(false)} />}
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 850 }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border)' }}>
                  {['Utilisateur', 'Role', 'Statut', 'Derniere connexion', 'IP', 'Sessions', 'Actions'].map(h => (
                    <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '10px 10px', textAlign: 'left', textTransform: 'uppercase' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderBottom: '1px solid rgba(99,130,255,0.06)' }}>
                    <td style={{ padding: '10px', fontSize: 12, fontWeight: 600 }}>{u.username}</td>
                    <td style={{ padding: '10px' }}>
                      {u.role === 'admin' ? (
                        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--red)' }}>ADMIN</span>
                      ) : (
                        <select value={u.role} onChange={e => changeRole(u.id, e.target.value)}
                          style={{ fontSize: 10, padding: '2px 4px', borderRadius: 4, border: '1px solid var(--border)', background: 'var(--bg3)', color: 'var(--text)' }}>
                          <option value="subadmin">Sub-Admin</option>
                          <option value="operator">Operateur</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      )}
                    </td>
                    <td style={{ padding: '10px' }}>
                      <span style={{ fontSize: 10, fontWeight: 600, color: u.is_locked ? 'var(--red)' : u.is_active ? 'var(--green)' : 'var(--text3)' }}>
                        {u.is_locked ? '🔒 Verrouille' : u.is_active ? '✓ Actif' : '✗ Desactive'}
                      </span>
                      {u.failed_login_count > 0 && <span style={{ fontSize: 9, color: 'var(--red)', marginLeft: 4 }}>({u.failed_login_count} echecs)</span>}
                    </td>
                    <td style={{ padding: '10px', fontSize: 10, color: 'var(--text3)' }}>
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString('fr-FR') : '—'}
                    </td>
                    <td style={{ padding: '10px', fontSize: 10, fontFamily: 'monospace' }}>{u.last_ip || '—'}</td>
                    <td style={{ padding: '10px', fontSize: 11, fontWeight: 600, color: 'var(--blue2)' }}>{u.active_sessions}</td>
                    <td style={{ padding: '10px', display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                      {u.role !== 'admin' && (
                        <>
                          <button className="btn" onClick={() => toggleActive(u.id, !u.is_active)} style={{ fontSize: 9, padding: '2px 6px', color: u.is_active ? 'var(--red)' : 'var(--green)' }}>
                            {u.is_active ? 'Desactiver' : 'Activer'}
                          </button>
                          {u.is_locked && <button className="btn" onClick={() => unlockUser(u.id)} style={{ fontSize: 9, padding: '2px 6px', color: 'var(--blue2)' }}>Deverrouiller</button>}
                          <button className="btn" onClick={() => resetPassword(u.id)} style={{ fontSize: 9, padding: '2px 6px', color: 'var(--yellow)' }}>Reset MDP</button>
                          <button className="btn" onClick={() => deleteUser(u.id)} style={{ fontSize: 9, padding: '2px 6px', color: 'var(--red)' }}>Supprimer</button>
                        </>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center', color: 'var(--text3)', fontSize: 12 }}>Aucun utilisateur.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sessions Tab */}
      {tab === 'sessions' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Utilisateur', 'Role', 'Adresse IP', 'Navigateur', 'OS', 'Connexion', 'Statut'].map(h => (
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
                  <td style={{ padding: '10px 12px', fontSize: 10 }}>{s.browser || '—'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 10 }}>{s.os || '—'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 10, color: 'var(--text3)' }}>
                    {s.login_at ? new Date(s.login_at).toLocaleString('fr-FR') : '—'}
                  </td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={{ fontSize: 10, fontWeight: 600, color: s.is_active ? 'var(--green)' : 'var(--text3)' }}>
                      {s.is_active ? '● En ligne' : '○ Terminee'}
                    </span>
                  </td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr><td colSpan={7} style={{ padding: 20, textAlign: 'center', color: 'var(--text3)', fontSize: 12 }}>Aucune session.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

function CreateUserForm({ onCreate, onClose }: { onCreate: (u: string, r: string) => void; onClose: () => void }) {
  const [username, setUsername] = useState('')
  const [role, setRole] = useState('viewer')
  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 12 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 10, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Nom d'utilisateur</label>
          <input className="input" value={username} onChange={e => setUsername(e.target.value)} placeholder="username" style={{ width: 160 }} />
        </div>
        <div>
          <label style={{ fontSize: 10, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>Role</label>
          <select className="input" value={role} onChange={e => setRole(e.target.value)} style={{ width: 130 }}>
            <option value="viewer">Viewer</option>
            <option value="operator">Operateur</option>
            <option value="subadmin">Sub-Admin</option>
          </select>
        </div>
        <button className="btn btn-primary" onClick={() => { if (username.length >= 3) { onCreate(username, role); setUsername(''); onClose() } }} style={{ fontSize: 11 }}>
          Creer
        </button>
        <button className="btn" onClick={onClose} style={{ fontSize: 11 }}>Annuler</button>
      </div>
      <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 8 }}>
        Un mot de passe temporaire sera genere automatiquement. Le role "admin" ne peut pas etre attribue.
      </div>
    </div>
  )
}
