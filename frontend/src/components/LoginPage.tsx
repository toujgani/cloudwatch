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

  return {
    name,
    role: account.role,
    baseRole: account.role,
  }
}

export default function LoginPage({ onLogin }: { onLogin: (user: AuthUser) => void }) {
  const [name, setName] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [backgroundLogo, setBackgroundLogo] = useState('/tangermedlogo.jpg')

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedName = name.trim()

    if (!trimmedName || !password.trim()) {
      setError('Veuillez renseigner votre utilisateur et votre mot de passe.')
      return
    }

    const authenticatedUser = authenticate(trimmedName, password)

    if (!authenticatedUser) {
      setError('Utilisateur ou mot de passe incorrect.')
      return
    }

    onLogin(authenticatedUser)
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: 24,
      background: '#eef3f8',
      position: 'relative',
      overflow: 'hidden',
    }}>
      <img
        src={backgroundLogo}
        alt=""
        onError={() => setBackgroundLogo('/cireslogo.png')}
        style={{
          position: 'absolute',
          inset: 0,
          width: '100%',
          height: '100%',
          objectFit: 'cover',
          opacity: 1,
          pointerEvents: 'none',
          userSelect: 'none',
        }}
      />

      <div style={{
        position: 'absolute',
        inset: 0,
        background: 'linear-gradient(135deg, rgba(255,255,255,0.14), rgba(15,23,42,0.12))',
        pointerEvents: 'none',
      }} />

      <main style={{
        width: 'min(100%, 460px)',
        background: 'rgba(255,255,255,0.9)',
        border: '1px solid rgba(203, 213, 225, 0.9)',
        borderRadius: 8,
        boxShadow: '0 28px 80px rgba(15, 23, 42, 0.18)',
        overflow: 'hidden',
        backdropFilter: 'blur(18px)',
        position: 'relative',
        zIndex: 1,
      }}>
        <form onSubmit={submit} style={{ padding: '40px 40px 42px' }}>
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 13, marginBottom: 22 }}>
              <img
                src="/cireslogo.png"
                alt="CIRES"
                style={{
                  width: 50,
                  height: 50,
                  objectFit: 'contain',
                  borderRadius: 8,
                  border: '1px solid var(--border)',
                  background: '#fff',
                  padding: 5,
                }}
              />
              <div>
                <div style={{ fontSize: 19, fontWeight: 800, color: 'var(--text)' }}>CloudWatch</div>
                <div style={{ color: 'var(--text3)', fontSize: 12 }}>Tanger Med - Supervision</div>
              </div>
            </div>
            <h2 style={{ fontSize: 26, lineHeight: 1.2, marginBottom: 8, letterSpacing: 0 }}>
              Connexion securisee
            </h2>
            <div style={{ color: 'var(--text3)', fontSize: 13, lineHeight: 1.55 }}>
              Entrez vos identifiants pour acceder a l'espace de supervision.
            </div>
          </div>

          <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 8 }}>
            Utilisateur
          </label>
          <input
            className="input"
            value={name}
            onChange={event => {
              setName(event.target.value)
              setError('')
            }}
            autoComplete="username"
            placeholder="Entrez votre utilisateur"
            style={{
              width: '100%',
              minHeight: 48,
              fontSize: 14,
              marginBottom: 18,
              borderRadius: 8,
              borderColor: '#d6dee8',
              background: '#f8fafc',
            }}
          />

          <label style={{ display: 'block', fontSize: 12, color: 'var(--text2)', fontWeight: 700, marginBottom: 8 }}>
            Mot de passe
          </label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={event => {
              setPassword(event.target.value)
              setError('')
            }}
            autoComplete="current-password"
            placeholder="Entrez votre mot de passe"
            style={{
              width: '100%',
              minHeight: 48,
              fontSize: 14,
              marginBottom: 18,
              borderRadius: 8,
              borderColor: '#d6dee8',
              background: '#f8fafc',
            }}
          />

          {error && (
            <div style={{
              color: 'var(--red)',
              background: '#fee2e2',
              border: '1px solid #fecaca',
              borderRadius: 8,
              padding: '10px 12px',
              fontSize: 12,
              marginBottom: 14,
              fontWeight: 700,
            }}>
              {error}
            </div>
          )}

          <button
            className="btn btn-primary"
            type="submit"
            style={{
              width: '100%',
              minHeight: 48,
              fontSize: 14,
              borderRadius: 8,
              boxShadow: '0 12px 26px rgba(37, 99, 235, 0.28)',
            }}
          >
            Se connecter
          </button>

          <div style={{
            marginTop: 22,
            paddingTop: 18,
            borderTop: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
            color: 'var(--text3)',
            fontSize: 11,
          }}>
            <span>CIRES Monitoring</span>
            <span>Session protegee</span>
          </div>
        </form>
      </main>
    </div>
  )
}
