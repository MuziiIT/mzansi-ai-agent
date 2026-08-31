import json
from scraper import scrape_bursary_page
from classifier import get_scam_probability, get_verdict
from llm_extract import extract_fields
from firestore_client import bursary_exists, push_bursary, log_rejected

TARGET_URLS = [
    "https://www.zabursaries.co.za/engineering-bursaries-south-africa/altron-bill-venter-academy-bursary/",
]

# --- SAFETY SWITCH ---
# True = Print to terminal only (Testing Mode)
# False = Push to Firebase (Live Production Mode)
DRY_RUN = True  

def run_pipeline():
    for url in TARGET_URLS:
        # We only check for duplicates in the DB if we are doing a live run
        if not DRY_RUN and bursary_exists(url):
            print(f"[*] Skipping duplicate URL: {url}")
            continue
            
        try:
            scraped = scrape_bursary_page(url)
        except Exception as e:
            print(f"[-] Scrape failed for {url}: {e}")
            continue

        score = get_scam_probability(scraped["raw_text"])
        verdict = get_verdict(score)

        if verdict == "rejected":
            if not DRY_RUN:
                log_rejected(scraped, score)
            print(f"[REJECTED] Scam Score ({score:.4f}): {url}")
            continue

        # Extract structured data using Gemini
        structured = extract_fields(scraped["raw_text"])
        
        # --- THE TESTING FORK ---
        if DRY_RUN:
            print("\n--- 🛑 DRY RUN MODE ENABLED 🛑 ---")
            print(f"Target URL: {url}")
            print(f"AI Verdict: {verdict.upper()} | Scam Score: {score:.4f}")
            print("Generated Firebase JSON:")
            print(json.dumps(structured, indent=2))
            print("-----------------------------------\n")
        else:
            # Write directly to Firebase
            push_bursary(structured, verdict, score, url)
            print(f"[{verdict.upper()}] Pushed to DB. Score ({score:.4f}): {structured.get('name')}")

if __name__ == "__main__":
    run_pipeline()