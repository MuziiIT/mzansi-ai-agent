# Mzansi Bursaries Scraper & AI Pipeline — Change Log

This document summarizes the debugging, fixes, and enhancements made to the bursary
scraping and AI validation pipeline across this session, in the order they were made.

---

## 1. Background

The system crawls bursary "directory" sites (e.g. `zabursaries.co.za`,
`mybursaries.com`) to discover individual bursary postings, then follows each
posting to find the **real, official application link** offered by the actual
funding provider (a bank, corporate sponsor, government department, etc.) — not
the directory site itself.

Once a link is found, it's run through the existing AI pipeline:

```
scraper.py → classifier.py (scam_classifier.joblib) → llm_extract.py (Gemini) → firestore_client.py
```

---

## 2. `scraper.py` — Discovery & Extraction Fixes

### 2.1 `extract_application_link()` — new function
Finds the real "Apply Now" / application link on a bursary detail page, since the
directory site almost never hosts the actual application itself.

- Scores candidate `<a>` tags using a keyword list (`CTA_KEYWORDS`) and gives a
  bonus to links pointing to an **external domain**, since the real application
  link is expected to live elsewhere.
- Ignores social media / junk domains (`IGNORED_DOMAINS`).
- **Bug found & fixed:** the original keyword list only matched phrases like
  `"apply"`, `"apply now"`, `"register"`. Real pages used different, unpredicted
  wording:
  - `"Application link portal"` (Sasol Bursary, mybursaries.com)
  - `"complete an online application form"` (Old Mutual Bursary, mid-sentence,
    not a button)
  
  Fixed by expanding `CTA_KEYWORDS` to include `"application"`, `"application
  form"`, `"application link"`, `"application portal"`, `"online application"`,
  `"portal"`, verified against the real fetched HTML of both pages.

### 2.2 `RELEVANT_PATH` regex — substring bug fixed
The original regex `r"(bursar|scholar|fund|grant|apply|program|study|opportunity)"`
had no word boundaries, so `"fund"` matched as a substring inside **"Fundi"** (a
sponsor/platform brand name), incorrectly pulling in an unrelated page.

Fixed with word-boundaried, more specific patterns:
```python
RELEVANT_PATH = re.compile(
    r"\b(bursar(?:y|ies)|scholar(?:ship|ships)?|fund(?:ing)?|grant(?:s)?|"
    r"apply|program(?:me)?|stud(?:y|ies)|opportunit(?:y|ies))\b",
    re.IGNORECASE,
)
```

### 2.3 `GUIDE_ARTICLE_PATTERN` — new blacklist
Directory sites publish SEO/keyword-targeted blog articles (e.g. "Where To Find
Economics And Business Science Bursaries", "Your Bursary Guide") alongside real
postings. These legitimately contain the word "bursary" so the keyword filter
alone couldn't exclude them. Added a phrase blacklist to skip guide/how-to style
content:
```python
GUIDE_ARTICLE_PATTERN = re.compile(
    r"(where to (find|secure|apply|get)|how to (apply|find)|"
    r"\btips\b|\bguide\b|list of|available in|top \d+)",
    re.IGNORECASE,
)
```

### 2.4 URL path-depth filter — new
Even after the above two fixes, one more false positive remained: `"Fundi |
Bursaries Portal"` — a sitewide branding link. Its anchor text legitimately
contains "Bursaries" (part of the site's own tagline, appended to every link on
the site), so keyword filtering alone can't exclude it.

Fixed by requiring the candidate link's URL path to have **at least 2 segments**
(e.g. `/engineering-bursaries/company-bursary/`), since real individual postings
on these sites are nested under a category folder, while root-level pages
(`/fundi/`, `/nsfas/`, `/bursary-guide/`) are single-segment info/branding pages.

### 2.5 `extract_internal_links()` — repurposed as level-2 discovery
Unchanged in role, but now benefits from all three fixes above (2.2–2.4): it finds
the individual bursary **detail pages** on a directory's listing page, filtering
out guide articles, branding pages, and false keyword matches.

### 2.6 `crawl_programme_links()` — new function
Given a list of detail-page URLs, fetches each one and runs
`extract_application_link()` on it, returning the *company's own* application
link for each posting — not the directory site's URL.

### 2.7 `scrape_bursary_page()` — added (was missing)
`ai_pipeline.py` was already importing this function, but it didn't exist in
`scraper.py`. Added it: fetches a single detail page, returns `raw_text` (page
text *plus* a list of `[anchor text](href)` pairs so the LLM extractor can see
actual links, not just prose) and the heuristic `application_link`.

### 2.8 `duckduckgo_search` → `ddgs`
The `duckduckgo_search` package was renamed upstream to `ddgs`. Updated the
import (`from ddgs import DDGS`) to remove the deprecation warning. Added `ddgs`
and `lxml` (used but previously missing) to `requirements.txt`.

---

## 3. `run_automated_pipeline()` — wiring changes

- Previously returned raw `internal_links` (the directory site's own URLs) for
  display.
- Now calls `crawl_programme_links()` on those internal links and returns
  `programme_links` instead — a list of `{title, detail_page, provider_link}`
  dicts pointing at the actual funding providers.

---

## 4. `app.py` (Streamlit UI)

- Displays `programme_links` (real company "Apply Now" buttons) instead of the
  old `internal_links` (zabursaries' own URLs), per explicit request to stop
  showing the directory site's links.
- Updated the results metric, description text, and per-site results panel
  accordingly.
- Added a missing `import time` (used by `time.sleep(0.8)`, which would have
  crashed on first run).

---

## 5. `llm_extract.py` — fallback link support

`extract_fields()` now accepts an optional `fallback_link` argument. If Gemini's
JSON response comes back with an empty `"link"` field, the heuristic
`application_link` found by the scraper is used instead, so a missing/failed LLM
extraction doesn't silently drop the application URL.

## 6. `ai_pipeline.py` — wiring for the fallback

Passes `scraped["application_link"]` through as `fallback_link` when calling
`extract_fields()`.

---

## 7. Firestore schema alignment

Compared the LLM's output schema against the **actual live Firestore document**
structure and found a type mismatch:

| Field | LLM prompt currently returns | Actual Firestore type |
|---|---|---|
| `deadline` | plain string (e.g. `"31 August 2026"`) | **Timestamp** |
| `createdAt` | n/a (set by script) | Timestamp ✅ already correct |
| `field` | string (e.g. `"All_field"`) | string ✅ matches |

**Fix (in `firestore_client.py`):** parse the LLM's `deadline` string into a real
Python `datetime` before writing, so `firebase-admin` converts it to a proper
Firestore Timestamp on write instead of storing plain text:

```python
from dateutil import parser as date_parser

def push_bursary(data: dict, status: str, scam_score: float, source_url: str):
    deadline_str = data.get("deadline", "")
    try:
        data["deadline"] = date_parser.parse(deadline_str) if deadline_str else None
    except (ValueError, TypeError):
        data["deadline"] = None

    doc = {
        **data,
        "source_url": source_url,
        "status": status,
        "scam_score": scam_score,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    db.collection("bursaries").add(doc)
```

Requires `python-dateutil` — added to `requirements.txt`.

---

## 8. Verification performed

All fixes above were tested against **real, live-fetched HTML** (via `web_fetch`)
from `mybursaries.com`, not just synthetic mock data:

- `https://mybursaries.com/` (listing page) — confirmed only genuine bursary
  posts survive the filter (Sasol, Old Mutual), while the Coca-Cola learnership,
  pagination links, tag links, and category links are correctly excluded.
- `https://mybursaries.com/post/sasol-bursary-2027.html` — confirmed
  `extract_application_link()` correctly finds
  `https://www.sasolbursaries.com/portal/register/` from the anchor text
  "Application link portal".
- `https://mybursaries.com/post/old-mutual-accounting-bursary-2027.html` —
  confirmed the same function finds
  `https://oldmutual.wd3.myworkdayjobs.com/.../Chartered-Accounting-Bursary-Programme_JR-78372`
  from an inline sentence link, not a button.

A synthetic mock replicating `zabursaries.co.za`'s known structure (branding
suffix "Bursaries Portal" on every link, `/fundi/` sponsor page, guide articles)
was also used to isolate and confirm the substring-matching bug and the
path-depth fix.

---

## 9. Outstanding / not yet done

- **Firestore `deadline` fix**: code written and reviewed in this session, but
  not yet committed — recommended to go on its own branch
  (`fix/deadline-timestamp-conversion`) since it touches production data
  shape.
- **`field` schema drift**: earlier prompt drafts showed `"fields_of_study":
  ["Field 1", "Field 2"]` as an array in one version, but the live schema uses a
  single string (`"All_field"`). Worth confirming which format the Flask
  front-end actually expects before the next LLM prompt revision.
- **Deep-crawl cost**: `crawl_programme_links()` fetches every detail page found
  on a directory's listing page, in addition to the listing page itself. For a
  directory with e.g. 10 postings, that's 11+ requests per site — no cap is
  currently set on how many detail pages get deep-crawled per run.
- **Discovery-layer approaches (sitemap/RSS/category-queue/Scrapy)**: discussed
  as free, zero-cost alternatives to the current search-based discovery, but not
  yet implemented — only proposed with sample flow diagrams.