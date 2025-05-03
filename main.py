import os
import requests
import openai
from flask import Flask, request

# Configura tus claves de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

openai.api_key = OPENAI_API_KEY

app = Flask(__name__)

# Función para enviar mensajes a Telegram
def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")

# Análisis emocional con OpenAI
def evaluar_emocion_con_openai(texto):
    try:
        prompt = (
            "Evalúa si el siguiente texto puede generar una emoción poderosa como dopamina, "
            "oxitocina, serotonina o asombro. Responde solo con una palabra en mayúsculas: "
            "DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o NINGUNA. Texto: " + texto
        )

        respuesta = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un analista emocional experto en contenido viral."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=10
        )

        emocion = respuesta.choices[0].message.content.strip().upper()
        return emocion
    except Exception as e:
        return f"Error al evaluar con OpenAI:\n{str(e)}"

# Ruta principal para recibir texto
@app.route("/", methods=["POST"])
def recibir_texto():
    data = request.get_json()
    texto = data.get("text", "")
    
    if not texto:
        return {"status": "error", "message": "No se recibió texto"}, 400

    emocion = evaluar_emocion_con_openai(texto)

    if emocion in ["DOPAMINA", "OXITOCINA", "SEROTONINA", "ASOMBRO"]:
        mensaje = f"✅ <b>NOTICIA DESTACADA</b>\nEmoción detectada: <b>{emocion}</b>\n\nTexto recibido:\n{texto}"
    else:
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>\nNo se detectaron emociones clave.\n\nTexto recibido:\n{texto}"

    enviar_telegram(mensaje)
    return {"status": "ok", "emocion": emocion}

# Iniciar servidor Flask
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
