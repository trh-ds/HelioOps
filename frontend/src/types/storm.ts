/**
 * HelioOps API Type Definitions
 *
 * Mirrors all backend Pydantic models for type-safe API integration.
 * Keep in sync with backend: backend/pipeline.py, genai/models.py, genai/contracts.py
 */

// ============================================================================
// CV Detection (Computer Vision) Models
// ============================================================================

export interface CvStormEvent {
  storm_id: string
  detected_at: string // ISO 8601
  confidence: number // 0-1
  scales: {
    G: number // Geomagnetic storm scale [0-5]
    S: number // Solar radiation storm scale [0-5]
    R: number // Radio blackout scale [0-5]
  }
  cme: {
    speed_km_s: number
    angular_width_deg: number
    direction: string
    arrival_estimate: string // ISO 8601
    detected: boolean
    source: string
    confidence: number
    frame_path: string
    bbox_norm: number[]
  }
  flare: {
    detected: boolean
    class: string // X, M, C, B, A
    r_scale: number
    s_scale: number
    source: string
    onset: string // ISO 8601
  }
  l1_solar_wind: {
    speed_km_s: number
    bz_nt: number // nanoTesla
    bt_nt: number
    density_cm3: number
    measured_at: string // ISO 8601
    g_scale: number
    eta_minutes: number
  }
  timeline: Array<{
    horizon: string
    source: string
    t: string // ISO 8601
  }>
  noaa_alert_raw: string
}

// ============================================================================
// ML Inference Models
// ============================================================================

export interface ImpactPrediction {
  gps_error_m: number // median GPS error in meters
  gps_error_ci_low: number // 95% CI lower bound
  gps_error_ci_high: number // 95% CI upper bound
  hf_blackout_prob: number // 0-1 probability
  hf_blackout_ci_low: number
  hf_blackout_ci_high: number
}

// ============================================================================
// GenAI Models
// ============================================================================

export type SeverityTier = "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type Industry = "aviation" | "grid" | "maritime" | "telecom"
export type SafetyFlag =
  | "SEVERITY_MISMATCH"
  | "HALLUCINATION_DETECTED"
  | "LOW_COVERAGE"
  | "LOW_CONFIDENCE"
  | "CITATION_GAP"
  | "GENERATION_FAILED"

export interface GenaiStormEvent {
  alert_id: string
  g_scale: string // "G1" - "G5"
  s_scale: string | null // "S1" - "S5" or null
  r_scale: string | null // "R1" - "R5" or null
  kp_index: number // 0-9
  estimated_arrival_utc: string | null // ISO 8601
  peak_impact_window_start: string | null // ISO 8601
  peak_impact_window_end: string | null // ISO 8601
  raw_alert_text: string
  source_url: string | null
}

export interface ActionItem {
  step: number // 1-indexed
  action: string
  rationale: string
  source_ref: string | null
  time_window: string | null
}

export interface AdvisoryOutput {
  advisory_id: string
  storm_event_id: string
  industry: Industry
  severity: SeverityTier
  confidence_score: number // 0-1
  summary: string
  action_items: ActionItem[]
  estimated_impact_window: string | null
  sources_cited: string[]
  validation_passed: boolean
  generated_at: string // ISO 8601
  model_used: string
  safety_flags: SafetyFlag[]
  generation_errors: string[]
}

// ============================================================================
// Verification Models
// ============================================================================

export interface VerifierCheck {
  field: string
  proposed: unknown
  status: "pass" | "blocked"
  corrected_to: unknown | null
  reason: string | null
}

export interface VerifierResult {
  status: "passed" | "passed_with_corrections" | "blocked"
  checks: VerifierCheck[]
}

export interface VerifiedAdvisory {
  advisory_id: string
  storm_id: string
  industry: string
  severity: string
  numbered_actions: string[]
  timing_window: {
    opens: string // ISO 8601
    duration_min: number
  }
  technical_details: string
  cited_procedure: {
    source: string
    ref: string
  }
  verifier: VerifierResult
  provenance_ref: string
  requires_human: boolean
}

// ============================================================================
// Provenance Models
// ============================================================================

export interface ProvenanceStep {
  step: string // "raw_data" | "detection" | "impact" | "retrieval" | "verifier" | "output"
  ref: string
  confidence: number | null
  ci_level: number | null // confidence interval level, e.g., 0.95 for 95%
}

export interface ProvenanceTrace {
  trace_id: string
  advisory_id: string
  chain: ProvenanceStep[]
}

// ============================================================================
// Pipeline Result
// ============================================================================

export interface PipelineResult {
  storm_id: string
  cv_event: CvStormEvent | Record<string, never> // Empty object if failed
  impact_prediction: ImpactPrediction | null
  genai_event: GenaiStormEvent | Record<string, never>
  advisories: AdvisoryOutput[]
  verified_advisories: VerifiedAdvisory[]
  provenance_traces: ProvenanceTrace[]
  errors: string[]
  completed_at: string // ISO 8601
}

// ============================================================================
// API Response Models
// ============================================================================

export interface StormSummary {
  storm_id: string
  completed_at: string // ISO 8601
  advisory_count: number
  verified_count: number
  error_count: number
}

export interface StormsResponse {
  available_storms: string[]
  completed: Record<string, StormSummary>
}

export interface AdvisoryLookupResponse {
  verified_advisory: VerifiedAdvisory
  provenance_trace: ProvenanceTrace
}

export interface HealthResponse {
  status: string // "ok" | "alive" | "ready" | "degraded"
  version?: string
  timestamp?: string
  checks?: Record<string, boolean>
}

// ============================================================================
// WebSocket Event Models
// ============================================================================

export interface PipelineStageEvent {
  event: "pipeline.stage"
  stage: "detection" | "impact_prediction" | "adaptation" | "advisory_generation" | "verification"
  status: "started" | "completed" | "failed"
  data?: Record<string, unknown>
  timestamp: string
}

export interface PipelineErrorEvent {
  event: "pipeline.error"
  stage: string
  error: string
  timestamp: string
}

export interface AdvisoryGeneratedEvent {
  event: "advisory.generated"
  industry: string
  step?: string
  data?: Record<string, unknown>
  timestamp: string
}

export interface AdvisoryVerifiedEvent {
  event: "advisory.verified"
  advisory_id: string
  industry: string
  severity: string
  verifier_status: string
  requires_human: boolean
  timestamp: string
}

export interface VerifierCheckEvent {
  event: "verifier.check"
  advisory_id: string
  field: string
  status: string
  timestamp: string
}

export interface VerifierErrorEvent {
  event: "verifier.error"
  advisory_id: string
  error: string
  timestamp: string
}

export interface PipelineCompleteEvent {
  event: "pipeline.complete"
  storm_id: string
  total_advisories: number
  total_verified: number
  errors: string[]
  timestamp: string
}

export interface WsErrorEvent {
  event: "error"
  message: string
  timestamp: string
}

export type WsEvent =
  | PipelineStageEvent
  | PipelineErrorEvent
  | AdvisoryGeneratedEvent
  | AdvisoryVerifiedEvent
  | VerifierCheckEvent
  | VerifierErrorEvent
  | PipelineCompleteEvent
  | WsErrorEvent

// ============================================================================
// Type Guards
// ============================================================================

export function isPipelineStageEvent(event: WsEvent): event is PipelineStageEvent {
  return event.event === "pipeline.stage"
}

export function isPipelineErrorEvent(event: WsEvent): event is PipelineErrorEvent {
  return event.event === "pipeline.error"
}

export function isAdvisoryVerifiedEvent(event: WsEvent): event is AdvisoryVerifiedEvent {
  return event.event === "advisory.verified"
}

export function isPipelineCompleteEvent(event: WsEvent): event is PipelineCompleteEvent {
  return event.event === "pipeline.complete"
}

export function isWsErrorEvent(event: WsEvent): event is WsErrorEvent {
  return event.event === "error"
}
