import { useEffect, useState } from 'react'
import { acknowledgeAlert, exportUrl, getAlerts, remediateActiveAlerts, remediateAlert, reprocessAlertAgent, resolveAlert, aiResolveAll } from '../api/client'
import type { Alert } from '../types'

type Filter = 'active' | 'all' | 'resolved'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [filter, setFilter] = useState<Filter>('active')
  const [busy, setBusy] = useState<number | null>(null)
  const [operator, setOperator] = useState('NOC')
  const [note, setNote] = useState('')
  const [agentBusy, setAgentBusy] = useState(false)

  const load = () => getAlerts(filter === 'all' ? undefined : filter).then(setAlerts)

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [filter])

  const act = async (id: number, action: 'ack' | 'resolve' | 'remediate') => {
    setBusy(id)
    if (action === 'ack') await acknowledgeAlert(id, operator, note || undefined)
    if (action === 'resolve') await resolveAlert(id, operator, note || undefined)
    if (action === 'remediate') await remediateAlert(id, operator || 'AI-Agent', true)
    setNote('')
    await load()
    setBusy(null)
  }

  const reprocessAgent = async () => {
    setAgentBusy(true)
    await reprocessAlertAgent()
    await load()
    setAgentBusy(false)
  }

  const runAIOpsAgent = async () => {
    setAgentBusy(true)
    await remediateActiveAlerts(operator || 'AI-Agent', false)
    await load()
    setAgentBusy(false)
  }

  const resolveAll = async () => {
    if (!window.confirm('Resoudre toutes les alertes actives avec l\'IA ? Cela executera les remediations automatiques.')) return
    setAgentBusy(true)
    try {
      await aiResolveAll()
    } catch {}
    await load()
    setAgentBusy(false)
  }

  const counts = {
    critical: alerts.filter(a => a.severity === 'critical' && a.status === 'active').length,
    warning: alerts.filter(a => a.severity === 'warning' && a.status === 'active').length,
    acknowledged: alerts.filter(a => a.acknowledged && a.status === 'active').length,
  }

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Alertes intelligentes</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>Traitement, acquittement, resolution et export des incidents.</div>
        </div>
        <button className="btn" disabled={agentBusy} onClick={reprocessAgent}>
          {agentBusy ? 'Analyse...' : 'Agent IA'}
        </button>
        <button className="btn btn-primary" disabled={agentBusy} onClick={runAIOpsAgent}>
          AIOps agent
        </button>
        <button className="btn" disabled={agentBusy} onClick={resolveAll} style={{ background: 'var(--green)', color: '#fff', borderColor: 'var(--green)' }}>
          {agentBusy ? '...' : 'Tout resoudre'}
        </button>
        <a className="btn" href={exportUrl('alerts', filter === 'all' ? undefined : filter)}>Exporter CSV</a>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10, marginBottom: 16 }}>
        {[
          { label: 'Critiques actives', value: counts.critical, color: 'var(--red)' },
          { label: 'Warnings actifs', value: counts.warning, color: 'var(--yellow)' },
          { label: 'Acquittees', value: counts.acknowledged, color: 'var(--green)' },
        ].map(item => (
          <div key={item.label} className="panel" style={{ padding: '12px 14px' }}>
            <div style={{ color: item.color, fontSize: 24, fontWeight: 700 }}>{item.value}</div>
            <div style={{ color: 'var(--text3)', fontSize: 11, textTransform: 'uppercase' }}>{item.label}</div>
          </div>
        ))}
      </div>

      <div className="panel" style={{ padding: 12, marginBottom: 16 }}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {(['active', 'all', 'resolved'] as const).map(f => (
            <button key={f} className={filter === f ? 'btn btn-primary' : 'btn'} onClick={() => setFilter(f)}>
              {f === 'active' ? 'Actives' : f === 'all' ? 'Toutes' : 'Resolues'}
            </button>
          ))}
          <div style={{ flex: 1 }} />
          <input className="input" value={operator} onChange={e => setOperator(e.target.value)} placeholder="Operateur" style={{ width: 130 }} />
          <input className="input" value={note} onChange={e => setNote(e.target.value)} placeholder="Commentaire intervention" style={{ minWidth: 240 }} />
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {alerts.length === 0 && (
          <div className="panel" style={{ padding: 32, textAlign: 'center', color: 'var(--text3)' }}>
            Aucune alerte dans cette categorie
          </div>
        )}

        {alerts.map(a => {
          const isCrit = a.severity === 'critical'
          const isWarn = a.severity === 'warning'
          const color = isCrit ? 'var(--red)' : isWarn ? 'var(--yellow)' : 'var(--blue2)'
          const resource = a.vm_id || a.pod_id || 'Ressource inconnue'

          return (
            <div key={a.id} className="panel" style={{ padding: '14px 16px', borderLeft: `3px solid ${color}`, opacity: a.status === 'resolved' ? 0.65 : 1 }}>
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6, flexWrap: 'wrap' }}>
                    <strong style={{ color: 'var(--text)' }}>{a.title}</strong>
                    <span className={`badge badge-${a.severity}`}>{a.severity}</span>
                    <span className={`badge badge-${a.status === 'active' ? 'warning' : 'running'}`}>{a.status}</span>
                    {a.acknowledged && <span className="badge badge-info">Vu par {a.acknowledged_by || 'operator'}</span>}
                    {a.ai_decision && <span className="badge badge-info">IA {a.ai_decision}</span>}
                  </div>
                  <div style={{ color: 'var(--text2)', fontSize: 12, marginBottom: 8 }}>{a.description}</div>
                  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', color: 'var(--text3)', fontSize: 11 }}>
                    <span>Ressource: <strong style={{ color: 'var(--text2)' }}>{resource}</strong></span>
                    {a.metric_value != null && <span>Valeur: <strong style={{ color: 'var(--text2)' }}>{a.metric_value.toFixed(1)}</strong></span>}
                    {a.threshold != null && <span>Seuil: <strong style={{ color: 'var(--text2)' }}>{a.threshold}</strong></span>}
                    <span>Declenchee: {new Date(a.triggered_at).toLocaleString('fr-FR')}</span>
                    {a.operator_note && <span>Note: <strong style={{ color: 'var(--text2)' }}>{a.operator_note}</strong></span>}
                  </div>
                  {a.ai_score != null && (
                    <div style={{ marginTop: 10, padding: '9px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(79,127,255,0.05)' }}>
                      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
                        <span>Health impact: <strong style={{ color }}>{a.ai_score}/100</strong></span>
                        {a.ai_category && <span>Categorie: <strong style={{ color: 'var(--text2)' }}>{a.ai_category}</strong></span>}
                        {a.ai_confidence != null && <span>Confiance: <strong style={{ color: 'var(--text2)' }}>{Math.round(a.ai_confidence * 100)}%</strong></span>}
                      </div>
                      <div style={{ color: 'var(--text2)', fontSize: 12 }}>{a.ai_recommendation}</div>
                      {a.ai_reason && <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 4 }}>Raison: {a.ai_reason}</div>}
                    </div>
                  )}
                  {a.remediation_action && (
                    <div style={{ marginTop: 8, padding: '9px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(26,188,156,0.05)' }}>
                      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>
                        <span>Action rapide: <strong style={{ color: 'var(--text2)' }}>{a.remediation_action}</strong></span>
                        {a.remediation_status && <span>Statut: <strong style={{ color: 'var(--text2)' }}>{a.remediation_status}</strong></span>}
                      </div>
                      {a.remediation_message && <div style={{ color: 'var(--text2)', fontSize: 12 }}>{a.remediation_message}</div>}
                    </div>
                  )}
                </div>

                {a.status === 'active' && (
                  <div style={{ display: 'flex', gap: 8 }}>
                    <button className="btn" disabled={busy === a.id} onClick={() => act(a.id, 'remediate')}>
                      Intervention rapide
                    </button>
                    {!a.acknowledged && (
                      <button className="btn" disabled={busy === a.id} onClick={() => act(a.id, 'ack')}>
                        Acquitter
                      </button>
                    )}
                    <button className="btn btn-primary" disabled={busy === a.id} onClick={() => act(a.id, 'resolve')}>
                      Resoudre
                    </button>
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
