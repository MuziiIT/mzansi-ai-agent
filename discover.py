"""
discover.py — Hub crawler for the Mzansi Bursaries AI pipeline.
No paid APIs, no search engine — just requests + BeautifulSoup.

Two stages, both free:
  1. Find individual bursary pages on each hub site, preferring that
     site's sitemap.xml (lists every post automatically, no need to
     guess homepage link patterns) and falling back to homepage-link
     scraping if no sitemap is found.
  2. Visit each of those pages and resolve the real outbound "apply"
     link — the sponsor's own site — so testing this file directly
     shows you the actual bursary, not the aggregator's page.
"""

import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed

from firestore_client import bursary_exists
from progress_logger import log_event

# How many listing pages to resolve per run, and how many at once.
# Sitemaps can easily return 1,000+ pages — resolving all of them one at a
# time would take an hour+ and hammer the target site. Cap + parallelize.
DEFAULT_LISTING_LIMIT = 150
RESOLVE_WORKERS = 8

# --- Configuration ---------------------------------------------------

# The only manual part left: which sites to check. Add a new one here
# any time you find another bursary-posting site — that's it, no other
# code changes needed.
HUB_URLS = [
    "https://allbursaries.co.za/",
    "https://www.zabursaries.co.za/",
]

HUB_DOMAINS = {urlparse(u).netloc.replace("www.", "") for u in HUB_URLS}

KEYWORD_PATTERN = re.compile(
    r"bursar|scholarship|funding|internship-programme", re.IGNORECASE
)

SKIP_PATTERN = re.compile(
    r"(facebook\.com|twitter\.com|x\.com|instagram\.com|/category/|/tag/|"
    r"/page/\d+|#|/student-accommodation/|/student-loans/|/how-to-|"
    r"/tips-to-|/privacy-policy|/universities/|/internships/|/learnerships/|"
    r"/vac-work|/what-expenses|/national-benchmark-test|/nsfas-funding|"
    r"/sassa-grants|/preparing-for-a-bursary-interview|sitemap)",
    re.IGNORECASE,
)

APPLY_KEYWORDS = re.compile(
    r"apply|official (site|website)|company website|visit website|"
    r"click here|more info|read more|application (form|link)",
    re.IGNORECASE,
)

NOISE_DOMAINS = re.compile(
    r"(facebook\.com|twitter\.com|x\.com|instagram\.com|linkedin\.com|"
    r"whatsapp\.com|pinterest\.com|youtube\.com|google\.com/recaptcha|"
    r"doubleclick\.net)",
    re.IGNORECASE,
)

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MzansiBursariesBot/1.0)"}
REQUEST_TIMEOUT = 15


def _is_valid_bursary_path(path: str) -> bool:
    parts = [p for p in path.split("/") if p]
    return len(parts) >= 2


# --- Stage 1a: sitemap-based discovery (preferred, free, complete) ------

def _fetch_xml(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except Exception:
        return None


def _sitemap_urls_for_domain(base_url: str) -> set:
    """Walk a site's sitemap (and any nested sitemaps, one level deep)
    and return every individual page URL listed. Free, no API needed —
    just the standard sitemap.xml every WordPress-based site publishes."""
    base = base_url.rstrip("/")
    all_urls = set()
    seen = set()

    def process(sm_url, depth=0):
        if sm_url in seen or depth > 2:
            return
        seen.add(sm_url)
        root = _fetch_xml(sm_url)
        if root is None:
            return
        tag = root.tag.lower()
        if tag.endswith("sitemapindex"):
            for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
                if loc.text:
                    process(loc.text.strip(), depth + 1)
        elif tag.endswith("urlset"):
            for loc in root.findall("sm:url/sm:loc", SITEMAP_NS):
                if loc.text:
                    all_urls.add(loc.text.strip())

    for candidate in (f"{base}/sitemap_index.xml", f"{base}/sitemap.xml"):
        process(candidate)
        if all_urls:
            break

    return all_urls


# --- Stage 1b: homepage-link fallback (used only if no sitemap found) ---

def _homepage_links(hub_url: str) -> set:
    candidates = set()
    try:
        resp = requests.get(hub_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log_event("discover", f"Failed to fetch hub {hub_url}: {e}", status="error")
        return candidates

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True) or ""
        if SKIP_PATTERN.search(href):
            continue
        if not (KEYWORD_PATTERN.search(text) or KEYWORD_PATTERN.search(href)):
            continue
        full_url = urljoin(hub_url, href)
        if full_url.rstrip("/") == hub_url.rstrip("/"):
            continue
        candidates.add(full_url)
    return candidates


def _find_listing_pages(hub_url: str) -> set:
    sitemap_urls = _sitemap_urls_for_domain(hub_url)
    if sitemap_urls:
        filtered = {
            u for u in sitemap_urls
            if not SKIP_PATTERN.search(u)
            and KEYWORD_PATTERN.search(u)
            and _is_valid_bursary_path(urlparse(u).path)
        }
        print(f"[discover]    (sitemap) {len(sitemap_urls)} pages found, {len(filtered)} look like bursaries")
        log_event("discover", f"Sitemap: {len(filtered)} bursary-like pages on {hub_url}",
                   status="success", data={"hub": hub_url, "count": len(filtered)})
        return filtered

    # No sitemap available — fall back to scanning the homepage's links.
    print(f"[discover]    No sitemap found for {hub_url}, falling back to homepage links")
    log_event("discover", f"No sitemap for {hub_url}, using homepage fallback", status="warning")
    found = _homepage_links(hub_url)
    log_event("discover", f"Homepage fallback: {len(found)} pages found on {hub_url}",
               status="success", data={"hub": hub_url, "count": len(found)})
    return found


# --- Stage 2: resolve the real outbound "apply" link --------------------

def resolve_outbound_link(listing_url: str) -> str | None:
    """Visit a listing page and find the actual sponsor link a student
    should land on. Returns None if nothing outbound is found."""
    try:
        resp = requests.get(listing_url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except requests.RequestException as e:
        log_event("discover", f"Failed to fetch listing {listing_url}: {e}", status="error")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.find("article") or soup.find(class_=re.compile("content|entry|post"))
    scope = content if content else soup

    outbound = []
    for a in scope.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(strip=True) or ""
        if not href.startswith("http"):
            continue
        if NOISE_DOMAINS.search(href):
            continue
        link_domain = urlparse(href).netloc.replace("www.", "")
        if link_domain in HUB_DOMAINS:
            continue
        outbound.append((bool(APPLY_KEYWORDS.search(text)), href))

    if not outbound:
        return None

    apply_links = [u for is_apply, u in outbound if is_apply]
    return apply_links[0] if apply_links else outbound[0][1]


# --- Orchestration --------------------------------------------------------

def discover_urls(hub_urls: list[str] = None, skip_existing: bool = True,
                   limit: int = DEFAULT_LISTING_LIMIT) -> list[str]:
    hub_urls = hub_urls or HUB_URLS
    all_listings: set[str] = set()

    for hub in hub_urls:
        print(f"[discover] Checking hub: {hub}")
        log_event("discover", f"Checking hub: {hub}")
        all_listings.update(_find_listing_pages(hub))

    all_listings = sorted(all_listings)

    if limit and len(all_listings) > limit:
        print(f"[discover] Found {len(all_listings)} listing pages — capping this run to the "
              f"first {limit} (pass limit=None to process all, but that will be slow).")
        log_event("discover", f"Capped run to {limit} of {len(all_listings)} listing pages",
                   status="info")
        all_listings = all_listings[:limit]

    print(f"[discover] Resolving outbound apply links for {len(all_listings)} listing pages "
          f"({RESOLVE_WORKERS} at a time)...")
    log_event("discover", f"Resolving outbound links for {len(all_listings)} listing pages")

    resolved_urls = []
    skipped = 0
    done = 0
    total = len(all_listings)

    with ThreadPoolExecutor(max_workers=RESOLVE_WORKERS) as executor:
        future_to_listing = {executor.submit(resolve_outbound_link, listing): listing
                              for listing in all_listings}
        for future in as_completed(future_to_listing):
            listing = future_to_listing[future]
            done += 1
            try:
                outbound = future.result()
            except Exception as e:
                outbound = None
                log_event("discover", f"Error resolving {listing}: {e}", status="error")

            if outbound:
                resolved_urls.append(outbound)
            else:
                skipped += 1
                log_event("discover", f"No outbound link found, skipped: {listing}", status="warning")

            if done % 20 == 0 or done == total:
                print(f"[discover]    ...resolved {done}/{total} "
                      f"({len(resolved_urls)} found, {skipped} skipped)")

    print(f"[discover] {len(resolved_urls)} resolved bursary links, {skipped} listings skipped (no outbound link)")

    resolved_urls = sorted(set(resolved_urls))

    if not skip_existing:
        return resolved_urls

    new_urls = []
    for url in resolved_urls:
        try:
            if not bursary_exists(url):
                new_urls.append(url)
        except Exception as e:
            print(f"[discover] Warning: dedup check failed for {url}: {e}")
            log_event("discover", f"Dedup check failed for {url}: {e}", status="warning")
            new_urls.append(url)

    print(f"[discover] {len(new_urls)} new URLs after Firestore dedup (out of {len(resolved_urls)} resolved)")
    log_event("discover", f"{len(new_urls)} new URLs after dedup", status="success",
               data={"new_count": len(new_urls), "resolved_count": len(resolved_urls)})
    return new_urls


if __name__ == "__main__":
    urls = discover_urls()
    print(f"\nDiscovered {len(urls)} new bursary URLs (already resolved to the real application link):")
    for u in urls:
        print(f"  {u}")