import os
import logging
import json
import time
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import defaultdict, Counter
from urllib.parse import urlparse
from retrying import retry

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "securetoken")
UMBRAL_APROBACION = int(os.getenv("UMBRAL_APROBACION", 65))
EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

EMOTION_KEYWORDS = {}
CATEGORY_KEYWORDS = {}

def inicializar_keywords():
    global EMOTION_KEYWORDS, CATEGORY_KEYWORDS
    for archivo in os.listdir(EMOTION_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "")
            with open(os.path.join(EMOTION_DIR, archivo), "r", encoding="utf-8") as f:
                EMOTION_KEYWORDS[nombre] = json.load(f)
    for archivo in os.listdir(CATEGORY_DIR):
        if archivo.endswith(".json"):
            with open(os.path.join(CATEGORY_DIR, archivo), "r", encoding="utf-8") as f:
                data = json.load(f)
                CATEGORY_KEYWORDS.update(data)

def clean_text(text):
    return ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text)

def is_valid_url(url):
    try:
        result = urlparse(url)
        return result.scheme in ("http", "https") and result.netloc != ""
    except:
        return False

def extract_text_from_url(url):
    try:
        time.sleep(2)
        headers = { "User-Agent": "Mozilla/5.0" }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=' ')
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logging.error("Error 429: Too Many Requests")
        else:
            logging.error(f"HTTPError: {e}")
    except Exception as e:
        logging.error(f"Error extrayendo texto de URL: {e}")
    return None

def detect_emotion(text):
    words = clean_text(text).split()
    scores = defaultdict(int)
    for emotion, palabras in EMOTION_KEYWORDS.items():
        for palabra, peso in palabras.items():
            scores[emotion] += words.count(palabra.lower()) * peso
    dominante = max(scores, key=scores.get, default=None)
    return dominante, scores

def detectar_categoria(texto):
    texto_limpio = clean_text(texto).lower()
    palabras_texto = texto_limpio.split()
    texto_completo = " " + " ".join(palabras_texto) + " "
    puntajes = defaultdict(int)
    for categoria, contenido in CATEGORY_KEYWORDS.items():
        keywords = contenido.get("keywords", {})
        for palabra, peso in keywords.items():
            palabra_limpia = palabra.lower().strip()
            if " " in palabra_limpia:
                if f" {palabra_limpia} " in texto_completo:
                    puntajes[categoria] += peso
            else:
                puntajes[categoria] += palabras_texto.count(palabra_limpia) * peso
    categoria_dominante = max(puntajes, key=puntajes.get, default="indefinido")
    return categoria_dominante, dict(puntajes)

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Asombro": "🌟",
    "Adrenalina": "⚡", "Norepinefrina": "🔥", "Anandamida": "🌀",
    "Serotonina": "🧘", "Acetilcolina": "🧠", "Fetileminalina": "💘"
}

def calcular_nuevo_puntaje(dominante, scores, categoria):
    total = sum(scores.values()) or 1
    dominante_valor = scores.get(dominante, 0)
    porcentaje_dominante = round((dominante_valor / total) * 100, 2)
    emociones_relevantes = [v for v in scores.values() if (v / total) * 100 > 5]
    diversidad = min(len(emociones_relevantes), 5) / 5
    bonus_categoria = 1 if categoria != "indefinido" else 0
    puntaje_final = round((porcentaje_dominante * 0.5) + (diversidad * 20) + (bonus_categoria * 30), 2)
    return puntaje_final, porcentaje_dominante

def generar_mensaje_emocional(dominante, scores, text, url=None, categoria=None):
    puntaje, porcentaje_dominante = calcular_nuevo_puntaje(dominante, scores, categoria)
    ordenadas = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    total = sum(scores.values()) or 1
    porcentajes = [(k, round((v / total) * 100, 2)) for k, v in ordenadas if v > 0]
    otras = "\n".join([f"- {e}: {p}%" for e, p in porcentajes if e != dominante])
    emoji = EMOJI.get(dominante, "")
    estado = "✅ Noticia Aprobada" if puntaje >= UMBRAL_APROBACION else "⚠️ Noticia con baja relevancia"
    fragmento = text.strip().replace("\n", " ")[:300]
    mensaje = (
        f"{estado} (Puntaje: {puntaje}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {dominante} ({porcentaje_dominante}%)\n"
        f"<b>Categoría detectada:</b> {categoria}\n"
        f"<b>Otras emociones detectadas:</b>\n{otras}\n"
        f"<b>Fragmento:</b>\n{fragmento}"
    )
    if url:
        mensaje += f"\n\n{url}"
    return mensaje

@retry(stop_max_attempt_number=3, wait_fixed=2000)
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    logging.info("Mensaje enviado a Telegram")

@app.route("/", methods=["POST"])
def recibir_webhook():
    if request.headers.get("X-Webhook-Token") != WEBHOOK_SECRET:
        return jsonify({"status": "unauthorized"}), 403
    try:
        raw_data = request.get_data(as_text=True)
        data = json.loads(raw_data)
        msg_data = data.get("message") or data.get("channel_post")
        texto = msg_data.get("text", "") if isinstance(msg_data, dict) else str(msg_data)
        texto = texto.strip().replace("\n", " ")
        if not texto:
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
            resumen = "<b>#Resumen Diario</b>\n\n" + "\n".join([f"- {emo}: {round((cant / total) * 100, 2)}%" for emo, cant in top3])
            send_to_telegram(resumen)
            return jsonify({"status": "ok"})

        urls = [p for p in texto.split() if is_valid_url(p)]
        if not urls:
            return jsonify({"status": "ignorado"})
        url = urls[0]

        contenido = extract_text_from_url(url)
        if not contenido:
            return jsonify({"status": "error", "msg": "No se pudo extraer el texto"})

        emocion, scores = detect_emotion(contenido)
        categoria, _ = detectar_categoria(contenido)
        hoy = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with open("registros.csv", "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([hoy, emocion, categoria])
        mensaje = generar_mensaje_emocional(emocion, scores, contenido, url, categoria)
        send_to_telegram(mensaje)
        return jsonify({"status": "ok", "emocion": emocion, "categoria": categoria})
    except Exception as e:
        logging.error(f"Error procesando el webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "msg": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    inicializar_keywords()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
