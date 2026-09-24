from discord.ext import commands

from utils.standings import get_league, compute_standings, make_standings_embed, get_league_id, resolve_categoria, categorias_disponibles_str


class Clasificacion(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="clasificacion")
    async def clasificacion(self, ctx, categoria: str = "pro"):
        """Muestra la clasificación actual de pilotos. Uso: !clasificacion [pro|gt3|porsche]"""
        cat_key = resolve_categoria(categoria)
        if not cat_key:
            await ctx.send(f"❌ Categoría inválida. Usa una de: {categorias_disponibles_str()}")
            return
        async with ctx.typing():
            league_id = await get_league_id(cat_key)
            league = await get_league(league_id)
            if not league:
                await ctx.send("❌ No se pudieron obtener datos de Firebase.")
                return
            standings = compute_standings(league)
            embed = make_standings_embed(standings, league.get("leagueName", "GT3 Platinum Cup"), cat_key)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(Clasificacion(bot))
