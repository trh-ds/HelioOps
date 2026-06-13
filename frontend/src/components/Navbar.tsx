"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"

const links = ["Dashboard", "API", "Docs", "Status"]

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 60)
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <motion.nav
      initial={{ y: -80, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 1, delay: 0.5, ease: [0.16, 1, 0.3, 1] }}
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-700 ${
        scrolled ? "glass border-b border-white/[0.04]" : ""
      }`}
    >
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="w-7 h-7 rounded-md bg-gradient-to-br from-aurora to-indigo flex items-center justify-center">
            <span className="text-[10px] font-bold text-deep-black font-display">H</span>
          </div>
          <span className="text-base font-display font-semibold text-white/90 tracking-tight">HelioOps</span>
        </a>

        <div className="hidden md:flex items-center gap-8">
          {links.map((l) => (
            <a
              key={l}
              href="#"
              className="text-sm text-white/40 hover:text-white/80 transition-all duration-300 font-body tracking-wide"
            >
              {l}
            </a>
          ))}
        </div>

        <button className="px-5 py-2 rounded-xl bg-white/[0.04] border border-white/[0.06] text-sm text-white/70 font-medium font-display hover:bg-white/[0.08] hover:text-white/90 transition-all duration-300">
          Sign In
        </button>
      </div>
    </motion.nav>
  )
}
