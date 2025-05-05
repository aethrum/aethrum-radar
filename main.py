import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import Counter

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Missing TELEGRAM_TOKEN or TELEGRAM_CHAT_ID env variables")

EMOTION_KEYWORDS = {
    "Dopamina": ["success", "goal", "motivation", "reward"],
    "Oxitocina": ["love", "trust", "family", "safe"],
    "Serotonina": ["peace", "gratitude", "calm"],
    "Asombro": ["amazing", "epic", "wonder"],
    "Adrenalina": ["danger", "thrill", "shock"],
    "Feniletilamina": ["romance", "passion", "crush"],
    "Norepinefrina": ["energy", "drive", "focus"],
    "Anandamida": ["bliss", "joy", "relaxation"],
    "Acetilcolina": ["learning", "clarity", "memory"],
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
        "Dopamina": "✨", "Oxitocina": "❤️", "Serotonina": "☀️",
        "Asombro": "🌟", "Adrenalina": "⚡", "Feniletilamina": "💘",
        "Norepinefrina": "🔥", "Anandamida": "🌈", "Acetilcolina": "📘"
    }

    emoji = EMOJI.get(emotion, "")
    relevancia = porcentajes[emotion]
    estado = "✅ Noticia Aprobada" if relevancia >= 25 and emotion in ["Dopamina", "Oxitocina", "Serotonina", "Asombro"] else "❌ Noticia Rechazada"
    otras = "\n".join([f"- {e}: {p}%" for e, p in ordenadas if e != emotion])

    fragmento = text.strip().replace("\n", " ")[:300]
    mensaje = (
        f"{estado} (Relevancia: {relevancia}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {emotion}\n"
        f"<b>Relevancia emocional:</b> {relevancia}%\n"
        f"<b>Otras emociones detectadas:</b>\n{otras}\n"
        f"<b>Fragmento:</b>\n{fragmento}..."
    )
    if url:
        mensaje += f"\n\n{url}"
    return mensaje

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
        logging.info("Mensaje enviado a Telegram.")
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    data = request.get_json()
    logging.warning(f"Mensaje recibido: {data}")

    # Detectar texto desde mensajes de canal
    texto = None
    if "message" in data:
        texto = data["message"].get("text", "").strip()
    elif "channel_post" in data:
        texto = data["channel_post"].get("text", "").strip()

    if not texto:
        return jsonify({"status": "ignored", "message": "Sin texto en el mensaje"})

    texto = texto.lower()

    if texto == "/resumen":
        try:
            with open("registros.csv", "r") as f:
                rows = [row for row in csv.reader(f)]
            total = len(rows)
            emociones = [row[1] for row in rows if len(row) > 1]
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
            return jsonify({"status": "error", "message": str(e)})

    if not texto.startswith("http"):
        return jsonify({"status": "ignored", "message": "No es un enlace"})

    if len(texto) < 30:
        return jsonify({"status": "ignored", "message": "Enlace muy corto"})

    texto_extraido = extract_text_from_url(texto)
    if not texto_extraido:
        return jsonify({"status": "error", "message": "No se pudo extraer texto"})

    emotion, scores = detect_emotion(texto_extraido)
    today = datetime.utcnow().strftime("%Y-%m-%d")

    try:
        with open("registros.csv", "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([today, emotion])
    except Exception as e:
        logging.error(f"Error escribiendo CSV: {e}")

    final_msg = generar_mensaje_emocional(emotion, scores, texto_extraido, url=texto)
    send_to_telegram(final_msg)
    return jsonify({"status": "ok", "emotion": emotion, "scores": scores})

@app.errorhandler(404)
def not_found(e):
    return jsonify({"status": "error", "message": "Ruta no existe"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
