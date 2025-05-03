import os
import openai
import requests
from flask import Flask, request

app = Flask(__name__)

# CONFIGURA AQUÍ TUS CLAVES
openai.api_key = os.getenv("OPENAI_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# EMOCIONES CLAVE
EMOCIONES_CLAVE = ["DOPAMINA", "OXITOCINA", "SEROTONINA", "ASOMBRO"]

# ENVÍA MENSAJE A TELEGRAM
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    requests.post(url, data=data)

# ANÁLISIS LOCAL SIMPLE POR PALABRAS
def analizar_emociones_clave(texto):
    texto_mayus = texto.upper()
    for emocion in EMOCIONES_CLAVE:
        if emocion in texto_mayus:
            return emocion
    return None

# EVALUACIÓN CON OPENAI (v1.0+)
def evaluar_con_openai(texto):
    try:
        response = openai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Eres un evaluador experto en emociones virales. Solo responde con una palabra: DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o DESCARTAR."},
                {"role": "user", "content": f"Elige solo una emoción dominante para este texto:\n{texto}"}
            ],
            temperature=0
        )
        resultado = response.choices[0].message.content.strip().upper()
        return resultado
    except Exception as e:
        return f"ERROR OPENAI: {str(e)}"

# PROCESAMIENTO PRINCIPAL
@app.route("/", methods=["POST"])
def recibir_mensaje():
    data = request.json
    if "message" not in data:
        return "Sin mensaje", 200

    mensaje = data["message"].get("text", "")
    if not mensaje:
        return "Mensaje vacío", 200

    texto_analizado = mensaje.strip()
    emocion_detectada = analizar_emociones_clave(texto_analizado)

    if emocion_detectada:
        enviar_telegram(f"✅ Emoción detectada por palabras clave: <b>{emocion_detectada}</b>")
    else:
        emocion_ia = evaluar_con_openai(texto_analizado)
        if emocion_ia in EMOCIONES_CLAVE:
            enviar_telegram(f"✅ Evaluación avanzada: <b>{emocion_ia}</b>")
        elif emocion_ia.startswith("ERROR"):
            enviar_telegram(f"⚠️ Error al evaluar con OpenAI:\n{emocion_ia}")
        else:
            enviar_telegram("❌ NOTICIA DESCARTADA\nNo se detectaron emociones clave ni impacto emocional suficiente.")

    return "OK", 200

# INICIO DE FLASK
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

