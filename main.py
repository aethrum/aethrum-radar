import os
from flask import Flask, request
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

@app.route('/evaluar', methods=['POST'])
def evaluar():
    data = request.get_json(force=True)
    print("DATA RECIBIDA:", data)
    
    mensaje = data.get("message", "").strip()
    print("MENSAJE EXTRAÍDO:", mensaje)

    if not mensaje:
        return "SIN MENSAJE", 400

    if "nature" in mensaje.lower() and any(palabra in mensaje.lower() for palabra in ["cura", "descubre", "revierte", "increíble", "impactante", "esperanza", "vida"]):
        bot.send_message(chat_id="@CuriosidadesRadar", text=f"NOTICIA ACEPTADA:\n{mensaje}")
    else:
        bot.send_message(chat_id="@CuriosidadesRadar", text="Noticia sin emoción fuerte. Ignorada.")

    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
