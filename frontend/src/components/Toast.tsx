"use client"

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  useRef,
  type ReactNode,
} from "react"
import { AlertTriangle, CheckCircle, Info, X } from "lucide-react"
import clsx from "clsx"

export type ToastType = "error" | "success" | "info"

export interface Toast {
  id: string
  type: ToastType
  message: string
}

interface ToastContextValue {
  addToast: (message: string, type?: ToastType) => void
  dismissToast: (id: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const TOAST_DURATION = 5000
const MAX_TOASTS = 5

const ICONS: Record<ToastType, typeof AlertTriangle> = {
  error: AlertTriangle,
  success: CheckCircle,
  info: Info,
}

const STYLES: Record<ToastType, string> = {
  error: "bg-red-500/10 border-red-500/20 text-red-300",
  success: "bg-emerald-500/10 border-emerald-500/20 text-emerald-300",
  info: "bg-white/[0.04] border-white/[0.08] text-white/60",
}

const ICON_STYLES: Record<ToastType, string> = {
  error: "text-red-400",
  success: "text-emerald-400",
  info: "text-white/40",
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const timersRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map())

  const dismissToast = useCallback((id: string) => {
    const timer = timersRef.current.get(id)
    if (timer) {
      clearTimeout(timer)
      timersRef.current.delete(id)
    }
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const addToast = useCallback(
    (message: string, type: ToastType = "error") => {
      const id = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
      const toast: Toast = { id, type, message }

      setToasts((prev) => {
        const next = [toast, ...prev]
        return next.length > MAX_TOASTS ? next.slice(0, MAX_TOASTS) : next
      })

      const timer = setTimeout(() => {
        dismissToast(id)
        timersRef.current.delete(id)
      }, TOAST_DURATION)
      timersRef.current.set(id, timer)
    },
    [dismissToast]
  )

  useEffect(() => {
    return () => {
      timersRef.current.forEach((timer) => clearTimeout(timer))
    }
  }, [])

  return (
    <ToastContext.Provider value={{ addToast, dismissToast }}>
      {children}
      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error("useToast must be used within ToastProvider")
  return ctx
}

function ToastContainer({
  toasts,
  onDismiss,
}: {
  toasts: Toast[]
  onDismiss: (id: string) => void
}) {
  if (toasts.length === 0) return null

  return (
    <div
      className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm"
      role="status"
      aria-live="polite"
    >
      {toasts.map((toast) => {
        const Icon = ICONS[toast.type]
        return (
          <div
            key={toast.id}
            className={clsx(
              "flex items-start gap-3 px-4 py-3 rounded-xl border backdrop-blur-sm animate-in slide-in-from-bottom-2",
              STYLES[toast.type]
            )}
          >
            <Icon className={clsx("w-4 h-4 shrink-0 mt-0.5", ICON_STYLES[toast.type])} />
            <span className="text-sm font-body flex-1">{toast.message}</span>
            <button
              onClick={() => onDismiss(toast.id)}
              className="shrink-0 text-white/30 hover:text-white/60 transition-colors"
              aria-label="Dismiss"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )
      })}
    </div>
  )
}
