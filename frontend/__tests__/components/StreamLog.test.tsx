import { describe, it, expect } from "vitest"
import { render, screen, fireEvent } from "@testing-library/react"
import StreamLog from "@/components/dashboard/StreamLog"
import type { WsEvent } from "@/types/storm"

const stageEvent: WsEvent = {
  event: "pipeline.stage",
  stage: "detection",
  status: "started",
  timestamp: "2024-10-11T20:00:00Z",
}

const advisoryEvent: WsEvent = {
  event: "advisory.generated",
  industry: "aviation",
  timestamp: "2024-10-11T20:01:00Z",
}

const verifierEvent: WsEvent = {
  event: "verifier.check",
  advisory_id: "adv-1",
  field: "severity",
  status: "pass",
  timestamp: "2024-10-11T20:02:00Z",
}

const errorEvent: WsEvent = {
  event: "pipeline.error",
  stage: "adaptation",
  error: "Timeout",
  timestamp: "2024-10-11T20:03:00Z",
}

const completeEvent: WsEvent = {
  event: "pipeline.complete",
  storm_id: "2024-10-G4",
  total_advisories: 2,
  total_verified: 1,
  errors: [],
  timestamp: "2024-10-11T20:04:00Z",
}

describe("StreamLog", () => {
  it("shows waiting message when no events", () => {
    render(<StreamLog events={[]} />)
    expect(screen.getByText("Waiting for pipeline events...")).toBeInTheDocument()
  })

  it("renders event labels", () => {
    render(<StreamLog events={[stageEvent, advisoryEvent]} />)
    expect(screen.getByText(/detection — started/)).toBeInTheDocument()
    expect(screen.getByText(/Advisory generated — aviation/)).toBeInTheDocument()
  })

  it("renders error events", () => {
    render(<StreamLog events={[errorEvent]} />)
    expect(screen.getByText(/Error in adaptation: Timeout/)).toBeInTheDocument()
  })

  it("renders complete events", () => {
    render(<StreamLog events={[completeEvent]} />)
    expect(
      screen.getByText(/Pipeline complete — 2 advisories, 1 verified/)
    ).toBeInTheDocument()
  })

  it("filter buttons are present", () => {
    render(<StreamLog events={[]} />)
    expect(screen.getByText("stage")).toBeInTheDocument()
    expect(screen.getByText("advisory")).toBeInTheDocument()
    expect(screen.getByText("verifier")).toBeInTheDocument()
    expect(screen.getByText("error")).toBeInTheDocument()
    expect(screen.getByText("complete")).toBeInTheDocument()
  })

  it("clicking filter shows only matching events", () => {
    render(
      <StreamLog events={[stageEvent, advisoryEvent, errorEvent, verifierEvent]} />
    )

    fireEvent.click(screen.getByText("error"))

    expect(screen.getByText(/Error in adaptation: Timeout/)).toBeInTheDocument()
    expect(screen.queryByText(/detection — started/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Advisory generated/)).not.toBeInTheDocument()
  })

  it("clicking filter again clears the filter", () => {
    render(<StreamLog events={[stageEvent, advisoryEvent]} />)

    fireEvent.click(screen.getByText("stage"))
    fireEvent.click(screen.getByText("stage"))

    expect(screen.getByText(/detection — started/)).toBeInTheDocument()
    expect(screen.getByText(/Advisory generated/)).toBeInTheDocument()
  })

  it("shows no match message when filter matches nothing", () => {
    render(<StreamLog events={[stageEvent]} />)

    fireEvent.click(screen.getByText("advisory"))

    expect(screen.getByText("No events match this filter.")).toBeInTheDocument()
  })

  it("formats timestamps", () => {
    render(<StreamLog events={[stageEvent]} />)
    const timestamp = screen.getByText(/^\d{2}:\d{2}:\d{2}$/)
    expect(timestamp).toBeInTheDocument()
  })
})
