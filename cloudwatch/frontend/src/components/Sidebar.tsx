import { NavLink } from 'react-router-dom'

const links = [
  { to: '/', icon: 'DB', label: 'Dashboard' },
  { to: '/alerts', icon: 'AL', label: 'Alertes' },
  { to: '/reports', icon: 'CSV', label: 'Rapports' },
  { to: '/vms', icon: 'VM', label: 'Machines virtuelles' },
  { to: '/pods', icon: 'OS', label: 'Pods OpenShift' },
]

export default function Sidebar() {
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
        {links.map(l => (
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
        <span style={{
          width: 7, height: 7, borderRadius: '50%', background: 'var(--green)',
          boxShadow: '0 0 6px var(--green)', display: 'inline-block', marginRight: 6,
        }} className="pulse" />
        <span style={{ fontSize: 11, color: 'var(--text3)' }}>Collecte active - 30s</span>
      </div>
    </aside>
  )
}
