import os
import requests
import openai
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from telegram import Bot

# Configuración de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Inicializar Flask y Telegram Bot
app = Flask(__name__)
bot = Bot(token=TELEGRAM_TOKEN)

# Palabras clave por emoción neuroquímica
EMOCIONES = {
    "DOPAMINA": ["descubrimiento", "avance", "nuevo", "impacto", "invento", "logro", "innovador"],
    "OXITOCINA": ["abrazo", "rescate", "ayuda", "solidaridad", "familia", "salvó", "unidos"],
    "SEROTONINA": ["calma", "sabiduría", "paz", "tranquilidad", "reflexión", "armonía"],
    "ASOMBRO": ["gigante", "antiguo", "inesperado", "jamás visto", "colosal", "misterioso"],
    "ADRENALINA": ["urgente", "peligro", "explosión", "alerta", "intenso", "correr"]
}
def analizar_emocion_por_palabras(texto):
    texto = texto.lower()
    puntajes = {e: 0 for e in EMOCIONES}
    for emocion, palabras in EMOCIONES.items():
        for palabra in palabras:
            if palabra in texto:
                puntajes[emocion] += 1
    emocion_detectada = max(puntajes, key=puntajes.get)
    return emocion_detectada if puntajes[emocion_detectada] > 0 else "DESCARTAR"

def clasificar_con_openai(texto):
    prompt = (
        "Clasifica el siguiente texto con una sola palabra: "
        "DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO, ADRENALINA o DESCARTAR. "
        "No expliques. Solo la emoción en mayúsculas:\n\n"
        f"{texto}"
    )
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=5,
            temperature=0.2
        )
        emocion = respuesta.choices[0].message.content.strip().upper()
        return emocion if emocion in EMOCIONES or emocion == "DESCARTAR" else "DESCARTAR"
    except:
        return "DESCARTAR"

def generar_contenido_emocional(texto, emocion):
    prompt = (
        f"Actúa como un creador de contenido viral para TikTok. "
        f"Genera un guión emocional breve (máx. 300 caracteres), con gancho inicial, desarrollo breve y cierre provocador. "
        f"Incluye CTA emocional y formato sugerido (reel, historia, carrusel). "
        f"Texto base:\n\n{texto}\n\nEmoción dominante: {emocion}"
    )
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.8
        )
        return respuesta.choices[0].message.content.strip()
    except:
        return "Error generando guión emocional."

def extraer_contenido(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        textos = [t.get_text() for t in soup.find_all(["p", "h1", "h2"])]
        return " ".join(textos)[:4000]
    except:
        return ""
def enviar_a_telegram(mensaje):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        print("Error enviando a Telegram:", e)

@app.route("/webhook", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    url = data.get("url")
    texto_directo = data.get("text")

    if url:
        texto = extraer_contenido(url)
    elif texto_directo:
        texto = texto_directo
    else:
        return jsonify({"status": "error", "message": "No se recibió texto ni link"}), 400

    emocion_palabra = analizar_emocion_por_palabras(texto)
    emocion_openai = clasificar_con_openai(texto)

    emocion_final = emocion_openai if emocion_openai != "DESCARTAR" else emocion_palabra

    if emocion_final == "DESCARTAR":
        mensaje = "❌ <b>NOTICIA DESCARTADA</b>\nNo se detectó emoción significativa."
    else:
        guion = generar_contenido_emocional(texto, emocion_final)
        mensaje = (
            f"✅ <b>NOTICIA ACEPTADA</b>\n"
            f"<b>Emoción:</b> {emocion_final}\n\n"
            f"<b>Guión sugerido:</b>\n{guion}"
        )

    enviar_a_telegram(mensaje)
    return jsonify({"status": "ok", "emocion": emocion_final})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
