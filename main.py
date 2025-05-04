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

# Load environment variables
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Flask app init
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Emotion keywords (DEFINITIVO)
EMOTION_KEYWORDS = {
    "Dopamina": ["logro", "éxito", "recompensa", "motivación", "placer", "meta", "avance", "progreso", "superación", "triunfo",
                 "ambición", "reto", "desafío", "objetivo", "ganancia", "beneficio", "mejora", "crecimiento", "desarrollo", "innovación",
                 "descubrimiento", "curiosidad", "aprendizaje", "exploración", "novedad", "sorpresa", "expectativa", "anticipación", "esperanza", "inspiración",
                 "pasión", "entusiasmo", "energía", "vitalidad", "dinamismo", "actividad", "productividad", "eficiencia", "rendimiento", "logística",
                 "planificación", "organización", "estrategia", "táctica", "habilidad", "destreza", "competencia", "maestría", "excelencia", "cambio"],
    "Oxitocina": ["amor", "afecto", "cariño", "ternura", "empatía", "compasión", "solidaridad", "amistad", "confianza", "lealtad",
                  "vínculo", "conexión", "relación", "intimidad", "proximidad", "abrazo", "caricia", "beso", "apoyo", "comprensión",
                  "escucha", "diálogo", "comunicación", "cooperación", "colaboración", "unidad", "familia", "hogar", "madre", "padre",
                  "hijo", "hermano", "pareja", "matrimonio", "compañía", "presencia", "seguridad", "protección", "cuidado", "altruismo",
                  "generosidad", "bondad", "amabilidad", "dulzura", "sensibilidad", "respeto", "tolerancia", "aceptación", "perdón", "reconciliación"],
    # Puedes agregar aquí las otras emociones si lo necesitas hoy
}

# Utilidades
def clean_text(text):
    return re.sub(r'[^a-zA-ZÀ-ÿ\s]', '', text).lower()

def extract_text_from_url(url):
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logging.error(f"Error scraping URL: {e}")
        return None

def detect_emotion(text):
    word_list = clean_text(text).split()
    word_counter = Counter(word_list)
    counts = {emotion: sum(word_counter.get(word, 0) for word in keywords)
              for emotion, keywords in EMOTION_KEYWORDS.items()}
    dominant = max(counts, key=counts.get)
    return dominant, counts

def generate_prompt(emotion, text):
    return (
        f"Texto base:\n\n{text[:1000]}\n\n"
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

# Webhook
@app.route("/webhook", methods=["POST"])
def webhook():
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

# Render compatibility
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
