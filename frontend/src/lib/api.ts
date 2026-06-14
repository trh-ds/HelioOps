/**
 * HelioOps API Client
 *
 * Typed wrapper around the FastAPI backend.
 * Security: All path parameters are URL-encoded to prevent injection.
 *           No secrets in code — BASE_URL from environment only.
 *           Errors are logged without leaking server stack traces.
 */

import type {
  PipelineResult,
  StormsResponse,
  AdvisoryLookupResponse,
  HealthResponse,
} from "@/types/storm"

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

/**
 * Custom error class for API failures.
 * Includes HTTP status code for programmatic handling.
 */
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = "ApiError"
  }
}

/**
 * Type-safe HTTP request wrapper.
 * Handles JSON serialization, error parsing, and timeout.
 *
 * @throws {ApiError} On HTTP error (4xx, 5xx)
 * @throws {Error} On network failure or malformed JSON
 */
async function request<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${BASE_URL}${path}`

  try {
    const response = await fetch(url, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...init?.headers,
      },
    })

    if (!response.ok) {
      let message = response.statusText

      try {
        const body = await response.json()
        message = body.detail ?? body.message ?? response.statusText
      } catch {
        // Malformed error response — use status text
      }

      throw new ApiError(response.status, message)
    }

    return await response.json()
  } catch (err) {
    // Re-throw ApiError as-is, wrap other errors
    if (err instanceof ApiError) throw err
    if (err instanceof Error) throw err
    throw new Error(`Request failed: ${String(err)}`)
  }
}

/**
 * HelioOps API endpoints.
 * All methods are type-safe and throw ApiError on failure.
 */
export const api = {
  /**
   * GET /api/storms
   * List all available storms and completed pipeline results.
   */
  getStorms: async (): Promise<StormsResponse> => {
    return request<StormsResponse>("/api/storms")
  },

  /**
   * POST /api/detect/{storm_id}
   * Trigger the full 5-step pipeline for a storm.
   * This is an expensive operation — check rate limiting.
   *
   * @param storm_id - Storm identifier (format: YYYY-MM-GN, e.g., "2024-10-G4")
   * @throws {ApiError} 400 if invalid format, 404 if unknown, 429 if rate-limited, 500 on pipeline failure
   */
  detect: async (stormId: string): Promise<PipelineResult> => {
    const encoded = encodeURIComponent(stormId)
    return request<PipelineResult>(`/api/detect/${encoded}`, { method: "POST" })
  },

  /**
   * GET /api/result/{storm_id}
   * Retrieve the full pipeline result for a previously processed storm.
   *
   * @param storm_id - Storm identifier
   * @throws {ApiError} 404 if no result exists
   */
  getResult: async (stormId: string): Promise<PipelineResult> => {
    const encoded = encodeURIComponent(stormId)
    return request<PipelineResult>(`/api/result/${encoded}`)
  },

  /**
   * GET /api/advisory/{advisory_id}
   * Retrieve a single verified advisory with its provenance trace.
   *
   * @param advisory_id - Advisory identifier (UUID)
   * @throws {ApiError} 404 if not found
   */
  getAdvisory: async (advisoryId: string): Promise<AdvisoryLookupResponse> => {
    const encoded = encodeURIComponent(advisoryId)
    return request<AdvisoryLookupResponse>(`/api/advisory/${encoded}`)
  },

  /**
   * GET /health
   * Basic liveness check. Always succeeds if server is reachable.
   */
  getHealth: async (): Promise<HealthResponse> => {
    return request<HealthResponse>("/health")
  },

  /**
   * GET /health/ready
   * Readiness check. Verifies all dependencies (CV, ML, GenAI).
   * Returns 200 if ready, 503 if any dependency is down.
   */
  getHealthReady: async (): Promise<HealthResponse> => {
    return request<HealthResponse>("/health/ready")
  },

  /**
   * GET /metrics
   * Retrieve Prometheus-compatible metrics.
   * Returns plain text (text/plain), not JSON.
   *
   * @returns Raw Prometheus text format (key value pairs)
   */
  getMetrics: async (): Promise<string> => {
    const url = `${BASE_URL}/metrics`
    const response = await fetch(url)
    if (!response.ok) {
      throw new ApiError(response.status, `Metrics fetch failed: ${response.statusText}`)
    }
    return response.text()
  },
}

/**
 * Parse Prometheus text format metrics into a key-value map.
 * Filters out comments and empty lines.
 *
 * @param text - Raw Prometheus metrics text
 * @returns Map of metric name -> value
 */
export function parseMetrics(text: string): Map<string, number> {
  const metrics = new Map<string, number>()

  for (const line of text.split("\n")) {
    const trimmed = line.trim()
    // Skip comments and empty lines
    if (!trimmed || trimmed.startsWith("#")) continue

    const parts = trimmed.split(/\s+/)
    if (parts.length >= 2) {
      const key = parts[0]
      const value = parseFloat(parts[1])
      if (!isNaN(value) && isFinite(value)) {
        metrics.set(key, value)
      }
    }
  }

  return metrics
}
