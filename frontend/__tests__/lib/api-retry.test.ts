import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { api, ApiError } from "@/lib/api"

const originalFetch = global.fetch

describe("API retry logic", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    global.fetch = originalFetch
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it("retries on 5xx and succeeds on second attempt", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      if (callCount === 1) {
        return { ok: false, status: 500, statusText: "Internal Server Error", json: async () => ({}) }
      }
      return { ok: true, status: 200, json: async () => ({ status: "ok" }) }
    })

    const result = await api.getHealth()
    expect(result).toEqual({ status: "ok" })
    expect(callCount).toBe(2)
  })

  it("does not retry on 4xx errors", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      return { ok: false, status: 404, statusText: "Not Found", json: async () => ({ detail: "Not found" }) }
    })

    await expect(api.getResult("2024-10-G4")).rejects.toThrow(ApiError)
    expect(callCount).toBe(1)
  })

  it("retries on network error and succeeds", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      if (callCount === 1) {
        throw new TypeError("Failed to fetch")
      }
      return { ok: true, status: 200, json: async () => ({ status: "ok" }) }
    })

    const result = await api.getHealth()
    expect(result).toEqual({ status: "ok" })
    expect(callCount).toBe(2)
  })

  it("fails after exhausting retries on persistent 5xx", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      return { ok: false, status: 503, statusText: "Service Unavailable", json: async () => ({ detail: "Down" }) }
    })

    await expect(api.getHealth()).rejects.toThrow(ApiError)
    expect(callCount).toBe(2) // initial + 1 retry
  })

  it("fails after exhausting retries on persistent network error", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      throw new TypeError("Failed to fetch")
    })

    await expect(api.getHealth()).rejects.toThrow("Failed to fetch")
    expect(callCount).toBe(2)
  })

  it("succeeds on first attempt without retry", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      return { ok: true, status: 200, json: async () => ({ status: "ok" }) }
    })

    const result = await api.getHealth()
    expect(result).toEqual({ status: "ok" })
    expect(callCount).toBe(1)
  })

  it("retries getMetrics on 5xx", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      if (callCount === 1) {
        return { ok: false, status: 500, statusText: "Internal Server Error", text: async () => "" }
      }
      return { ok: true, status: 200, text: async () => "helioops_uptime_seconds 100" }
    })

    const result = await api.getMetrics()
    expect(result).toBe("helioops_uptime_seconds 100")
    expect(callCount).toBe(2)
  })

  it("does not retry getMetrics on 4xx", async () => {
    let callCount = 0
    global.fetch = vi.fn().mockImplementation(async () => {
      callCount++
      return { ok: false, status: 403, statusText: "Forbidden" }
    })

    await expect(api.getMetrics()).rejects.toThrow(ApiError)
    expect(callCount).toBe(1)
  })
})
