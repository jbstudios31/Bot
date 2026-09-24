"""
Cog de música. Acepta tanto playlists de YouTube/YouTube Music (se pone
el link directo de cada video) como de Spotify (Spotify ya no permite
leer playlists sin cuenta Premium en su Web API, así que se "exporta":
se lee título+artista de cada canción desde la página pública de Spotify
— sin login, sin API key — y esa canción se busca y reproduce desde
YouTube). En ambos casos el audio real siempre sale de YouTube.

Requiere: discord.py[voice] + davey (protocolo DAVE, obligatorio en
Discord desde el 2 de marzo de 2026 para que un bot participe en voz) y
ffmpeg instalado en el sistema (ver nixpacks.toml).
"""
import asyncio
import logging

import discord
from discord.ext import commands

from services import spotify
from services.youtube import buscar_audio, get_playlist, FFMPEG_OPTIONS

logger = logging.getLogger(__name__)


class Musica(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Una cola por servidor: guild_id -> list[{"title", "url"}]
        self.colas: dict[int, list] = {}

    def _cola(self, guild_id: int) -> list:
        return self.colas.setdefault(guild_id, [])

    async def _conectar(self, ctx):
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send("⚠️ Tenés que estar en un canal de voz primero.", delete_after=8)
            return None
        canal = ctx.author.voice.channel
        if ctx.voice_client is None:
            try:
                return await canal.connect()
            except Exception as e:
                logger.error("[MUSICA ERROR] conectar: %s", e)
                await ctx.send(f"❌ No pude unirme al canal de voz: {e}")
                return None
        if ctx.voice_client.channel != canal:
            await ctx.voice_client.move_to(canal)
        return ctx.voice_client

    def _siguiente(self, ctx, error=None):
        if error:
            logger.error("[MUSICA ERROR] reproducción: %s", error)
        cola = self._cola(ctx.guild.id)
        if not cola or ctx.voice_client is None:
            return
        cancion = cola.pop(0)
        asyncio.run_coroutine_threadsafe(self._reproducir(ctx, cancion), self.bot.loop)

    async def _reproducir(self, ctx, cancion: dict):
        vc = ctx.voice_client
        if vc is None:
            return
        # Playlist de YouTube: ya tenemos el link directo del video.
        # Playlist "exportada" de Spotify: hay que buscarla en YouTube por
        # título + artista (yt-dlp maneja tanto un link directo como una
        # búsqueda de texto).
        if cancion.get("url"):
            query = cancion["url"]
        else:
            query = f"{cancion['title']} {cancion.get('artist', '')} audio".strip()
        resultado = await buscar_audio(query)
        if resultado is None:
            await ctx.send(f"⚠️ No encontré audio para **{cancion['title']}**, sigo con la próxima.", delete_after=8)
            self._siguiente(ctx)
            return
        stream_url, _titulo = resultado
        try:
            fuente = discord.FFmpegPCMAudio(stream_url, **FFMPEG_OPTIONS)
            vc.play(fuente, after=lambda e: self._siguiente(ctx, e))
        except Exception as e:
            logger.error("[MUSICA ERROR] play: %s", e)
            await ctx.send(f"⚠️ Error reproduciendo **{cancion['title']}**, sigo con la próxima.", delete_after=8)
            self._siguiente(ctx)
            return
        await ctx.send(f"▶️ Sonando: **{cancion['title']}**")

    @commands.command(name="playlist")
    async def playlist(self, ctx, url: str = None):
        """Une el bot a tu canal de voz y pone una playlist de YouTube, YouTube Music o Spotify. Uso: !playlist <link>"""
        if url is None:
            await ctx.send("⚠️ Pasame el link de la playlist. Uso: `!playlist <link>`", delete_after=8)
            return
        vc = await self._conectar(ctx)
        if vc is None:
            return
        es_spotify = spotify.es_link_spotify(url)
        if es_spotify:
            await ctx.send("🔄 Exportando la playlist de Spotify a YouTube, un toque…", delete_after=10)
        async with ctx.typing():
            try:
                if es_spotify:
                    nombre, tracks = await spotify.get_playlist(url)
                else:
                    nombre, tracks = await get_playlist(url)
            except Exception as e:
                await ctx.send(f"❌ {e}")
                return
        if not tracks:
            await ctx.send("⚠️ Esa playlist está vacía, es privada o no pude leerla.", delete_after=8)
            return
        cola = self._cola(ctx.guild.id)
        cola.extend(tracks)
        await ctx.send(f"🎶 Agregué **{len(tracks)}** canciones de **{nombre}** a la cola.")
        if not vc.is_playing() and not vc.is_paused():
            self._siguiente(ctx)

    @commands.command(name="skip")
    async def skip(self, ctx):
        """Salta a la siguiente canción de la cola."""
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("⏭️ Saltado.")
        else:
            await ctx.send("⚠️ No hay nada sonando.", delete_after=8)

    @commands.command(name="cola")
    async def cola_cmd(self, ctx):
        """Muestra las próximas canciones en la cola."""
        cola = self._cola(ctx.guild.id)
        if not cola:
            await ctx.send("📭 La cola está vacía.")
            return
        lineas = []
        for i, c in enumerate(cola[:10], 1):
            texto = f"{c['title']} — {c['artist']}" if c.get("artist") else c["title"]
            lineas.append(f"{i}. {texto}")
        extra = f"\n…y {len(cola) - 10} más." if len(cola) > 10 else ""
        await ctx.send("📋 **Próximas:**\n" + "\n".join(lineas) + extra)

    @commands.command(name="stop")
    async def stop(self, ctx):
        """Para la música, vacía la cola y saca al bot del canal de voz."""
        self._cola(ctx.guild.id).clear()
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
        await ctx.send("⏹️ Listo, salí del canal.")


async def setup(bot):
    await bot.add_cog(Musica(bot))
