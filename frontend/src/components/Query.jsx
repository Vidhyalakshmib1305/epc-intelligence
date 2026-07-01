import { useState } from 'react'

export default function Query() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleQuery = async () => {
    if (!question.trim()) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: topK }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Query failed')
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div className="max-w-3xl">
      <h2 className="text-2xl font-bold text-gray-800 mb-2">RAG Query</h2>
      <p className="text-gray-500 mb-6">Ask any question about your EPC project documents.</p>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Question</label>
          <textarea value={question} onChange={e => setQuestion(e.target.value)}
            placeholder="e.g. What are the UPS redundancy requirements?" rows={3}
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Top K results: {topK}</label>
          <input type="range" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} className="w-full" />
        </div>
        <button onClick={handleQuery} disabled={!question.trim() || loading}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
          {loading ? 'Thinking...' : 'Ask Question'}
        </button>
      </div>
      {error && <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>}
      {result && (
        <div className="mt-4 space-y-4">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
            <h3 className="font-semibold text-gray-800 mb-3">Answer</h3>
            <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">{result.answer}</p>
          </div>
          {result.sources?.length > 0 && (
            <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
              <h3 className="font-semibold text-gray-700 mb-3">Sources</h3>
              <div className="space-y-2">
                {result.sources.map((s, i) => (
                  <div key={i} className="bg-white rounded-lg border border-gray-200 p-3">
                    <div className="flex justify-between items-center mb-1">
                      <span className="text-xs font-medium text-blue-600">{s.filename} — chunk {s.chunk_index}</span>
                      <span className="text-xs text-gray-400">score: {s.score?.toFixed(3)}</span>
                    </div>
                    <p className="text-xs text-gray-500 line-clamp-2">{s.text_preview}</p>
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