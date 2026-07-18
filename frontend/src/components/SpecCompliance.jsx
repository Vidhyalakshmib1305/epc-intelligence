import { useState, useEffect, useRef } from 'react'
import { streamAgent } from '../utils/streamAgent'

function Aurora() {
  return (
    <div className="fixed inset-0 overflow-hidden pointer-events-none z-0">
      <div style={{ position:'absolute', width:700, height:700, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(59,130,246,0.22) 0%,transparent 70%)',
        top:'-15%', left:'-10%', animation:'aurora1 14s ease-in-out infinite' }}/>
      <div style={{ position:'absolute', width:550, height:550, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(99,102,241,0.18) 0%,transparent 70%)',
        bottom:'5%', right:'-8%', animation:'aurora2 18s ease-in-out infinite' }}/>
      <div style={{ position:'absolute', width:400, height:400, borderRadius:'50%',
        background:'radial-gradient(circle,rgba(34,211,238,0.13) 0%,transparent 70%)',
        top:'40%', left:'40%', animation:'aurora3 11s ease-in-out infinite' }}/>
    </div>
  )
}

function Idle3D({ icon, color, label }) {
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
          <div style={{ position:'absolute', inset:0, borderRadius:'50%', border:`2px solid ${color}`,
            transform:'perspective(200px) rotateX(72deg)', animation:'spin-slow 4s linear infinite',
            boxShadow:`0 0 16px ${color}55,inset 0 0 8px ${color}22` }}/>
          <div style={{ position:'absolute', inset:10, borderRadius:'50%', border:`1px solid ${color}55`,
            transform:'perspective(200px) rotateX(72deg)', animation:'spin-slow 2.5s linear infinite reverse' }}/>
          <div style={{ position:'absolute', inset:0, display:'flex', alignItems:'center',
            justifyContent:'center', fontSize:28, animation:'floatBob 3s ease-in-out infinite' }}>
            {icon}
          </div>
        </div>
        <p style={{ color, fontSize:10, fontWeight:800, letterSpacing:'0.22em', opacity:0.85, marginBottom:4 }}>
          AWAITING QUERY
        </p>
        <p style={{ color:'rgba(255,255,255,0.25)', fontSize:10 }}>{label}</p>
      </div>
    </div>
  )
}

const STATUS_CFG = {
  'COMPLIANT':             { grad:'from-green-500 to-emerald-700',  glow:'glow-yellow',  icon:'✅', critical:false },
  'NON-COMPLIANT':         { grad:'from-red-600 to-red-900',        glow:'glow-red',     icon:'❌', critical:true  },
  'REQUIRES VERIFICATION': { grad:'from-amber-500 to-orange-600',   glow:'glow-orange',  icon:'⚠️', critical:false },
}

const DOTS = ['⠋','⠙','⠹','⠸','⠼','⠴','⠦','⠧','⠇','⠏']

export default function SpecCompliance() {
  const [query, setQuery]       = useState('')
  const [topK, setTopK]         = useState(3)
  const [loading, setLoading]   = useState(false)
  const [stream, setStream]     = useState('')
  const [result, setResult]     = useState(null)
  const [error, setError]       = useState('')
  const [focused, setFocused]   = useState(false)
  const [revealed, setRevealed] = useState(false)
  const [dotIdx, setDotIdx]     = useState(0)
  const ctrlRef = useRef(null)

  useEffect(() => {
    if (!loading) return
    const iv = setInterval(() => setDotIdx(i => (i + 1) % DOTS.length), 90)
    return () => clearInterval(iv)
  }, [loading])

  const run = async (e) => {
    e.preventDefault()
    if (!query.trim() || loading) return
    if (ctrlRef.current) ctrlRef.current.abort()
    ctrlRef.current = new AbortController()
    setLoading(true); setStream(''); setResult(null); setError(''); setRevealed(false)
    try {
      await streamAgent(
        '/api/agents/spec-compliance/stream',
        { query, top_k: topK },
        tok => setStream(tok),
        (analysis, meta, sources) => {
          setResult({ analysis, status: meta?.compliance_status, sources: sources || [] })
          setLoading(false)
          setTimeout(() => setRevealed(true), 60)
        }
      )
    } catch (err) {
      if (err.name !== 'AbortError') { setError(err.message || 'Analysis failed'); setLoading(false) }
    }
  }

  const cfg = result ? (STATUS_CFG[result.status] || STATUS_CFG['REQUIRES VERIFICATION']) : null

  return (
    <div className="slide-in relative min-h-screen -mx-8 -mt-8 px-8 pt-8 pb-14"
      style={{ background:'linear-gradient(135deg,#060d1f 0%,#0a1628 40%,#0d1f3c 70%,#071224 100%)' }}>
      <Aurora />
      <div className="relative z-10 max-w-6xl mx-auto">

        {/* Header */}
        <div className="mb-8">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full mb-3"
            style={{ background:'rgba(59,130,246,0.12)', border:'1px solid rgba(59,130,246,0.25)' }}>
            <span className="text-base">✅</span>
            <span className="text-blue-300 text-xs font-bold tracking-widest uppercase">Spec Compliance Agent</span>
          </div>
          <h1 className="text-3xl font-black text-white">Specification Compliance Check</h1>
          <p className="text-slate-400 text-sm mt-1">Verify design components against project specification documents</p>
        </div>

        <div className="grid grid-cols-5 gap-6">

          {/* ── Form (sticky left panel) ── */}
          <div className="col-span-2">
            <div className="rounded-2xl p-6 sticky top-6 transition-all duration-300"
              style={{
                background:'rgba(255,255,255,0.05)',
                backdropFilter:'blur(22px)', WebkitBackdropFilter:'blur(22px)',
                border:`1px solid ${focused ? 'rgba(59,130,246,0.5)' : 'rgba(255,255,255,0.08)'}`,
                boxShadow: focused ? '0 0 40px rgba(59,130,246,0.12)' : 'none',
              }}>
              <form onSubmit={run} className="space-y-5">
                <div>
                  <label className="block text-xs font-bold text-slate-400 uppercase tracking-widest mb-2">Compliance Query</label>
                  <textarea rows={6} value={query} onChange={e => setQuery(e.target.value)}
                    onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
                    placeholder="e.g. Is a UPS with 94% efficiency compliant with the data centre spec?"
                    className="w-full rounded-xl px-4 py-3 text-white placeholder-slate-500 resize-none focus:outline-none text-sm leading-relaxed"
                    style={{ background:'rgba(0,0,0,0.4)', border:'1px solid rgba(255,255,255,0.08)' }}/>
                </div>
                <div>
                  <label className="text-xs text-slate-400 font-bold uppercase tracking-widest">
                    Top K Sources: <span className="text-blue-400 font-black">{topK}</span>
                  </label>
                  <input type="range" min={1} max={8} value={topK}
                    onChange={e => setTopK(+e.target.value)} className="w-full mt-1.5 accent-blue-500"/>
                </div>
                <button type="submit" disabled={loading || !query.trim()}
                  className="w-full py-3.5 rounded-xl font-black text-white text-sm uppercase tracking-wider transition-all duration-200 disabled:opacity-40"
                  style={{
                    background: loading ? 'rgba(59,130,246,0.4)' : 'linear-gradient(135deg,#3b82f6,#4f46e5)',
                    boxShadow: loading ? 'none' : '0 4px 24px rgba(59,130,246,0.35)',
                    transform: loading ? 'scale(0.98)' : 'scale(1)',
                  }}>
                  {loading ? `${DOTS[dotIdx]} Analysing…` : '✅ Check Compliance'}
                </button>
              </form>
            </div>
          </div>

          {/* ── Results panel ── */}
          <div className="col-span-3 space-y-4">

            {/* Idle */}
            {!loading && !result && !error && (
              <Idle3D icon="✅" color="#3b82f6" label="Enter your query to begin compliance analysis" />
            )}

            {/* Loading — radar scan */}
            {loading && (
              <div className="rounded-2xl p-8 flex flex-col items-center gap-5"
                style={{ background:'rgba(255,255,255,0.04)', border:'1px solid rgba(59,130,246,0.18)' }}>
                <div className="relative w-20 h-20">
                  {[0, 1, 2].map(i => (
                    <div key={i} className="absolute inset-0 rounded-full border-2 border-blue-500"
                      style={{ animation:`radar 1.8s ${i * 0.6}s ease-out infinite` }}/>
                  ))}
                  <div className="absolute inset-0 flex items-center justify-center text-3xl">✅</div>
                </div>
                <div className="text-center">
                  <p className="text-blue-300 font-bold">Scanning Spec Documents…</p>
                  <p className="text-slate-500 text-xs mt-1 font-mono">{DOTS[dotIdx]} Retrieving top {topK} chunks</p>
                </div>
                {stream && (
                  <div className="w-full rounded-xl p-4 text-xs font-mono text-green-300 leading-relaxed max-h-28 overflow-y-auto"
                    style={{ background:'rgba(0,0,0,0.45)' }}>
                    {stream}<span style={{ animation:'blink 0.7s step-end infinite' }}>█</span>
                  </div>
                )}
              </div>
            )}

            {/* Error */}
            {error && (
              <div className="pop-bounce rounded-2xl p-5 flex gap-4"
                style={{ background:'rgba(239,68,68,0.12)', border:'1px solid rgba(239,68,68,0.35)' }}>
                <span className="text-2xl">🚨</span>
                <div>
                  <p className="text-red-300 font-bold">Analysis Failed</p>
                  <p className="text-red-400 text-sm mt-1">{error}</p>
                </div>
              </div>
            )}

            {/* Result */}
            {result && cfg && (
              <div className={revealed ? 'flip-in-3d space-y-4' : 'opacity-0'}>

                {/* Status Badge */}
                <div className="relative">
                  {cfg.critical && (
                    <>
                      <div className="absolute inset-0 rounded-2xl border-2 border-red-500/50"
                        style={{ animation:'radar 1.8s ease-out infinite' }}/>
                      <div className="absolute inset-0 rounded-2xl border-2 border-red-500/25"
                        style={{ animation:'radar 1.8s 0.7s ease-out infinite' }}/>
                    </>
                  )}
                  <div className={`pop-bounce bg-gradient-to-r ${cfg.grad} ${cfg.glow} rounded-2xl p-5 text-white relative z-10`}>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <span className={`text-4xl ${cfg.critical ? 'siren-spin' : ''}`}>{cfg.icon}</span>
                        <div>
                          <p className="text-xs opacity-70 uppercase tracking-widest font-semibold">Compliance Status</p>
                          <p className={`text-2xl font-black ${cfg.critical ? 'glitch-text' : ''}`}>{result.status}</p>
                        </div>
                      </div>
                      {cfg.critical && <span className="siren-spin text-3xl" style={{ animationDirection:'reverse' }}>🚨</span>}
                    </div>
                  </div>
                </div>

                {/* Analysis */}
                <div className="rounded-2xl p-5"
                  style={{ background:'rgba(255,255,255,0.05)', backdropFilter:'blur(16px)',
                    border:'1px solid rgba(255,255,255,0.1)' }}>
                  <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3">Analysis</h3>
                  <p className="text-slate-200 text-sm leading-relaxed whitespace-pre-wrap">{result.analysis}</p>
                </div>

                {/* Sources */}
                {result.sources.length > 0 && (
                  <div className="space-y-2">
                    <h3 className="text-xs font-bold text-slate-400 uppercase tracking-widest">
                      📎 {result.sources.length} Source{result.sources.length !== 1 ? 's' : ''}
                    </h3>
                    {result.sources.map((src, i) => (
                      <div key={i} className="slide-from-right rounded-xl p-4"
                        style={{ background:'rgba(255,255,255,0.04)', backdropFilter:'blur(12px)',
                          border:'1px solid rgba(255,255,255,0.08)', animationDelay:`${i * 0.12}s` }}>
                        <div className="flex items-start gap-3">
                          <span className="flex-none w-6 h-6 rounded-md flex items-center justify-center text-xs font-black text-white"
                            style={{ background:'linear-gradient(135deg,#3b82f6,#4f46e5)' }}>{i + 1}</span>
                          <div className="flex-1 min-w-0">
                            <span className="px-2 py-0.5 rounded text-xs font-semibold text-blue-300 mb-1 inline-block"
                              style={{ background:'rgba(59,130,246,0.15)' }}>
                              {src.source || src.metadata?.source || 'document'}
                            </span>
                            <p className="text-slate-300 text-xs leading-relaxed">{src.content || src.text}</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}