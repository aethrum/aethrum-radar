
import os
import logging
import json
import re
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import csv
from collections import defaultdict, Counter
from urllib.parse import urlparse
from filelock import FileLock

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "mi_token_super_secreto")
EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"
UMBRAL_APROBACION = int(os.getenv("UMBRAL_APROBACION", 65))
REGISTROS_CSV = "registros.csv"

KEYWORDS_CACHE = {}
CATEGORIAS_CACHE = {}
pending_verifications = {}
pending_summaries = {}

def inicializar_keywords():
    for archivo in os.listdir(EMOTION_DIR):
        if archivo.endswith(".json"):
            with open(os.path.join(EMOTION_DIR, archivo), "r", encoding="utf-8") as f:
                KEYWORDS_CACHE[archivo.replace(".json", "")] = json.load(f)
    for archivo in os.listdir(CATEGORY_DIR):
        if archivo.endswith(".json"):
            with open(os.path.join(CATEGORY_DIR, archivo), "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    if "keywords" in data:
                        CATEGORIAS_CACHE[archivo.replace(".json", "")] = data
                    else:
                        CATEGORIAS_CACHE[archivo.replace(".json", "")] = {"keywords": data}

inicializar_keywords()

def clean_text(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()

def extract_text_from_url(url):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return None
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        return soup.get_text(separator=' ')
    except Exception as e:
        logging.error(f"Error al extraer texto: {e}")
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
    palabras_texto = clean_text(texto).split()
    texto_completo = " " + " ".join(palabras_texto) + " "
    puntajes = defaultdict(int)
    coincidencias = defaultdict(set)
    for categoria, contenido in CATEGORIAS_CACHE.items():
        keywords = contenido.get("keywords", {})
        for palabra, peso in keywords.items():
            palabra_limpia = palabra.lower().strip()
            if " " in palabra_limpia:
                if f" {palabra_limpia} " in texto_completo:
                    puntajes[categoria] += peso
                    coincidencias[categoria].add(palabra_limpia)
            else:
                repeticiones = palabras_texto.count(palabra_limpia)
                if repeticiones:
                    puntajes[categoria] += repeticiones * peso
                    coincidencias[categoria].add(palabra_limpia)
    if not puntajes:
        return "sin_categoria", {}
    max_puntaje = max(puntajes.values())
    candidatas = [cat for cat, pts in puntajes.items() if pts == max_puntaje]
    if len(candidatas) == 1:
        return candidatas[0], dict(puntajes)
    else:
        mejor = max(candidatas, key=lambda c: (len(coincidencias[c]), c))
        return mejor, dict(puntajes)

EMOJI = {
    "Dopamina": "✨", "Oxitocina": "❤️", "Asombro": "🌟",
    "Adrenalina": "⚡", "Norepinefrina": "🔥", "Anandamida": "🌀",
    "Serotonina": "🧘", "Acetilcolina": "🧠", "Fetileminalina": "💘"
}

def calcular_nuevo_puntaje(dominante, scores, categoria):
    total = sum(scores.values()) or 1
    porcentaje = round((scores.get(dominante, 0) / total) * 100, 2)
    relevantes = [v for v in scores.values() if (v / total) * 100 > 5]
    diversidad = min(len(relevantes), 5) / 5
    bonus = 1 if categoria != "sin_categoria" else 0
    puntaje = round((porcentaje * 0.5) + (diversidad * 20) + (bonus * 30), 2)
    return puntaje, porcentaje

def generar_mensaje_emocional(dominante, scores, texto, url=None, categoria=None):
    puntaje, porcentaje = calcular_nuevo_puntaje(dominante, scores, categoria)
    total = sum(scores.values()) or 1
    porcentajes = [(k, round((v / total) * 100, 2)) for k, v in sorted(scores.items(), key=lambda x: x[1], reverse=True)]
    otras = "\n".join([f"- {e}: {p}%" for e, p in porcentajes if e != dominante])
    emoji = EMOJI.get(dominante, "")
    estado = "✅ Noticia Aprobada" if puntaje >= UMBRAL_APROBACION else "⚠️ Noticia con baja relevancia"
    fragmento = texto.strip().replace("\n", " ")[:300].replace("maldita", "**BENDITO**")
    mensaje = (
        f"{estado} (Puntaje: {puntaje}%)\n"
        f"<b>Emoción dominante:</b> {emoji} {dominante} ({porcentaje}%)\n"
        f"<b>Categoría detectada:</b> {categoria}\n"
        f"<b>Otras emociones detectadas:</b>\n{otras}\n"
        f"<b>Fragmento:</b>\n{fragmento}"
    )
    if url:
        mensaje += f"\n\n{url}"
    return mensaje

def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error al enviar mensaje a Telegram: {e}")

@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update or "message" not in update:
        return jsonify({"status": "ok"}), 200

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    if text.startswith("/verificar"):
        return handle_verificar(chat_id, text)
    elif text.startswith("/resumen"):
        return handle_resumen(chat_id, text)
    return jsonify({"status": "ok"}), 200

def handle_verificar(chat_id, text):
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(chat_id, "Por favor, proporciona una URL o texto para verificar.")
        return jsonify({"status": "ok"}), 200

    input_text = parts[1]
    if input_text.startswith("http"):
        texto = extract_text_from_url(input_text)
        if not texto:
            send_telegram_message(chat_id, "No se pudo extraer texto de la URL.")
            return jsonify({"status": "ok"}), 200
    else:
        texto = input_text

    dominante, scores = detect_emotion(texto)
    categoria, _ = detectar_categoria(texto)
    mensaje = generar_mensaje_emocional(dominante, scores, texto, input_text if input_text.startswith("http") else None, categoria)
    send_telegram_message(chat_id, mensaje)
    return jsonify({"status": "ok"}), 200

def handle_resumen(chat_id, text):
    parts = text.split(maxsplit=1)
    if len(parts) < 2:
        send_telegram_message(chat_id, "Por favor, proporciona una URL o texto para resumir.")
        return jsonify({"status": "ok"}), 200

    input_text = parts[1]
    if input_text.startswith("http"):
        texto = extract_text_from_url(input_text)
        if not texto:
            send_telegram_message(chat_id, "No se pudo extraer texto de la URL.")
            return jsonify({"status": "ok"}), 200
    else:
        texto = input_text

    resumen = " ".join(clean_text(texto).split()[:100]) + "..."
    send_telegram_message(chat_id, f"<b>Resumen:</b>\n{resumen}")
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
