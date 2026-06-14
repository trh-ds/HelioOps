"use client"

import { Component, type ReactNode } from "react"
import { AlertTriangle, RefreshCw } from "lucide-react"

interface Props {
  children: ReactNode
  fallback?: ReactNode
  onError?: (error: Error, errorInfo: React.ErrorInfo) => void
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.props.onError?.(error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="rounded-xl p-5 bg-red-500/[0.04] border border-red-500/[0.12] space-y-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-sm font-body font-medium text-red-300">
              Something went wrong
            </span>
          </div>

          {this.state.error && (
            <p className="text-xs font-mono text-red-400/60 break-all">
              {this.state.error.message}
            </p>
          )}

          <button
            onClick={this.handleReset}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-body text-red-300 hover:text-red-200 bg-red-500/[0.08] hover:bg-red-500/[0.12] border border-red-500/[0.15] transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            Try again
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
