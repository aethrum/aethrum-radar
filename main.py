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

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "mi_token_super_secreto")
EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"
UMBRAL_APROBACION = int(os.getenv("UMBRAL_APROBACION", 65))
REGISTROS_CSV = "registros.csv"

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

KEYWORDS_CACHE = {}
CATEGORIAS_CACHE = {}

pending_verifications = {}

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
    return re.sub(r'[^a-z0-9\s]', ' ', text.lower()).strip()

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

def send_to_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

@app.route("/", methods=["POST"])
def recibir_webhook():
    data = request.get_json(force=True)
    if data.get("token") != WEBHOOK_SECRET:
        return jsonify({"status": "forbidden"}), 403

    texto = data.get("message", "").strip()
    if not texto:
        return jsonify({"status": "ignorado"})

    if texto.lower() == "verificar":
        pending_verifications["esperando_url"] = True
        send_to_telegram("Por favor, introduce ahora la URL que deseas verificar.")
        return jsonify({"status": "esperando_url"})

    if pending_verifications.get("esperando_url"):
        url = texto
        pending_verifications.clear()
        if not re.match(r'^https?://', url):
            send_to_telegram("⚠️ URL inválida. Asegúrate de que comience con http o https.")
            return jsonify({"status": "url inválida"})

        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                send_to_telegram(f"✅ URL verificada con éxito: {url}")
                return jsonify({"status": "verificada"})
            else:
                send_to_telegram(f"❌ La URL respondió con error: {response.status_code}")
                return jsonify({"status": "rechazada"})
        except Exception as e:
            send_to_telegram(f"❌ Error al verificar la URL: {e}")
            return jsonify({"status": "error"})

    if texto.lower() == "/resumen":
        if not os.path.exists(REGISTROS_CSV):
            send_to_telegram("⚠️ No hay datos para el resumen.")
            return jsonify({"status": "ok"})
        with FileLock(REGISTROS_CSV + ".lock"):
            with open(REGISTROS_CSV, "r", encoding="utf-8") as f:
                rows = list(csv.reader(f))
        emociones = [r[1] for r in rows if len(r) > 1]
        top3 = Counter(emociones).most_common(3)
        resumen = "<b>#Resumen Diario</b>\n\n" + "\n".join([f"- {e}: {round(c/len(rows)*100,2)}%" for e, c in top3])
        send_to_telegram(resumen)
        return jsonify({"status": "ok"})

    urls = [p for p in texto.split() if re.match(r'^https?://', p)]
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

@app.errorhandler(404)
def ruta_no_encontrada(e):
    return jsonify({"status": "error", "msg": "Ruta no encontrada"}), 404

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
