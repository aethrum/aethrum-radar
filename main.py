import os
import json
import re
import logging
from flask import Flask, request, jsonify
from bs4 import BeautifulSoup
import requests
from collections import Counter
from dotenv import load_dotenv
import openai

# Load environment variables
load_dotenv()

# Validate environment variables
required_vars = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
    "TELEGRAM_BOT_TOKEN": os.getenv("TELEGRAM_BOT_TOKEN"),
    "TELEGRAM_CHAT_ID": os.getenv("TELEGRAM_CHAT_ID")
}

missing_vars = [k for k, v in required_vars.items() if not v]
if missing_vars:
    logging.error(f"Faltan variables de entorno requeridas: {', '.join(missing_vars)}")
    raise EnvironmentError("Variables faltantes: " + ", ".join(missing_vars))

# Assign secrets
openai.api_key = required_vars["OPENAI_API_KEY"]
TELEGRAM_BOT_TOKEN = required_vars["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = required_vars["TELEGRAM_CHAT_ID"]

# Initialize Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Emotions dictionary (to be filled with valid keywords)
EMOTION_KEYWORDS = {
    "Dopamina": ["logro", "éxito", "recompensa", "motivación"],
    "Oxitocina": ["amor", "cariño", "confianza", "amistad"],
    "Serotonina": ["felicidad", "calma", "gratitud", "orgullo"],
    "Asombro": ["sorpresa", "maravilla", "descubrimiento", "fascinación"],
    "Adrenalina": ["emoción", "intensidad", "acción", "peligro"],
    "Feniletilamina": ["pasión", "romance", "enamoramiento", "atracción"],
    "Norepinefrina": ["energía", "alerta", "foco", "vitalidad"],
    "Anandamida": ["relajación", "paz", "equilibrio", "bienestar"],
    "Acetilcolina": ["concentración", "memoria", "aprendizaje", "atención"]
}

def clean_text(text):
    """Limpia el texto eliminando caracteres especiales y convirtiéndolo a minúsculas."""
    return re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', text).lower()

def extract_text_from_url(url):
    """Extrae texto del HTML de una URL."""
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except requests.exceptions.Timeout:
        logging.error(f"Timeout al intentar acceder a la URL: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error al realizar la solicitud: {e}")
        return None

def detect_emotion(text):
    """Detecta la emoción dominante en el texto."""
    word_list = clean_text(text).split()
    counts = {}
    for emotion, keywords in EMOTION_KEYWORDS.items():
        count = sum(word in keywords for word in word_list)
        counts[emotion] = count
    dominant = max(counts, key=counts.get)
    return dominant, counts

def generate_prompt(emotion, text):
    """Genera un prompt para OpenAI basado en la emoción detectada."""
    return (
        f"Basado en el siguiente texto:\n\n{text[:1000]}\n\n"
        f"Identificamos que la emoción química dominante es **{emotion}**.\n\n"
        "Crea un guion viral para un video de 17 segundos dividido en 5 bloques:\n"
        "1. Gancho emocional impactante\n"
        "2. Desarrollo rápido\n"
        "3. Momento de tensión o giro\n"
        "4. Resolución emocional\n"
        "5. Llamado a la acción fuerte\n\n"
        "Agrega un título emocional y sugiere un formato visual ideal para redes sociales. Sé muy creativo."
    )

def send_to_openai(prompt):
    """Envía un prompt a OpenAI y devuelve la respuesta."""
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
    """Envía un mensaje a Telegram."""
    try:
        telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        r = requests.post(telegram_url, json=payload)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.error(f"Telegram error: {e}")
        return False

@app.route("/webhook", methods=["POST"])
def webhook():
    """Procesa solicitudes entrantes al webhook."""
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
        return jsonify({"status": "error", "message": "Text too short for meaningful analysis"}), 400

    emotion, all_counts = detect_emotion(text)
    prompt = generate_prompt(emotion, text)
    script = send_to_openai(prompt)

    if not script:
        return jsonify({"status": "error", "message": "Failed to generate script"}), 500

    sent = send_to_telegram(f"*Emoción detectada:* {emotion}\n\n{script}")

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
