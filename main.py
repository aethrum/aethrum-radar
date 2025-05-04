import os
import requests
import openai
from flask import Flask, request
from bs4 import BeautifulSoup

app = Flask(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Palabras clave por emoción
PALABRAS_CLAVE = {
    "DOPAMINA": ["nuevo", "descubrimiento", "premio", "avance", "sorprendente", "primera vez"],
    "OXITOCINA": ["rescate", "ayuda", "solidaridad", "amor", "abrazo", "salvó"],
    "SEROTONINA": ["logro", "calma", "tranquilidad", "serenidad", "cura", "balance", "esperanza"],
    "ASOMBRO": ["inesperado", "misterioso", "antiguo", "gigante", "colosal", "jamás visto"]
}

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

def analizar_palabras_clave(texto):
    texto = texto.lower()
    conteo = {emocion: 0 for emocion in PALABRAS_CLAVE}
    for emocion, palabras in PALABRAS_CLAVE.items():
        for palabra in palabras:
            if palabra in texto:
                conteo[emocion] += 1
    emocion_detectada = max(conteo, key=conteo.get)
    return emocion_detectada if conteo[emocion_detectada] > 0 else "DESCARTAR"

def evaluar_con_openai(texto):
    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "Evalúa si este texto genera DOPAMINA, OXITOCINA, SEROTONINA, ASOMBRO o se debe DESCARTAR. Responde solo una palabra en mayúsculas."
                },
                {
                    "role": "user",
                    "content": texto
                }
            ],
            temperature=0.3,
            max_tokens=10
        )
        return response.choices[0].message.content.strip().upper()
    except Exception as e:
        return f"ERROR OPENAI: {e}"
def generar_guion_emocional(texto, emocion):
    try:
        prompt = f"""
Crea un guión de 17 segundos estilo TikTok, dividido en 3 partes:
1. Gancho inicial impactante
2. Explicación emocional rápida del evento
3. Cierre con llamado a la acción

Emoción dominante: {emocion}
Texto base: {texto}

El guión debe ser humano, emocionante, y de alto impacto.
        """
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un creador experto en contenido viral emocional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[ERROR GUION] {e}"

def sugerir_formato(emocion):
    if emocion == "DOPAMINA":
        return "Reel con subtítulos grandes y cortes rápidos"
    elif emocion == "OXITOCINA":
        return "Historia con música suave y voz en off cálida"
    elif emocion == "ASOMBRO":
        return "Carrusel visual con zooms lentos"
    elif emocion == "SEROTONINA":
        return "Video narrado estilo relajante con texto flotante"
    else:
        return "Formato no definido"

def extraer_texto_desde_url(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        textos = soup.find_all(['p', 'h1', 'h2'])
        contenido = " ".join([t.get_text() for t in textos])
        return contenido.strip()[:4000]
    except Exception as e:
        return f"[ERROR LINK] {str(e)}"
        @app.route("/", methods=["POST"])
def recibir():
    data = request.get_json()
    texto = data.get("text", "").strip()

    if not texto:
        return {"status": "error", "message": "Texto vacío"}, 400

    if texto.startswith("http"):
        procesado = extraer_texto_desde_url(texto)
    else:
        procesado = texto

    emocion_keywords = analizar_palabras_clave(procesado)
    emocion_openai = evaluar_con_openai(procesado)

    emocion_final = (
        emocion_openai if emocion_openai in PALABRAS_CLAVE else emocion_keywords
        if emocion_keywords != "DESCARTAR" else "DESCARTAR"
    )

    if emocion_final == "DESCARTAR":
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>"
        enviar_telegram(mensaje)
        return {"status": "ok", "emocion": "DESCARTAR"}, 200

    guion = generar_guion_emocional(procesado, emocion_final)
    formato = sugerir_formato(emocion_final)

    mensaje = f"""
✅ <b>NOTICIA ACEPTADA</b>
<b>Emoción:</b> {emocion_final}
<b>Formato sugerido:</b> {formato}

<b>Guion sugerido:</b>
{guion}

<b>Fuente:</b> {texto}
    """.strip()

    enviar_telegram(mensaje)
    return {"status": "ok", "emocion": emocion_final}, 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
