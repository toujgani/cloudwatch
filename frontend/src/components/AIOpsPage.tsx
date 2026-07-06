import { useEffect, useRef, useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, RadarChart, Radar, PolarGrid, PolarAngleAxis } from 'recharts'
import { simulateVector, injectAnomaly, getAIOpsKnowledgeBase, getAIOpsPipelineStatus, getAuditLogs } from '../api/client'
import type { AnomalyVectorSim, AIOpsInjectionResult, AIOpsKnowledgeEntry, AIOPSPipelineStatus, AuditLogEntry } from '../types'

const DECISION_COLOR: Record<string, string> = {
  escalate: 'var(--red)',
  investigate: 'var(--yellow)',
  watch: 'var(--blue2)',
  suppress: 'var(--text3)',
}

const SEV_LABELS = ['info', 'warning', 'critical'] as const

export default function AIOpsPage() {
  // Vector simulator state
  const [m, setM] = useState(0.3)
  const [l, setL] = useState(0.2)
  const [t, setT] = useState(0.1)
  const [sev, setSev] = useState<'info' | 'warning' | 'critical'>('warning')
  const [simResult, setSimResult] = useState<AnomalyVectorSim | null>(null)
  const [simBusy, setSimBusy] = useState(false)

  // Injection state
  const [injTitle, setInjTitle] = useState('CPU Saturation Simulée')
  const [injDesc, setInjDesc]   = useState('Test injection via AIOps Simulator')
  const [injRule, setInjRule]   = useState('sim.cpu.critical')
  const [injMetric, setInjMetric] = useState(92)
  const [injThresh, setInjThresh] = useState(90)
  const [injSev, setInjSev]     = useState<'info' | 'warning' | 'critical'>('critical')
  const [useOverride, setUseOverride] = useState(false)
  const [injBusy, setInjBusy]   = useState(false)
  const [injResult, setInjResult] = useState<AIOpsInjectionResult | null>(null)

  // Knowledge base + pipeline
  const [kb, setKb]             = useState<AIOpsKnowledgeEntry[]>([])
  const [pipeline, setPipeline] = useState<AIOPSPipelineStatus | null>(null)
  const [auditLog, setAuditLog] = useState<AuditLogEntry[]>([])

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    getAIOpsKnowledgeBase().then(setKb).catch(() => {})
    const refresh = () => {
      getAIOpsPipelineStatus().then(setPipeline).catch(() => {})
      getAuditLogs(20).then(setAuditLog).catch(() => {})
    }
    refresh()
    intervalRef.current = setInterval(refresh, 5000)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  // Auto-simulate when sliders change
  useEffect(() => {
    const t_ = setTimeout(async () => {
      setSimBusy(true)
      try { setSimResult(await simulateVector(m, l, t, sev)) } catch {}
      setSimBusy(false)
    }, 150)
    return () => clearTimeout(t_)
  }, [m, l, t, sev])

  const runInject = async () => {
    setInjBusy(true)
    setInjResult(null)
    try {
      const payload: Record<string, unknown> = {
        title: injTitle, description: injDesc,
        severity: injSev, rule_name: injRule,
        metric_value: injMetric, threshold: injThresh,
      }
      if (useOverride) { payload.override_m = m; payload.override_l = l; payload.override_t = t }
      setInjResult(await injectAnomaly(payload))
    } catch {}
    setInjBusy(false)
  }


  const decisionColor = simResult ? DECISION_COLOR[simResult.decision] ?? 'var(--text2)' : 'var(--text3)'
  const radarData = [
    { axis: 'Metrics (m)', value: Math.round(m * 100) },
    { axis: 'Logs (l)', value: Math.round(l * 100) },
    { axis: 'Traces (t)', value: Math.round(t * 100) },
    { axis: 'Norm |A|', value: simResult ? Math.round(simResult.norm * 100) : 0 },
    { axis: 'AI Score', value: simResult?.ai_score ?? 0 },
  ]

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ marginBottom: 18 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 4 }}>AIOps Engine — Simulateur interactif</h2>
        <div style={{ color: 'var(--text3)', fontSize: 12 }}>
          Architecture D · Anomaly Vector A = [m, l, t] · Modèle de decay dynamique · Pipeline temps réel
        </div>
      </div>

      {/* Pipeline live status bar */}
      {pipeline && (
        <div className="panel" style={{ padding: '10px 16px', marginBottom: 16, display: 'flex', gap: 24, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 11, color: 'var(--text3)', textTransform: 'uppercase' }}>Pipeline</span>
          <span style={{ color: 'var(--green)', fontWeight: 700 }}>● ACTIF</span>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Alertes actives: <strong>{pipeline.active_alerts}</strong></span>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Score moyen: <strong>{pipeline.avg_ai_score}</strong></span>
          <span style={{ fontSize: 12, color: 'var(--text2)' }}>Norme moy: <strong>{pipeline.avg_anomaly_norm}</strong></span>
          {pipeline.last_audit_action && (
            <span style={{ fontSize: 11, color: 'var(--text3)' }}>Dernier audit: {pipeline.last_audit_action}</span>
          )}
          <div style={{ flex: 1 }} />
          {Object.entries(pipeline.decision_distribution).map(([d, count]) => (
            <span key={d} style={{ fontSize: 11, color: DECISION_COLOR[d] ?? 'var(--text2)', fontWeight: 600 }}>
              {d}: {count}
            </span>
          ))}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
        {/* Vector Sliders */}
        <div className="panel" style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 14 }}>Vecteur d'anomalie A = [m, l, t]</div>
          {([['m', m, setM, 'Metrics'], ['l', l, setL, 'Logs'], ['t', t, setT, 'Traces']] as const).map(
            ([key, val, setter, label]) => (
              <div key={key} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
                  <span style={{ color: 'var(--text2)' }}>{label} <code style={{ color: 'var(--blue2)' }}>{key}</code></span>
                  <strong style={{ color: 'var(--text)' }}>{val.toFixed(2)}</strong>
                </div>
                <input type="range" min={0} max={1} step={0.01} value={val}
                  onChange={e => (setter as (v: number) => void)(parseFloat(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--blue2)' }} />
              </div>
            )
          )}
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 12, color: 'var(--text3)', marginBottom: 6 }}>Sévérité</div>
            <div style={{ display: 'flex', gap: 8 }}>
              {SEV_LABELS.map(s => (
                <button key={s} className={sev === s ? 'btn btn-primary' : 'btn'} onClick={() => setSev(s)}
                  style={{ flex: 1, fontSize: 11 }}>{s}</button>
              ))}
            </div>
          </div>
          {simResult && (
            <div style={{ padding: '12px 14px', borderRadius: 8, border: `1px solid ${decisionColor}`, background: `${decisionColor}10` }}>
              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Health Score</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: decisionColor }}>{simResult.health_score.toFixed(1)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>AI Score</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: decisionColor }}>{simResult.ai_score}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>|A| Norme</div>
                  <div style={{ fontSize: 26, fontWeight: 700, color: 'var(--text)' }}>{simResult.norm.toFixed(3)}</div>
                </div>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>Décision</div>
                  <div style={{ fontSize: 16, fontWeight: 700, color: decisionColor, textTransform: 'uppercase' }}>{simResult.decision}</div>
                </div>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text3)', fontFamily: 'monospace' }}>{simResult.formula}</div>
            </div>
          )}
        </div>


        {/* Decay curve + radar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="panel" style={{ padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>Courbe de decay H(|A|)</div>
            {simResult ? (
              <ResponsiveContainer width="100%" height={150}>
                <LineChart data={simResult.decay_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(99,130,255,0.06)" />
                  <XAxis dataKey="norm" tick={{ fill: 'var(--text3)', fontSize: 9 }} label={{ value: '|A|', position: 'insideRight', fill: 'var(--text3)', fontSize: 10 }} />
                  <YAxis domain={[0, 100]} tick={{ fill: 'var(--text3)', fontSize: 9 }} />
                  <Tooltip contentStyle={{ background: 'var(--card)', border: '1px solid var(--border2)', color: 'var(--text)', fontSize: 11 }} />
                  <Line type="monotone" dataKey="health" stroke={decisionColor} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            ) : <div style={{ height: 150, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text3)', fontSize: 12 }}>Déplacez les curseurs...</div>}
          </div>
          <div className="panel" style={{ padding: '16px 18px' }}>
            <div style={{ fontWeight: 600, marginBottom: 10 }}>Radar — dimensions d'anomalie</div>
            <ResponsiveContainer width="100%" height={160}>
              <RadarChart data={radarData}>
                <PolarGrid stroke="rgba(99,130,255,0.1)" />
                <PolarAngleAxis dataKey="axis" tick={{ fill: 'var(--text3)', fontSize: 9 }} />
                <Radar dataKey="value" stroke="var(--blue2)" fill="var(--blue2)" fillOpacity={0.25} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Injection form */}
      <div className="panel" style={{ padding: '16px 18px', marginBottom: 14 }}>
        <div style={{ fontWeight: 600, marginBottom: 12 }}>Injection d'anomalie dans le pipeline live</div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 10 }}>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Titre</div>
            <input className="input" value={injTitle} onChange={e => setInjTitle(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Règle</div>
            <input className="input" value={injRule} onChange={e => setInjRule(e.target.value)} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Sévérité</div>
            <select className="input" value={injSev} onChange={e => setInjSev(e.target.value as typeof injSev)} style={{ width: '100%' }}>
              {SEV_LABELS.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Valeur métrique</div>
            <input className="input" type="number" value={injMetric} onChange={e => setInjMetric(Number(e.target.value))} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Seuil</div>
            <input className="input" type="number" value={injThresh} onChange={e => setInjThresh(Number(e.target.value))} style={{ width: '100%' }} />
          </div>
          <div>
            <div style={{ fontSize: 11, color: 'var(--text3)', marginBottom: 4 }}>Description</div>
            <input className="input" value={injDesc} onChange={e => setInjDesc(e.target.value)} style={{ width: '100%' }} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 10 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--text2)', cursor: 'pointer' }}>
            <input type="checkbox" checked={useOverride} onChange={e => setUseOverride(e.target.checked)} />
            Utiliser le vecteur A des curseurs (m={m.toFixed(2)}, l={l.toFixed(2)}, t={t.toFixed(2)})
          </label>
        </div>
        <button className="btn btn-primary" disabled={injBusy} onClick={runInject}>
          {injBusy ? 'Injection...' : 'Injecter dans le pipeline IA'}
        </button>
      </div>


      {/* Injection result */}
      {injResult && (
        <div className="panel" style={{ padding: '14px 16px', marginBottom: 14, borderLeft: `3px solid ${DECISION_COLOR[injResult.ai_decision ?? ''] ?? 'var(--blue2)'}` }}>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Résultat d'injection — Alerte #{injResult.id}</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 10 }}>
            {[
              { label: 'AI Score', value: injResult.ai_score ?? '—', color: DECISION_COLOR[injResult.ai_decision ?? ''] },
              { label: 'Décision', value: (injResult.ai_decision ?? '—').toUpperCase(), color: DECISION_COLOR[injResult.ai_decision ?? ''] },
              { label: 'Confiance', value: injResult.ai_confidence != null ? `${Math.round(injResult.ai_confidence * 100)}%` : '—', color: 'var(--text2)' },
              { label: '|A| Norme', value: injResult.anomaly_vector_norm?.toFixed(3) ?? '—', color: 'var(--text2)' },
              { label: 'Remédiation', value: injResult.remediation_status ?? '—', color: injResult.remediation_status === 'applied' || injResult.remediation_status === 'applied_mock' ? 'var(--green)' : 'var(--yellow)' },
            ].map(item => (
              <div key={item.label} style={{ background: 'var(--bg3)', borderRadius: 8, padding: '10px 12px' }}>
                <div style={{ fontSize: 10, color: 'var(--text3)', textTransform: 'uppercase' }}>{item.label}</div>
                <div style={{ fontSize: 16, fontWeight: 700, color: item.color ?? 'var(--text)' }}>{String(item.value)}</div>
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 8 }}>
            <div style={{ flex: 1, background: 'rgba(79,127,255,0.06)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>Recommandation IA</div>
              <div style={{ fontSize: 12, color: 'var(--text2)' }}>{injResult.ai_recommendation ?? '—'}</div>
            </div>
            <div style={{ flex: 1, background: 'rgba(26,188,156,0.06)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px' }}>
              <div style={{ fontSize: 10, color: 'var(--text3)', marginBottom: 4 }}>Plan de remédiation</div>
              <div style={{ fontSize: 12, color: 'var(--text2)' }}>{injResult.remediation_message?.slice(0, 240) ?? '—'}</div>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 16, fontSize: 11, color: 'var(--text3)' }}>
            <span>Vecteur injecté: m={injResult.anomaly_m?.toFixed(3)} · l={injResult.anomaly_l?.toFixed(3)} · t={injResult.anomaly_t?.toFixed(3)}</span>
            <span>Action: {injResult.remediation_action ?? '—'}</span>
            <span>Catégorie: {injResult.ai_category ?? '—'}</span>
          </div>
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
        {/* Knowledge Base */}
        <div className="panel" style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Base de connaissances IA ({kb.length} règles)</div>
          <div style={{ maxHeight: 280, overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
              <thead>
                <tr>
                  {['Mot-clé', 'Catégorie', 'Log w', 'Trace w', 'Bonus'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '4px 8px', color: 'var(--text3)', fontWeight: 500, textTransform: 'uppercase', fontSize: 10 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {kb.map(entry => (
                  <tr key={entry.keyword} style={{ borderTop: '1px solid rgba(99,130,255,0.06)' }}>
                    <td style={{ padding: '4px 8px', color: 'var(--blue2)', fontFamily: 'monospace' }}>{entry.keyword}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--text2)' }}>{entry.category}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--text2)' }}>{entry.log_weight}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--text2)' }}>{entry.trace_weight}</td>
                    <td style={{ padding: '4px 8px', color: 'var(--yellow)', fontWeight: 600 }}>+{entry.score_bonus}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Audit trail */}
        <div className="panel" style={{ padding: '16px 18px' }}>
          <div style={{ fontWeight: 600, marginBottom: 10 }}>Audit Trail — 20 dernières entrées</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 280, overflowY: 'auto' }}>
            {auditLog.length === 0 && <div style={{ color: 'var(--text3)', fontSize: 12, textAlign: 'center', padding: 20 }}>Aucune entrée d'audit</div>}
            {auditLog.map(entry => (
              <div key={entry.id} style={{ padding: '7px 10px', borderRadius: 6, background: 'var(--bg3)', fontSize: 11 }}>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 2 }}>
                  <span style={{ fontWeight: 600, color: 'var(--blue2)', fontFamily: 'monospace' }}>{entry.action}</span>
                  <span style={{ color: 'var(--text3)' }}>par</span>
                  <span style={{ color: 'var(--text2)', fontWeight: 500 }}>{entry.actor}</span>
                  {entry.resource_type && <span style={{ color: 'var(--text3)' }}>→ {entry.resource_type} #{entry.resource_id}</span>}
                </div>
                {entry.detail && <div style={{ color: 'var(--text2)' }}>{entry.detail.slice(0, 120)}</div>}
                <div style={{ color: 'var(--text3)', marginTop: 2 }}>{new Date(entry.created_at).toLocaleString('fr-FR')}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
