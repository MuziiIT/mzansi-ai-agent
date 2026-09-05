import json

from config import DRY_RUN
from logger_setup import logger
from scraper import scrape_bursary_page, UnsupportedContentError
from classifier import get_scam_probability, get_verdict
from llm_extract import extract_fields
from firestore_client import bursary_exists, push_bursary, log_rejected
from discover import discover_urls
from progress_logger import start_run, log_event, finish_run
from test_deadline_utils import is_expired
import quota_tracker


def _process_one_url(url: str):
    """
    Handles everything for a single URL: scrape -> classify -> extract ->
    publish. Wrapped by the caller in a try/except so a bug or unexpected
    error on ANY one URL can't take down the rest of an unattended run.
    """
    if not DRY_RUN and bursary_exists(url):
        logger.info(f"Skipping duplicate URL: {url}")
        log_event("skip", f"Duplicate, already in Firestore: {url}", status="info")
        return

    try:
        log_event("scrape", f"Scraping: {url}")
        scraped = scrape_bursary_page(url)
        log_event("scrape", f"Scraped OK: {url}", status="success")
    except UnsupportedContentError as e:
        logger.warning(f"Skipping unsupported content at {url}: {e}")
        log_event("scrape", f"Unsupported content, skipped: {e}", status="warning")
        return
    except Exception as e:
        logger.error(f"Scrape failed for {url}: {e}")
        log_event("scrape", f"Scrape failed for {url}: {e}", status="error")
        return

    score = get_scam_probability(scraped["raw_text"])
    verdict = get_verdict(score)
    log_event("classify", f"Score {score:.4f} -> {verdict}", status="info",
               data={"url": url, "score": score, "verdict": verdict})

    if verdict == "rejected":
        if not DRY_RUN:
            log_rejected(scraped, score)
        logger.info(f"REJECTED (score {score:.4f}): {url}")
        log_event("reject", f"Rejected (score {score:.4f}): {url}", status="warning",
                   data={"url": url, "score": score})
        return

    if not quota_tracker.has_budget():
        logger.warning(f"Gemini daily quota budget exhausted, skipping remaining "
                        f"extraction for: {url}")
        log_event("extract", f"Quota budget exhausted, skipped: {url}", status="warning")
        return

    log_event("extract", f"Extracting structured fields: {url}")
    structured = extract_fields(scraped["annotated_text"], scraped.get("direct_links", []))

    if not structured.get("name"):
        logger.warning(f"Extraction produced no name, skipping publish: {url}")
        log_event("extract", f"Extraction incomplete (no name found), skipped: {url}",
                   status="warning", data={"url": url})
        return

    log_event("extract", f"Extracted: {structured.get('name', url)}", status="success")

    deadline_text = structured.get("deadline", "")
    if is_expired(deadline_text):
        logger.info(f"Deadline already passed ({deadline_text}), skipping publish: {url}")
        log_event("extract", f"Expired deadline ({deadline_text}), skipped: {url}",
                   status="warning", data={"url": url, "deadline": deadline_text})
        return

    if DRY_RUN:
        logger.info(f"[DRY RUN] Would publish as {verdict} (score {score:.4f}): "
                    f"{structured.get('name')}")
        log_event("publish", f"[DRY RUN] Would publish as {verdict}: {structured.get('name')}",
                   status="info")
    else:
        doc_id = push_bursary(structured, verdict, score, url)
        logger.info(f"{verdict.upper()} — pushed to DB (ID: {doc_id}). "
                    f"Score ({score:.4f}): {structured.get('name')}")
        log_event("publish", f"Pushed as {verdict}: {structured.get('name')}", status="success",
                   data={"doc_id": doc_id, "name": structured.get("name"), "verdict": verdict,
                         "score": score, "url": url})


def run_pipeline():
    start_run()  # resets pipeline_run_log.json for this run
    logger.info(f"Pipeline run started (DRY_RUN={DRY_RUN}, "
                f"Gemini budget remaining today: {quota_tracker.remaining()})")

    log_event("discover", "Starting discovery run")
    target_urls = discover_urls()

    if not target_urls:
        logger.info("No new bursaries found this run.")
        log_event("discover", "No new bursaries found this run", status="info")
        finish_run()
        return

    processed = 0
    failed = 0

    for url in target_urls:
        try:
            _process_one_url(url)
            processed += 1
        except Exception as e:
            # Last-resort safety net: something truly unexpected happened
            # for this URL. Log it, move on, don't let it kill the whole
            # unattended run.
            failed += 1
            logger.error(f"Unexpected error processing {url}, skipping and continuing: {e}",
                         exc_info=True)
            log_event("error", f"Unexpected error on {url}: {e}", status="error", data={"url": url})

    logger.info(f"Pipeline run finished. {processed} URLs processed, {failed} hit unexpected "
                f"errors. Gemini budget remaining today: {quota_tracker.remaining()}")
    finish_run()


if __name__ == "__main__":
    run_pipeline()