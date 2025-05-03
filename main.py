import os
import requests
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

def filter_message(update: Update, context):
    text = update.message.text
    if "Nature" in text or "Science" in text:
        if any(word in text.lower() for word in ["cura", "descubrimiento", "impactante", "esperanza"]):
            update.message.reply_text("Esta noticia se queda.")
        else:
            update.message.reply_text("Noticia sin emoción fuerte. Ignorada.")
    else:
        update.message.reply_text("Fuente no verificada. Ignorada.")

@app.route('/evaluar', methods=['POST'])
def evaluar():
    data = request.get_json(force=True)
    print("DATA COMPLETA RECIBIDA:", data)

    mensaje = data.get("message", "")
    print("MENSAJE EXTRAÍDO:", mensaje)

    bot.send_message(chat_id="@Curiosidadesradar", text=mensaje)  # <--- AGREGA ESTA LÍNEA

    return "OK", 200

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, filter_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
    app.run(host='0.0.0.0', port=10000)
