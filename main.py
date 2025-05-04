import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
import openai

# Logging configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Flask app initialization
app = Flask(__name__)

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Validate required environment variables
required_vars = {"TELEGRAM_TOKEN": TELEGRAM_TOKEN, "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID, "OPENAI_API_KEY": OPENAI_API_KEY}
missing_vars = [k for k, v in required_vars.items() if not v]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Emotion keywords dictionary
EMOTION_KEYWORDS = {
    "Dopamina": ["achievement", "success", "reward", "motivation", "pleasure", "goal", "discovery", "progress", "curiosity", "inspiration"],
    "Oxitocina": ["love", "affection", "trust", "bond", "connection", "family", "friendship", "support", "compassion", "kindness"],
    "Serotonina": ["peace", "balance", "gratitude", "calm", "well-being", "stability", "harmony", "order", "clarity", "serenity"],
    "Asombro": ["amazing", "wonder", "epic", "unbelievable", "gigantic", "legendary", "magnificent", "mysterious", "discovery", "phenomenal"],
    "Adrenalina": ["danger", "thrill", "intensity", "action", "explosive", "alert", "emergency", "crisis", "shock", "rescue"],
    "Feniletilamina": ["passion", "romance", "love", "chemistry", "attraction", "desire", "infatuation", "flirt", "kiss", "crush"],
    "Norepinefrina": ["focus", "alertness", "energy", "vitality", "determination", "strength", "drive", "efficiency", "power", "momentum"],
    "Anandamida": ["calmness", "relaxation", "peace", "joy", "bliss", "balance", "harmony", "serenity", "contentment", "tranquility"],
    "Acetilcolina": ["learning", "memory", "focus", "attention", "clarity", "strategy", "creativity", "problem-solving", "analysis", "logic"]
}

def clean_text(text):
    """Clean text by removing special characters and converting to lowercase."""
    return ''.join([char if char.isalnum() or char.isspace() else '' for char in text]).lower()

def extract_text_from_url(url):
    """Scrape text content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logging.error(f"Error extracting text from URL: {e}")
        return None

def detect_emotion(text):
    """Detect the dominant emotion based on keyword frequency."""
    word_list = clean_text(text).split()
    counts = {emotion: sum(word_list.count(keyword) for keyword in keywords) for emotion, keywords in EMOTION_KEYWORDS.items()}
    dominant_emotion = max(counts, key=counts.get)
    return dominant_emotion, counts

def generate_prompt(emotion, text):
    """Generate a structured prompt for OpenAI."""
    return (
        f"Based on the following text:\n\n{text[:1000]}\n\n"
        f"The dominant chemical emotion detected is {emotion}.\n\n"
        "Generate a viral 17-second TikTok script divided into 5 blocks:\n"
        "1. Emotional hook\n"
        "2. Fast-paced development\n"
        "3. Plot twist\n"
        "4. Emotional resolution\n"
        "5. Strong call-to-action\n\n"
        "Include an emotional title and suggest an ideal visual format for social media."
    )

def send_to_openai(prompt):
    """Send a prompt to OpenAI and retrieve the response."""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"Error communicating with OpenAI: {e}")
        return None

def send_to_telegram(message):
    """Send a message to a Telegram chat."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Message sent to Telegram successfully.")
    except Exception as e:
        logging.error(f"Error sending message to Telegram: {e}")

@app.route("/webhook", methods=["POST"])
def webhook():
    """Handle POST requests to the /webhook endpoint."""
    data = request.get_json()
    if not data or ("texto" not in data and "url" not in data):
        return jsonify({"status": "error", "message": "Invalid JSON payload"}), 400

    text = data.get("texto") or extract_text_from_url(data.get("url"))
    if not text or len(text.strip()) < 30:
        return jsonify({"status": "error", "message": "Text too short for analysis"}), 400

    emotion, counts = detect_emotion(text)
    prompt = generate_prompt(emotion, text)
    script = send_to_openai(prompt)

    if not script:
        return jsonify({"status": "error", "message": "Failed to generate script"}), 500

    send_to_telegram(f"<b>Dominant Emotion:</b> {emotion}\n\n{script}")

    return jsonify({"status": "ok", "emotion": emotion, "counts": counts, "script": script})

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

@app.route("/", methods=["GET"])
def root():
    return jsonify({"status": "ok", "message": "AETHRUM is live"}), 200
