import os
import requests
from telegram import Bot, Update
from telegram.ext import Updater, MessageHandler, Filters, CallbackContext

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

def filter_message(update: Update, context: CallbackContext):
    text = update.message.text
    if "Nature" in text or "Science" in text or "NASA" in text:
        if any(word in text.lower() for word in ["descubren", "activan", "revelan", "impactante", "neuronas", "emocional", "milagro", "inesperado"]):
            update.message.reply_text("Esta noticia tiene potencial AETHRUM. Revisando...")
        else:
            update.message.reply_text("Noticia sin emoción fuerte. Ignorada.")
    else:
        update.message.reply_text("Fuente no verificada. Ignorada.")

def main():
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, filter_message))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
