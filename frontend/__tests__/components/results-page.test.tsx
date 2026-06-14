import { describe, it, expect, vi, beforeEach, afterEach } from "vitest"
import { render, screen, waitFor } from "@testing-library/react"
import ResultsPage from "@/app/dashboard/results/[stormId]/page"
import { ApiError } from "@/lib/api"

vi.mock("next/navigation", () => ({
  useParams: () => ({ stormId: "2024-10-G4" }),
  usePathname: () => "/dashboard/results/2024-10-G4",
}))

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: any) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const mockGetResult = vi.fn()
vi.mock("@/lib/api", () => ({
  api: {
    getResult: (id: string) => mockGetResult(id),
  },
  ApiError: class ApiError extends Error {
    status: number
    constructor(status: number, message: string) {
      super(message)
      this.status = status
    }
  },
}))

const fullResult = {
  storm_id: "2024-10-G4",
  cv_event: {
    storm_id: "2024-10-G4",
    detected_at: "2024-10-11T18:00:00Z",
    confidence: 0.92,
    scales: { G: 4, S: 2, R: 3 },
    cme: {
      speed_km_s: 1200,
      angular_width_deg: 360,
      direction: "Earth-directed",
      arrival_estimate: "2024-10-12T06:00:00Z",
      detected: true,
      source: "SOHO LASCO",
      confidence: 0.88,
      frame_path: "/frames/cme.png",
      bbox_norm: [0.1, 0.2, 0.8, 0.9],
    },
    flare: {
      detected: true,
      class: "X2.1",
      r_scale: 3,
      s_scale: 2,
      source: "GOES XRS",
      onset: "2024-10-11T17:45:00Z",
    },
    l1_solar_wind: {
      speed_km_s: 650,
      bz_nt: -12.5,
      bt_nt: 15.2,
      density_cm3: 8.3,
      measured_at: "2024-10-11T19:30:00Z",
      g_scale: 4,
      eta_minutes: 45,
    },
    timeline: [],
    noaa_alert_raw: "ALERT: G4 storm",
  },
  impact_prediction: {
    gps_error_m: 12.8,
    gps_error_ci_low: 6.6,
    gps_error_ci_high: 13.3,
    hf_blackout_prob: 0.9,
    hf_blackout_ci_low: 0.66,
    hf_blackout_ci_high: 0.93,
  },
  genai_event: {},
  advisories: [
    {
      advisory_id: "adv-001",
      storm_event_id: "2024-10-G4",
      industry: "aviation",
      severity: "HIGH",
      confidence_score: 0.87,
      summary: "HF radio blackouts expected.",
      action_items: [],
      estimated_impact_window: "2024-10-11T22:00Z to 2024-10-12T04:00Z",
      sources_cited: ["NOAA SWPC"],
      validation_passed: true,
      generated_at: "2024-10-11T20:00:00Z",
      model_used: "gpt-4o-mini",
      safety_flags: [],
      generation_errors: [],
    },
  ],
  verified_advisories: [
    {
      advisory_id: "vadv-001",
      storm_id: "2024-10-G4",
      industry: "aviation",
      severity: "HIGH",
      numbered_actions: ["Notify pilots"],
      timing_window: { opens: "2024-10-11T22:00:00Z", duration_min: 360 },
      technical_details: "Solar wind elevated.",
      cited_procedure: { source: "ICAO", ref: "Annex 3" },
      verifier: { status: "passed", checks: [] },
      provenance_ref: "prov-abc",
      requires_human: false,
    },
  ],
  provenance_traces: [
    {
      trace_id: "trace-001",
      advisory_id: "adv-001",
      chain: [
        { step: "raw_data", ref: "nws-123", confidence: 0.95, ci_level: 0.95 },
        { step: "detection", ref: "cv-1", confidence: 0.88, ci_level: null },
        { step: "impact", ref: "ml-1", confidence: 0.72, ci_level: null },
        { step: "retrieval", ref: "rag-1", confidence: 0.81, ci_level: null },
        { step: "verifier", ref: "ver-1", confidence: 0.93, ci_level: null },
        { step: "output", ref: "out-1", confidence: 0.85, ci_level: null },
      ],
    },
  ],
  errors: [],
  completed_at: "2024-10-11T20:30:00Z",
}

describe("ResultsPage", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it("shows loading state", () => {
    mockGetResult.mockReturnValue(new Promise(() => {}))
    render(<ResultsPage />)
    expect(screen.getByText("Loading results...")).toBeInTheDocument()
  })

  it("renders impact prediction section", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Impact Prediction")).toBeInTheDocument()
    })
  })

  it("renders advisories section", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Advisories (1)")).toBeInTheDocument()
      expect(screen.getByText("HF radio blackouts expected.")).toBeInTheDocument()
    })
  })

  it("renders verified advisories section", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText(/Verified Advisories/)).toBeInTheDocument()
      expect(screen.getByText("Notify pilots")).toBeInTheDocument()
    })
  })

  it("renders provenance traces section", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText(/Provenance Traces/)).toBeInTheDocument()
      expect(screen.getByText("trace-001")).toBeInTheDocument()
    })
  })

  it("renders empty state when no result", async () => {
    mockGetResult.mockRejectedValue(new (ApiError as any)(404, "Not found"))
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText(/No results available/)).toBeInTheDocument()
    })
  })

  it("renders error state", async () => {
    mockGetResult.mockRejectedValue(new (ApiError as any)(500, "Network error"))
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument()
    })
  })

  it("renders page heading with storm id", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Results: 2024-10-G4")).toBeInTheDocument()
    })
  })

  it("renders back link", async () => {
    mockGetResult.mockResolvedValue(fullResult)
    render(<ResultsPage />)
    await waitFor(() => {
      const link = screen.getByText("Back to storms")
      expect(link).toHaveAttribute("href", "/dashboard/storms")
    })
  })

  it("renders correctly with empty advisories", async () => {
    const result = { ...fullResult, advisories: [], verified_advisories: [] }
    mockGetResult.mockResolvedValue(result)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Results: 2024-10-G4")).toBeInTheDocument()
    })
    expect(screen.queryByText(/Advisories/)).not.toBeInTheDocument()
  })

  it("renders null impact_prediction gracefully", async () => {
    const result = { ...fullResult, impact_prediction: null }
    mockGetResult.mockResolvedValue(result)
    render(<ResultsPage />)
    await waitFor(() => {
      expect(screen.getByText("Results: 2024-10-G4")).toBeInTheDocument()
    })
    expect(screen.queryByText("Impact Prediction")).not.toBeInTheDocument()
  })
})
