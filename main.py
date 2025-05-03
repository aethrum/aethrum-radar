from flask import Flask, request, jsonify
import requests
import os
import json
from datetime import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

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
    "dopamina": "⚡️",
    "oxitocina": "❤️",
    "serotonina": "🌿",
    "asombro": "🌌",
    "adrenalina": "🔥",
    "feniletilamina": "💘",
    "norepinefrina": "🚨",
    "anandamida": "☁️",
    "neuroplasticidad": "🧠"
}

HASHTAGS = {
    "dopamina": "#inspiración #motivación",
    "oxitocina": "#conexiónhumana #solidaridad",
    "serotonina": "#bienestar #equilibrio",
    "asombro": "#wow #descubrimiento",
    "adrenalina": "#impactante #urgente",
    "feniletilamina": "#romance #emociones",
    "norepinefrina": "#alerta #tensión",
    "anandamida": "#relax #libertad",
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

def evaluar_emocion_detallado(texto):
    texto = texto.lower()
    conteo = {emocion: 0 for emocion in PALABRAS_CLAVE}
    for emocion, palabras in PALABRAS_CLAVE.items():
        conteo[emocion] = sum(f" {palabra} " in f" {texto} " for palabra in palabras)
    emociones_detectadas = [e for e, c in conteo.items() if c > 0]
    return emociones_detectadas, conteo

def generar_resumen_emocional(emociones, conteo):
    resumen = ""
    for emocion in emociones:
        intensidad = conteo[emocion]
        nivel = "ALTA" if intensidad >= 3 else "MEDIA" if intensidad == 2 else "BAJA"
        resumen += f"{EMOJIS[emocion]} <b>{emocion.upper()}</b> — Intensidad: {nivel}\n"
    return resumen

def sugerencia_formato(emociones, conteo):
    if not emociones:
        return "No aplicable"
    emociones_ordenadas = sorted(emociones, key=lambda e: conteo[e], reverse=True)
    dominante = emociones_ordenadas[0]
    return FORMATO_SUGERIDO.get(dominante, "Formato no definido")

def hashtags_recomendados(emociones):
    tags = [HASHTAGS[e] for e in emociones if e in HASHTAGS]
    return " ".join(tags)

def exportar_json(data):
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    ruta = f"registro_noticias/{timestamp}.json"
    os.makedirs("registro_noticias", exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def enviar_mensaje_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        print("Mensaje enviado correctamente a Telegram")
    except Exception as e:
        print("Error al enviar mensaje a Telegram:", e)

@app.route("/", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    if not data:
        return jsonify({"ok": False, "error": "No se recibió ningún dato"})

    texto_completo = f"{data.get('title', '')} {data.get('description', '')} {data.get('message', '')}"
    emociones, conteo = evaluar_emocion_detallado(texto_completo)

    if emociones:
        resumen = generar_resumen_emocional(emociones, conteo)
        formato = sugerencia_formato(emociones, conteo)
        hashtags = hashtags_recomendados(emociones)
        mensaje = (
            f"✅ <b>NOTICIA ACEPTADA</b>\n\n"
            f"<b>Emociones detectadas:</b>\n{resumen}\n"
            f"<b>Formato sugerido:</b> {formato}\n"
            f"<b>Hashtags:</b> {hashtags}"
        )
    else:
        mensaje = (
            "❌ <b>NOTICIA DESCARTADA</b>\n"
            "No se detectaron emociones clave.\n"
            "Agrega más impacto emocional al texto."
        )

    enviar_mensaje_telegram(mensaje)
    exportar_json({
        "entrada_original": data,
        "emociones_detectadas": emociones,
        "conteo_por_emocion": conteo,
        "mensaje_enviado": mensaje
    })

    return jsonify({"ok": True, "emociones": emociones, "conteo": conteo})

# ESTE ES EL NUEVO MAIN FINAL
if __name__ == "__main__":
    app.run(debug=False)
