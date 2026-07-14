import { useState } from 'react'

const statusColors = {
  'COMPLIANT': 'bg-green-100 text-green-800 border-green-300',
  'NON-COMPLIANT': 'bg-red-100 text-red-800 border-red-300',
  'REQUIRES VERIFICATION': 'bg-yellow-100 text-yellow-800 border-yellow-300',
}

export default function SpecCompliance() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleCheck = async () => {
    if (!question.trim()) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/agents/spec-compliance', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: topK }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Request failed')
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-1">Spec Compliance</h2>
      <p className="text-gray-500 mb-6">Check if a design or component meets project specification requirements.</p>
      <div className="grid grid-cols-10 gap-4">
        <div className="col-span-3">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Compliance Query</label>
              <textarea value={question} onChange={e => setQuestion(e.target.value)}
                placeholder="e.g. Is the proposed UPS with 94% efficiency compliant with the spec?" rows={4}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Top K: {topK}</label>
              <input type="range" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} className="w-full" />
            </div>
            <button onClick={handleCheck} disabled={!question.trim() || loading}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {loading ? 'Checking...' : 'Check Compliance'}
            </button>
          </div>
        </div>

        {error && (
          <div className="col-span-7 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>
        )}
        {result && (
          <>
            <div className="col-span-4 space-y-4">
              <div className={`rounded-xl border-2 p-4 ${statusColors[result.compliance_status] || 'bg-gray-100 text-gray-800 border-gray-300'}`}>
                <p className="text-xs opacity-70 mb-1">Compliance Status</p>
                <p className="text-2xl font-bold">{result.compliance_status}</p>
              </div>
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-800 mb-3">Analysis</h3>
                <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">{result.analysis}</p>
              </div>
            </div>
            <div className="col-span-3">
              {result.sources?.length > 0 && (
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
                  <h3 className="font-semibold text-gray-700 mb-3 text-sm">Spec References</h3>
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
          </>
        )}
        {!result && !error && (
          <div className="col-span-7 bg-gray-50 rounded-xl border border-dashed border-gray-300 p-12 flex items-center justify-center">
            <p className="text-gray-400 text-sm">Results will appear here</p>
          </div>
        )}
      </div>
    </div>
  )
}