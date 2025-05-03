from flask import Flask, request, jsonify
import requests
import os
import json
import openai
from datetime import datetime

app = Flask(__name__)

# Variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# Diccionarios de emociones y formatos
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

def exportar_json(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta = f"registro_noticias/{timestamp}.json"
    os.makedirs("registro_noticias", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

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
    respuesta = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9
    )
    return respuesta.choices[0].message.content.strip()

def enviar_mensaje_telegram(mensaje, buttons=False):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    if buttons:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "🔁 Generar otra versión", "callback_data": "regenera"}]]
        }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        print("Error al enviar mensaje a Telegram:", e)

@app.route("/", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    if not data: return jsonify({"ok": False, "error": "No se recibió ningún dato"})

    texto = f"{data.get('title','')} {data.get('description','')} {data.get('message','')}"
    emociones, conteo = evaluar_emocion_detallado(texto)

    if emociones:
        resumen = generar_resumen_emocional(emociones, conteo)
        formato = sugerencia_formato(emociones, conteo)
        hashtags = hashtags_recomendados(emociones)
        contenido_creado = generar_contenido_viral(texto, emociones)
        mensaje = (
            f"✅ <b>NOTICIA ACEPTADA</b>\n\n"
            f"<b>Emociones detectadas:</b>\n{resumen}\n"
            f"<b>Formato sugerido:</b> {formato}\n"
            f"<b>Hashtags:</b> {hashtags}\n\n"
            f"{contenido_creado}\n\n"
            f"<i>Toca el botón abajo si no te gustó</i>"
        )
        regeneraciones["último"] = {"texto": texto, "emociones": emociones, "intentos": 1}
        enviar_mensaje_telegram(mensaje, buttons=True)
    else:
        mensaje = (
            "❌ <b>NOTICIA DESCARTADA</b>\n"
            "No se detectaron emociones clave.\n"
            f"<b>Texto recibido:</b>\n{texto or '(vacío)'}"
        )
        enviar_mensaje_telegram(mensaje)

    exportar_json({
        "entrada_original": data,
        "emociones_detectadas": emociones,
        "conteo_por_emocion": conteo
    })

    return jsonify({"ok": True, "emociones": emociones, "conteo": conteo})

@app.route("/callback", methods=["POST"])
def procesar_callback():
    update = request.get_json()
    if "callback_query" in update:
        query = update["callback_query"]
        if query["data"] == "regenera":
            datos = regeneraciones.get("último")
            if datos and datos["intentos"] < 3:
                nuevo = generar_contenido_viral(datos["texto"], datos["emociones"])
                datos["intentos"] += 1
                regeneraciones["último"] = datos
                mensaje = f"🔁 <b>Versión nueva generada</b> (intento {datos['intentos']}):\n\n{nuevo}"
                enviar_mensaje_telegram(mensaje, buttons=True)
            else:
                enviar_mensaje_telegram("❌ Límite de regeneraciones alcanzado.")
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=False, port=5000)
