import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Stat, Loading, Chip } from '../ui.jsx'

export default function DataQuality() {
  const [d, setD] = useState(null)
  useEffect(() => { get('/dataquality').then(setD).catch(() => setD({ error: true })) }, [])
  if (!d) return <Loading />
  if (d.error) return <div className="p-10 text-red-400">Backend unreachable.</div>

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <div className="text-xl font-bold text-slate-100">Data Quality — pre-analytics gate</div>
          <div className="text-xs text-slate-400 mt-1 max-w-2xl">
            Every submission passes validation BEFORE analytics. Rejected rows are quarantined
            with reasons — never silently discarded; degraded rows are accepted but flagged.
          </div>
        </div>
        <a href="/api/dataquality/export"
          className="no-print rounded-lg bg-violet-600 hover:bg-violet-500 px-3 py-1.5 text-[11px] font-semibold text-white">
          ⬇ flagged records (CSV)
        </a>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Records in window" value={d.totals.records.toLocaleString('en-IN')} color="#38bdf8" sub="daily submissions + rejects" />
        <Stat label="Valid" value={d.totals.valid.toLocaleString('en-IN')} color="#34d399" />
        <Stat label="Warning (accepted, flagged)" value={d.totals.warning} color="#fbbf24" />
        <Stat label="Rejected (quarantined)" value={d.totals.rejected} color={d.totals.rejected ? '#f87171' : '#34d399'} />
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Quality score dimensions" sub={`overall ${d.overall}/100 — weights: schema .25 · completeness .25 · consistency .2 · timeliness .15 · uniqueness .15`}>
          <div className="space-y-2">
            {Object.entries(d.dimensions).map(([k, v]) => (
              <div key={k}>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-400">{k}</span>
                  <span className="font-semibold text-slate-200">{v}</span>
                </div>
                <div className="h-1.5 bg-slate-800 rounded overflow-hidden">
                  <div className="h-full" style={{ width: `${v}%`, background: v >= 90 ? '#34d399' : v >= 70 ? '#fbbf24' : '#f87171' }} />
                </div>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2 mt-4 text-center">
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
              <div className="text-[10px] text-slate-500 uppercase">Duplicates</div>
              <div className="text-lg font-bold text-slate-200">{d.duplicates}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
              <div className="text-[10px] text-slate-500 uppercase">Invalid values</div>
              <div className="text-lg font-bold text-slate-200">{d.invalid_values}</div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/50 p-2">
              <div className="text-[10px] text-slate-500 uppercase">Entities w/ gaps</div>
              <div className="text-lg font-bold text-slate-200">{Object.keys(d.reporting_gaps).length}</div>
            </div>
          </div>
        </Card>

        <Card title="Per-entity quality & reporting gaps" sub="30-day window">
          <div className="space-y-1.5">
            {Object.entries(d.per_entity).sort((a, b) => a[1] - b[1]).map(([e, v]) => (
              <div key={e} className="flex items-center gap-2 text-xs">
                <span className="font-mono w-16 text-slate-400">{e}</span>
                <div className="flex-1 h-2 rounded bg-slate-800 overflow-hidden">
                  <div className="h-full rounded" style={{ width: `${v}%`, background: v >= 90 ? '#34d399' : v >= 70 ? '#fbbf24' : '#f87171' }} />
                </div>
                <span className="w-10 text-right text-slate-300 font-semibold">{v}</span>
                <span className="w-24 text-right text-[10px] text-slate-500">
                  {d.reporting_gaps[e] ? `${d.reporting_gaps[e]} missing day(s)` : ''}
                  {d.missing_fields_pct[e] ? ` · ${d.missing_fields_pct[e]}% fields` : ''}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Quarantined submissions" sub="rejected rows with machine-readable reasons">
          {d.quarantine.length === 0 && <div className="text-sm text-emerald-400">None.</div>}
          <div className="space-y-1.5 max-h-64 overflow-auto">
            {d.quarantine.map((q, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] border-b border-slate-800/60 pb-1">
                <span className="font-mono text-slate-400 w-16">{q.entity_id}</span>
                <span className="text-red-300 flex-1">{q.reason}</span>
                <span className="text-slate-600">{q.ts.slice(5, 16).replace('T', ' ')}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Accepted-but-flagged records" sub="warning tier — usable for analytics, visible to the supervisor">
          {d.flagged.length === 0 && <div className="text-sm text-emerald-400">None.</div>}
          <div className="space-y-1.5 max-h-64 overflow-auto">
            {d.flagged.slice(0, 60).map((f, i) => (
              <div key={i} className="flex items-center gap-2 text-[11px] border-b border-slate-800/60 pb-1">
                <span className="font-mono text-slate-400 w-16">{f.entity_id}</span>
                <span className="text-slate-500 w-20">{f.date}</span>
                <Chip color="#fbbf24">{f.flag}</Chip>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="text-[11px] text-slate-500">{d.note}</div>
    </div>
  )
}
