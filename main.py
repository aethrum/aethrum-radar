import os
import logging
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import Counter
import json

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Serotonina": "☀️",
    "Asombro": "🌟", "Adrenalina": "⚡", "Feniletilamina": "💘",
    "Norepinefrina": "🔥", "Anandamida": "🌈", "Acetilcolina": "📘"
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
        logging.error(f"Error extrayendo texto: {e}")
        return None

def cargar_keywords():
    keywords = {}
    base_path = "emociones"
    for archivo in os.listdir(base_path):
        if archivo.endswith(".json"):
            emocion = archivo.replace(".json", "")
            with open(os.path.join(base_path, archivo), "r") as f:
                keywords[emocion] = json.load(f)
    return keywords

def detect_emotion(text, keywords_dict):
    words = clean_text(text).split()
    scores = {emocion: sum(words.count(kw) for kw in keywords) for emocion, keywords in keywords_dict.items()}
    dominante = max(scores, key=scores.get)
    return dominante, scores

def generar_mensaje_emocional(emocion, scores, text, url=None):
    total = sum(scores.values()) or 1
    porcentajes = {k: round((v / total) * 100) for k, v in scores.items()}
    ordenadas = sorted([(e, p) for e, p in porcentajes.items()], key=lambda x: -x[1])
    emoji = EMOJI.get(emocion, "")
    relevancia = porcentajes[emocion]
    estado = "✅ Noticia Aprobada" if relevancia >= 25 and emocion in ["Dopamina", "Oxitocina", "Serotonina", "Asombro"] else "❌ Noticia Rechazada"
    otras = "\n".join([f"- {e}: {p}%" for e, p in ordenadas if e != emocion])
    fragmento = text.strip().replace("\n", " ")
    fragmento = fragmento[:300] + "..." if len(fragmento) > 300 else fragmento

    mensaje = (
        f"{estado} (Relevancia: {relevancia}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {emocion}\n"
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
        requests.post(url, json=payload).raise_for_status()
        logging.info("Mensaje enviado a Telegram.")
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
                return jsonify({"status": "ok", "message": "Sin datos"})
            with open("registros.csv", "r") as f:
                rows = list(csv.reader(f))
                total = len(rows)
                emociones = [row[1] for row in rows]
                conteo = Counter(emociones)
                top3 = conteo.most_common(3)
                resumen = f"<b>#Resumen Diario</b>\n\n"
                for emo, cant in top3:
                    porcentaje = round((cant / total) * 100, 2)
                    resumen += f"- {emo}: {porcentaje}%\n"
                send_to_telegram(resumen)
            return jsonify({"status": "ok", "message": "Resumen enviado"})

        if not texto.startswith("http") or "://" not in texto:
            return jsonify({"status": "ignored", "message": "No es una URL válida"})

        contenido = extract_text_from_url(texto)
        if not contenido:
            return jsonify({"status": "error", "message": "No se pudo extraer contenido"})

        keywords_dict = cargar_keywords()
        emocion, scores = detect_emotion(contenido, keywords_dict)
        hoy = datetime.utcnow().strftime("%Y-%m-%d")
        with open("registros.csv", "a", newline="") as f:
            csv.writer(f).writerow([hoy, emocion])

        mensaje = generar_mensaje_emocional(emocion, scores, contenido, url=texto)
        send_to_telegram(mensaje)
        return jsonify({"status": "ok", "message": "Mensaje procesado"})

    except Exception as e:
        logging.error(f"Error procesando webhook: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "message": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
