import { useState, useEffect } from 'react'
import Upload from './components/Upload'
import Query from './components/Query'
import SpecCompliance from './components/SpecCompliance'
import ScheduleRisk from './components/ScheduleRisk'
import RFICopilot from './components/RFICopilot'
import Documents from './components/Documents'

const tabs = [
  { id: 'upload',    label: 'Upload Documents', icon: '📄' },
  { id: 'query',     label: 'RAG Query',         icon: '🔍' },
  { id: 'spec',      label: 'Spec Compliance',   icon: '✅' },
  { id: 'schedule',  label: 'Schedule Risk',     icon: '📅' },
  { id: 'rfi',       label: 'RFI Copilot',       icon: '💬' },
  { id: 'documents', label: 'Documents',          icon: '📁' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('upload')
  const [health, setHealth] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then(r => r.json())
      .then(setHealth)
      .catch(() => setHealth({ status: 'error' }))
  }, [])

  return (
    <div className="flex h-screen bg-gray-100">
      <div className="w-64 bg-gray-900 text-white flex flex-col">
        <div className="p-6 border-b border-gray-700">
          <h1 className="text-lg font-bold text-blue-400">EPC Intelligence</h1>
          <p className="text-xs text-gray-400 mt-1">Data Centre Platform</p>
          {health && (
            <span className={`inline-block mt-2 px-2 py-1 rounded text-xs font-medium ${
              health.status === 'ok' ? 'bg-green-800 text-green-200' : 'bg-red-800 text-red-200'
            }`}>
              {health.status === 'ok' ? '● Online' : '● Degraded'}
            </span>
          )}
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? 'bg-blue-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              }`}
            >
              <span>{tab.icon}</span>
              {tab.label}
            </button>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-700">
          <p className="text-xs text-gray-500">ET AI Hackathon 2026</p>
          <p className="text-xs text-gray-600">Powered by Mistral 7B</p>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-8">
        {activeTab === 'upload'    && <Upload />}
        {activeTab === 'query'     && <Query />}
        {activeTab === 'spec'      && <SpecCompliance />}
        {activeTab === 'schedule'  && <ScheduleRisk />}
        {activeTab === 'rfi'       && <RFICopilot />}
        {activeTab === 'documents' && <Documents />}
      </div>
    </div>
  )
}