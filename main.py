from flask import Flask, request, jsonify
import requests
import os
import openai

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

def evaluar_emocion(texto):
    texto = texto.lower()
    emociones_detectadas = []
    for emocion, palabras in PALABRAS_CLAVE.items():
        if any(f" {palabra} " in f" {texto} " for palabra in palabras):
            emociones_detectadas.append(emocion)
    return emociones_detectadas

def evaluar_con_openai(texto):
    prompt = (
        "Evalúa si este texto tiene potencial emocional para contenido viral. "
        "Analiza si genera dopamina, oxitocina, serotonina o asombro. "
        f"Texto: {texto}\n\nResponde con una de estas opciones:\n"
        "- ALTO IMPACTO EMOCIONAL\n- IMPACTO MEDIO\n- DESCARTAR\n"
        "Y da una breve razón."
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return response['choices'][0]['message']['content']
    except Exception as e:
        return f"Error al evaluar con OpenAI: {str(e)}"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensaje,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print("Error al enviar mensaje:", e)

@app.route("/", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": False, "error": "No se encontró el campo 'message'"})

    texto = data["message"]
    emociones = evaluar_emocion(texto)

    if emociones:
        openai_eval = evaluar_con_openai(texto)
        mensaje = f"✅ <b>NOTICIA ACEPTADA</b>\n\nEmociones detectadas: {', '.join(emociones)}\n\nEvaluación avanzada:\n{openai_eval}"
    else:
        openai_eval = evaluar_con_openai(texto)
        mensaje = f"❌ <b>NOTICIA DESCARTADA</b>\n\nNo se detectaron emociones clave.\n\nEvaluación avanzada:\n{openai_eval}\n\nTexto recibido:\n\n{texto}"

    enviar_telegram(mensaje)
    return jsonify({"ok": True, "emociones": emociones})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
