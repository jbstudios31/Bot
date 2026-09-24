"""Punto de entrada del bot. Toda la lógica vive en services/, utils/ y cogs/."""
import asyncio
import logging
import os

import discord
from aiohttp import web
from discord.ext import commands

import config
from services.firebase import firebase_login, close_session

config.validar_config()

# Logging centralizado. Antes todos los módulos usaban print() y no había
# forma de filtrar por nivel ni de mandar los errores a un sink externo
# (Sentry, etc). Ahora se configura acá una vez y el resto de los módulos
# hace `logger = logging.getLogger(__name__)`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("bot")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=config.PREFIX, intents=intents)

COGS = [
    "cogs.ia",
    "cogs.clasificacion",
    "cogs.penalizaciones",
    "cogs.resultados",
    "cogs.protestas",
    "cogs.admin_mensajes",
    "cogs.info",
    "cogs.musica",
]


@bot.event
async def on_ready():
    logger.info("Bot conectado como: %s", bot.user)
    logger.info("ID: %s", bot.user.id)
    logger.info("Servidores: %d", len(bot.guilds))
    logger.info("─" * 40)
    for guild in bot.guilds:
        logger.info("📡 %s  (id: %s)", guild.name, guild.id)
        for channel in guild.text_channels:
            logger.info("    #%s  (id: %s)", channel.name, channel.id)
    logger.info("─" * 40)
    logger.info("Listo para recibir comandos. Usa !ayuda para ver la lista completa.")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("⚠️ Faltan argumentos. Usa `!ayuda` para ver el uso correcto.", delete_after=8)
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("❌ Canal no encontrado. Menciona el canal con #.", delete_after=8)
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ Usuario no encontrado.", delete_after=8)
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("🔒 No tenés permisos para usar ese comando.", delete_after=8)
    elif isinstance(error, commands.CommandNotFound):
        return
    else:
        await ctx.send(f"❌ Error: {error}", delete_after=8)
        raise error


async def start_healthcheck_server():
    """Render (Web Service) requiere un puerto abierto o mata el deploy tras timeout.
    Esto NO sirve para nada del bot en sí, solo satisface el port scan de Render."""
    app = web.Application()
    app.router.add_get("/", lambda request: web.Response(text="Bot1 vivo"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Healthcheck server escuchando en puerto %d", port)


async def main():
    await firebase_login()
    logger.info("Sesión de Firebase iniciada correctamente.")
    await start_healthcheck_server()
    try:
        async with bot:
            for ext in COGS:
                await bot.load_extension(ext)
            await bot.start(config.TOKEN)
    finally:
        await close_session()


if __name__ == "__main__":
    asyncio.run(main())
