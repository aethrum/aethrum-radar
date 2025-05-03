import os
from flask import Flask, request
from telegram import Bot, Update
from telegram.ext import Dispatcher, MessageHandler, Filters

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

app = Flask(__name__)

dispatcher = Dispatcher(bot=bot, update_queue=None, workers=0, use_context=True)

def filter_message(update: Update, context):
    text = update.message.text
    if "Nature" in text or "Science" in text:
        if any(word in text.lower() for word in ["descubrimiento", "increíble", "cura", "impactante", "esperanza"]):
            update.message.reply_text("Está verificada y tiene emoción. Evaluando…")
        else:
            update.message.reply_text("Noticia sin emoción fuerte. Ignorada.")
    else:
        update.message.reply_text("Fuente no verificada. Ignorada.")

dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, filter_message))

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK", 200

@app.route("/", methods=["GET"])
def index():
    return "Bot funcionando", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
