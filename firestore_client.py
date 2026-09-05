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

# AI-created bursaries are staged here for admin review — NOT the same
# collection the public site reads from. Nothing lands on the live site
# until an admin approves it and it gets copied into BURSARIES_COLLECTION.
AI_BURSARIES_COLLECTION = "ai_bursaries"
BURSARIES_COLLECTION = "bursaries"


def bursary_exists(source_url: str) -> bool:
    """Checks both collections — a URL already sitting in ai_bursaries
    (awaiting review) or already promoted into the live bursaries
    collection should both count as 'already have this one'."""
    for collection in (AI_BURSARIES_COLLECTION, BURSARIES_COLLECTION):
        docs = (
            db.collection(collection)
            .where(filter=FieldFilter("source_url", "==", source_url))
            .limit(1)
            .stream()
        )
        if len(list(docs)) > 0:
            return True
    return False


def push_bursary(data: dict, status: str, scam_score: float, source_url: str):
    # Internal verdict stays "approved"/"flagged" everywhere in code and
    # logs. Only the stored Firestore value is remapped: "approved" -> "legit".
    STATUS_DB_VALUES = {"approved": "legit", "flagged": "flagged"}
    db_status = STATUS_DB_VALUES.get(status, status)

    deadline_text = data.pop("deadline", "")
    doc = {
        **data,
        "deadline": deadline_to_timestamp(deadline_text),
        "deadline_text": deadline_text,
        "source_url": source_url,
        "status": db_status,
        "scam_score": scam_score,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }

    try:
        update_time, doc_ref = db.collection(AI_BURSARIES_COLLECTION).add(doc)
    except Exception as e:
        print(f"[-] Firestore write failed for {source_url}: {e}")
        raise

    print(f"[DEBUG] Document written to '{AI_BURSARIES_COLLECTION}' with ID: {doc_ref.id}")
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