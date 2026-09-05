# Mzansi Bursaries AI Engine (RECAB) — Project README & Roadmap

This technical document outlines the architecture, current implementation progress, component inventory, and future roadmap for the Mzansi Bursaries AI Engine. It is intended to align team members on project status, security protocols, and upcoming integration tasks.

---

## 1. Project Overview & Architecture

The Mzansi Bursaries AI Engine is an autonomous pipeline designed to discover, vet, extract, and categorize South African bursary opportunities in real time. It eliminates manual link searching by crawling aggregator sitemaps, filtering out noise, running machine learning-based scam detection, extracting structured JSON via Gemini LLMs, and pushing verified listings to Google Cloud Firestore.

### End-to-End Pipeline Flow

- **Discovery (`discover.py`)**: Crawls aggregator sitemaps (e.g., `zabursaries.co.za`, `allbursaries.co.za`), applies depth/skip regex patterns, and concurrently resolves outbound direct sponsor application links using a multi-threaded worker pool.
- **Scraping (`scraper.py`)**: Fetches target pages, strips non-essential markup, guards against binary PDF links, and generates dual text versions: a clean text block for scam classification and an annotated text block (`[DIRECT_LINK: ...]`) for LLM link-extraction.
- **Classification (`classifier.py`)**: Computes a scam probability risk score using a trained machine learning model. System thresholds classify records into:
  - **Approved**: Score ≤ 0.30
  - **Flagged**: Score 0.31 – 0.60
  - **Rejected**: Score > 0.60
- **Extraction (`llm_extract.py`)**: Sends text to the Gemini API (`gemini-3.5-flash-lite`) with a strict JSON schema prompt to extract the bursary name, provider, description, fields of study, deadline text, and official direct application link.
- **Validation & Filtering (`deadline_utils.py`)**: Parses human-readable deadline strings into timezone-aware datetimes and drops expired opportunities to prevent publishing stale listings.
- **Storage (`firestore_client.py`)**: Pushes validated structured JSON records with native Firestore Timestamp fields into the database.

---

## 2. File Inventory & Component Status

| Component | File | Status | Description |
|-----------|------|--------|-------------|
| Discovery | `discover.py` | Completed | Sitemap-based discovery crawler with multi-threaded outbound link resolution. |
| Scraping | `scraper.py` | Completed | Dual-text extraction scraper (classifier vs. LLM) with PDF and junk-tag guards. |
| Classification | `classifier.py` | Completed | ML model interface returning scam probability risk scores. |
| Extraction | `llm_extract.py` | Completed | Link-aware Gemini structured JSON extractor with retry logic and quota management. |
| Validation | `deadline_utils.py` | Completed | Fuzzy date parsing, expiry checking, and Firestore Timestamp alignment. |
| Orchestrator | `ai_pipeline.py` | Completed | Main orchestrator managing batch processing, crash isolation, and logging. |
| Configuration | `config.py` | Completed | Centralized settings manager with fail-fast secret validation. |
| Quota Manager | `quota_tracker.py` | Completed | Local daily API budget manager to prevent hitting provider rate limits. |
| Logging | `logger_setup.py` | Completed | Dual-channel logger writing to console and persistent files (`logs/pipeline.log`). |
| Dashboard | `dashboard.py` | Completed | Local Streamlit UI for real-time monitoring and safe dry-run testing. |
| Tests | `test_deadline_utils.py` | Completed | Comprehensive unit test suite (all 8 tests passing). |
| Git Ignore | `.gitignore` | Completed | Protects sensitive keys (`serviceAccountKey.json`, `.env`) and local state files. |

---

## 3. Security & Operational Hardening

- **Credential Protection**: Following an early-stage service account key exposure, credentials have been revoked, regenerated via the Firebase Console, and bound strictly to `.gitignore` to prevent repository leakage.
- **Database Safety Isolation**: A `DRY_RUN` configuration flag enables safe testing via the Streamlit dashboard (`dashboard.py`) and terminal runs without writing to production Firestore collections.
- **Quota Management**: Integrated local budgeting tracking (`quota_tracker.py`) paired with an optimized model selection (`gemini-3.5-flash-lite`) ensures daily API limits are respected.

---

## 4. Current Progress & Verified Milestones

- End-to-end dry-run executions successfully crawl, resolve, classify, and filter over 100+ live listings per test batch without unexpected runtime crashes.
- Automated date parsing successfully catches and drops expired deadlines, ensuring data integrity.
- Direct application link resolution successfully bypasses aggregator landing pages so end-users navigate straight to official company portals.

---

## 5. Roadmap & Pending Implementation Items

The following items remain on the project development backlog for team completion:

- **Flask Admin Integration**: Build and integrate the AI Flagged Review tab inside the admin panel (`admin.html`) so human moderators can review, approve, or reject borderline listings.
- **Public Service Query Filtering**: Update `bursaries_service.py` data queries to restrict public-facing views strictly to records where `status == "approved"`.
- **Legacy Document Strategy**: Coordinate team resolution for pre-AI legacy Firestore documents that lack a `status` field (options include backfilling a default `"approved"` status or updating database queries to gracefully treat missing status fields as active).
- **Production Automation**: Configure Windows Task Scheduler or a cron job to handle automated nightly unattended runs.


# Teammate Reference: AI Firestore Schema & Admin Requirements

## 1. The Collections (Where to Look)

| Collection | Purpose |
|------------|---------|
| `ai_bursaries` | **Staging collection.** Your AI Review page fetches all data only from here. |
| `bursaries` | **Live, public-facing collection.** The AI pipeline reads this to prevent duplicates, but never writes to it. |

---

## 2. The Split-Screen Logic (The `status` Field)

When rendering the two columns on the Admin page, split documents based on the `status` field:

| Column | Query |
|--------|-------|
| **Left Column** (Approved by AI) | `status == "legit"` *(Note: Python maps the AI's "approved" verdict to `"legit"` in the DB)* |
| **Right Column** (Needs Review) | `status == "flagged"` |

> **Rejected items** never make it to Firestore; they are logged to a local CSV file, so you won't see them in the DB.

---

## 3. The Document Schema (Available Fields for HTML)

Every document in `ai_bursaries` contains these exact keys for UI cards:

| Field | Description |
|-------|-------------|
| `name` | The bursary title. |
| `provider` | The sponsor/company name. |
| `description` | The extracted text description. |
| `field` | The fields of study. |
| `link` | The direct application URL. |
| `deadline_text` | Original human-readable date string (e.g., `"31 August 2026"`). |
| `deadline` | Native Firestore Timestamp object. |
| `source_url` | The aggregator page where the AI found this listing. |
| `scam_score` | Float number (e.g., `0.2867`) representing the AI's risk assessment. |
| `createdAt` | Native Firestore Server Timestamp. |

---

## 4. Admin Button Actions (JS/Backend Requirements)

| Button | Action |
|--------|--------|
| **Approve** | Copy the full document from `ai_bursaries` into `bursaries`, then delete the original from `ai_bursaries`. |
| **Reject** | Permanently delete the document from `ai_bursaries`. |
EOF

