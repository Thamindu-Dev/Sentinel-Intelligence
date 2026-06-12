"""
Sentinel Intelligence — LLM Analyzer Module

Sends raw scraped content to the Gemini API for structured threat extraction.
Rate-limited via asyncio.Semaphore.

Usage:
    from backend.collector.analyzer import analyse_item
    finding = await analyse_item(raw_item)  # returns dict or None
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import google.generativeai as genai

from backend.config import settings
from backend.collector.sources import RawItem

logger = logging.getLogger("sentinel.analyzer")

# ---------------------------------------------------------------------------
# Gemini client setup
# ---------------------------------------------------------------------------

_configured = False

def _ensure_configured():
    """Configure the Gemini SDK once."""
    global _configured
    if not _configured:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

_semaphore: Optional[asyncio.Semaphore] = None

def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.GEMINI_RATE_LIMIT)
    return _semaphore


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT_BATCH = """You are a cybersecurity analyst. Analyse the following batch of threat intelligence articles and extract structured data.

Return ONLY a valid JSON array of objects with the exact fields below. There must be exactly one JSON object per article provided.

[
  {{
    "id": "<The item_id provided in the prompt>",
    "title": "<A clear, concise title. Include CVE ID if present.>",
    "severity": "<Critical|High|Medium|Low>",
    "impact": "<RCE|LPE|SQLi|XSS|DoS|Zero-day|Phishing|Data Breach|Supply Chain|Other>",
    "summary": "<Exactly 2 sentences. Sentence 1: what the vulnerability/threat is. Sentence 2: what the impact or risk is.>",
    "target": "<Affected software, hardware, platform and version numbers>",
    "cve_id": "<CVE-YYYY-NNNNN if present, else null>",
    "is_critical_field": <true if this is a legitimate security finding, false if general news/marketing>
  }}
]

Articles to analyze:
{batch_content}

CRITICAL: Do not use bullet points. Do not add any explanation. Output ONLY a raw, valid JSON array. Your entire response must be parseable by `json.loads()`."""


# ---------------------------------------------------------------------------
# Analysis function
# ---------------------------------------------------------------------------

@dataclass
class AnalysedFinding:
    """Result of LLM analysis — ready for dedup and DB insertion."""
    title: str
    severity: str
    impact: str
    summary: str
    target: str
    cve_id: Optional[str]
    source_name: str
    source_url: str


def _parse_llm_response(text: str) -> Optional[list]:
    """
    Extract JSON array from the LLM response text.
    """
    text = text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return [data] # fallback if it returned a single object
    except json.JSONDecodeError:
        # Try to find JSON array within the text
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end])
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass
    return None


_VALID_SEVERITIES = {"Critical", "High", "Medium", "Low"}
_VALID_IMPACTS = {
    "RCE", "LPE", "SQLi", "XSS", "DoS", "Zero-day",
    "Phishing", "Data Breach", "Supply Chain", "Other",
}


def _validate_finding(data: Dict[str, Any]) -> bool:
    """Validate that the LLM returned well-formed data."""
    if not data:
        return False
    if data.get("severity") not in _VALID_SEVERITIES:
        return False
    if not data.get("title"):
        return False
    if not data.get("summary"):
        return False
    # is_critical_field must be true to keep the finding
    if not data.get("is_critical_field", False):
        return False
    return True


async def analyse_chunk(chunk: list[RawItem]) -> tuple[list[AnalysedFinding], bool]:
    """
    Send a chunk of exactly 5 RawItems to Gemini for analysis in a single prompt.
    Returns (findings, success_flag).
    """
    if not chunk:
        return [], True

    _ensure_configured()

    # Build the batch prompt content
    batch_text = ""
    for idx, item in enumerate(chunk):
        raw = item.raw_text[:settings.RAW_TEXT_MAX_CHARS]
        batch_text += f"\n--- Item ID: {idx} ---\nSource: {item.source_name}\nURL: {item.url}\nContent: {raw}\n"

    prompt = _ANALYSIS_PROMPT_BATCH.format(batch_content=batch_text)
    sem = _get_semaphore()

    try:
        async with sem:
            model = genai.GenerativeModel(settings.GEMINI_MODEL)
            response = None
            
            for attempt in range(6):
                try:
                    response = await asyncio.to_thread(
                        model.generate_content, prompt
                    )
                    break
                except Exception as api_err:
                    if "429" in str(api_err) or "ResourceExhausted" in str(type(api_err).__name__):
                        wait_sec = 60
                        logger.warning(f"API Rate limit hit (429). Retrying in {wait_sec}s... (Attempt {attempt+1}/6)")
                        await asyncio.sleep(wait_sec)
                    else:
                        raise api_err
            
            if response is None:
                logger.error(f"Failed to get response for batch of {len(chunk)} after 6 attempts")
                return [], False

        if not response.text:
            logger.warning("Empty LLM response for batch")
            return [], False

        data_list = _parse_llm_response(response.text)
        if not data_list:
            logger.warning("Failed to parse LLM JSON Array for batch")
            logger.error(f"Raw response: {response.text[:500]}")
            return [], False

        findings = []
        for data in data_list:
            # Map back to original item
            try:
                item_idx = int(data.get("id", -1))
            except ValueError:
                continue

            if item_idx < 0 or item_idx >= len(chunk):
                continue

            item = chunk[item_idx]

            if not _validate_finding(data):
                continue

            impact = data.get("impact", "Other")
            if impact not in _VALID_IMPACTS:
                impact = "Other"

            findings.append(AnalysedFinding(
                title=data.get("title", item.title),
                severity=data["severity"],
                impact=impact,
                summary=data.get("summary", ""),
                target=data.get("target", "Unknown"),
                cve_id=data.get("cve_id"),
                source_name=item.source_name,
                source_url=item.url,
            ))

        return findings, True

    except Exception as e:
        logger.error(f"Gemini API error for batch: {e}", exc_info=True)
        return [], False


async def analyse_batch(items: list[RawItem]) -> tuple[list[AnalysedFinding], list[str]]:
    """
    Analyse a batch of RawItems by splitting them into chunks of 5
    and sending each chunk to the LLM.
    Returns (findings, successfully_processed_urls).
    """
    chunk_size = 5
    chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
    
    logger.info(f"Splitting {len(items)} items into {len(chunks)} LLM requests (batch size: {chunk_size})")

    findings: list[AnalysedFinding] = []
    processed_urls: list[str] = []
    errors = 0

    for idx, chunk in enumerate(chunks):
        logger.info(f"Processing chunk {idx + 1}/{len(chunks)}...")
        try:
            # Send the chunk
            r, success = await analyse_chunk(chunk)
            if success:
                findings.extend(r)
                processed_urls.extend([item.url for item in chunk])
            else:
                errors += 1
                logger.error(f"Chunk {idx + 1} failed, keeping its items in the queue.")
            
            # Sleep 60 seconds between requests to avoid burst rate limits and account bans
            if idx < len(chunks) - 1:
                await asyncio.sleep(60)
        except Exception as e:
            errors += 1
            logger.error(f"Analysis task error on chunk {idx + 1}: {e}")

    logger.info(
        f"Analysis complete: {len(findings)} valid findings from {len(items)} raw items. Errors: {errors}"
    )
    return findings, processed_urls
