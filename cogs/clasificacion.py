from discord.ext import commands

from utils.standings import get_league, compute_standings, make_standings_embed, league_id_for


class Clasificacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clasificacion")
    async def clasificacion(self, ctx, categoria: str = "pro"):
        """Muestra la clasificación actual de pilotos. Uso: !clasificacion [pro|junior]"""
        league_id = league_id_for(categoria)
        async with ctx.typing():
            league = await get_league(league_id)
            if not league:
                await ctx.send("❌ No se pudieron obtener datos de Firebase.")
                return
            standings = compute_standings(league)
            embed = make_standings_embed(standings, league.get("leagueName", "GT3 Cup"), league_id)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Clasificacion(bot))
