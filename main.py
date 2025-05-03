import os
import requests
import openai
from flask import Flask, request
from bs4 import BeautifulSoup

# --- CONFIGURACIÓN DE CLAVES ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# --- INICIALIZAR FLASK ---
app = Flask(__name__)

# --- FUNCIÓN: ENVIAR A TELEGRAM ---
def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": mensaje,
            "parse_mode": "HTML"
        }
        requests.post(url, data=payload)
    except Exception as e:
        print("Error al enviar a Telegram:", e)

# --- FUNCIÓN: EXTRAER TEXTO DESDE UN LINK ---
def extraer_texto_desde_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        textos = soup.find_all(['p', 'h1', 'h2'])
        contenido = " ".join([t.get_text() for t in textos])
        return contenido.strip()[:4000]  # Límite por seguridad
    except Exception as e:
        return f"[ERROR LINK] {str(e)}"

# --- FUNCIÓN: EVALUAR CON OPENAI ---
def evaluar_emocion(texto):
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un analista emocional para contenido viral. Evalúa si el siguiente texto puede "
                        "generar DOPAMINA, OXITOCINA, SEROTONINA o ASOMBRO. Si no hay emoción clara, responde DESCARTAR. "
                        "Devuelve solo una palabra en mayúsculas."
                    )
                },
                {
                    "role": "user",
                    "content": texto
                }
            ],
            temperature=0.3,
            max_tokens=10
        )
        return respuesta.choices[0].message.content.strip().upper()
    except Exception as e:
        return f"[ERROR OPENAI] {str(e)}"

# --- RUTA PRINCIPAL ---
@app.route("/", methods=["POST"])
def recibir():
    data = request.get_json()
    texto_entrada = data.get("text", "").strip()

    if not texto_entrada:
        return {"status": "error", "message": "Texto vacío"}, 400

    # LINK o TEXTO
    if texto_entrada.startswith("http"):
        texto_procesado = extraer_texto_desde_url(texto_entrada)
    else:
        texto_procesado = texto_entrada

    resultado = evaluar_emocion(texto_procesado)

    # --- RESPUESTA Y ENVÍO ---
    if resultado in ["DOPAMINA", "OXITOCINA", "SEROTONINA", "ASOMBRO"]:
        mensaje = f"✅ <b>NOTICIA ACEPTADA</b>\nEmoción detectada: <b>{resultado}</b>\n\n{texto_entrada}"
    elif resultado.startswith("[ERROR"):
        mensaje = f"⚠️ <b>ERROR EN SISTEMA</b>\n{resultado}"
    else:
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>\nSin emoción clara.\n\n{texto_entrada}"

    enviar_telegram(mensaje)
    return {"status": "ok", "emocion": resultado}, 200

# --- INICIO DEL SERVIDOR ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

