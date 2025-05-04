import os
import requests
import openai
from bs4 import BeautifulSoup
from flask import Flask, request
from telegram import Bot

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Inicialización
bot = Bot(token=TELEGRAM_TOKEN)
openai.api_key = OPENAI_API_KEY
app = Flask(__name__)

# Diccionario de emociones con palabras clave
EMOCIONES = {
    "DOPAMINA": ["descubrimiento", "avance", "nuevo", "impacto", "invento", "potente", "logro"],
    "OXITOCINA": ["abrazo", "rescate", "ayuda", "solidaridad", "familia", "salvó", "compasión"],
    "SEROTONINA": ["calma", "sabiduría", "paz", "tranquilidad", "reflexión", "armonía"],
    "ASOMBRO": ["gigante", "antiguo", "inesperado", "nunca antes", "colosal", "misterioso"]
}
def analizar_emocion_por_palabras(texto):
    texto = texto.lower()
    puntajes = {emocion: 0 for emocion in EMOCIONES}
    for emocion, palabras in EMOCIONES.items():
        for palabra in palabras:
            if palabra in texto:
                puntajes[emocion] += 1
    max_emocion = max(puntajes, key=puntajes.get)
    return max_emocion if puntajes[max_emocion] > 0 else "DESCARTAR"

def clasificar_con_openai(texto):
    prompt = (
        "Clasifica el siguiente texto en una sola emoción dominante: "
        "DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o DESCARTAR. "
        "Solo responde con una palabra. No expliques nada.\n\n"
        f"Texto: {texto}"
    )
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=5
        )
        emocion = respuesta.choices[0].message.content.strip().upper()
        if emocion in EMOCIONES or emocion == "DESCARTAR":
            return emocion
    except Exception as e:
        print("Error OpenAI:", e)
    return "DESCARTAR"

def generar_guion_emocional(texto, emocion):
    prompt = (
        f"Actúa como un creador de contenido viral. Crea un guión de 3 partes para un video "
        f"emocional de 17 segundos basado en esta emoción: {emocion}. No seas académico. "
        f"Debe tener gancho, desarrollo y cierre. Texto base:\n\n{texto}"
    )
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=300
        )
        return respuesta.choices[0].message.content.strip()
    except:
        return "Error generando guión"

def extraer_texto_de_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        respuesta = requests.get(url, headers=headers, timeout=10)
        sopa = BeautifulSoup(respuesta.text, "html.parser")
        textos = [tag.get_text() for tag in sopa.find_all(["p", "h1", "h2"])]
        return " ".join(textos)[:4000]
    except:
        return ""
        @app.route("/", methods=["POST"])
        def recibir_noticia():
    data = request.get_json()
    url = data.get('url')
    if url:
        noticia = extraer_contenido(url)
        emocion, mensaje = analizar_emocion_y_mensaje(noticia)
        enviar_a_telegram(mensaje)
        return jsonify({"status": "ok", "emocion": emocion})
    return jsonify({"status": "error", "message": "URL no proporcionada"}), 400

    if not texto:
        return {"status": "error", "mensaje": "Texto vacío"}, 400

    emocion_palabra = analizar_emocion_por_palabras(texto)
    emocion_gpt = clasificar_con_openai(texto)
    emocion_final = emocion_gpt if emocion_gpt != "DESCARTAR" else emocion_palabra

    if emocion_final == "DESCARTAR":
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>\n\nSin emoción relevante."
    else:
        guion = generar_guion_emocional(texto, emocion_final)
        mensaje = (
            f"✅ <b>NOTICIA ACEPTADA</b>\n"
            f"<b>Emoción detectada:</b> {emocion_final}\n\n"
            f"<b>Guión sugerido:</b>\n{guion}"
        )

    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode="HTML", disable_web_page_preview=True)
    except Exception as e:
        print("Error enviando mensaje:", e)

    return {"status": "ok", "emocion": emocion_final}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
