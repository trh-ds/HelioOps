### 1. The Core Problem & The "Why"

When the sun shoots out massive bursts of energy (a solar storm), it messes with technology on Earth. The government issues alerts about this, but they are written for scientists, not business operators.

* 
*The Simple Concept:* The alerts are full of complicated physics equations and measurements.


* 
*The Jargon:* The *NOAA* (National Oceanic and Atmospheric Administration) *SWPC* (Space Weather Prediction Center) issues these alerts. They use terms like *Kp indices, **G-scale classifications, and **solar proton flux*.


* 
*The Simple Concept:* The people who actually run businesses don't understand the physics; they just need to know what safety rules to follow.


* 
*The Jargon:* Operations teams speak in the language of industry regulations, like *ICAO procedures* (aviation rules), *NERC standards* (power grid rules), and *GMDSS protocols* (maritime communication rules).



Because these two groups speak different languages, it currently takes expensive specialists 2 to 4 hours to translate the warnings manually. HelioOps fixes this by acting as an "AI-native space weather intelligence platform" that translates the physics into an action plan in under three minutes.

### 2. The Real-World Danger (The Case Study)

To prove why this software is needed, the document uses a real event from May 2024.

* 
*The Simple Concept:* A massive solar storm hit Earth, causing hundreds of planes to change course, messing up GPS, and threatening electrical grids.


* 
*The Jargon:* This was a *G4/G5 peak storm* with a *Kp=9* (these are the maximum severity scores for space weather). It caused 500+ flight diversions, degraded *L1 civilian receivers* (GPS) by 15-40 meters, and caused *HF radio blackouts* (high-frequency communication failures).



### 3. Who Uses This? (Target Personas)

The document outlines four main types of users who desperately need this translation tool:

| Simple Concept | The Professional User | The Jargon / Their Specific Needs |
| --- | --- | --- |
| *Airlines* | Flight Dispatch Supervisor | They need to know which *HF backup frequencies* to use because normal radios fail over the North Pole.

 |
| *Power Grids* | Grid Operations Engineer | They need to protect massive electrical transformers from *GIC* (Geomagnetically Induced Currents) to comply with *NERC GMD* safety rules.

 |
| *Telecom / Tech* | NOC (Network Operations Center) Lead | They need to warn clients about *GPS accuracy degradation* and *satellite uplink fade* (loss of signal).

 |
| *Shipping* | Fleet Operations Manager | They need to know when their emergency ship radios (*GMDSS HF) or tracking systems (AIS*) might break.

 |

### 4. The Core Features (How it actually works)

The engineers break down the software into specific "Features" (labeled as F-01, F-02, etc.). Here is the step-by-step pipeline:

* *The Simple Concept:* The software constantly checks the government website for new warnings.
* 
*The Jargon: F-01 Storm Detection:* The system *polls* (checks) the NOAA APIs every 5 minutes to look for a specific trigger, like a *Kp >= 5.0* (a level 1 storm).


* *The Simple Concept:* If a storm is found, the AI reads it and figures out how bad it is and when it will hit Earth.
* 
*The Jargon: F-02 Event Classification:* An AI parses the text and wind speed to create a *structured StormEvent object* that includes the estimated Earth arrival time and a *peak impact window*.


* *The Simple Concept:* The system decides which industries are actually in danger based on the storm's severity.
* 
*The Jargon: F-03 Industry Impact Routing:* A *deterministic matrix* maps the storm scale to severity tiers; for example, a G3 storm triggers Aviation and Grid as "CRITICAL".


* *The Simple Concept:* The AI acts as a specialist for each industry, writing a custom safety checklist.
* 
*The Jargon: F-04 / F-05 Industry Advisory Agents:* Dedicated AI nodes retrieve rulebooks from a database and generate an *AdvisoryOutput, which must include an **action_items* numbered list and specific time windows.


* *The Simple Concept:* Finally, it sends the checklist to the human operators so they can approve it and get to work.
* 
*The Jargon: F-06 Advisory Delivery & CRM:* A *Delivery Agent* creates a *CRM ticket* (a tracking log) and sends alerts via Slack or email, logging everything in an *audit trail*.



### 5. Success Metrics (How they know it worked)

The company has strict goals to know if the software is a success.

* 
*Product Goal:* Time from the government alert to the final advisory being delivered must be *< 3 minutes*.


* 
*Business Goal:* Zylon Labs aims to sign *5 active paying clients* by the end of Year 1.


* 
*Financial Goal:* They want an *ARR* (Annual Recurring Revenue) of 2,000,000 SEK (Swedish Krona).