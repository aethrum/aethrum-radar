from flask import Flask, request, jsonify
import os
import logging
import requests
from bs4 import BeautifulSoup
import openai

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

PALABRAS_CLAVE = {
    "dopamina": [
        "descubrimiento", "logro", "avance", "premio", "innovación", "éxito", "mejora", "novedad", "triunfo", "impacto",
        "impulso", "motivación", "reto", "reto superado", "cambio", "reto alcanzado", "productividad", "habilidad",
        "hack", "inteligencia", "curioso", "ciencia", "avance médico", "tecnología", "meta", "logrado", "beneficio",
        "desarrollo", "potencial", "progreso", "superación", "determinación", "proyecto", "solución", "crecimiento",
        "reinvención", "ganancia", "mejorado", "alto rendimiento", "record", "eficiencia", "autonomía", "adrenalina buena",
        "biohacking", "excelencia", "objetivo", "conquista", "felicidad"
    ],
    "oxitocina": [
        "abrazo", "cariño", "amistad", "apoyo", "conexión", "compasión", "empatía", "solidaridad", "amor", "beso",
        "confianza", "ternura", "acompañamiento", "generosidad", "gratitud", "ayuda", "equipo", "familia", "perdón",
        "unión", "escucha", "reencuentro", "protección", "compañía", "cooperación", "abrazar", "gesto", "consuelo",
        "aprecio", "rescate", "socorro", "entrega", "humanidad", "lealtad", "respeto", "sensibilidad", "comprensión",
        "solidario", "madre", "padre", "hermano", "infancia", "mascota", "gesto noble", "tiempo juntos", "pertenencia",
        "grupo", "tribu", "alianza"
    ],
    "serotonina": [
        "calma", "relajación", "tranquilidad", "equilibrio", "bienestar", "serenidad", "armonía", "descanso", "rutina sana",
        "hábitos", "meditación", "pausa", "naturaleza", "gratitud", "sol", "día perfecto", "aire libre", "sonrisa", "lectura",
        "orden", "claridad", "autocontrol", "paz", "mindfulness", "silencio", "fluidez", "salud emocional", "autocuidado",
        "estabilidad", "relajado", "gratificante", "estímulo positivo", "sin prisa", "control", "respiración", "oxígeno",
        "paseo", "energía positiva", "ritmo", "balance", "plenitud", "satisfacción", "descubrimiento suave", "sabiduría",
        "dormir bien", "vida lenta", "momentos simples", "claridad mental", "felicidad simple"
    ],
    "asombro": [
        "increíble", "inusual", "gigante", "descubrimiento", "colosal", "inesperado", "impactante", "sorprendente", "misterioso",
        "antiguo", "prehistórico", "universo", "fósil", "esqueleto", "momento exacto", "maravilla", "único", "extraño",
        "impresionante", "marciano", "cosmos", "glaciar", "iceberg", "caverna", "milagro", "aurora", "ovni", "planeta nuevo",
        "anomalía", "genialidad", "talento fuera de serie", "prodigio", "código antiguo", "inteligencia animal", "fenómeno natural",
        "inexplicable", "arqueología", "bajo tierra", "cambio radical", "física cuántica", "alienígena", "galaxia", "súper",
        "cometa", "telescopio", "nasa", "inteligencia del pasado", "exploración", "viaje al centro"
    ],
    "adrenalina": [
        "peligro", "acción", "salto", "vértigo", "riesgo", "velocidad", "urgente", "rescate", "límite", "escape",
        "huida", "correr", "incendio", "impacto", "ataque", "tensión", "sismo", "inundación", "desafío", "combate",
        "grito", "adrenalina pura", "explosión", "drama", "tiempo límite", "intenso", "reacción", "salvarse", "caída",
        "intensidad", "búsqueda extrema", "rastreo", "al límite", "situación crítica", "shock", "detonante", "reacción veloz",
        "alta energía", "acelerado", "temblor", "alarma", "cápsula del tiempo", "tope", "estrés útil", "impulso",
        "instinto", "supervivencia", "sobresalto", "persecución"
    ]
}
def detectar_emocion(texto):
    texto = texto.lower()
    conteo = {emocion: sum(texto.count(p) for p in palabras) for emocion, palabras in EMOCIONES.items()}
    emocion_dominante = max(conteo, key=conteo.get)
    if conteo[emocion_dominante] == 0:
        return "ninguna"
    return emocion_dominante

# Generar guion viral usando OpenAI GPT
def generar_guion_openai(texto, emocion):
    prompt = f"""
Texto: {texto}
Emoción dominante: {emocion.upper()}
Crea un guion viral para TikTok de 17 segundos, dividido en 5 bloques, con título emocional, CTA fuerte, y formato visual sugerido.
Responde en este formato exacto:
Título:
Guion:
CTA:
Formato:
    """
    try:
        respuesta = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "Eres un experto en marketing viral emocional."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=600
        )
        return respuesta.choices[0].message["content"]
    except Exception as e:
        return f"Error al generar guion: {e}"

# Enviar el contenido final a Telegram
def enviar_a_telegram(mensaje):
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=mensaje, parse_mode='HTML')
    except Exception as e:
        logging.error(f"Error enviando a Telegram: {e}")

# Webhook principal del sistema
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        texto = data.get("texto") or data.get("url") or ""

        if texto.startswith("http"):
            html = requests.get(texto, timeout=10).text
            soup = BeautifulSoup(html, "html.parser")
            texto = soup.get_text(separator=" ", strip=True)

        if len(texto) < 50:
            return jsonify({"error": "Texto demasiado corto"}), 400

        emocion = detectar_emocion(texto)
        if emocion == "ninguna":
            return jsonify({"status": "descartado", "razon": "sin emoción dominante"})

        guion = generar_guion_openai(texto, emocion)
        fecha = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
        mensaje = f"<b>AETHRUM</b>\n\n<b>Emoción:</b> {emocion.upper()}\n<b>Fecha:</b> {fecha}\n\n{guion}"

        enviar_a_telegram(mensaje)
        return jsonify({"status": "ok", "emocion": emocion, "guion": guion})

    except Exception as e:
        logging.error(f"Error en webhook: {e}")
        return jsonify({"error": str(e)}), 500
        if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
