"use client"

import { motion, useScroll, useTransform } from "framer-motion"

const links = ["Dashboard", "API", "Docs", "Status"]

export default function Navbar() {
  const { scrollY } = useScroll()
  const bgOpacity = useTransform(scrollY, [0, 60], [0, 0.6])
  const borderOpacity = useTransform(scrollY, [0, 60], [0, 0.04])

  return (
    <motion.nav
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 1, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className="fixed top-0 left-0 right-0 z-50 backdrop-blur-xl"
    >
      <motion.div
        className="absolute inset-0 -z-10 bg-deep-black"
        style={{ opacity: bgOpacity }}
      />
      <motion.div
        className="absolute bottom-0 left-0 right-0 h-px bg-white"
        style={{ opacity: borderOpacity }}
      />
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between relative">
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-md bg-aurora flex items-center justify-center">
            <span className="text-[10px] font-bold text-deep-black font-display">H</span>
          </div>
          <span className="text-base font-display font-semibold text-white/90 tracking-tight">HelioOps</span>
        </a>

        <div className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a
              key={l}
              href="#"
              className="text-sm text-white/40 hover:text-white/80 transition-colors duration-300 font-body tracking-wide"
            >
              {l}
            </a>
          ))}
        </div>

        <button className="px-5 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06] text-sm text-white/70 font-medium font-display hover:bg-white/[0.08] hover:text-white/90 transition-all duration-300 active:scale-[0.98]">
          Sign In
        </button>
      </div>
    </motion.nav>
  )
}