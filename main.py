import os
import logging
import json
import time
import re
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import defaultdict, Counter
from urllib.parse import urlparse
from filelock import FileLock

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secure_token")
EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"
UMBRAL_APROBACION = int(os.getenv("UMBRAL_APROBACION", 65))
REGISTROS_CSV = "registros.csv"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

KEYWORDS_CACHE = {}
CATEGORIAS_CACHE = {}

def inicializar_keywords():
    for archivo in os.listdir(EMOTION_DIR):
        if archivo.endswith(".json"):
            nombre = archivo.replace(".json", "")
            with open(os.path.join(EMOTION_DIR, archivo), "r", encoding="utf-8") as f:
                KEYWORDS_CACHE[nombre] = json.load(f)
    for archivo in os.listdir(CATEGORY_DIR):
        if archivo.endswith(".json"):
            with open(os.path.join(CATEGORY_DIR, archivo), "r", encoding="utf-8") as f:
                data = json.load(f)
                CATEGORIAS_CACHE.update({archivo.replace(".json", ""): data})

inicializar_keywords()

def clean_text(text):
    return re.sub(r'[^a-z0-9\s]', ' ', text.lower()).strip()

def extract_text_from_url(url):
    try:
        time.sleep(2)
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=' ')
    except Exception as e:
        logging.error(f"Error extrayendo texto: {e}")
        return None

def detect_emotion(text):
    words = clean_text(text).split()
    word_counts = Counter(words)
    scores = defaultdict(int)
    for emotion, palabras in KEYWORDS_CACHE.items():
        for palabra, peso in palabras.items():
            scores[emotion] += word_counts.get(palabra.lower(), 0) * peso
    dominante = max(scores, key=scores.get, default="indefinido")
    return dominante, scores

def detectar_categoria(texto):
    texto_limpio = clean_text(texto)
    palabras_texto = texto_limpio.split()
    texto_completo = " " + " ".join(palabras_texto) + " "
    puntajes = defaultdict(int)
    for categoria, palabras in CATEGORIAS_CACHE.items():
        for palabra, peso in palabras.items():
            palabra = palabra.lower().strip()
            if " " in palabra:
                if f" {palabra} " in texto_completo:
                    puntajes[categoria] += peso
            else:
                puntajes[categoria] += palabras_texto.count(palabra) * peso
    categoria_dominante = max(puntajes, key=puntajes.get, default="otros")
    return categoria_dominante, dict(puntajes)

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Asombro": "🌟",
    "Adrenalina": "⚡", "Norepinefrina": "🔥", "Anandamida": "🌀",
    "Serotonina": "🧘", "Acetilcolina": "🧠", "Fetileminalina": "💘"
}

def calcular_nuevo_puntaje(dominante, scores, categoria):
    total = sum(scores.values()) or 1
    porcentaje = (scores[dominante] / total) * 100
    diversidad = min(len([v for v in scores.values() if (v / total) * 100 > 5]), 5) / 5
    bonus = 30 if categoria != "otros" else 0
    final = round((porcentaje * 0.5) + (diversidad * 20) + bonus, 2)
    return final, round(porcentaje, 2)

def generar_mensaje_emocional(dominante, scores, text, url=None, categoria=None):
    puntaje, porcentaje_dominante = calcular_nuevo_puntaje(dominante, scores, categoria)
    total = sum(scores.values()) or 1
    porcentajes = [(k, round((v / total) * 100, 2)) for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True) if v > 0]
    otras = "\n".join([f"- {k}: {p}%" for k, p in porcentajes if k != dominante])
    emoji = EMOJI.get(dominante, "")
    estado = "✅ Noticia Aprobada" if puntaje >= UMBRAL_APROBACION else "⚠️ Noticia con baja relevancia"
    fragmento = text.strip().replace("\n", " ")[:300].replace("maldita", "**BENDITO**")
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

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=data, timeout=10)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    if request.headers.get("Authorization") != f"Bearer {WEBHOOK_SECRET}":
        return jsonify({"status": "forbidden"}), 403
    try:
        raw_data = request.get_data(as_text=True)
        data = json.loads(raw_data)
        msg_data = data.get("message") or data.get("channel_post")
        texto = msg_data.get("text", "") if isinstance(msg_data, dict) else str(msg_data or "")
        texto = texto.strip().replace("\n", " ")
        if not texto:
            return jsonify({"status": "ignorado"})

        if texto.lower() == "/resumen":
            if not os.path.exists(REGISTROS_CSV):
                send_to_telegram("⚠️ Aún no hay datos.")
                return jsonify({"status": "ok"})
            with FileLock(REGISTROS_CSV + ".lock"):
                with open(REGISTROS_CSV, "r", encoding="utf-8") as f:
                    rows = list(csv.reader(f))
            total = len(rows)
            emociones = [row[1] for row in rows if len(row) > 1]
            conteo = Counter(emociones).most_common(3)
            resumen = "<b>#Resumen Diario</b>\n\n" + "\n".join([f"- {e}: {round(c / total * 100, 2)}%" for e, c in conteo])
            send_to_telegram(resumen)
            return jsonify({"status": "ok"})

        urls = [x for x in texto.split() if re.match(r'^https?://', x)]
        if not urls:
            return jsonify({"status": "ignorado"})
        url = urls[0]
        contenido = extract_text_from_url(url)
        if not contenido:
            return jsonify({"status": "error", "msg": "No se pudo extraer texto"})

        emocion, scores = detect_emotion(contenido)
        categoria, _ = detectar_categoria(contenido)
        hoy = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with FileLock(REGISTROS_CSV + ".lock"):
            with open(REGISTROS_CSV, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([hoy, emocion, categoria])
        mensaje = generar_mensaje_emocional(emocion, scores, contenido, url, categoria)
        send_to_telegram(mensaje)
        return jsonify({"status": "ok", "emocion": emocion, "categoria": categoria})
    except Exception as e:
        logging.error(f"Error procesando webhook: {e}")
        return jsonify({"status": "error", "msg": str(e)})

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "msg": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
