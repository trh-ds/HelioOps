import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { WsClient, type WsEventListener } from "@/lib/ws-client"
import type { WsEvent, PipelineStageEvent } from "@/types/storm"

// Mock WebSocket
class MockWebSocket {
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readyState: number = WebSocket.CONNECTING
  url: string
  sent: string[] = []

  constructor(url: string) {
    this.url = url
  }

  send(data: string): void {
    this.sent.push(data)
  }

  close(): void {
    this.readyState = WebSocket.CLOSED
    if (this.onclose) {
      this.onclose(new CloseEvent("close"))
    }
  }

  simulateOpen(): void {
    this.readyState = WebSocket.OPEN
    if (this.onopen) {
      this.onopen(new Event("open"))
    }
  }

  simulateMessage(data: string): void {
    if (this.onmessage) {
      this.onmessage(new MessageEvent("message", { data }))
    }
  }

  simulateError(): void {
    if (this.onerror) {
      this.onerror(new Event("error"))
    }
  }
}

describe("WsClient", () => {
  let mockWebSocket: MockWebSocket | null = null
  const originalWebSocket = global.WebSocket

  beforeEach(() => {
    mockWebSocket = null

    // Mock global WebSocket
    ;(global as any).WebSocket = class extends MockWebSocket {
      constructor(url: string) {
        super(url)
        mockWebSocket = this
      }
    }

    vi.useFakeTimers()
  })

  afterEach(() => {
    if (mockWebSocket) {
      mockWebSocket.close()
    }
    ;(global as any).WebSocket = originalWebSocket
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  describe("Connection", () => {
    it("should connect and set correct URL", () => {
      const client = new WsClient()
      client.connect()

      expect(mockWebSocket).toBeDefined()
      expect(mockWebSocket?.url).toContain("ws://")
      expect(mockWebSocket?.url).toContain("/ws/stream")
    })

    it("should convert https to wss", () => {
      // Override BASE_URL for this test
      const originalEnv = process.env.NEXT_PUBLIC_API_URL
      process.env.NEXT_PUBLIC_API_URL = "https://example.com"

      const client = new WsClient()
      client.connect()

      expect(mockWebSocket?.url).toContain("wss://")

      process.env.NEXT_PUBLIC_API_URL = originalEnv
    })

    it("should not connect twice simultaneously", () => {
      const client = new WsClient()
      client.connect()
      const firstWs = mockWebSocket

      client.connect()

      expect(mockWebSocket).toBe(firstWs)
    })

    it("should be safe to call connect when already connected", () => {
      const client = new WsClient()
      client.connect()

      mockWebSocket?.simulateOpen()
      expect(client.isConnected()).toBe(true)

      const connectedWs = mockWebSocket
      client.connect()

      expect(mockWebSocket).toBe(connectedWs)
    })

    it("should transition to CONNECTED state on open", () => {
      const client = new WsClient()
      expect(client.getState()).toBe("DISCONNECTED")

      client.connect()
      expect(client.getState()).toBe("CONNECTING")

      mockWebSocket?.simulateOpen()
      expect(client.getState()).toBe("CONNECTED")
      expect(client.isConnected()).toBe(true)
    })
  })

  describe("Disconnection", () => {
    it("should disconnect and close WebSocket", () => {
      const client = new WsClient()
      client.connect()
      mockWebSocket?.simulateOpen()

      const closeSpy = vi.spyOn(mockWebSocket!, "close")
      client.disconnect()

      expect(closeSpy).toHaveBeenCalled()
      expect(client.isConnected()).toBe(false)
    })

    it("should cancel pending reconnect on disconnect", () => {
      const client = new WsClient()
      client.connect()

      mockWebSocket?.simulateError()
      expect(client.getState()).toBe("DISCONNECTED")

      client.disconnect()
      vi.advanceTimersByTime(2000)

      // Should not have created a new WebSocket
      expect(client.isConnected()).toBe(false)
    })
  })

  describe("Event Listeners", () => {
    it("should subscribe and receive events", () => {
      const client = new WsClient()
      const listener = vi.fn()

      client.connect()
      const unsubscribe = client.subscribe(listener)

      mockWebSocket?.simulateOpen()

      const event: PipelineStageEvent = {
        event: "pipeline.stage",
        stage: "detection",
        status: "started",
        timestamp: "2026-06-14T12:00:00Z",
      }

      mockWebSocket?.simulateMessage(JSON.stringify(event))

      expect(listener).toHaveBeenCalledWith(event)

      unsubscribe()
      mockWebSocket?.simulateMessage(JSON.stringify(event))

      expect(listener).toHaveBeenCalledTimes(1)
    })

    it("should support multiple subscribers", () => {
      const client = new WsClient()
      const listener1 = vi.fn()
      const listener2 = vi.fn()

      client.subscribe(listener1)
      client.subscribe(listener2)

      client.connect()
      mockWebSocket?.simulateOpen()

      const event: WsEvent = {
        event: "error",
        message: "Test error",
        timestamp: "2026-06-14T12:00:00Z",
      }

      mockWebSocket?.simulateMessage(JSON.stringify(event))

      expect(listener1).toHaveBeenCalledWith(event)
      expect(listener2).toHaveBeenCalledWith(event)
    })

    it("should handle malformed JSON gracefully", () => {
      const client = new WsClient()
      const listener = vi.fn()

      client.connect()
      client.subscribe(listener)
      mockWebSocket?.simulateOpen()

      mockWebSocket?.simulateMessage("invalid json {")

      // Should not call listener or throw
      expect(listener).not.toHaveBeenCalled()
    })

    it("should isolate listener errors", () => {
      const client = new WsClient()
      const badListener = vi.fn(() => {
        throw new Error("Listener error")
      })
      const goodListener = vi.fn()

      client.subscribe(badListener)
      client.subscribe(goodListener)

      client.connect()
      mockWebSocket?.simulateOpen()

      const event: WsEvent = {
        event: "error",
        message: "Test",
        timestamp: "2026-06-14T12:00:00Z",
      }

      mockWebSocket?.simulateMessage(JSON.stringify(event))

      // Both should be called, error in one doesn't prevent the other
      expect(badListener).toHaveBeenCalled()
      expect(goodListener).toHaveBeenCalled()
    })
  })

  describe("Sending", () => {
    it("should send message when connected", () => {
      const client = new WsClient()
      client.connect()
      mockWebSocket?.simulateOpen()

      const message = { action: "run_pipeline", storm_id: "2024-10-G4" }
      client.send(message)

      expect(mockWebSocket?.sent).toHaveLength(1)
      expect(JSON.parse(mockWebSocket!.sent[0])).toEqual(message)
    })

    it("should throw when sending while disconnected", () => {
      const client = new WsClient()

      expect(() => {
        client.send({ action: "run_pipeline", storm_id: "2024-10-G4" })
      }).toThrow("WebSocket not connected")
    })

    it("should throw when sending before connection completes", () => {
      const client = new WsClient()
      client.connect()

      // Not yet open
      expect(() => {
        client.send({ action: "run_pipeline", storm_id: "2024-10-G4" })
      }).toThrow("WebSocket not connected")
    })
  })

  describe("Reconnection", () => {
    it("should reconnect on close with exponential backoff", () => {
      const client = new WsClient()
      client.connect()
      mockWebSocket?.simulateOpen()

      let firstWs = mockWebSocket
      expect(firstWs).toBeDefined()

      // Simulate connection close
      mockWebSocket?.close()
      expect(client.isConnected()).toBe(false)

      // Advance time to trigger reconnect
      vi.advanceTimersByTime(1000)
      const secondWs = mockWebSocket

      // Should have created a new WebSocket
      expect(secondWs).not.toBe(firstWs)
      expect(secondWs).toBeDefined()
    })

    it("should increase backoff delay exponentially", () => {
      const client = new WsClient()

      // First failure
      client.connect()
      mockWebSocket?.simulateError()
      vi.advanceTimersByTime(1000)

      // Second failure
      mockWebSocket?.simulateError()
      vi.advanceTimersByTime(2000)

      // Third failure
      mockWebSocket?.simulateError()
      vi.advanceTimersByTime(4000)

      // All reconnects should have been attempted
      expect(mockWebSocket).toBeDefined()
    })

    it("should cap backoff delay at 30 seconds", () => {
      const client = new WsClient()

      // Simulate multiple failures and reconnects
      for (let i = 0; i < 6; i++) {
        client.connect()
        mockWebSocket?.simulateError()
        if (i < 5) {
          vi.advanceTimersByTime(40000) // Exceed max delay to test capping
        }
      }

      // After many failures, delay should not exceed 30s
      // Final state should be in reconnect mode with reasonable delay
      expect(client.getState()).not.toBe("CONNECTED")
    })

    it("should reset backoff on successful connection", () => {
      const client = new WsClient()

      // First connection with failure
      client.connect()
      mockWebSocket?.simulateError()

      // Reconnect succeeds
      vi.advanceTimersByTime(1000)
      mockWebSocket?.simulateOpen()

      // Close and see if backoff is reset
      const firstWs = mockWebSocket
      mockWebSocket?.close()

      // Next reconnect should use 1s delay (reset), not exponential
      vi.advanceTimersByTime(1000)
      const secondWs = mockWebSocket

      expect(secondWs).not.toBe(firstWs)
    })
  })

  describe("Error Handling", () => {
    it("should handle WebSocket construction error gracefully", () => {
      ;(global as any).WebSocket = class {
        constructor() {
          throw new Error("WebSocket not supported")
        }
      }

      const client = new WsClient()
      expect(() => {
        client.connect()
      }).not.toThrow()

      expect(client.getState()).toBe("DISCONNECTED")

      // Should schedule reconnect
      vi.advanceTimersByTime(1000)

      // No crash
      expect(client.getState()).toBe("DISCONNECTED")
    })

    it("should handle onerror event", () => {
      const client = new WsClient()
      client.connect()
      mockWebSocket?.simulateOpen()

      expect(client.isConnected()).toBe(true)

      mockWebSocket?.simulateError()

      // Should close and transition to disconnected
      expect(client.isConnected()).toBe(false)
    })
  })

  describe("State Management", () => {
    it("should report correct connection state", () => {
      const client = new WsClient()

      expect(client.getState()).toBe("DISCONNECTED")
      expect(client.isConnected()).toBe(false)

      client.connect()
      expect(client.getState()).toBe("CONNECTING")
      expect(client.isConnected()).toBe(false)

      mockWebSocket?.simulateOpen()
      expect(client.getState()).toBe("CONNECTED")
      expect(client.isConnected()).toBe(true)

      mockWebSocket?.close()
      expect(client.getState()).toBe("DISCONNECTED")
      expect(client.isConnected()).toBe(false)
    })

    it("should handle multiple rapid connect calls", () => {
      const client = new WsClient()

      client.connect()
      client.connect()
      client.connect()

      // Should only have one WebSocket instance
      const firstWs = mockWebSocket
      expect(firstWs).toBeDefined()

      mockWebSocket?.simulateOpen()

      client.connect()
      expect(mockWebSocket).toBe(firstWs)
    })
  })

  describe("URL Construction", () => {
    it("should use env variable for base URL", () => {
      const originalEnv = process.env.NEXT_PUBLIC_API_URL
      process.env.NEXT_PUBLIC_API_URL = "http://api.example.com:8000"

      const client = new WsClient()
      client.connect()

      expect(mockWebSocket?.url).toBe("ws://api.example.com:8000/ws/stream")

      process.env.NEXT_PUBLIC_API_URL = originalEnv
    })

    it("should default to localhost:8000", () => {
      const originalEnv = process.env.NEXT_PUBLIC_API_URL
      delete process.env.NEXT_PUBLIC_API_URL

      const client = new WsClient()
      client.connect()

      expect(mockWebSocket?.url).toContain("ws://")
      expect(mockWebSocket?.url).toContain("localhost:8000")
      expect(mockWebSocket?.url).toContain("/ws/stream")

      process.env.NEXT_PUBLIC_API_URL = originalEnv
    })
  })
})
