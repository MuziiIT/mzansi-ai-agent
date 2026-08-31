import csv, os
from datetime import datetime, timezone
import firebase_admin
from firebase_admin import credentials, firestore

if not firebase_admin._apps:
    cred = credentials.Certificate("serviceAccountKey.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

def bursary_exists(source_url: str) -> bool:
    docs = db.collection("bursaries").where("source_url", "==", source_url).limit(1).stream()
    return len(list(docs)) > 0

def push_bursary(data: dict, status: str, scam_score: float, source_url: str):
    doc = {
        **data,
        "source_url": source_url,
        "status": status,
        "scam_score": scam_score,
        "createdAt": firestore.SERVER_TIMESTAMP,
    }
    db.collection("bursaries").add(doc)

def log_rejected(data: dict, scam_score: float):
    os.makedirs("logs", exist_ok=True)
    log_path = "logs/rejected_log.csv"
    file_exists = os.path.isfile(log_path)
    with open(log_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "source_url", "scam_score", "snippet"])
        writer.writerow([datetime.now(timezone.utc), data.get("source_url"), scam_score, data.get("raw_text", "")[:200]])
