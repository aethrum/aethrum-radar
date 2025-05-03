from flask import Flask, request, jsonify
import requests
import os
import json
import openai
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

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
    "dopamina": "#inspiración #motivación", "oxitocina": "#conexiónhumana #solidaridad",
    "serotonina": "#bienestar #equilibrio", "asombro": "#wow #descubrimiento",
    "adrenalina": "#impactante #urgente", "feniletilamina": "#romance #emociones",
    "norepinefrina": "#alerta #tensión", "anandamida": "#relax #libertad",
    "neuroplasticidad": "#aprendizaje #hábitos"
}

FORMATO_SUGERIDO = {
    "dopamina": "Reel dinámico con texto en pantalla",
    "oxitocina": "Historia visual con narración cálida",
    "serotonina": "Post tipo carrusel con frases relajantes",
    "asombro": "Video de descubrimiento con efectos visuales",
    "adrenalina": "Video urgente tipo breaking news",
    "feniletilamina": "Reel romántico o nostálgico",
    "norepinefrina": "Alerta visual con sonido dramático",
    "anandamida": "Video lento y fluido, música suave",
    "neuroplasticidad": "Carrusel educativo con tips visuales"
}

regeneraciones = {}

def analizar_emocion_con_gpt(texto):
    prompt = (
        "Evalúa si este texto puede tener potencial emocional para contenido viral:

"
        f"{texto}

"
        "Responde solo con 'sí' o 'no'. No expliques nada."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0
    )
    decision = response.choices[0].message.content.strip().lower()
    return "sí" in decision

def reescribir_con_emocion(texto):
    prompt = (
        "Reescribe este texto de forma emocional, viral, humana y optimista, como si fueras un creador de contenido emocional para TikTok:

"
        f"{texto}"
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.85
    )
    return response.choices[0].message.content.strip()

def extraer_texto_de_link(link):
    prompt = (
        f"Lee y resume emocionalmente el contenido de esta página web:
{link}

"
        "Extrae solo el contenido importante como si fueras a usarlo en un video de TikTok."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7
    )
    return response.choices[0].message.content.strip()

def evaluar_emocion_detallado(texto):
    texto = texto.lower()
    conteo = {e: sum(f" {p} " in f" {texto} " for p in PALABRAS_CLAVE[e]) for e in PALABRAS_CLAVE}
    emociones_detectadas = [e for e, c in conteo.items() if c > 0]
    return emociones_detectadas, conteo

def generar_resumen_emocional(emociones, conteo):
    return "".join([f"{EMOJIS[e]} <b>{e.upper()}</b> — Intensidad: {'ALTA' if conteo[e]>=3 else 'MEDIA' if conteo[e]==2 else 'BAJA'}\n" for e in emociones])

def sugerencia_formato(emociones, conteo):
    if not emociones: return "No aplicable"
    dominante = sorted(emociones, key=lambda e: conteo[e], reverse=True)[0]
    return FORMATO_SUGERIDO.get(dominante, "Formato no definido")

def hashtags_recomendados(emociones):
    return " ".join([HASHTAGS[e] for e in emociones if e in HASHTAGS])

def generar_contenido_viral(texto, emociones):
    prompt = (
        "Actúa como creador profesional de contenido viral en redes.\n"
        f"Texto recibido: {texto}\n"
        f"Emociones detectadas: {', '.join(emociones)}\n\n"
        "Genera:\n"
        "1. Un título emocional fuerte de máximo 10 palabras.\n"
        "2. Un subtítulo que cause asombro, empatía o curiosidad.\n"
        "3. Una pregunta final emocional que invite a comentar o guardar.\n\n"
        "Solo responde con el contenido, sin explicaciones."
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )
    return response.choices[0].message.content.strip()

def enviar_mensaje_telegram(mensaje, buttons=False, tipo="regenera"):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "💫 Reescribir con emoción" if tipo=="reparar" else "🔁 Generar otra versión", "callback_data": tipo}]]
        }
    try:
        requests.post(url, json=payload).raise_for_status()
    except Exception as e:
        print("Error al enviar mensaje a Telegram:", e)

@app.route("/", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No se recibió ningún dato"})

    texto_original = ""
    if "link" in data:
        texto_original = extraer_texto_de_link(data["link"])
    else:
        texto_original = f"{data.get('title','')} {data.get('description','')} {data.get('message','')}"

    if not analizar_emocion_con_gpt(texto_original):
        regeneraciones["último"] = {"texto": texto_original, "intentos": 0, "modo": "reparar"}
        enviar_mensaje_telegram(
            f"❌ <b>NOTICIA DESCARTADA</b>\nGPT no detectó emociones suficientes para contenido viral.\n"
            "<b>Motivo:</b> Texto percibido como frío, académico o poco emocional.\n\n"
            f"<b>Texto recibido:</b>\n{texto_original[:1000]}",
            buttons=True, tipo="reparar"
        )
        return jsonify({"ok": True, "descartado_por_gpt": True})

    emociones, conteo = evaluar_emocion_detallado(texto_original)
    resumen = generar_resumen_emocional(emociones, conteo)
    formato = sugerencia_formato(emociones, conteo)
    hashtags = hashtags_recomendados(emociones)
    contenido_creado = generar_contenido_viral(texto_original, emociones)
    mensaje = (
        f"✅ <b>NOTICIA ACEPTADA</b>\n\n"
        f"<b>Emociones detectadas:</b>\n{resumen}\n"
        f"<b>Formato sugerido:</b> {formato}\n"
        f"<b>Hashtags:</b> {hashtags}\n\n"
        f"{contenido_creado}\n\n"
        f"<i>Toca el botón abajo si no te gustó</i>"
    )
    regeneraciones["último"] = {"texto": texto_original, "emociones": emociones, "intentos": 1, "modo": "regenera"}
    enviar_mensaje_telegram(mensaje, buttons=True)
    return jsonify({"ok": True})

@app.route("/callback", methods=["POST"])
def procesar_callback():
    update = request.get_json()
    query = update.get("callback_query", {})
    datos = regeneraciones.get("último", {})
    if query.get("data") == "regenera" and datos.get("modo") == "regenera":
        if datos["intentos"] < 3:
            nuevo = generar_contenido_viral(datos["texto"], datos["emociones"])
            datos["intentos"] += 1
            regeneraciones["último"] = datos
            enviar_mensaje_telegram(f"🔁 <b>Versión nueva generada</b> (intento {datos['intentos']}):\n\n{nuevo}", buttons=True)
    elif query.get("data") == "reparar" and datos.get("modo") == "reparar":
        reparado = reescribir_con_emocion(datos["texto"])
        emociones, conteo = evaluar_emocion_detallado(reparado)
        if emociones:
            resumen = generar_resumen_emocional(emociones, conteo)
            formato = sugerencia_formato(emociones, conteo)
            hashtags = hashtags_recomendados(emociones)
            viral = generar_contenido_viral(reparado, emociones)
            regeneraciones["último"] = {"texto": reparado, "emociones": emociones, "intentos": 1, "modo": "regenera"}
            enviar_mensaje_telegram(
                f"✅ <b>REPARADO CON ÉXITO</b>\n\n"
                f"<b>Emociones detectadas:</b>\n{resumen}\n"
                f"<b>Formato sugerido:</b> {formato}\n"
                f"<b>Hashtags:</b> {hashtags}\n\n{viral}",
                buttons=True
            )
        else:
            enviar_mensaje_telegram("❌ Incluso reescribiendo, no se detectaron emociones suficientes.")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=False, port=5000)
