#!/usr/bin/env python3
"""Evaluate chunks using the LangGraph evaluator.

This script loads chunks from chunks.jsonl, runs them through the
LangGraph evaluation pipeline, and saves results to evaluations.jsonl.

Usage:
    python scripts/evaluate_with_langgraph.py [OPTIONS]

Options:
    --limit N       Only process first N chunks
    --verbose       Enable verbose logging
"""

import json
import sys
from pathlib import Path

import typer
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from graphs.evaluator_graph import evaluate_chunk
from graphs.state import ChunkData
from src.config import settings
from src.utils import setup_logging

app = typer.Typer()


def load_chunks(jsonl_path: Path) -> list[ChunkData]:
    """Load chunks from JSONL file.

    Args:
        jsonl_path: Path to chunks.jsonl.

    Returns:
        List of ChunkData dictionaries.
    """
    chunks = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
                # Ensure all required fields
                chunk_data: ChunkData = {
                    "artifact_id": chunk.get("artifact_id", ""),
                    "chunk_id": chunk.get("chunk_id", ""),
                    "district": chunk.get("district", ""),
                    "meeting_date": chunk.get("meeting_date") or None,
                    "source_url": chunk.get("source_url", ""),
                    "board_page_url": chunk.get("board_page_url", ""),
                    "text": chunk.get("text", ""),
                }
                chunks.append(chunk_data)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse chunk: {e}")
                continue
    return chunks


def load_existing_evaluations(jsonl_path: Path) -> set[str]:
    """Load existing evaluation chunk IDs to avoid re-processing.

    Returns:
        Set of chunk_ids that have been evaluated.
    """
    if not jsonl_path.exists():
        return set()

    evaluated = set()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                evaluated.add(record.get("chunk_id", ""))
            except json.JSONDecodeError:
                continue
    return evaluated


@app.command()
def main(
    limit: int = typer.Option(0, "--limit", help="Limit chunks to evaluate"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Reprocess all chunks"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Evaluate chunks using the LangGraph evaluator pipeline."""
    # Setup logging
    setup_logging("evaluate_with_langgraph" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting LangGraph evaluation...")

    # Check for chunks file
    if not settings.chunks_jsonl.exists():
        logger.error(f"Chunks file not found: {settings.chunks_jsonl}")
        logger.error("Run extract_and_chunk.py first.")
        raise typer.Exit(1)

    # Load chunks
    chunks = load_chunks(settings.chunks_jsonl)
    if not chunks:
        logger.warning("No chunks found to evaluate.")
        raise typer.Exit(0)

    logger.info(f"Loaded {len(chunks)} chunks")

    # Apply limit
    if limit > 0:
        chunks = chunks[:limit]
        logger.info(f"Limited to {limit} chunks")

    # Load existing evaluations
    evaluated_ids = set() if reprocess else load_existing_evaluations(settings.evaluations_jsonl)
    logger.info(f"Found {len(evaluated_ids)} already evaluated chunks")

    # Filter out already evaluated
    chunks_to_evaluate = [c for c in chunks if c["chunk_id"] not in evaluated_ids]
    logger.info(f"{len(chunks_to_evaluate)} chunks to evaluate")

    if not chunks_to_evaluate:
        logger.info("No new chunks to evaluate.")
        raise typer.Exit(0)

    # Ensure output directory exists
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    # Open evaluations file in append mode
    mode = "w" if reprocess else "a"
    eval_file = open(settings.evaluations_jsonl, mode, encoding="utf-8")

    kept_count = 0
    error_count = 0

    try:
        for i, chunk in enumerate(chunks_to_evaluate, 1):
            logger.info(f"[{i}/{len(chunks_to_evaluate)}] Evaluating: {chunk['chunk_id']}")

            try:
                # Run through LangGraph
                final_state = evaluate_chunk(chunk)

                # Create evaluation record
                eval_record = {
                    "chunk_id": chunk["chunk_id"],
                    "artifact_id": chunk["artifact_id"],
                    "district": chunk["district"],
                    "keep": final_state.get("keep", False),
                    "errors": final_state.get("errors", []),
                }

                # Add classification if present
                classification = final_state.get("classification")
                if classification:
                    eval_record["classification"] = classification

                # Add scoring if present
                scoring = final_state.get("scoring")
                if scoring:
                    eval_record["scoring"] = scoring

                # Add signal_record if present (for kept signals)
                signal_record = final_state.get("signal_record")
                if signal_record:
                    eval_record["signal_record"] = signal_record
                    kept_count += 1
                    logger.info(
                        f"  KEPT: score={signal_record.get('opportunity_score')}, "
                        f"category={signal_record.get('category')}"
                    )
                else:
                    logger.debug(f"  DROPPED")

                # Write to file
                eval_file.write(json.dumps(eval_record) + "\n")
                eval_file.flush()  # Ensure progress is saved

            except Exception as e:
                logger.error(f"  ERROR: {e}")
                error_count += 1
                # Write error record
                eval_record = {
                    "chunk_id": chunk["chunk_id"],
                    "artifact_id": chunk["artifact_id"],
                    "district": chunk["district"],
                    "keep": False,
                    "errors": [str(e)],
                }
                eval_file.write(json.dumps(eval_record) + "\n")
                eval_file.flush()

    finally:
        eval_file.close()

    logger.info(
        f"Evaluation complete. "
        f"Kept: {kept_count}, Dropped: {len(chunks_to_evaluate) - kept_count - error_count}, "
        f"Errors: {error_count}"
    )


if __name__ == "__main__":
    app()
