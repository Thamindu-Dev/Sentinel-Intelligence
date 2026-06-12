"""
Sentinel Intelligence — Source Scraper Module

Defines all CTI sources and provides async scraping functions.
Each source type (RSS, HTML, JSON API) has its own parser.

Usage:
    from backend.collector.sources import scrape_all_sources
    raw_items = await scrape_all_sources()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

import feedparser
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger("sentinel.sources")

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SourceDef:
    """Definition of a single CTI source."""
    name: str
    url: str
    source_type: str          # "rss", "html", or "json_api"
    selector: str = "article" # CSS selector for HTML sources
    max_items: int = 15       # Max entries to pull per source per run


@dataclass
class RawItem:
    """A single scraped item before LLM analysis."""
    title: str
    url: str
    raw_text: str
    source_name: str
    fetched_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCE_LIST: List[SourceDef] = [
    SourceDef(
        name="BleepingComputer",
        url="https://www.bleepingcomputer.com/feed/",
        source_type="rss",
    ),
    SourceDef(
        name="The Hacker News",
        url="https://feeds.feedburner.com/TheHackersNews",
        source_type="rss",
    ),
    SourceDef(
        name="Krebs on Security",
        url="https://krebsonsecurity.com/feed/",
        source_type="rss",
    ),
    SourceDef(
        name="Google Project Zero",
        url="https://googleprojectzero.blogspot.com/feeds/posts/default",
        source_type="rss",
    ),
    SourceDef(
        name="CISA Advisories",
        url="https://www.cisa.gov/news-events/cybersecurity-advisories?f%5B0%5D=advisory_type%3A94",
        source_type="html",
        selector="article, .c-teaser, .views-row",
    ),
    SourceDef(
        name="NIST NVD Recent",
        url="https://services.nvd.nist.gov/rest/json/cves/2.0?resultsPerPage=20",
        source_type="json_api",
    ),
]


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------

def _get_client() -> httpx.AsyncClient:
    """Build a pre-configured async HTTP client."""
    return httpx.AsyncClient(
        timeout=15.0,
        follow_redirects=True,
        headers={
            "User-Agent": "SentinelBot/1.0 (+https://github.com/sentinel-cti)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )


# ---------------------------------------------------------------------------
# Parsers — one per source type
# ---------------------------------------------------------------------------

def _parse_rss(feed_content: str, source: SourceDef) -> List[RawItem]:
    """Parse RSS/Atom feed content into RawItems."""
    feed = feedparser.parse(feed_content)
    items: List[RawItem] = []

    for entry in feed.entries[: source.max_items]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "")

        # Build raw text from summary + content
        raw_parts: list = []
        if entry.get("summary"):
            raw_parts.append(entry.summary)
        if entry.get("content"):
            for c in entry.content:
                raw_parts.append(c.get("value", ""))

        raw_html = " ".join(raw_parts)
        # Strip HTML tags for clean text
        raw_text = BeautifulSoup(raw_html, "html.parser").get_text(
            separator=" ", strip=True
        )

        if title and raw_text:
            items.append(RawItem(
                title=title,
                url=link,
                raw_text=raw_text,
                source_name=source.name,
            ))

    return items


def _parse_html(html_content: str, source: SourceDef) -> List[RawItem]:
    """Parse an HTML page using the configured CSS selector."""
    soup = BeautifulSoup(html_content, "html.parser")
    items: List[RawItem] = []

    # Try each selector (comma-separated means OR)
    elements = soup.select(source.selector)

    for el in elements[: source.max_items]:
        # Try to find a title
        title_el = el.find(["h2", "h3", "h4", "a"])
        title = title_el.get_text(strip=True) if title_el else ""

        # Try to find a link
        link_el = el.find("a", href=True)
        link = link_el["href"] if link_el else ""
        if link and not link.startswith("http"):
            # Make relative URLs absolute
            from urllib.parse import urljoin
            link = urljoin(source.url, link)

        raw_text = el.get_text(separator=" ", strip=True)

        if title and len(raw_text) > 50:
            items.append(RawItem(
                title=title,
                url=link,
                raw_text=raw_text,
                source_name=source.name,
            ))

    return items


def _parse_nvd_json(json_data: dict, source: SourceDef) -> List[RawItem]:
    """Parse the NIST NVD 2.0 JSON API response."""
    items: List[RawItem] = []
    vulnerabilities = json_data.get("vulnerabilities", [])

    for vuln in vulnerabilities[: source.max_items]:
        cve = vuln.get("cve", {})
        cve_id = cve.get("id", "")

        # Get English description
        descriptions = cve.get("descriptions", [])
        desc = ""
        for d in descriptions:
            if d.get("lang") == "en":
                desc = d.get("value", "")
                break

        # Build raw text
        raw_text = f"{cve_id}: {desc}"

        # Get references
        refs = cve.get("references", [])
        ref_url = refs[0].get("url", "") if refs else f"https://nvd.nist.gov/vuln/detail/{cve_id}"

        if cve_id and desc:
            items.append(RawItem(
                title=f"{cve_id}: {desc[:120]}",
                url=ref_url,
                raw_text=raw_text,
                source_name=source.name,
            ))

    return items


# ---------------------------------------------------------------------------
# Per-source scraper
# ---------------------------------------------------------------------------

async def _scrape_source(
    client: httpx.AsyncClient, source: SourceDef
) -> List[RawItem]:
    """Scrape a single source. Returns empty list on any error."""
    try:
        logger.info(f"Scraping: {source.name} ({source.url})")
        response = await client.get(source.url)
        response.raise_for_status()

        if source.source_type == "rss":
            return _parse_rss(response.text, source)
        elif source.source_type == "html":
            return _parse_html(response.text, source)
        elif source.source_type == "json_api":
            return _parse_nvd_json(response.json(), source)
        else:
            logger.warning(f"Unknown source type: {source.source_type}")
            return []

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP {e.response.status_code} from {source.name}: {e}")
        return []
    except httpx.RequestError as e:
        logger.error(f"Request error from {source.name}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error scraping {source.name}: {e}", exc_info=True)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def scrape_all_sources() -> List[RawItem]:
    """
    Scrape all registered sources concurrently.
    Returns a flat list of RawItems from all sources.
    Errors in one source do not affect others.
    """
    async with _get_client() as client:
        tasks = [_scrape_source(client, src) for src in SOURCE_LIST]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: List[RawItem] = []
    for i, result in enumerate(results):
        source_name = SOURCE_LIST[i].name
        if isinstance(result, Exception):
            logger.error(f"Source {source_name} raised: {result}")
        elif isinstance(result, list):
            logger.info(f"Source {source_name}: {len(result)} items scraped")
            all_items.extend(result)

    logger.info(f"Total raw items scraped: {len(all_items)}")
    return all_items
