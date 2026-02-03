#!/usr/bin/env python3
"""Extract text from PDFs and chunk into processable segments.

This script extracts text from downloaded PDF artifacts using pdfplumber
(with pypdf fallback), saves full text, and creates chunks for evaluation.

Usage:
    python scripts/extract_and_chunk.py [OPTIONS]

Options:
    --limit N       Only process first N artifacts
    --reprocess     Reprocess all artifacts (ignore existing)
    --verbose       Enable verbose logging
"""

import csv
import json
import sys
from pathlib import Path

import pdfplumber
import tiktoken
import typer
from loguru import logger
from pypdf import PdfReader

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import setup_logging

app = typer.Typer()


def extract_text_pdfplumber(filepath: Path) -> str | None:
    """Extract text using pdfplumber.

    Args:
        filepath: Path to PDF file.

    Returns:
        Extracted text or None on failure.
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            return "\n\n".join(pages_text) if pages_text else None
    except Exception as e:
        logger.debug(f"pdfplumber failed: {e}")
        return None


def extract_text_pypdf(filepath: Path) -> str | None:
    """Extract text using pypdf (fallback).

    Args:
        filepath: Path to PDF file.

    Returns:
        Extracted text or None on failure.
    """
    try:
        reader = PdfReader(filepath)
        pages_text = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages_text.append(text)
        return "\n\n".join(pages_text) if pages_text else None
    except Exception as e:
        logger.debug(f"pypdf failed: {e}")
        return None


def extract_text_from_pdf(filepath: Path) -> str:
    """Extract text from PDF using multiple methods.

    Args:
        filepath: Path to PDF file.

    Returns:
        Extracted text (empty string if all methods fail).
    """
    # Try pdfplumber first (better quality)
    text = extract_text_pdfplumber(filepath)
    if text and len(text.strip()) > 100:
        return text

    # Fallback to pypdf
    text = extract_text_pypdf(filepath)
    if text and len(text.strip()) > 100:
        return text

    # Return whatever we got, even if minimal
    return text or ""


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 100,
    model: str = "gpt-4o",
) -> list[str]:
    """Chunk text by token count with overlap.

    Args:
        text: Text to chunk.
        chunk_size: Target tokens per chunk.
        overlap: Overlap tokens between chunks.
        model: Model for tokenizer (to match API).

    Returns:
        List of text chunks.
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    total_tokens = len(tokens)

    if total_tokens == 0:
        return []

    if total_tokens <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < total_tokens:
        end = min(start + chunk_size, total_tokens)
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)
        chunks.append(chunk_text)

        # Move start with overlap
        start = end - overlap
        if start >= total_tokens:
            break

    return chunks


def load_artifacts(csv_path: Path) -> list[dict]:
    """Load artifacts from CSV."""
    if not csv_path.exists():
        return []

    artifacts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            artifacts.append(dict(row))
    return artifacts


def load_existing_chunks(jsonl_path: Path) -> set[str]:
    """Load existing chunk IDs to avoid reprocessing.

    Returns:
        Set of artifact_ids that have been processed.
    """
    if not jsonl_path.exists():
        return set()

    processed = set()
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                chunk = json.loads(line)
                processed.add(chunk.get("artifact_id", ""))
            except json.JSONDecodeError:
                continue
    return processed


@app.command()
def main(
    limit: int = typer.Option(0, "--limit", help="Limit artifacts to process"),
    reprocess: bool = typer.Option(False, "--reprocess", help="Reprocess all"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Extract text from PDFs and create chunks for evaluation."""
    # Setup logging
    setup_logging("extract_and_chunk" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting text extraction and chunking...")

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

    # Load existing processed artifacts
    processed_artifacts = set() if reprocess else load_existing_chunks(settings.chunks_jsonl)
    logger.info(f"Found {len(processed_artifacts)} already processed artifacts")

    # Ensure output directories exist
    settings.extracted_text_dir.mkdir(parents=True, exist_ok=True)
    settings.outputs_dir.mkdir(parents=True, exist_ok=True)

    # Process artifacts
    total_chunks = 0
    processed_count = 0

    # Open chunks file in append mode (or write if reprocessing)
    mode = "w" if reprocess else "a"
    chunks_file = open(settings.chunks_jsonl, mode, encoding="utf-8")

    try:
        for i, artifact in enumerate(artifacts, 1):
            artifact_id = artifact["artifact_id"]

            # Skip if already processed
            if artifact_id in processed_artifacts:
                logger.debug(f"[{i}/{len(artifacts)}] Skipping (exists): {artifact_id}")
                continue

            filepath = Path(artifact["file_path"])
            if not filepath.exists():
                logger.warning(f"[{i}/{len(artifacts)}] File not found: {filepath}")
                continue

            logger.info(f"[{i}/{len(artifacts)}] Processing: {artifact_id}")

            # Extract text
            text = extract_text_from_pdf(filepath)
            if not text or len(text.strip()) < 100:
                logger.warning(f"  No meaningful text extracted from {artifact_id}")
                continue

            # Save full text
            text_path = settings.extracted_text_dir / f"{artifact_id}.txt"
            text_path.write_text(text, encoding="utf-8")
            logger.debug(f"  Saved text: {len(text)} chars")

            # Create chunks
            chunks = chunk_text(
                text,
                chunk_size=settings.chunk_size_tokens,
                overlap=settings.chunk_overlap_tokens,
            )
            logger.info(f"  Created {len(chunks)} chunks")

            # Write chunks to JSONL
            for j, chunk_text_content in enumerate(chunks):
                chunk_record = {
                    "artifact_id": artifact_id,
                    "chunk_id": f"{artifact_id}_chunk_{j:03d}",
                    "district": artifact.get("district", ""),
                    "district_slug": artifact.get("district_slug", ""),
                    "meeting_date": artifact.get("inferred_meeting_date", ""),
                    "source_url": artifact.get("source_url", ""),
                    "board_page_url": artifact.get("board_page_url", ""),
                    "text": chunk_text_content,
                }
                chunks_file.write(json.dumps(chunk_record) + "\n")
                total_chunks += 1

            processed_count += 1

    finally:
        chunks_file.close()

    logger.info(
        f"Extraction complete. "
        f"Processed {processed_count} artifacts. "
        f"Created {total_chunks} chunks."
    )


if __name__ == "__main__":
    app()
