import { useEffect, useState } from 'react'
import { get } from '../api.js'
import { Loading } from '../ui.jsx'

export default function Bulletin({ back }) {
  const [b, setB] = useState(null)
  useEffect(() => { get('/bulletin').then(setB) }, [])
  if (!b) return <Loading />
  return (
    <div className="max-w-3xl mx-auto">
      <div className="no-print flex gap-2 mb-4">
        <button onClick={back} className="text-xs text-slate-400 hover:text-slate-200">← Console</button>
        <button onClick={() => window.print()}
          className="ml-auto rounded-lg bg-violet-600 hover:bg-violet-500 px-4 py-1.5 text-xs font-semibold text-white">
           Print / Save as PDF
        </button>
      </div>

      <div className="bg-white text-slate-900 rounded-xl p-8 shadow-xl print:shadow-none">
        <div className="border-2 border-slate-900 text-center text-[10px] font-bold tracking-[0.25em] py-1 mb-5">
          NCIIPC · WEEKLY SUPERVISORY BULLETIN · OFFLINE ENCLAVE COPY
        </div>
        <div className="flex justify-between border-b-2 border-slate-900 pb-3 text-[12px]">
          <div>
            <div className="text-2xl font-black tracking-wide">SAT-SA</div>
            <div className="text-slate-600 text-[11px]">Supervisory Analytics Tool for SOC Assessment</div>
          </div>
          <div className="text-right text-slate-600 text-[11px]">
            <div>Assessment week ending <b className="text-slate-900">{b.week}</b></div>
            <div>Ref: SAT-SA/BULL/{b.week}</div>
          </div>
        </div>

        <h3 className="text-sm font-bold mt-5 mb-1 border-b border-slate-400">1. Week in numbers</h3>
        <table className="w-full text-[12px]">
          <tbody>
            <tr><td className="py-1 pr-3 text-slate-600">Alerts submitted (all CSEs, 7d)</td><td className="py-1 text-right font-bold">{b.alerts7.toLocaleString('en-IN')}</td></tr>
            <tr><td className="py-1 pr-3 text-slate-600">Critical alerts</td><td className="py-1 text-right font-bold">{b.critical7.toLocaleString('en-IN')}</td></tr>
            <tr><td className="py-1 pr-3 text-slate-600">Escalations to NCIIPC</td><td className="py-1 text-right font-bold">{b.escalations7}</td></tr>
            <tr><td className="py-1 pr-3 text-slate-600">Reporting compliance (30d)</td><td className="py-1 text-right font-bold">{b.compliance}%</td></tr>
          </tbody>
        </table>

        <h3 className="text-sm font-bold mt-5 mb-1 border-b border-slate-400">2. Active supervisory signals by capability</h3>
        <table className="w-full text-[12px]">
          <tbody>
            {Object.entries(b.signals_by_category).map(([k, v]) => (
              <tr key={k}><td className="py-1 pr-3 text-slate-600">{k}</td><td className="py-1 text-right font-bold">{v}</td></tr>
            ))}
          </tbody>
        </table>

        <h3 className="text-sm font-bold mt-5 mb-1 border-b border-slate-400">3. Priority review queue (top 5)</h3>
        <ol className="list-decimal ml-5 text-[12px] mt-1 space-y-0.5">
          {b.top_risk.map((e) => (
            <li key={e.id}>{e.name} ({e.id}) — composite risk <b>{e.score}/100</b></li>
          ))}
        </ol>

        <h3 className="text-sm font-bold mt-5 mb-1 border-b border-slate-400">4. Trajectory watch-list</h3>
        <p className="text-[12px] text-slate-700 mt-1">
          {b.deteriorating.length === 0 ? 'No entity deteriorated ≥5 risk points over the assessment horizon.' :
            b.deteriorating.map((d) => `${d.name}: ${d.before} → ${d.now} (+${d.delta})`).join(' · ')}
        </p>
        {b.improving.length > 0 && (
          <p className="text-[12px] text-slate-600 mt-1">
            Improving: {b.improving.map((d) => `${d.name} (${d.before} → ${d.now})`).join(' · ')}
          </p>
        )}

        <div className="grid grid-cols-2 gap-10 mt-12 text-[11px] text-slate-600">
          <div className="border-t border-slate-500 pt-1">Prepared by (SAT-SA automated analysis)</div>
          <div className="border-t border-slate-500 pt-1">NCIIPC Supervisor — examination & decision</div>
        </div>
      </div>
    </div>
  )
}
