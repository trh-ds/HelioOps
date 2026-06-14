Thought: 821ms
Now I have a comprehensive understanding of the entire project. Let me create the enhanced plan with phase-by-phase implementation, unit testing, and security assurance. The user wants:

1. Detailed phase-by-phase plan
2. Unit testing after each file in each phase
3. Integration testing for API execution
4. Security hardening (SQL injection, XSS, hardcoded secrets, input validation, CSRF/CORS)

Let me structure this comprehensively.
Here's the enhanced plan with phase-by-phase implementation, testing gates, and security hardening.
HelioOps Dashboard — Enhanced Implementation Plan
Security Threat Model (Applies Across All Phases)
Threat	Frontend Risk
XSS	React auto-escapes, but advisory text/summaries could be injective if rendered raw
SQL Injection	N/A (no DB in frontend)
Hardcoded Secrets	NEXT_PUBLIC_API_URL is public, not secret
Missing Input Validation	storm_id from URL params passed to API
CSRF/CORS	N/A (SPA, no cookie-based auth)
Rate Limiting	Debounce pipeline trigger button
WebSocket Abuse	N/A
Supply Chain	npm ci in CI, lock file committed
Phase 1: Foundation — Types, API Client, Config
Goal: Establish typed API layer and backend connectivity without touching UI.
Step 1.1: TypeScript Types
File: frontend/src/types/storm.ts
Define interfaces matching every backend Pydantic model:
// Pipeline result (GET /api/result/{storm_id}, POST /api/detect/{storm_id})
export interface PipelineResult {
  storm_id: string
  cv_event: CvStormEvent
  impact_prediction: ImpactPrediction | null
  genai_event: GenaiStormEvent
  advisories: AdvisoryOutput[]
  verified_advisories: VerifiedAdvisory[]
  provenance_traces: ProvenanceTrace[]
  errors: string[]
  completed_at: string
}

export interface CvStormEvent {
  storm_id: string
  detected_at: string
  confidence: number
  scales: { G: number; S: number; R: number }
  cme: { speed_km_s: number; angular_width_deg: number; direction: string; arrival_estimate: string; detected: boolean; source: string; confidence: number; frame_path: string; bbox_norm: number[] }
  flare: { detected: boolean; class: string; r_scale: number; s_scale: number; source: string; onset: string }
  l1_solar_wind: { speed_km_s: number; bz_nt: number; bt_nt: number; density_cm3: number; measured_at: string; g_scale: number; eta_minutes: number }
  timeline: { horizon: string; source: string; t: string }[]
  noaa_alert_raw: string
}

export interface ImpactPrediction {
  gps_error_m: number
  gps_error_ci_low: number
  gps_error_ci_high: number
  hf_blackout_prob: number
  hf_blackout_ci_low: number
  hf_blackout_ci_high: number
}

export interface GenaiStormEvent {
  alert_id: string
  g_scale: string
  s_scale: string | null
  r_scale: string | null
  kp_index: number
  estimated_arrival_utc: string | null
  peak_impact_window_start: string | null
  peak_impact_window_end: string | null
  raw_alert_text: string
  source_url: string | null
}

export type SeverityTier = "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"
export type Industry = "aviation" | "grid" | "maritime" | "telecom"
export type SafetyFlag = "SEVERITY_MISMATCH" | "HALLUCINATION_DETECTED" | "LOW_COVERAGE" | "LOW_CONFIDENCE" | "CITATION_GAP" | "GENERATION_FAILED"

export interface ActionItem {
  step: number
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
  confidence_score: number
  summary: string
  action_items: ActionItem[]
  estimated_impact_window: string | null
  sources_cited: string[]
  validation_passed: boolean
  generated_at: string
  model_used: string
  safety_flags: SafetyFlag[]
  generation_errors: string[]
}

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
  timing_window: { opens: string; duration_min: number }
  technical_details: string
  cited_procedure: { source: string; ref: string }
  verifier: VerifierResult
  provenance_ref: string
  requires_human: boolean
}

export interface ProvenanceStep {
  step: string
  ref: string
  confidence: number | null
  ci_level: number | null
}

export interface ProvenanceTrace {
  trace_id: string
  advisory_id: string
  chain: ProvenanceStep[]
}

export interface StormSummary {
  storm_id: string
  completed_at: string
  advisory_count: number
  verified_count: number
  error_count: number
}

export interface StormsResponse {
  available_storms: string[]
  completed: Record<string, StormSummary>
}

export interface HealthResponse {
  status: string
  version: string
  timestamp?: string
  checks?: Record<string, boolean>
}

// WebSocket events
export type WsEvent =
  | { event: "pipeline.stage"; stage: string; status: "started" | "completed" | "failed"; data?: Record<string, unknown>; timestamp: string }
  | { event: "pipeline.error"; stage: string; error: string; timestamp: string }
  | { event: "advisory.generated"; data: Record<string, unknown>; timestamp: string }
  | { event: "advisory.verified"; advisory_id: string; industry: string; severity: string; verifier_status: string; requires_human: boolean; timestamp: string }
  | { event: "verifier.check"; advisory_id: string; field: string; status: string; timestamp: string }
  | { event: "verifier.error"; advisory_id: string; error: string; timestamp: string }
  | { event: "pipeline.complete"; storm_id: string; total_advisories: number; total_verified: number; errors: string[]; timestamp: string }
  | { event: "error"; message: string; timestamp: string }
Testing after Step 1.1:
- Type check: npx tsc --noEmit — verifies all types compile
- Unit test: Create frontend/__tests__/types/storm.test.ts — type-level tests using satisfies operator to verify interface compatibility with sample JSON from backend docs
Step 1.2: API Client
File: frontend/src/lib/api.ts
const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"

class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? res.statusText)
  }
  return res.json()
}

export const api = {
  getStorms: () => request<StormsResponse>("/api/storms"),
  getResult: (id: string) => request<PipelineResult>(`/api/result/${encodeURIComponent(id)}`),
  detect: (id: string) => request<PipelineResult>(`/api/detect/${encodeURIComponent(id)}`, { method: "POST" }),
  getAdvisory: (id: string) => request<{ verified_advisory: VerifiedAdvisory; provenance_trace: ProvenanceTrace }>(`/api/advisory/${encodeURIComponent(id)}`),
  getHealth: () => request<HealthResponse>("/health"),
  getHealthReady: () => request<HealthResponse>("/health/ready"),
  getMetrics: () => fetch(`${BASE_URL}/metrics`).then(r => r.text()),
}
Security in api.ts:
- encodeURIComponent() on all path params — prevents path traversal
- No secrets in code — BASE_URL from env only
- Content-Type header enforced
- Error handling extracts server message, never leaks stack traces
Testing after Step 1.2:
- Unit test: frontend/__tests__/lib/api.test.ts — mock fetch, test each method:
- Correct URL construction with encodeURIComponent
- Error handling for 404, 500 responses
- Headers set correctly
- ApiError contains status + message
Step 1.3: WebSocket Client
File: frontend/src/lib/ws-client.ts
type WsCallback = (event: WsEvent) => void

class WsClient {
  private ws: WebSocket | null = null
  private listeners: Set<WsCallback> = new Set()
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000
  private maxDelay = 30000
  private url: string

  constructor() {
    const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"
    this.url = base.replace(/^http/, "ws") + "/ws/stream"
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return
    this.ws = new WebSocket(this.url)
    this.ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data) as WsEvent
        this.listeners.forEach(cb => cb(event))
      } catch { /* malformed message — ignore */ }
    }
    this.ws.onclose = () => this.scheduleReconnect()
    this.ws.onerror = () => this.ws?.close()
  }

  private scheduleReconnect() {
    if (this.reconnectTimer) return
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxDelay)
      this.connect()
    }, this.reconnectDelay)
  }

  send(data: { action: string; storm_id: string }) {
    if (this.ws?.readyState !== WebSocket.OPEN) throw new Error("WebSocket not connected")
    this.ws.send(JSON.stringify(data))
  }

  subscribe(cb: WsCallback) { this.listeners.add(cb); return () => this.listeners.delete(cb) }
  disconnect() { this.reconnectTimer && clearTimeout(this.reconnectTimer); this.ws?.close(); this.ws = null }
}

export const wsClient = new WsClient()
Security in ws-client.ts:
- JSON.parse with try/catch — malformed messages don't crash
- Reconnect backoff prevents reconnection storms
- No message injection — send() serializes only typed objects
Testing after Step 1.3:
- Unit test: frontend/__tests__/lib/ws-client.test.ts — mock WebSocket:
- Connection lifecycle (connect, close, reconnect)
- Message parsing and listener dispatch
- Reconnect backoff timing
- send() throws when not connected
- Listener unsubscribe works
Step 1.4: Environment Config
Files:
- frontend/next.config.mjs — add rewrites
- frontend/.env.local — create
next.config.mjs rewrites:
rewrites: async () => [
  { source: "/api/:path*", destination: "http://localhost:8000/api/:path*" },
  { source: "/ws/:path*", destination: "http://localhost:8000/ws/:path*" },
  { source: "/health", destination: "http://localhost:8000/health" },
  { source: "/health/:path*", destination: "http://localhost:8000/health/:path*" },
  { source: "/metrics", destination: "http://localhost:8000/metrics" },
]
.env.local:
NEXT_PUBLIC_API_URL=http://localhost:8000
Testing after Step 1.4:
- Build test: npm run build — verifies config compiles
- Lint: npm run lint — no new warnings
- Type check: npx tsc --noEmit
Phase 1 Gate
✅ npx tsc --noEmit          (types compile)
✅ npm run lint              (no warnings)
✅ npm run build             (config valid)
✅ pytest tests/ -v          (existing backend tests still pass)
✅ All 3 frontend unit test files pass
Phase 2: Backend Security Hardening
Goal: Harden the FastAPI server before frontend connects to it.
Step 2.1: Security Middleware
File: backend/middleware.py (new)
Add:
- Security headers middleware (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection, Content-Security-Policy, Referrer-Policy)
- Request ID middleware (trace ID per request)
- Rate limiting (in-memory token bucket for /api/detect/*)
# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response
Rate limiting for pipeline:
# Simple in-memory rate limiter
_pipeline_calls: dict[str, float] = {}
RATE_LIMIT_SECONDS = 30  # one pipeline run per storm per 30s

def check_rate_limit(storm_id: str) -> bool:
    now = time.time()
    last = _pipeline_calls.get(storm_id, 0)
    if now - last < RATE_LIMIT_SECONDS:
        return False
    _pipeline_calls[storm_id] = now
    return True
Step 2.2: Input Validation
File: backend/app.py (modify endpoint)
Add storm_id format validation:
import re
STORM_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-G[1-5]$")

@app.post("/api/detect/{storm_id}")
async def detect(storm_id: str):
    if not STORM_ID_PATTERN.match(storm_id):
        raise HTTPException(400, f"Invalid storm_id format: {storm_id}")
    if not check_rate_limit(storm_id):
        raise HTTPException(429, "Rate limit: wait 30s between pipeline runs for this storm")
    ...
Step 2.3: Tighten CORS
File: backend/app.py (modify)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,  # already restricted
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # was ["*"]
    allow_headers=["Content-Type", "Authorization"],  # was ["*"]
)
Step 2.4: WebSocket Origin Validation
File: backend/app.py (modify WS handler)
@app.websocket("/ws/stream")
async def ws_stream(websocket: WebSocket):
    origin = websocket.headers.get("origin", "")
    allowed = settings.CORS_ORIGINS
    if origin and not any(origin.startswith(o) for o in allowed):
        await websocket.close(code=4003, reason="Origin not allowed")
        return
    ...
Step 2.5: Env Var Validation at Startup
File: backend/config.py (modify)
Add startup validation:
@validator("GROQ_API_KEY")
def validate_groq_key(cls, v):
    if not v:
        import warnings
        warnings.warn("GROQ_API_KEY not set — GenAI advisories will fail")
    return v
Testing after Phase 2:
- Unit test: tests/test_security.py (new)
- Security headers present on all responses
- Rate limiter blocks rapid requests
- Storm ID regex rejects invalid formats ("../../etc", "'; DROP TABLE--", "G5", "2024-13-G6")
- CORS headers only include allowed origins
- WebSocket rejects unknown origins
- Missing GROQ_API_KEY produces warning
- Integration test: tests/test_api_endpoints.py (new)
- GET /health returns 200 + correct schema
- GET /health/ready returns 200 or 503
- GET /api/storms returns correct schema
- POST /api/detect/2024-10-G4 returns 200 or 500 (depends on data)
- POST /api/detect/invalid-id returns 400
- GET /api/result/unknown returns 404
- GET /api/advisory/unknown returns 404
- GET /metrics returns text/plain
Phase 2 Gate
✅ pytest tests/test_security.py -v
✅ pytest tests/test_api_endpoints.py -v
✅ pytest tests/test_pipeline.py -v  (regression)
✅ ruff check backend/
✅ ruff format --check backend/
Phase 3: Dashboard Layout + Navigation
Goal: Create the dashboard shell — layout, sidebar, topbar, routing.
Step 3.1: Dashboard Layout
File: frontend/src/app/dashboard/layout.tsx
- Separate layout from landing page
- Sidebar + topbar + main content area
- Health status indicator (polls /health every 30s)
- No auth gate (not yet), but structured for future addition
Step 3.2: Sidebar
File: frontend/src/components/dashboard/Sidebar.tsx
- Nav links: Storm List, Pipeline, Health, Back to Home
- Active link highlighting via usePathname()
- Collapsible on mobile
- All links use <Link> (no <a href="#"> placeholders)
Step 3.3: TopBar
File: frontend/src/components/dashboard/TopBar.tsx
- WS connection status dot (green=connected, red=disconnected)
- Backend health badge (polls /health/ready)
- Current page title from pathname
Step 3.4: Dashboard Home Page
File: frontend/src/app/dashboard/page.tsx
- Fetches GET /api/storms on mount
- Displays storm cards grid
- Quick action: "Run Pipeline" button
- Health summary section
Testing after Phase 3:
- Component test: frontend/__tests__/components/Sidebar.test.tsx
- Renders all nav links
- Active link highlighting works
- Mobile collapse toggle
- Component test: frontend/__tests__/components/TopBar.test.tsx
- Health badge shows correct status
- WS status indicator updates
- E2E smoke: npm run build — all pages compile
Phase 3 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All component tests pass
Phase 4: Storm List + Detail Pages
Goal: Display storm data from API, with drill-in to details.
Step 4.1: StormCard Component
File: frontend/src/components/dashboard/StormCard.tsx
- Displays: storm ID, G-scale badge (color-coded), completion status, advisory count
- Severity badge uses aurora/warm colors from tailwind config
- Click navigates to /dashboard/storms/[stormId]
Step 4.2: Storm List Page
File: frontend/src/app/dashboard/storms/page.tsx
- Fetches GET /api/storms
- Renders StormCard grid
- Loading skeleton, error state
- Empty state if no storms
Step 4.3: Storm Detail Page
File: frontend/src/app/dashboard/storms/[stormId]/page.tsx
- Fetches GET /api/result/{stormId}
- Sections: CV Event (scales, CME data, solar wind), Impact Prediction, Timeline
- "Run Pipeline" button (triggers POST /api/detect/{stormId})
- Back navigation
Step 4.4: Impact Display Component
File: frontend/src/components/dashboard/ImpactDisplay.tsx
- GPS error with confidence interval bar
- HF blackout probability gauge
- Conservative defaults warning if prediction is fallback
Testing after Phase 4:
- Component test: StormCard.test.tsx — renders correctly for all severity levels
- Component test: ImpactDisplay.test.tsx — renders with data, renders fallback warning
- Page test: storms/page.test.tsx — loading state, data state, error state
- Integration test: Mock API, verify storm list fetches and renders
Phase 4 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All tests pass
✅ XSS check: no dangerouslySetInnerHTML used anywhere
Phase 5: Pipeline Runner + Real-Time Streaming
Goal: Trigger pipeline, show live progress via WebSocket.
Step 5.1: PipelineProgress Component
File: frontend/src/components/dashboard/PipelineProgress.tsx
- 5 steps: Detection → Impact Prediction → Adaptation → Advisory → Verification
- Each step: pending (gray), active (aurora pulse), done (green check), error (red)
- Animated transitions via Framer Motion
Step 5.2: StreamLog Component
File: frontend/src/components/dashboard/StreamLog.tsx
- Auto-scrolling event log
- Color-coded by event type (stage=blue, advisory=green, error=red, verifier=purple)
- Filter by event type
- Timestamp display
Step 5.3: Pipeline Page
File: frontend/src/app/dashboard/pipeline/page.tsx
- Storm selector dropdown (from GET /api/storms)
- "Run Pipeline" button (disabled while running)
- PipelineProgress + StreamLog side by side
- On pipeline.complete event, link to results page
Step 5.4: WebSocket Integration
- Connect wsClient to pipeline page
- Subscribe to events → update PipelineProgress state
- Cleanup on unmount
Security in Pipeline page:
- Button disabled during execution (prevent double-submit)
- storm_id validated before sending to WS
- Error events displayed, not thrown
Testing after Phase 5:
- Component test: PipelineProgress.test.tsx — all 5 step states render correctly
- Component test: StreamLog.test.tsx — events append, filter works, auto-scroll
- Hook test: WebSocket client mock — connect, receive events, reconnect
- Page test: Pipeline page — selector populates, button enables/disables
Phase 5 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All tests pass
✅ WebSocket reconnect test passes
✅ Double-submit prevention verified
Phase 6: Results Display — Advisories, Verification, Provenance
Goal: Full results page with all advisory data and audit trail.
Step 6.1: AdvisoryCard Component
File: frontend/src/components/dashboard/AdvisoryCard.tsx
- Industry badge (aviation=blue, grid=amber, maritime=cyan, telecom=purple)
- Severity tier with color coding
- Summary text
- Action items accordion (expandable)
- Sources cited list
- Safety flags warnings
Step 6.2: VerifiedAdvisoryCard Component
File: frontend/src/components/dashboard/VerifiedAdvisoryCard.tsx
- Verifier status badge (passed=green, corrections=yellow, blocked=red)
- Numbered actions list
- Timing window display
- Technical details
- Cited procedure link
- "Requires Human Review" warning banner
Step 6.3: ProvenanceChain Component
File: frontend/src/components/dashboard/ProvenanceChain.tsx
- Horizontal timeline of 6 steps: raw_data → detection → impact → retrieval → verifier → output
- Each step: name, ref, confidence bar
- Click to expand details
Step 6.4: Results Page
File: frontend/src/app/dashboard/results/[stormId]/page.tsx
- Fetches GET /api/result/{stormId}
- Sections: Impact Prediction (chart), Advisories (cards), Verified Advisories (cards), Provenance Traces
- Error state if no result
Testing after Phase 6:
- Component tests: Each card component with sample data
- Page test: Results page with mocked API response
- XSS test: Verify advisory text is escaped (no raw HTML rendering)
- Edge case: Empty advisories array renders correctly
- Edge case: null impact_prediction renders fallback
Phase 6 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All tests pass
✅ XSS audit: grep for dangerouslySetInnerHTML — zero results
Phase 7: Health + Metrics Page
Goal: System health dashboard with parsed Prometheus metrics.
Step 7.1: MetricsDisplay Component
File: frontend/src/components/dashboard/MetricsDisplay.tsx
- Parses Prometheus text format → key-value pairs
- Gauge cards: uptime, requests, errors, avg latency, p99 latency
- Error rate percentage calculation
- Connection count
Step 7.2: Health Page
File: frontend/src/app/dashboard/health/page.tsx
- GET /health — basic status
- GET /health/ready — dependency checks (detection, ML models, genai)
- GET /metrics — parsed metrics
- Auto-refresh every 10s
- Status indicators: green check / red X per dependency
Testing after Phase 7:
- Unit test: MetricsDisplay.test.ts — parses valid Prometheus text, handles malformed input
- Component test: Health page — renders all three sections, auto-refresh works
- Edge case: Backend down → error state, not crash
Phase 7 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All tests pass
✅ Prometheus parser handles edge cases (empty, malformed)
Phase 8: Error Boundaries + Edge Cases
Goal: Prevent full-page crashes, handle all failure modes.
Step 8.1: Error Boundary Components
Files:
- frontend/src/components/ErrorBoundary.tsx — generic class component
- frontend/src/components/dashboard/DashboardErrorBoundary.tsx — wraps each dashboard section
Step 8.2: Loading States
- Skeleton loaders for all data-fetching pages
- Suspense boundaries with fallback UI
Step 8.3: Empty States
- No storms available
- No completed results
- No advisories generated
- Backend unreachable
Step 8.4: Network Error Handling
- API client retries on 5xx (1 retry, exponential backoff)
- WebSocket auto-reconnect (already in Phase 1)
- Toast notifications for transient errors
Testing after Phase 8:
- Component test: Error boundary catches thrown errors, renders fallback
- Component test: Loading skeletons render
- Integration test: Mock fetch failure → error state renders
- Edge case: Malformed API response → graceful degradation
Phase 8 Gate
✅ npx tsc --noEmit
✅ npm run lint
✅ npm run build
✅ All tests pass
✅ Error boundary test passes
Phase 9: CI Enforcement + Final Security Audit
Goal: Make CI actually gate, run full security scan.
Step 9.1: Fix CI Pipeline
File: .github/workflows/ci.yml
- Remove all || true — lint and test failures must block merge
- Add frontend test step: npm test (after setting up vitest)
- Add security scan step: npm audit --audit-level=high
- Add backend security: pip-audit for Python deps
- Add coverage reporting
Step 9.2: Frontend Test Setup
Files:
- frontend/vitest.config.ts — vitest + testing-library
- frontend/__tests__/ — all unit tests from phases 1-8
- frontend/package.json — add test script
Step 9.3: Security Audit Checklist
Check	Method
No dangerouslySetInnerHTML	grep -r "dangerouslySetInnerHTML" src/
No hardcoded secrets	grep -r "gsk_|api_key|password|secret" src/ --include="*.ts" --include="*.tsx"
No except: pass	grep -r "except.*pass" backend/
Input validation on all endpoints	Manual review of app.py
CORS restrictive	Review allow_methods, allow_headers
Security headers present	curl -I localhost:8000/health
Rate limiting active	Manual test: rapid POST calls
WebSocket origin check	Test with wrong origin
No secrets in git	.gitignore includes .env, .env.local
Dependencies clean	npm audit, pip-audit
Step 9.4: Full Regression
# Backend
pytest tests/ -v --tb=short

# Frontend
npm test
npm run build
npm run lint
npx tsc --noEmit

# Integration (backend running)
curl localhost:8000/health
curl localhost:8000/api/storms
curl -X POST localhost:8000/api/detect/2024-10-G4
Phase 9 Gate
✅ CI pipeline passes (no || true)
✅ All backend tests pass
✅ All frontend tests pass
✅ Security audit: all 10 checks green
✅ npm audit: 0 high/critical
✅ pip-audit: 0 high/critical
✅ Full regression suite passes
Execution Summary
Phase	Files Created/Modified
1. Foundation	4 files (types, api, ws-client, config)
2. Backend Security	3 files (middleware.py, app.py, config.py)
3. Dashboard Layout	4 files (layout, sidebar, topbar, page)
4. Storm Pages	4 files (StormCard, list, detail, ImpactDisplay)
5. Pipeline + WS	4 files (PipelineProgress, StreamLog, page, ws integration)
6. Results Display	4 files (AdvisoryCard, VerifiedAdvisoryCard, ProvenanceChain, page)
7. Health + Metrics	2 files (MetricsDisplay, page)
8. Error Boundaries	4 files (ErrorBoundary, DashboardErrorBoundary, loading, empty states)
9. CI + Audit	1 file (ci.yml) + test config
Total	~30 files
Test Setup Requirement
Before Phase 1, install test dependencies in frontend:
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
Add to frontend/package.json:
"scripts": {
  "test": "vitest run",
  "test:watch": "vitest"
}
Create frontend/vitest.config.ts with React testing support.
Ready to execute. Confirm and I'll start with Phase 1 (types + API client + WS client + config) and their tests.