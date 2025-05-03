from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

PALABRAS_CLAVE = {
    "dopamina": ["descubre", "nuevo", "revoluciona", "récord", "avance", "increíble", "inédito", "sorprendente"],
    "oxitocina": ["ayuda", "solidaridad", "amor", "rescate", "abrazo", "milagro", "familia", "esperanza"],
    "serotonina": ["logro", "calma", "tranquilidad", "paz", "gratitud", "serenidad", "bienestar"],
    "asombro": ["inesperado", "misterioso", "antiguo", "descubrimiento", "colosal", "gigante", "impresionante"]
}

def evaluar_emocion(texto):
    texto = texto.lower()
    emociones_detectadas = []
    for emocion, palabras in PALABRAS_CLAVE.items():
        if any(palabra in texto for palabra in palabras):
            emociones_detectadas.append(emocion)
    return emociones_detectadas

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
    if not data or "message" not in data:
        return jsonify({"ok": False, "error": "No se recibió ningún mensaje válido"})

    texto = data["message"]
    emociones = evaluar_emocion(texto)

    if emociones:
        resumen = f"✅ <b>NOTICIA ACEPTADA</b>\nEmociones: {', '.join(emociones)}\n\n{texto}"
    else:
        resumen = f"❌ <b>DESCARTADA</b>\nSin emociones detectadas.\n\n{texto}"

    enviar_mensaje_telegram(resumen)

    return jsonify({"ok": True, "emociones": emociones})

if __name__ == "__main__":
    app.run()
