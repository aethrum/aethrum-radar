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
EMOTION_DIR = "emociones"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

def cargar_keywords():
    emociones = {}
    for archivo in os.listdir(EMOTION_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "")
            with open(os.path.join(EMOTION_DIR, archivo), "r", encoding="utf-8") as f:
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
        logging.error(f"Error extrayendo texto de URL: {e}")
        return None

def detect_emotion(text, keywords_dict):
    words = clean_text(text).split()
    scores = {emotion: sum(words.count(kw) for kw in kws) for emotion, kws in keywords_dict.items()}
    dominante = max(scores, key=scores.get, default=None)
    return dominante, scores

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Asombro": "🌟",
    "Adrenalina": "⚡", "Norepinefrina": "🔥", "Anandamida": "🌀"
}

def generar_mensaje_emocional(dominante, scores, text, url=None):
    total = sum(scores.values()) or 1
    porcentajes = {k: round((v / total) * 100, 2) for k, v in scores.items()}
    ordenadas = sorted(porcentajes.items(), key=lambda x: x[1], reverse=True)
    emoji = EMOJI.get(dominante, "")
    relevancia = porcentajes.get(dominante, 0)
    estado = "✅ Noticia Aprobada" if relevancia > 15 else "⚠️ Noticia con baja relevancia"
    otras = "\n".join([f"- {e}: {p}%" for e, p in ordenadas if e != dominante])
    fragmento = text.strip().replace("\n", " ")[:300]
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
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("Mensaje enviado a Telegram")
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    try:
        raw_data = request.get_data(as_text=True)
        logging.warning(f"Raw recibido: {raw_data}")
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            data = {"message": raw_data.strip()}

        msg = data.get("message", "")
        if isinstance(msg, dict):
            texto = msg.get("text", "")
        else:
            texto = str(msg)

        texto = texto.strip().replace("\n", " ")
        if not texto:
            logging.warning("Mensaje vacío o sin texto")
            return jsonify({"status": "ignorado"})

        if texto.lower() == "/resumen":
            if not os.path.exists("registros.csv"):
                send_to_telegram("⚠️ Aún no hay datos para mostrar un resumen.")
                return jsonify({"status": "ok"})
            with open("registros.csv", "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
            total = len(rows)
            emociones = [row[1] for row in rows if len(row) > 1]
            conteo = Counter(emociones)
            top3 = conteo.most_common(3)
            resumen = "<b>#Resumen Diario</b>\n\n"
            for emo, cant in top3:
                porcentaje = round((cant / total) * 100, 2)
                resumen += f"- {emo}: {porcentaje}%\n"
            send_to_telegram(resumen)
            return jsonify({"status": "ok"})

        # Extrae URL si está dentro del texto
        palabras = texto.split()
        urls = [p for p in palabras if p.startswith("http")]
        if not urls:
            logging.warning(f"Texto ignorado por no contener URL válida: {texto}")
            return jsonify({"status": "ignorado"})
        url = urls[0]

        contenido = extract_text_from_url(url)
        if not contenido:
            return jsonify({"status": "error", "msg": "No se pudo extraer el texto"})

        keywords_dict = cargar_keywords()
        emocion, scores = detect_emotion(contenido, keywords_dict)
        hoy = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open("registros.csv", "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([hoy, emocion])

        mensaje = generar_mensaje_emocional(emocion, scores, contenido, url)
        send_to_telegram(mensaje)
        return jsonify({"status": "ok", "emocion": emocion})

    except Exception as e:
        logging.error(f"Error procesando el webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "msg": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render injecta dinámicamente el puerto
    app.run(host="0.0.0.0", port=port)
