import { useState } from 'react'
import type { ReactNode } from 'react'
import { BrowserRouter, Navigate, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import VMsPage from './components/VMsPage'
import PodsPage from './components/PodsPage'
import AlertsPage from './components/AlertsPage'
import ReportsPage from './components/ReportsPage'
import KubernetesPage from './components/KubernetesPage'
import InfrastructureMapPage from './components/InfrastructureMapPage'
import LogsPage from './components/LogsPage'
import GrafanaVisualizationsPage from './components/GrafanaVisualizationsPage'
import LoginPage from './components/LoginPage'
import type { AuthUser, UserRole } from './types'
import './index.css'

const STORAGE_KEY = 'cloudwatch-auth-user'

const homeByRole: Record<UserRole, string> = {
  admin: '/',
  operator: '/alerts',
  viewer: '/',
}

const routeRoles: Record<string, UserRole[]> = {
  '/': ['admin', 'viewer'],
  '/infrastructure': ['admin'],
  '/vms': ['admin'],
  '/pods': ['admin'],
  '/alerts': ['admin', 'operator'],
  '/logs': ['admin'],
  '/grafana': ['admin', 'viewer'],
  '/reports': ['admin', 'viewer'],
  '/kubernetes': ['admin'],
}

function readStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null

    const parsed = JSON.parse(raw) as AuthUser
    if (!parsed.name || !['admin', 'operator', 'viewer'].includes(parsed.role)) return null

    return {
      ...parsed,
      baseRole: parsed.baseRole || parsed.role,
    }
  } catch {
    return null
  }
}

function ProtectedRoute({ user, path, children }: { user: AuthUser; path: string; children: ReactNode }) {
  if (!routeRoles[path].includes(user.role)) {
    return <Navigate to={homeByRole[user.role]} replace />
  }

  return <>{children}</>
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser())

  const login = (nextUser: AuthUser) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser))
    setUser(nextUser)
  }

  const logout = () => {
    localStorage.removeItem(STORAGE_KEY)
    setUser(null)
  }

  const switchRole = (role: UserRole) => {
    if (!user || user.baseRole !== 'admin') return

    const nextUser: AuthUser = { ...user, role }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser))
    setUser(nextUser)
  }

  if (!user) {
    return <LoginPage onLogin={login} />
  }

  return (
    <BrowserRouter>
      <div style={{ display: 'flex', minHeight: '100vh', position: 'relative', zIndex: 1 }}>
        <Sidebar user={user} onLogout={logout} onSwitchRole={switchRole} />
        <main style={{ marginLeft: 220, flex: 1 }}>
          <div style={{
            height: 60,
            background: 'var(--bg2)',
            borderBottom: '1px solid var(--border)',
            display: 'flex',
            alignItems: 'center',
            padding: '0 24px',
            gap: 12,
            position: 'sticky',
            top: 0,
            zIndex: 50,
            boxShadow: '0 1px 10px rgba(15,23,42,0.04)',
          }}>
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 12 }}>
              <img src="/cireslogo.png" alt="CIRES" style={{ width: 34, height: 34, objectFit: 'contain' }} />
              <div>
                <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text)' }}>CloudWatch</div>
                <div style={{ fontSize: 12, color: 'var(--text3)', fontWeight: 400 }}>
                  Plateforme de supervision
                </div>
              </div>
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 12px',
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 700,
              background: '#dcfce7',
              color: 'var(--green)',
              border: '1px solid #bbf7d0',
            }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: 'var(--green)',
                display: 'inline-block',
                animation: 'pulse 1.2s infinite',
              }} />
              LIVE
            </div>
          </div>

          <Routes>
            <Route path="/" element={<ProtectedRoute user={user} path="/"><Dashboard /></ProtectedRoute>} />
            <Route path="/infrastructure" element={<ProtectedRoute user={user} path="/infrastructure"><InfrastructureMapPage /></ProtectedRoute>} />
            <Route path="/vms" element={<ProtectedRoute user={user} path="/vms"><VMsPage /></ProtectedRoute>} />
            <Route path="/pods" element={<ProtectedRoute user={user} path="/pods"><PodsPage /></ProtectedRoute>} />
            <Route path="/alerts" element={<ProtectedRoute user={user} path="/alerts"><AlertsPage /></ProtectedRoute>} />
            <Route path="/logs" element={<ProtectedRoute user={user} path="/logs"><LogsPage /></ProtectedRoute>} />
            <Route path="/grafana" element={<ProtectedRoute user={user} path="/grafana"><GrafanaVisualizationsPage /></ProtectedRoute>} />
            <Route path="/reports" element={<ProtectedRoute user={user} path="/reports"><ReportsPage /></ProtectedRoute>} />
            <Route path="/kubernetes" element={<ProtectedRoute user={user} path="/kubernetes"><KubernetesPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to={homeByRole[user.role]} replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
