# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

EduQuest Signal Scout is a GTM intelligence prototype for the 2026 GTM Hackathon by Mobly. It detects early-stage buying signals from K-12 school districts by analyzing publicly available school board meeting agendas, minutes, and packets to surface pre-RFP buying intent.

**Current Status**: Prototype-stage with README documentation only - implementation not yet started.

## Planned Tech Stack

- **Language**: Python
- **LLM**: OpenAI API or similar
- **PDF Processing**: pdfplumber or pypdf
- **Orchestration**: n8n or scripts
- **UI**: Lovable or Streamlit
- **Storage**: CSV / Google Sheets / Notion

## Architecture

Pipeline-based signal detection flow:

```
Input (District URLs) → Ingestion (PDF/HTML download) → Extraction (text conversion) → Chunking (by agenda items) → Reasoning (LLM classification + scoring) → Output (ranked signal table)
```

## Intent Classification System

**High-Intent Signals** (strongest buying indicators):
- Curriculum adoption or review
- Instructional materials selection
- Pilot or program evaluation
- Budget allocation for instructional technology
- Vendor dissatisfaction

**Medium-Intent Signals**:
- Learning loss/learning gaps
- Personalized or project-based learning initiatives
- Strategic plan updates
- Teacher workload or engagement challenges

## Opportunity Scoring

Signals are scored 0-100 based on: intent category, timing signals, evidence strength, and EduQuest product fit.

## Output Format

Each detected signal includes: district name, meeting date, intent category, opportunity score, summary, evidence snippet, and recommended next steps.
