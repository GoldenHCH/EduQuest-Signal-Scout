#!/usr/bin/env python3
"""Weekly orchestration script for Utah Board Signal Scout.

This script runs the full pipeline:
1. Discover board pages (optional)
2. Fetch artifacts
3. Evaluate PDFs directly (uploads to LLM API)
4. Export signals

Usage:
    python scripts/run_weekly.py [OPTIONS]

Options:
    --skip-discover         Skip board page discovery
    --limit-districts N     Limit number of districts
    --limit-docs N          Limit docs per district
    --limit-pdfs N          Limit PDFs to evaluate
    --verbose               Enable verbose logging
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import typer
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import setup_logging

app = typer.Typer()


def run_script(
    script_name: str,
    args: list[str] | None = None,
    description: str = "",
) -> bool:
    """Run a pipeline script.

    Args:
        script_name: Name of the script (without path).
        args: Additional arguments to pass.
        description: Human-readable description for logging.

    Returns:
        True if successful, False otherwise.
    """
    script_path = settings.project_root / "scripts" / script_name
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    logger.info(f"Running: {description or script_name}")
    logger.debug(f"Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(settings.project_root),
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                if line:
                    logger.debug(f"  {line}")

        if result.returncode != 0:
            logger.error(f"Script failed with code {result.returncode}")
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if line:
                        logger.error(f"  {line}")
            return False

        logger.info(f"Completed: {description or script_name}")
        return True

    except Exception as e:
        logger.error(f"Failed to run {script_name}: {e}")
        return False


@app.command()
def main(
    skip_discover: bool = typer.Option(False, "--skip-discover", help="Skip discovery"),
    limit_districts: int = typer.Option(0, "--limit-districts", help="Limit districts"),
    limit_docs: int = typer.Option(0, "--limit-docs", help="Limit docs per district"),
    limit_pdfs: int = typer.Option(0, "--limit-pdfs", help="Limit PDFs to evaluate"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Run the full Utah Board Signal Scout pipeline."""
    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = setup_logging(f"run_weekly_{timestamp}")
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")
        if log_path:
            logger.add(log_path, level="DEBUG")

    logger.info("=" * 60)
    logger.info("Utah Board Signal Scout - Weekly Pipeline")
    logger.info(f"Started at: {datetime.now().isoformat()}")
    logger.info("=" * 60)

    # Track pipeline status
    steps_run = 0
    steps_failed = 0

    # Step 1: Discover board pages (optional)
    if not skip_discover:
        args = []
        if limit_districts > 0:
            args.extend(["--limit", str(limit_districts)])

        success = run_script(
            "discover_board_pages.py",
            args=args if args else None,
            description="Step 1/4: Discover board pages",
        )
        steps_run += 1
        if not success:
            steps_failed += 1
            logger.warning("Discovery failed, continuing with existing data...")
    else:
        logger.info("Step 1/4: Skipping board page discovery")

    # Step 2: Fetch artifacts
    args = []
    if limit_districts > 0:
        args.extend(["--limit-districts", str(limit_districts)])
    if limit_docs > 0:
        args.extend(["--limit-docs", str(limit_docs)])

    success = run_script(
        "fetch_artifacts.py",
        args=args if args else None,
        description="Step 2/4: Fetch artifacts",
    )
    steps_run += 1
    if not success:
        steps_failed += 1
        logger.error("Artifact fetching failed!")
        # Continue anyway - might have existing artifacts

    # Check if we have artifacts to evaluate
    if not settings.artifacts_csv.exists():
        logger.error("No artifacts file found. Cannot proceed with evaluation.")
        raise typer.Exit(1)

    # Step 3: Evaluate PDFs directly (uploads to LLM API)
    args = []
    if limit_pdfs > 0:
        args.extend(["--limit", str(limit_pdfs)])

    success = run_script(
        "evaluate_pdfs.py",
        args=args if args else None,
        description="Step 3/4: Evaluate PDFs directly",
    )
    steps_run += 1
    if not success:
        steps_failed += 1
        logger.error("PDF evaluation failed!")

    # Step 4: Export signals
    success = run_script(
        "export_signals.py",
        description="Step 4/4: Export signals",
    )
    steps_run += 1
    if not success:
        steps_failed += 1
        logger.error("Signal export failed!")

    # Summary
    logger.info("=" * 60)
    logger.info("Pipeline Complete")
    logger.info(f"Steps run: {steps_run}, Failed: {steps_failed}")
    logger.info(f"Finished at: {datetime.now().isoformat()}")

    # Report output locations
    logger.info("Output files:")
    for path in [
        settings.artifacts_csv,
        settings.evaluations_jsonl,
        settings.signals_csv,
        settings.signals_json,
        settings.top_signals_md,
    ]:
        if path.exists():
            size = path.stat().st_size
            logger.info(f"  {path.name}: {size:,} bytes")
        else:
            logger.info(f"  {path.name}: (not created)")

    logger.info("=" * 60)

    if steps_failed > 0:
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
