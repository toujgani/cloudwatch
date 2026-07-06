import { NavLink } from 'react-router-dom'
import type { AuthUser, UserRole } from '../types'

const links = [
  { to: '/', icon: 'DB', label: 'Dashboard', roles: ['admin', 'viewer'] },
  { to: '/infrastructure', icon: 'MAP', label: 'Vue infrastructure', roles: ['admin'] },
  { to: '/alerts', icon: 'AL', label: 'Alertes', roles: ['admin', 'operator'] },
  { to: '/logs', icon: 'LOG', label: 'Logs', roles: ['admin'] },
  { to: '/grafana', icon: 'GRF', label: 'Visualisations', roles: ['admin', 'viewer'] },
  { to: '/reports', icon: 'CSV', label: 'Rapports', roles: ['admin', 'viewer'] },
  { to: '/kubernetes', icon: 'K8S', label: 'Clusters Kubernetes', roles: ['admin'] },
  { to: '/vms', icon: 'VM', label: 'Machines virtuelles', roles: ['admin'] },
  { to: '/pods', icon: 'OS', label: 'Pods OpenShift', roles: ['admin'] },
  { to: '/aiops', icon: 'AI', label: 'AIOps Engine', roles: ['admin'] },
  { to: '/audit', icon: 'AUD', label: 'Audit Trail', roles: ['admin'] },
]

const adminModes: { role: UserRole; label: string }[] = [
  { role: 'admin', label: 'Admin' },
  { role: 'operator', label: 'Operateur' },
  { role: 'viewer', label: 'Viewer' },
]

export default function Sidebar({
  user,
  onLogout,
  onSwitchRole,
}: {
  user: AuthUser
  onLogout: () => void
  onSwitchRole: (role: UserRole) => void
}) {
  const visibleLinks = links.filter(link => link.roles.includes(user.role))

  return (
    <aside style={{
      width: 220, background: 'var(--bg2)', borderRight: '1px solid var(--border)',
      display: 'flex', flexDirection: 'column', position: 'fixed',
      top: 0, left: 0, bottom: 0, zIndex: 100,
      boxShadow: '2px 0 12px rgba(15,23,42,0.04)',
    }}>
      <div style={{ padding: '18px 18px 16px', borderBottom: '1px solid var(--border)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <img
            src="/cireslogo.png"
            alt="CIRES"
            style={{
              width: 42,
              height: 42,
              objectFit: 'contain',
              borderRadius: 8,
              background: '#fff',
              border: '1px solid var(--border)',
              padding: 4,
            }}
          />
          <div>
            <div style={{ fontSize: 15, fontWeight: 800, color: 'var(--text)' }}>CloudWatch</div>
            <div style={{ fontSize: 11, color: 'var(--text3)' }}>CIRES Monitoring</div>
          </div>
        </div>
      </div>

      <nav style={{ padding: '12px 0', flex: 1 }}>
        <div style={{ padding: '8px 16px 4px', fontSize: 10, color: 'var(--text3)', letterSpacing: '1.2px', textTransform: 'uppercase' }}>
          Navigation
        </div>
        {visibleLinks.map(l => (
          <NavLink key={l.to} to={l.to} end={l.to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '10px 16px', fontSize: 13, textDecoration: 'none',
              color: isActive ? 'var(--blue2)' : 'var(--text2)',
              background: isActive ? '#eff6ff' : 'transparent',
              borderLeft: isActive ? '3px solid var(--blue2)' : '3px solid transparent',
              transition: 'all 0.2s',
            })}
          >
            <span style={{
              fontSize: 10,
              width: 26,
              height: 22,
              borderRadius: 5,
              background: 'var(--bg3)',
              color: 'var(--text2)',
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
            }}>{l.icon}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>

      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        {user.baseRole === 'admin' && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 10, color: 'var(--text3)', letterSpacing: '1px', textTransform: 'uppercase', marginBottom: 8 }}>
              Mode d'acces
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 6 }}>
              {adminModes.map(mode => (
                <button
                  key={mode.role}
                  className={user.role === mode.role ? 'btn btn-primary' : 'btn'}
                  onClick={() => onSwitchRole(mode.role)}
                  style={{ width: '100%', minHeight: 28 }}
                >
                  {mode.label}
                </button>
              ))}
            </div>
          </div>
        )}
        <button className="btn" onClick={onLogout} style={{ width: '100%', marginBottom: 10 }}>
          Deconnexion
        </button>
        <div>
          <span style={{
            width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
            boxShadow: '0 0 6px var(--green)', display: 'inline-block', marginRight: 6,
          }} className="pulse" />
          <span style={{ fontSize: 11, color: 'var(--text3)' }}>Collecte active - 30s</span>
        </div>
      </div>
    </aside>
  )
}
