import joblib

model = joblib.load("scam_classifier.joblib")

def get_scam_probability(text: str) -> float:
    proba = model.predict_proba([text])[0]
    return round(float(proba[1]), 4)

def get_verdict(score: float) -> str:
    if score <= 0.30:
        return "approved"
    elif score <= 0.60:
        return "flagged"
    else:
        return "rejected"
