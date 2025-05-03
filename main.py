from flask import Flask, request, jsonify
import requests
import os
from bs4 import BeautifulSoup
import openai

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

MEMORIA = {}

PALABRAS_CLAVE = {
    "dopamina": ["descubre", "nuevo", "revolucionario", "premio", "meta"],
    "oxitocina": ["ayuda", "solidaridad", "amor", "abrazo", "rescate"],
    "serotonina": ["logro", "calma", "tranquilidad", "serenidad", "balance"],
    "asombro": ["inesperado", "misterioso", "antiguo", "gigante", "colosal"],
    "adrenalina": ["urgente", "peligro", "impacto", "explosión", "fuga"],
    "feniletilamina": ["enamorado", "mariposas", "cita", "romance", "pasión"],
    "norepinefrina": ["alerta", "estrés", "respuesta", "amenaza", "tensión"],
    "anandamida": ["placer", "relajación", "fluidez", "libertad", "fluir"],
    "neuroplasticidad": ["entrenamiento", "hábitos", "aprendizaje", "conexiones", "neuronas"]
}

EMOJIS = {
    "dopamina": "⚡️", "oxitocina": "❤️", "serotonina": "🌿", "asombro": "🌌",
    "adrenalina": "🔥", "feniletilamina": "💘", "norepinefrina": "🚨",
    "anandamida": "☁️", "neuroplasticidad": "🧠"
}

HASHTAGS = {
    "dopamina": "#motivación #descubrimiento", "oxitocina": "#empatía #solidaridad",
    "serotonina": "#bienestar #tranquilidad", "asombro": "#sorprendente #misterio",
    "adrenalina": "#impacto #urgente", "feniletilamina": "#romance #emociones",
    "norepinefrina": "#alerta #tensión", "anandamida": "#relax #fluidez",
    "neuroplasticidad": "#aprendizaje #cerebro"
}

FORMATO_SUGERIDO = {
    "dopamina": "Reel narrativo con ritmo rápido",
    "oxitocina": "Video con voz cálida y subtítulos grandes",
    "serotonina": "Carrusel estático con frases positivas",
    "asombro": "Visual extremo + narración intrigante",
    "adrenalina": "Video tipo alerta con sonido fuerte",
    "feniletilamina": "Clip nostálgico o poético",
    "norepinefrina": "Advertencia visual de tema tenso",
    "anandamida": "Animación lenta con música suave",
    "neuroplasticidad": "Carrusel educativo con tips"
}

def extraer_texto_desde_url(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        texto = " ".join([p.get_text() for p in soup.find_all("p")])
        return texto.strip()[:3000]
    except Exception as e:
        return f"Error al extraer texto: {e}"

def evaluar_emocion(texto):
    texto = texto.lower()
    emociones = []
    for emocion, palabras in PALABRAS_CLAVE.items():
        if any(f" {p} " in f" {texto} " for p in palabras):
            emociones.append(emocion)
    return emociones

def generar_contenido_viral(texto, emociones):
    prompt = f"""Actúa como creador de contenido viral para redes. Emociones detectadas: {', '.join(emociones)}.
    Texto base: {texto}

    Genera:
    1. Un título corto y emocional (máx 10 palabras)
    2. Un subtítulo atractivo y emocional
    3. Una pregunta final que invite a comentar o guardar

    Solo da el contenido sin explicar nada.
    """
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )
    return res.choices[0].message.content.strip()

def analizar_con_openai(texto):
    prompt = f"""Evalúa si este texto tiene potencial emocional para contenido viral. Di si genera dopamina, oxitocina, serotonina o asombro. Si no sirve, explica por qué. Sé directo.

Texto:
{texto}
"""
    res = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    return res.choices[0].message.content.strip()

def enviar_telegram(mensaje, boton=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    if boton:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "🔁 Generar otra versión", "callback_data": "regenerar"}]]
        }
    requests.post(url, json=payload)

@app.route("/", methods=["POST"])
def recibir():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": False, "error": "No message"})

    entrada = data["message"]
    if entrada.startswith("http"):
        texto = extraer_texto_desde_url(entrada)
    else:
        texto = entrada

    if texto.startswith("Error"):
        enviar_telegram(f"❌ <b>ERROR</b>
{texto}")
        return jsonify({"ok": False})

    emociones = evaluar_emocion(texto)
    gpt_result = analizar_con_openai(texto)

    if not emociones and "no" in gpt_result.lower():
        MEMORIA["último"] = {"texto": texto, "emociones": [], "modo": "reparar"}
        enviar_telegram(f"❌ <b>DESCARTADA</b>
{gpt_result}

{entrada}", boton=True)
        return jsonify({"ok": True})

    MEMORIA["último"] = {"texto": texto, "emociones": emociones, "modo": "regenerar"}

    resumen = "\n".join([f"{EMOJIS.get(e,'')} <b>{e.upper()}</b>" for e in emociones])
    formato = FORMATO_SUGERIDO.get(emociones[0], "Formato no definido") if emociones else "No detectado"
    hashtags = " ".join([HASHTAGS[e] for e in emociones if e in HASHTAGS])
    viral = generar_contenido_viral(texto, emociones)

    mensaje = f"✅ <b>ACEPTADA</b>

<b>Emociones:</b>
{resumen}

<b>Formato sugerido:</b> {formato}
<b>Hashtags:</b> {hashtags}

{viral}"
    enviar_telegram(mensaje, boton=True)
    return jsonify({"ok": True})

@app.route("/callback", methods=["POST"])
def callback():
    data = request.get_json()
    if not data or "callback_query" not in data:
        return jsonify({"ok": False})
    query = data["callback_query"]
    if query.get("data") != "regenerar":
        return jsonify({"ok": False})

    memo = MEMORIA.get("último", {})
    texto = memo.get("texto", "")
    emociones = memo.get("emociones", [])

    if not texto:
        enviar_telegram("⚠️ No hay contenido anterior para regenerar.")
        return jsonify({"ok": False})

    nuevo = generar_contenido_viral(texto, emociones)
    enviar_telegram(f"🔁 <b>Versión regenerada:</b>

{nuevo}", boton=True)
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
