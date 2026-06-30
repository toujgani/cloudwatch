import { useEffect, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import { getVMs, getVMMetrics } from '../api/client'
import type { VM, MetricPoint } from '../types'

export default function VMsPage() {
  const [vms, setVMs]         = useState<VM[]>([])
  const [selected, setSelected] = useState<VM | null>(null)
  const [metrics, setMetrics] = useState<MetricPoint[]>([])

  useEffect(() => {
    getVMs().then(setVMs)
    const t = setInterval(() => getVMs().then(setVMs), 30_000)
    return () => clearInterval(t)
  }, [])

  const select = async (vm: VM) => {
    setSelected(vm)
    const m = await getVMMetrics(vm.id, 24)
    setMetrics(m)
  }

  const chartData = metrics.map(p => ({
    time: new Date(p.collected_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    cpu: p.cpu_percent,
    ram: p.ram_percent,
  }))

  return (
    <div style={{ padding: '20px 24px' }}>
      <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}> Machines virtuelles OpenStack</h2>
      <p style={{ color: 'var(--text3)', fontSize: 12, marginBottom: 20 }}>{vms.length} VMs détectées</p>

      <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 1.4fr' : '1fr', gap: 16 }}>
        {/* Table */}
        <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Nom','Statut','Flavor','CPU','RAM','Hôte'].map(h => (
                  <th key={h} style={{ fontSize: 11, color: 'var(--text3)', padding: '10px 12px', textAlign: 'left', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {vms.map(vm => (
                <tr key={vm.id}
                  onClick={() => select(vm)}
                  style={{
                    borderBottom: '1px solid rgba(99,130,255,0.06)',
                    cursor: 'pointer',
                    background: selected?.id === vm.id ? 'rgba(79,127,255,0.08)' : 'transparent',
                  }}
                >
                  <td style={{ padding: '10px 12px', fontWeight: 500, color: 'var(--text)', fontSize: 12 }}>{vm.name}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span className={`badge badge-${vm.status.toLowerCase()}`}>{vm.status}</span>
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text3)' }}>{vm.flavor ?? '—'}</td>
                  <td style={{ padding: '10px 12px', fontSize: 11, fontWeight: 600,
                    color: (vm.cpu_percent??0)>=90?'var(--red)':(vm.cpu_percent??0)>=70?'var(--yellow)':'var(--teal2)' }}>
                    {vm.cpu_percent != null ? `${vm.cpu_percent.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 11, fontWeight: 600,
                    color: (vm.ram_percent??0)>=90?'var(--red)':(vm.ram_percent??0)>=75?'var(--yellow)':'var(--teal2)' }}>
                    {vm.ram_percent != null ? `${vm.ram_percent.toFixed(1)}%` : '—'}
                  </td>
                  <td style={{ padding: '10px 12px', fontSize: 11, color: 'var(--text3)' }}>{vm.host ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        {selected && (
          <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
              <div>
                <div style={{ fontSize: 16, fontWeight: 700 }}>{selected.name}</div>
                <div style={{ fontSize: 11, color: 'var(--text3)', marginTop: 2 }}>{selected.id}</div>
              </div>
              <button onClick={() => setSelected(null)} style={{
                background: 'transparent', border: '1px solid var(--border2)',
                color: 'var(--text2)', borderRadius: 6, padding: '4px 10px', cursor: 'pointer', fontSize: 12,
              }}>✕</button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
              {[
                { l: 'CPU', v: `${selected.cpu_percent?.toFixed(1) ?? '—'}%` },
                { l: 'RAM', v: `${selected.ram_percent?.toFixed(1) ?? '—'}%` },
                { l: 'RAM utilisée', v: selected.ram_used_mb ? `${selected.ram_used_mb} MB` : '—' },
                { l: 'RAM totale', v: selected.ram_total_mb ? `${selected.ram_total_mb} MB` : '—' },
              ].map(item => (
                <div key={item.l} style={{ background: 'var(--bg3)', borderRadius: 8, padding: '10px 14px' }}>
                  <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.8px' }}>{item.l}</div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--blue2)' }}>{item.v}</div>
                </div>
              ))}
            </div>

            <div style={{ fontWeight: 600, fontSize: 12, marginBottom: 10 }}>Historique CPU/RAM 24h</div>
            <ResponsiveContainer width="100%" height={180}>
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.06)" />
                <XAxis dataKey="time" tick={{ fill: 'var(--text3)', fontSize: 9 }} interval="preserveStartEnd" />
                <YAxis domain={[0,100]} tick={{ fill: 'var(--text3)', fontSize: 9 }} tickFormatter={v => v+'%'} />
                <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)' }} />
                <Line type="monotone" dataKey="cpu" stroke="var(--blue2)" strokeWidth={2} dot={false} name="CPU" />
                <Line type="monotone" dataKey="ram" stroke="var(--teal2)" strokeWidth={2} dot={false} name="RAM" />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
