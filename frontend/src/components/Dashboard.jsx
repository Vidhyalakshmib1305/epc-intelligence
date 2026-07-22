import { useState, useEffect, useRef } from 'react'

function AnimatedCounter({ target, duration = 1800 }) {
  const [count, setCount] = useState(0)
  const raf = useRef(null)
  useEffect(() => {
    let start = null
    const step = (ts) => {
      if (!start) start = ts
      const p = Math.min((ts - start) / duration, 1)
      setCount(Math.floor((1 - Math.pow(1 - p, 3)) * target))
      if (p < 1) raf.current = requestAnimationFrame(step)
    }
    raf.current = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf.current)
  }, [target])
  return <>{count}</>
}

function Tilt({ children, className }) {
  const ref = useRef(null)
  const move = (e) => {
    const r = ref.current.getBoundingClientRect()
    const rx = ((e.clientY - r.top  - r.height/2) / (r.height/2)) * -12
    const ry = ((e.clientX - r.left - r.width /2) / (r.width /2)) *  12
    ref.current.style.transform = `perspective(700px) rotateX(${rx}deg) rotateY(${ry}deg) scale(1.06)`
  }
  const leave = () => { ref.current.style.transform = '' }
  return (
    <div ref={ref} className={`tilt-card ${className}`} onMouseMove={move} onMouseLeave={leave}>
      {children}
    </div>
  )
}

function Particles() {
  const pts = Array.from({ length: 18 }, (_, i) => ({
    id: i, size: Math.random() * 6 + 2,
    left: Math.random() * 100, delay: Math.random() * 5, dur: Math.random() * 4 + 4,
  }))
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {pts.map(p => (
        <div key={p.id} className="absolute rounded-full bg-white"
          style={{ width: p.size, height: p.size, left: `${p.left}%`, bottom: 0, opacity: 0,
            animation: `floatUp ${p.dur}s ${p.delay}s ease-in infinite` }} />
      ))}
    </div>
  )
}

function LiveClock() {
  const [time, setTime] = useState(new Date())
  useEffect(() => { const iv = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(iv) }, [])
  return (
    <span className="font-mono text-blue-200 text-sm tabular-nums">
      {time.toLocaleTimeString('en-IN', { timeZone: 'Asia/Kolkata', hour12: false })} IST
    </span>
  )
}

function AlertTicker() {
  const alerts = [
    '🚨 CRITICAL: ABB 33kV Switchgear panel damaged in transit — replacement ETA 30 Jun 2026',
    '⚠️ HIGH: Eaton UPS Systems — only 2-week buffer before installation window',
    '⚠️ HIGH: Stulz CRAH Batch 2 delayed 6 weeks — only 4 of 12 units on site',
    '❌ NCR-001 OPEN: UPS Unit 2 tripped at 87% load — retest scheduled 25 Jun 2026',
    '❌ NCR-002 OPEN: CRAH hot aisle reached 38°C — blanking panels missing rows 3 & 4',
    '⏳ PENDING: HV Switchgear interlock test — waiting for ABB replacement panel',
    '✅ PASSED: Generator auto-start test — all 3 generators started within 8 seconds',
    '✅ PASSED: Chiller efficiency COP 6.4 at 95% load — exceeds spec minimum of 6.0',
  ]
  const text = alerts.join('     ·     ')
  return (
    <div className="bg-slate-900 border-y border-slate-700 py-2 overflow-hidden">
      <div className="ticker-text text-xs font-mono text-amber-400">
        {'⚡ LIVE ALERTS   ' + text + '   ⚡ LIVE ALERTS   ' + text}
      </div>
    </div>
  )
}

function MetricCard({ label, value, icon, gradient, glow, ping, loaded }) {
  return (
    <Tilt className={`${gradient} ${glow} rounded-2xl p-5 text-white cursor-default shadow-xl`}>
      <div className="flex justify-between items-start mb-4">
        <span className="text-3xl">{icon}</span>
        {ping && (
          <div className="relative w-4 h-4">
            <div className="absolute inset-0 rounded-full bg-white opacity-60 animate-ping" />
            <div className="absolute inset-0 rounded-full bg-white opacity-40"
              style={{ animation: 'radar 2s 0.7s ease-out infinite' }} />
            <div className="absolute inset-0 rounded-full bg-white opacity-90 scale-50 rounded-full" />
          </div>
        )}
      </div>
      <div className="text-4xl font-black mb-1">
        {loaded ? <AnimatedCounter target={value} /> : '—'}
      </div>
      <div className="text-sm opacity-80 font-medium">{label}</div>
    </Tilt>
  )
}

function AgentCard({ agent, onClick }) {
  const [hovered, setHovered] = useState(false)
  return (
    <Tilt className={`bg-gradient-to-br ${agent.gradient} rounded-2xl cursor-pointer shadow-lg`}>
      <div className="p-5 text-white" onClick={() => onClick(agent.id)}
        onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}>
        <div className={`text-3xl mb-3 inline-block transition-all duration-200 ${hovered ? 'bounce-icon scale-125' : ''}`}>
          {agent.icon}
        </div>
        <div className="font-bold text-sm mb-1">{agent.label}</div>
        <div className="text-xs opacity-75 leading-relaxed mb-3">{agent.desc}</div>
        <div className={`text-xs font-semibold flex items-center gap-1 transition-all duration-300 ${hovered ? 'opacity-100 gap-2' : 'opacity-50'}`}>
          Launch <span className={`transition-transform duration-300 ${hovered ? 'translate-x-1' : ''}`}>→</span>
        </div>
      </div>
    </Tilt>
  )
}

export default function Dashboard({ onNavigate }) {
  const [docCount, setDocCount] = useState(0)
  const [loaded, setLoaded] = useState(false)
  const [progress, setProgress] = useState(0)
  const [displayTitle, setDisplayTitle] = useState('')
  const [titleDone, setTitleDone] = useState(false)
  const [evalLatest, setEvalLatest] = useState(null)
  const title = "Hyperscale Data Centre"

  useEffect(() => {
    let i = 0
    const iv = setInterval(() => {
      setDisplayTitle(title.slice(0, i + 1)); i++
      if (i >= title.length) { clearInterval(iv); setTitleDone(true) }
    }, 55)
    fetch('/api/documents').then(r => r.json())
      .then(d => { setDocCount(d.length); setLoaded(true) })
      .catch(() => setLoaded(true))
    fetch('/api/eval/runs/latest').then(r => r.json())
      .then(d => { if (d?.id) setEvalLatest(d) })
      .catch(() => {})
    setTimeout(() => setProgress(64), 700)
    return () => clearInterval(iv)
  }, [])

  const agents = [
    { id: 'spec-compliance',  label: 'Spec Compliance',  icon: '✅', gradient: 'from-blue-500 to-blue-700',    desc: 'Detect specification deviations instantly' },
    { id: 'schedule-risk',    label: 'Schedule Risk',    icon: '📅', gradient: 'from-violet-500 to-violet-700', desc: 'Predict delays weeks before they hit the critical path' },
    { id: 'rfi-copilot',      label: 'RFI Copilot',      icon: '💬', gradient: 'from-teal-500 to-teal-700',     desc: 'Search past RFI resolutions in seconds' },
    { id: 'supply-chain',     label: 'Supply Chain',     icon: '🚚', gradient: 'from-orange-500 to-orange-600', desc: 'Track at-risk equipment deliveries live' },
    { id: 'commissioning-qa', label: 'Commissioning QA', icon: '🔬', gradient: 'from-pink-500 to-pink-700',     desc: 'Monitor NCRs and Tier III readiness' },
  ]

  return (
    <div className="slide-in space-y-0">
      {/* Alert Ticker */}
      <div className="-mx-8 -mt-8 mb-6">
        <AlertTicker />
      </div>

      <div className="space-y-6">
        {/* Hero */}
        <div className="relative bg-gradient-to-r from-blue-800 via-indigo-800 to-violet-900 rounded-2xl overflow-hidden" style={{ minHeight: 170 }}>
          <div className="absolute inset-0 animated-grid" />
          <Particles />
          <div className="absolute top-4 right-6 flex items-center gap-3 z-10">
            <LiveClock />
            <span className="text-3xl" title="Our hardhat hero">👷‍♂️</span>
          </div>
          <div className="relative z-10 p-8">
            <div className="flex items-center gap-3 mb-3">
              <span className="flex items-center gap-1.5 bg-green-400 text-green-900 text-xs font-bold px-3 py-1 rounded-full animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-green-900 animate-ping" />LIVE
              </span>
              <span className="text-blue-300 text-sm">Chennai Campus · Phase 1 · ET AI Hackathon 2026</span>
            </div>
            <h1 className="text-4xl font-black text-white mb-1 tracking-tight min-h-[48px]">
              {displayTitle}
              {!titleDone && <span className="inline-block w-0.5 h-8 bg-white ml-1 align-middle"
                style={{ animation: 'blink 0.7s step-end infinite' }} />}
            </h1>
            <p className="text-blue-300 text-base">AI-Powered EPC Intelligence · Mistral 7B · Fully Local · Zero API Keys · Zero Cloud</p>
          </div>
        </div>

        {/* Metric Cards */}
        <div className="grid grid-cols-4 gap-4">
          <MetricCard label="Documents Indexed"  value={loaded ? docCount : 0} icon="📄"
            gradient="bg-gradient-to-br from-blue-500 to-blue-700"     glow=""            ping={false} loaded={loaded} />
          <MetricCard label="Open NCRs"          value={2}  icon="⚠️"
            gradient="bg-gradient-to-br from-red-500 to-red-700"       glow="glow-red"    ping={true}  loaded={loaded} />
          <MetricCard label="At-Risk Deliveries" value={3}  icon="🚨"
            gradient="bg-gradient-to-br from-orange-500 to-orange-600" glow="glow-orange" ping={true}  loaded={loaded} />
          <MetricCard label="Tests Passed / 48"  value={27} icon="✅"
            gradient="bg-gradient-to-br from-green-500 to-green-700"   glow=""            ping={false} loaded={loaded} />
        </div>

        {/* Progress */}
        <div className="bg-white rounded-2xl border border-gray-100 shadow-sm p-6">
          <div className="flex justify-between items-center mb-3">
            <div>
              <h3 className="font-bold text-gray-800 text-lg">Commissioning Progress</h3>
              <p className="text-sm text-gray-400">31 of 48 tests complete · 2 open NCRs · Tier III Audit: 15 Jul 2026</p>
            </div>
            <div className="text-right">
              <span className="text-4xl font-black text-blue-600">{progress}%</span>
            </div>
          </div>
          <div className="w-full bg-gray-100 rounded-full h-5 overflow-hidden">
            <div className="h-5 rounded-full bg-gradient-to-r from-blue-500 via-indigo-500 to-green-500 relative transition-all duration-1000 ease-out"
              style={{ width: `${progress}%` }}>
              <div className="absolute inset-0 bg-white opacity-20 animate-pulse rounded-full" />
              <div className="absolute right-2 top-0 bottom-0 flex items-center text-white text-xs font-bold">{progress}%</div>
            </div>
          </div>
          <div className="flex justify-between text-xs mt-3">
            <span className="flex items-center gap-1 text-green-600 font-semibold bg-green-50 px-2 py-1 rounded-lg">✅ 27 Passed</span>
            <span className="flex items-center gap-1 text-red-500 font-semibold bg-red-50 px-2 py-1 rounded-lg">❌ 3 Failed</span>
            <span className="flex items-center gap-1 text-yellow-600 font-semibold bg-yellow-50 px-2 py-1 rounded-lg">⏳ 1 Pending</span>
            <span className="flex items-center gap-1 text-gray-400 font-medium bg-gray-50 px-2 py-1 rounded-lg">⬜ 17 Not Started</span>
          </div>
        </div>

        {/* RAG Eval Health Card */}
        <div className="rounded-2xl p-5 cursor-pointer transition-all hover:scale-[1.01]"
          style={{ background: evalLatest
            ? 'linear-gradient(135deg,rgba(99,102,241,0.12),rgba(79,70,229,0.08))'
            : 'rgba(255,255,255,0.03)',
            border: evalLatest ? '1px solid rgba(99,102,241,0.3)' : '1px dashed rgba(255,255,255,0.12)' }}
          onClick={() => onNavigate('eval')}>
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <span className="text-2xl">🧪</span>
              <div>
                <p className="font-bold text-white text-sm">RAG Quality Metrics</p>
                <p className="text-slate-400 text-xs">
                  {evalLatest
                    ? `Last run: ${evalLatest.run_at?.slice(0,10)} · ${evalLatest.total_questions} questions`
                    : 'No eval run yet — click to set up'}
                </p>
              </div>
            </div>
            <span className="text-slate-500 text-xs font-mono">→ RAG Eval</span>
          </div>
          {evalLatest ? (
            <div className="grid grid-cols-5 gap-3">
              {[
                { label: 'Hit@1',        val: evalLatest.hit_at_1,         color: '#6366f1' },
                { label: 'Hit@3',        val: evalLatest.hit_at_3,         color: '#8b5cf6' },
                { label: 'Hit@5',        val: evalLatest.hit_at_5,         color: '#a78bfa' },
                { label: 'MRR',          val: evalLatest.mrr,              color: '#3b82f6' },
                { label: 'Faithfulness', val: evalLatest.avg_faithfulness, color: '#10b981' },
              ].map(m => (
                <div key={m.label} className="rounded-xl p-3 text-center"
                  style={{ background:'rgba(0,0,0,0.2)', border:`1px solid ${m.color}33` }}>
                  <p className="text-lg font-black" style={{ color: m.color }}>
                    {Math.round((m.val ?? 0) * 100)}%
                  </p>
                  <p className="text-xs text-slate-500 font-bold uppercase tracking-widest mt-0.5">{m.label}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-slate-500 text-xs">
              Generate Q&A pairs from uploaded documents, validate them, then run eval to see retrieval quality metrics here.
            </p>
          )}
        </div>

        {/* Agents */}
        <div>
          <h3 className="font-bold text-gray-700 mb-3 text-lg">🤖 AI Agents — hover & click to launch</h3>
          <div className="grid grid-cols-5 gap-3">
            {agents.map(a => <AgentCard key={a.id} agent={a} onClick={onNavigate} />)}
          </div>
        </div>

        <div className="text-center text-gray-400 text-xs py-2 border-t border-gray-100">
          🏗️ Mistral 7B · Qdrant · FastAPI · React · Docker · <span className="text-green-500 font-semibold">Zero API keys</span> · <span className="text-blue-500 font-semibold">Zero cloud</span>
        </div>
      </div>
    </div>
  )
}
