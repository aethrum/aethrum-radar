import os
from flask import Flask, request
from telegram import Bot

# Token del bot desde las variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = Bot(token=TELEGRAM_TOKEN)

# Crear app Flask
app = Flask(__name__)

# Ruta para recibir mensajes desde IFTTT
@app.route('/evaluar', methods=['POST'])
def evaluar():
    data = request.get_json(force=True)
    mensaje = data.get("message", "")

    print("Mensaje recibido:", mensaje)

    # Filtro simple: verifica si contiene Nature o Science
    if "Nature" in mensaje or "Science" in mensaje:
        bot.send_message(chat_id='@Cutiosidadesradar', text=f"APROBADA: {mensaje}")
    else:
        bot.send_message(chat_id='@Cutiosidadesradar', text="Noticia sin emoción fuerte. Ignorada.")

    return "OK", 200

# Ejecutar solo Flask, sin polling
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
