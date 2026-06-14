"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useState } from "react"
import { LayoutDashboard, Activity, HeartPulse, Home, Menu, X } from "lucide-react"
import clsx from "clsx"

const navLinks = [
  { href: "/dashboard/storms", label: "Storm List", icon: LayoutDashboard },
  { href: "/dashboard/pipeline", label: "Pipeline", icon: Activity },
  { href: "/dashboard/health", label: "Health", icon: HeartPulse },
]

const homeLink = { href: "/", label: "Back to Home", icon: Home }

export default function Sidebar() {
  const pathname = usePathname()
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <>
      {/* Mobile toggle */}
      <button
        onClick={() => setMobileOpen(!mobileOpen)}
        className="fixed top-4 left-4 z-50 md:hidden p-2 rounded-lg bg-deep-900/80 border border-white/[0.08] backdrop-blur-xl"
        aria-label="Toggle navigation"
      >
        {mobileOpen ? (
          <X className="w-5 h-5 text-white/60" />
        ) : (
          <Menu className="w-5 h-5 text-white/60" />
        )}
      </button>

      {/* Mobile overlay */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          "fixed top-0 left-0 z-40 h-full w-60 flex flex-col",
          "bg-deep-black/95 backdrop-blur-xl border-r border-white/[0.06]",
          "transition-transform duration-300 ease-[cubic-bezier(0.16,1,0.3,1)]",
          "md:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {/* Logo */}
        <div className="h-16 flex items-center gap-2.5 px-5 border-b border-white/[0.06]">
          <div className="w-7 h-7 rounded-md bg-aurora flex items-center justify-center">
            <span className="text-[10px] font-bold text-deep-black font-display">H</span>
          </div>
          <span className="text-base font-display font-semibold text-white/90 tracking-tight">
            HelioOps
          </span>
        </div>

        {/* Nav links */}
        <nav className="flex-1 py-4 px-3 space-y-1">
          {navLinks.map(({ href, label, icon: Icon }) => {
            const isActive = pathname.startsWith(href)

            return (
              <Link
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={clsx(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-body transition-all duration-200",
                  isActive
                    ? "bg-aurora/[0.08] text-aurora border border-aurora/[0.12]"
                    : "text-white/40 hover:text-white/70 hover:bg-white/[0.04] border border-transparent",
                )}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* Bottom link */}
        <div className="px-3 pb-4 border-t border-white/[0.06] pt-3">
          <Link
            href={homeLink.href}
            onClick={() => setMobileOpen(false)}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-body text-white/30 hover:text-white/60 hover:bg-white/[0.03] transition-colors duration-200 border border-transparent"
          >
            <homeLink.icon className="w-4 h-4 shrink-0" />
            {homeLink.label}
          </Link>
        </div>
      </aside>
    </>
  )
}
