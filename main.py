from flask import Flask, request, jsonify
import os
import logging

app = Flask(__name__)

# Logging claro en consola para Render
logging.basicConfig(level=logging.INFO)

# Home test
@app.route('/', methods=['GET'])
def index():
    return 'AETHRUM RADAR ACTIVO', 200

# Webhook de IFTTT
@app.route('/evaluar', methods=['POST'])
def evaluar():
    try:
        # Validar que venga JSON
        if not request.is_json:
            logging.warning("Solicitud sin JSON válida")
            return jsonify({"error": "Contenido no es JSON"}), 400

        data = request.get_json(force=True)
        mensaje = data.get("message", "").strip()

        logging.info(f"Mensaje recibido: {mensaje}")

        if not mensaje:
            logging.warning("Mensaje vacío o malformado")
            return jsonify({"respuesta": "Mensaje vacío. Ignorado."}), 400

        # Diccionario de palabras emocionales
        palabras_clave = [
            "cura", "descubren", "asombroso", "impactante", "milagro", "niños",
            "oxitocina", "dopamina", "inesperado", "jamás visto", "revolucionario",
            "vida", "increíble", "impresionante", "emocionante", "humanidad", "salvó"
        ]

        if any(palabra in mensaje.lower() for palabra in palabras_clave):
            respuesta = "¡Noticia con emoción fuerte detectada!"
        else:
            respuesta = "Noticia sin emoción fuerte. Ignorada."

        logging.info(f"Respuesta enviada: {respuesta}")
        return jsonify({"respuesta": respuesta}), 200

    except Exception as e:
        logging.error(f"Error en evaluar: {str(e)}")
        return jsonify({"error": "Error interno en el servidor"}), 500

# Para correr en local (útil para testing)
if __name__ == '__main__':
    puerto = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=puerto)
