/**
 * HelioOps WebSocket Client
 *
 * Real-time pipeline event streaming.
 * Features:
 * - Automatic reconnection with exponential backoff
 * - Event listener pattern for decoupled subscribers
 * - Type-safe event handling
 * - Malformed message resilience
 */

import type { WsEvent } from "@/types/storm"

/**
 * Internal state of WebSocket connection
 */
enum ConnectionState {
  DISCONNECTED = "DISCONNECTED",
  CONNECTING = "CONNECTING",
  CONNECTED = "CONNECTED",
}

/**
 * Type for event listener callback
 */
export type WsEventListener = (event: WsEvent) => void

/**
 * Type-safe WebSocket client with automatic reconnection.
 *
 * Usage:
 *   wsClient.connect()
 *   const unsubscribe = wsClient.subscribe((event) => {
 *     console.log("Event:", event)
 *   })
 *   wsClient.send({ action: "run_pipeline", storm_id: "2024-10-G4" })
 *   // Later:
 *   unsubscribe()
 *   wsClient.disconnect()
 */
export class WsClient {
  private ws: WebSocket | null = null
  private listeners: Set<WsEventListener> = new Set()
  private state: ConnectionState = ConnectionState.DISCONNECTED
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000 // Start with 1 second
  private maxDelay = 30000 // Cap at 30 seconds
  private url: string

  constructor() {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    // Convert http[s] to ws[s]
    this.url = baseUrl.replace(/^https?:/, (match) =>
      match === "https:" ? "wss:" : "ws:",
    ) + "/ws/stream"
  }

  /**
   * Connect to the WebSocket server.
   * Safe to call multiple times — if already connected, returns immediately.
   */
  public connect(): void {
    if (this.state === ConnectionState.CONNECTING || this.state === ConnectionState.CONNECTED) {
      return
    }

    this.state = ConnectionState.CONNECTING

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this.state = ConnectionState.CONNECTED
        this.reconnectDelay = 1000 // Reset backoff on successful connection
      }

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data)
      }

      this.ws.onclose = () => {
        this.state = ConnectionState.DISCONNECTED
        this.scheduleReconnect()
      }

      this.ws.onerror = () => {
        this.state = ConnectionState.DISCONNECTED
        // Close will trigger onclose, which triggers reconnect
        this.ws?.close()
      }
    } catch (err) {
      this.state = ConnectionState.DISCONNECTED
      this.scheduleReconnect()
    }
  }

  /**
   * Disconnect and stop reconnection attempts.
   */
  public disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.state = ConnectionState.DISCONNECTED
  }

  /**
   * Send a message to the server.
   * Must be connected or will throw an error.
   *
   * @throws {Error} If not connected
   */
  public send(data: { action: string; storm_id: string }): void {
    if (this.state !== ConnectionState.CONNECTED || !this.ws) {
      throw new Error("WebSocket not connected")
    }
    this.ws.send(JSON.stringify(data))
  }

  /**
   * Subscribe to WebSocket events.
   * Returns an unsubscribe function.
   *
   * @param callback - Function to call on each event
   * @returns Function to unsubscribe
   */
  public subscribe(callback: WsEventListener): () => void {
    this.listeners.add(callback)
    return () => {
      this.listeners.delete(callback)
    }
  }

  /**
   * Check if currently connected.
   */
  public isConnected(): boolean {
    return this.state === ConnectionState.CONNECTED
  }

  /**
   * Get the current connection state.
   */
  public getState(): string {
    return this.state
  }

  /**
   * Handle incoming message from server.
   * Silently ignores malformed JSON.
   * @private
   */
  private handleMessage(data: string): void {
    try {
      const event = JSON.parse(data) as WsEvent
      this.listeners.forEach((listener) => {
        try {
          listener(event)
        } catch (err) {
          // Silently ignore listener errors
          console.error("Listener error:", err)
        }
      })
    } catch {
      // Silently ignore malformed JSON
      console.warn("Malformed WebSocket message:", data)
    }
  }

  /**
   * Schedule a reconnection attempt with exponential backoff.
   * @private
   */
  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return
    }

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
      this.connect()
    }, this.reconnectDelay)
  }
}

/**
 * Singleton instance of the WebSocket client.
 * Use this throughout the app for real-time events.
 */
export const wsClient = new WsClient()
