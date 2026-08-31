import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def scrape_bursary_page(url: str) -> dict:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Remove junk tags
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
        
    text_content = " ".join(soup.stripped_strings)
    return {
        "source_url": url,
        "raw_text": text_content,
        "title_guess": soup.title.string if soup.title else ""
    }
