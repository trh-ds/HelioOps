import { describe, it, expect } from "vitest"
import { parseMetrics } from "@/lib/api"

describe("parseMetrics", () => {
  it("parses valid Prometheus text", () => {
    const text = `
# HELP helioops_uptime_seconds Process uptime
# TYPE helioops_uptime_seconds gauge
helioops_uptime_seconds 3600.50

# HELP helioops_pipeline_requests_total Total requests
# TYPE helioops_pipeline_requests_total counter
helioops_pipeline_requests_total 42
`
    const metrics = parseMetrics(text)
    expect(metrics.get("helioops_uptime_seconds")).toBe(3600.5)
    expect(metrics.get("helioops_pipeline_requests_total")).toBe(42)
  })

  it("skips comment lines", () => {
    const text = `
# This is a comment
# TYPE helioops_uptime_seconds gauge
helioops_uptime_seconds 100
`
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(1)
    expect(metrics.get("helioops_uptime_seconds")).toBe(100)
  })

  it("skips empty lines", () => {
    const text = `
helioops_uptime_seconds 100

helioops_pipeline_requests_total 5

`
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(2)
  })

  it("handles empty string", () => {
    const metrics = parseMetrics("")
    expect(metrics.size).toBe(0)
  })

  it("handles malformed lines gracefully", () => {
    const text = `
helioops_uptime_seconds 100
malformed line without number
helioops_pipeline_requests_total 42
also_not_valid
helioops_errors 10
`
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(3)
    expect(metrics.get("helioops_uptime_seconds")).toBe(100)
    expect(metrics.get("helioops_pipeline_requests_total")).toBe(42)
    expect(metrics.get("helioops_errors")).toBe(10)
  })

  it("handles lines with extra whitespace", () => {
    const text = "  helioops_uptime_seconds   3600.50  "
    const metrics = parseMetrics(text)
    expect(metrics.get("helioops_uptime_seconds")).toBe(3600.5)
  })

  it("handles non-numeric values", () => {
    const text = "helioops_status not_a_number"
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(0)
  })

  it("handles NaN values", () => {
    const text = "helioops_value NaN"
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(0)
  })

  it("handles Infinity values", () => {
    const text = "helioops_value Infinity"
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(0)
  })

  it("handles negative Infinity values", () => {
    const text = "helioops_value -Infinity"
    const metrics = parseMetrics(text)
    expect(metrics.size).toBe(0)
  })

  it("handles multiple metrics on same line (takes first two tokens)", () => {
    const text = "helioops_metric 123 extra_token"
    const metrics = parseMetrics(text)
    expect(metrics.get("helioops_metric")).toBe(123)
  })

  it("parses full Prometheus output from backend", () => {
    const text = `# HELP helioops_uptime_seconds Process uptime in seconds
# TYPE helioops_uptime_seconds gauge
helioops_uptime_seconds 12345.67

# HELP helioops_pipeline_requests_total Total pipeline requests
# TYPE helioops_pipeline_requests_total counter
helioops_pipeline_requests_total 15

# HELP helioops_pipeline_errors_total Total pipeline errors
# TYPE helioops_pipeline_errors_total counter
helioops_pipeline_errors_total 2

# HELP helioops_pipeline_duration_seconds_avg Average pipeline duration
# TYPE helioops_pipeline_duration_seconds_avg gauge
helioops_pipeline_duration_seconds_avg 12.3456

# HELP helioops_pipeline_duration_seconds_p99 P99 pipeline duration
# TYPE helioops_pipeline_duration_seconds_p99 gauge
helioops_pipeline_duration_seconds_p99 25.7890

# HELP helioops_detection_requests_total Total detection requests
# TYPE helioops_detection_requests_total counter
helioops_detection_requests_total 10

# HELP helioops_advisory_requests_total Total advisory requests
# TYPE helioops_advisory_requests_total counter
helioops_advisory_requests_total 8

# HELP helioops_ws_connections_total Total WebSocket connections
# TYPE helioops_ws_connections_total counter
helioops_ws_connections_total 3`
    const metrics = parseMetrics(text)
    expect(metrics.get("helioops_uptime_seconds")).toBe(12345.67)
    expect(metrics.get("helioops_pipeline_requests_total")).toBe(15)
    expect(metrics.get("helioops_pipeline_errors_total")).toBe(2)
    expect(metrics.get("helioops_pipeline_duration_seconds_avg")).toBe(12.3456)
    expect(metrics.get("helioops_pipeline_duration_seconds_p99")).toBe(25.789)
    expect(metrics.get("helioops_detection_requests_total")).toBe(10)
    expect(metrics.get("helioops_advisory_requests_total")).toBe(8)
    expect(metrics.get("helioops_ws_connections_total")).toBe(3)
  })
})
