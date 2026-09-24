import logging

import discord
from discord.ext import commands

from services.groq import ask_groq
from utils.standings import get_league, get_league_id, resolve_categoria, cat_label_for, categorias_disponibles_str, build_ai_context

logger = logging.getLogger(__name__)


class Info(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="stats")
    async def stats(self, ctx, categoria: str = "pro"):
        """Muestra un resumen de la liga generado por IA. Uso: !stats [pro|gt3|porsche]"""
        cat_key = resolve_categoria(categoria)
        if not cat_key:
            await ctx.send(f"❌ Categoría inválida. Usa una de: {categorias_disponibles_str()}")
            return
        cat_label = cat_label_for(cat_key)
        async with ctx.typing():
            league_id = await get_league_id(cat_key)
            data = await get_league(league_id)
            if not data:
                await ctx.send(f"❌ No se pudieron obtener los datos de Firebase para **{cat_label}**.")
                return
            # Antes se le mandaba a la IA el dump JSON crudo de Firebase (con
            # ids internos y a veces truncado a mitad de un objeto). Ahora usa
            # el mismo resumen limpio (solo nombres/puntos) que las respuestas
            # de mención, para que no invente ni muestre datos internos.
            resumen_datos = build_ai_context(data, cat_key)
            system = f"Eres el bot de GT3 Platinum Cup. Resume la clasificación de la categoría {cat_label} de forma clara y concisa usando ÚNICAMENTE los datos dados. Nunca menciones IDs ni datos técnicos. Usa emojis de carreras. Responde en español."
            resumen = await ask_groq(system, f"Resume esta información de {cat_label}:\n{resumen_datos}")
            await ctx.send(resumen)

    @commands.command(name="ayuda")
    async def ayuda(self, ctx):
        """Muestra todos los comandos disponibles."""
        embed = discord.Embed(
            title="🏎️ Comandos GT3 Platinum Cup",
            color=0xFFD600,
            description="Todos los comandos del bot oficial de la liga."
        )
        embed.add_field(
            name="📊 Clasificación",
            value="`!clasificacion [pro|gt3|porsche]` — Ver clasificación de pilotos\n`!stats [pro|gt3|porsche]` — Resumen de la liga generado por IA",
            inline=False
        )
        embed.add_field(
            name="🚦 Penalizaciones (solo admins)",
            value=(
                '`!penalizar <pro|gt3|porsche> "Piloto" <tipo> "Carrera" <motivo>`\n'
                "Tipos: `+5s` `+10s` `+15s` `+20s` `+30s` `DT` `DQ` `ADVERTENCIA`\n"
                'Ejemplo: `!penalizar pro "Gonzalez" +5s "Monaco" Corte en la chicane`\n'
                "`!penalizaciones [pro|gt3|porsche]` — Ver sanciones agrupadas por carrera\n"
                "`!borrar_penalizacion <id>` — Eliminar penalización de GT3 Pro\n"
                "`!borrar_penalizacion_gt3 <id>` — Eliminar penalización de GT3\n"
                "`!borrar_penalizacion_porsche <id>` — Eliminar penalización de Porsche Cup"
            ),
            inline=False
        )
        embed.add_field(
            name="🏁 Resultados (solo admins)",
            value=(
                '`!resultado "Nombre Carrera" 1:Piloto 2:Piloto dnf:Piloto vr:Piloto` — GT3 Pro\n'
                '`!resultado_gt3 "Nombre Carrera" ...` — GT3\n'
                '`!resultado_porsche "Nombre Carrera" ...` — Porsche Cup\n'
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
            value="Mencióname o respondeme para hablar con la IA del bot (sabe la clasificación y el último ganador de la categoría de tu canal). Máx. 1 pregunta cada 15s por usuario.",
            inline=False
        )
        embed.set_footer(text="GT3 Platinum Cup Bot")
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Info(bot))
