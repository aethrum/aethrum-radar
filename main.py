import os
import logging
import json
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
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en las variables de entorno")

EMOTION_DIR = "emociones"

def cargar_keywords():
    emociones = {}
    for archivo in os.listdir(EMOTION_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "")
            with open(os.path.join(EMOTION_DIR, archivo), "r") as f:
                emociones[nombre] = json.load(f)
    return emociones

def clean_text(text):
    return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text)

def extract_text_from_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=' ')
    except Exception as e:
        logging.error(f"Error extrayendo texto desde URL: {e}")
        return None

def detect_emotion(text, keywords_dict):
    words = clean_text(text).split()
    scores = {
        emotion: sum(words.count(kw) for kw in kws)
        for emotion, kws in keywords_dict.items()
    }
    dominante = max(scores, key=scores.get)
    return dominante, scores

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Asombro": "🌟",
    "Adrenalina": "⚡️", "Norepinefrina": "🔥", "Anandamida": "🧘"
}

def generar_mensaje_emocional(dominante, scores, text, url):
    total = sum(scores.values()) or 1
    porcentajes = {k: round((v / total) * 100, 2) for k, v in scores.items()}
    ordenadas = sorted(porcentajes.items(), key=lambda x: x[1], reverse=True)
    emoji = EMOJI.get(dominante, "")
    relevancia = porcentajes[dominante]
    estado = "✅ Noticia Aprobada" if relevancia > 25 else "❌ Noticia Irrelevante"
    otras = "\n".join(f"- {e}: {p}%" for e, p in ordenadas if e != dominante)
    fragmento = text.strip().replace("\n", " ")[:600]
    mensaje = (
        f"{estado} (Relevancia: {relevancia}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {dominante}\n"
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
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Mensaje enviado a Telegram")
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    try:
        data = request.get_json()
        logging.warning(f"Mensaje recibido: {data}")

        texto = data.get("message") or data.get("text", "")
        if isinstance(texto, dict):
            texto = texto.get("text", "")
        texto = str(texto or "").strip()

        if texto == "/resumen":
            if not os.path.exists("registros.csv"):
                send_to_telegram("⚠️ Aún no hay datos para mostrar un resumen.")
                return jsonify({"status": "ok"})

            with open("registros.csv", "r") as f:
                rows = list(csv.reader(f))
            total = len(rows)
            emociones = [row[1] for row in rows if len(row) > 1]
            conteo = Counter(emociones)
            top3 = conteo.most_common(3)

            resumen = f"<b>#Resumen Diario de Emociones ({total} noticias)</b>\n"
            for emo, cant in top3:
                porcentaje = round((cant / total) * 100, 2)
                resumen += f"- {emo}: {porcentaje}%\n"

            send_to_telegram(resumen)
            return jsonify({"status": "ok"})

        if "http" not in texto:
            return jsonify({"status": "ignored"})

        partes = texto.split(" - ")
        url = partes[-1].strip() if "http" in partes[-1] else ""
        contenido = extract_text_from_url(url)
        if not contenido:
            return jsonify({"status": "error", "msg": "no content"})

        keywords_dict = cargar_keywords()
        emocion, scores = detect_emotion(contenido, keywords_dict)
        hoy = datetime.utcnow().strftime("%Y-%m-%d")
        with open("registros.csv", "a", newline="") as f:
            csv.writer(f).writerow([hoy, emocion])

        mensaje = generar_mensaje_emocional(emocion, scores, contenido, url)
        send_to_telegram(mensaje)
        return jsonify({"status": "ok", "message": mensaje})

    except Exception as e:
        logging.error(f"Error procesando webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "msg": "ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
