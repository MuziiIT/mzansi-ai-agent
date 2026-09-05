"""
config.py — centralized configuration for the Mzansi Bursaries AI pipeline.

Import from here instead of scattering magic numbers, thresholds, and
secret-loading logic across individual files. Fails fast with a clear
message if a required secret is missing, instead of a confusing crash
three files deep.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()


def _require(value, name: str, hint: str):
    if not value:
        print(f"[CONFIG ERROR] Missing required setting: {name}")
        print(f"  {hint}")
        sys.exit(1)
    return value


# --- Required secrets ------------------------------------------------------

GEMINI_API_KEY = _require(
    os.getenv("GEMINI_API_KEY"),
    "GEMINI_API_KEY",
    "Set this in your .env file: GEMINI_API_KEY=your-key-here",
)

SERVICE_ACCOUNT_PATH = os.getenv("SERVICE_ACCOUNT_PATH", "serviceAccountKey.json")
if not os.path.isfile(SERVICE_ACCOUNT_PATH):
    print(f"[CONFIG ERROR] Firebase service account file not found: {SERVICE_ACCOUNT_PATH}")
    print("  Download a fresh key from Firebase Console -> Project Settings -> Service Accounts")
    sys.exit(1)

# --- Classifier thresholds --------------------------------------------------

APPROVED_MAX = float(os.getenv("APPROVED_MAX", "0.30"))
FLAGGED_MAX = float(os.getenv("FLAGGED_MAX", "0.60"))

# --- Discovery settings ------------------------------------------------------

HUB_URLS = [
    "https://allbursaries.co.za/",
    "https://www.zabursaries.co.za/",
]
DEFAULT_LISTING_LIMIT = int(os.getenv("DEFAULT_LISTING_LIMIT", "150"))
RESOLVE_WORKERS = int(os.getenv("RESOLVE_WORKERS", "8"))

# --- Pipeline mode -----------------------------------------------------------
# Defaults to live (writes to Firestore). Override with DRY_RUN=true in .env
# for a throwaway test run without touching the database.
DRY_RUN = os.getenv("DRY_RUN", "false").strip().lower() == "true"

# --- Gemini model + quota safety --------------------------------------------

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Free-tier quotas are often capped low (you hit a 20/day wall in testing).
# Set this comfortably under your actual plan's daily limit so the pipeline
# stops cleanly and tells you why, instead of burning retries against a
# wall it can't see. Adjust via .env if your plan/limit changes.
GEMINI_DAILY_REQUEST_BUDGET = int(os.getenv("GEMINI_DAILY_REQUEST_BUDGET", "18"))

# --- Logging -----------------------------------------------------------------

LOG_DIR = os.getenv("LOG_DIR", "logs")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")