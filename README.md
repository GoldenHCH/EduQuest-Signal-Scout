# Utah Board Signal Scout

Automated detection of buying signals from Utah K-12 school board meetings using LangGraph.

---

## Overview

Utah Board Signal Scout is a GTM intelligence system that identifies **early-stage buying signals from Utah school districts** by analyzing publicly available school board meeting agendas, minutes, and packets.

District purchasing conversations about curriculum adoption, instructional technology, pilots, and learning gaps often appear in board meetings **months before** an RFP or vendor outreach. Signal Scout surfaces these signals automatically, classifies their relevance, and converts them into actionable sales opportunities.

**Key Features:**
- Automated board page discovery from district websites
- PDF artifact downloading and text extraction
- LangGraph-based agentic evaluation pipeline
- Intent classification with evidence validation
- Opportunity scoring (0-100)
- Weekly automated runs via cron

---

## Quick Start

### 1. Install Dependencies

```bash
cd EduQuest-Signal-Scout
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your OpenAI API key:
# OPENAI_API_KEY=sk-your-api-key-here
```

### 3. Run the Pipeline

**Full pipeline (all districts):**
```bash
python scripts/run_weekly.py
```

**Limited test run (recommended for first run):**
```bash
python scripts/run_weekly.py --limit-districts 5 --limit-docs 3
```

### 4. View Results

After running, check the outputs:
- `data/outputs/signals.csv` - All detected signals
- `data/outputs/signals.json` - JSON format
- `data/outputs/top_signals.md` - Human-readable report
- `data/logs/` - Execution logs

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Weekly Pipeline                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. DISCOVER         2. FETCH            3. EXTRACT                  │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐             │
│  │ District     │──▶│ Board Page   │──▶│ PDF Text     │             │
│  │ Websites     │   │ PDFs         │   │ Chunks       │             │
│  └──────────────┘   └──────────────┘   └──────────────┘             │
│                                               │                      │
│                                               ▼                      │
│  5. EXPORT           4. EVALUATE (LangGraph)                        │
│  ┌──────────────┐   ┌────────────────────────────────────┐          │
│  │ signals.csv  │◀──│ classify → validate → score →      │          │
│  │ signals.json │   │           normalize → decide       │          │
│  │ top_signals  │   └────────────────────────────────────┘          │
│  └──────────────┘                                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## LangGraph Evaluator

The core evaluation is implemented as a LangGraph state machine with typed state:

```
START → classify → validate_evidence → [decision_router]
                                          ├─ score → [final_router] → normalize → END
                                          │                         → drop → END
                                          ├─ drop → END
                                          └─ error_handler → END
```

**Nodes:**
- `classify_node` - LLM classification into intent categories
- `evidence_validation_node` - Verify evidence is exact substring
- `score_node` - Score opportunity 0-100
- `normalize_node` - Create export record
- `decision_router` - Route based on category/confidence
- `final_decision_router` - Route based on score

---

## Intent Categories

**High-Intent Signals:**
- `curriculum_adoption` - Curriculum review/adoption cycles
- `instructional_materials` - Textbook/resource selection
- `pilot_evaluation` - Program pilots and evaluations
- `budget_allocation` - EdTech budget discussions
- `vendor_dissatisfaction` - Complaints about current vendors

**Medium-Intent Signals:**
- `learning_gaps` - Learning loss/achievement gaps
- `personalization_pbl` - Personalized/project-based learning
- `strategic_plan` - Strategic planning with tech focus
- `teacher_workload` - Teacher efficiency/burnout

---

## Directory Structure

```
EduQuest-Signal-Scout/
├── graphs/
│   ├── state.py              # TypedDict state definitions
│   ├── nodes.py              # Node function implementations
│   ├── evaluator_graph.py    # LangGraph graph definition
│   └── prompts/              # LLM prompt templates
├── scripts/
│   ├── discover_board_pages.py
│   ├── fetch_artifacts.py
│   ├── extract_and_chunk.py
│   ├── evaluate_with_langgraph.py
│   ├── export_signals.py
│   ├── run_weekly.py
│   ├── install_cron.sh
│   └── uninstall_cron.sh
├── src/
│   ├── config.py             # Configuration management
│   ├── llm.py                # LLM provider abstraction
│   └── utils.py              # Utility functions
├── data/
│   ├── utah_districts.csv    # District seed data
│   ├── raw_docs/             # Downloaded PDFs
│   ├── extracted_text/       # Extracted text files
│   ├── outputs/              # Pipeline outputs
│   └── logs/                 # Execution logs
├── requirements.txt
├── .env.example
└── README.md
```

---

## Configuration

Environment variables (set in `.env`):

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key (required) | - |
| `OPENAI_MODEL` | Model for classification/scoring | `gpt-4o` |
| `MAX_DOCS_PER_DISTRICT` | Max PDFs to download per district | `10` |
| `CHUNK_SIZE_TOKENS` | Tokens per chunk | `1200` |
| `CHUNK_OVERLAP_TOKENS` | Overlap between chunks | `100` |
| `CONFIDENCE_THRESHOLD` | Min confidence to score | `0.7` |
| `SCORE_THRESHOLD` | Min score to keep | `50` |

---

## Scheduling

### Install Weekly Cron (Sunday 9pm)

```bash
./scripts/install_cron.sh
```

### Uninstall Cron

```bash
./scripts/uninstall_cron.sh
```

### View Cron Jobs

```bash
crontab -l
```

---

## Adding Districts

Edit `data/utah_districts.csv` to add districts:

```csv
district_name,website_url,board_page_url
My New District,https://mynewdistrict.org,
```

- Leave `board_page_url` empty for auto-discovery
- Or manually set it if you know the exact URL

To refresh all discovered URLs:
```bash
python scripts/discover_board_pages.py --refresh
```

---

## Output Format

### signals.csv / signals.json

| Field | Description |
|-------|-------------|
| `district` | School district name |
| `meeting_date` | Meeting date (if detected) |
| `category` | Intent category |
| `opportunity_score` | 0-100 score |
| `confidence` | Classification confidence |
| `recommended_next_step` | reach_out_now / research_more / monitor |
| `summary` | 2-3 sentence summary |
| `evidence_snippet` | Verbatim quote from document |
| `source_url` | Link to source PDF |

### top_signals.md

Human-readable report with:
- Ranked signals by score
- Evidence snippets
- Source links
- Recommended actions

---

## Limitations

- **Site Variability**: Not all district websites are easily crawlable
- **PDF Quality**: Some PDFs are scanned images without text
- **Date Detection**: Meeting dates aren't always parseable
- **Rate Limits**: Polite scraping (1s delay) means full runs take time
- **LLM Costs**: Each chunk requires 2 LLM calls (classify + score)

---

## Development

### Run Individual Scripts

```bash
# Discover board pages only
python scripts/discover_board_pages.py --limit 5

# Fetch artifacts only
python scripts/fetch_artifacts.py --limit-districts 5 --limit-docs 3

# Extract and chunk only
python scripts/extract_and_chunk.py --limit 10

# Evaluate only
python scripts/evaluate_with_langgraph.py --limit 10

# Export only
python scripts/export_signals.py
```

### Verbose Logging

Add `--verbose` to any script for debug output.

---

## License

This project was created for the 2026 GTM Hackathon by Mobly.
