import { useState } from 'react'

const STEPS = [
  ['overview', 'National supervisory picture',
    'KPIs, 90-day severity trend, detection-capability coverage, sector risk and the priority review queue. The detector F1 chip shows how the analytics stack scores against seeded ground truth.'],
  ['entities', 'Ranked CSE entities',
    'Every Critical Sector Entity ranked by composite supervisory risk (0–100), with SLA/MTTR/escalation metrics and the 4-window risk trajectory. Click any row to drill down.'],
  ['signals', 'Supervisory signals',
    'Prioritized findings from five detection families. Each carries observed-vs-benchmark, machine-readable evidence, a plain-language explanation, and supervisor actions (review / request info / escalate / dismiss) that feed the audit trail.'],
  ['ingest', 'Structured data ingestion',
    'The CSE SOC submission channel: schema reference, optional HMAC signing, validation, upsert semantics and one-click reseed of the demo dataset.'],
  ['about', 'Architecture & evaluation',
    'Workflow (CSE → SOC → SAT-SA → NCIIPC), capabilities, toolkit stack, and the live detector evaluation (precision/recall vs the planted ground truth).'],
]

export default function Tour({ goTab, onDone }) {
  const [i, setI] = useState(0)
  const [tab, title, body] = STEPS[i]
  function next() {
    if (i === STEPS.length - 1) onDone()
    else { setI(i + 1); goTab(STEPS[i + 1][0]) }
  }
  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-6 no-print">
      <div className="max-w-md w-full rounded-2xl border border-violet-700/60 bg-slate-900 p-6 shadow-2xl">
        <div className="text-[10px] uppercase tracking-widest text-violet-400 mb-2">
          Guided tour · step {i + 1} of {STEPS.length}
        </div>
        <div className="text-lg font-bold text-slate-100">{title}</div>
        <p className="text-sm text-slate-400 mt-2 leading-relaxed">{body}</p>
        <div className="flex gap-2 mt-6">
          <button onClick={onDone} className="text-xs text-slate-500 hover:text-slate-300">Skip</button>
          <div className="ml-auto flex gap-2">
            {i > 0 && (
              <button onClick={() => { setI(i - 1); goTab(STEPS[i - 1][0]) }}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300">Back</button>
            )}
            <button onClick={next}
              className="rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-1.5 text-xs font-semibold text-white">
              {i === STEPS.length - 1 ? 'Finish' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
