Markdown
# Mzansi Bursaries AI Agent 

An autonomous Artificial Intelligence pipeline designed to protect South African students from fraudulent educational funding schemes while eliminating manual data entry for administrators. 

This agent crawls target bursary websites, evaluates the legitimacy of the opportunities using a Supervised Machine Learning model, extracts key details using Generative AI, and automatically syncs the verified data to a Firebase Firestore database.

---

##  AI & Machine Learning Architecture

This project practically applies core Machine Learning concepts to solve a real-world problem:

* **Supervised Learning (Binary Classification):** The legitimacy engine (`classifier.py`) uses a trained Random Forest model. Supervised learning operates under guidance using labeled data[cite: 14]. Specifically, this is a binary classification task, which sorts data into one of two distinct categories (e.g., "Legit" vs. "Scam")[cite: 14].
* **Data Pre-processing:** The web scraper (`scraper.py`) cleans messy HTML tags into raw text before feeding it to the model. This addresses the "Garbage In, Garbage Out (GIGO)" principle, recognizing that poor-quality data leads to poor-quality predictions[cite: 15].
* **Scientific Computing Toolkit:** Built using industry-standard Python libraries for data analysis and model building, which makes Python the most popular programming language for machine learning[cite: 9].

---

##  System Components

1. **`scraper.py`**: A BeautifulSoup4 web spider that securely extracts readable text from target URLs.
2. **`classifier.py`**: Loads `scam_classifier.joblib` to calculate a Scam Probability Score.
    * *Score <= 0.30:* **Approved**
    * *Score 0.31 - 0.60:* **Flagged for Review**
    * *Score > 0.60:* **Rejected**
3. **`llm_extract.py`**: Uses the Google Gemini 3.6 Flash model to extract unstructured text into a strict JSON schema.
4. **`firestore_client.py`**: Connects to the live Firebase database, handling URL deduplication and system timestamps.
5. **`ai_pipeline.py`**: The main orchestration script that ties all modules together.

---

## Getting Started

### Prerequisites
* Python 3.11+
* A Google Gemini API Key
* A Firebase Service Account Private Key (`serviceAccountKey.json`)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/MuziiIT/mzansi-ai-agent.git](https://github.com/MuziiIT/mzansi-ai-agent.git)
   cd mzansi-ai-agent
Create and activate a virtual environment:

Bash
# Windows
python -m venv venv
source venv/Scripts/activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
Install dependencies:

Bash
pip install -r requirements.txt
Configuration
Place your trained model (scam_classifier.joblib) into the root directory.

Place your Firebase credentials file (serviceAccountKey.json) into the root directory.

Create a .env file in the root directory and add your Gemini API key:

Plaintext
GEMINI_API_KEY=your_actual_api_key_here
(Note: Both .env and serviceAccountKey.json are strictly ignored by Git to prevent credential leakage).

 Usage
Testing (Dry-Run Mode)
It is highly recommended to test new target URLs before pushing data to the live database.

Open ai_pipeline.py.

Set DRY_RUN = True at the top of the file.

Run the pipeline:

Bash
python ai_pipeline.py
This will print the AI's verdict, the scam score, and the generated JSON directly to your terminal without altering Firebase.

Live Production
Once you verify the JSON output is correct:

Open ai_pipeline.py.

Set DRY_RUN = False.

Run the script to automatically publish the verified bursary to the student front-end.

Built for the BICT332  Group Project.


***

Now that your repository is documented, would you like to move on to updating your Flask web application to display the "AI Flagged Review" tab for the borderline bursaries?






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
