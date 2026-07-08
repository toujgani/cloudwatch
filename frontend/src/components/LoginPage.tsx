import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AuthUser, UserRole } from '../types'

const accounts: Record<string, { password: string; role: UserRole }> = {
  admin: { password: 'Admin@123', role: 'admin' },
  operator: { password: 'Operator@123', role: 'operator' },
  viewer: { password: 'Viewer@123', role: 'viewer' },
}

function authenticate(name: string, password: string): AuthUser | null {
  const account = accounts[name.toLowerCase()]
  if (!account || account.password !== password) return null
  return { name, role: account.role, baseRole: account.role }
}

export default function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedName = name.trim()
    if (!trimmedName || !password.trim()) {
      setError('Veuillez renseigner votre utilisateur et votre mot de passe.')
      return
    }
    const user = authenticate(trimmedName, password)
    if (!user) { setError('Utilisateur ou mot de passe incorrect.'); return }
    onLogin(user)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      background: '#f7f8fa',
    }}>
      <main style={{
        width: 'min(100%, 440px)',
        background: '#fff',
        border: '1px solid #e8ecf0',
        borderRadius: 14,
        boxShadow: '0 20px 60px rgba(0,0,0,0.06)',
        overflow: 'hidden',
      }}>
        {/* Orange accent bar */}
        <div style={{ height: 4, background: 'linear-gradient(90deg, #f5a623, #e67e22)' }} />

        <form onSubmit={submit} style={{ padding: '36px 36px 38px' }}>
          <div style={{ marginBottom: 28 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 24 }}>
              <img
                src="/cireslogo.png"
                alt="CIRES"
                style={{
                  width: 50, height: 50, objectFit: 'contain',
                  borderRadius: 10,
                  border: '1px solid #e8ecf0',
                  padding: 5,
                }}
              />
              <div>
                <div style={{ fontSize: 18, fontWeight: 800, color: '#1a2030' }}>Cloud AI Monitor</div>
                <div style={{ color: '#8a94a6', fontSize: 12 }}>CIRES Technologies</div>
              </div>
            </div>
            <h2 style={{ fontSize: 24, lineHeight: 1.2, marginBottom: 8, color: '#1a2030' }}>
              Connexion sécurisée
            </h2>
            <div style={{ color: '#8a94a6', fontSize: 13, lineHeight: 1.55 }}>
              Entrez vos identifiants pour accéder à l'espace de supervision.
            </div>
          </div>

          <label style={{ display: 'block', fontSize: 12, color: '#4a5568', fontWeight: 700, marginBottom: 8 }}>
            Utilisateur
          </label>
          <input
            className="input"
            value={name}
            onChange={e => { setName(e.target.value); setError('') }}
            autoComplete="username"
            placeholder="admin / operator / viewer"
            style={{
              width: '100%', minHeight: 44, fontSize: 14, marginBottom: 18,
              borderRadius: 8, background: '#f7f8fa', borderColor: '#e8ecf0',
            }}
          />

          <label style={{ display: 'block', fontSize: 12, color: '#4a5568', fontWeight: 700, marginBottom: 8 }}>
            Mot de passe
          </label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={e => { setPassword(e.target.value); setError('') }}
            autoComplete="current-password"
            placeholder="••••••••"
            style={{
              width: '100%', minHeight: 44, fontSize: 14, marginBottom: 18,
              borderRadius: 8, background: '#f7f8fa', borderColor: '#e8ecf0',
            }}
          />

          {error && (
            <div style={{
              color: '#dc3545',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: 8, padding: '10px 12px',
              fontSize: 12, marginBottom: 14, fontWeight: 700,
            }}>
              {error}
            </div>
          )}

          <button
            className="btn btn-primary"
            type="submit"
            style={{
              width: '100%', minHeight: 46, fontSize: 14, borderRadius: 8,
              boxShadow: '0 6px 20px rgba(245,166,35,0.25)',
            }}
          >
            Se connecter
          </button>

          <div style={{
            marginTop: 22, paddingTop: 18,
            borderTop: '1px solid #e8ecf0',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            color: '#8a94a6', fontSize: 11,
          }}>
            <span>CIRES Technologies © 2026</span>
            <span style={{ color: '#f5a623', fontWeight: 600 }}>Session protégée</span>
          </div>
        </form>
      </main>
    </div>
  )
}
