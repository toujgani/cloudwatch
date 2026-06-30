import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import VMsPage from './components/VMsPage'
import PodsPage from './components/PodsPage'
import AlertsPage from './components/AlertsPage'
import ReportsPage from './components/ReportsPage'
import './index.css'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', minHeight: '100vh', position: 'relative', zIndex: 1 }}>
        <Sidebar />
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
                  Tanger Med Special Agency - Infrastructure
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
            <Route path="/" element={<Dashboard />} />
            <Route path="/vms" element={<VMsPage />} />
            <Route path="/pods" element={<PodsPage />} />
            <Route path="/alerts" element={<AlertsPage />} />
            <Route path="/reports" element={<ReportsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
