"""Utility functions for Utah Board Signal Scout."""

import re
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger

from src.config import settings


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug.

    Args:
        text: Text to convert to slug.

    Returns:
        Lowercase slug with only alphanumeric characters and hyphens.
    """
    # Convert to lowercase
    text = text.lower()
    # Replace spaces and underscores with hyphens
    text = re.sub(r"[\s_]+", "-", text)
    # Remove non-alphanumeric characters except hyphens
    text = re.sub(r"[^a-z0-9-]", "", text)
    # Remove consecutive hyphens
    text = re.sub(r"-+", "-", text)
    # Strip leading/trailing hyphens
    text = text.strip("-")
    return text


def setup_logging(log_name: str | None = None) -> Path | None:
    """Configure logging for the application.

    Args:
        log_name: Optional name for the log file. If None, only console logging is used.

    Returns:
        Path to the log file if created, None otherwise.
    """
    # Remove default handler
    logger.remove()

    # Add console handler with color
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
        colorize=True,
    )

    log_path = None
    if log_name:
        # Create logs directory if needed
        settings.logs_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = settings.logs_dir / f"{timestamp}_{log_name}.log"

        # Add file handler
        logger.add(
            log_path,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            level="DEBUG",
            rotation="10 MB",
        )

        logger.info(f"Logging to: {log_path}")

    return log_path


def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    dirs = [
        settings.raw_docs_dir,
        settings.extracted_text_dir,
        settings.outputs_dir,
        settings.logs_dir,
    ]
    for dir_path in dirs:
        dir_path.mkdir(parents=True, exist_ok=True)


def parse_date_from_text(text: str) -> datetime | None:
    """Try to parse a date from text.

    Args:
        text: Text that may contain a date.

    Returns:
        Parsed datetime or None if no date found.
    """
    patterns = [
        # MM/DD/YYYY or MM-DD-YYYY
        (r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})", "%m/%d/%Y"),
        # YYYY-MM-DD
        (r"(\d{4})-(\d{2})-(\d{2})", "%Y-%m-%d"),
        # Month DD, YYYY
        (
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
            "%B %d %Y",
        ),
        # Mon DD, YYYY
        (
            r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})",
            "%b %d %Y",
        ),
    ]

    for pattern, date_format in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                date_str = match.group(0).replace(",", "").replace(".", "")
                # Normalize format for parsing
                date_str = re.sub(r"\s+", " ", date_str)
                return datetime.strptime(date_str, date_format)
            except ValueError:
                continue

    return None


def truncate_text(text: str, max_length: int = 200) -> str:
    """Truncate text to a maximum length, adding ellipsis if needed.

    Args:
        text: Text to truncate.
        max_length: Maximum length.

    Returns:
        Truncated text.
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."
