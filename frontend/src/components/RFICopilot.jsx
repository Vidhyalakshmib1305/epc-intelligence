import { useState } from 'react'

export default function RFICopilot() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleSearch = async () => {
    if (!question.trim()) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/agents/rfi-copilot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: topK }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">RFI Copilot</h2>
      <p className="text-gray-500 mb-6">Search past RFI resolutions before raising a new one.</p>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">RFI Question</label>
          <textarea value={question} onChange={e => setQuestion(e.target.value)}
            placeholder="e.g. Has there been any RFI about cable tray fill factor?" rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Top K: {topK}</label>
          <input type="range" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} className="w-full" />
        </div>
        <button onClick={handleSearch} disabled={!question.trim() || loading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {loading ? 'Searching RFI Log...' : 'Search RFI Log'}
        </button>
      </div>
      {error && <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>}
      {result && (
        <div className="mt-4 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3">RFI Resolution</h3>
            <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
          </div>
          {result.sources?.length > 0 && (
            <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
              <h3 className="font-semibold text-gray-700 mb-3">RFI Log References</h3>
              <div className="space-y-2">
                {result.sources.map((s, i) => (
                  <div key={i} className="bg-white rounded-lg border border-gray-200 p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-medium text-blue-600">{s.filename} — chunk {s.chunk_index}</span>
                      <span className="text-xs text-gray-400">score: {s.score?.toFixed(3)}</span>
                    </div>
                    <p className="text-xs text-gray-500">{s.text_preview}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}