import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import ImpactDisplay from "@/components/dashboard/ImpactDisplay"
import type { ImpactPrediction } from "@/types/storm"

describe("ImpactDisplay", () => {
  const realPrediction: ImpactPrediction = {
    gps_error_m: 12.8,
    gps_error_ci_low: 6.6,
    gps_error_ci_high: 13.3,
    hf_blackout_prob: 0.9,
    hf_blackout_ci_low: 0.66,
    hf_blackout_ci_high: 0.93,
  }

  const fallbackPrediction: ImpactPrediction = {
    gps_error_m: 20.0,
    gps_error_ci_low: 15.0,
    gps_error_ci_high: 25.0,
    hf_blackout_prob: 0.85,
    hf_blackout_ci_low: 0.7,
    hf_blackout_ci_high: 0.95,
  }

  it("renders GPS error value", () => {
    render(<ImpactDisplay prediction={realPrediction} />)
    expect(screen.getByText("12.8")).toBeInTheDocument()
    expect(screen.getByText("m")).toBeInTheDocument()
  })

  it("renders HF blackout probability", () => {
    render(<ImpactDisplay prediction={realPrediction} />)
    expect(screen.getByText("90")).toBeInTheDocument()
  })

  it("renders confidence intervals", () => {
    render(<ImpactDisplay prediction={realPrediction} />)
    expect(screen.getByText("6.6–13.3 m")).toBeInTheDocument()
    expect(screen.getByText("Low: 66%")).toBeInTheDocument()
    expect(screen.getByText("High: 93%")).toBeInTheDocument()
  })

  it("shows fallback warning for conservative defaults", () => {
    render(<ImpactDisplay prediction={fallbackPrediction} />)
    expect(screen.getByText(/Conservative defaults/)).toBeInTheDocument()
  })

  it("does not show fallback warning for real predictions", () => {
    render(<ImpactDisplay prediction={realPrediction} />)
    expect(screen.queryByText(/Conservative defaults/)).not.toBeInTheDocument()
  })

  it("renders section labels", () => {
    render(<ImpactDisplay prediction={realPrediction} />)
    expect(screen.getByText("GPS L1 Error")).toBeInTheDocument()
    expect(screen.getByText("HF Blackout Probability")).toBeInTheDocument()
  })
})
