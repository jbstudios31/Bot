import logging

import discord
from discord.ext import commands
from datetime import datetime

from services.firebase import get_firebase, push_firebase, patch_firebase
from utils.standings import (
    get_league, get_penalties, find_driver, find_race,
    get_league_id, resolve_categoria, cat_label_for, cat_color_for, categorias_disponibles_str,
)

logger = logging.getLogger(__name__)

EMOJI_MAP = {
    "+5s": "⏱️", "+10s": "⏱️", "+15s": "⏱️", "+20s": "⏱️", "+30s": "⏱️",
    "DT": "🚗", "DQ": "🚫", "ADVERTENCIA": "⚠️"
}

TIPOS_VALIDOS = {"+5s", "+10s", "+15s", "+20s", "+30s", "DT", "DQ", "ADVERTENCIA"}


class Penalizaciones(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="penalizar")
    @commands.has_permissions(manage_roles=True)
    async def penalizar(self, ctx, categoria: str, piloto_nombre: str, tipo: str, carrera_nombre: str, *, motivo: str = "Sin motivo especificado"):
        """
        Registra una penalización a un piloto.
        Uso: !penalizar <pro|gt3|porsche> "Nombre" <tipo> "Carrera" <motivo>
        Tipos: +5s +10s +15s +20s +30s DT DQ ADVERTENCIA
        """
        cat_key = resolve_categoria(categoria)
        if not cat_key:
            await ctx.send(
                f"❌ Categoría inválida. Usa una de: {categorias_disponibles_str()}\n"
                'Ejemplo: `!penalizar pro "Gonzalez" +5s "Monaco" Corte en la chicane`'
            )
            return

        league_id = await get_league_id(cat_key)
        tipo = tipo.upper()
        if tipo.startswith("+") and tipo.endswith("S"):
            tipo = tipo[:-1] + "s"

        if tipo not in TIPOS_VALIDOS:
            await ctx.send(f"❌ Tipo inválido `{tipo}`. Usa uno de: {', '.join(sorted(TIPOS_VALIDOS))}")
            return

        league = await get_league(league_id)
        if not league:
            await ctx.send("❌ No se pudieron obtener datos de Firebase.")
            return

        cat_label = cat_label_for(cat_key)

        driver = find_driver(league, piloto_nombre)
        if not driver:
            await ctx.send(f"❌ Piloto `{piloto_nombre}` no encontrado en la categoría **{cat_label}**.")
            return

        races_data = await get_firebase(f"leagues/{league_id}/races")
        races = []
        if races_data:
            races = [r for r in races_data if r] if isinstance(races_data, list) else list(races_data.values())

        race_match = find_race(races, carrera_nombre)

        if not race_match:
            nombres = [r.get("name", "?") for r in races]
            disponibles = ", ".join(f"`{n}`" for n in nombres) if nombres else "ninguna"
            await ctx.send(
                f"❌ Carrera `{carrera_nombre}` no encontrada en el calendario **{cat_label}**.\n"
                f"Carreras disponibles: {disponibles}"
            )
            return

        emoji = EMOJI_MAP.get(tipo, "🔴")

        penalty = {
            "driverId": driver["id"],
            "driverName": driver["name"],
            "type": tipo,
            "reason": motivo,
            "issuedBy": ctx.author.display_name,
            "timestamp": datetime.utcnow().isoformat(),
            "raceId": race_match["id"],
            "raceName": race_match["name"],
            "raceDate": race_match.get("date", ""),
            "category": cat_label,
            "active": True
        }

        key = await push_firebase(f"leagues/{league_id}/penalties", penalty)
        if not key:
            await ctx.send("❌ Error al guardar la penalización en Firebase.")
            return

        embed = discord.Embed(
            title=f"{emoji} Penalización registrada",
            color=cat_color_for(cat_key)
        )
        embed.add_field(name="Categoría", value=f"**{cat_label}**", inline=True)
        embed.add_field(name="Gran Premio", value=f"🏁 {race_match['name']}", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Piloto", value=driver["name"], inline=True)
        embed.add_field(name="Tipo", value=f"`{tipo}`", inline=True)
        embed.add_field(name="\u200b", value="\u200b", inline=True)
        embed.add_field(name="Motivo", value=motivo, inline=False)
        embed.add_field(name="Emitida por", value=ctx.author.display_name, inline=True)
        embed.add_field(name="ID", value=f"`{key[:8]}`", inline=True)
        embed.set_footer(text=f"GT3 Platinum Cup • {datetime.utcnow().strftime('%d/%m/%Y %H:%M')} UTC")
        await ctx.send(embed=embed)
        logger.info("[PENALIZACIÓN] [%s] %s | %s | GP: %s | %s | por %s", cat_label, driver['name'], tipo, race_match['name'], motivo, ctx.author.name)

    @commands.command(name="penalizaciones")
    async def penalizaciones(self, ctx, categoria: str = "pro"):
        """Muestra las penalizaciones activas agrupadas por Gran Premio. Uso: !penalizaciones [pro|gt3|porsche]"""
        cat_key = resolve_categoria(categoria)
        if not cat_key:
            await ctx.send(f"❌ Categoría inválida. Usa una de: {categorias_disponibles_str()}")
            return
        league_id = await get_league_id(cat_key)
        cat_label = cat_label_for(cat_key)

        async with ctx.typing():
            pens = await get_penalties(league_id)
            activas = [p for p in pens if p.get("active", True)]

            if not activas:
                await ctx.send(f"✅ No hay penalizaciones activas en **{cat_label}**.")
                return

            races_data = await get_firebase(f"leagues/{league_id}/races")
            races = []
            if races_data:
                races = [r for r in races_data if r] if isinstance(races_data, list) else list(races_data.values())

            race_order = {r["id"]: i for i, r in enumerate(sorted(races, key=lambda r: r.get("date", "9999")))}

            groups = {}
            sin_carrera = []
            for p in activas:
                rid = p.get("raceId")
                if rid:
                    if rid not in groups:
                        groups[rid] = {"name": p.get("raceName", "Sin carrera"), "date": p.get("raceDate", ""), "order": race_order.get(rid, 999), "pens": []}
                    groups[rid]["pens"].append(p)
                else:
                    sin_carrera.append(p)

            sorted_groups = sorted(groups.values(), key=lambda g: g["order"])
            if sin_carrera:
                sorted_groups.append({"name": "Sin carrera asignada", "date": "", "pens": sin_carrera})

            embed = discord.Embed(title=f"🚦 Penalizaciones — {cat_label}", color=cat_color_for(cat_key))

            for group in sorted_groups:
                date_str = f" · {group['date']}" if group.get("date") else ""
                field_name = f"🏁 {group['name']}{date_str}"
                lines = [
                    f"{EMOJI_MAP.get(p.get('type', ''), '🔴')} **{p.get('driverName', '?')}** — `{p.get('type', '?')}` — {p.get('reason', '?')}"
                    for p in group["pens"]
                ]
                texto = "\n".join(lines)
                # El "value" de un field de embed tiene límite de 1024 caracteres
                # en Discord. Antes esto podía romper el comando si una carrera
                # juntaba muchas sanciones; ahora se parte en varios fields.
                if len(texto) <= 1024:
                    embed.add_field(name=field_name, value=texto, inline=False)
                else:
                    partes, actual = [], ""
                    for linea in lines:
                        if len(actual) + len(linea) + 1 > 1024:
                            partes.append(actual)
                            actual = linea
                        else:
                            actual = f"{actual}\n{linea}" if actual else linea
                    if actual:
                        partes.append(actual)
                    for i, parte in enumerate(partes):
                        nombre = field_name if i == 0 else f"{field_name} (cont.)"
                        embed.add_field(name=nombre, value=parte, inline=False)

            total = sum(len(g["pens"]) for g in sorted_groups)
            embed.set_footer(text=f"{total} sanción(es) activa(s) • !borrar_penalizacion <id> (o _gt3 / _porsche)")
            await ctx.send(embed=embed)

    async def _borrar_penalizacion(self, ctx, categoria: str, penalty_id: str):
        cat_key = resolve_categoria(categoria)
        league_id = await get_league_id(cat_key)
        cat_label = cat_label_for(cat_key)

        data = await get_firebase(f"leagues/{league_id}/penalties")
        if not data or isinstance(data, list):
            await ctx.send(f"❌ No se encontraron penalizaciones en **{cat_label}**.")
            return

        match_key = None
        for key in data:
            if key == penalty_id or key.startswith(penalty_id):
                match_key = key
                break

        if not match_key:
            await ctx.send(f"❌ No se encontró ninguna penalización con ID `{penalty_id}` en **{cat_label}**.")
            return

        ok = await patch_firebase(f"leagues/{league_id}/penalties/{match_key}", {"active": False})
        if ok:
            await ctx.send(f"✅ Penalización `{penalty_id}` eliminada de **{cat_label}**.")
        else:
            await ctx.send("❌ Error al eliminar la penalización.")

    @commands.command(name="borrar_penalizacion")
    @commands.has_permissions(manage_roles=True)
    async def borrar_penalizacion(self, ctx, penalty_id: str):
        """Elimina (desactiva) una penalización de GT3 Pro por su ID."""
        await self._borrar_penalizacion(ctx, "pro", penalty_id)

    @commands.command(name="borrar_penalizacion_gt3")
    @commands.has_permissions(manage_roles=True)
    async def borrar_penalizacion_gt3(self, ctx, penalty_id: str):
        """Elimina (desactiva) una penalización de GT3 por su ID."""
        await self._borrar_penalizacion(ctx, "gt3", penalty_id)

    @commands.command(name="borrar_penalizacion_porsche")
    @commands.has_permissions(manage_roles=True)
    async def borrar_penalizacion_porsche(self, ctx, penalty_id: str):
        """Elimina (desactiva) una penalización de Porsche Cup por su ID."""
        await self._borrar_penalizacion(ctx, "porsche", penalty_id)


async def setup(bot):
    await bot.add_cog(Penalizaciones(bot))
