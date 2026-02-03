#!/usr/bin/env python3
"""Export evaluated signals to CSV, JSON, and Markdown formats.

This script reads evaluations.jsonl, filters to kept signals, deduplicates,
and exports to multiple formats.

Usage:
    python scripts/export_signals.py [OPTIONS]

Options:
    --top N         Number of signals for top_signals.md (default: 20)
    --verbose       Enable verbose logging
"""

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import setup_logging, truncate_text

app = typer.Typer()


def load_evaluations(jsonl_path: Path) -> list[dict]:
    """Load evaluations from JSONL file.

    Args:
        jsonl_path: Path to evaluations.jsonl.

    Returns:
        List of evaluation records.
    """
    evaluations = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                evaluations.append(record)
            except json.JSONDecodeError:
                continue
    return evaluations


def extract_signals(evaluations: list[dict]) -> list[dict]:
    """Extract kept signals from evaluations.

    Args:
        evaluations: List of evaluation records.

    Returns:
        List of signal records.
    """
    signals = []
    for eval_record in evaluations:
        if eval_record.get("keep") and eval_record.get("signal_record"):
            signals.append(eval_record["signal_record"])
    return signals


def deduplicate_signals(signals: list[dict]) -> list[dict]:
    """Deduplicate signals by (artifact_id, category, evidence_snippet).

    Keeps the highest scoring signal for each unique combination.

    Args:
        signals: List of signal records.

    Returns:
        Deduplicated list of signals.
    """
    # Group by dedup key
    groups: dict[tuple, list[dict]] = {}
    for signal in signals:
        key = (
            signal.get("artifact_id", ""),
            signal.get("category", ""),
            signal.get("evidence_snippet", "")[:100],  # First 100 chars for matching
        )
        if key not in groups:
            groups[key] = []
        groups[key].append(signal)

    # Keep highest scoring in each group
    deduped = []
    for group in groups.values():
        best = max(group, key=lambda s: s.get("opportunity_score", 0))
        deduped.append(best)

    return deduped


def export_csv(signals: list[dict], csv_path: Path) -> None:
    """Export signals to CSV.

    Args:
        signals: List of signal records.
        csv_path: Output path.
    """
    if not signals:
        logger.warning("No signals to export to CSV")
        return

    fieldnames = [
        "district",
        "meeting_date",
        "category",
        "opportunity_score",
        "confidence",
        "recommended_next_step",
        "summary",
        "evidence_snippet",
        "source_url",
        "board_page_url",
        "artifact_id",
        "chunk_id",
        "rationale",
        "generated_at",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(signals)

    logger.info(f"Exported {len(signals)} signals to {csv_path}")


def export_json(signals: list[dict], json_path: Path) -> None:
    """Export signals to JSON.

    Args:
        signals: List of signal records.
        json_path: Output path.
    """
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(signals, f, indent=2, default=str)

    logger.info(f"Exported {len(signals)} signals to {json_path}")


def export_markdown(signals: list[dict], md_path: Path, top_n: int = 20) -> None:
    """Export top signals to Markdown.

    Args:
        signals: List of signal records (should be sorted by score).
        md_path: Output path.
        top_n: Number of top signals to include.
    """
    top_signals = signals[:top_n]

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Top Buying Signals - Utah School Board Meetings\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"**Total Signals Found:** {len(signals)}\n\n")
        f.write("---\n\n")

        for i, signal in enumerate(top_signals, 1):
            district = signal.get("district", "Unknown")
            score = signal.get("opportunity_score", 0)
            category = signal.get("category", "unknown")
            confidence = signal.get("confidence", 0)
            meeting_date = signal.get("meeting_date") or "Unknown"
            summary = signal.get("summary", "No summary available.")
            evidence = signal.get("evidence_snippet", "No evidence.")
            next_step = signal.get("recommended_next_step", "monitor")
            source_url = signal.get("source_url", "")

            # Format next step as badge
            step_emoji = {
                "reach_out_now": "🔥",
                "research_more": "🔍",
                "monitor": "👀",
            }.get(next_step, "")

            f.write(f"## {i}. {district}\n\n")
            f.write(f"**Score:** {score}/100 | ")
            f.write(f"**Category:** {category.replace('_', ' ').title()} | ")
            f.write(f"**Confidence:** {confidence:.0%}\n\n")
            f.write(f"**Meeting Date:** {meeting_date}\n\n")
            f.write(f"**Next Step:** {step_emoji} {next_step.replace('_', ' ').title()}\n\n")
            f.write(f"### Summary\n{summary}\n\n")
            f.write(f"### Evidence\n> {truncate_text(evidence, 500)}\n\n")
            if source_url:
                f.write(f"**Source:** [{truncate_text(source_url, 60)}]({source_url})\n\n")
            f.write("---\n\n")

        # Footer
        f.write("\n## About This Report\n\n")
        f.write(
            "This report was generated by **Utah Board Signal Scout**, "
            "an automated system that scans public school board meeting documents "
            "to identify early-stage buying signals for educational technology.\n\n"
        )
        f.write("**Scoring Criteria:**\n")
        f.write("- Intent Strength (0-25): Explicit RFP, evaluation, or discussion\n")
        f.write("- Time Window (0-25): Expected decision timeline\n")
        f.write("- EduQuest Fit (0-25): Alignment with personalized learning\n")
        f.write("- Evidence Quality (0-25): Clarity of documentation\n")

    logger.info(f"Exported top {len(top_signals)} signals to {md_path}")


@app.command()
def main(
    top: int = typer.Option(20, "--top", help="Number of signals for top_signals.md"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Export evaluated signals to CSV, JSON, and Markdown formats."""
    # Setup logging
    setup_logging("export_signals" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting signal export...")

    # Check for evaluations file
    if not settings.evaluations_jsonl.exists():
        logger.error(f"Evaluations file not found: {settings.evaluations_jsonl}")
        logger.error("Run evaluate_with_langgraph.py first.")
        raise typer.Exit(1)

    # Load evaluations
    evaluations = load_evaluations(settings.evaluations_jsonl)
    logger.info(f"Loaded {len(evaluations)} evaluation records")

    # Extract kept signals
    signals = extract_signals(evaluations)
    logger.info(f"Found {len(signals)} kept signals")

    if not signals:
        logger.warning("No signals to export.")
        # Create empty output files
        settings.signals_csv.write_text("")
        settings.signals_json.write_text("[]")
        settings.top_signals_md.write_text("# No Signals Found\n\nNo buying signals were detected.")
        raise typer.Exit(0)

    # Deduplicate
    signals = deduplicate_signals(signals)
    logger.info(f"After deduplication: {len(signals)} unique signals")

    # Sort by score (descending)
    signals.sort(key=lambda s: s.get("opportunity_score", 0), reverse=True)

    # Export
    export_csv(signals, settings.signals_csv)
    export_json(signals, settings.signals_json)
    export_markdown(signals, settings.top_signals_md, top_n=top)

    logger.info("Export complete!")


if __name__ == "__main__":
    app()
