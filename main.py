import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)
app = Flask(__name__)

# Dispatcher global
dispatcher = Dispatcher(bot=bot, update_queue=None, workers=0, use_context=True)

# Filtro de mensajes
def filter_message(update: Update, context):
    text = update.message.text
    if "Nature" in text or "Science" in text:
        if any(word in text.lower() for word in ["amor", "asombro", "milagro", "misterio", "madre", "niño", "cura", "cerebro"]):
            update.message.reply_text("Esta noticia será analizada.")
        else:
            update.message.reply_text("Noticia sin emoción fuerte. Ignorada.")
    else:
        update.message.reply_text("Fuente no verificada. Ignorada.")

# Agregar manejador
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, filter_message))

# Webhook para recibir mensajes de Telegram
@app.route(f'/{TELEGRAM_TOKEN}', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok', 200

# Ruta de test opcional
@app.route('/', methods=['GET'])
def index():
    return 'Bot AETHRUM activo.', 200

# Activar webhook al iniciar
if __name__ == '__main__':
    bot.set_webhook(f"https://aethrum-radar.onrender.com/{TELEGRAM_TOKEN}")
    app.run(host='0.0.0.0', port=10000)
