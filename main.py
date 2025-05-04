if not all([openai.api_key, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
    logging.error("Faltan variables de entorno requeridas.")
    raise EnvironmentError("Faltan variables de entorno requeridas.")
import os
import json
import re
import logging
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
import openai
from collections import Counter
from dotenv import load_dotenv
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN")  # Token para autenticar el webhook

if not openai.api_key or not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logging.error("Faltan variables de entorno requeridas.")
    exit(1)

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EMOTION_KEYWORDS = {
    "Dopamina": ["logro", "éxito", "recompensa", "motivación", "placer", "meta", "avance", "progreso", "superación", "triunfo",
                 "ambición", "reto", "desafío", "objetivo", "ganancia", "beneficio", "mejora", "crecimiento", "desarrollo", "innovación"],
    "Oxitocina": ["amor", "afecto", "cariño", "ternura", "empatía", "compasión", "solidaridad", "amistad", "confianza", "lealtad"]
}

def clean_text(text):
    return re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', text).lower()

def truncate_text(text, max_length=1000):
    return text[:max_length]

def extract_text_from_url(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except requests.exceptions.Timeout:
        logging.error(f"Timeout al intentar acceder a la URL: {url}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al realizar la solicitud: {e}")
    return None

def detect_emotion(text):
    word_list = clean_text(text).split()
    word_counter = Counter(word_list)
    counts = {emotion: sum(word_counter.get(word, 0) for word in keywords)
              for emotion, keywords in EMOTION_KEYWORDS.items()}
    dominant = max(counts, key=counts.get)
    return dominant, counts

def generate_prompt(emotion, text):
    text = truncate_text(text)
    return (
        f"Texto base:\n\n{text}\n\n"
        f"Emoción dominante detectada: {emotion.upper()}.\n\n"
        "Genera un guion viral para un video de 17 segundos dividido en 5 bloques:\n"
        "1. Gancho emocional\n"
        "2. Desarrollo veloz\n"
        "3. Punto de giro\n"
        "4. Cierre emocional\n"
        "5. Llamado a la acción impactante\n\n"
        "Agrega un TÍTULO emocional y sugiere FORMATO visual para redes sociales. Sé creativo."
    )

def send_to_openai(prompt):
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en creación de contenido viral emocional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8,
            max_tokens=600
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        return None

def send_to_telegram(message):
    try:
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        r = requests.post(telegram_url, json=payload)
        r.raise_for_status()
        return True
    except Exception as e:
        logging.error(f"Telegram error: {e}")
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    # Autenticación básica del webhook
    token = request.headers.get("Authorization")
    if token != f"Bearer {WEBHOOK_TOKEN}":
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    if not request.is_json:
        return jsonify({"status": "error", "message": "Invalid JSON"}), 400

    data = request.get_json()
    text = ""

    if "texto" in data:
        text = data["texto"]
    elif "url" in data:
        text = extract_text_from_url(data["url"])
        if not text:
            return jsonify({"status": "error", "message": "Failed to extract content from URL"}), 400
    else:
        return jsonify({"status": "error", "message": "Missing 'texto' or 'url'"}), 400

    if len(text.strip()) < 30:
        return jsonify({"status": "error", "message": "Text too short"}), 400

    emotion, all_counts = detect_emotion(text)
    prompt = generate_prompt(emotion, text)
    script = send_to_openai(prompt)

    if not script or len(script) < 20:
        return jsonify({"status": "error", "message": "Script too short"}), 500

    sent = send_to_telegram(f"<b>Emoción detectada:</b> {emotion.upper()}\n\n{script}")

    return jsonify({
        "status": "ok",
        "emotion": emotion,
        "counts": all_counts,
        "message_sent": sent,
        "script": script
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
