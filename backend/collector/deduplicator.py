"""
Sentinel Intelligence — Deduplication Module

Prevents duplicate findings in the database.
A finding is a duplicate if:
  1. Same CVE ID (exact match), OR
  2. Title similarity >= 85% (fuzzy match via rapidfuzz).

When a duplicate is found, the new source is appended to the existing
finding's sources list instead of creating a new row.

Usage:
    from backend.collector.deduplicator import deduplicate_finding
    result = deduplicate_finding(analysed_finding)
"""

import logging
import re
from typing import Optional, Tuple

from rapidfuzz import fuzz

from backend.collector.analyzer import AnalysedFinding
from backend.db.database import (
    find_by_cve_id,
    get_all_titles,
    insert_finding,
    append_source,
)

logger = logging.getLogger("sentinel.deduplicator")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIMILARITY_THRESHOLD = 85  # Levenshtein ratio threshold (0-100)


# ---------------------------------------------------------------------------
# Title normalisation
# ---------------------------------------------------------------------------

def _normalise_title(title: str) -> str:
    """
    Normalise a title for fuzzy comparison:
    - Lowercase
    - Strip punctuation
    - Collapse whitespace
    """
    title = title.lower()
    title = re.sub(r"[^\w\s]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------

def _find_duplicate_by_cve(cve_id: Optional[str]) -> Optional[int]:
    """Check if a finding with this CVE ID already exists. Returns the ID."""
    if not cve_id:
        return None
    existing = find_by_cve_id(cve_id)
    if existing:
        logger.debug(f"CVE match found: {cve_id} -> existing ID {existing['id']}")
        return existing["id"]
    return None


def _find_duplicate_by_title(title: str) -> Optional[int]:
    """
    Check all existing titles for fuzzy similarity.
    Returns the ID of the best match above the threshold, or None.
    """
    normalised = _normalise_title(title)
    if not normalised:
        return None

    all_titles = get_all_titles()
    best_score = 0.0
    best_id = None

    for row in all_titles:
        existing_normalised = _normalise_title(row["title"])
        score = fuzz.ratio(normalised, existing_normalised)
        if score > best_score:
            best_score = score
            best_id = row["id"]

    if best_score >= SIMILARITY_THRESHOLD and best_id is not None:
        logger.debug(
            f"Title fuzzy match ({best_score:.0f}%): '{title[:50]}' -> existing ID {best_id}"
        )
        return best_id

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deduplicate_finding(finding: AnalysedFinding) -> Tuple[str, int]:
    """
    Check if a finding is a duplicate and either insert or merge it.

    Returns:
        Tuple of (action, finding_id) where action is 'inserted' or 'updated'.
    """
    source_entry = {"name": finding.source_name, "url": finding.source_url}

    # --- Check 1: CVE ID match ---
    dup_id = _find_duplicate_by_cve(finding.cve_id)

    # --- Check 2: Title similarity ---
    if dup_id is None:
        dup_id = _find_duplicate_by_title(finding.title)

    # --- Merge or Insert ---
    if dup_id is not None:
        # Duplicate found — append source to existing finding
        append_source(dup_id, source_entry)
        logger.info(f"Merged source into existing finding #{dup_id}: {finding.title[:60]}")
        return ("updated", dup_id)
    else:
        # New finding — insert
        new_id = insert_finding({
            "cve_id": finding.cve_id,
            "title": finding.title,
            "severity": finding.severity,
            "impact": finding.impact,
            "summary": finding.summary,
            "target": finding.target,
            "sources": [source_entry],
        })
        logger.info(f"Inserted new finding #{new_id}: {finding.title[:60]}")
        return ("inserted", new_id)
