Markdown
# Mzansi Bursaries AI Agent 

An autonomous Artificial Intelligence pipeline designed to protect South African students from fraudulent educational funding schemes while eliminating manual data entry for administrators. 

This agent crawls target bursary websites, evaluates the legitimacy of the opportunities using a Supervised Machine Learning model, extracts key details using Generative AI, and automatically syncs the verified data to a Firebase Firestore database.

---

##  AI & Machine Learning Architecture

This project practically applies core Machine Learning concepts to solve a real-world problem:

* **Supervised Learning (Binary Classification):** The legitimacy engine (`classifier.py`) uses a trained Random Forest model. Supervised learning operates under guidance using labeled data[cite: 14]. Specifically, this is a binary classification task, which sorts data into one of two distinct categories (e.g., "Legit" vs. "Scam")[cite: 14].
* **Data Pre-processing:** The web scraper (`scraper.py`) cleans messy HTML tags into raw text before feeding it to the model. This addresses the "Garbage In, Garbage Out (GIGO)" principle, recognizing that poor-quality data leads to poor-quality predictions[cite: 15].
* **Scientific Computing Toolkit:** Built using industry-standard Python libraries for data analysis and model building, which makes Python the most popular programming language for machine learning[cite: 9].

---

##  System Components

1. **`scraper.py`**: A BeautifulSoup4 web spider that securely extracts readable text from target URLs.
2. **`classifier.py`**: Loads `scam_classifier.joblib` to calculate a Scam Probability Score.
    * *Score <= 0.30:* **Approved**
    * *Score 0.31 - 0.60:* **Flagged for Review**
    * *Score > 0.60:* **Rejected**
3. **`llm_extract.py`**: Uses the Google Gemini 3.6 Flash model to extract unstructured text into a strict JSON schema.
4. **`firestore_client.py`**: Connects to the live Firebase database, handling URL deduplication and system timestamps.
5. **`ai_pipeline.py`**: The main orchestration script that ties all modules together.

---

## Getting Started

### Prerequisites
* Python 3.11+
* A Google Gemini API Key
* A Firebase Service Account Private Key (`serviceAccountKey.json`)

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/MuziiIT/mzansi-ai-agent.git](https://github.com/MuziiIT/mzansi-ai-agent.git)
   cd mzansi-ai-agent
Create and activate a virtual environment:

Bash
# Windows
python -m venv venv
source venv/Scripts/activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
Install dependencies:

Bash
pip install -r requirements.txt
Configuration
Place your trained model (scam_classifier.joblib) into the root directory.

Place your Firebase credentials file (serviceAccountKey.json) into the root directory.

Create a .env file in the root directory and add your Gemini API key:

Plaintext
GEMINI_API_KEY=your_actual_api_key_here
(Note: Both .env and serviceAccountKey.json are strictly ignored by Git to prevent credential leakage).

 Usage
Testing (Dry-Run Mode)
It is highly recommended to test new target URLs before pushing data to the live database.

Open ai_pipeline.py.

Set DRY_RUN = True at the top of the file.

Run the pipeline:

Bash
python ai_pipeline.py
This will print the AI's verdict, the scam score, and the generated JSON directly to your terminal without altering Firebase.

Live Production
Once you verify the JSON output is correct:

Open ai_pipeline.py.

Set DRY_RUN = False.

Run the script to automatically publish the verified bursary to the student front-end.

Built for the BICT332  Group Project.


***

Now that your repository is documented, would you like to move on to updating your Flask web application to display the "AI Flagged Review" tab for the borderline bursaries?
