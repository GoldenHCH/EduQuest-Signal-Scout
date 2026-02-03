#!/usr/bin/env python3
"""Fetch board meeting artifacts (PDFs) from discovered board pages.

This script downloads meeting documents (agendas, minutes, packets) from
each district's board page URL.

Usage:
    python scripts/fetch_artifacts.py [OPTIONS]

Options:
    --limit-districts N    Only process first N districts
    --limit-docs N         Limit documents per district
    --verbose              Enable verbose logging
"""

import csv
import hashlib
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import typer
from bs4 import BeautifulSoup
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import parse_date_from_text, setup_logging, slugify

app = typer.Typer()

# HTTP headers
HEADERS = {
    "User-Agent": "EduQuest-Signal-Scout/1.0 (Educational Research Bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8",
}

# PDF link patterns
PDF_PATTERN = re.compile(r"\.pdf$", re.IGNORECASE)

# Keywords that suggest meeting documents
MEETING_KEYWORDS = [
    "agenda",
    "minutes",
    "packet",
    "meeting",
    "board",
    "regular",
    "special",
    "work session",
]


def generate_artifact_id(district_slug: str, url: str) -> str:
    """Generate a unique artifact ID.

    Args:
        district_slug: Slugified district name.
        url: Source URL of the artifact.

    Returns:
        Unique artifact ID.
    """
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{district_slug}_{url_hash}"


def extract_pdf_links(html: str, base_url: str) -> list[dict]:
    """Extract PDF links from HTML with metadata.

    Args:
        html: HTML content.
        base_url: Base URL for resolving relative links.

    Returns:
        List of dicts with url, link_text, meeting_date.
    """
    soup = BeautifulSoup(html, "lxml")
    links = []
    seen_urls = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]

        # Check if it's a PDF
        if not PDF_PATTERN.search(href):
            continue

        full_url = urljoin(base_url, href)

        # Skip duplicates
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)

        # Get link text
        link_text = a_tag.get_text(strip=True)
        if not link_text:
            # Try to get text from parent or nearby elements
            parent = a_tag.parent
            if parent:
                link_text = parent.get_text(strip=True)[:200]

        # Try to parse date from link text or URL
        meeting_date = parse_date_from_text(link_text) or parse_date_from_text(href)

        # Score relevance
        relevance = 0
        text_lower = (link_text + " " + href).lower()
        for keyword in MEETING_KEYWORDS:
            if keyword in text_lower:
                relevance += 1

        links.append(
            {
                "url": full_url,
                "link_text": link_text[:500] if link_text else "",
                "meeting_date": meeting_date,
                "relevance": relevance,
            }
        )

    # Sort by relevance (desc) and date (most recent first)
    links.sort(
        key=lambda x: (-x["relevance"], -(x["meeting_date"].timestamp() if x["meeting_date"] else 0))
    )

    return links


def fetch_page(url: str) -> str | None:
    """Fetch a web page.

    Args:
        url: URL to fetch.

    Returns:
        HTML content or None on failure.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type:
            logger.debug(f"Skipping non-HTML content: {content_type}")
            return None

        return response.text

    except requests.RequestException as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return None


def download_pdf(url: str, filepath: Path) -> bool:
    """Download a PDF file.

    Args:
        url: URL of the PDF.
        filepath: Local path to save to.

    Returns:
        True if successful.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=60, stream=True)
        response.raise_for_status()

        # Verify it's a PDF
        content_type = response.headers.get("content-type", "").lower()
        if "pdf" not in content_type and not url.lower().endswith(".pdf"):
            logger.warning(f"Unexpected content type for PDF: {content_type}")

        # Save to file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        logger.debug(f"Downloaded: {filepath}")
        return True

    except requests.RequestException as e:
        logger.error(f"Failed to download {url}: {e}")
        return False


def load_districts(csv_path: Path) -> list[dict]:
    """Load districts from CSV."""
    districts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            districts.append(dict(row))
    return districts


def load_existing_artifacts(csv_path: Path) -> dict[str, dict]:
    """Load existing artifacts to avoid re-downloading.

    Returns:
        Dict mapping artifact_id to artifact data.
    """
    if not csv_path.exists():
        return {}

    artifacts = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            artifacts[row["artifact_id"]] = dict(row)
    return artifacts


def save_artifacts(csv_path: Path, artifacts: list[dict]) -> None:
    """Save artifacts to CSV."""
    if not artifacts:
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "artifact_id",
        "district",
        "district_slug",
        "board_page_url",
        "source_url",
        "fetched_at",
        "file_path",
        "inferred_meeting_date",
        "link_text",
        "mime_type",
    ]

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(artifacts)


@app.command()
def main(
    limit_districts: int = typer.Option(0, "--limit-districts", help="Limit districts"),
    limit_docs: int = typer.Option(0, "--limit-docs", help="Limit docs per district"),
    verbose: bool = typer.Option(False, "--verbose", help="Verbose logging"),
) -> None:
    """Fetch board meeting artifacts from discovered board pages."""
    # Setup logging
    setup_logging("fetch_artifacts" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting artifact fetching...")

    # Load districts
    if not settings.districts_csv.exists():
        logger.error(f"Districts CSV not found: {settings.districts_csv}")
        raise typer.Exit(1)

    districts = load_districts(settings.districts_csv)
    logger.info(f"Loaded {len(districts)} districts")

    # Apply district limit
    if limit_districts > 0:
        districts = districts[:limit_districts]
        logger.info(f"Limited to {limit_districts} districts")

    # Get max docs per district
    max_docs = limit_docs if limit_docs > 0 else settings.max_docs_per_district

    # Load existing artifacts to avoid re-downloading
    existing_artifacts = load_existing_artifacts(settings.artifacts_csv)
    logger.info(f"Found {len(existing_artifacts)} existing artifacts")

    # Process each district
    all_artifacts = list(existing_artifacts.values())
    new_count = 0
    six_months_ago = datetime.now() - timedelta(days=180)

    for i, district in enumerate(districts, 1):
        name = district["district_name"]
        board_page_url = district.get("board_page_url", "").strip()

        if not board_page_url:
            logger.warning(f"[{i}/{len(districts)}] Skipping {name}: no board page URL")
            continue

        logger.info(f"[{i}/{len(districts)}] Fetching artifacts for: {name}")
        district_slug = slugify(name)

        # Fetch board page
        time.sleep(settings.request_delay)
        html = fetch_page(board_page_url)
        if not html:
            logger.warning(f"  Failed to fetch board page")
            continue

        # Extract PDF links
        pdf_links = extract_pdf_links(html, board_page_url)
        logger.info(f"  Found {len(pdf_links)} PDF links")

        # Filter to recent documents
        recent_links = []
        for link in pdf_links:
            meeting_date = link.get("meeting_date")
            # Keep if no date (can't filter) or date is recent
            if meeting_date is None or meeting_date >= six_months_ago:
                recent_links.append(link)

        logger.info(f"  {len(recent_links)} recent documents (last 6 months)")

        # Download up to max_docs
        docs_downloaded = 0
        for link in recent_links[:max_docs * 2]:  # Check more than we need in case some fail
            if docs_downloaded >= max_docs:
                break

            artifact_id = generate_artifact_id(district_slug, link["url"])

            # Skip if already downloaded
            if artifact_id in existing_artifacts:
                logger.debug(f"  Skipping (exists): {artifact_id}")
                continue

            # Download
            time.sleep(settings.request_delay)
            filepath = settings.raw_docs_dir / district_slug / f"{artifact_id}.pdf"

            if download_pdf(link["url"], filepath):
                artifact = {
                    "artifact_id": artifact_id,
                    "district": name,
                    "district_slug": district_slug,
                    "board_page_url": board_page_url,
                    "source_url": link["url"],
                    "fetched_at": datetime.now().isoformat(),
                    "file_path": str(filepath),
                    "inferred_meeting_date": (
                        link["meeting_date"].strftime("%Y-%m-%d")
                        if link["meeting_date"]
                        else ""
                    ),
                    "link_text": link["link_text"][:500],
                    "mime_type": "application/pdf",
                }
                all_artifacts.append(artifact)
                existing_artifacts[artifact_id] = artifact
                docs_downloaded += 1
                new_count += 1
                logger.info(f"  Downloaded: {artifact_id}")

        logger.info(f"  Downloaded {docs_downloaded} new documents")

    # Save all artifacts
    save_artifacts(settings.artifacts_csv, all_artifacts)
    logger.info(f"Fetch complete. {new_count} new artifacts. Total: {len(all_artifacts)}")


if __name__ == "__main__":
    app()
