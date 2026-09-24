"""Auto-asignación de rol al registrarse + respuestas de IA al mencionar/responder al bot."""
import logging

import discord
from discord.ext import commands

import config
from services.groq import generar_respuesta, normalizar_texto
from utils.standings import league_id_for

logger = logging.getLogger(__name__)


def _es_mensaje_de_registro(message: discord.Message) -> bool:
    """Detecta si un mensaje es un formulario de registro.

    Antes se matcheaba con un string literal exacto (emoji + texto codificado
    en símbolos Unicode fancy). Si alguien copiaba el mensaje sin el emoji o
    lo pegaba en otro cliente que rendere distinto, la asignación de rol se
    rompía silenciosamente. Ahora se matchea por prefijo normalizado: si el
    mensaje empieza con "registration form" (con o sin emoji, con o sin
    acentos, mayúsculas o minúsculas), se considera registro.
    """
    if (
        not message.channel.category
        or message.channel.category.name != config.CATEGORIA_REGISTRO
    ):
        return False
    contenido = normalizar_texto(message.content)
    return config.REGISTRO_PREFIJO in contenido


def _categoria_de_canal(message: discord.Message) -> str:
    """Detecta la categoría (pro/junior) del canal donde se escribió el mensaje.

    Antes siempre se asumía PRO (default-league). Después se hizo buscando
    la palabra "junior" en el nombre del canal o de su categoría, pero seguía
    siendo frágil: un canal junior mal nombrado caía como PRO.

    Estrategia actual en orden de prioridad:
      1. Si el nombre del canal contiene "junior" → junior.
      2. Si el nombre de la categoría padre contiene "junior" → junior.
      3. Si el topic del canal lo declara explícitamente (ej. "category:junior"
         o "category=pro") → ese.
      4. Default: pro.
    """
    topic = ""
    if hasattr(message.channel, "topic") and message.channel.topic:
        topic = message.channel.topic.lower()
    if "category:junior" in topic or "category=junior" in topic:
        return "junior"
    if "category:pro" in topic or "category=pro" in topic:
        return "pro"

    nombres = []
    if message.channel.category:
        nombres.append(message.channel.category.name)
    if hasattr(message.channel, "name"):
        nombres.append(message.channel.name)
    texto = " ".join(nombres).lower()
    return "junior" if "junior" in texto else "pro"

# 1 respuesta de IA cada 15s por usuario. Antes no había límite: cualquiera
# podía spammear menciones y agotar la cuota de la API de Groq.
_ia_cooldown = commands.CooldownMapping.from_cooldown(1, 15.0, commands.BucketType.user)


class IA(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if _es_mensaje_de_registro(message):
            rol = discord.utils.get(message.guild.roles, name=config.NOMBRE_ROL)
            if rol:
                try:
                    await message.author.add_roles(rol)
                    logger.info("'%s' asignado a %s", config.NOMBRE_ROL, message.author.name)
                except (discord.Forbidden, discord.HTTPException) as e:
                    logger.error("Fallo al asignar rol: %s", e)

        es_mencion = self.bot.user in message.mentions
        es_respuesta = (
            message.reference is not None
            and isinstance(message.reference.resolved, discord.Message)
            and message.reference.resolved.author == self.bot.user
        )

        if es_mencion or es_respuesta:
            bucket = _ia_cooldown.get_bucket(message)
            retry_after = bucket.update_rate_limit()
            if retry_after:
                await message.reply(
                    f"⏳ Tranquilo, esperá `{retry_after:.0f}s` antes de preguntarme otra cosa.",
                    mention_author=False,
                    delete_after=5,
                )
                return

            texto = (
                message.content
                .replace(f"<@{self.bot.user.id}>", "")
                .replace(f"<@!{self.bot.user.id}>", "")
                .strip()
            )
            if not texto:
                texto = "(el usuario te mencionó sin escribir nada)"
            async with message.channel.typing():
                try:
                    league_id = league_id_for(_categoria_de_canal(message))
                    respuesta = await generar_respuesta(message, texto, league_id=league_id)
                    await message.reply(respuesta, mention_author=False)
                except Exception as e:
                    logger.error("Error en IA: %s", e)
                    await message.reply("❌ Hubo un error al procesar tu mensaje. Probá de nuevo en un momento.", mention_author=False)


async def setup(bot):
    await bot.add_cog(IA(bot))
