from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

# Usa variables de entorno para proteger tu token y chat ID
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # Ej: @Cutiosidadesradar

# Diccionario de emociones con palabras clave asociadas
PALABRAS_CLAVE = {
    "dopamina": ["descubre", "nuevo", "revoluciona", "récord", "impresionante", "éxito", "avance", "primera vez"],
    "oxitocina": ["ayuda", "solidaridad", "amor", "niño", "madre", "esperanza", "cura", "salvó", "rescató"],
    "serotonina": ["logro", "calma", "tranquilidad", "bienestar", "mejoró", "equilibrio"],
    "asombro": ["inesperado", "misterioso", "antártida", "prehistórico", "fósil", "extraterrestre", "oculto"]
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
        print("Mensaje enviado correctamente a Telegram.")
    except Exception as e:
        print("Error al enviar mensaje a Telegram:", e)

@app.route("/", methods=["POST"])
def recibir_noticia():
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"ok": False, "error": "No se recibió mensaje válido"}), 400

    texto = data["message"]
    emociones = evaluar_emocion(texto)

    if emociones:
        resumen = f"✅ <b>NOTICIA ACEPTADA</b>\n<b>Emociones:</b> {', '.join(emociones)}\n\n{texto}"
    else:
        resumen = f"❌ <b>DESCARTADA</b>\nSin emoción detectable.\n\n{texto}"

    enviar_mensaje_telegram(resumen)

    return jsonify({"ok": True, "emociones": emociones}), 200

if __name__ == "__main__":
    app.run()
