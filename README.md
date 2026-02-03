# EduQuest Signal Scout

Early District Buying-Intent Detection from Public Board Meetings

---

## Overview

EduQuest Signal Scout is a GTM intelligence prototype that helps EduQuest identify **early-stage buying signals from K–12 school districts** by analyzing publicly available school board meeting agendas, minutes, and packets.

District purchasing conversations about curriculum adoption, instructional technology, pilots, and learning gaps often appear in board meetings **months before** an RFP or vendor outreach. Signal Scout surfaces these signals automatically, classifies their relevance, and converts them into actionable sales opportunities.

This project was designed as a build-first GTM prototype for the 2026 GTM Hackathon by Mobly.

---

## Problem

Early-stage EdTech teams struggle to:

- Discover districts entering curriculum review or adoption cycles  
- Detect buying intent before RFPs are published  
- Monitor hundreds of district board pages manually  
- Prioritize outreach using real evidence  

Most outbound tools rely on firmographics, keywords, or engagement tracking — **not upstream institutional decision signals**.

---

## Solution

Signal Scout continuously scans district board-meeting artifacts and:

1. Extracts agenda and minutes text  
2. Classifies agenda items into intent categories  
3. Scores opportunity strength and timing  
4. Provides evidence snippets  
5. Generates recommended next steps and outreach angles  

Result: a ranked pipeline of districts showing **pre-RFP buying intent**.

---

## Core Features

- Board agenda & minutes ingestion (PDF / HTML)
- LLM-based agenda item classification
- Buying-intent scoring (0–100)
- Evidence-backed summaries
- EduQuest-fit reasoning
- Pipeline export (CSV / Sheets / Notion)
- Optional personalized outreach draft

---

## Intent Categories

High-Intent Signals

- Curriculum adoption or review  
- Instructional materials selection  
- Pilot or program evaluation  
- Budget allocation for instructional technology  
- Vendor dissatisfaction  

Medium-Intent Signals

- Learning loss / learning gaps  
- Personalized or project-based learning initiatives  
- Strategic plan updates  
- Teacher workload or engagement challenges  

---

## Example Output

District: Alpine School District  
Meeting Date: Jan 15, 2026  
Category: Curriculum Adoption  
Opportunity Score: 87  

Summary  
Board discussion on initiating a district-wide math curriculum review focused on student engagement and alignment with personalized instruction models.

Evidence Snippet  
"...administration recommends forming a committee to evaluate alternative math instructional programs that better support personalized and project-based learning..."

Recommended Next Step  
Contact Director of Curriculum to introduce EduQuest as a personalized, quest-driven pilot solution.

---

## Architecture

High-level Flow

Input  
→ District board URLs  

Ingestion  
→ Download PDFs / scrape HTML  

Extraction  
→ Convert documents to text  

Chunking  
→ Split by agenda items  

Reasoning  
→ Classify + score + summarize  

Output  
→ Signal table + drill-down + export  

---

## Tech Stack (Suggested)

- Python  
- OpenAI API or similar LLM  
- PDF text extraction (pdfplumber / pypdf)  
- Simple workflow orchestration (n8n or scripts)  
- Lightweight UI (Lovable or Streamlit)  
- Storage: CSV / Google Sheets / Notion  

---

## Repository Structure

