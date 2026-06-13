"use client"

import { motion } from "framer-motion"

const fadeUp = {
  initial: { opacity: 0, y: 40 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-100px" },
  transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1] },
}

const fadeUpDelay = (delay: number) => ({
  ...fadeUp,
  transition: { duration: 0.8, ease: [0.22, 1, 0.36, 1], delay },
})

export default function SectionOverlay() {
  return (
    <section className="relative z-10 bg-deep-black">
      <div className="max-w-7xl mx-auto px-6 py-32">

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-start mb-32">
          <motion.div {...fadeUp} className="lg:col-span-7">
            <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-6 leading-tight tracking-tight">
              Solar Storms <br />
              <span className="gradient-text-warm">Degrade Infrastructure</span>
            </h2>
            <p className="text-lg text-white/40 font-body leading-relaxed max-w-[55ch]">
              Coronal Mass Ejections and solar flares degrade GPS tracking accuracy and trigger HF radio blackouts across global infrastructure.
            </p>
          </motion.div>

          <motion.div {...fadeUpDelay(0.15)} className="lg:col-span-5 grid grid-cols-2 gap-3">
            <div className="glass rounded-2xl p-5">
              <div className="text-2xl md:text-3xl font-mono font-medium text-white">±30m</div>
              <div className="text-xs font-body text-white/40 mt-1.5">GPS L1 Error</div>
            </div>
            <div className="glass rounded-2xl p-5">
              <div className="text-2xl md:text-3xl font-mono font-medium text-white">R1–R5</div>
              <div className="text-xs font-body text-white/40 mt-1.5">NOAA Scale</div>
            </div>
            <div className="col-span-2 glass rounded-2xl p-5">
              <div className="text-2xl md:text-3xl font-mono font-medium text-warm">G5</div>
              <div className="text-xs font-body text-white/40 mt-1.5">Maximum Severity</div>
            </div>
          </motion.div>
        </div>

        <motion.div {...fadeUp} className="mb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-aurora/20 bg-aurora/5 backdrop-blur-sm mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-aurora" />
            <span className="text-[10px] font-mono text-aurora/80 tracking-[0.2em] uppercase">
              Machine Learning
            </span>
          </div>
          <h2 className="text-4xl md:text-5xl lg:text-6xl font-display font-bold mb-6 leading-tight tracking-tight">
            Predictive <span className="gradient-text-accent">Intelligence</span>
          </h2>
          <p className="text-lg text-white/40 font-body max-w-[55ch]">
            LightGBM algorithms forecasting GPS errors and HF blackouts with calibrated uncertainty bounds.
          </p>
        </motion.div>

        <div className="grid grid-cols-1 md:grid-cols-6 gap-3 mb-32">
          <motion.div
            {...fadeUp}
            className="md:col-span-4 glass-strong rounded-2xl p-8 border border-white/10"
          >
            <div className="text-4xl md:text-5xl font-mono font-medium text-white mb-2">
              0.9858 <span className="text-lg text-white/40">R² Score</span>
            </div>
            <p className="text-sm text-white/50 font-body">GPS L1 Error Prediction Accuracy</p>
          </motion.div>
          <motion.div
            {...fadeUpDelay(0.08)}
            className="md:col-span-2 glass rounded-2xl p-8 border border-white/5"
          >
            <div className="text-3xl md:text-4xl font-mono font-medium text-aurora mb-2">96.4%</div>
            <p className="text-sm text-white/50 font-body">Confidence Interval Coverage</p>
          </motion.div>
          <motion.div
            {...fadeUpDelay(0.12)}
            className="md:col-span-2 glass rounded-2xl p-8 border border-white/5"
          >
            <div className="text-3xl md:text-4xl font-mono font-medium text-white mb-2">3.2%</div>
            <p className="text-sm text-white/50 font-body">Mean Absolute Error (HF)</p>
          </motion.div>
          <motion.div
            {...fadeUpDelay(0.16)}
            className="md:col-span-4 glass rounded-2xl p-8 border border-white/5"
          >
            <div className="text-3xl md:text-4xl font-mono font-medium text-white mb-2">&lt; 500kb</div>
            <p className="text-sm text-white/50 font-body">Ultra-lightweight model for edge deployment</p>
          </motion.div>
        </div>

        <motion.div {...fadeUp} className="text-center py-24">
          <h2 className="text-5xl md:text-7xl font-display font-bold mb-6 leading-tight tracking-tight">
            Deploy <span className="gradient-text-accent">HelioOps</span>
          </h2>
          <p className="text-lg text-white/40 font-body mb-10 max-w-xl mx-auto">
            Enterprise-grade space weather predictions, ready for integration.
          </p>
          <button className="group relative px-10 py-5 rounded-xl bg-aurora text-deep-black font-semibold font-display text-lg overflow-hidden transition-all duration-500 hover:scale-[1.02] active:scale-[0.98]">
            <span className="relative z-10">Deploy Platform</span>
            <div className="absolute inset-0 bg-[linear-gradient(110deg,transparent_0%,rgba(255,255,255,0.15)_50%,transparent_100%)] -translate-x-full group-hover:translate-x-full transition-transform duration-[1.5s] ease-in-out" />
          </button>
          <div className="flex flex-wrap items-center justify-center gap-12 mt-16">
            {[
              { v: "Verified", l: "Physics Anchors" },
              { v: "< 50ms", l: "Inference Time" },
              { v: "Global", l: "Deployment" },
            ].map((s) => (
              <div key={s.l} className="text-center">
                <div className="text-base font-mono font-medium text-white">{s.v}</div>
                <div className="text-[11px] font-body text-white/40 mt-1 uppercase tracking-widest">
                  {s.l}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>
    </section>
  )
}