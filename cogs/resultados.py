import logging
import random
import re
import string
from datetime import datetime

import discord
from discord.ext import commands

from services.firebase import get_firebase, set_firebase, patch_firebase
from utils.standings import (
    get_league, find_driver, find_race, compute_standings, make_standings_embed,
    get_league_id, resolve_categoria, cat_label_for, categorias_disponibles_str,
)

logger = logging.getLogger(__name__)


class Resultados(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _cargar_resultado(self, ctx, categoria: str, nombre_carrera: str, posiciones: str, fecha: str = None):
        cat_key = resolve_categoria(categoria)
        if not cat_key:
            await ctx.send(f"❌ Categoría inválida. Usa una de: {categorias_disponibles_str()}")
            return
        cat_label = cat_label_for(cat_key)

        # Si el admin pasó fecha, validamos el formato. Si no, usamos hoy UTC.
        # Antes la fecha de la carrera nueva siempre era "hoy UTC", lo que era
        # incorrecto si el admin cargaba la carrera de un día distinto (ej.
        # cargando el lunes una del domingo).
        fecha_carrera = fecha or datetime.utcnow().strftime("%Y-%m-%d")
        if fecha and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            await ctx.send("❌ Fecha inválida. Usa formato `YYYY-MM-DD`, ej: `2026-03-15`.")
            return

        league_id = await get_league_id(cat_key)
        league = await get_league(league_id)
        if not league:
            await ctx.send("❌ No se pudieron obtener datos de Firebase.")
            return

        tokens = posiciones.split()
        vr_driver = None
        dnf_drivers = []
        pos_map = {}

        for token in tokens:
            if ":" not in token:
                continue
            key, val = token.split(":", 1)
            key, val = key.lower().strip(), val.strip()
            if key == "vr":
                vr_driver = val
            elif key == "dnf":
                dnf_drivers.append(val)
            else:
                try:
                    pos_int = int(key)
                    if pos_int < 1:
                        continue
                    pos_map[pos_int] = val
                except ValueError:
                    pass

        if not pos_map and not dnf_drivers:
            await ctx.send("❌ No se encontraron posiciones válidas. Usa formato: `1:Piloto 2:Piloto dnf:Piloto`")
            return

        races_data = await get_firebase(f"leagues/{league_id}/races")
        races = []
        if races_data:
            races = [r for r in races_data if r] if isinstance(races_data, list) else list(races_data.values())

        race = find_race(races, nombre_carrera)

        # Resuelve el piloto de vuelta rápida con la misma lógica de find_driver
        # (exact-match primero, luego substring) en vez de un startswith suelto,
        # para ser consistente con el resto de las búsquedas de piloto.
        vr_driver_obj = find_driver(league, vr_driver) if vr_driver else None

        # Antes: un piloto mal escrito se "saltaba" silenciosamente y la carga
        # quedaba incompleta sin que el admin lo notara. Ahora: si falta algún
        # piloto, se aborta toda la carga ANTES de tocar Firebase (ni siquiera
        # se crea la carrera) y se lista qué nombres no se pudieron resolver,
        # para que el admin corrija y reintente.
        no_encontrados = []
        for _, pname in sorted(pos_map.items()):
            if not find_driver(league, pname):
                no_encontrados.append(pname)
        for pname in dnf_drivers:
            if not find_driver(league, pname):
                no_encontrados.append(pname)
        if vr_driver and not vr_driver_obj:
            no_encontrados.append(vr_driver)

        if no_encontrados:
            await ctx.send(
                "❌ No se encontraron estos pilotos, no se cargó nada: "
                + ", ".join(f"`{n}`" for n in no_encontrados)
            )
            return

        if not race:
            # Antes: se reescribía TODO el array "races" con set_firebase, lo
            # que podía pisar una carrera cargada por otra persona en simultáneo.
            # Ahora: se agrega como hijo nuevo con PUT a su propia key, sin
            # tocar el resto del calendario.
            race_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
            race = {
                "id": race_id,
                "name": nombre_carrera,
                "date": fecha_carrera,
            }
            ok = await set_firebase(f"leagues/{league_id}/races/{race_id}", race)
            if not ok:
                await ctx.send("❌ Error al crear la carrera en Firebase.")
                return

        race_id = race["id"]
        result_entries = []
        processed = set()

        for pos, pname in sorted(pos_map.items()):
            driver = find_driver(league, pname)
            result_entries.append({
                "driverId": driver["id"],
                "position": pos,
                "dnf": False,
                "fastestLap": bool(vr_driver_obj and driver["id"] == vr_driver_obj["id"])
            })
            processed.add(driver["id"])

        for pname in dnf_drivers:
            driver = find_driver(league, pname)
            if driver["id"] not in processed:
                result_entries.append({"driverId": driver["id"], "position": None, "dnf": True, "fastestLap": False})

        # Antes: fetch de "results" completo + merge local + PUT de todo el
        # objeto de vuelta, lo que podía pisar resultados de otra carrera
        # cargados en simultáneo. Ahora: PATCH apuntando solo a la key de
        # esta carrera dentro de "results" — Firebase lo mergea de forma
        # atómica sin tocar las demás carreras.
        ok = await patch_firebase(f"leagues/{league_id}/results", {race_id: result_entries})
        if not ok:
            await ctx.send("❌ Error al guardar los resultados.")
            return

        embed = discord.Embed(title=f"🏁 Resultado: {nombre_carrera} ({cat_label})", color=0x3DDC97)
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for e in result_entries:
            driver = next((d for d in (league.get("drivers") or []) if d.get("id") == e["driverId"]), None)
            name = driver.get("name", "?") if driver else "?"
            if e["dnf"]:
                lines.append(f"❌ DNF — **{name}**")
            else:
                pos = e["position"]
                medal = medals[pos - 1] if pos <= 3 else f"`P{pos}`"
                vr = " ⚡" if e.get("fastestLap") else ""
                lines.append(f"{medal} **{name}**{vr}")
        embed.description = "\n".join(lines)
        embed.set_footer(text=f"Cargado por {ctx.author.display_name} • GT3 Platinum Cup")
        await ctx.send(embed=embed)

        league_updated = await get_league(league_id)
        standings = compute_standings(league_updated)
        embed2 = make_standings_embed(standings, league.get("leagueName", "GT3 Platinum Cup"), cat_key)
        embed2.title = f"📊 Clasificación actualizada — {cat_label}"
        await ctx.send(embed=embed2)

    @commands.command(name="resultado")
    @commands.has_permissions(manage_roles=True)
    async def resultado(self, ctx, nombre_carrera: str, *, resto: str):
        """
        Carga el resultado de una carrera de GT3 Pro.
        Uso: !resultado "Ronda 1 Monaco" 1:Gonzalez 2:Martinez 3:Lopez dnf:Perez vr:Gonzalez
              !resultado "Ronda 1 Monaco" 2026-03-15 1:Gonzalez ...
        El segundo parámetro (opcional) es la fecha en formato YYYY-MM-DD.
        Para GT3 usa !resultado_gt3, para Porsche Cup usa !resultado_porsche.
        """
        # La sintaxis original es: nombre_carrera + posiciones
        # La nueva sintaxis es: nombre_carrera + fecha (YYYY-MM-DD) + posiciones
        # Detectamos la diferencia: si el primer token después del nombre es
        # una fecha válida, lo separamos.
        partes = resto.split(maxsplit=1)
        fecha = None
        cuerpo = resto
        if partes and re.fullmatch(r"\d{4}-\d{2}-\d{2}", partes[0]):
            fecha = partes[0]
            cuerpo = partes[1] if len(partes) > 1 else ""
        if not cuerpo:
            await ctx.send("❌ Faltan las posiciones. Ejemplo: `!resultado \"Monaco\" 1:Gonzalez 2:Martinez`")
            return
        await self._cargar_resultado(ctx, "pro", nombre_carrera, cuerpo, fecha)

    @commands.command(name="resultado_gt3")
    @commands.has_permissions(manage_roles=True)
    async def resultado_gt3(self, ctx, nombre_carrera: str, *, resto: str):
        """Igual que !resultado pero para la categoría GT3."""
        partes = resto.split(maxsplit=1)
        fecha = None
        cuerpo = resto
        if partes and re.fullmatch(r"\d{4}-\d{2}-\d{2}", partes[0]):
            fecha = partes[0]
            cuerpo = partes[1] if len(partes) > 1 else ""
        if not cuerpo:
            await ctx.send("❌ Faltan las posiciones. Ejemplo: `!resultado_gt3 \"Monaco\" 1:Gonzalez 2:Martinez`")
            return
        await self._cargar_resultado(ctx, "gt3", nombre_carrera, cuerpo, fecha)

    @commands.command(name="resultado_porsche")
    @commands.has_permissions(manage_roles=True)
    async def resultado_porsche(self, ctx, nombre_carrera: str, *, resto: str):
        """Igual que !resultado pero para la categoría Porsche Cup."""
        partes = resto.split(maxsplit=1)
        fecha = None
        cuerpo = resto
        if partes and re.fullmatch(r"\d{4}-\d{2}-\d{2}", partes[0]):
            fecha = partes[0]
            cuerpo = partes[1] if len(partes) > 1 else ""
        if not cuerpo:
            await ctx.send("❌ Faltan las posiciones. Ejemplo: `!resultado_porsche \"Monaco\" 1:Gonzalez 2:Martinez`")
            return
        await self._cargar_resultado(ctx, "porsche", nombre_carrera, cuerpo, fecha)


async def setup(bot):
    await bot.add_cog(Resultados(bot))
