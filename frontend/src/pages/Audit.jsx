import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Loading, Chip } from '../ui.jsx'

const EVENT_COLOR = {
  login: '#38bdf8', ingest: '#34d399', config: '#fbbf24', reset: '#f87171',
  'signal_action': '#a78bfa', 'holdout-eval': '#f472b6',
}

export default function Audit() {
  const [d, setD] = useState(null)
  useEffect(() => { get('/audit?limit=200').then((r) => setD(r.audit)).catch(() => setD([])) }, [])
  if (!d) return <Loading />

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-bold text-slate-100">Audit trail</div>
        <div className="text-xs text-slate-400 mt-1 max-w-3xl">
          Every privileged operation — logins, data ingestion, supervisor actions on findings,
          configuration and weight changes, reseeds — is recorded with user and timestamp.
          Combined with the notary hash chain, assessment runs are reproducible and tamper-evident.
        </div>
      </div>

      <Card title={`Recorded events (latest ${d.length})`}
        right={<Chip color="#64748b">auditor role: read-only</Chip>}>
        {d.length === 0 && (
          <div className="text-sm text-slate-500 py-4">
            No events yet in this session. Logins, ingests and actions will appear here.
          </div>
        )}
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full text-xs min-w-[720px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5 pr-3">Timestamp</th>
                <th className="text-left py-1.5 pr-3">User</th>
                <th className="text-left py-1.5 pr-3">Event</th>
                <th className="text-left py-1.5">Detail</th>
              </tr>
            </thead>
            <tbody>
              {d.map((a, i) => (
                <tr key={i} className="border-b border-slate-800/60">
                  <td className="py-1.5 pr-3 font-mono text-slate-500 whitespace-nowrap">{a.ts}</td>
                  <td className="py-1.5 pr-3 text-violet-300 font-semibold">{a.user}</td>
                  <td className="py-1.5 pr-3">
                    <Chip color={EVENT_COLOR[a.event] || '#64748b'}>{a.event}</Chip>
                  </td>
                  <td className="py-1.5 text-slate-400 break-all">{a.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card title="Evidence notarization chain" sub="SHA-256 fingerprint of the evidence base per analytics run — tamper-evident extension point for a permissioned ledger">
        <Notary />
      </Card>
    </div>
  )
}

function Notary() {
  const [n, setN] = useState(null)
  useEffect(() => { get('/notary').then(setN).catch(() => {}) }, [])
  if (!n) return <Loading />
  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Chip color={n.intact ? '#34d399' : '#f87171'}>{n.intact ? 'chain intact' : 'CHAIN BROKEN'}</Chip>
        <span className="text-[11px] text-slate-400">{n.length} entries</span>
      </div>
      <div className="space-y-1 max-h-52 overflow-auto">
        {n.chain.slice().reverse().map((r, i) => (
          <div key={i} className="text-[10px] font-mono border-b border-slate-800/60 pb-1 flex gap-2">
            <span className="text-slate-500 whitespace-nowrap">{r.ts}</span>
            <span className="text-slate-400">{r.event}</span>
            <span className="text-slate-600 truncate">…{r.hash.slice(-24)}</span>
          </div>
        ))}
      </div>
      <div className="text-[10px] text-slate-500 mt-2">
        No sensitive SOC content is hashed into a public ledger; the chain stores fingerprints
        only. Replace the local chain with a permissioned blockchain without touching analytics.
      </div>
    </div>
  )
}
