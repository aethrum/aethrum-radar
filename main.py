import os
import logging
import json
import re
from flask import Flask, request, jsonify
import requests
from bs4 import BeautifulSoup
from collections import defaultdict, Counter
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import csv
from datetime import datetime

# --- Configuración ---
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024  # 1MB límite

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
TOKEN_SECRETO = os.getenv("TOKEN_SECRETO")
PORT = int(os.getenv("PORT", 10000))

EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"
CSV_FILE = "registros.csv"
UMBRAL_APROBACION = int(os.getenv("UMBRAL_APROBACION", "65"))

if not TELEGRAM_TOKEN or not WEBHOOK_SECRET:
    raise EnvironmentError("Variables de entorno faltantes")

# --- Caches ---
KEYWORDS_CACHE = {}
CATEGORIAS_CACHE = {}
esperando_url_verificacion = {}

# --- Inicialización ---
def inicializar_keywords():
    for folder, cache in [(EMOTION_DIR, KEYWORDS_CACHE), (CATEGORY_DIR, CATEGORIAS_CACHE)]:
        if not os.path.isdir(folder):
            raise FileNotFoundError(f"Falta directorio: {folder}")
        for archivo in os.listdir(folder):
            if archivo.endswith(".json"):
                with open(os.path.join(folder, archivo), "r", encoding="utf-8") as f:
                    datos = json.load(f)
                    if isinstance(datos, dict) and "keywords" in datos:
                        cache[archivo.replace(".json", "")] = datos
                    else:
                        cache[archivo.replace(".json", "")] = {"keywords": datos}

inicializar_keywords()

# --- Utilidades ---
def clean_text(text):
    return re.sub(r'\s+', ' ', re.sub(r'[^\w\sÀ-ÿ]', ' ', text.lower())).strip()

def extract_text_from_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser").get_text(separator=" ")
    except Exception as e:
        logging.error(f"Error extrayendo texto de URL: {e}")
        return None

def is_valid_rss_feed(url):
    try:
        response = requests.get(url, timeout=10)
        root = ET.fromstring(response.content)
        return root.tag in ["rss", "feed"]
    except:
        return False

def detect_emotion(text):
    words = clean_text(text).split()
    word_counts = Counter(words)
    scores = defaultdict(int)
    for emotion, datos in KEYWORDS_CACHE.items():
        for palabra, peso in datos.items():
            scores[emotion] += word_counts.get(palabra.lower(), 0) * peso
    dominante = max(scores, key=scores.get, default="indefinido")
    return dominante, dict(scores)

def detectar_categoria(texto):
    palabras_texto = clean_text(texto).split()
    texto_completo = " " + " ".join(palabras_texto) + " "
    puntajes = defaultdict(int)
    coincidencias = defaultdict(set)
    for categoria, datos in CATEGORIAS_CACHE.items():
        for palabra, peso in datos.get("keywords", {}).items():
            palabra_limpia = palabra.lower().strip()
            if " " in palabra_limpia and f" {palabra_limpia} " in texto_completo:
                puntajes[categoria] += peso
                coincidencias[categoria].add(palabra_limpia)
            elif palabra_limpia in palabras_texto:
                repeticiones = palabras_texto.count(palabra_limpia)
                puntajes[categoria] += repeticiones * peso
                coincidencias[categoria].add(palabra_limpia)
    if not puntajes:
        return "sin_categoria", {}
    max_puntaje = max(puntajes.values())
    candidatas = [cat for cat, pts in puntajes.items() if pts == max_puntaje]
    return candidatas[0] if len(candidatas) == 1 else max(candidatas, key=lambda c: len(coincidencias[c])), dict(puntajes)

def calcular_nuevo_puntaje(dominante, scores, categoria):
    total = sum(scores.values()) or 1
    porcentaje = round((scores.get(dominante, 0) / total) * 100, 2)
    relevantes = [v for v in scores.values() if (v / total) * 100 > 5]
    diversidad = min(len(relevantes), 5) / 5
    bonus = 1 if categoria != "sin_categoria" else 0
    puntaje = round((porcentaje * 0.5) + (diversidad * 20) + (bonus * 30), 2)
    return puntaje, porcentaje

def registrar_en_csv(fecha, emocion, url, categoria):
    with open(CSV_FILE, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow([fecha, emocion, url, categoria])

def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error enviando mensaje: {e}")

# --- Rutas ---
@app.route(f"/webhook/{WEBHOOK_SECRET}", methods=["POST"])
def webhook():
    update = request.get_json()
    if not update or "message" not in update:
        return jsonify({"status": "ok"}), 200

    message = update["message"]
    chat_id = message["chat"]["id"]
    texto = message.get("text", "").strip()

    if chat_id in esperando_url_verificacion:
        url = texto
        if is_valid_rss_feed(url):
            send_telegram(chat_id, "✅ URL RSS válida")
        else:
            send_telegram(chat_id, "❌ No es una URL RSS válida")
        esperando_url_verificacion.pop(chat_id, None)
        return jsonify({"status": "ok"}), 200

    if texto.startswith("/verificar"):
        esperando_url_verificacion[chat_id] = True
        send_telegram(chat_id, "Introduce la dirección URL RSS para verificar.")
    elif texto.startswith("/resumen"):
        return handle_resumen(chat_id)
    return jsonify({"status": "ok"}), 200

@app.route("/ifttt", methods=["POST"])
def ifttt():
    data = request.get_json()
    token = data.get("token")
    url = data.get("url")
    if token != TOKEN_SECRETO or not url:
        return jsonify({"status": "unauthorized"}), 401
    texto = extract_text_from_url(url)
    if not texto:
        return jsonify({"status": "error"}), 400
    dominante, scores = detect_emotion(texto)
    categoria, _ = detectar_categoria(texto)
    mensaje = generar_mensaje_emocional(dominante, scores, texto, url, categoria)
    registrar_en_csv(datetime.now().isoformat(), dominante, url, categoria)
    send_telegram(os.getenv("TELEGRAM_CHAT_ID"), mensaje)
    return jsonify({"status": "ok"}), 200

def generar_mensaje_emocional(dominante, scores, texto, url=None, categoria=None):
    puntaje, porcentaje = calcular_nuevo_puntaje(dominante, scores, categoria)
    fragmento = texto.strip().replace("\n", " ")[:300]
    mensaje = (
        f"✅ Puntaje: {puntaje}%\n"
        f"Emoción dominante: {dominante} ({porcentaje}%)\n"
        f"Categoría: {categoria}\n"
        f"Fragmento:\n{fragmento}"
    )
    if url:
        mensaje += f"\n\n{url}"
    return mensaje

def handle_resumen(chat_id):
    if not os.path.exists(CSV_FILE):
        send_telegram(chat_id, "No hay registros aún.")
        return jsonify({"status": "ok"}), 200
    emociones = Counter()
    categorias = Counter()
    total = 0
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        for row in csv.reader(f, delimiter=";"):
            if len(row) < 4:
                continue
            _, emocion, _, categoria = row
            emociones[emocion] += 1
            categorias[categoria] += 1
            total += 1
    if total == 0:
        send_telegram(chat_id, "No hay registros válidos.")
        return jsonify({"status": "ok"}), 200
    top_emocion, count = emociones.most_common(1)[0]
    porcentaje = round((count / total) * 100, 2)
    resumen = (
        f"Total noticias: {total}\n"
        f"Emoción dominante: {top_emocion} ({porcentaje}%)\n"
        f"Principales categorías:\n" + "\n".join(f"- {k}: {v}" for k, v in categorias.most_common(3))
    )
    send_telegram(chat_id, resumen)
    return jsonify({"status": "ok"}), 200

# --- Inicio ---
if __name__ == "__main__":
    logging.info(f"Iniciando servidor en puerto {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
