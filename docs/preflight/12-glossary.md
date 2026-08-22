# 12 — Glossary

*Every term used in this pack, defined for a reader with no background. Space
weather first, then software, then the terms specific to this feature.*

---

## Space weather

**Bz** — the north/south component of the magnetic field carried by the solar
wind, in nanotesla. **Negative (southward) Bz couples to Earth's field and
drives storms; positive (northward) Bz largely does not.** This is a mechanism,
not a matter of degree, which is why a positive Bz alongside a severe storm
rating is a genuine contradiction rather than a discrepancy.

**Ballistic arrival estimate** — the arrival time you get by propagating a CME
at constant speed from where it was observed to Earth. Ignores drag, so it
carries roughly **10 hours of mean absolute error**. Every arrival threshold in
this feature is derived from that number.

**CME (coronal mass ejection)** — a large eruption of magnetised plasma from the
Sun, typically 300–3000 km/s. Takes one to three days to reach Earth.

**Coronagraph** — a telescope that blocks the Sun's bright disc so the faint
outflow around it becomes visible. How CMEs are seen at launch.

**DONKI** — NASA's Space Weather Database Of Notifications, Knowledge,
Information. Publishes **human-reviewed** CME analyses: speed, width, ballistic
arrival estimate. The only source in this system that serves historical dates.

**DSCOVR / L1** — a NASA spacecraft at the L1 Lagrange point, about a million
miles sunward, where it measures the solar wind roughly an hour before it
reaches Earth. Its real-time feed is called `rtsw`.

**Flare class (A/B/C/M/X)** — a logarithmic scale of solar X-ray flux. X is the
top. Maps directly onto the R-scale.

**GOES / XRS** — NOAA's geostationary satellites; the X-Ray Sensor instrument
measures the flux used for flare classification. Its `xrays` feed is real-time
only.

**G / S / R scales** — NOAA's 1–5 severity scales for geomagnetic storms,
radiation storms, and radio blackouts. The two storms HelioOps replays are a G4
(October 2024) and a G5 (May 2024).

**HF (high frequency)** — 3–30 MHz radio. The only long-range voice link for
aircraft outside satellite coverage, and the first thing a storm takes away.

**Solar wind** — the continuous stream of charged particles from the Sun,
typically 400 km/s at quiet times.

---

## Software

**Cache** — a local copy of remote data kept on disk. In HelioOps every external
client is **cache-first**: use the file if it is there, otherwise fetch it and
write it. That "otherwise" is the trap this feature had to work around.

**Fallback** — what a program does when its first choice is unavailable.
HelioOps has one at every step by design, so nothing crashes the demo. The cost
is that degradation is silent — which is the problem this feature exists to
solve.

**Rate limit** — a cap on how often something may run. One pipeline run per
storm per thirty seconds here.

**Read-only** — an operation that observes without changing anything. Harder
than it sounds when the components you call write on read; see
[chapter 6](06-the-read-only-invariants.md).

**Stub** — a stored, known-good answer used when the real computation cannot
run. HelioOps ships one per storm. It makes the demo deterministic, and it also
means the demo can look identical whether or not any work was done.

**TPM (tokens per minute)** — how language model throughput is metered.
Exceeding it does not fail requests; it queues them. A 70-second run becomes a
three-minute run with no error anywhere.

**TTL (time to live)** — how long a cached value stays valid. 30 seconds for the
health snapshot here.

---

## Terms specific to this feature

**Conflict** — two independent sources describing the same event in ways that
cannot both be physically true. Not an error, not a validation failure: each
source is individually well-formed. The contradiction only exists between them.

**Demotion** — dropping a finding's severity from `warn` to `info`, with the
reason appended to its detail, when the finding is true but cannot affect this
run's output. See [5.6](05-the-conflict-rules.md#56-the-stub-replay-demotion).

**Finding** — one item in the pre-flight response: a stable `id`, a `severity`,
a one-line `title`, and a paragraph of `detail`. Titles are what the panel shows;
`id`s are what tests assert on.

**Gate** — the panel between clicking Run and the run starting. Never blocks;
disappears and runs directly if the check itself fails.

**Headline** — layer one of the disclosure: one plain-English sentence taken
from the most severe finding, stating the consequence rather than the fact.

**Peek** — a non-mutating read of state that a normal check would record. Here,
`peek_rate_limit()` versus `check_rate_limit()`.

**Pre-flight / dry run** — describing what an operation *would* do without
doing it.

**Progressive disclosure** — showing the smallest thing that lets someone
decide, with everything else one deliberate action away. Three layers here:
sentence, pills, evidence.

**Severity** — `block` (the run will be rejected right now), `warn` (it will
succeed but the result is compromised in a specific way), `info` (worth knowing,
will not change your decision).

**Stale epoch** — a cache whose contents come from a different time period than
the storm it is named for, because the endpoint it came from serves only recent
data and ignores the date requested.

**Stub replay** — the state where no preprocessed imagery exists, so detection
returns the stored answer wholesale without reading any other source.

---

Back to the [index](README.md).
