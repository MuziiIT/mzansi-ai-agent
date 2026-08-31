import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EXTRACTION_PROMPT = """You are a data extraction assistant for a South African bursary platform. 
Read the following scraped text and extract the details into a strict JSON object. 
Use EXACTLY these keys. Do not add any others.

{
  "name": "Full name of the bursary",
  "provider": "Company or organization offering it",
  "description": "A short 2-3 sentence summary of the opportunity",
  "field": "Target fields of study (e.g., STEM, Commerce, Arts)",
  "deadline": "Extract the closing date as a string, e.g., '31 August 2026'",
  "link": "The URL to apply"
}

If a specific piece of information is missing, return an empty string "" for that key.
Text to analyze:
"""

def extract_fields(raw_text: str) -> dict:
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=EXTRACTION_PROMPT + raw_text[:6000],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1
            )
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"LLM Extraction failed: {e}")
        return {}
