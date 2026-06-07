**HelioOps**

Design Handoff

UI/UX component specifications, design tokens, states, and accessibility
requirements

**Field**

**Value**

Author

Neal Daftary — B\.Tech CSE AI/ML, Nirma University

Sponsor / Operator

Zylon Labs

Document Version

v1\.0 — Draft

Date

June 2026

Status

In Review

Classification

Confidential

**Purpose**

This document specifies all visual and interaction requirements for HelioOps
engineers implementing the frontend\. Pixel measurements, component states,
colour tokens, and accessibility requirements are defined here\. Figma is the
source of truth for visual comps; this document is the source of truth for
behaviour, states, and edge cases\.

# **1\. Design Tokens**

## **1\.1 Colour System**

**Token**

**Hex Value**

**Usage**

\-\-color\-teal\-600 \(primary brand\)

\#1D9E75

Primary CTA buttons, active states, storm severity badges, chart lines

\-\-color\-teal\-50 \(primary light\)

\#E1F5EE

Advisory card backgrounds \(calm\), success alert fills

\-\-color\-amber\-600 \(watch\)

\#854F0B

Watch state banners, yellow severity badges

\-\-color\-amber\-50 \(watch light\)

\#FAEEDA

Watch state card backgrounds

\-\-color\-coral\-600 \(warning\)

\#993C1D

Warning state banners, orange severity badges

\-\-color\-red\-600 \(critical\)

\#A32D2D

Critical state banners, red severity badges, error states

\-\-color\-red\-50 \(critical light\)

\#FCEBEB

Critical state card backgrounds

\-\-color\-gray\-900 \(text primary\)

\#1A1A1A

All body text, headings

\-\-color\-gray\-500 \(text secondary\)

\#666666

Labels, metadata, timestamps

\-\-color\-gray\-100 \(surface\)

\#F5F5F5

Card backgrounds, table alternate rows

\-\-color\-gray\-200 \(border\)

\#E0E0E0

Dividers, card borders, input borders

## **1\.2 Typography**

**Role**

**Font**

**Size**

**Weight**

**Line Height**

Display — storm scale number

Inter

72px

700

1\.0

Heading 1 — page title

Inter

32px

600

1\.2

Heading 2 — section title

Inter

24px

600

1\.3

Heading 3 — card title

Inter

18px

600

1\.4

Body — advisory text

Inter

15px

400

1\.6

Label — metadata, timestamps

Inter

12px

500

1\.4

Code — LLM reasoning log

JetBrains Mono

13px

400

1\.5

## **1\.3 Spacing Scale**

All spacing uses an 8px base unit: 4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 96px\.
Component internal padding: 16px \(cards\), 12px \(badges\), 8px \(compact list
items\)\.

## **1\.4 Border Radius**

**Token**

**Value**

**Usage**

\-\-radius\-sm

4px

Badges, status pills, table cell highlights

\-\-radius\-md

8px

Input fields, dropdowns, tooltips

\-\-radius\-lg

12px

Cards, panels, modals

\-\-radius\-xl

16px

Dashboard sections, storm status banner

# **2\. Storm Status Banner**

## **2\.1 States & Visual Specifications**

**State**

**Background**

**Text Colour**

**Content**

**Animation**

Calm

\-\-color\-gray\-100

\-\-color\-gray\-900

Solar quiet | Kp = \{value\} | Last checked: \{time\}

None

Watch \(G1–G2\)

\-\-color\-amber\-50

\-\-color\-amber\-600

STORM WATCH — G\{n\} | Kp = \{value\} | Expected impact: \{time\}

Slow pulse 3s

Warning \(G3\)

\#FFF3E0

\-\-color\-coral\-600

STORM WARNING — G\{n\} | Impact in ~\{eta\} min | \{N\} advisories active

Medium pulse 2s

Critical \(G4–G5\)

\-\-color\-red\-50

\-\-color\-red\-600

CRITICAL STORM — G\{n\} | IMPACT NOW | All advisories dispatched

Fast pulse 1s \+ subtle vibrate

## **2\.2 Banner Behaviour**

- The banner occupies the full viewport width, height 64px, position: sticky
  top\.
- The Kp value updates every 5 minutes without a full page reload \(WebSocket
  push\)\.
- Clicking the banner opens a storm detail modal showing the full StormEvent
  object\.
- On mobile, the banner collapses to a 44px pill with an icon and the G\-scale
  number only\.

# **3\. Industry Advisory Cards**

## **3\.1 Card Anatomy**

Each advisory card has: \(1\) a header row with industry icon, industry name,
severity badge, and timestamp; \(2\) a body showing the top 3 action items as a
numbered list; \(3\) a collapsible detail section with technical details and
reference procedures; \(4\) a footer row with 'Approve' and 'Reject' buttons and
the CRM ticket ID\.

## **3\.2 Severity Badge Spec**

**Severity**

**Background**

**Text**

**Icon**

CRITICAL

\-\-color\-red\-600

\#FFFFFF

ti\-alert\-triangle \(16px\)

HIGH

\-\-color\-coral\-600

\#FFFFFF

ti\-alert\-circle \(16px\)

MEDIUM

\-\-color\-amber\-600

\#FFFFFF

ti\-info\-circle \(16px\)

LOW

\-\-color\-teal\-600

\#FFFFFF

ti\-check\-circle \(16px\)

## **3\.3 Card States**

**State**

**Visual Treatment**

Generating

Card skeleton shimmer animation\. 'Generating advisory…' placeholder text in
body\.

Pending review

Border: 2px solid \-\-color\-amber\-600\. 'Awaiting approval' pill in header\.

Approved

Border: 2px solid \-\-color\-teal\-600\. Green checkmark in header\.

Auto\-approved

Border: 1px solid \-\-color\-gray\-200\. 'Auto\-dispatched' label in footer\.

Rejected

Card opacity: 0\.6\. Red X in header\. 'Rejected by \{name\}' in footer\.

Dispatched

Green glow on card edge \(box\-shadow: 0 0 0 2px \#1D9E75\)\. 'Delivered'
badge\.

## **3\.4 Approve / Reject Interaction**

- Approve button: primary teal, 'Approve & Send', 36px height, 12px horizontal
  padding\. On click: optimistic UI update → POST
  /api/v1/advisories/\{id\}/approve → WebSocket confirms dispatch\.
- Reject button: outlined, 'Reject', same size as Approve\. On click: inline
  rejection reason textarea appears \(required, max 200 chars\) → POST
  /api/v1/advisories/\{id\}/reject\.
- Both buttons become disabled once an action is taken\. No undo\.

# **4\. Kp / Solar Wind Sparkline**

- Component: Recharts LineChart, height 120px, full card width\.
- X\-axis: last 24 hours, tick every 6 hours\.
- Y\-axis: Kp scale 0–9\. Reference line at Kp=5 \(G1 threshold\), dashed
  amber\. Reference line at Kp=7 \(G3 threshold\), dashed red\.
- Line colour: below threshold → \-\-color\-teal\-600\. Above G1 threshold →
  \-\-color\-amber\-600\. Above G3 → \-\-color\-red\-600\. Line colour
  transitions based on value\.
- Tooltip on hover: timestamp, Kp value, G\-scale label\.
- Current value highlighted with a pulsing dot at the right edge of the line\.

# **5\. Live Agent Reasoning Panel**

- Positioned: right sidebar, width 320px \(desktop\), or full\-width bottom
  sheet \(mobile\)\.
- Contents: scrolling log of agent reasoning steps, colour\-coded by step type\.

**Step Type**

**Prefix Colour**

**Format**

Storm detected

\-\-color\-teal\-600

\[STORM\] G\{n\} Kp=\{value\} ETA=\{min\}m

Industry routed

\-\-color\-amber\-600

\[ROUTE\] Aviation: CRITICAL, Grid: HIGH…

RAG retrieval

\-\-color\-gray\-500

\[RAG\] aviation_kb: querying 'G4 HF polar procedures' → 5 chunks

LLM generating

\-\-color\-gray\-900

\[LLM\] Streaming: 'Based on G4 severity, recommend re\-routing…'

Advisory complete

\-\-color\-teal\-600

\[DONE\] Aviation advisory generated in 1842ms

Dispatched

\-\-color\-teal\-600 bold

\[SENT\] CRM ticket created: HO\-2024\-001\. Email sent to ops@airline\.se

- Auto\-scrolls to bottom on new messages\.
- Older entries fade to opacity: 0\.5 after 10 new entries to show recency\.
- Code font \(JetBrains Mono 13px\) for all reasoning log text\.

# **6\. Responsive Breakpoints**

**Breakpoint**

**Width**

**Layout Changes**

Mobile

< 768px

Single column layout\. Advisory cards stack vertically\. Banner collapses\.
Reasoning panel becomes bottom sheet\. Sparkline height reduces to 80px\.

Tablet

768–1199px

Two\-column layout: storm status \+ sparkline left, advisory cards right\.
Reasoning panel hidden \(accessible via button\)\.

Desktop \(default\)

> = 1200px

Three\-column layout: status panel left, advisory cards centre, reasoning panel
right\. Full sparkline\. All components visible simultaneously\.

# **7\. Accessibility Requirements**

- All interactive elements \(approve/reject buttons, card expand/collapse\) must
  be keyboard navigable with visible focus rings\.
- Severity badges must not rely on colour alone — include an icon with
  aria\-label\.
- Storm status banner: aria\-live='assertive' for CRITICAL state, 'polite' for
  WATCH/WARNING\. Announce severity change to screen readers\.
- Colour contrast: all text meets WCAG 2\.1 AA \(4\.5:1 minimum\)\. Severity
  badge text on coloured backgrounds tested and confirmed compliant with
  specified hex values\.
- Agent reasoning panel: aria\-live='off' \(too noisy for screen readers during
  storms\)\. Provide a 'Download reasoning log' button that saves the session to
  a text file\.
- Minimum touch target size: 44px × 44px for all interactive elements \(approve
  / reject buttons, banner clicks\)\.
