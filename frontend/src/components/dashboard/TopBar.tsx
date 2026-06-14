"use client"

import { useEffect, useState } from "react"
import { usePathname } from "next/navigation"
import clsx from "clsx"
import { api } from "@/lib/api"
import { wsClient } from "@/lib/ws-client"

const pageTitles: Record<string, string> = {
  "/dashboard": "Storm List",
  "/dashboard/pipeline": "Pipeline",
  "/dashboard/health": "Health",
}

function getPageTitle(pathname: string): string {
  if (pageTitles[pathname]) return pageTitles[pathname]
  for (const [prefix, title] of Object.entries(pageTitles)) {
    if (pathname.startsWith(prefix) && pathname !== prefix) return title
  }
  return "Dashboard"
}

export default function TopBar() {
  const pathname = usePathname()
  const [wsConnected, setWsConnected] = useState(false)
  const [healthStatus, setHealthStatus] = useState<string | null>(null)

  // Poll health every 30s
  useEffect(() => {
    let active = true

    async function checkHealth() {
      try {
        const res = await api.getHealth()
        if (active) setHealthStatus(res.status)
      } catch {
        if (active) setHealthStatus("offline")
      }
    }

    checkHealth()
    const interval = setInterval(checkHealth, 30000)
    return () => {
      active = false
      clearInterval(interval)
    }
  }, [])

  // Track WebSocket connection state
  useEffect(() => {
    setWsConnected(wsClient.isConnected())

    const interval = setInterval(() => {
      setWsConnected(wsClient.isConnected())
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  return (
    <header className="h-16 flex items-center justify-between px-6 border-b border-white/[0.06] bg-deep-black/60 backdrop-blur-xl">
      <h1 className="text-sm font-display font-semibold text-white/80 tracking-wide">
        {getPageTitle(pathname)}
      </h1>

      <div className="flex items-center gap-4">
        {/* Backend health badge */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
          <span
            className={clsx(
              "w-2 h-2 rounded-full",
              healthStatus === "ok" || healthStatus === "ready"
                ? "bg-aurora"
                : healthStatus === "degraded"
                  ? "bg-warm"
                  : "bg-red-500",
            )}
          />
          <span className="text-xs font-mono text-white/50">
            {healthStatus ?? "..."}
          </span>
        </div>

        {/* WebSocket status dot */}
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/[0.06]">
          <span
            className={clsx(
              "w-2 h-2 rounded-full animate-pulse-soft",
              wsConnected ? "bg-aurora" : "bg-red-500",
            )}
          />
          <span className="text-xs font-mono text-white/50">
            WS {wsConnected ? "live" : "off"}
          </span>
        </div>
      </div>
    </header>
  )
}
