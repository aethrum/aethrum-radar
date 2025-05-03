
import os
import openai
from flask import Flask, request
import requests

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje
    }
    requests.post(url, data=data)

def evaluar_texto_con_openai(texto):
    try:
        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Eres un analista emocional experto. Elige solo una: DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o DESCARTAR. Justifica en 1 línea."
                },
                {
                    "role": "user",
                    "content": f"Evalúa este texto: {texto}"
                }
            ]
        )
        return respuesta.choices[0].message.content.strip()
    except Exception as e:
        return f"Error al evaluar con OpenAI: {str(e)}"

@app.route("/", methods=["POST"])
def recibir_mensaje():
    data = request.json
    if "message" in data and "text" in data["message"]:
        texto = data["message"]["text"]
        resultado = evaluar_texto_con_openai(texto)
        if "DOPAMINA" in resultado or "OXITOCINA" in resultado or "SEROTONINA" in resultado or "ASOMBRO" in resultado:
            mensaje = f"✅ NOTICIA ACEPTADA
Emoción detectada: {resultado}

Texto recibido:
{texto}"
        elif "DESCARTAR" in resultado:
            mensaje = f"❌ NOTICIA DESCARTADA
No se detectaron emociones clave.

Texto recibido:
{texto}"
        else:
            mensaje = f"⚠️ EVALUACIÓN INDETERMINADA
{resultado}

Texto recibido:
{texto}"
        enviar_telegram(mensaje)
    return {"status": "ok"}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

