import os
import csv
import logging
from datetime import datetime
from collections import Counter
from flask import Flask, request, jsonify
import requests

# Configuración básica
logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Cargar variables de entorno
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    raise EnvironmentError("Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID")

# Función para enviar mensajes a Telegram
def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Telegram error: {e}")

# Ruta principal que recibe todo
@app.route("/", methods=["POST"])
def root_webhook():
    data = request.get_json()

    # Este es el FIX CRÍTICO:
    message = data.get("message", {}).get("text", "").strip().lower()

    if message == "/resumen":
        try:
            with open("registros.csv", "r") as f:
                rows = [row for row in csv.reader(f)]

            if not rows:
                send_to_telegram("No hay registros aún.")
                return jsonify({"status": "ok", "message": "No data"})

            total = len(rows)
            emociones = [row[1] for row in rows if len(row) > 1]
            conteo = Counter(emociones)
            top3 = conteo.most_common(3)

            resumen = f"<b>#Resumen Diario</b>\nTotal emociones: {total}\n"
            for emo, cant in top3:
                porcentaje = round((cant / total) * 100, 1)
                resumen += f"- {emo}: {cant} ({porcentaje}%)\n"

            send_to_telegram(resumen)
            return jsonify({"status": "ok", "resumen": resumen})
        except Exception as e:
            logging.error(f"Resumen error: {e}")
            send_to_telegram("Error generando el resumen.")
            return jsonify({"status": "error", "message": str(e)})

    return jsonify({"status": "ok"})

# Puerto para Render u otros servicios
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
