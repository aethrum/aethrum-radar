import os
import datetime
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# Seguridad: cargamos tokens desde variables de entorno
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Diccionario de emociones y palabras clave
EMOCIONES = {
    "dopamina": [
        "nuevo", "descubrimiento", "récord", "histórico", "impresionante",
        "inesperado", "potente", "revoluciona", "impactante", "logro", "avanza",
        "primera vez", "jamás visto", "sorprendente"
    ],
    "oxitocina": [
        "salva vidas", "unió", "esperanza", "solidaridad", "ayudó",
        "voluntario", "niño", "mamá", "papá", "milagro", "amor",
        "familia", "rescate", "conmueve"
    ],
    "serotonina": [
        "bienestar", "tranquilidad", "felicidad", "logro personal", "relajación",
        "equilibrio", "armonía", "motivación", "superación", "crecimiento"
    ],
    "asombro": [
        "NASA", "extraterrestre", "universo", "planeta", "dimensión",
        "prehistórico", "fósil", "misterioso", "antiguo", "arqueología",
        "hallazgo", "colosal", "gigante", "nunca antes visto"
    ]
}

@app.route("/", methods=["GET"])
def index():
    return "AETHRUM está escuchando...", 200

@app.route("/evaluar", methods=["POST"])
def evaluar():
    data = request.get_json(force=True)
    raw_mensaje = data.get("message", "")
    mensaje = raw_mensaje.lower()

    emocion_detectada = None
    claves_usadas = []

    for emocion, claves in EMOCIONES.items():
        for palabra in claves:
            if palabra in mensaje:
                emocion_detectada = emocion
                claves_usadas.append(palabra)

    ahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if emocion_detectada:
        texto = (
            f"**¡Noticia relevante!**\n"
            f"• Emoción: {emocion_detectada.upper()}\n"
            f"• Palabras clave: {', '.join(set(claves_usadas))}\n"
            f"• Fecha: {ahora}\n"
            f"• Contenido:\n{raw_mensaje}"
        )
    else:
        texto = (
            f"Noticia sin emoción fuerte. Ignorada.\n"
            f"• Fecha: {ahora}\n"
            f"• Contenido:\n{raw_mensaje}"
        )

    enviar_a_telegram(texto)
    return jsonify({"ok": True, "evaluada": True}), 200

def enviar_a_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    response = requests.post(url, json={
        "chat_id": CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    })
    return response.status_code == 200

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
