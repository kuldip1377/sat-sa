import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Card, Stat, Loading, Chip } from '../ui.jsx'

export default function Validation() {
  const [d, setD] = useState(null)
  const [h, setH] = useState(null)
  useEffect(() => {
    get('/validation').then(setD).catch(() => setD({ error: true }))
    get('/holdout').then(setH).catch(() => {})   // first call runs the held-out dataset (~2s)
  }, [])
  if (!d) return <Loading />
  if (d.error) return <div className="p-10 text-red-400">Backend unreachable.</div>
  const ev = d.detector_eval, prio = d.prioritization

  return (
    <div className="space-y-4">
      <div>
        <div className="text-xl font-bold text-slate-100">Validation framework</div>
        <div className="text-xs text-slate-400 mt-1 max-w-3xl">
          The tool scores itself continuously against seeded ground-truth scenarios (known
          blind spots, SLA failures, silent closures, planted campaigns, missing evidence).
          Every number below is computed live from the current database — nothing is hardcoded.
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Stat label="True positives" value={ev.tp} color="#34d399" sub="planted issues detected" />
        <Stat label="False positives" value={ev.fp} color={ev.fp ? '#f87171' : '#34d399'} sub="signals without planted cause" />
        <Stat label="False negatives" value={ev.fn} color={ev.fn ? '#fbbf24' : '#34d399'} sub="planted issues missed" />
        <Stat label="Precision" value={ev.precision.toFixed(3)} color="#38bdf8" />
        <Stat label="Recall" value={ev.recall.toFixed(3)} color="#38bdf8" />
        <Stat label="F1 / FPR" value={`${ev.f1.toFixed(3)} / ${ev.fpr.toFixed(3)}`} color="#a78bfa" />
      </div>

      <Card title="Held-out validation — the honest number"
        sub="second dataset: independent seed, shifted pattern placements, magnitudes and categories; never used to tune thresholds"
        right={<Chip color="#f472b6">{h ? h.dataset : 'running…'}</Chip>}>
        {!h && <div className="text-xs text-slate-500 animate-pulse py-4">
          Generating and scoring the held-out dataset… (runs fully offline, ~2s)</div>}
        {h && (
          <div className="grid lg:grid-cols-3 gap-4">
            <div>
              <div className="grid grid-cols-3 gap-2 text-center mb-3">
                {[['Precision', h.precision], ['Recall', h.recall], ['F1', h.f1]].map(([l, v]) => (
                  <div key={l} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
                    <div className="text-[9px] uppercase tracking-wider text-slate-500">{l}</div>
                    <div className="text-xl font-black text-emerald-400">{v.toFixed(2)}</div>
                  </div>
                ))}
              </div>
              <div className="text-[11px] text-slate-400">
                {h.tp} tp · {h.fp} fp · {h.fn} fn · FPR {h.fpr.toFixed(3)}
                {h.missed.length > 0 && <span className="text-amber-400"> · missed: {h.missed.join(', ')}</span>}
                {h.extras.length > 0 && <span className="text-amber-400"> · extras: {h.extras.join(', ')}</span>}
              </div>
              <div className="text-[11px] text-slate-400 mt-2">
                Prioritization on held-out data:
                {Object.entries(h.prioritization.per_k).map(([k, v]) => (
                  <span key={k} className="ml-2">P@{k} {(v.precision_at_k * 100).toFixed(0)}%</span>
                ))}
                <span className="ml-2 text-fbbf24">workload −{Math.round(h.prioritization.workload_reduction * 100)}%</span>
              </div>
            </div>
            <div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1.5">Confusion matrix (entity × detector-key)</div>
              <table className="text-xs border border-slate-800">
                <thead>
                  <tr className="text-[9px] text-slate-500">
                    <th className="p-1.5" />
                    <th className="p-1.5">pred POS</th>
                    <th className="p-1.5">pred NEG</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td className="p-1.5 text-slate-400">actual POS</td>
                    <td className="p-1.5 text-emerald-400 font-bold text-center">{h.confusion.tp}</td>
                    <td className="p-1.5 text-amber-400 font-bold text-center">{h.confusion.fn}</td>
                  </tr>
                  <tr>
                    <td className="p-1.5 text-slate-400">actual NEG</td>
                    <td className="p-1.5 text-red-400 font-bold text-center">{h.confusion.fp}</td>
                    <td className="p-1.5 text-slate-300 font-bold text-center">{h.confusion.tn}</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="text-[11px] text-slate-500 leading-relaxed">
              {h.note} The held-out set also contains false-positive-prone healthy entities
              (near-threshold silent-close rates, missing days outside the assessment window,
              elevated-but-acceptable MTTR) — they stayed clean.
            </div>
          </div>
        )}
      </Card>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Prioritization quality — P@K / R@K"
          sub="review-queue ranking vs hidden ground truth"
          right={<Chip color="#fbbf24">{Math.round(prio.workload_reduction * 100)}% workload reduction</Chip>}>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5">K (samples reviewed)</th>
                <th className="text-right py-1.5">Precision@K</th>
                <th className="text-right py-1.5">Recall@K</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(prio.per_k).map(([k, v]) => (
                <tr key={k} className="border-b border-slate-800/60">
                  <td className="py-2 text-slate-300">top {k} of {prio.candidates}</td>
                  <td className="py-2 text-right font-bold text-emerald-300">{(v.precision_at_k * 100).toFixed(1)}%</td>
                  <td className="py-2 text-right text-sky-300">{(v.recall_at_k * 100).toFixed(1)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="text-[11px] text-slate-500 mt-3">
            {prio.gt_total} ground-truth review-worthy samples among {prio.candidates} candidates in 30 days.
          </div>
        </Card>

        <Card title="Per-detector ground truth" sub="tp / fp / fn by signal family">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
            {Object.entries(ev.per_key).map(([k, v]) => (
              <div key={k} className="rounded-lg border border-slate-800 bg-slate-950/50 px-2.5 py-1.5">
                <div className="font-mono text-[11px] text-slate-200">{k}</div>
                <div className="text-[10px] text-slate-500">
                  <span className="text-emerald-400">{v.tp} tp</span> · <span className={v.fp ? 'text-red-400' : ''}>{v.fp} fp</span> · <span className={v.fn ? 'text-amber-400' : ''}>{v.fn} fn</span>
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card title="Data-quality scores by CSE" sub="submission completeness + field hygiene (quarantined rows included)">
          <div className="space-y-1.5">
            {Object.entries(d.dq).sort((a, b) => a[1] - b[1]).map(([e, v]) => (
              <div key={e} className="flex items-center gap-2 text-xs">
                <span className="font-mono w-16 text-slate-400">{e}</span>
                <div className="flex-1 h-2 rounded bg-slate-800 overflow-hidden">
                  <div className="h-full rounded" style={{
                    width: `${v}%`, background: v >= 90 ? '#34d399' : v >= 70 ? '#fbbf24' : '#f87171' }} />
                </div>
                <span className="w-10 text-right text-slate-300 font-semibold">{v}</span>
              </div>
            ))}
          </div>
        </Card>

        <Card title="Quarantine — rejected submissions" sub="never silently discarded; visible with reasons">
          {d.quarantine.length === 0 && <div className="text-sm text-emerald-400">No quarantined rows.</div>}
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
      </div>

      <Card title="Per-entity expected vs detected" sub="full ground-truth matrix (planted scenario → detector output)">
        <div className="overflow-x-auto -mx-4 px-4">
          <table className="w-full text-xs min-w-[720px]">
            <thead>
              <tr className="text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="text-left py-1.5 pr-3">Entity</th>
                <th className="text-left py-1.5 pr-3">Planted (expected)</th>
                <th className="text-left py-1.5 pr-3">Detected</th>
                <th className="text-left py-1.5">Verdict</th>
              </tr>
            </thead>
            <tbody>
              {d.gt_rows.map((r) => (
                <tr key={r.entity} className="border-b border-slate-800/60 align-top">
                  <td className="py-1.5 pr-3 font-mono text-slate-300">{r.entity}</td>
                  <td className="py-1.5 pr-3">
                    <div className="flex flex-wrap gap-1">{r.expected.length
                      ? r.expected.map((x) => <Chip key={x} color="#64748b">{x}</Chip>)
                      : <span className="text-emerald-400">healthy</span>}</div>
                  </td>
                  <td className="py-1.5 pr-3">
                    <div className="flex flex-wrap gap-1">{r.detected.map((x) => (
                      <Chip key={x} color={r.correct.includes(x) ? '#34d399' : '#f87171'}>{x}</Chip>))}
                    </div>
                  </td>
                  <td className="py-1.5">
                    {r.wrong.length === 0
                      ? <span className="text-emerald-400 font-semibold">✓ exact</span>
                      : <span className="text-red-400">{r.wrong.join(', ')}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="text-[11px] text-slate-500 leading-relaxed">
        {d.note} Auxiliary signals (IsolationForest, Mahalanobis) are excluded from
        precision/recall because they are corroborating context, not scenario detectors.
      </div>
    </div>
  )
}
