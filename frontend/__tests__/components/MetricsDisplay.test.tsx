import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import MetricsDisplay from "@/components/dashboard/MetricsDisplay"

const sampleMetrics = `
# HELP helioops_uptime_seconds Process uptime in seconds
# TYPE helioops_uptime_seconds gauge
helioops_uptime_seconds 7200.00

# HELP helioops_pipeline_requests_total Total pipeline requests
# TYPE helioops_pipeline_requests_total counter
helioops_pipeline_requests_total 42

# HELP helioops_pipeline_errors_total Total pipeline errors
# TYPE helioops_pipeline_errors_total counter
helioops_pipeline_errors_total 3

# HELP helioops_pipeline_duration_seconds_avg Average pipeline duration
# TYPE helioops_pipeline_duration_seconds_avg gauge
helioops_pipeline_duration_seconds_avg 15.2300

# HELP helioops_pipeline_duration_seconds_p99 P99 pipeline duration
# TYPE helioops_pipeline_duration_seconds_p99 gauge
helioops_pipeline_duration_seconds_p99 28.5000

# HELP helioops_detection_requests_total Total detection requests
# TYPE helioops_detection_requests_total counter
helioops_detection_requests_total 20

# HELP helioops_advisory_requests_total Total advisory requests
# TYPE helioops_advisory_requests_total counter
helioops_advisory_requests_total 15

# HELP helioops_ws_connections_total Total WebSocket connections
# TYPE helioops_ws_connections_total counter
helioops_ws_connections_total 5
`

describe("MetricsDisplay", () => {
  it("renders uptime", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("2h 0m")).toBeInTheDocument()
  })

  it("renders pipeline requests", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("42")).toBeInTheDocument()
  })

  it("renders error rate percentage", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    // 3/42 = 7.1%
    expect(screen.getByText("7.1")).toBeInTheDocument()
  })

  it("renders avg latency", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("15.23")).toBeInTheDocument()
    const sUnits = screen.getAllByText("s")
    expect(sUnits.length).toBeGreaterThanOrEqual(1)
  })

  it("renders p99 latency", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("28.50")).toBeInTheDocument()
  })

  it("renders ws connections", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("5")).toBeInTheDocument()
  })

  it("renders detection requests", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("20")).toBeInTheDocument()
  })

  it("renders advisory requests", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("15")).toBeInTheDocument()
  })

  it("renders all gauge labels", () => {
    render(<MetricsDisplay rawMetrics={sampleMetrics} />)
    expect(screen.getByText("Uptime")).toBeInTheDocument()
    expect(screen.getByText("Pipeline Requests")).toBeInTheDocument()
    expect(screen.getByText("Error Rate")).toBeInTheDocument()
    expect(screen.getByText("WS Connections")).toBeInTheDocument()
    expect(screen.getByText("Avg Latency")).toBeInTheDocument()
    expect(screen.getByText("P99 Latency")).toBeInTheDocument()
    expect(screen.getByText("Detection Requests")).toBeInTheDocument()
    expect(screen.getByText("Advisory Requests")).toBeInTheDocument()
  })

  it("shows 0.0 error rate when no requests", () => {
    const noRequests = `
helioops_pipeline_requests_total 0
helioops_pipeline_errors_total 0
helioops_uptime_seconds 100
`
    render(<MetricsDisplay rawMetrics={noRequests} />)
    expect(screen.getByText("0.0")).toBeInTheDocument()
  })

  it("shows dash when no latency data", () => {
    const noLatency = `
helioops_pipeline_requests_total 10
helioops_pipeline_errors_total 0
helioops_pipeline_duration_seconds_avg 0
helioops_pipeline_duration_seconds_p99 0
helioops_uptime_seconds 100
`
    render(<MetricsDisplay rawMetrics={noLatency} />)
    const dashes = screen.getAllByText("—")
    expect(dashes.length).toBeGreaterThanOrEqual(2)
  })

  it("renders with empty metrics", () => {
    render(<MetricsDisplay rawMetrics="" />)
    expect(screen.getByText("Uptime")).toBeInTheDocument()
    expect(screen.getByText("0m")).toBeInTheDocument()
  })

  it("shows red error rate when above 5%", () => {
    const highError = `
helioops_pipeline_requests_total 10
helioops_pipeline_errors_total 1
helioops_uptime_seconds 100
`
    render(<MetricsDisplay rawMetrics={highError} />)
    const errorRate = screen.getByText("10.0")
    expect(errorRate.className).toContain("red-400")
  })
})
