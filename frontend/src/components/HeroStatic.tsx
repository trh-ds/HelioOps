"use client"

import { motion } from "framer-motion"

export default function HeroStatic() {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center pt-20 px-6 bg-deep-black overflow-hidden">
      {/* Background radial gradient for subtle glow */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] bg-indigo/5 rounded-full blur-[120px] pointer-events-none" />
      
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, ease: "easeOut" }}
        className="max-w-5xl mx-auto text-center relative z-10"
      >
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 backdrop-blur-md mb-8">
          <span className="w-2 h-2 rounded-full bg-aurora animate-pulse-soft" />
          <span className="text-xs font-mono text-white/60 tracking-[0.15em] uppercase">
            Defense-Grade Infrastructure
          </span>
        </div>

        <h1 className="text-5xl md:text-7xl lg:text-8xl font-display font-semibold tracking-tight leading-[1.1] mb-8 text-white">
          Predictive Space Weather <br />
          <span className="gradient-text-accent">Impact Intelligence</span>
        </h1>

        <p className="text-lg md:text-xl text-white/40 font-body max-w-2xl mx-auto leading-relaxed mb-12">
          Empowering aviation and military operators with real-time GPS L1 error tracking 
          and HF radio blackout forecasting. Built on verified LightGBM architectures.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button className="px-8 py-4 rounded-xl bg-white text-deep-black font-semibold font-display text-base transition-all duration-300 hover:scale-[1.02] hover:bg-white/90">
            Deploy Platform
          </button>
          <button className="px-8 py-4 rounded-xl glass border border-white/10 text-white font-semibold font-display text-base transition-all duration-300 hover:bg-white/10">
            Read Documentation
          </button>
        </div>
      </motion.div>

      {/* Scroll indicator */}
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.2, duration: 1 }}
        className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3"
      >
        <span className="text-[10px] font-mono text-white/30 uppercase tracking-widest">Scroll to explore</span>
        <div className="w-px h-12 bg-gradient-to-b from-white/20 to-transparent" />
      </motion.div>
    </div>
  )
}
