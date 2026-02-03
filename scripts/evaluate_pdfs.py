#!/usr/bin/env python3
"""Evaluate PDFs directly using LLM with file upload.

This script loads artifacts from artifacts.csv, sends each PDF directly to
the LLM API for analysis, and saves results to evaluations.jsonl.

This replaces the extract_and_chunk.py + evaluate_with_langgraph.py pipeline
with a single step that uploads PDFs directly to the LLM.

Usage:
    python scripts/evaluate_pdfs.py [OPTIONS]

Options:
    --limit N       Only process first N PDFs
    --reprocess     Reprocess all PDFs (ignore existing evaluations)
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

from graphs.state import SignalRecord
from src.config import settings
from src.llm import invoke_llm_with_pdf
from src.utils import setup_logging

app = typer.Typer()

# Load prompt template
PROMPTS_DIR = Path(__file__).parent.parent / "graphs" / "prompts"


def load_prompt() -> str:
    """Load the PDF signal prompt template."""
    prompt_path = PROMPTS_DIR / "pdf_signal_prompt.txt"
    return prompt_path.read_text()


def load_artifacts(csv_path: Path) -> list[dict]:
    """Load artifacts from CSV.

    Args:
        csv_path: Path to artifacts.csv.

    Returns:
        List of artifact dictionaries.
    """
    if not csv_path.exists():
        return []

    artifacts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            artifacts.append(dict(row))
    return artifacts


def load_existing_evaluations(jsonl_path: Path) -> set[str]:
    """Load existing evaluation artifact IDs to avoid re-processing.

    Returns:
        Set of artifact_ids that have been evaluated.
    """
    if not jsonl_path.exists():
        return set()

    evaluated = set()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                evaluated.add(record.get("artifact_id", ""))
            except json.JSONDecodeError:
                continue
    return evaluated


def normalize_signal(
    signal: dict,
    artifact: dict,
    signal_idx: int,
) -> tuple[dict, dict, SignalRecord]:
    """Normalize a raw signal from LLM into classification, scoring, and signal_record.

    Args:
        signal: Raw signal dict from LLM response.
        artifact: Artifact metadata from artifacts.csv.
        signal_idx: Index of this signal within the PDF.

    Returns:
        Tuple of (classification, scoring, signal_record).
    """
    artifact_id = artifact["artifact_id"]
    chunk_id = f"{artifact_id}_pdfsig_{signal_idx:03d}"

    # Build classification result
    classification = {
        "category": signal.get("category", "none"),
        "confidence": float(signal.get("confidence", 0.0)),
        "evidence_snippet": signal.get("evidence_snippet", ""),
        "rationale": signal.get("rationale", ""),
    }

    # Build score breakdown
    score_breakdown = signal.get("score_breakdown", {})
    scoring = {
        "opportunity_score": int(signal.get("opportunity_score", 0)),
        "score_breakdown": {
            "intent_strength": int(score_breakdown.get("intent_strength", 0)),
            "time_window": int(score_breakdown.get("time_window", 0)),
            "eduquest_fit": int(score_breakdown.get("eduquest_fit", 0)),
            "evidence_quality": int(score_breakdown.get("evidence_quality", 0)),
        },
        "summary": signal.get("summary", ""),
        "recommended_next_step": signal.get("recommended_next_step", "monitor"),
    }

    # Build signal record
    signal_record: SignalRecord = {
        "chunk_id": chunk_id,
        "artifact_id": artifact_id,
        "district": artifact.get("district", ""),
        "meeting_date": artifact.get("inferred_meeting_date") or None,
        "source_url": artifact.get("source_url", ""),
        "board_page_url": artifact.get("board_page_url", ""),
        "category": classification["category"],
        "confidence": classification["confidence"],
        "opportunity_score": scoring["opportunity_score"],
        "evidence_snippet": classification["evidence_snippet"],
        "summary": scoring["summary"],
        "recommended_next_step": scoring["recommended_next_step"],
        "rationale": classification["rationale"],
        "generated_at": datetime.now().isoformat(),
    }

    return classification, scoring, signal_record


def should_keep_signal(
    classification: dict,
    scoring: dict,
    confidence_threshold: float,
    score_threshold: int,
) -> bool:
    """Determine if a signal should be kept based on thresholds.

    Mirrors the logic in graphs.nodes.final_decision_router.

    Args:
        classification: Classification result.
        scoring: Scoring result.
        confidence_threshold: Minimum confidence to keep.
        score_threshold: Minimum score to keep.

    Returns:
        True if signal should be kept.
    """
    # Drop if category is "none"
    if classification["category"] == "none":
        return False

    # Drop if confidence is below threshold
    if classification["confidence"] < confidence_threshold:
        return False

    # Keep if score is high enough OR recommended to reach out now
    if (
        scoring["opportunity_score"] >= score_threshold
        or scoring["recommended_next_step"] == "reach_out_now"
    ):
        return True

    return False


@app.command()
def main(
    limit: int = typer.Option(0, "--limit", help="Limit PDFs to evaluate"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Reprocess all PDFs"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Evaluate PDFs directly using LLM with file upload."""
    # Setup logging
    setup_logging("evaluate_pdfs" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting direct PDF evaluation...")

    # Check for artifacts file
    if not settings.artifacts_csv.exists():
        logger.error(f"Artifacts file not found: {settings.artifacts_csv}")
        logger.error("Run fetch_artifacts.py first.")
        raise typer.Exit(1)

    # Load artifacts
    artifacts = load_artifacts(settings.artifacts_csv)
    if not artifacts:
        logger.warning("No artifacts found. Run fetch_artifacts.py first.")
        raise typer.Exit(0)

    logger.info(f"Loaded {len(artifacts)} artifacts")

    # Apply limit
    if limit > 0:
        artifacts = artifacts[:limit]
        logger.info(f"Limited to {limit} artifacts")

    # Load existing evaluations
    evaluated_ids = set() if reprocess else load_existing_evaluations(settings.evaluations_jsonl)
    logger.info(f"Found {len(evaluated_ids)} already evaluated artifacts")

    # Filter out already evaluated
    artifacts_to_evaluate = [a for a in artifacts if a["artifact_id"] not in evaluated_ids]
    logger.info(f"{len(artifacts_to_evaluate)} artifacts to evaluate")

    if not artifacts_to_evaluate:
        logger.info("No new artifacts to evaluate.")
        raise typer.Exit(0)

    # Ensure output directory exists
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    # Load prompt
    prompt = load_prompt()
    logger.debug(f"Loaded prompt: {len(prompt)} chars")

    # Open evaluations file in append mode
    mode = "w" if reprocess else "a"
    eval_file = open(settings.evaluations_jsonl, mode, encoding="utf-8")

    total_signals_kept = 0
    total_signals_dropped = 0
    error_count = 0

    try:
        for i, artifact in enumerate(artifacts_to_evaluate, 1):
            artifact_id = artifact["artifact_id"]
            file_path = Path(artifact["file_path"])

            logger.info(f"[{i}/{len(artifacts_to_evaluate)}] Evaluating: {artifact_id}")

            # Check file exists
            if not file_path.exists():
                logger.warning(f"  File not found: {file_path}")
                # Write error record
                eval_record = {
                    "chunk_id": f"{artifact_id}_pdfsig_000",
                    "artifact_id": artifact_id,
                    "district": artifact.get("district", ""),
                    "keep": False,
                    "errors": [f"File not found: {file_path}"],
                }
                eval_file.write(json.dumps(eval_record) + "\n")
                eval_file.flush()
                error_count += 1
                continue

            try:
                # Call LLM with PDF
                signals = invoke_llm_with_pdf(file_path, prompt)

                # Ensure we got a list
                if not isinstance(signals, list):
                    logger.warning(f"  Unexpected response type: {type(signals)}, treating as single signal")
                    signals = [signals] if signals else []

                logger.info(f"  Found {len(signals)} signals")

                if not signals:
                    # No signals found - write a single record for traceability
                    eval_record = {
                        "chunk_id": f"{artifact_id}_pdfsig_000",
                        "artifact_id": artifact_id,
                        "district": artifact.get("district", ""),
                        "keep": False,
                        "errors": [],
                    }
                    eval_file.write(json.dumps(eval_record) + "\n")
                    eval_file.flush()
                    continue

                # Process each signal
                for idx, signal in enumerate(signals):
                    classification, scoring, signal_record = normalize_signal(
                        signal, artifact, idx
                    )

                    # Determine if we should keep this signal
                    keep = should_keep_signal(
                        classification,
                        scoring,
                        settings.confidence_threshold,
                        settings.score_threshold,
                    )

                    # Build evaluation record
                    eval_record = {
                        "chunk_id": signal_record["chunk_id"],
                        "artifact_id": artifact_id,
                        "district": artifact.get("district", ""),
                        "keep": keep,
                        "errors": [],
                        "classification": classification,
                        "scoring": scoring,
                    }

                    if keep:
                        eval_record["signal_record"] = signal_record
                        total_signals_kept += 1
                        logger.info(
                            f"  KEPT signal {idx}: score={scoring['opportunity_score']}, "
                            f"category={classification['category']}"
                        )
                    else:
                        total_signals_dropped += 1
                        logger.debug(
                            f"  DROPPED signal {idx}: score={scoring['opportunity_score']}, "
                            f"confidence={classification['confidence']:.2f}"
                        )

                    # Write to file
                    eval_file.write(json.dumps(eval_record) + "\n")
                    eval_file.flush()

            except Exception as e:
                logger.error(f"  ERROR: {e}")
                error_count += 1
                # Write error record
                eval_record = {
                    "chunk_id": f"{artifact_id}_pdfsig_000",
                    "artifact_id": artifact_id,
                    "district": artifact.get("district", ""),
                    "keep": False,
                    "errors": [str(e)],
                }
                eval_file.write(json.dumps(eval_record) + "\n")
                eval_file.flush()

    finally:
        eval_file.close()

    logger.info(
        f"Evaluation complete. "
        f"Kept: {total_signals_kept}, Dropped: {total_signals_dropped}, "
        f"Errors: {error_count}"
    )


if __name__ == "__main__":
    app()
