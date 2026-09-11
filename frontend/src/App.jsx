import { useEffect, useState } from 'react'
import Overview from './pages/Overview.jsx'
import Entities from './pages/Entities.jsx'
import EntityDetail from './pages/EntityDetail.jsx'
import Signals from './pages/Signals.jsx'
import ReviewQueue from './pages/ReviewQueue.jsx'
import Validation from './pages/Validation.jsx'
import EvidenceExplorer from './pages/EvidenceExplorer.jsx'
import DataQuality from './pages/DataQuality.jsx'
import Assessments from './pages/Assessments.jsx'
import Configuration from './pages/Configuration.jsx'
import Audit from './pages/Audit.jsx'
import Ingest from './pages/Ingest.jsx'
import About from './pages/About.jsx'
import Report from './pages/Report.jsx'
import Bulletin from './pages/Bulletin.jsx'
import Login from './pages/Login.jsx'
import Tour from './components/Tour.jsx'
import ErrorBoundary from './components/ErrorBoundary.jsx'
import { Chip, Loading } from './ui.jsx'
import { get } from './api.js'

const TABS = [
  ['overview', 'Supervisor Dashboard'],
  ['entities', 'CSE Entities'],
  ['signals', 'Supervisory Signals'],
  ['queue', 'Review Queue'],
  ['graph', 'Evidence Graph'],
  ['dq', 'Data Quality'],
  ['assessments', 'Assessments'],
  ['validation', 'Benchmark & Validation'],
  ['config', 'Configuration'],
  ['audit', 'Audit'],
  ['ingest', 'Data Ingest'],
  ['about', 'Architecture'],
]

export default function App() {
  const [auth, setAuth] = useState('checking')
  const [tab, setTab] = useState('overview')
  const [eid, setEid] = useState(null)
  const [tour, setTour] = useState(false)
  const openEntity = (id) => { setEid(id); setTab('detail') }
  const openReport = (id) => { setEid(id); setTab('report') }

  useEffect(() => {
    get('/health').then((h) => setAuth(
      h.auth_enabled && !localStorage.getItem('satsa_token') ? 'login' : 'in'))
      .catch(() => setAuth('in'))
    const on401 = () => { localStorage.removeItem('satsa_token'); setAuth('login') }
    window.addEventListener('satsa:401', on401)
    return () => window.removeEventListener('satsa:401', on401)
  }, [])

  useEffect(() => {
    if (auth === 'in' && !localStorage.getItem('satsa_tour_done')) setTour(true)
  }, [auth])

  if (auth === 'checking') return <Loading />
  if (auth === 'login') return <Login onLogin={() => setAuth('in')} />

  return (
    <div className="min-h-screen text-slate-200">
      <header className="no-print border-b border-slate-800 bg-slate-950/80 backdrop-blur sticky top-0 z-20">
        <div className="max-w-[1400px] mx-auto px-5 py-3 flex flex-wrap items-center gap-3">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" aria-label="SAT-SA logo">
            <path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3z" fill="#7c3aed" opacity="0.25" />
            <path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3z" stroke="#a78bfa" strokeWidth="1.4" />
            <path d="M8 12l2.5 2.5L16 9" stroke="#a78bfa" strokeWidth="1.8" strokeLinecap="round" />
          </svg>
          <div className="mr-auto">
            <div className="font-extrabold tracking-wide text-lg leading-5">
              SAT-<span className="text-violet-400">SA</span>
            </div>
            <div className="text-[11px] text-slate-400">
              Supervisory Analytics Tool for SOC Assessment
            </div>
          </div>
          <button onClick={() => setTour(true)}
            className="text-[11px] text-violet-300 border border-violet-700/60 rounded-full px-3 py-1 hover:bg-violet-900/30">
            ▶ Guided tour
          </button>
          <Chip color="#a78bfa">NCIIPC Supervisor Console</Chip>
          <Chip color="#34d399">Offline / Air-gapped</Chip>
          <Chip color="#64748b">SIH 2026 · PS 26157</Chip>
        </div>
        <nav className="max-w-[1400px] mx-auto px-5 flex gap-1 overflow-x-auto">
          {TABS.map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)}
              className={`px-3.5 py-2 text-[13px] font-medium border-b-2 whitespace-nowrap transition-colors ${
                tab === id ? 'border-violet-400 text-violet-300'
                           : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
              {label}
            </button>
          ))}
          {tab === 'detail' && (
            <button className="px-3.5 py-2 text-[13px] font-medium border-b-2 border-violet-400 text-violet-300 whitespace-nowrap">
              Entity Drill-down {eid && `· ${eid}`}
            </button>
          )}
          {tab === 'report' && (
            <button className="px-3.5 py-2 text-[13px] font-medium border-b-2 border-violet-400 text-violet-300 whitespace-nowrap">
              Supervisor Report {eid && `· ${eid}`}
            </button>
          )}
          {tab === 'bulletin' && (
            <button className="px-3.5 py-2 text-[13px] font-medium border-b-2 border-violet-400 text-violet-300 whitespace-nowrap">
              Weekly Bulletin
            </button>
          )}
        </nav>
      </header>

      <main className="max-w-[1400px] mx-auto px-5 py-5">
        <ErrorBoundary>
          {tab === 'overview' && <Overview openEntity={openEntity} openBulletin={() => setTab('bulletin')} />}
          {tab === 'entities' && <Entities openEntity={openEntity} />}
          {tab === 'detail' && eid && <EntityDetail eid={eid} openEntity={openEntity} openReport={openReport} back={() => setTab('entities')} />}
          {tab === 'report' && eid && <Report eid={eid} back={() => setTab('detail')} />}
          {tab === 'bulletin' && <Bulletin back={() => setTab('overview')} />}
          {tab === 'signals' && <Signals openEntity={openEntity} />}
          {tab === 'queue' && <ReviewQueue openEntity={openEntity} />}
          {tab === 'graph' && <EvidenceExplorer openEntity={openEntity} />}
          {tab === 'dq' && <DataQuality />}
          {tab === 'assessments' && <Assessments openEntity={openEntity} />}
          {tab === 'validation' && <Validation />}
          {tab === 'config' && <Configuration />}
          {tab === 'audit' && <Audit />}
          {tab === 'ingest' && <Ingest />}
          {tab === 'about' && <About />}
        </ErrorBoundary>
      </main>

      <footer className="no-print max-w-[1400px] mx-auto px-5 pb-6 text-[11px] text-slate-500">
        All operations are performed in a secure, offline (air-gapped) environment controlled by
        NCIIPC. Demo runs on seeded synthetic SOC operational data.
      </footer>

      {tour && (
        <Tour goTab={(t) => setTab(t)} onDone={() => {
          setTour(false)
          localStorage.setItem('satsa_tour_done', '1')
        }} />
      )}
    </div>
  )
}
