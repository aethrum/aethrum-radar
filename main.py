import os
import requests
import openai
from flask import Flask, request
from bs4 import BeautifulSoup

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

def enviar_telegram(mensaje):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
        requests.post(url, data=data)
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

def extraer_texto_desde_url(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        textos = soup.find_all(['p', 'h1', 'h2'])
        contenido = " ".join([p.get_text() for p in textos])
        return contenido.strip()[:4000]  # Límite seguro
    except Exception as e:
        return f"Error al leer el link: {e}"

def evaluar_emocion(texto):
    try:
        prompt = (
            "Eres un analista emocional experto. Evalúa si este texto genera una emoción fuerte para redes sociales. "
            "Elige solo una: DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o DESCARTAR. Justifica en 1 línea.

"
            f"TEXTO:
{texto}"
        )
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error OpenAI: {e}"

@app.route("/", methods=["POST"])
def recibir():
    data = request.get_json()
    texto_original = data.get("text", "").strip()

    if not texto_original:
        return {"status": "error", "message": "Texto vacío"}, 400

    if texto_original.startswith("http"):
        contenido = extraer_texto_desde_url(texto_original)
        texto_a_evaluar = contenido
    else:
        texto_a_evaluar = texto_original

    resultado = evaluar_emocion(texto_a_evaluar)

    if any(e in resultado.upper() for e in ["DOPAMINA", "OXITOCINA", "SEROTONINA", "ASOMBRO"]):
        mensaje = f"✅ <b>NOTICIA ACEPTADA</b>

{resultado}"
    else:
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>

{resultado}"

    enviar_telegram(mensaje)
    return {"status": "ok", "evaluacion": resultado}

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

