import { useState } from 'react'
import { streamAgent } from '../utils/streamAgent'

const riskColors = {
  HIGH:   'bg-red-100 text-red-800 border-red-300',
  MEDIUM: 'bg-yellow-100 text-yellow-800 border-yellow-300',
  LOW:    'bg-green-100 text-green-800 border-green-300',
}

export default function ScheduleRisk() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleAnalyse = async () => {
    if (!question.trim() || loading || streaming) return
    setLoading(true); setError(null); setResult(null)
    try {
      setLoading(false); setStreaming(true)
      setResult({ analysis: '', sources: [], risk_level: null })
      await streamAgent(
        '/api/agents/schedule-risk/stream',
        { question, top_k: topK },
        (text) => setResult(prev => ({ ...prev, analysis: text })),
        (done) => { setResult(done); setStreaming(false) }
      )
    } catch (e) { setError(e.message); setLoading(false); setStreaming(false) }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-1">Schedule Risk</h2>
      <p className="text-gray-500 mb-6">Analyse project schedule for delays, critical path risks, and mitigation strategies.</p>
      <div className="grid grid-cols-10 gap-4">
        <div className="col-span-3">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Risk Query</label>
              <textarea value={question} onChange={e => setQuestion(e.target.value)}
                placeholder="e.g. What are the current delays and risks to the project timeline?" rows={5}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Top K: {topK}</label>
              <input type="range" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} className="w-full" />
            </div>
            <button onClick={handleAnalyse} disabled={!question.trim() || loading || streaming}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {loading ? 'Searching...' : streaming ? 'Analysing...' : 'Analyse Risk'}
            </button>
          </div>
        </div>

        <div className="col-span-4 space-y-3">
          {error && <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>}
          {result?.risk_level && (
            <div className={`rounded-xl border-2 p-4 ${riskColors[result.risk_level] || 'bg-gray-100 text-gray-800 border-gray-300'}`}>
              <p className="text-xs opacity-70 mb-1">Risk Level</p>
              <p className="text-2xl font-bold">{result.risk_level}</p>
            </div>
          )}
          {result && (
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-5">
              <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
                Analysis
                {streaming && <span className="text-blue-400 text-xs animate-pulse">● generating...</span>}
              </h3>
              <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">
                {result.analysis}
                {streaming && <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1 rounded" />}
              </p>
            </div>
          )}
          {!result && !error && (
            <div className="bg-gray-50 rounded-xl border border-dashed border-gray-300 p-12 flex items-center justify-center">
              <p className="text-gray-400 text-sm">Results will appear here</p>
            </div>
          )}
        </div>

        <div className="col-span-3">
          {result?.sources?.length > 0 && (
            <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
              <h3 className="font-semibold text-gray-700 mb-3 text-sm">Schedule References</h3>
              <div className="space-y-2">
                {result.sources.map((s, i) => (
                  <div key={i} className="bg-white rounded-lg border border-gray-200 p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-medium text-blue-600">{s.filename} — chunk {s.chunk_index}</span>
                      <span className="text-xs text-gray-400">{s.score?.toFixed(3)}</span>
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-3">{s.text_preview}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}