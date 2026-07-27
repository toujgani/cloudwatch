import { useEffect, useState } from 'react'
import { apiClient as api } from '../api/client'

interface UserEntry {
  id: number
  username: string
  role: string
  is_active: boolean
  is_locked: boolean
  last_login_at: string | null
  last_ip: string | null
  active_sessions: number
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

  const terminateSession = async (id: number) => {
    try { await api.delete(`/admin/sessions/${id}`); load() }
    catch (e: any) { alert(e?.response?.data?.detail || 'Erreur') }
  }

  if (error) return (
    <div style={{ padding: '60px 24px', textAlign: 'center' }}>
      <div style={{ fontSize: 16, color: 'var(--red)', fontWeight: 700 }}>{error}</div>
    </div>
  )

  return (
    <div style={{ padding: '24px 28px' }}>
      <div style={{ marginBottom: 24 }}>
        <h2 style={{ fontSize: 22, fontWeight: 800, marginBottom: 6, color: 'var(--text)' }}>
          Administration
        </h2>
        <p style={{ color: 'var(--text3)', fontSize: 13, margin: 0 }}>
          Gestion des comptes et sessions actives.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '2px solid var(--border)' }}>
        {([
          { key: 'users' as Tab, label: 'Utilisateurs' },
          { key: 'sessions' as Tab, label: 'Sessions' },
        ]).map(t => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            style={{
              padding: '10px 20px', fontSize: 13,
              fontWeight: tab === t.key ? 700 : 500,
              color: tab === t.key ? '#e67e22' : 'var(--text2)',
              background: 'none', border: 'none',
              borderBottom: tab === t.key ? '2px solid #e67e22' : '2px solid transparent',
              cursor: 'pointer', marginBottom: -2,
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Password modal */}
      {passwordModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', zIndex: 9999, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div style={{ background: 'var(--card)', borderRadius: 14, padding: 28, maxWidth: 420, width: '90%', border: '1px solid var(--border)' }}>
            <h3 style={{ marginBottom: 16, fontSize: 16, fontWeight: 700, textAlign: 'center' }}>Nouveau mot de passe</h3>
            <div style={{ background: 'var(--bg3)', borderRadius: 8, padding: 14, marginBottom: 16, border: '1px solid var(--border)' }}>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>Utilisateur</div>
              <div style={{ fontSize: 14, fontWeight: 700 }}>{passwordModal.username}</div>
              <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6, marginTop: 12 }}>Mot de passe temporaire</div>
              <code style={{ fontSize: 14, fontWeight: 700, color: '#e67e22' }}>{passwordModal.password}</code>
            </div>
            <button className="btn btn-primary" style={{ width: '100%' }} onClick={() => {
              navigator.clipboard.writeText(passwordModal.password)
              setPasswordModal(null)
            }}>Copier & Fermer</button>
          </div>
        </div>
      )}

      {/* Users */}
      {tab === 'users' && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)' }}>
                {['Utilisateur', 'Role', 'Statut', 'Derniere connexion', 'IP', 'Actions'].map(h => (
                  <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '12px 12px', textAlign: 'left', textTransform: 'uppercase', fontWeight: 700 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} style={{ borderBottom: '1px solid var(--border)' }}>
                  <td style={{ padding: '12px', fontSize: 13, fontWeight: 600 }}>{u.username}</td>
                  <td style={{ padding: '12px' }}>
                    {u.role === 'admin' ? (
                      <span style={{ fontSize: 10, fontWeight: 800, color: '#fff', background: 'var(--red)', padding: '3px 8px', borderRadius: 4 }}>ADMIN</span>
                    ) : (
                      <select value={u.role} onChange={e => changeRole(u.id, e.target.value)}
                        style={{ fontSize: 11, padding: '4px 8px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg3)', color: 'var(--text)', fontWeight: 600 }}>
                        <option value="subadmin">Sub-Admin</option>
                        <option value="operator">Operateur</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    )}
                  </td>
                  <td style={{ padding: '12px' }}>
                    {u.is_locked ? (
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--red)' }}>🔒 Verrouille</span>
                    ) : u.is_active ? (
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--green)' }}>● Actif</span>
                    ) : (
                      <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text3)' }}>○ Desactive</span>
                    )}
                  </td>
                  <td style={{ padding: '12px', fontSize: 11, color: 'var(--text3)' }}>
                    {u.last_login_at ? new Date(u.last_login_at).toLocaleString('fr-FR') : 'Jamais'}
                  </td>
                  <td style={{ padding: '12px', fontSize: 11, fontFamily: 'monospace' }}>{u.last_ip || '—'}</td>
                  <td style={{ padding: '12px' }}>
                    {u.role !== 'admin' && (
                      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                        <button className="btn" onClick={() => resetPassword(u.id)} style={{ fontSize: 10, padding: '3px 8px', color: '#e67e22', fontWeight: 600 }}>Reset MDP</button>
                        <button className="btn" onClick={() => toggleActive(u.id, !u.is_active)} style={{ fontSize: 10, padding: '3px 8px', fontWeight: 600, color: u.is_active ? 'var(--red)' : 'var(--green)' }}>
                          {u.is_active ? 'Desactiver' : 'Activer'}
                        </button>
                        {u.is_locked && (
                          <button className="btn" onClick={() => unlockUser(u.id)} style={{ fontSize: 10, padding: '3px 8px', color: 'var(--blue2)', fontWeight: 600 }}>Deverrouiller</button>
                        )}
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr><td colSpan={6} style={{ padding: 30, textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>Aucun utilisateur.</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* Sessions */}
      {tab === 'sessions' && (
        <div>
          <div style={{ marginBottom: 14, display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 13, color: 'var(--text2)' }}>
              <strong style={{ color: 'var(--green)' }}>{sessions.filter(s => s.is_active).length}</strong> session(s) active(s)
            </span>
            <button className="btn" onClick={load} style={{ fontSize: 11, padding: '4px 12px' }}>↻ Rafraichir</button>
          </div>
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 700 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid var(--border)' }}>
                  {['Utilisateur', 'Role', 'Adresse IP', 'Navigateur / OS', 'Connecte le', 'Statut', ''].map(h => (
                    <th key={h} style={{ fontSize: 10, color: 'var(--text3)', padding: '12px 12px', textAlign: 'left', textTransform: 'uppercase', fontWeight: 700 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sessions.map(s => (
                  <tr key={s.id} style={{ borderBottom: '1px solid var(--border)' }}>
                    <td style={{ padding: '12px', fontSize: 13, fontWeight: 600 }}>{s.username}</td>
                    <td style={{ padding: '12px', fontSize: 11 }}>{s.role}</td>
                    <td style={{ padding: '12px', fontSize: 12, fontFamily: 'monospace', fontWeight: 600 }}>{s.ip_address || '—'}</td>
                    <td style={{ padding: '12px', fontSize: 11, color: 'var(--text3)' }}>{s.browser || '?'} / {s.os || '?'}</td>
                    <td style={{ padding: '12px', fontSize: 11, color: 'var(--text2)' }}>
                      {s.login_at ? new Date(s.login_at).toLocaleString('fr-FR') : '—'}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {s.is_active ? (
                        <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--green)', display: 'flex', alignItems: 'center', gap: 4 }}>
                          <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--green)', display: 'inline-block' }} />
                          En ligne
                        </span>
                      ) : (
                        <span style={{ fontSize: 11, color: 'var(--text3)' }}>Terminee</span>
                      )}
                    </td>
                    <td style={{ padding: '12px' }}>
                      {s.is_active && (
                        <button className="btn" onClick={() => terminateSession(s.id)} style={{ fontSize: 9, padding: '3px 8px', color: 'var(--red)', fontWeight: 600 }}>Deconnecter</button>
                      )}
                    </td>
                  </tr>
                ))}
                {sessions.length === 0 && (
                  <tr><td colSpan={7} style={{ padding: 30, textAlign: 'center', color: 'var(--text3)', fontSize: 13 }}>Aucune session.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
