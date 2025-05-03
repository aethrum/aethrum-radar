import logging
import datetime
import re
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- CONFIGURACIÓN DEL BOT ---
TOKEN = '7124925219:AAHxbx64BtjzFewOZF4L1BlKyxMg6ZcODz0'
CHANNEL_ID = '@CuriosidadesRadar'

# --- SETUP ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
bot = Bot(token=TOKEN)

# --- LISTAS DE PALABRAS CLAVE POR EMOCIÓN ---
dopamina_keywords = ['descubren', 'nuevo', 'récord', 'avance', 'increíble', 'impactante', 'milagro', 'asombroso', 'inesperado', 'primera vez', 'potente', 'tecnología', 'inteligencia', 'energia', 'futuro', 'bio']
oxitocina_keywords = ['bebé', 'abrazo', 'rescate', 'ayuda', 'humanidad', 'amor', 'solidaridad', 'familia', 'perro', 'niño', 'vida', 'madre', 'padre', 'voluntarios', 'emoción']
serotonina_keywords = ['felicidad', 'relajación', 'paz', 'logro', 'sabiduría', 'aprendizaje', 'bienestar', 'calma', 'sueño', 'crecimiento', 'armonía', 'mente', 'psicología']
asombro_keywords = ['universo', 'galaxia', 'espacio', 'fósil', 'caverna', 'océano', 'civilización', 'dinosaurio', 'extraterrestre', 'cueva', 'antártida', 'planeta', 'hielo', 'arqueología', 'historia']

# --- FUNCIONES CLAVE ---

def detectar_emocion_y_palabras(mensaje):
    mensaje_lower = mensaje.lower()
    resultado = {'dopamina': [], 'oxitocina': [], 'serotonina': [], 'asombro': []}

    for palabra in dopamina_keywords:
        if palabra in mensaje_lower:
            resultado['dopamina'].append(palabra)

    for palabra in oxitocina_keywords:
        if palabra in mensaje_lower:
            resultado['oxitocina'].append(palabra)

    for palabra in serotonina_keywords:
        if palabra in mensaje_lower:
            resultado['serotonina'].append(palabra)

    for palabra in asombro_keywords:
        if palabra in mensaje_lower:
            resultado['asombro'].append(palabra)

    return resultado

def calcular_puntaje(resultado):
    pesos = {'dopamina': 1.2, 'oxitocina': 1.5, 'serotonina': 1.1, 'asombro': 1.4}
    total = 0
    detalle = {}

    for emocion, palabras in resultado.items():
        score = len(palabras) * pesos[emocion]
        total += score
        detalle[emocion] = round(score, 2)

    max_emocion = max(detalle, key=detalle.get)
    porcentaje = min(100, int((total / 8) * 20))  # normalizamos
    return porcentaje, max_emocion, detalle

def extraer_fuente(texto):
    match = re.search(r'https?://([^/\s]+)', texto)
    return match.group(1) if match else 'desconocida'

def generar_respuesta(mensaje):
    emociones = detectar_emocion_y_palabras(mensaje)
    porcentaje, emocion_dominante, detalle = calcular_puntaje(emociones)
    fuente = extraer_fuente(mensaje)
    ahora = datetime.datetime.now().strftime("%d/%m/%Y - %I:%M %p")

    if porcentaje >= 90:
        clasificacion = "✅ Publicar VIDEO de inmediato"
    elif porcentaje >= 60:
        clasificacion = "🟡 Publicar como historia"
    else:
        clasificacion = "🔘 Archivar, poco impacto"

    respuesta = f"""
🧠 Noticia recibida:
{mensaje}

🧪 Emoción dominante: *{emocion_dominante.capitalize()}* ({porcentaje}%)
Palabras clave encontradas: {', '.join(emociones[emocion_dominante]) or 'ninguna'}

Emociones detectadas:
• Dopamina: {detalle['dopamina']}
• Oxitocina: {detalle['oxitocina']}
• Serotonina: {detalle['serotonina']}
• Asombro: {detalle['asombro']}

🕒 Fecha: {ahora}
🌐 Fuente: {fuente}

🎯 Clasificación AETHRUM:
{clasificacion}
"""
    return respuesta

# --- HANDLER ---
def manejar_mensaje(update: Update, context: CallbackContext):
    texto = update.message.text
    respuesta = generar_respuesta(texto)
    context.bot.send_message(chat_id=CHANNEL_ID, text=respuesta, parse_mode='Markdown')

def iniciar_bot():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, manejar_mensaje))
    updater.start_polling()
    updater.idle()

# --- INICIO ---
if __name__ == '__main__':
    iniciar_bot()
