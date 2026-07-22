import { useState, useEffect } from 'react'
import Dashboard from './components/Dashboard'
import Upload from './components/Upload'
import Query from './components/Query'
import SpecCompliance from './components/SpecCompliance'
import ScheduleRisk from './components/ScheduleRisk'
import RFICopilot from './components/RFICopilot'
import SupplyChain from './components/SupplyChain'
import CommissioningQA from './components/CommissioningQA'
import Documents from './components/Documents'
import EvalDashboard from './components/EvalDashboard'

const NAV = [
  { id: 'dashboard',        label: 'Dashboard',        icon: '🏠' },
  { id: 'rag-query',        label: 'RAG Query',        icon: '🔍' },
  { id: 'spec-compliance',  label: 'Spec Compliance',  icon: '✅' },
  { id: 'schedule-risk',    label: 'Schedule Risk',    icon: '📅' },
  { id: 'rfi-copilot',      label: 'RFI Copilot',      icon: '💬' },
  { id: 'supply-chain',     label: 'Supply Chain',     icon: '🚚' },
  { id: 'commissioning-qa', label: 'Commissioning QA', icon: '🔬' },
  { id: 'documents',        label: 'Documents',        icon: '📁' },
  { id: 'upload',           label: 'Upload Documents', icon: '📤' },
  { id: 'eval',             label: 'Quality Metrics',   icon: '📊' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [health, setHealth] = useState('loading')
  const [ollamaReady, setOllamaReady] = useState(false)
  const [docCount, setDocCount] = useState(0)

  useEffect(() => {
    const check = async () => {
      try {
        const r = await fetch('/api/health')
        const d = await r.json()
        setHealth(d.status)
        setOllamaReady(d.services?.ollama?.mistral_ready ?? false)
        setDocCount(d.services?.qdrant?.documents ?? 0)
      } catch { setHealth('degraded'); setOllamaReady(false) }
    }
    check()
    const iv = setInterval(check, 15000)
    return () => clearInterval(iv)
  }, [])

  return (
    <div className="flex h-screen bg-slate-950 font-sans">
      {/* Sidebar */}
      <div className="w-60 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 flex flex-col h-screen fixed left-0 top-0 shadow-2xl">
        {/* Branding */}
        <div className="p-5 border-b border-slate-700">
          <h1 className="text-white font-black text-lg leading-tight">EPC Intelligence</h1>
          <p className="text-slate-400 text-xs mt-0.5">Data Centre Platform</p>
          <div className="mt-3 flex items-center gap-2">
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1.5 ${
              health === 'ok' ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : health === 'loading' ? 'bg-slate-500/20 text-slate-400 border border-slate-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${health === 'ok' ? 'bg-green-400 animate-pulse' : health === 'loading' ? 'bg-slate-400' : 'bg-red-400 animate-pulse'}`} />
              {health === 'ok' ? 'Online' : health === 'loading' ? 'Starting' : 'Degraded'}
            </span>
          </div>
        </div>

        {/* Banners */}
        {!ollamaReady && health !== 'loading' && (
          <div className="mx-3 mt-2 p-2.5 bg-yellow-500/10 border border-yellow-500/30 rounded-lg text-yellow-300 text-xs">
            ⏳ Mistral 7B loading… First query may take 1–2 min.
          </div>
        )}
        {ollamaReady && docCount === 0 && (
          <div className="mx-3 mt-2 p-2.5 bg-blue-500/10 border border-blue-500/30 rounded-lg text-blue-300 text-xs">
            📄 No documents yet. Upload seed data first.
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto mt-1">
          {NAV.map(item => (
            <button key={item.id} onClick={() => setActiveTab(item.id)}
              className={`w-full text-left px-3 py-2.5 rounded-xl flex items-center gap-3 text-sm font-medium transition-all duration-150 ${
                activeTab === item.id
                  ? 'bg-blue-600 text-white shadow-lg shadow-blue-500/25'
                  : 'text-slate-400 hover:text-white hover:bg-slate-700/60'
              }`}>
              <span className="text-base">{item.icon}</span>
              {item.label}
            </button>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-slate-700">
          <p className="text-slate-500 text-xs">ET AI Hackathon 2026</p>
          <p className="text-slate-600 text-xs">Powered by Mistral 7B</p>
        </div>
      </div>

      {/* Main Content */}
      <div className="ml-60 flex-1 overflow-y-auto">
        <div className="p-8">
          <div key={activeTab} className="slide-in">
            {activeTab === 'dashboard'        && <Dashboard onNavigate={setActiveTab} />}
            {activeTab === 'upload'           && <Upload />}
            {activeTab === 'rag-query'        && <Query />}
            {activeTab === 'spec-compliance'  && <SpecCompliance />}
            {activeTab === 'schedule-risk'    && <ScheduleRisk />}
            {activeTab === 'rfi-copilot'      && <RFICopilot />}
            {activeTab === 'supply-chain'     && <SupplyChain />}
            {activeTab === 'commissioning-qa' && <CommissioningQA />}
            {activeTab === 'documents'        && <Documents />}
            {activeTab === 'eval'             && <EvalDashboard />}
          </div>
        </div>
      </div>
    </div>
  )
}