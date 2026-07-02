import { useEffect, useState } from 'react'
import { exportUrl, getReportSummary } from '../api/client'
import type { ReportSummary } from '../types'

function Metric({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  return (
    <div className="panel" style={{ padding: '16px 18px' }}>
      <div style={{ color: 'var(--text3)', fontSize: 11, textTransform: 'uppercase', marginBottom: 8 }}>{label}</div>
      <div style={{ color, fontSize: 28, fontWeight: 700 }}>{value}</div>
      <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 6 }}>{sub}</div>
    </div>
  )
}

export default function ReportsPage() {
  const [hours, setHours] = useState(24)
  const [summary, setSummary] = useState<ReportSummary | null>(null)

  useEffect(() => {
    getReportSummary(hours).then(setSummary)
  }, [hours])

  const vmAvailability = summary ? Math.round((summary.availability.active_vms / Math.max(summary.inventory.vms, 1)) * 100) : 0
  const podAvailability = summary ? Math.round((summary.availability.running_pods / Math.max(summary.inventory.pods, 1)) * 100) : 0

  return (
    <div style={{ padding: '20px 24px' }}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, marginBottom: 6 }}>Rapports operationnels</h2>
          <div style={{ color: 'var(--text3)', fontSize: 12 }}>Synthese de disponibilite, capacite et incidents sur la periode choisie.</div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {[24, 168, 720].map(h => (
            <button key={h} className={hours === h ? 'btn btn-primary' : 'btn'} onClick={() => setHours(h)}>
              {h === 24 ? '24h' : h === 168 ? '7j' : '30j'}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, minmax(0, 1fr))', gap: 12, marginBottom: 18 }}>
        <Metric label="Disponibilite VMs" value={`${vmAvailability}%`} sub={`${summary?.availability.active_vms ?? 0}/${summary?.inventory.vms ?? 0} actives`} color="var(--blue2)" />
        <Metric label="Disponibilite Pods" value={`${podAvailability}%`} sub={`${summary?.availability.running_pods ?? 0}/${summary?.inventory.pods ?? 0} running`} color="var(--teal2)" />
        <Metric label="CPU moyen VM" value={`${summary?.metrics.avg_vm_cpu ?? 0}%`} sub="moyenne sur la periode" color="var(--yellow)" />
        <Metric label="Alertes actives" value={summary?.alerts.active ?? 0} sub={`${summary?.alerts.critical_active ?? 0} critiques`} color="var(--red)" />
        <Metric label="ROI automatisation" value={`${summary?.financial.roi_percent ?? 0}%`} sub={`${summary?.financial.estimated_period_savings ?? 0} MAD economises`} color="var(--green)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.25fr 0.75fr', gap: 12 }}>
        <div className="panel" style={{ padding: 18 }}>
          <div style={{ fontWeight: 700, marginBottom: 14 }}>Resume de sante</div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 12 }}>
            {[
              ['VMs inventoriees', summary?.inventory.vms ?? 0],
              ['Pods inventories', summary?.inventory.pods ?? 0],
              ['Pods en erreur', summary?.availability.failed_pods ?? 0],
              ['Alertes declenchees', summary?.alerts.triggered_in_period ?? 0],
              ['Warnings actifs', summary?.alerts.warning_active ?? 0],
              ['Alertes acquittees', summary?.alerts.acknowledged_active ?? 0],
              ['RAM moyenne VM', `${summary?.metrics.avg_vm_ram ?? 0}%`],
              ['RAM moyenne pod', `${summary?.metrics.avg_pod_ram_mb ?? 0} MB`],
            ].map(([label, value]) => (
              <div key={label} style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 8, background: 'var(--bg3)' }}>
                <div style={{ color: 'var(--text3)', fontSize: 11, marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel" style={{ padding: 18 }}>
          <div style={{ fontWeight: 700, marginBottom: 14 }}>Exports</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <a className="btn btn-primary" href={exportUrl('alerts')}>Exporter toutes les alertes</a>
            <a className="btn" href={exportUrl('alerts', 'active')}>Exporter alertes actives</a>
            <a className="btn" href={exportUrl('vms')}>Exporter VMs</a>
            <a className="btn" href={exportUrl('pods')}>Exporter pods</a>
          </div>
          {summary && (
            <div style={{ color: 'var(--text3)', fontSize: 11, marginTop: 16 }}>
              Genere le {new Date(summary.generated_at).toLocaleString('fr-FR')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
