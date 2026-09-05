import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


class UnsupportedContentError(Exception):
    """Raised when a URL doesn't point at scrapeable HTML (e.g. a PDF)."""


def scrape_bursary_page(url: str) -> dict:
    if url.lower().split("?")[0].endswith(".pdf"):
        raise UnsupportedContentError(f"URL points directly at a PDF, not HTML: {url}")

    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()

    content_type = resp.headers.get("Content-Type", "").lower()
    if "pdf" in content_type or "application/octet-stream" in content_type:
        raise UnsupportedContentError(
            f"URL returned non-HTML content ({content_type or 'unknown'}), skipping: {url}"
        )

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove junk tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    # Collect outbound links BEFORE mutating anything, from a copy of the
    # tree, so we can build a clean plain-text version and a separate
    # LLM-annotated version without one affecting the other.
    direct_links = []  # (anchor_text, href), in document order
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        text = a.get_text(strip=True)
        if not text:
            img = a.find("img")
            if img and img.get("alt"):
                text = img["alt"].strip()
        if not text:
            text = "Apply"
        direct_links.append((text, href))

    # --- Plain text, for the ML classifier ---------------------------
    # No [DIRECT_LINK: ...] markers here. The classifier was trained on
    # ordinary article text — feeding it text full of raw URLs and bracket
    # tags it never saw in training can shift its scores unpredictably
    # (this is very likely why legitimate bursaries were scoring as
    # high-risk). Keep this version exactly as clean as the training data.
    plain_text = " ".join(soup.stripped_strings)

    # --- Annotated text, for the LLM extractor only -------------------
    # Re-parse a fresh copy so inserting markers here doesn't touch the
    # plain_text version above.
    soup_annotated = BeautifulSoup(resp.text, "html.parser")
    for tag in soup_annotated(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    for a in soup_annotated.find_all("a", href=True):
        href = a["href"].strip()
        if not href.startswith("http"):
            continue
        text = a.get_text(strip=True)
        if not text:
            img = a.find("img")
            if img and img.get("alt"):
                text = img["alt"].strip()
        if not text:
            text = "Apply"
        a.replace_with(f" {text} [DIRECT_LINK: {href}] ")
    annotated_text = " ".join(soup_annotated.stripped_strings)

    return {
        "source_url": url,
        "raw_text": plain_text,            # used for scam classification
        "annotated_text": annotated_text,  # used for LLM field extraction
        "title_guess": soup.title.string if soup.title else "",
        "direct_links": direct_links,
    }