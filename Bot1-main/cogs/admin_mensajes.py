import logging

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class AdminMensajes(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="enviar")
    @commands.has_permissions(manage_messages=True)
    async def enviar(self, ctx, canal: discord.TextChannel, *, mensaje: str = ""):
        """Envía un mensaje (y opcionalmente imágenes adjuntas) a un canal. Uso: !enviar #canal <mensaje>"""
        archivos = [await a.to_file() for a in ctx.message.attachments]
        if not mensaje and not archivos:
            await ctx.send("❌ Escribí un mensaje o adjuntá un archivo/imagen. Discord no permite un mensaje completamente vacío.", delete_after=8)
            return
        try:
            await canal.send(content=mensaje if mensaje else None, files=archivos or [])
        except discord.HTTPException as e:
            await ctx.send(f"❌ No se pudo enviar el mensaje a #{canal.name}: {e}", delete_after=8)
            return
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("No se pudo borrar el mensaje de !enviar: %s", e)
        logger.info("[ENVIADO] #%s: %s | Imágenes: %d", canal.name, mensaje, len(archivos))

    @commands.command(name="dm")
    @commands.has_permissions(manage_messages=True)
    async def dm(self, ctx, usuario: discord.Member, *, mensaje: str):
        """Envía un mensaje privado a un piloto. Uso: !dm @usuario <mensaje>"""
        try:
            await usuario.send(mensaje)
        except discord.Forbidden:
            await ctx.send(f"❌ No se pudo enviar el DM: **{usuario.display_name}** tiene los mensajes privados cerrados.", delete_after=8)
            return
        except discord.HTTPException as e:
            await ctx.send(f"❌ Error al enviar el DM: {e}", delete_after=8)
            return
        await ctx.send(f"✅ DM enviado a **{usuario.display_name}**.", delete_after=5)
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("No se pudo borrar el mensaje de !dm: %s", e)
        logger.info("[DM] → %s: %s", usuario.name, mensaje)

    @commands.command(name="canales")
    async def canales(self, ctx):
        """Lista los canales de texto del servidor."""
        lines = ["**Canales de texto disponibles:**"]
        for ch in ctx.guild.text_channels:
            lines.append(f"• #{ch.name}  —  `{ch.id}`")
        await ctx.send("\n".join(lines))


async def setup(bot):
    await bot.add_cog(AdminMensajes(bot))
