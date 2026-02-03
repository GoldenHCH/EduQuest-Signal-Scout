---
marp: true
paginate: true
theme: default
---

<!--
Utah Board Signal Scout — Pitch Deck

How to use:
- Option A (fast): Copy/paste each slide into Google Slides / Keynote.
- Option B (nice): Render with Marp (VS Code Marp extension or `marp` CLI) and export PDF/PPTX.
-->

## Utah Board Signal Scout
### Turn school board meetings into qualified pipeline — before the RFP exists

**GTM intelligence for Utah K‑12**  
LangGraph-powered detection of early buying signals from agendas, minutes, and board packets

---

## The problem
School districts signal intent **months before** an RFP:
- Curriculum adoption cycles
- EdTech pilots and evaluations
- Budget allocations
- Vendor dissatisfaction
- Strategic plans and learning gaps

But these signals are buried across **hundreds of PDFs** on inconsistent district websites.  
Most teams find out too late—after the shortlist is formed.

---

## The stakes (why now)
EdTech selling is a timing game:
- **Pre‑RFP** = shape requirements, build relationships, influence pilots
- **Post‑RFP** = compete on price + procurement checklists

Today, “monitor the board” is manual, unreliable, and doesn’t scale past a handful of districts.

---

## The solution
**Utah Board Signal Scout** automatically:
- Discovers district board pages
- Downloads meeting artifacts (PDFs)
- Extracts and chunks text
- Uses a LangGraph evaluator to **classify → validate evidence → score → decide**
- Exports ranked opportunities with **verbatim quotes + source links**

Result: a weekly feed of “who to call and why” for district GTM.

---

## Product (what you get)
1) **Signals dataset** (`signals.csv` / `signals.json`)
- District, meeting date, category, confidence, opportunity score (0–100)
- Summary + rationale
- Evidence snippet (verbatim) + source URL
- Recommended next step: `reach_out_now` / `research_more` / `monitor`

2) **Human-readable report** (`top_signals.md`)
- Ranked highlights, evidence, and actions

3) **Streamlit viewer**
- Filter by score/category/district/action
- Expand to see summaries and evidence; download filtered CSV/JSON

---

## Real output (example)
From `data/outputs/top_signals.md` (generated 2026‑02‑03):
- **Total signals found:** 11
- **Top signal:** Canyons School District — *Score 78/100* — **Curriculum Adoption** — *93% confidence*
- Evidence includes named vendors + scope:
  - “K‑12 Math Curriculum Adoption Proposal (Second Reading)… Elementary (Amplify Desmos)… Middle/High (Reveal Math 2025, McGraw Hill)”

This is exactly the moment to position complementary tools and support implementation.

---

## Why we win (quality + trust)
Most “AI lead gen” fails because it can’t show receipts.

Signal Scout is built to be **defensible and actionable**:
- **Evidence validation**: the quote must be an exact substring of the source text
- **Opportunity scoring**: intent, timing window, product fit, evidence quality
- **Source links**: every signal ties back to the public artifact for instant verification

---

## How it works (architecture)
Weekly pipeline:
- Discover → Fetch → Extract/Chunk → Evaluate (LangGraph) → Export

Evaluator graph:
START → classify → validate_evidence → route  
→ score → final_route → normalize → END

Built for automation:
- Runs weekly via cron
- Produces stable, auditable outputs for sales ops workflows

---

## Customer + use cases
**Who pays:**
- EdTech GTM teams (founders, AEs, SDRs, sales ops)
- Curriculum publishers + service providers selling into districts

**What they do with it:**
- Build territory plans from real board discussions
- Prioritize outreach with evidence-backed context
- Track adoption cycles and pilots across a state (and soon, nationally)

---

## Market expansion
Beachhead: **Utah districts** (highly accessible public board artifacts)

Expansion path:
- Add more states + districts (seed list + automated discovery)
- Add board packet sources and meeting types
- Add integrations: Slack/email alerts, CRM enrichment, sequencing triggers

Long-term: become the “pre‑RFP intent layer” for public-sector education GTM.

---

## Competitive landscape
Alternatives today:
- Manual monitoring (Google alerts, board calendars, interns)
- RFP trackers (often **too late**)
- Generic web scrapers (no intent model, low trust, no scoring)

Signal Scout differentiation:
- **Pre‑RFP intent detection**
- **Receipts-first** evidence + source links
- Structured scoring + next-step recommendations

---

## Traction (current)
Working end-to-end system with:
- Automated discovery + artifact fetching
- LLM evaluation with evidence validation
- Exports + Streamlit demo UI

Concrete example output includes:
- “Reach out now” signals tied to active curriculum adoption and measurable spend lines

Next: broaden district coverage and quantify time-to-first-meeting uplift vs control territories.

---

## Roadmap
Near-term:
- OCR for scanned PDFs + better date extraction
- Deduping + entity extraction (program names, vendors, budgets, timelines)
- Alerting (weekly digest + “high score” real-time notifications)

Mid-term:
- Multi-state scaling + monitoring coverage metrics
- CRM push (HubSpot/Salesforce) + territory ownership + collaboration

---

## The ask
Looking for:
- **Pilot design partners**: 3–5 GTM teams selling into K‑12 districts
- **Distribution**: partners with multi-state education sales coverage
- Optional: seed funding to accelerate scaling + integrations

Success metric for pilots: more qualified conversations **before** the RFP window.

