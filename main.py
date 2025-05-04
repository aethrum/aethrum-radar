import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")

EMOTION_KEYWORDS = {
    "Dopamina": ["success", "goal", "motivation", "reward", "pleasure"],
    "Oxitocina": ["love", "trust", "family", "support", "bond"],
    "Serotonina": ["peace", "gratitude", "calm", "balance", "clarity"],
    "Asombro": ["amazing", "epic", "wonder", "mystery", "legendary"],
    "Adrenalina": ["danger", "thrill", "shock", "emergency", "intensity"],
    "Feniletilamina": ["romance", "passion", "chemistry", "kiss", "attraction"],
    "Norepinefrina": ["energy", "drive", "focus", "power", "momentum"],
    "Anandamida": ["bliss", "joy", "relaxation", "serenity", "calmness"],
    "Acetilcolina": ["learning", "clarity", "memory", "focus", "strategy"]
}

def clean_text(text):
    return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text)

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logging.error(f"Error extracting from URL: {e}")
        return None

def detect_emotion(text):
    words = clean_text(text).split()
    scores = {emotion: sum(words.count(kw) for kw in kws) for emotion, kws in EMOTION_KEYWORDS.items()}
    dominant = max(scores, key=scores.get)
    return dominant, scores

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Message sent to Telegram.")
    except Exception as e:
        logging.error(f"Telegram error: {e}")

@app.route("/", methods=["POST"])
def root_webhook():
    data = request.get_json()
    message = data.get("message")

    if not message:
        return jsonify({"status": "error", "message": "Missing 'message' field"}), 400

    text = message if not message.startswith("http") else extract_text_from_url(message)
    if not text or len(text.strip()) < 30:
        return jsonify({"status": "error", "message": "Text too short or failed to extract"}), 400

    emotion, scores = detect_emotion(text)
    final_msg = f"<b>Emotion Detected:</b> {emotion}\n\n{text[:300]}..."
    send_to_telegram(final_msg)

    return jsonify({"status": "ok", "emotion": emotion, "scores": scores})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
