import { useState, useEffect, useRef } from 'react'
import { streamAgent } from '../utils/streamAgent'

/* ── Aurora background blobs ── */
function Aurora() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div style={{
        position:'absolute', width:700, height:700, borderRadius:'50%',
        background:'radial-gradient(circle, rgba(59,130,246,0.22) 0%, transparent 70%)',
        top:'-15%', left:'-10%', animation:'aurora1 14s ease-in-out infinite',
      }}/>
      <div style={{
        position:'absolute', width:550, height:550, borderRadius:'50%',
        background:'radial-gradient(circle, rgba(139,92,246,0.18) 0%, transparent 70%)',
        bottom:'5%', right:'-8%', animation:'aurora2 18s ease-in-out infinite',
      }}/>
      <div style={{
        position:'absolute', width:420, height:420, borderRadius:'50%',
        background:'radial-gradient(circle, rgba(20,184,166,0.14) 0%, transparent 70%)',
        top:'40%', left:'42%', animation:'aurora3 11s ease-in-out infinite',
      }}/>
    </div>
  )
}

/* ── 3D orbital idle state ── */
function Idle3D() {
  const cards = [
    { text:'6 Documents Ready',  emoji:'📄', x:8,  y:10, delay:0,   rx:-12, ry:18  },
    { text:'5 AI Agents Active', emoji:'🤖', x:60, y:6,  delay:1.8, rx:8,   ry:-22 },
    { text:'Mistral 7B · Local', emoji:'⚡', x:68, y:58, delay:3.2, rx:12,  ry:18  },
    { text:'Qdrant · 384-dim',   emoji:'🔗', x:2,  y:62, delay:2.1, rx:-8,  ry:-18 },
  ]
  return (
    <div className="rounded-2xl relative overflow-hidden"
      style={{ height:300, background:'rgba(255,255,255,0.025)', border:'1px dashed rgba(255,255,255,0.08)' }}>
      {cards.map((c,i) => (
        <div key={i} style={{ position:'absolute', left:`${c.x}%`, top:`${c.y}%`,
          animation:`floatBob ${4.5+c.delay*0.4}s ${c.delay}s ease-in-out infinite`, perspective:400 }}>
          <div style={{ background:'rgba(255,255,255,0.055)', backdropFilter:'blur(10px)',
            WebkitBackdropFilter:'blur(10px)', border:'1px solid rgba(255,255,255,0.13)',
            borderRadius:10, padding:'5px 13px', fontSize:10, fontWeight:700,
            color:'rgba(255,255,255,0.6)', letterSpacing:'0.08em', whiteSpace:'nowrap',
            transform:`rotateX(${c.rx}deg) rotateY(${c.ry}deg)`,
            boxShadow:'0 8px 24px rgba(0,0,0,0.35),inset 0 1px 0 rgba(255,255,255,0.1)' }}>
            {c.emoji} {c.text}
          </div>
        </div>
      ))}
      <div style={{ position:'absolute', top:'50%', left:'50%',
        transform:'translate(-50%,-50%)', textAlign:'center' }}>
        <div style={{ position:'relative', width:90, height:90, margin:'0 auto 14px' }}>
          <div style={{ position:'absolute', inset:0, borderRadius:'50%', border:'2px solid #6366f1',
            transform:'perspective(200px) rotateX(72deg)', animation:'spin-slow 4s linear infinite',
            boxShadow:'0 0 16px #6366f155,inset 0 0 8px #6366f122' }}/>
          <div style={{ position:'absolute', inset:10, borderRadius:'50%', border:'1px solid #6366f155',
            transform:'perspective(200px) rotateX(72deg)', animation:'spin-slow 2.5s linear infinite reverse' }}/>
          <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
            justifyContent:'center', fontSize:28, animation:'floatBob 3s ease-in-out infinite' }}>
            ⚡
          </div>
        </div>
        <p style={{ color:'#6366f1', fontSize:10, fontWeight:800, letterSpacing:'0.22em', opacity:0.85, marginBottom:4 }}>
          AWAITING QUERY
        </p>
        <p style={{ color:'rgba(255,255,255,0.25)', fontSize:10 }}>
          Ask any question about your EPC documents
        </p>
      </div>
    </div>
  )
}

/* ── Spinning braille loader ── */
const DOTS = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']

export default function Query() {
  const [question, setQuestion] = useState('')
  const [topK, setTopK]         = useState(3)
  const [loading, setLoading]   = useState(false)
  const [answer, setAnswer]     = useState('')
  const [sources, setSources]   = useState([])
  const [error, setError]       = useState('')
  const [focused, setFocused]   = useState(false)
  const [dotIdx, setDotIdx]     = useState(0)
  const answerRef = useRef(null)
  const ctrlRef   = useRef(null)

  /* spinner tick */
  useEffect(() => {
    if (!loading) return
    const iv = setInterval(() => setDotIdx(i => (i + 1) % DOTS.length), 90)
    return () => clearInterval(iv)
  }, [loading])

  /* auto-scroll answer box */
  useEffect(() => {
    if (answerRef.current) answerRef.current.scrollTop = answerRef.current.scrollHeight
  }, [answer])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!question.trim() || loading) return
    if (ctrlRef.current) ctrlRef.current.abort()
    ctrlRef.current = new AbortController()
    setLoading(true); setAnswer(''); setSources([]); setError('')
    try {
      await streamAgent(
        '/api/query/stream',
        { question, top_k: topK },
        (tok) => setAnswer(tok),
        (analysis, _meta, srcs) => {
          setAnswer(analysis)
          setSources(srcs || [])
          setLoading(false)
        }
      )
    } catch (err) {
      if (err.name !== 'AbortError') { setError(err.message || 'Query failed'); setLoading(false) }
    }
  }

  return (
    <div
      className="slide-in relative min-h-screen -mx-8 -mt-8 px-8 pt-8 pb-14"
      style={{ background:'linear-gradient(135deg,#0f0c29 0%,#1a1a2e 40%,#16213e 70%,#0f3460 100%)' }}
    >
      <Aurora />

      <div className="relative z-10 max-w-4xl mx-auto space-y-6">

        {/* ── Header ── */}
        <div className="text-center pt-2 pb-4">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-4"
            style={{ background:'rgba(59,130,246,0.13)', border:'1px solid rgba(59,130,246,0.28)' }}>
            <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse"/>
            <span className="text-blue-300 text-xs font-bold tracking-widest uppercase">RAG Query Engine · Mistral 7B · Qdrant</span>
          </div>
          <h1 className="text-4xl font-black text-white mb-2 tracking-tight">Ask Your Documents</h1>
          <p className="text-slate-400 text-sm">Vector search over 6 EPC project documents · fully local · no API keys</p>
        </div>

        {/* ── Form ── */}
        <div
          className="rounded-2xl p-6 transition-all duration-300"
          style={{
            background:'rgba(255,255,255,0.05)',
            backdropFilter:'blur(22px)',
            WebkitBackdropFilter:'blur(22px)',
            border:`1px solid ${focused ? 'rgba(99,102,241,0.6)' : 'rgba(255,255,255,0.09)'}`,
            boxShadow: focused ? '0 0 40px rgba(99,102,241,0.12), inset 0 1px 0 rgba(255,255,255,0.05)' : 'inset 0 1px 0 rgba(255,255,255,0.04)',
          }}
        >
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Query</label>
              <textarea
                rows={3}
                value={question}
                onChange={e => setQuestion(e.target.value)}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                placeholder="e.g. What are the UPS redundancy requirements?"
                className="w-full rounded-xl px-4 py-3 text-white placeholder-slate-500 resize-none focus:outline-none text-sm leading-relaxed"
                style={{ background:'rgba(0,0,0,0.38)', border:'1px solid rgba(255,255,255,0.08)', fontFamily:'monospace' }}
              />
            </div>
            <div className="flex items-center gap-6">
              <div className="flex-1">
                <label className="text-xs text-slate-400 font-bold uppercase tracking-widest">
                  Top K Sources: <span className="text-blue-400 font-black">{topK}</span>
                </label>
                <input type="range" min={1} max={8} value={topK}
                  onChange={e => setTopK(+e.target.value)}
                  className="w-full mt-1.5 accent-indigo-500"/>
              </div>
              <button
                type="submit"
                disabled={loading || !question.trim()}
                className="px-8 py-3 rounded-xl font-black text-white text-sm uppercase tracking-wider transition-all duration-200 disabled:opacity-40"
                style={{
                  background: loading
                    ? 'rgba(99,102,241,0.45)'
                    : 'linear-gradient(135deg,#6366f1,#3b82f6)',
                  boxShadow: loading ? 'none' : '0 4px 22px rgba(99,102,241,0.42)',
                  transform: loading ? 'scale(0.97)' : 'scale(1)',
                }}
              >
                {loading ? `${DOTS[dotIdx]} Processing…` : '⚡ Ask'}
              </button>
            </div>
          </form>
        </div>

        {/* ── Idle 3D orbital ── */}
        {!loading && !answer && !error && <Idle3D />}

        {/* ── Terminal answer panel ── */}
        {(loading || answer) && (
          <div
            className="flip-in-3d rounded-2xl overflow-hidden"
            style={{
              background:'rgba(4,8,20,0.85)',
              backdropFilter:'blur(20px)',
              WebkitBackdropFilter:'blur(20px)',
              border:'1px solid rgba(99,102,241,0.28)',
              boxShadow:'0 0 50px rgba(99,102,241,0.08)',
            }}
          >
            {/* Titlebar */}
            <div
              className="flex items-center gap-2 px-5 py-3"
              style={{ background:'rgba(255,255,255,0.04)', borderBottom:'1px solid rgba(255,255,255,0.07)' }}
            >
              <div className="w-3 h-3 rounded-full bg-red-500/80"/>
              <div className="w-3 h-3 rounded-full bg-yellow-400/80"/>
              <div className="w-3 h-3 rounded-full bg-green-500/80"/>
              <span className="ml-3 text-xs text-slate-400 font-mono">mistral-7b-instruct › rag-response</span>
              {loading && <span className="ml-auto text-xs text-indigo-400 font-mono animate-pulse">● streaming</span>}
              {!loading && answer && <span className="ml-auto text-xs text-green-400 font-mono">✓ complete</span>}
            </div>

            {/* Horizontal scan line while loading */}
            {loading && (
              <div className="relative h-0.5 overflow-hidden" style={{ background:'rgba(99,102,241,0.08)' }}>
                <div
                  className="absolute inset-y-0 w-1/3"
                  style={{
                    background:'linear-gradient(90deg,transparent,rgba(99,102,241,0.9),transparent)',
                    animation:'hScan 1.4s linear infinite',
                  }}
                />
              </div>
            )}

            {/* Content */}
            <div ref={answerRef} className="p-6 max-h-[22rem] overflow-y-auto" style={{ fontFamily:'monospace' }}>
              {loading && !answer && (
                <p className="text-slate-400 text-sm">
                  <span className="text-indigo-400">›</span> Searching {topK} document chunks…
                  <span className="ml-2 text-purple-400">{DOTS[dotIdx]}</span>
                </p>
              )}
              {answer && (
                <div className="text-[0.8rem] leading-relaxed">
                  <span className="text-indigo-400 select-none">› </span>
                  <span className="text-green-300 whitespace-pre-wrap">{answer}</span>
                  {loading && (
                    <span className="text-green-300" style={{ animation:'blink 0.7s step-end infinite' }}>█</span>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── Error ── */}
        {error && (
          <div
            className="pop-bounce rounded-2xl p-5 flex items-start gap-4"
            style={{ background:'rgba(239,68,68,0.13)', border:'1px solid rgba(239,68,68,0.38)' }}
          >
            <span className="text-2xl">🚨</span>
            <div>
              <p className="text-red-300 font-bold">Query Failed</p>
              <p className="text-red-400 text-sm mt-1">{error}</p>
            </div>
          </div>
        )}

        {/* ── Sources ── */}
        {sources.length > 0 && (
          <div className="space-y-3">
            <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
              📎 {sources.length} Source{sources.length !== 1 ? 's' : ''} Retrieved
            </h3>
            {sources.map((src, i) => (
              <div
                key={i}
                className="slide-from-right rounded-xl p-4"
                style={{
                  background:'rgba(255,255,255,0.05)',
                  backdropFilter:'blur(16px)',
                  WebkitBackdropFilter:'blur(16px)',
                  border:'1px solid rgba(255,255,255,0.1)',
                  animationDelay:`${i * 0.1}s`,
                }}
              >
                <div className="flex items-start gap-3">
                  <span
                    className="flex-none w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black text-white"
                    style={{ background:'linear-gradient(135deg,#6366f1,#3b82f6)' }}
                  >{i + 1}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                      <span
                        className="px-2 py-0.5 rounded-md text-xs font-semibold text-indigo-300"
                        style={{ background:'rgba(99,102,241,0.18)' }}
                      >
                        {src.source || src.metadata?.source || 'document'}
                      </span>
                      {src.score !== undefined && (
                        <span className="text-xs text-slate-500">
                          relevance {Math.round(src.score * 100)}%
                        </span>
                      )}
                    </div>
                    <p className="text-slate-300 text-xs leading-relaxed">
                      {src.content || src.text || '—'}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

      </div>
    </div>
  )
}