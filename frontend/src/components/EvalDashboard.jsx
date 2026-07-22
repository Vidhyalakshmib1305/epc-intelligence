import { useState, useEffect, useCallback, useRef } from 'react'

/* ── Aurora ── */
function Aurora() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div style={{ position:'absolute', width:700, height:700, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(99,102,241,0.18) 0%,transparent 70%)',
        top:'-15%', left:'-10%', animation:'aurora1 14s ease-in-out infinite' }}/>
      <div style={{ position:'absolute', width:550, height:550, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(168,85,247,0.14) 0%,transparent 70%)',
        bottom:'5%', right:'-8%', animation:'aurora2 18s ease-in-out infinite' }}/>
      <div style={{ position:'absolute', width:400, height:400, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(59,130,246,0.10) 0%,transparent 70%)',
        top:'40%', left:'42%', animation:'aurora3 11s ease-in-out infinite' }}/>
    </div>
  )
}

/* ── Gauge ring ── */
function Gauge({ value, label, color, size = 80 }) {
  const pct   = Math.round((value ?? 0) * 100)
  const r     = (size - 14) / 2
  const circ  = 2 * Math.PI * r
  const dash  = circ * (pct / 100)
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size}>
        <circle cx={size/2} cy={size/2} r={r} fill="none"
          stroke="rgba(255,255,255,0.07)" strokeWidth={7}/>
        <circle cx={size/2} cy={size/2} r={r} fill="none"
          stroke={color} strokeWidth={7}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform={`rotate(-90 ${size/2} ${size/2})`}
          style={{ transition:'stroke-dasharray 0.8s ease' }}/>
        <text x={size/2} y={size/2+5} textAnchor="middle"
          fill="white" fontSize={13} fontWeight="bold">{pct}%</text>
      </svg>
      <span className="text-xs text-slate-400 font-bold tracking-widest uppercase">{label}</span>
    </div>
  )
}

/* ── Status pill ── */
function StatusPill({ ok }) {
  return ok
    ? <span className="px-2 py-0.5 rounded text-xs font-bold text-green-300" style={{ background:'rgba(34,197,94,0.15)' }}>✓ Hit</span>
    : <span className="px-2 py-0.5 rounded text-xs font-bold text-red-400"   style={{ background:'rgba(239,68,68,0.15)'  }}>✗ Miss</span>
}

const TABS = ['Questions', 'Run Results', 'History']

export default function EvalDashboard() {
  const [tab, setTab]             = useState('Questions')
  const [questions, setQuestions] = useState([])
  const [latestRun, setLatestRun] = useState(null)
  const [runResults, setRunResults] = useState([])
  const [runs, setRuns]           = useState([])
  const [running, setRunning]         = useState(false)
  const [runningInBg, setRunningInBg] = useState(false)
  const [generating, setGenerating]   = useState({})
  const [docs, setDocs]               = useState([])
  const [expandedQ, setExpandedQ]     = useState(null)
  const [error, setError]             = useState('')
  const pollRef = useRef(null)

  const fetchQuestions = useCallback(async () => {
    const r = await fetch('/api/eval/questions')
    setQuestions(await r.json())
  }, [])

  const fetchLatestRun = useCallback(async () => {
    const r = await fetch('/api/eval/runs/latest')
    const data = await r.json()
    if (data?.id) {
      setLatestRun(data)
      const rr = await fetch(`/api/eval/runs/${data.id}/results`)
      setRunResults(await rr.json())
    }
  }, [])

  const fetchRuns = useCallback(async () => {
    const r = await fetch('/api/eval/runs')
    setRuns(await r.json())
  }, [])

  const fetchDocs = useCallback(async () => {
    const r = await fetch('/api/documents')
    setDocs(await r.json())
  }, [])

  useEffect(() => {
    fetchQuestions(); fetchLatestRun(); fetchRuns(); fetchDocs()
  }, [])

  const patch = async (id, body) => {
    await fetch(`/api/eval/questions/${id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
    fetchQuestions()
  }

  const deleteQ = async (id) => {
    await fetch(`/api/eval/questions/${id}`, { method: 'DELETE' })
    fetchQuestions()
  }

  const generateForDoc = async (docId) => {
    setGenerating(g => ({ ...g, [docId]: true }))
    try {
      await fetch(`/api/eval/questions/${docId}/generate`, { method: 'POST' })
      await fetchQuestions()
    } finally {
      setGenerating(g => ({ ...g, [docId]: false }))
    }
  }

  // Stop polling helper
  const stopPoll = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
    setRunningInBg(false)
  }, [])

  // Poll /eval/status until done, then refresh results
  const startPolling = useCallback((knownRunId) => {
    setRunningInBg(true)
    pollRef.current = setInterval(async () => {
      try {
        const s = await fetch('/api/eval/status')
        const status = await s.json()
        if (!status.running) {
          stopPoll()
          if (status.error) {
            setError('Eval failed: ' + status.error)
          } else {
            await fetchLatestRun(); await fetchRuns()
            setTab('Run Results')
          }
        }
      } catch { /* network blip — keep polling */ }
    }, 8000)
  }, [fetchLatestRun, fetchRuns, stopPoll])

  // Cleanup on unmount
  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  const runEval = async () => {
    setRunning(true); setError('')
    try {
      const r = await fetch('/api/eval/run', { method: 'POST' })
      const d = await r.json()
      if (!r.ok) { setError(d.detail || 'Eval run failed'); return }
      // Returns immediately — start background polling
      startPolling(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  const pending   = questions.filter(q => !q.validated && !q.rejected)
  const validated = questions.filter(q => q.validated)
  const rejected  = questions.filter(q => q.rejected)

  return (
    <div className="slide-in relative min-h-screen -mx-8 -mt-8 px-8 pt-8 pb-14"
      style={{ background:'linear-gradient(135deg,#0a0a1a 0%,#111128 40%,#0f0f2e 70%,#0a0a1a 100%)' }}>
      <Aurora />
      <div className="relative z-10 max-w-6xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-3"
            style={{ background:'rgba(99,102,241,0.12)', border:'1px solid rgba(99,102,241,0.25)' }}>
            <span className="text-base">📊</span>
            <span className="text-indigo-300 text-xs font-bold tracking-widest uppercase">RAG Performance Dashboard</span>
          </div>
          <h1 className="text-3xl font-black text-white">System Quality Metrics</h1>
          <p className="text-slate-400 text-sm mt-1">
            Automated RAG evaluation · 20 domain Q&A pairs · hit rate, MRR and faithfulness scoring
          </p>
        </div>

        {/* Latest run summary */}
        {latestRun && (
          <div className="rounded-2xl p-6 mb-6"
            style={{ background:'rgba(99,102,241,0.07)', border:'1px solid rgba(99,102,241,0.2)',
              backdropFilter:'blur(16px)' }}>
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mb-1">Latest Eval Run</p>
                <p className="text-slate-300 text-xs font-mono">{latestRun.run_at?.slice(0,19).replace('T',' ')} · {latestRun.total_questions} questions</p>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span className="text-xs px-3 py-1.5 rounded-lg font-mono"
                  style={{ background:'rgba(34,197,94,0.1)', border:'1px solid rgba(34,197,94,0.25)', color:'#86efac' }}>
                  ✓ Pre-evaluated · last run {latestRun?.run_at?.slice(0,10)}
                </span>
                <span className="text-xs text-slate-600 font-mono">full re-run takes ~15 min</span>
              </div>
            </div>
            <div className="flex items-center justify-around gap-4 flex-wrap">
              <Gauge value={latestRun.hit_at_1}         label="Hit@1"         color="#6366f1" />
              <Gauge value={latestRun.hit_at_3}         label="Hit@3"         color="#8b5cf6" />
              <Gauge value={latestRun.hit_at_5}         label="Hit@5"         color="#a78bfa" />
              <Gauge value={latestRun.mrr}              label="MRR"           color="#3b82f6" />
              <Gauge value={latestRun.avg_faithfulness} label="Faithfulness"  color="#10b981" />
            </div>
          </div>
        )}

        {/* Run eval prompt if no run yet */}
        {!latestRun && (
          <div className="rounded-2xl p-6 mb-6 flex items-center justify-between"
            style={{ background:'rgba(255,255,255,0.03)', border:'1px dashed rgba(255,255,255,0.1)' }}>
            <div>
              <p className="text-white font-bold">No eval runs yet</p>
              <p className="text-slate-400 text-sm mt-1">Validate some questions below, then run the eval.</p>
            </div>
            <span className="text-xs px-3 py-1.5 rounded-lg font-mono"
              style={{ background:'rgba(34,197,94,0.1)', border:'1px solid rgba(34,197,94,0.25)', color:'#86efac' }}>
              ✓ Pre-evaluated
            </span>
          </div>
        )}

        {runningInBg && (
          <div className="rounded-xl p-4 mb-4 flex items-center gap-3"
            style={{ background:'rgba(99,102,241,0.12)', border:'1px solid rgba(99,102,241,0.35)' }}>
            <span className="text-lg animate-spin inline-block">⚙</span>
            <div>
              <p className="text-indigo-200 text-sm font-bold">Eval running in background…</p>
              <p className="text-slate-400 text-xs mt-0.5">This takes ~10–15 min. You can navigate away — this page will update automatically when done.</p>
            </div>
          </div>
        )}

        {error && (
          <div className="rounded-xl p-4 mb-4 flex gap-3"
            style={{ background:'rgba(239,68,68,0.12)', border:'1px solid rgba(239,68,68,0.3)' }}>
            <span className="text-xl">🚨</span>
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-6 p-1 rounded-xl" style={{ background:'rgba(255,255,255,0.04)', width:'fit-content' }}>
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="px-4 py-2 rounded-lg text-sm font-bold transition-all"
              style={{
                background: tab === t ? 'rgba(99,102,241,0.35)' : 'transparent',
                color: tab === t ? 'white' : 'rgba(255,255,255,0.4)',
                border: tab === t ? '1px solid rgba(99,102,241,0.5)' : '1px solid transparent',
              }}>
              {t}
              {t === 'Questions' && (
                <span className="ml-2 px-1.5 py-0.5 rounded text-xs"
                  style={{ background:'rgba(99,102,241,0.3)' }}>
                  {questions.length}
                </span>
              )}
            </button>
          ))}
        </div>

        {/* ── QUESTIONS TAB ── */}
        {tab === 'Questions' && (
          <div className="space-y-6">

            {/* Generate for docs */}
            <div className="rounded-2xl p-5"
              style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)' }}>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">
                Generate Q&A from Documents
              </h3>
              <div className="grid grid-cols-2 gap-3">
                {docs.map(doc => (
                  <div key={doc.id} className="flex items-center justify-between rounded-xl px-4 py-3"
                    style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.07)' }}>
                    <div>
                      <p className="text-white text-sm font-semibold">{doc.filename.replace(/\.pdf$/i,'')}</p>
                      <p className="text-slate-500 text-xs">{doc.doc_type?.replace(/_/g,' ')} · {doc.page_count} pages</p>
                    </div>
                    <button onClick={() => generateForDoc(doc.id)}
                      disabled={generating[doc.id]}
                      className="px-3 py-1.5 rounded-lg text-xs font-bold text-white disabled:opacity-40 transition-all"
                      style={{ background: generating[doc.id] ? 'rgba(99,102,241,0.3)' : 'rgba(99,102,241,0.5)',
                        border:'1px solid rgba(99,102,241,0.4)' }}>
                      {generating[doc.id] ? '⠙ Generating…' : '+ Generate'}
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Stats bar */}
            <div className="flex gap-4">
              {[
                { label:'Pending review', count: pending.length,   color:'rgba(99,102,241,0.25)'  },
                { label:'Validated',      count: validated.length, color:'rgba(34,197,94,0.2)'    },
                { label:'Rejected',       count: rejected.length,  color:'rgba(239,68,68,0.2)'    },
              ].map(s => (
                <div key={s.label} className="flex-1 rounded-xl px-4 py-3 text-center"
                  style={{ background: s.color, border:'1px solid rgba(255,255,255,0.07)' }}>
                  <p className="text-white text-xl font-black">{s.count}</p>
                  <p className="text-slate-400 text-xs">{s.label}</p>
                </div>
              ))}
            </div>

            {/* Question list */}
            {['Pending review', 'Validated', 'Rejected'].map(section => {
              const qs = section === 'Pending review' ? pending
                       : section === 'Validated'      ? validated : rejected
              if (!qs.length) return null
              const sectionColor = section === 'Validated' ? '#22c55e' : section === 'Rejected' ? '#ef4444' : '#6366f1'
              return (
                <div key={section}>
                  <h3 className="text-xs font-bold uppercase tracking-widest mb-3"
                    style={{ color: sectionColor }}>
                    {section} ({qs.length})
                  </h3>
                  <div className="space-y-3">
                    {qs.map(q => (
                      <div key={q.id} className="rounded-xl overflow-hidden"
                        style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)' }}>
                        {/* Question header */}
                        <div className="flex items-start gap-3 p-4 cursor-pointer"
                          onClick={() => setExpandedQ(expandedQ === q.id ? null : q.id)}>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="text-xs px-2 py-0.5 rounded font-bold text-indigo-300"
                                style={{ background:'rgba(99,102,241,0.15)' }}>
                                {q.filename.replace(/\.pdf$/i,'')}
                              </span>
                              <span className="text-xs text-slate-500">{q.doc_type?.replace(/_/g,' ')}</span>
                            </div>
                            <p className="text-white text-sm font-semibold leading-snug">{q.question}</p>
                          </div>
                          <span className="text-slate-500 text-xs mt-1">{expandedQ === q.id ? '▲' : '▼'}</span>
                        </div>

                        {/* Expanded answer */}
                        {expandedQ === q.id && (
                          <div className="px-4 pb-4">
                            <div className="rounded-xl p-3 mb-3"
                              style={{ background:'rgba(0,0,0,0.3)', border:'1px solid rgba(255,255,255,0.06)' }}>
                              <p className="text-xs text-slate-500 font-bold uppercase tracking-widest mb-1">Generated Answer</p>
                              <p className="text-slate-300 text-sm leading-relaxed">{q.expected_answer}</p>
                            </div>
                          </div>
                        )}

                        {/* Actions */}
                        <div className="flex items-center gap-2 px-4 py-3"
                          style={{ borderTop:'1px solid rgba(255,255,255,0.06)' }}>
                          {!q.validated && (
                            <button onClick={() => patch(q.id, { validated: true })}
                              className="px-3 py-1 rounded-lg text-xs font-bold text-green-300 transition-all hover:bg-green-500/20"
                              style={{ background:'rgba(34,197,94,0.1)', border:'1px solid rgba(34,197,94,0.25)' }}>
                              ✓ Approve
                            </button>
                          )}
                          {!q.rejected && (
                            <button onClick={() => patch(q.id, { rejected: true })}
                              className="px-3 py-1 rounded-lg text-xs font-bold text-red-400 transition-all hover:bg-red-500/20"
                              style={{ background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.25)' }}>
                              ✗ Reject
                            </button>
                          )}
                          {q.validated && (
                            <button onClick={() => patch(q.id, { validated: false })}
                              className="px-3 py-1 rounded-lg text-xs font-bold text-slate-400 hover:text-white transition-all"
                              style={{ background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.1)' }}>
                              ↩ Unvalidate
                            </button>
                          )}
                          <button onClick={() => deleteQ(q.id)}
                            className="ml-auto px-3 py-1 rounded-lg text-xs font-bold text-slate-600 hover:text-red-400 transition-all">
                            🗑
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )
            })}

            {questions.length === 0 && (
              <div className="text-center py-16">
                <p className="text-4xl mb-3">🧪</p>
                <p className="text-slate-300 font-bold">No questions generated yet</p>
                <p className="text-slate-500 text-sm mt-1">Click "+ Generate" next to a document above to create Q&A pairs.</p>
              </div>
            )}
          </div>
        )}

        {/* ── RUN RESULTS TAB ── */}
        {tab === 'Run Results' && (
          <div className="space-y-4">
            {latestRun && (
              <div className="flex items-center gap-3 mb-4">
                <p className="text-slate-400 text-xs font-mono">
                  Run {latestRun.id.slice(0,8)} · {latestRun.run_at?.slice(0,19).replace('T',' ')} · {latestRun.total_questions} questions
                </p>
              </div>
            )}
            {runResults.length === 0 && (
              <div className="text-center py-16">
                <p className="text-4xl mb-3">▶</p>
                <p className="text-slate-300 font-bold">No results yet</p>
                <p className="text-slate-500 text-sm mt-1">Validate questions and run the eval to see per-question results.</p>
              </div>
            )}
            {runResults.map((r, i) => (
              <div key={r.id} className="rounded-2xl p-5"
                style={{ background:'rgba(255,255,255,0.04)', border:`1px solid ${r.hit_at_3 ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
                <div className="flex items-start gap-3 mb-3">
                  <span className="flex-none w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black text-white"
                    style={{ background: r.hit_at_3 ? 'linear-gradient(135deg,#22c55e,#16a34a)' : 'linear-gradient(135deg,#ef4444,#dc2626)' }}>
                    {i + 1}
                  </span>
                  <p className="text-white text-sm font-semibold flex-1">{r.question}</p>
                </div>
                <div className="grid grid-cols-3 gap-3 mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Hit@1</span><StatusPill ok={r.hit_at_1}/>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Hit@3</span><StatusPill ok={r.hit_at_3}/>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-slate-500">Faithfulness</span>
                    <span className="text-xs font-bold" style={{ color: r.faithfulness >= 0.7 ? '#22c55e' : r.faithfulness >= 0.4 ? '#f59e0b' : '#ef4444' }}>
                      {Math.round((r.faithfulness ?? 0) * 100)}%
                    </span>
                  </div>
                </div>
                <div className="rounded-xl p-3 mb-2" style={{ background:'rgba(0,0,0,0.3)' }}>
                  <p className="text-xs text-slate-500 mb-1">Expected source: <span className="text-indigo-300 font-mono">{r.expected_source}</span></p>
                  <p className="text-xs text-slate-500">Retrieved: <span className="text-slate-300 font-mono">{(r.retrieved_sources || []).join(', ') || '—'}</span></p>
                </div>
                {r.generated_answer && (
                  <p className="text-slate-400 text-xs leading-relaxed italic border-l-2 border-indigo-800 pl-2">
                    "{r.generated_answer.slice(0,200)}{r.generated_answer.length > 200 ? '…' : ''}"
                  </p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ── HISTORY TAB ── */}
        {tab === 'History' && (
          <div className="space-y-3">
            {runs.length === 0 && (
              <div className="text-center py-16">
                <p className="text-4xl mb-3">📈</p>
                <p className="text-slate-300 font-bold">No runs yet</p>
              </div>
            )}
            {runs.map((run, i) => (
              <div key={run.id} className="rounded-xl p-4 flex items-center gap-4"
                style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)' }}>
                <span className="text-slate-500 text-xs font-mono w-5 text-right">{i + 1}</span>
                <div className="flex-1">
                  <p className="text-white text-sm font-semibold">
                    Hit@3: <span className="text-green-400">{Math.round((run.hit_at_3 ?? 0)*100)}%</span>
                    <span className="mx-2 text-slate-600">·</span>
                    MRR: <span className="text-blue-400">{Math.round((run.mrr ?? 0)*100)}%</span>
                    <span className="mx-2 text-slate-600">·</span>
                    Faithfulness: <span className="text-emerald-400">{Math.round((run.avg_faithfulness ?? 0)*100)}%</span>
                  </p>
                  <p className="text-slate-500 text-xs mt-0.5">{run.run_at?.slice(0,19).replace('T',' ')} · {run.total_questions} questions</p>
                </div>
                <span className="text-xs text-slate-600 font-mono">{run.id.slice(0,8)}</span>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  )
}
