import { describe, it, expect } from "vitest"
import type {
  PipelineResult,
  CvStormEvent,
  ImpactPrediction,
  GenaiStormEvent,
  AdvisoryOutput,
  VerifiedAdvisory,
  ProvenanceTrace,
  StormsResponse,
  WsEvent,
  SeverityTier,
  Industry,
  SafetyFlag,
  ActionItem,
  VerifierResult,
  VerifierCheck,
  ProvenanceStep,
} from "@/types/storm"
import {
  isPipelineStageEvent,
  isPipelineErrorEvent,
  isAdvisoryVerifiedEvent,
  isPipelineCompleteEvent,
  isWsErrorEvent,
} from "@/types/storm"

describe("Storm Types", () => {
  describe("CvStormEvent", () => {
    it("should match expected structure", () => {
      const event: CvStormEvent = {
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
          frame_path: "/path/to/frame",
          bbox_norm: [0.1, 0.2, 0.3, 0.4],
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
        timeline: [
          {
            horizon: "realtime",
            source: "DONKI",
            t: "2024-10-28T10:30:00Z",
          },
        ],
        noaa_alert_raw: "Space Weather Alert: G4 Severe Geomagnetic Storm",
      }

      expect(event.storm_id).toBe("2024-10-G4")
      expect(event.confidence).toBeGreaterThan(0)
      expect(event.confidence).toBeLessThanOrEqual(1)
      expect(event.scales.G).toBe(4)
      expect(event.cme.detected).toBe(true)
    })
  })

  describe("ImpactPrediction", () => {
    it("should match expected structure", () => {
      const prediction: ImpactPrediction = {
        gps_error_m: 12.81,
        gps_error_ci_low: 6.59,
        gps_error_ci_high: 13.28,
        hf_blackout_prob: 0.898,
        hf_blackout_ci_low: 0.657,
        hf_blackout_ci_high: 0.927,
      }

      expect(prediction.gps_error_m).toBeGreaterThan(0)
      expect(prediction.gps_error_ci_low).toBeLessThan(prediction.gps_error_m)
      expect(prediction.gps_error_ci_high).toBeGreaterThan(prediction.gps_error_m)
      expect(prediction.hf_blackout_prob).toBeGreaterThanOrEqual(0)
      expect(prediction.hf_blackout_prob).toBeLessThanOrEqual(1)
    })
  })

  describe("GenaiStormEvent", () => {
    it("should match expected structure", () => {
      const event: GenaiStormEvent = {
        alert_id: "2024-10-G4",
        g_scale: "G4",
        s_scale: null,
        r_scale: "R3",
        kp_index: 8.3,
        estimated_arrival_utc: "2024-10-29T04:00:00Z",
        peak_impact_window_start: "2024-10-29T04:00:00Z",
        peak_impact_window_end: "2024-10-29T10:00:00Z",
        raw_alert_text: "Space Weather Alert: G4",
        source_url: null,
      }

      expect(event.alert_id).toBe("2024-10-G4")
      expect(event.g_scale).toMatch(/^G[1-5]$/)
      expect(event.kp_index).toBeGreaterThanOrEqual(0)
      expect(event.kp_index).toBeLessThanOrEqual(9)
    })
  })

  describe("AdvisoryOutput", () => {
    it("should match expected structure", () => {
      const advisory: AdvisoryOutput = {
        advisory_id: "adv-123",
        storm_event_id: "2024-10-G4",
        industry: "aviation" as Industry,
        severity: "HIGH" as SeverityTier,
        confidence_score: 0.92,
        summary: "Aviation operators should reroute aircraft poleward",
        action_items: [
          {
            step: 1,
            action: "Increase monitoring of HF radio systems",
            rationale: "G4 storm can degrade HF communications",
            source_ref: "ICAO 7030",
            time_window: "0-6 hours",
          },
        ],
        estimated_impact_window: "0-6 hours",
        sources_cited: ["ICAO 7030", "DONKI"],
        validation_passed: true,
        generated_at: "2026-06-14T00:00:00Z",
        model_used: "llama-3.3-70b",
        safety_flags: [],
        generation_errors: [],
      }

      expect(advisory.advisory_id).toBeDefined()
      expect(advisory.industry).toMatch(/^(aviation|grid|maritime|telecom)$/)
      expect(advisory.severity).toMatch(/^(NONE|LOW|MEDIUM|HIGH|CRITICAL)$/)
      expect(advisory.action_items).toHaveLength(1)
      expect(advisory.action_items[0].step).toBe(1)
    })

    it("should allow safety flags", () => {
      const advisory: AdvisoryOutput = {
        advisory_id: "adv-456",
        storm_event_id: "2024-05-G5",
        industry: "grid" as Industry,
        severity: "CRITICAL" as SeverityTier,
        confidence_score: 0.75,
        summary: "Critical grid impact expected",
        action_items: [],
        estimated_impact_window: "0-12 hours",
        sources_cited: [],
        validation_passed: false,
        generated_at: "2026-06-14T00:00:00Z",
        model_used: "llama-3.3-70b",
        safety_flags: ["LOW_CONFIDENCE", "HALLUCINATION_DETECTED"] as SafetyFlag[],
        generation_errors: ["Model confidence below threshold"],
      }

      expect(advisory.safety_flags).toContain("LOW_CONFIDENCE")
      expect(advisory.generation_errors).toHaveLength(1)
    })
  })

  describe("VerifiedAdvisory", () => {
    it("should match expected structure with verifier result", () => {
      const verified: VerifiedAdvisory = {
        advisory_id: "adv-123",
        storm_id: "2024-10-G4",
        industry: "aviation",
        severity: "HIGH",
        numbered_actions: [
          "1. Monitor HF systems on 3, 5, 8 MHz",
          "2. Reroute to southern routes",
        ],
        timing_window: {
          opens: "2024-10-29T04:00:00Z",
          duration_min: 360,
        },
        technical_details: "G4 storm with Bz=-15nT",
        cited_procedure: {
          source: "ICAO 7030",
          ref: "Space Weather Procedures",
        },
        verifier: {
          status: "passed" as const,
          checks: [
            {
              field: "hf_frequencies",
              proposed: [3, 5, 8],
              status: "pass" as const,
              corrected_to: null,
              reason: null,
            },
          ],
        },
        provenance_ref: "trace-789",
        requires_human: false,
      }

      expect(verified.advisory_id).toBe("adv-123")
      expect(verified.verifier.status).toBe("passed")
      expect(verified.requires_human).toBe(false)
    })
  })

  describe("ProvenanceTrace", () => {
    it("should match expected structure", () => {
      const trace: ProvenanceTrace = {
        trace_id: "trace-789",
        advisory_id: "adv-123",
        chain: [
          { step: "raw_data", ref: "NOAA:12345", confidence: null, ci_level: null },
          {
            step: "detection",
            ref: "cv-detection:g4-frame-001",
            confidence: 0.91,
            ci_level: 0.95,
          },
          {
            step: "impact",
            ref: "ml-model:gps-error-median",
            confidence: 0.985,
            ci_level: 0.95,
          },
          {
            step: "retrieval",
            ref: "chroma-kb:aviation-5-chunks",
            confidence: 0.88,
            ci_level: null,
          },
          {
            step: "verifier",
            ref: "rule-engine:icao-7030-pass",
            confidence: 1.0,
            ci_level: null,
          },
          { step: "output", ref: "advisory:adv-123", confidence: 0.92, ci_level: 0.95 },
        ],
      }

      expect(trace.trace_id).toBe("trace-789")
      expect(trace.chain).toHaveLength(6)
      expect(trace.chain[0].step).toBe("raw_data")
      expect(trace.chain[5].step).toBe("output")
    })
  })

  describe("PipelineResult", () => {
    it("should match expected structure with complete data", () => {
      const result: PipelineResult = {
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
            frame_path: "/path/frame",
            bbox_norm: [0.1, 0.2, 0.3, 0.4],
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
          noaa_alert_raw: "G4 Storm",
        },
        impact_prediction: {
          gps_error_m: 12.81,
          gps_error_ci_low: 6.59,
          gps_error_ci_high: 13.28,
          hf_blackout_prob: 0.898,
          hf_blackout_ci_low: 0.657,
          hf_blackout_ci_high: 0.927,
        },
        genai_event: {
          alert_id: "2024-10-G4",
          g_scale: "G4",
          s_scale: null,
          r_scale: "R3",
          kp_index: 8.3,
          estimated_arrival_utc: "2024-10-29T04:00:00Z",
          peak_impact_window_start: "2024-10-29T04:00:00Z",
          peak_impact_window_end: "2024-10-29T10:00:00Z",
          raw_alert_text: "G4 Storm",
          source_url: null,
        },
        advisories: [],
        verified_advisories: [],
        provenance_traces: [],
        errors: [],
        completed_at: "2026-06-14T12:30:00Z",
      }

      expect(result.storm_id).toBe("2024-10-G4")
      expect(result.cv_event).toBeDefined()
      expect(result.impact_prediction).toBeDefined()
      expect(result.advisories).toEqual([])
      expect(result.errors).toEqual([])
    })

    it("should allow empty cv_event when failed", () => {
      const result: PipelineResult = {
        storm_id: "2024-10-G4",
        cv_event: {},
        impact_prediction: null,
        genai_event: {},
        advisories: [],
        verified_advisories: [],
        provenance_traces: [],
        errors: ["CV detection failed"],
        completed_at: "2026-06-14T12:30:00Z",
      }

      expect(Object.keys(result.cv_event)).toHaveLength(0)
      expect(result.impact_prediction).toBeNull()
      expect(result.errors).toHaveLength(1)
    })
  })

  describe("StormsResponse", () => {
    it("should match expected structure", () => {
      const response: StormsResponse = {
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

      expect(response.available_storms).toHaveLength(2)
      expect(response.completed["2024-10-G4"].advisory_count).toBe(4)
    })
  })

  describe("WebSocket Event Type Guards", () => {
    it("should identify pipeline.stage events", () => {
      const event: WsEvent = {
        event: "pipeline.stage",
        stage: "detection",
        status: "started",
        timestamp: "2026-06-14T12:00:00Z",
      }

      expect(isPipelineStageEvent(event)).toBe(true)
      expect(isPipelineErrorEvent(event)).toBe(false)
    })

    it("should identify pipeline.error events", () => {
      const event: WsEvent = {
        event: "pipeline.error",
        stage: "detection",
        error: "FITS file not found",
        timestamp: "2026-06-14T12:00:00Z",
      }

      expect(isPipelineErrorEvent(event)).toBe(true)
      expect(isPipelineStageEvent(event)).toBe(false)
    })

    it("should identify advisory.verified events", () => {
      const event: WsEvent = {
        event: "advisory.verified",
        advisory_id: "adv-123",
        industry: "aviation",
        severity: "HIGH",
        verifier_status: "passed",
        requires_human: false,
        timestamp: "2026-06-14T12:00:00Z",
      }

      expect(isAdvisoryVerifiedEvent(event)).toBe(true)
    })

    it("should identify pipeline.complete events", () => {
      const event: WsEvent = {
        event: "pipeline.complete",
        storm_id: "2024-10-G4",
        total_advisories: 4,
        total_verified: 4,
        errors: [],
        timestamp: "2026-06-14T12:00:00Z",
      }

      expect(isPipelineCompleteEvent(event)).toBe(true)
    })

    it("should identify error events", () => {
      const event: WsEvent = {
        event: "error",
        message: "Unknown storm_id",
        timestamp: "2026-06-14T12:00:00Z",
      }

      expect(isWsErrorEvent(event)).toBe(true)
    })
  })

  describe("Type Constraints", () => {
    it("should enforce valid SeverityTier values", () => {
      // This test verifies TypeScript compilation, not runtime behavior
      const validTiers: SeverityTier[] = ["NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
      expect(validTiers).toHaveLength(5)
    })

    it("should enforce valid Industry values", () => {
      const validIndustries: Industry[] = ["aviation", "grid", "maritime", "telecom"]
      expect(validIndustries).toHaveLength(4)
    })

    it("should enforce valid SafetyFlag values", () => {
      const validFlags: SafetyFlag[] = [
        "SEVERITY_MISMATCH",
        "HALLUCINATION_DETECTED",
        "LOW_COVERAGE",
        "LOW_CONFIDENCE",
        "CITATION_GAP",
        "GENERATION_FAILED",
      ]
      expect(validFlags).toHaveLength(6)
    })
  })
})
