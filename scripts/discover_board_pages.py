#!/usr/bin/env python3
"""Discover board meeting pages from district websites.

This script performs a BFS crawl (max depth 2) from each district's website URL
to find board meeting pages using keyword matching.

Usage:
    python scripts/discover_board_pages.py [OPTIONS]

Options:
    --refresh       Re-discover URLs even if already set
    --limit N       Only process first N districts
    --verbose       Enable verbose logging
"""

import csv
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
import typer
from bs4 import BeautifulSoup
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import settings
from src.utils import setup_logging

app = typer.Typer()

# Keywords to look for in URLs
BOARD_KEYWORDS = [
    "board",
    "meeting",
    "agenda",
    "minutes",
    "boarddocs",
    "boardbook",
    "agendaonline",
    "publicmeeting",
]

# Common board meeting portal domains
KNOWN_PORTALS = [
    "boarddocs.com",
    "agendaonline.net",
    "civicclerk.com",
    "diligent.com",
    "boardbook.org",
]

# HTTP headers
HEADERS = {
    "User-Agent": "EduQuest-Signal-Scout/1.0 (Educational Research Bot)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def score_url(url: str) -> int:
    """Score a URL based on keyword matches.

    Higher scores indicate more likely board meeting pages.

    Args:
        url: URL to score.

    Returns:
        Score (0 = no match, higher = better match).
    """
    url_lower = url.lower()
    score = 0

    # Check for keywords
    for keyword in BOARD_KEYWORDS:
        if keyword in url_lower:
            score += 1

    # Bonus for multiple keywords
    if score >= 2:
        score += 2

    # Bonus for known portal domains
    for portal in KNOWN_PORTALS:
        if portal in url_lower:
            score += 5

    # Penalty for common non-board pages
    penalties = ["calendar", "employment", "jobs", "staff", "directory"]
    for penalty in penalties:
        if penalty in url_lower and "board" not in url_lower:
            score -= 1

    return max(0, score)


def is_valid_url(url: str, base_domain: str) -> bool:
    """Check if a URL is valid for crawling.

    Args:
        url: URL to check.
        base_domain: Base domain to stay within.

    Returns:
        True if URL should be crawled.
    """
    try:
        parsed = urlparse(url)

        # Must have scheme and netloc
        if not parsed.scheme or not parsed.netloc:
            return False

        # Only HTTP(S)
        if parsed.scheme not in ("http", "https"):
            return False

        # Stay within domain (allow subdomains) or known portals
        url_domain = parsed.netloc.lower()
        if not (
            url_domain.endswith(base_domain)
            or any(portal in url_domain for portal in KNOWN_PORTALS)
        ):
            return False

        # Skip file downloads (except HTML)
        skip_extensions = [
            ".pdf",
            ".doc",
            ".docx",
            ".xls",
            ".xlsx",
            ".ppt",
            ".pptx",
            ".zip",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".mp4",
            ".mp3",
        ]
        path_lower = parsed.path.lower()
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            return False

        return True

    except Exception:
        return False


def extract_links(html: str, base_url: str) -> list[str]:
    """Extract links from HTML content.

    Args:
        html: HTML content.
        base_url: Base URL for resolving relative links.

    Returns:
        List of absolute URLs.
    """
    soup = BeautifulSoup(html, "lxml")
    links = []

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        # Skip javascript and mailto links
        if href.startswith(("javascript:", "mailto:", "tel:", "#")):
            continue
        # Resolve relative URLs
        full_url = urljoin(base_url, href)
        links.append(full_url)

    return links


def discover_board_page(website_url: str, max_depth: int = 2) -> str | None:
    """Discover board meeting page using BFS crawl.

    Args:
        website_url: Starting URL (district website).
        max_depth: Maximum crawl depth.

    Returns:
        Best matching board page URL, or None if not found.
    """
    visited = set()
    queue = deque([(website_url, 0)])  # (url, depth)
    candidates = []

    # Parse base domain for staying within site
    parsed = urlparse(website_url)
    base_domain = parsed.netloc.lower()
    # Remove www. prefix for domain matching
    if base_domain.startswith("www."):
        base_domain = base_domain[4:]

    while queue:
        url, depth = queue.popleft()

        # Skip if already visited or too deep
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        # Check URL score before fetching
        url_score = score_url(url)
        if url_score > 0:
            candidates.append((url_score, depth, url))

        # Don't fetch if at max depth (no more links to follow)
        if depth >= max_depth:
            continue

        try:
            # Polite delay
            time.sleep(settings.request_delay)

            logger.debug(f"Fetching (depth={depth}): {url}")
            response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
            response.raise_for_status()

            # Check content type
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" not in content_type:
                continue

            # Extract and queue new links
            links = extract_links(response.text, url)
            for link in links:
                if is_valid_url(link, base_domain) and link not in visited:
                    queue.append((link, depth + 1))

        except requests.RequestException as e:
            logger.debug(f"Failed to fetch {url}: {e}")
            continue
        except Exception as e:
            logger.debug(f"Error processing {url}: {e}")
            continue

    # Return best candidate (highest score, prefer shallower depth)
    if candidates:
        # Sort by score (desc), then depth (asc)
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best = candidates[0]
        logger.info(f"Found board page (score={best[0]}, depth={best[1]}): {best[2]}")
        return best[2]

    return None


def load_districts(csv_path: Path) -> list[dict]:
    """Load districts from CSV.

    Args:
        csv_path: Path to districts CSV.

    Returns:
        List of district dictionaries.
    """
    districts = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            districts.append(dict(row))
    return districts


def save_districts(csv_path: Path, districts: list[dict]) -> None:
    """Save districts to CSV.

    Args:
        csv_path: Path to districts CSV.
        districts: List of district dictionaries.
    """
    if not districts:
        return

    fieldnames = districts[0].keys()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(districts)


@app.command()
def main(
    refresh: bool = typer.Option(False, "--refresh", help="Re-discover all URLs"),
    limit: int = typer.Option(0, "--limit", help="Limit number of districts to process"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging"),
) -> None:
    """Discover board meeting pages from district websites."""
    # Setup logging
    setup_logging("discover_board_pages" if not verbose else None)
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    logger.info("Starting board page discovery...")

    # Load districts
    if not settings.districts_csv.exists():
        logger.error(f"Districts CSV not found: {settings.districts_csv}")
        raise typer.Exit(1)

    districts = load_districts(settings.districts_csv)
    logger.info(f"Loaded {len(districts)} districts")

    # Apply limit if specified
    if limit > 0:
        districts = districts[:limit]
        logger.info(f"Limited to {limit} districts")

    # Process each district
    updated = 0
    for i, district in enumerate(districts, 1):
        name = district["district_name"]
        website_url = district.get("website_url", "").strip()
        current_board_url = district.get("board_page_url", "").strip()

        # Skip if already has board URL and not refreshing
        if current_board_url and not refresh:
            logger.debug(f"[{i}/{len(districts)}] Skipping {name}: already has board URL")
            continue

        if not website_url:
            logger.warning(f"[{i}/{len(districts)}] Skipping {name}: no website URL")
            continue

        logger.info(f"[{i}/{len(districts)}] Discovering board page for: {name}")

        try:
            board_url = discover_board_page(
                website_url, max_depth=settings.crawl_depth
            )

            if board_url:
                district["board_page_url"] = board_url
                updated += 1
                logger.info(f"  Found: {board_url}")
            else:
                logger.warning(f"  No board page found for {name}")

        except Exception as e:
            logger.error(f"  Error discovering board page for {name}: {e}")

    # Save updated districts
    save_districts(settings.districts_csv, districts)
    logger.info(f"Discovery complete. Updated {updated} districts.")


if __name__ == "__main__":
    app()
