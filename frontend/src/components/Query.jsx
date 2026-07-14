import { useState } from 'react'

export default function Query() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [streaming, setStreaming] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleQuery = async () => {
    if (!question.trim() || loading || streaming) return
    setLoading(true); setError(null); setResult(null)
    try {
      const res = await fetch('/api/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, top_k: topK }),
      })
      if (!res.ok) throw new Error('Query failed')
      setLoading(false); setStreaming(true)
      setResult({ answer: '', sources: [] })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let fullText = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        fullText += chunk
        if (fullText.includes('__SOURCES__')) {
          const [answerPart, sourcesPart] = fullText.split('__SOURCES__')
          try { setResult({ answer: answerPart.trim(), sources: JSON.parse(sourcesPart.trim()) }) }
          catch { setResult({ answer: answerPart.trim(), sources: [] }) }
          break
        } else { setResult({ answer: fullText, sources: [] }) }
      }
    } catch (e) { setError(e.message); setLoading(false) }
    finally { setStreaming(false); setLoading(false) }
  }

  return (
    <div>
      <h2 className="text-2xl font-bold text-gray-800 mb-1">RAG Query</h2>
      <p className="text-gray-500 mb-6">Ask any question about your EPC project documents.</p>
      <div className="grid grid-cols-10 gap-4">
        <div className="col-span-3">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Question</label>
              <textarea value={question} onChange={e => setQuestion(e.target.value)}
                placeholder="e.g. What are the UPS redundancy requirements?" rows={4}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Top K: {topK}</label>
              <input type="range" min={1} max={10} value={topK} onChange={e => setTopK(Number(e.target.value))} className="w-full" />
            </div>
            <button onClick={handleQuery} disabled={!question.trim() || loading || streaming}
              className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {loading ? 'Searching docs...' : streaming ? 'Generating...' : 'Ask Question'}
            </button>
          </div>
        </div>

        {error && (
          <div className="col-span-7 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">❌ {error}</div>
        )}
        {result && (
          <>
            <div className="col-span-4">
              <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
                <h3 className="font-semibold text-gray-800 mb-3 flex items-center gap-2">
                  Answer
                  {streaming && <span className="text-blue-400 text-xs font-normal animate-pulse">● generating...</span>}
                </h3>
                <p className="text-gray-700 text-sm leading-relaxed whitespace-pre-wrap">
                  {result.answer}
                  {streaming && <span className="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1 rounded" />}
                </p>
              </div>
            </div>
            <div className="col-span-3">
              {result.sources?.length > 0 && (
                <div className="bg-gray-50 rounded-xl border border-gray-200 p-4">
                  <h3 className="font-semibold text-gray-700 mb-3 text-sm">Sources</h3>
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