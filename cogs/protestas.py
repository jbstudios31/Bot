import logging
from datetime import datetime

import discord
from discord.ext import commands

from services.firebase import push_firebase

logger = logging.getLogger(__name__)


class Protestas(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="protesta")
    @commands.cooldown(1, 60.0, commands.BucketType.user)
    async def protesta(self, ctx, denunciado: discord.Member, *, motivo: str):
        """Registra una protesta formal contra otro piloto. Uso: !protesta @piloto <motivo>"""
        protest_data = {
            "from": ctx.author.display_name,
            "fromId": str(ctx.author.id),
            "against": denunciado.display_name,
            "againstId": str(denunciado.id),
            "reason": motivo,
            "timestamp": datetime.utcnow().isoformat(),
            "status": "pending"
        }
        key = await push_firebase("leagues/default-league/protests", protest_data)
        if not key:
            await ctx.send("❌ No se pudo registrar la protesta en Firebase. Intentá de nuevo en un momento.", delete_after=8)
            return

        embed = discord.Embed(title="📋 Protesta Oficial", color=0xF2A93B)
        embed.add_field(name="Denunciante", value=ctx.author.mention, inline=True)
        embed.add_field(name="Denunciado", value=denunciado.mention, inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)
        embed.add_field(name="Estado", value="⏳ Pendiente de revisión", inline=False)
        embed.set_footer(text=f"Presentada el {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC • GT3 Cup World Series")

        await ctx.send(embed=embed)
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException) as e:
            logger.warning("No se pudo borrar el mensaje de protesta: %s", e)

    @protesta.error
    async def protesta_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(
                f"⏳ Ya presentaste una protesta hace poco. Esperá `{error.retry_after:.0f}s` antes de presentar otra.",
                delete_after=8,
            )


async def setup(bot):
    await bot.add_cog(Protestas(bot))
