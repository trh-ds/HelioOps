"use client"

import { useEffect, useRef, useState } from "react"
import { motion } from "framer-motion"

interface ContentSection {
  id: string
  start: number
  end: number
  children: (progress: number) => React.ReactNode
}

const sections: ContentSection[] = [
  {
    id: "threat",
    start: 0.1,
    end: 0.4,
    children: (p) => {
      const localP = (p - 0.1) / 0.3
      const opacity = Math.min(localP / 0.1, 1) * Math.max(1 - (localP - 0.9) / 0.1, 0)
      const x = 80 - localP * 80
      return (
        <div className="max-w-4xl mx-auto px-6" style={{ opacity, transform: `translateX(${x}px)` }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-warm/20 bg-warm/5 backdrop-blur-sm mb-5">
            <span className="w-1.5 h-1.5 rounded-full bg-warm" />
            <span className="text-[10px] font-mono text-warm/80 tracking-[0.2em] uppercase">Threat Vectors</span>
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-6 leading-tight">
            Solar Storms <br/>
            <span className="gradient-text-warm">Degrade Infrastructure</span>
          </h2>
          <p className="text-lg text-white/40 font-body leading-relaxed max-w-xl">
            Coronal Mass Ejections (CMEs) and solar flares degrade GPS tracking accuracy and trigger high-frequency (HF) radio blackouts globally.
          </p>
          <div className="grid grid-cols-3 gap-4 mt-12">
            {[
              { v: "±30m", l: "GPS L1 Error" },
              { v: "R1-R5", l: "NOAA Scale" },
              { v: "G5", l: "Max Severity" },
            ].map((s) => (
              <div key={s.l} className="glass rounded-2xl p-6 border border-white/[0.08]">
                <div className="text-3xl font-mono font-medium text-white">{s.v}</div>
                <div className="text-xs font-body text-white/40 mt-2">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      )
    },
  },
  {
    id: "ml",
    start: 0.4,
    end: 0.7,
    children: (p) => {
      const localP = (p - 0.4) / 0.3
      const opacity = Math.min(localP / 0.1, 1) * Math.max(1 - (localP - 0.9) / 0.1, 0)
      const y = 60 - localP * 60
      return (
        <div className="max-w-5xl mx-auto px-6 w-full" style={{ opacity, transform: `translateY(${y}px)` }}>
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-indigo/20 bg-indigo/5 backdrop-blur-sm mb-5 mx-auto w-fit">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo" />
            <span className="text-[10px] font-mono text-indigo/80 tracking-[0.2em] uppercase">Machine Learning</span>
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-6 text-center leading-tight">
            Predictive <span className="gradient-text-accent">Intelligence</span>
          </h2>
          <p className="text-lg text-white/40 font-body text-center max-w-2xl mx-auto mb-12">
            LightGBM algorithms forecasting GPS errors and HF blackouts with statistically calibrated uncertainty bounds.
          </p>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="col-span-1 md:col-span-2 glass-strong rounded-2xl p-8 border border-white/10 flex flex-col justify-center">
              <div className="text-5xl font-mono font-medium text-white mb-2">0.9858 <span className="text-xl text-white/40">R² Score</span></div>
              <p className="text-sm text-white/50 font-body">GPS L1 Error Prediction Accuracy</p>
            </div>
            <div className="glass rounded-2xl p-8 border border-white/5 flex flex-col justify-center">
              <div className="text-4xl font-mono font-medium text-aurora mb-2">96.4%</div>
              <p className="text-sm text-white/50 font-body">Confidence Interval Coverage</p>
            </div>
            <div className="glass rounded-2xl p-8 border border-white/5 flex flex-col justify-center">
              <div className="text-4xl font-mono font-medium text-white mb-2">3.2%</div>
              <p className="text-sm text-white/50 font-body">Mean Absolute Error (HF Radio)</p>
            </div>
            <div className="col-span-1 md:col-span-2 glass rounded-2xl p-8 border border-white/5 flex flex-col justify-center">
              <div className="text-4xl font-mono font-medium text-indigo mb-2">&lt; 500kb</div>
              <p className="text-sm text-white/50 font-body">Ultra-lightweight execution model for edge deployment</p>
            </div>
          </div>
        </div>
      )
    },
  },
  {
    id: "cta",
    start: 0.7,
    end: 1.0,
    children: (p) => {
      const localP = (p - 0.7) / 0.3
      const opacity = Math.min(localP / 0.15, 1)
      const scale = 0.95 + localP * 0.05
      return (
        <div className="text-center px-6 max-w-4xl mx-auto" style={{ opacity, transform: `scale(${scale})` }}>
          <h2 className="text-5xl md:text-7xl font-display font-bold mb-6 leading-tight">
            Deploy <span className="gradient-text-accent">HelioOps</span>
          </h2>
          <p className="text-lg text-white/40 font-body mb-10 max-w-xl mx-auto">
            Ready for integration. Equip your operations with enterprise-grade space weather predictions.
          </p>
          <button className="group relative px-10 py-5 rounded-xl bg-white text-deep-black font-semibold font-display text-lg overflow-hidden transition-all duration-500 hover:scale-[1.02]">
            <span className="relative z-10">Initialize Radar</span>
            <div className="absolute inset-0 bg-[linear-gradient(110deg,transparent_0%,rgba(0,0,0,0.1)_50%,transparent_100%)] -translate-x-full group-hover:translate-x-full transition-transform duration-[1.5s] ease-in-out" />
          </button>
          <div className="flex flex-wrap items-center justify-center gap-12 mt-16">
            {[
              { v: "Verified", l: "Physics Anchors" },
              { v: "< 50ms", l: "Inference Time" },
              { v: "Global", l: "Deployment" },
            ].map((s) => (
              <div key={s.l} className="text-center">
                <div className="text-base font-mono font-medium text-white">{s.v}</div>
                <div className="text-[11px] font-body text-white/40 mt-1 uppercase tracking-widest">{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      )
    },
  },
]

export default function SectionOverlay() {
  const [activeId, setActiveId] = useState("hero")
  const [progressMap, setProgressMap] = useState<Record<string, number>>({})

  useEffect(() => {
    const onScroll = () => {
      const scrollTop = window.scrollY
      const docHeight = document.documentElement.scrollHeight - window.innerHeight
      const progress = Math.min(scrollTop / docHeight, 1)

      let found = "hero"
      const map: Record<string, number> = {}
      for (const s of sections) {
        if (progress >= s.start && progress <= s.end) found = s.id
        const localP = Math.max(0, Math.min(1, (progress - s.start) / (s.end - s.start)))
        map[s.id] = localP
      }
      setActiveId(found)
      setProgressMap(map)
    }

    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <div className="fixed inset-0 z-10 flex items-center pointer-events-none">
      {sections.map((s) => (
        <div key={s.id} className="w-full" style={{ display: activeId === s.id ? "block" : "none" }}>
          {s.children(progressMap[s.id] ?? 0)}
        </div>
      ))}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 flex items-center gap-2">
        {sections.map((s) => (
          <div
            key={s.id}
            className={`h-0.5 rounded-full transition-all duration-500 ${
              activeId === s.id ? "w-8 bg-white/40" : "w-2 bg-white/10"
            }`}
          />
        ))}
      </div>
    </div>
  )
}
