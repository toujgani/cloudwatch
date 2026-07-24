import { useEffect, useState } from 'react'
import axios from 'axios'
import { getStoredToken, clearStoredToken } from '../api/client'

const api = axios.create({ baseURL: '/api' })

// Attach token to every request
api.interceptors.request.use((config) => {
  const token = getStoredToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  console.log(`[AdminPage REQUEST] ${config.method?.toUpperCase()} ${config.url} — Authorization: ${token ? 'Bearer ' + token.substring(0, 20) + '...' : 'NONE'}`)
  return config
})

// Handle 401 — log it but don't clear token (let the user see the error)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      console.error('[AdminPage] 401 received on:', error.config?.method?.toUpperCase(), error.config?.url)
      console.error('[AdminPage] Token at time of error:', getStoredToken() ? 'present (' + getStoredToken()!.length + ' chars)' : 'MISSING')
    }
    return Promise.reject(error)
  }
)

interface UserEntry {
  id: number
  username: string
  role: string
  is_active: boolean
  is_locked: boolean
  force_password_change: boolean
  failed_login_count: number
  last_login_at: string | null
  created_at: string | null
  active_sessions: number
  last_ip: string | null
}

interface SessionEntry {
  id: number
  username: string
  role: string
  ip_address: string | null
  browser: string | null
  os: string | null
  login_at: string | null
  is_active: boolean
}

type Tab = 'users' | 'sessions'

export default function AdminPage() {
  const [users, setUsers] = useState<UserEntry[]>([])
  const [sessions, setSessions] = useState<SessionEntry[]>([])
  const [tab, setTab] = useState<Tab>('users')
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [passwordModal, setPasswordModal] = useState<{ username: string; password: string } | null>(null)

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

  // ── User actions ─────────────────────────────────────────────────────────

  const createUser = async (username: string, role: string) => {
    try {
      const res = await api.post('/admin/users', { username, role })
      setPasswordModal({ username: res.data.username, password: res.data.temporary_password })
      load()
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      const status = e?.response?.status
      if (status === 401) return // interceptor handles re-login
      if (status === 403) {
        setError('Acces refuse. Vous devez etre connecte en tant qu\'admin.')
        return
      }
      alert(detail || 'Erreur lors de la creation')
    }
  }

  const deleteUser = async (id: number) => {
    if (!confirm('Supprimer cet utilisateur definitivement ?')) return
    try { await api.delete(`/admin/users/${id}`); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  const toggleActive = async (id: number, activate: boolean) => {
    try {
      await api.patch(`/admin/users/${id}/${activate ? 'enable' : 'disable'}`)
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
      setPasswordModal({ username: res.data.username, password: res.data.temporary_password })
    } catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  // ── Session actions ──────────────────────────────────────────────────────

  const terminateSession = async (id: number) => {
    try { await api.delete(`/admin/sessions/${id}`); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  // ── Error state ──────────────────────────────────────────────────────────

  if (error) return (
    <div style={{ padding: '60px 24px', textAlign: 'center' }}>
      <div style={{ fontSize: 48, marginBottom: 16 }}>🔒</div>
      <div style={{ fontSize: 16, color: 'var(--red)', fontWeight: 700 }}>{error}</div>
    </div>
  )

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div style={{ padding: '24px 28px' }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, color: 'var(--text)' }}>
          Administration
        </h2>
        <p style={{ color: 'var(--text3)', fontSize: 13, margin: 0 }}>
          Gerer les comptes utilisateurs et surveiller les sessions actives.
        </p>
      </div>

      {/* Tab navigation */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid var(--border)', paddingBottom: 0 }}>
        {([
          { key: 'users' as Tab, label: 'Gestion Utilisateurs', icon: '👥' },
          { key: 'sessions' as Tab, label: 'Sessions', icon: '🌐' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '10px 20px',
              fontSize: 13,
              fontWeight: tab === t.key ? 700 : 500,
              color: tab === t.key ? '#e67e22' : 'var(--text2)',
              background: 'none',
              border: 'none',
              borderBottom: tab === t.key ? '2px solid #e67e22' : '2px solid transparent',
              cursor: 'pointer',
              marginBottom: -2,
              transition: 'all 0.15s',
            }}
          >
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Password modal */}
      {passwordModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          background: 'rgba(0,0,0,0.5)', zIndex: 9999,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--card)', borderRadius: 14, padding: 28,
            maxWidth: 420, width: '90%', border: '1px solid var(--border)',
            boxShadow: '0 20px 60px rgba(0,0,0,0.15)',
          }}>
            <div style={{ fontSize: 28, marginBottom: 12, textAlign: 'center' }}>🔑</div>
            <h3 style={{ marginBottom: 16, fontSize: 16, fontWeight: 700, textAlign: 'center' }}>
              Mot de passe genere
            </h3>
            <div style={{
              background: 'var(--bg3)', borderRadius: 8, padding: 14,
              marginBottom: 16, border: '1px solid var(--border)',
            }}>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>Utilisateur</div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{passwordModal.username}</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6, marginTop: 12 }}>Mot de passe temporaire</div>
              <code style={{
                fontSize: 14, fontWeight: 700, color: '#e67e22',
                background: 'rgba(245,166,35,0.1)', padding: '4px 10px',
                borderRadius: 4, display: 'inline-block',
              }}>
                {passwordModal.password}
              </code>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 16, textAlign: 'center' }}>
              L'utilisateur devra changer ce mot de passe a sa prochaine connexion.
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button className="btn btn-primary" style={{ flex: 1 }} onClick={() => {
                navigator.clipboard.writeText(passwordModal.password)
                setPasswordModal(null)
              }}>
                Copier & Fermer
              </button>
              <button className="btn" onClick={() => setPasswordModal(null)}>Fermer</button>
            </div>
          </div>
        </div>
      )}

      {/* ═══════════════ USERS PANEL ═══════════════ */}
      {tab === 'users' && (
        <div>
          {/* Create user button */}
          <div style={{ marginBottom: 14 }}>
            <button
              className="btn btn-primary"
              onClick={() => setShowCreate(!showCreate)}
              style={{ fontSize: 12, padding: '8px 16px' }}
            >
              + Nouveau utilisateur
            </button>
          </div>

          {/* Create user form */}
          {showCreate && (
            <div style={{
              background: 'var(--card)', border: '1px solid var(--border)',
              borderRadius: 10, padding: 18, marginBottom: 16,
            }}>
              <CreateUserForm
                onCreate={(u, r) => { createUser(u, r); setShowCreate(false) }}
                onClose={() => setShowCreate(false)}
              />
            </div>
          )}

          {/* Users table */}
          <div style={{
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 10, overflow: 'auto',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 780 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['Utilisateur', 'Role', 'Statut', 'Derniere connexion', 'IP', 'Actions'].map(h => (
                    <th key={h} style={{
                      fontSize: 10, color: 'var(--text3)', padding: '12px 12px',
                      textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.5px',
                      fontWeight: 700,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {users.map(u => (
                  <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    {/* Username */}
                    <td style={{ padding: '12px', fontSize: 13, fontWeight: 600 }}>
                      {u.username}
                      {u.force_password_change && (
                        <span style={{ fontSize: 9, color: 'var(--yellow)', marginLeft: 6 }} title="Doit changer son mot de passe">
                          ⚠ MDP temp
                        </span>
                      )}
                    </td>

                    {/* Role */}
                    <td style={{ padding: '12px' }}>
                      {u.role === 'admin' ? (
                        <span style={{
                          fontSize: 10, fontWeight: 800, color: '#fff',
                          background: 'var(--red)', padding: '3px 8px',
                          borderRadius: 4, textTransform: 'uppercase',
                        }}>Admin</span>
                      ) : (
                        <select
                          value={u.role}
                          onChange={e => changeRole(u.id, e.target.value)}
                          style={{
                            fontSize: 11, padding: '4px 8px', borderRadius: 6,
                            border: '1px solid var(--border)', background: 'var(--bg3)',
                            color: 'var(--text)', cursor: 'pointer', fontWeight: 600,
                          }}
                        >
                          <option value="subadmin">Sub-Admin</option>
                          <option value="operator">Operateur</option>
                          <option value="viewer">Viewer</option>
                        </select>
                      )}
                    </td>

                    {/* Status */}
                    <td style={{ padding: '12px' }}>
                      {u.is_locked ? (
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--red)' }}>🔒 Verrouille</span>
                      ) : u.is_active ? (
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--green)' }}>● Actif</span>
                      ) : (
                        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)' }}>○ Desactive</span>
                      )}
                    </td>

                    {/* Last login */}
                    <td style={{ padding: '12px', fontSize: 11, color: 'var(--text3)' }}>
                      {u.last_login_at ? new Date(u.last_login_at).toLocaleString('fr-FR') : 'Jamais'}
                    </td>

                    {/* IP */}
                    <td style={{ padding: '12px', fontSize: 11, fontFamily: 'monospace', color: 'var(--text2)' }}>
                      {u.last_ip || '—'}
                    </td>

                    {/* Actions */}
                    <td style={{ padding: '12px' }}>
                      {u.role !== 'admin' && (
                        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                          <button
                            className="btn"
                            onClick={() => resetPassword(u.id)}
                            style={{ fontSize: 10, padding: '3px 8px', color: '#e67e22', fontWeight: 600 }}
                            title="Reinitialiser le mot de passe"
                          >
                            Reset MDP
                          </button>
                          <button
                            className="btn"
                            onClick={() => toggleActive(u.id, !u.is_active)}
                            style={{
                              fontSize: 10, padding: '3px 8px', fontWeight: 600,
                              color: u.is_active ? 'var(--red)' : 'var(--green)',
                            }}
                          >
                            {u.is_active ? 'Desactiver' : 'Activer'}
                          </button>
                          {u.is_locked && (
                            <button
                              className="btn"
                              onClick={() => unlockUser(u.id)}
                              style={{ fontSize: 10, padding: '3px 8px', color: 'var(--blue2)', fontWeight: 600 }}
                            >
                              Deverrouiller
                            </button>
                          )}
                          <button
                            className="btn"
                            onClick={() => deleteUser(u.id)}
                            style={{ fontSize: 10, padding: '3px 8px', color: 'var(--red)', fontWeight: 600 }}
                            title="Supprimer definitivement"
                          >
                            Supprimer
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
                {users.length === 0 && (
                  <tr>
                    <td colSpan={6} style={{ padding: 30, textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>
                      Aucun utilisateur enregistre.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ═══════════════ SESSIONS PANEL ═══════════════ */}
      {tab === 'sessions' && (
        <div>
          <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>
              <strong style={{ color: 'var(--green)' }}>{sessions.filter(s => s.is_active).length}</strong> session(s) active(s)
            </span>
            <button className="btn" onClick={load} style={{ fontSize: 11, padding: '4px 12px' }}>
              ↻ Rafraichir
            </button>
          </div>

          <div style={{
            background: 'var(--card)', border: '1px solid var(--border)',
            borderRadius: 10, overflow: 'auto',
          }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 750 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['Utilisateur', 'Role', 'Adresse IP', 'Navigateur / OS', 'Connecte le', 'Statut', ''].map(h => (
                    <th key={h} style={{
                      fontSize: 10, color: 'var(--text3)', padding: '12px 12px',
                      textAlign: 'left', textTransform: 'uppercase', letterSpacing: '0.5px',
                      fontWeight: 700,
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '12px', fontSize: 13, fontWeight: 600 }}>{s.username}</td>
                    <td style={{ padding: '12px' }}>
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 8px',
                        borderRadius: 4, textTransform: 'uppercase',
                        background: s.role === 'admin' ? 'rgba(255,77,109,0.1)' :
                                   s.role === 'subadmin' ? 'rgba(99,130,255,0.1)' :
                                   'rgba(99,130,255,0.05)',
                        color: s.role === 'admin' ? 'var(--red)' :
                               s.role === 'subadmin' ? 'var(--blue2)' :
                               'var(--text2)',
                      }}>
                        {s.role}
                      </span>
                    </td>
                    <td style={{ padding: '12px', fontSize: 12, fontFamily: 'monospace', fontWeight: 600, color: 'var(--text)' }}>
                      {s.ip_address || '—'}
                    </td>
                    <td style={{ padding: '12px', fontSize: 11, color: 'var(--text3)' }}>
                      {s.browser || '?'} / {s.os || '?'}
                    </td>
                    <td style={{ padding: '12px', fontSize: 11, color: 'var(--text2)' }}>
                      {s.login_at ? new Date(s.login_at).toLocaleString('fr-FR') : '—'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {s.is_active ? (
                        <span style={{
                          fontSize: 11, fontWeight: 700, color: 'var(--green)',
                          display: 'flex', alignItems: 'center', gap: 4,
                        }}>
                          <span style={{
                            width: 7, height: 7, borderRadius: '50%',
                            background: 'var(--green)', display: 'inline-block',
                            boxShadow: '0 0 6px rgba(26,188,156,0.5)',
                          }} />
                          En ligne
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: 'var(--text3)' }}>Terminee</span>
                      )}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {s.is_active && (
                        <button
                          className="btn"
                          onClick={() => terminateSession(s.id)}
                          style={{ fontSize: 9, padding: '3px 8px', color: 'var(--red)', fontWeight: 600 }}
                          title="Terminer cette session"
                        >
                          Deconnecter
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr>
                    <td colSpan={7} style={{ padding: 30, textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>
                      Aucune session enregistree.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Create User Form ─────────────────────────────────────────────────────────

function CreateUserForm({ onCreate, onClose }: { onCreate: (u: string, r: string) => void; onClose: () => void }) {
  const [username, setUsername] = useState('')
  const [role, setRole] = useState('viewer')
  const [err, setErr] = useState('')

  const handleSubmit = () => {
    if (username.trim().length < 3) {
      setErr('Le nom doit contenir au moins 3 caracteres.')
      return
    }
    if (/[^a-zA-Z0-9_.-]/.test(username)) {
      setErr('Caracteres autorises : lettres, chiffres, _ . -')
      return
    }
    onCreate(username.trim(), role)
    setUsername('')
  }

  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 12, color: 'var(--text)' }}>
        Creer un nouveau compte
      </div>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>
            Nom d'utilisateur
          </label>
          <input
            className="input"
            value={username}
            onChange={e => { setUsername(e.target.value); setErr('') }}
            placeholder="ex: ahmed.ops"
            style={{ width: 180, fontSize: 12 }}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
          />
        </div>
        <div>
          <label style={{ fontSize: 11, color: 'var(--text3)', display: 'block', marginBottom: 4 }}>
            Role
          </label>
          <select
            className="input"
            value={role}
            onChange={e => setRole(e.target.value)}
            style={{ width: 140, fontSize: 12 }}
          >
            <option value="viewer">Viewer</option>
            <option value="operator">Operateur</option>
            <option value="subadmin">Sub-Admin</option>
          </select>
        </div>
        <button className="btn btn-primary" onClick={handleSubmit} style={{ fontSize: 12, padding: '6px 16px' }}>
          Creer
        </button>
        <button className="btn" onClick={onClose} style={{ fontSize: 12, padding: '6px 12px' }}>
          Annuler
        </button>
      </div>
      {err && (
        <div style={{ fontSize: 11, color: 'var(--red)', marginTop: 8, fontWeight: 600 }}>{err}</div>
      )}
      <div style={{ fontSize: 10, color: 'var(--text3)', marginTop: 10 }}>
        Un mot de passe temporaire sera genere. Le role admin ne peut pas etre attribue.
      </div>
    </div>
  )
}
