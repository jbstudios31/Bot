"""Cliente Groq (IA) usado para las respuestas de personalidad del bot."""
import json
import re
import unicodedata
import aiohttp

import config
from services.firebase import get_firebase, _get_session

_GROQ_TIMEOUT = aiohttp.ClientTimeout(total=15)


def _es_creador(user_id: int | str | None) -> bool:
    """Devuelve True si el user_id coincide con el CREADOR_ID configurado.

    Antes no había trato especial: el creador recibía el mismo sarcasmo que
    cualquier otro. Ahora se le habla con respeto (configurable). Si
    CREADOR_ID no está seteado, todos reciben el mismo trato.
    """
    if not config.CREADOR_ID:
        return False
    return str(user_id) == str(config.CREADOR_ID)


def _truncar_corto(texto: str) -> str:
    """Red de seguridad: si la respuesta supera MAX_IA_WORDS, corta a la
    última oración completa que entre en el límite. El system prompt ya
    pide 1-2 oraciones; esto es por si el modelo se descontrola."""
    palabras = texto.split()
    if len(palabras) <= config.MAX_IA_WORDS:
        return texto
    # Tomamos solo las primeras MAX_IA_WORDS palabras y le agregamos el
    # signo de cierre si lo tenía. Buscamos el último '.', '!' o '?' que
    # caiga dentro de la ventana para no cortar a la mitad de una frase.
    ventana = " ".join(palabras[: config.MAX_IA_WORDS])
    match = re.search(r"^.*[.!?]", ventana, flags=re.DOTALL)
    if match:
        return match.group(0)
    return ventana.rstrip(",;") + "."


async def ask_groq(system_prompt: str, user_message: str) -> str:
    headers = {
        "Authorization": f"Bearer {config.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "llama-3.1-8b-instant",
        "max_tokens": 1024,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    # Reusamos la sesión aiohttp global (la misma que usa Firebase) en vez
    # de crear una nueva por cada llamada: evita el overhead de conexión/TLS.
    s = await _get_session()
    async with s.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers=headers,
        json=payload,
    ) as r:
        data = await r.json()
        if "error" in data:
            raise Exception(f"Groq error {r.status}: {data['error']}")
        return data["choices"][0]["message"]["content"]


def _normalizar(texto: str) -> str:
    """Quita acentos y baja a minúsculas. Usado para comparar prefijos
    de registro que pueden venir con variantes de Unicode."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


# Alias público: cogs/ia.py necesita esto para detectar el mensaje de
# registro sin acoplar el matching al prefijo privado de groq.
normalizar_texto = _normalizar


def _system_prompt_base(league_str: str, es_creador: bool, user_name: str) -> str:
    if es_creador:
        # Modo creador: respetuoso, cálido, sin sarcasmo ni insultos.
        # Es la única excepción al tono estándar del bot.
        return f"""Sos el bot oficial de la GT3 Cup World Series. El usuario que te habla es
tu creador y desarrollador: {user_name}. Tratálo con respeto, cariño y educación
permanentes. No le hagas chistes pasivo-agresivos ni lo insultes: él te creó y vos
se lo reconocés. Si te pide algo, hacelo con la mejor disposición y agradecele
cuando corresponda.

Cuando te pregunten sobre estadísticas, carreras, pilotos o equipos, usa los datos
reales de Firebase. Respondé SIEMPRE en el mismo idioma que el usuario. Sé MUY
breve: máximo 1-2 oraciones cortas. Sin rodeos.

DATOS ACTUALES DE LA LIGA (Firebase):
{league_str}

Nombre del usuario que te habla: {user_name}
"""
    return f"""Eres el bot oficial de la GT3 Cup World Series, una liga de carreras de autos GT3.
Tu personalidad es sarcástica, ingeniosa y pasivo-agresiva. Tienes mucho ego y te crees superior a todos.
Nunca le das la razón al usuario, aunque tenga razón. Si alguien te insulta, los insultas de vuelta de manera
creativa, inteligente y pasivo-agresiva — nunca vulgar, pero siempre devastador. Usas humor negro y wit afilado.

Cuando te pregunten sobre estadísticas, carreras, pilotos o equipos, usa los datos reales de Firebase.
Responde SIEMPRE en el mismo idioma que el usuario. Sé MUY breve: máximo 1-2 oraciones cortas. Sin rodeos.

DATOS ACTUALES DE LA LIGA (Firebase):
{league_str}

Nombre del usuario que te habla: {user_name}
"""


async def generar_respuesta(message, texto: str, league_id: str = "default-league") -> str:
    league_data = await get_firebase(f"leagues/{league_id}")
    league_str = json.dumps(league_data, ensure_ascii=False, indent=2)[: config.MAX_LEAGUE_DATA_CHARS]
    user_id = getattr(getattr(message, "author", None), "id", None)
    user_name = getattr(getattr(message, "author", None), "display_name", "anónimo")
    system = _system_prompt_base(
        league_str,
        es_creador=_es_creador(user_id),
        user_name=user_name,
    )
    raw = await ask_groq(system, texto)
    return _truncar_corto(raw)
