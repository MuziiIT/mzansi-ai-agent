import os
import json
import re
import time
from google import genai
from google.genai import types

from config import GEMINI_API_KEY, GEMINI_MODEL
import quota_tracker

client = genai.Client(api_key=GEMINI_API_KEY)

AGGREGATOR_DOMAINS = ("zabursaries.co.za", "allbursaries.co.za")

APPLY_KEYWORDS = re.compile(
    r"apply|official (site|website)|company website|visit website|"
    r"click here|more info|application (form|link)",
    re.IGNORECASE,
)

# Errors worth retrying — transient overload/rate-limit, not our fault.
RETRYABLE_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500")

EXTRACTION_PROMPT = """You are a data extraction assistant for a South African bursary platform.
Read the following scraped text and extract the details into a strict JSON object.
Use EXACTLY these keys. Do not add any others.

{{
  "name": "Full name of the bursary",
  "provider": "Company or organization offering it",
  "description": "A short 2-3 sentence summary of the opportunity",
  "field": "Target fields of study (e.g., STEM, Commerce, Arts)",
  "deadline": "Extract the closing date as a string, e.g., '31 August 2026'",
  "link": "CRITICAL: The official DIRECT external application or company website URL. Prefer one from the 'Candidate application links' list below. Do NOT use zabursaries.co.za or allbursaries.co.za links."
}}

If a specific piece of information is missing, return an empty string "" for that key.

Candidate application links found on this page (anchor text -> URL):
{links_block}

Text to analyze:
{text}"""


def _pick_fallback_link(direct_links: list) -> str:
    candidates = [
        (text, href) for text, href in direct_links
        if not any(dom in href for dom in AGGREGATOR_DOMAINS)
    ]
    if not candidates:
        return ""
    apply_like = [href for text, href in candidates if APPLY_KEYWORDS.search(text)]
    if apply_like:
        return apply_like[0]
    return candidates[0][1]


def extract_fields(raw_text: str, direct_links: list = None, max_retries: int = 3) -> dict:
    """
    raw_text here should be the ANNOTATED text (scraper.py's
    'annotated_text'), not the plain classifier text — this function
    needs the [DIRECT_LINK: ...] markers to find the real apply link.
    """
    direct_links = direct_links or []

    # Check budget BEFORE calling — don't discover the quota wall through
    # a stack of failed retries like before.
    if not quota_tracker.has_budget():
        print(f"[-] Gemini daily quota budget exhausted ({quota_tracker.remaining()} left) "
              f"— skipping extraction for this URL rather than retrying into a wall.")
        return {}

    links_block = "\n".join(f"- {text} -> {href}" for text, href in direct_links[:15]) or "(none found)"
    prompt = EXTRACTION_PROMPT.format(links_block=links_block, text=raw_text[:10000])

    structured = {}
    for attempt in range(1, max_retries + 1):
        quota_tracker.record_call()  # count the attempt itself, success or not
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1
                )
            )
            structured = json.loads(response.text)
            break
        except Exception as e:
            msg = str(e)
            is_retryable = any(marker in msg for marker in RETRYABLE_MARKERS)
            is_last_attempt = attempt == max_retries
            quota_exhausted_mid_run = not quota_tracker.has_budget()

            if not is_retryable or is_last_attempt or quota_exhausted_mid_run:
                reason = "quota exhausted" if quota_exhausted_mid_run else "giving up"
                print(f"[-] LLM Extraction failed (attempt {attempt}/{max_retries}, {reason}): {msg}")
                structured = {}
                break

            wait = 2 ** attempt  # 2s, 4s, 8s
            print(f"[-] LLM Extraction failed (attempt {attempt}/{max_retries}), "
                  f"retrying in {wait}s: {msg}")
            time.sleep(wait)

    link = structured.get("link", "")
    if not link or any(dom in link for dom in AGGREGATOR_DOMAINS):
        fallback = _pick_fallback_link(direct_links)
        if fallback:
            structured["link"] = fallback

    return structured