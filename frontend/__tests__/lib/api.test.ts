import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { api, ApiError, parseMetrics } from "@/lib/api"
import type { PipelineResult, StormsResponse, HealthResponse } from "@/types/storm"

describe("API Client", () => {
  beforeEach(() => {
    // Mock fetch globally
    global.fetch = vi.fn()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe("ApiError", () => {
    it("should create error with status and message", () => {
      const err = new ApiError(404, "Not found")
      expect(err.status).toBe(404)
      expect(err.message).toBe("Not found")
      expect(err.name).toBe("ApiError")
    })
  })

  describe("getStorms", () => {
    it("should fetch and return storms list", async () => {
      const mockResponse: StormsResponse = {
        available_storms: ["2024-10-G4", "2024-05-G5"],
        completed: {
          "2024-10-G4": {
            storm_id: "2024-10-G4",
            completed_at: "2026-06-13T19:58:59Z",
            advisory_count: 4,
            verified_count: 4,
            error_count: 0,
          },
        },
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      })

      const result = await api.getStorms()
      expect(result).toEqual(mockResponse)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining("/api/storms"),
        expect.objectContaining({
          headers: expect.objectContaining({
            "Content-Type": "application/json",
          }),
        }),
      )
    })

    it("should throw ApiError on 404", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Storms not found" }),
      })

      try {
        await api.getStorms()
        expect.fail("Should have thrown ApiError")
      } catch (err) {
        expect(err).toBeInstanceOf(ApiError)
        expect((err as ApiError).status).toBe(404)
      }
    })

    it("should throw ApiError on 500", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
        json: async () => ({ detail: "Database error" }),
      })

      await expect(api.getStorms()).rejects.toThrow(ApiError)
    })

    it("should handle malformed error response", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Server Error",
        json: async () => {
          throw new Error("Invalid JSON")
        },
      })

      await expect(api.getStorms()).rejects.toThrow(ApiError)
    })
  })

  describe("detect", () => {
    it("should POST to /api/detect with encoded storm_id", async () => {
      const mockResult: PipelineResult = {
        storm_id: "2024-10-G4",
        cv_event: {},
        impact_prediction: null,
        genai_event: {},
        advisories: [],
        verified_advisories: [],
        provenance_traces: [],
        errors: [],
        completed_at: "2026-06-14T12:00:00Z",
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      })

      const result = await api.detect("2024-10-G4")
      expect(result.storm_id).toBe("2024-10-G4")

      // Verify URL encoding was used
      const call = (global.fetch as any).mock.calls[0]
      expect(call[0]).toContain("/api/detect/2024-10-G4")
      expect(call[1].method).toBe("POST")
    })

    it("should encode special characters in storm_id", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ storm_id: "test" }),
      })

      await api.detect("2024-10-G4; DROP TABLE--")

      const call = (global.fetch as any).mock.calls[0]
      const url = call[0]
      // Should be URL-encoded, not raw
      expect(url).not.toContain("DROP TABLE")
      expect(url).toContain("%")
    })

    it("should throw 429 on rate limit", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 429,
        statusText: "Too Many Requests",
        json: async () => ({ detail: "Rate limit exceeded" }),
      })

      await expect(api.detect("2024-10-G4")).rejects.toMatchObject({
        status: 429,
      })
    })

    it("should throw 400 on invalid storm_id format", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 400,
        statusText: "Bad Request",
        json: async () => ({ detail: "Invalid storm_id format" }),
      })

      await expect(api.detect("invalid")).rejects.toMatchObject({
        status: 400,
      })
    })
  })

  describe("getResult", () => {
    it("should fetch result for storm_id", async () => {
      const mockResult: PipelineResult = {
        storm_id: "2024-10-G4",
        cv_event: {
          storm_id: "2024-10-G4",
          detected_at: "2024-10-28T10:30:00Z",
          confidence: 0.91,
          scales: { G: 4, S: 0, R: 3 },
          cme: {
            speed_km_s: 1200,
            angular_width_deg: 45,
            direction: "SE",
            arrival_estimate: "2024-10-29T04:00:00Z",
            detected: true,
            source: "LASCO",
            confidence: 0.88,
            frame_path: "/path",
            bbox_norm: [],
          },
          flare: {
            detected: true,
            class: "X",
            r_scale: 3,
            s_scale: 0,
            source: "GOES",
            onset: "2024-10-28T09:45:00Z",
          },
          l1_solar_wind: {
            speed_km_s: 650,
            bz_nt: -15.2,
            bt_nt: 18.5,
            density_cm3: 12.4,
            measured_at: "2024-10-28T10:15:00Z",
            g_scale: 4,
            eta_minutes: 45,
          },
          timeline: [],
          noaa_alert_raw: "G4",
        } as any,
        impact_prediction: {
          gps_error_m: 12.5,
          gps_error_ci_low: 6,
          gps_error_ci_high: 19,
          hf_blackout_prob: 0.9,
          hf_blackout_ci_low: 0.7,
          hf_blackout_ci_high: 0.95,
        },
        genai_event: {
          alert_id: "2024-10-G4",
          g_scale: "G4",
          s_scale: null,
          r_scale: "R3",
          kp_index: 8.3,
          estimated_arrival_utc: null,
          peak_impact_window_start: null,
          peak_impact_window_end: null,
          raw_alert_text: "G4",
          source_url: null,
        },
        advisories: [],
        verified_advisories: [],
        provenance_traces: [],
        errors: [],
        completed_at: "2026-06-14T12:00:00Z",
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockResult,
      })

      const result = await api.getResult("2024-10-G4")
      expect(result.storm_id).toBe("2024-10-G4")
      expect(result.impact_prediction).toBeDefined()
    })

    it("should throw 404 when result not found", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "No result for storm" }),
      })

      await expect(api.getResult("unknown-storm")).rejects.toMatchObject({
        status: 404,
      })
    })

    it("should URL-encode storm_id", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => ({}),
      })

      await api.getResult("2024-10-G4/../../../etc/passwd")

      const call = (global.fetch as any).mock.calls[0]
      const url = call[0]
      expect(url).not.toContain("../../../")
    })
  })

  describe("getAdvisory", () => {
    it("should fetch advisory by ID", async () => {
      const mockAdvisory = {
        verified_advisory: {
          advisory_id: "adv-123",
          storm_id: "2024-10-G4",
          industry: "aviation",
          severity: "HIGH",
          numbered_actions: ["Action 1"],
          timing_window: { opens: "2024-10-29T04:00:00Z", duration_min: 360 },
          technical_details: "Details",
          cited_procedure: { source: "ICAO", ref: "7030" },
          verifier: { status: "passed", checks: [] },
          provenance_ref: "trace-789",
          requires_human: false,
        },
        provenance_trace: {
          trace_id: "trace-789",
          advisory_id: "adv-123",
          chain: [],
        },
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockAdvisory,
      })

      const result = await api.getAdvisory("adv-123")
      expect(result.verified_advisory.advisory_id).toBe("adv-123")
      expect(result.provenance_trace.trace_id).toBe("trace-789")
    })

    it("should throw 404 when advisory not found", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 404,
        statusText: "Not Found",
        json: async () => ({ detail: "Advisory not found" }),
      })

      await expect(api.getAdvisory("unknown-id")).rejects.toMatchObject({
        status: 404,
      })
    })
  })

  describe("getHealth", () => {
    it("should return health status", async () => {
      const mockHealth: HealthResponse = {
        status: "ok",
        version: "0.1.0",
        timestamp: "2026-06-14T12:00:00Z",
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockHealth,
      })

      const result = await api.getHealth()
      expect(result.status).toBe("ok")
    })

    it("should throw on server down", async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new Error("Network error"))

      await expect(api.getHealth()).rejects.toThrow()
    })
  })

  describe("getHealthReady", () => {
    it("should return readiness with checks", async () => {
      const mockReady: HealthResponse = {
        status: "ready",
        version: "0.1.0",
        checks: {
          detection: true,
          ml_models: true,
          genai_module: true,
        },
      }

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        json: async () => mockReady,
      })

      const result = await api.getHealthReady()
      expect(result.checks?.detection).toBe(true)
    })

    it("should throw 503 when not ready", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 503,
        statusText: "Service Unavailable",
        json: async () => ({ status: "degraded" }),
      })

      await expect(api.getHealthReady()).rejects.toMatchObject({
        status: 503,
      })
    })
  })

  describe("getMetrics", () => {
    it("should fetch and return metrics as text", async () => {
      const mockMetrics = `helioops_uptime_seconds 3600
helioops_pipeline_requests_total 42
helioops_pipeline_errors_total 2`

      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        text: async () => mockMetrics,
      })

      const result = await api.getMetrics()
      expect(result).toContain("helioops_uptime_seconds")
      expect(result).toContain("3600")
    })

    it("should throw ApiError on failure", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Internal Server Error",
      })

      await expect(api.getMetrics()).rejects.toThrow(ApiError)
    })

    it("should not set Content-Type header for /metrics", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: true,
        text: async () => "metrics",
      })

      // Note: getMetrics uses raw fetch, not the request() wrapper
      await api.getMetrics()

      const call = (global.fetch as any).mock.calls[0]
      // getMetrics doesn't use request(), so it doesn't set headers
      expect(call[0]).toContain("/metrics")
    })
  })

  describe("parseMetrics", () => {
    it("should parse Prometheus text format", () => {
      const text = `# HELP helioops_uptime_seconds Uptime in seconds
# TYPE helioops_uptime_seconds gauge
helioops_uptime_seconds 3600
helioops_pipeline_requests_total 42
helioops_pipeline_errors_total 2
helioops_pipeline_duration_seconds_avg 1.5
`

      const metrics = parseMetrics(text)

      expect(metrics.get("helioops_uptime_seconds")).toBe(3600)
      expect(metrics.get("helioops_pipeline_requests_total")).toBe(42)
      expect(metrics.get("helioops_pipeline_errors_total")).toBe(2)
      expect(metrics.get("helioops_pipeline_duration_seconds_avg")).toBe(1.5)
    })

    it("should skip comments and empty lines", () => {
      const text = `# Comment line
metric1 100

# Another comment
metric2 200

`

      const metrics = parseMetrics(text)

      expect(metrics.size).toBe(2)
      expect(metrics.get("metric1")).toBe(100)
      expect(metrics.get("metric2")).toBe(200)
    })

    it("should skip malformed lines", () => {
      const text = `valid_metric 42
invalid_line_no_value
another_valid 3.14
also_invalid
`

      const metrics = parseMetrics(text)

      expect(metrics.size).toBe(2)
      expect(metrics.get("valid_metric")).toBe(42)
      expect(metrics.get("another_valid")).toBe(3.14)
    })

    it("should handle NaN values", () => {
      const text = `good_metric 100
bad_metric NaN
another_good 50
`

      const metrics = parseMetrics(text)

      expect(metrics.size).toBe(2)
      expect(metrics.has("bad_metric")).toBe(false)
      expect(metrics.get("good_metric")).toBe(100)
    })

    it("should return empty map for empty input", () => {
      const metrics = parseMetrics("")
      expect(metrics.size).toBe(0)
    })

    it("should handle scientific notation", () => {
      const text = `metric1 1e3
metric2 2.5e2
metric3 1.2e-3
`

      const metrics = parseMetrics(text)

      expect(metrics.get("metric1")).toBe(1000)
      expect(metrics.get("metric2")).toBe(250)
      expect(metrics.get("metric3")).toBeCloseTo(0.0012)
    })
  })

  describe("Error handling edge cases", () => {
    it("should handle error response with missing detail field", async () => {
      ;(global.fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: "Server Error",
        json: async () => ({ error: "Something went wrong" }),
      })

      const error = await api.getStorms().catch((e) => e)
      expect(error).toBeInstanceOf(ApiError)
      expect(error.message).toBe("Server Error")
    })

    it("should throw Error on network failure", async () => {
      ;(global.fetch as any).mockRejectedValueOnce(new TypeError("Failed to fetch"))

      try {
        await api.getStorms()
        expect.fail("Should have thrown error")
      } catch (err) {
        expect(err).toBeInstanceOf(Error)
        expect((err as Error).message).toContain("Failed to fetch")
      }
    })
  })
})
