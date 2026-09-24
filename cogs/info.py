import json
import logging

import discord
from discord.ext import commands

import config
from services.firebase import get_firebase
from services.groq import ask_groq
from utils.standings import league_id_for, cat_label_for

logger = logging.getLogger(__name__)


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stats")
    async def stats(self, ctx, categoria: str = "pro"):
        """Muestra un resumen de la liga generado por IA. Uso: !stats [pro|junior]"""
        league_id = league_id_for(categoria)
        cat_label = cat_label_for(categoria)
        async with ctx.typing():
            data = await get_firebase(f"leagues/{league_id}")
            if not data:
                await ctx.send(f"❌ No se pudieron obtener los datos de Firebase para **{cat_label}**.")
                return
            data_str = json.dumps(data, ensure_ascii=False, indent=2)[: config.MAX_LEAGUE_DATA_CHARS]
            system = f"Eres el bot de GT3 Cup World Series. Resume las estadísticas de la liga {cat_label} de forma clara y concisa usando los datos dados. Usa emojis de carreras. Responde en español."
            resumen = await ask_groq(system, f"Resume estos datos de la liga {cat_label}:\n{data_str}")
            await ctx.send(resumen)

    @commands.command(name="ayuda")
    async def ayuda(self, ctx):
        """Muestra todos los comandos disponibles."""
        embed = discord.Embed(
            title="🏎️ Comandos GT3 Cup World Series",
            color=0xFFD600,
            description="Todos los comandos del bot oficial de la liga."
        )
        embed.add_field(
            name="📊 Clasificación",
            value="`!clasificacion [pro|junior]` — Ver clasificación de pilotos",
            inline=False
        )
        embed.add_field(
            name="🚦 Penalizaciones (solo admins)",
            value=(
                "`!penalizar <pro|junior> \"Piloto\" <tipo> \"Carrera\" <motivo>`\n"
                "Tipos: `+5s` `+10s` `+15s` `+20s` `+30s` `DT` `DQ` `ADVERTENCIA`\n"
                "Ejemplo: `!penalizar pro \"Gonzalez\" +5s \"Monaco\" Corte en la chicane`\n"
                "`!penalizaciones [pro|junior]` — Ver sanciones agrupadas por carrera\n"
                "`!borrar_penalizacion <id>` — Eliminar penalización PRO\n"
                "`!borrar_penalizacion_junior <id>` — Eliminar penalización Junior"
            ),
            inline=False
        )
        embed.add_field(
            name="🏁 Resultados (solo admins)",
            value=(
                "`!resultado \"Nombre Carrera\" 1:Piloto 2:Piloto dnf:Piloto vr:Piloto` — PRO\n"
                "`!resultado_junior \"Nombre Carrera\" ...` — Junior\n"
                "Carga resultados y actualiza la clasificación automáticamente."
            ),
            inline=False
        )
        embed.add_field(
            name="📋 Protestas",
            value="`!protesta @piloto <motivo>` — Presentar una protesta formal",
            inline=False
        )
        embed.add_field(
            name="📢 Mensajes (solo admins)",
            value=(
                "`!enviar #canal [mensaje]` — Enviar mensaje/imagen a un canal\n"
                "`!dm @usuario <mensaje>` — Enviar DM a un piloto"
            ),
            inline=False
        )
        embed.add_field(
            name="🎵 Música",
            value=(
                "`!playlist <link>` — Une el bot a tu canal de voz y pone una playlist de YouTube, YouTube Music o Spotify\n"
                "`!skip` — Salta a la siguiente canción\n"
                "`!cola` — Ver la cola de reproducción\n"
                "`!stop` — Parar la música y salir del canal"
            ),
            inline=False
        )
        embed.add_field(
            name="🤖 IA",
            value="Mencióname o respondeme para hablar con la IA del bot. (Máx. 1 pregunta cada 15s por usuario)",
            inline=False
        )
        embed.set_footer(text="GT3 Cup World Series Bot • Railway")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
