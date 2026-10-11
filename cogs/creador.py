"""Comandos exclusivos del creador del bot (gate por CREADOR_ID).

Todos los comandos de acá requieren que CREADOR_ID esté configurado como
variable de entorno y que quien los invoque tenga exactamente ese ID de
Discord. Cualquier otro usuario recibe un rechazo genérico.
"""
import json
import logging

import discord
from discord.ext import commands

import config
from services.firebase import get_firebase

logger = logging.getLogger(__name__)


class SoloCreador(commands.CheckFailure):
    """El que invocó el comando no es el creador."""


class CreadorNoConfigurado(commands.CheckFailure):
    """CREADOR_ID no está seteado en las variables de entorno."""


def solo_creador():
    async def predicate(ctx):
        if not config.CREADOR_ID:
            raise CreadorNoConfigurado()
        if str(ctx.author.id) == str(config.CREADOR_ID):
            return True
        raise SoloCreador()

    return commands.check(predicate)


class Creador(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def _error(self, ctx, error):
        if isinstance(error, CreadorNoConfigurado):
            await ctx.send(
                "⚙️ Este comando requiere configurar `CREADOR_ID` con el ID de Discord "
                "del creador (Railway → Variables).",
                delete_after=15,
            )
        elif isinstance(error, SoloCreador):
            await ctx.send("🔒 Este comando es solo para el creador del bot.", delete_after=8)
        else:
            logger.error("[CREADOR] %s", error)
            await ctx.send(f"❌ Error: {error}", delete_after=8)

    @commands.command(name="ligas")
    @solo_creador()
    async def ligas(self, ctx):
        """Diagnóstico: lista las ligas reales de Firebase con su esquema.
        Uso: !ligas (solo creador)"""
        async with ctx.typing():
            ligas = await get_firebase("leagues", shallow=True)
            if not isinstance(ligas, dict) or not ligas:
                await ctx.send("❌ No pude leer `leagues/` de Firebase (o está vacía).")
                return

            lines = []
            for key in sorted(ligas.keys()):
                if key.endswith("__seasons"):
                    meta = await get_firebase(f"leagues/{key}")
                    current = meta.get("current") if isinstance(meta, dict) else None
                    lines.append(f"{key}  → temporada actual: {current}")
                    continue

                sub = await get_firebase(f"leagues/{key}", shallow=True)
                campos = ", ".join(sorted(sub.keys())) if isinstance(sub, dict) else "?"
                lines.append(f"{key}  → campos: {campos}")

                drivers = await get_firebase(f"leagues/{key}/drivers", shallow=True)
                ids = list(drivers.keys()) if isinstance(drivers, dict) else []
                lines.append(f"    pilotos: {len(ids)}")
                if ids:
                    ejemplo = await get_firebase(f"leagues/{key}/drivers/{ids[0]}")
                    lines.append(f"    ejemplo: {json.dumps(ejemplo, ensure_ascii=False)}")
                lines.append("")

            texto = "```yaml\n" + "\n".join(lines) + "\n```"
            if len(texto) > 1980:
                texto = texto[:1970] + "\n…(truncado)\n```"
            await ctx.send(texto)

    @ligas.error
    async def ligas_error(self, ctx, error):
        await self._error(ctx, error)


async def setup(bot):
    await bot.add_cog(Creador(bot))
