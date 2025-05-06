import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import Counter

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Serotonina": "☀️",
    "Asombro": "🌟", "Adrenalina": "⚡", "Feniletilamina": "💘",
    "Norepinefrina": "🔥", "Anandamida": "🌈", "Acetilcolina": "📘"
}

def load_emotion_keywords():
    emotion_keywords = {}
    carpeta = "emociones"
    for archivo in os.listdir(carpeta):
        if archivo.endswith(".txt"):
            emocion = archivo.replace(".txt", "")
            with open(os.path.join(carpeta, archivo), "r", encoding="utf-8") as f:
                palabras = [line.strip().lower() for line in f if line.strip()]
                emotion_keywords[emocion] = palabras
    return emotion_keywords

EMOTION_KEYWORDS = load_emotion_keywords()

def clean_text(text):
    return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text)

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        logging.error(f"Error extrayendo texto: {e}")
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
    emoji = EMOJI.get(emotion, "")
    relevancia = porcentajes[emotion]
    estado = "✅ Noticia Aprobada" if relevancia >= 25 and emotion in ["Dopamina", "Oxitocina", "Serotonina", "Asombro"] else "❌ Noticia Rechazada"
    otras = "\n".join([f"- {e}: {p}%" for e, p in ordenadas if e != emotion])
    fragmento = text.strip().replace("\n", " ")
    fragmento = fragmento[:300] + "..." if len(fragmento) > 300 else fragmento

    mensaje = (
        f"{estado} (Relevancia: {relevancia}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {emotion}\n"
        f"<b>Relevancia emocional:</b> {relevancia}%\n"
        f"<b>Otras emociones detectadas:</b>\n{otras}\n"
        f"<b>Fragmento:</b>\n{fragmento}"
    )
    if url:
        mensaje += f"\n\n{url}"
    return mensaje

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload).raise_for_status()
        logging.info("Mensaje enviado a Telegram.")
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    try:
        data = request.get_json()
        logging.info(f"Payload recibido: {data}")

        texto = ""
        if isinstance(data.get("message"), dict):
            texto = data["message"].get("text", "")
        elif isinstance(data.get("channel_post"), dict):
            texto = data["channel_post"].get("text", "")
        elif isinstance(data.get("message"), str):
            texto = data["message"]
        elif isinstance(data.get("channel_post"), str):
            texto = data["channel_post"]

        texto = texto.strip().lower()

        if texto == "/resumen":
            if not os.path.exists("registros.csv"):
                send_to_telegram("⚠️ Aún no hay datos para mostrar un resumen.")
                return jsonify({"status": "error", "message": "CSV no existe"})

            with open("registros.csv", "r") as f:
                rows = list(csv.reader(f))
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

        if not texto.startswith("http") or len(texto) < 30:
            return jsonify({"status": "ignored", "message": "No hay URL válida"})

        contenido = extract_text_from_url(texto)
        if not contenido:
            return jsonify({"status": "error", "message": "No se pudo extraer texto"})

        emotion, scores = detect_emotion(contenido)
        hoy = datetime.utcnow().strftime("%Y-%m-%d")

        with open("registros.csv", "a", newline="") as f:
            csv.writer(f).writerow([hoy, emotion])

        mensaje_final = generar_mensaje_emocional(emotion, scores, contenido, url=texto)
        send_to_telegram(mensaje_final)
        return jsonify({"status": "ok", "emotion": emotion, "scores": scores})
    except Exception as e:
        logging.error(f"Error en webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "message": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
