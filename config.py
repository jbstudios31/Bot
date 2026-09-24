import os

TOKEN = os.environ.get("TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
PREFIX = "!"
NOMBRE_ROL = "PILOTO GT3 🚗"
CATEGORIA_REGISTRO = "🏎️ | REGISTRO"

# ID de Discord del creador del bot. Si está configurado, la IA le habla
# con respeto/cariño en vez del modo sarcástico estándar. Opcional: si no
# está, todos los usuarios reciben el mismo trato.
CREADOR_ID = os.environ.get("CREADOR_ID")

# Cantidad máxima de caracteres de datos de liga que se le pasan a Groq en
# cada prompt. Antes estaba como literal 4000 en dos lugares distintos; si
# se cambiaba había que acordarse de los dos. Centralizado acá.
MAX_LEAGUE_DATA_CHARS = 4000

# Palabras (separadas por espacio) en una respuesta de la IA. Si la respuesta
# supera este límite se trunca a la última oración completa como red de
# seguridad, además del límite que ya viene en el system prompt.
MAX_IA_WORDS = 30

# Prefijo que identifica un mensaje de registro en la categoría de registro.
# Antes era un string literal con emoji + texto exacto, lo que se rompía si
# alguien copiaba el mensaje sin el emoji o con un emoji similar. Ahora se
# matchea por prefijo normalizado.
REGISTRO_PREFIJO = "registration form"

FIREBASE_URL = "https://data-base-92efd-default-rtdb.firebaseio.com"
# Web API key del proyecto Firebase: no es secreta (la seguridad la dan las
# Firebase Rules + Auth), pero se lee de env var para no dejarla en el repo
# y poder rotarla sin tocar código.
FIREBASE_API_KEY = os.environ.get("FIREBASE_API_KEY")
FIREBASE_BOT_EMAIL = os.environ.get("FIREBASE_BOT_EMAIL")
FIREBASE_BOT_PASSWORD = os.environ.get("FIREBASE_BOT_PASSWORD")


def validar_config():
    """Falla rápido y con un mensaje claro si falta alguna env var, en vez
    de fallar más adelante con un error críptico a mitad de un comando."""
    faltantes = []
    if not TOKEN:
        faltantes.append("TOKEN")
    if not GROQ_API_KEY:
        faltantes.append("GROQ_API_KEY")
    if not FIREBASE_API_KEY:
        faltantes.append("FIREBASE_API_KEY")
    if not FIREBASE_BOT_EMAIL:
        faltantes.append("FIREBASE_BOT_EMAIL")
    if not FIREBASE_BOT_PASSWORD:
        faltantes.append("FIREBASE_BOT_PASSWORD")
    if faltantes:
        raise RuntimeError(
            "Faltan variables de entorno: " + ", ".join(faltantes) +
            ". Configuralas en Railway (Settings → Variables) antes de arrancar el bot."
        )
