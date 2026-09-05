import csv, os
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from deadline_utils import deadline_to_timestamp

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()


def bursary_exists(source_url: str) -> bool:
    # Uses the current filter= keyword syntax instead of the deprecated
    # positional (field, op, value) form — same behavior, no deprecation
    # warning.
    docs = (
        db.collection("bursaries")
        .where(filter=FieldFilter("source_url", "==", source_url))
        .limit(1)
        .stream()
    )
    return len(list(docs)) > 0


def push_bursary(data: dict, status: str, scam_score: float, source_url: str):
    # The extracted 'deadline' comes in as free text (e.g. "31 August 2026").
    # Convert it to a real Timestamp to match the live site's existing
    # schema — the original text is kept separately as 'deadline_text' so
    # nothing human-readable is lost, but 'deadline' itself is now a date
    # any Flask query can actually filter/sort on.
    deadline_text = data.pop("deadline", "")
    doc = {
        **data,
        "deadline": deadline_to_timestamp(deadline_text),
        "deadline_text": deadline_text,
        "source_url": source_url,
        "status": status,
        "scam_score": scam_score,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    try:
        update_time, doc_ref = db.collection("bursaries").add(doc)
    except Exception as e:
        # Don't let one bad write kill the whole run — surface it clearly
        # and let the caller decide what to do (e.g. skip and move on).
        print(f"[-] Firestore write failed for {source_url}: {e}")
        raise

    print(f"[DEBUG] Document written with ID: {doc_ref.id}")
    return doc_ref.id


def log_rejected(data: dict, scam_score: float):
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/rejected_log.csv"
    file_exists = os.path.isfile(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "source_url", "scam_score", "snippet"])
        writer.writerow([datetime.now(timezone.utc), data.get("source_url"), scam_score, data.get("raw_text", "")[:200]])