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

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMOTION_DIR = "emociones"
CATEGORY_DIR = "categorias"
UMBRAL_APROBACION = 65

STOPWORDS = {
    "fox", "news", "media", "audio", "weather", "outkick", "noticias", "books",
    "u.s.", "crime", "topics", "week's", "top", "latest", "unread", "subscribe"
}

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
    cleaned = ''.join(c.lower() if c.isalnum() or c.isspace() else ' ' for c in text)
    return ' '.join([w for w in cleaned.split() if w not in STOPWORDS])

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

def detect_emotion(text, keywords_dict):
    words = clean_text(text).split()
    scores = defaultdict(int)
    for emotion, palabras in keywords_dict.items():
        for palabra, peso in palabras.items():
            scores[emotion] += words.count(palabra.lower()) * peso
    dominante = max(scores, key=scores.get, default=None)
    return dominante, scores

def detectar_categoria(texto, carpeta=CATEGORY_DIR):
    texto_limpio = clean_text(texto).lower()
    palabras_texto = texto_limpio.split()
    texto_completo = " " + " ".join(palabras_texto) + " "
    puntajes = defaultdict(int)

    for archivo in os.listdir(carpeta):
        if archivo.endswith(".json"):
            ruta = os.path.join(carpeta, archivo)
            try:
                with open(ruta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for categoria, contenido in data.items():
                        keywords = contenido.get("keywords", {})
                        for palabra, peso in keywords.items():
                            palabra_limpia = palabra.lower().strip()
                            if " " in palabra_limpia:
                                if f" {palabra_limpia} " in texto_completo:
                                    puntajes[categoria] += peso
                            else:
                                puntajes[categoria] += palabras_texto.count(palabra_limpia) * peso
            except Exception as e:
                logging.warning(f"Error procesando {archivo}: {e}")

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
            data = {}

        msg_data = data.get("message") or data.get("channel_post")
        if isinstance(msg_data, dict):
            texto = msg_data.get("text", "")
        else:
            texto = str(msg_data or data.get("message") or "")

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

        urls = [p for p in texto.split() if p.startswith("http")]
        if not urls:
            logging.warning(f"Texto ignorado por no contener URL válida: {texto}")
            return jsonify({"status": "ignorado"})
        url = urls[0]

        contenido = extract_text_from_url(url)
        if not contenido:
            return jsonify({"status": "error", "msg": "No se pudo extraer el texto"})

        keywords_dict = cargar_keywords()
        emocion, scores = detect_emotion(contenido, keywords_dict)
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
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
