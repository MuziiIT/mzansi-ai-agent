import streamlit as st
from discover import discover_urls
from scraper import scrape_bursary_page
from classifier import get_scam_probability, get_verdict
from llm_extract import extract_fields
from firestore_client import bursary_exists, push_bursary, log_rejected
from progress_logger import start_run, log_event, finish_run

st.set_page_config(
    page_title="Mzansi AI Bursary Agent - Real-Time Monitor",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Mzansi AI Agent — Autonomous Pipeline Dashboard")
st.caption("Real-time discovery, scam screening, and direct application link extraction.")

# --- Sidebar ---------------------------------------------------------
st.sidebar.header("Pipeline Controls")
dry_run_toggle = st.sidebar.toggle("DRY RUN MODE (Safe — No DB Writes)", value=True)
max_url_limit = st.sidebar.slider("Max URLs to process for test", min_value=1, max_value=20, value=5)

if dry_run_toggle:
    st.sidebar.info("🔒 SAFE MODE ACTIVE: nothing is written to Firebase.")
else:
    st.sidebar.warning("⚠️ LIVE MODE: approved/flagged items WILL be pushed to Firestore.")

st.sidebar.caption(
    "Every run — dry or live — also writes to pipeline_run_log.json, "
    "so live_dashboard.html shows the same run if you have it open."
)

# --- Main run ----------------------------------------------------------
if st.button("🚀 Run Pipeline", type="primary"):
    st.divider()
    start_run()
    log_event("discover", "Streamlit run started",
               data={"dry_run": dry_run_toggle, "limit": max_url_limit})

    with st.spinner("Crawling aggregator hubs for fresh bursary links..."):
        # In live mode, skip URLs already in Firestore. In dry-run mode,
        # allow re-testing on already-published URLs.
        discovered_urls = discover_urls(skip_existing=not dry_run_toggle)

    if not discovered_urls:
        st.warning("No new bursaries found on configured hub pages.")
        log_event("discover", "No new bursaries found this run", status="info")
        finish_run()
    else:
        st.success(f"Discovered {len(discovered_urls)} candidate URLs! Processing top {max_url_limit}...")
        test_batch = discovered_urls[:max_url_limit]

        col1, col2, col3, col4 = st.columns(4)
        approved_metric = col1.metric("Approved", 0)
        flagged_metric = col2.metric("Flagged", 0)
        rejected_metric = col3.metric("Rejected", 0)
        processed_metric = col4.metric("Total Processed", 0)

        counts = {"approved": 0, "flagged": 0, "rejected": 0, "total": 0}

        for idx, url in enumerate(test_batch):
            st.markdown(f"### 📍 Item {idx+1}: `{url}`")

            # Dedup check inside the batch too — discover_urls already did this
            # in live mode, but re-check here in case the batch loop takes a
            # while and something else pushed the same URL meanwhile.
            if not dry_run_toggle and bursary_exists(url):
                st.info("Already in Firestore — skipping.")
                log_event("skip", f"Duplicate, already in Firestore: {url}", status="info")
                continue

            with st.status(f"Processing URL {idx+1}/{len(test_batch)}...", expanded=True) as status:
                st.write("🕷️ Scraping plain text & inline destination URLs...")
                try:
                    log_event("scrape", f"Scraping: {url}")
                    scraped = scrape_bursary_page(url)
                    log_event("scrape", f"Scraped OK: {url}", status="success")
                except Exception as e:
                    st.error(f"Scrape failed: {e}")
                    log_event("scrape", f"Scrape failed for {url}: {e}", status="error")
                    status.update(label="Scrape failed", state="error", expanded=True)
                    continue

                st.write("🧠 Running ML Scam Risk Classifier...")
                score = get_scam_probability(scraped["raw_text"])
                verdict = get_verdict(score)
                log_event("classify", f"Score {score:.4f} -> {verdict}", status="info",
                           data={"url": url, "score": score, "verdict": verdict})

                if verdict == "approved":
                    st.success(f"Verdict: **APPROVED** | Scam Score: `{score:.4f}`")
                    counts["approved"] += 1
                elif verdict == "flagged":
                    st.warning(f"Verdict: **FLAGGED FOR REVIEW** | Scam Score: `{score:.4f}`")
                    counts["flagged"] += 1
                else:
                    st.error(f"Verdict: **REJECTED** | Scam Score: `{score:.4f}`")
                    counts["rejected"] += 1

                counts["total"] += 1

                if verdict == "rejected":
                    if not dry_run_toggle:
                        log_rejected(scraped, score)
                    log_event("reject", f"Rejected (score {score:.4f}): {url}", status="warning",
                               data={"url": url, "score": score})
                    status.update(label=f"Done: REJECTED ({score:.4f})", state="complete", expanded=False)
                else:
                    st.write("✨ Extracting structured JSON with Gemini...")
                    log_event("extract", f"Extracting structured fields: {url}")
                    structured = extract_fields(scraped["annotated_text"], scraped.get("direct_links", []))

                    if not structured.get("name"):
                        st.error("Extraction produced no usable data — skipping publish for this one.")
                        log_event("extract", f"Extraction incomplete (no name found): {url}",
                                   status="warning", data={"url": url})
                        status.update(label="Extraction incomplete", state="error", expanded=True)
                        continue

                    log_event("extract", f"Extracted: {structured.get('name', url)}", status="success")

                    direct_link = structured.get("link", "")
                    st.markdown("#### 🎯 Extracted Bursary Details:")
                    st.json(structured)

                    if direct_link:
                        display_link = direct_link if direct_link.startswith("http") else "https://" + direct_link
                        st.markdown(f"👉 **Direct Application URL:** [{direct_link}]({display_link})")
                    else:
                        st.caption("⚠️ Direct link not found on source page — will need manual review.")

                    if dry_run_toggle:
                        log_event("publish", f"[DRY RUN] Would publish as {verdict}: {structured.get('name')}",
                                   status="info")
                        st.caption("🔒 Dry run — not written to Firestore.")
                    else:
                        doc_id = push_bursary(structured, verdict, score, url)
                        log_event("publish", f"Pushed as {verdict}: {structured.get('name')}", status="success",
                                   data={"doc_id": doc_id, "name": structured.get("name"),
                                         "verdict": verdict, "score": score, "url": url})
                        st.caption(f"✅ Pushed to Firestore — doc ID `{doc_id}`")

                    status.update(label=f"Done: {verdict.upper()} ({score:.4f})", state="complete", expanded=False)

            approved_metric = col1.metric("Approved", counts["approved"])
            flagged_metric = col2.metric("Flagged", counts["flagged"])
            rejected_metric = col3.metric("Rejected", counts["rejected"])
            processed_metric = col4.metric("Total Processed", counts["total"])
            st.divider()

        finish_run()
        st.info("Run complete. See pipeline_run_log.json / live_dashboard.html for the full event log.")