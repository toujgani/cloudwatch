import { useState, useEffect, useRef } from 'react'
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
import AIOpsPage from './components/AIOpsPage'
import CostPage from './components/CostPage'
import AdminPage from './components/AdminPage'
import { clearStoredToken, getStoredToken } from './api/client'
import type { AuthUser, WsSnapshot } from './types'
import type { UserRole } from './types'
import './index.css'

const STORAGE_KEY = 'cloudwatch-auth-user'

const homeByRole: Record<UserRole, string> = {
  admin: '/',
  operator: '/alerts',
  viewer: '/',
}

const routeRoles: Record<string, UserRole[]> = {
  '/': ['admin', 'operator', 'viewer'],
  '/infrastructure': ['admin', 'operator'],
  '/vms': ['admin', 'operator'],
  '/pods': ['admin', 'operator'],
  '/alerts': ['admin', 'operator'],
  '/logs': ['admin', 'operator'],
  '/grafana': ['admin', 'operator', 'viewer'],
  '/reports': ['admin', 'operator', 'viewer'],
  '/costs': ['admin', 'operator', 'viewer'],
  '/kubernetes': ['admin', 'operator'],
  '/aiops': ['admin', 'operator'],
  '/admin': ['admin'],
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
  if (!routeRoles[path]?.includes(user.role)) {
    return <Navigate to={homeByRole[user.role]} replace />
  }

  return <>{children}</>
}

export default function App() {
  const [user, setUser] = useState<AuthUser | null>(() => readStoredUser())
  const [wsSnapshot, setWsSnapshot] = useState<WsSnapshot | null>(null)
  const wsRef = useRef<WebSocket | null>(null)
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('theme') === 'dark')

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', darkMode ? 'dark' : 'light')
    localStorage.setItem('theme', darkMode ? 'dark' : 'light')
  }, [darkMode])

  useEffect(() => {
    if (!user) return
    const connect = () => {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${proto}//${window.location.host}/ws/live`
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws
      ws.onmessage = (e) => {
        try { setWsSnapshot(JSON.parse(e.data) as WsSnapshot) } catch {}
      }
      ws.onclose = () => setTimeout(connect, 3000)
    }
    connect()
    return () => { wsRef.current?.close() }
  }, [!!user])

  const login = (nextUser: AuthUser) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(nextUser))
    setUser(nextUser)
  }

  const logout = () => {
    const token = getStoredToken()
    if (token) {
      fetch('/api/auth/logout', {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {})
    }
    clearStoredToken()
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
                <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text)' }}>Cloud AI Monitor</div>
                <div style={{ fontSize: 12, color: 'var(--text3)', fontWeight: 400 }}>
                  CIRES Technologies
                </div>
              </div>
            </div>
            {wsSnapshot?.runtime && (
              <div style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '4px 10px', borderRadius: 6, fontSize: 10,
                background: 'rgba(99,130,255,0.08)', color: 'var(--blue2)',
                border: '1px solid rgba(99,130,255,0.2)', fontWeight: 600,
              }}>
                ◆ {wsSnapshot.runtime.display_name}
              </div>
            )}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '5px 12px',
              borderRadius: 20,
              fontSize: 12,
              fontWeight: 700,
              background: '#fff7ed',
              color: '#e67e22',
              border: '1px solid #fed7aa',
            }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: '#f5a623',
                display: 'inline-block',
                animation: 'pulse 1.2s infinite',
              }} />
              LIVE
            </div>
            <button
              onClick={() => setDarkMode(!darkMode)}
              style={{
                background: 'var(--bg3)', border: '1px solid var(--border2)',
                borderRadius: 8, padding: '5px 10px', fontSize: 11,
                color: 'var(--text2)', cursor: 'pointer', fontWeight: 600,
              }}
            >
              {darkMode ? 'Light' : 'Dark'}
            </button>
            {wsSnapshot && (
              <div style={{ display: 'flex', gap: 14, fontSize: 12, color: 'var(--text2)' }}>
                <span>VMs: <strong style={{ color: 'var(--blue2)' }}>{wsSnapshot.kpis.vms.active}/{wsSnapshot.kpis.vms.total}</strong></span>
                <span>Pods: <strong style={{ color: 'var(--teal2)' }}>{wsSnapshot.kpis.pods.running}/{wsSnapshot.kpis.pods.total}</strong></span>
                <span>Alertes: <strong style={{ color: 'var(--red)' }}>{wsSnapshot.kpis.alerts.total_active}</strong></span>
                <span style={{
                  padding: '2px 10px', borderRadius: 12,
                  background: wsSnapshot.kpis.health_score >= 70 ? 'rgba(26,188,156,0.12)' : wsSnapshot.kpis.health_score >= 45 ? 'rgba(255,209,102,0.15)' : 'rgba(255,77,109,0.12)',
                  color: wsSnapshot.kpis.health_score >= 70 ? 'var(--green)' : wsSnapshot.kpis.health_score >= 45 ? 'var(--yellow)' : 'var(--red)',
                  fontWeight: 700,
                }}>
                  ⚡ {wsSnapshot.kpis.health_score}/100
                </span>
              </div>
            )}
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
            <Route path="/aiops" element={<ProtectedRoute user={user} path="/aiops"><AIOpsPage /></ProtectedRoute>} />
            <Route path="/costs" element={<ProtectedRoute user={user} path="/costs"><CostPage /></ProtectedRoute>} />
            <Route path="/admin" element={<ProtectedRoute user={user} path="/admin"><AdminPage /></ProtectedRoute>} />
            <Route path="*" element={<Navigate to={homeByRole[user.role]} replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
