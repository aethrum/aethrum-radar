import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import Counter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID")

EMOTION_KEYWORDS = {
    "Dopamina": ["success", "goal", "motivation"],
    "Oxitocina": ["love", "trust", "family"],
    "Serotonina": ["peace", "gratitude", "calm"],
    "Asombro": ["amazing", "epic", "wonder"],
    "Adrenalina": ["danger", "thrill", "shock"],
    "Feniletilamina": ["romance", "passion", "crush"],
    "Norepinefrina": ["energy", "drive", "focus"],
    "Anandamida": ["bliss", "joy", "relaxation"],
    "Acetilcolina": ["learning", "clarity", "memory"]
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
    scores = {emotion: sum(words.count(kw) for kw in keywords) for emotion, keywords in EMOTION_KEYWORDS.items()}
    dominant = max(scores, key=scores.get)
    return dominant, scores

def generar_mensaje_emocional(emotion, scores, text, url=None):
    total = sum(scores.values()) or 1
    porcentajes = {k: round((v / total) * 100) for k, v in scores.items()}
    ordenadas = sorted([(e, p) for e, p in porcentajes.items()], key=lambda x: -x[1])

    EMOJI = {
        "Dopamina": "✨", "Oxitocina": "❤️", "Serotonina": "☮️",
        "Asombro": "🌟", "Adrenalina": "⚡", "Feniletilamina": "💕",
        "Norepinefrina": "🔥", "Anandamida": "🌈", "Acetilcolina": "🧠"
    }

    emoji = EMOJI.get(emotion, "")
    relevancia = porcentajes[emotion]
    estado = "✅ Noticia Aprobada" if relevancia >= 20 and emotion in ["Dopamina", "Oxitocina", "Serotonina"] else "❌ Noticia Rechazada"
    otras = "\n".join([f"- {e}: {p}%" for e, p in ordenadas if e != emotion])
    fragmento = text.strip().replace("\n", " ")
    if len(fragmento) > 300:
        fragmento = fragmento[:300] + "..."

    mensaje = (
        f"{estado} (Relevancia: {relevancia}%)\n\n"
        f"<b>Emoción dominante:</b> {emoji} {emotion}\n"
        f"<b>Relevancia emocional:</b> {relevancia}%\n"
        f"<b>Otras emociones detectadas:</b>\n{otras}\n\n"
        f"<b>Fragmento:</b>\n{fragmento}"
    )
    if url:
        mensaje += f"\n\n🔗 {url}"
    return mensaje

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
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
    logging.info(f"Mensaje recibido: {message}")

    if message and message.strip().lower().startswith("/resumen"):
        logging.info("Entrando al bloque /resumen")
        try:
            today = datetime.utcnow().strftime("%Y-%m-%d")
            with open("registros.csv", "r") as f:
                rows = [row for row in csv.reader(f) if row and row[0] == today]
            if not rows:
                send_to_telegram("Aún no hay registros hoy para generar un resumen.")
                return jsonify({"status": "ok", "resumen": "vacío"})

            total = len(rows)
            emociones = [row[1] for row in rows]
            conteo = Counter(emociones)
            top3 = conteo.most_common(3)

            resumen = f"<b>#Resumen Diario</b>\nTotal noticias: {total}\n"
            for emo, cant in top3:
                porcentaje = round((cant / total) * 100)
                resumen += f"- {emo}: {cant} ({porcentaje}%)\n"

            send_to_telegram(resumen)
            return jsonify({"status": "ok", "resumen": resumen})
        except Exception as e:
            logging.error(f"Error generando resumen: {e}")
            send_to_telegram("Error generando el resumen.")
            return jsonify({"status": "error", "message": str(e)})

    if not message:
        return jsonify({"status": "error", "message": "No message"})

    text = message if not message.startswith("http") else extract_text_from_url(message)
    if not text or len(text.strip()) < 30:
        return jsonify({"status": "error", "message": "Texto vacío o muy corto"})

    emotion, scores = detect_emotion(text)
    today = datetime.utcnow().strftime("%Y-%m-%d")
    try:
        with open("registros.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([today, emotion])
    except Exception as e:
        logging.error(f"Error guardando CSV: {e}")

    final_msg = generar_mensaje_emocional(emotion, scores, text, url=message if message.startswith("http") else None)
    send_to_telegram(final_msg)
    return jsonify({"status": "ok", "emotion": emotion, "scores": scores})

@app.errorhandler(404)
def route_not_found(e):
    path = request.path
    ua = request.headers.get("User-Agent", "no-agent")
    ip = request.remote_addr or "no-ip"
    if "7124925219" in path:
        logging.warning(f"403 BLOCKED: path={path} | UA={ua} | IP={ip}")
        return jsonify({"status": "forbidden", "message": "Access Denied"}), 403
    logging.warning(f"404 on path: {path} | UA={ua} | IP={ip}")
    return jsonify({"status": "error", "message": "Ruta no encontrada"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
