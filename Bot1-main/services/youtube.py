"""
Búsqueda, lectura de playlists y extracción de audio, todo desde YouTube
vía yt-dlp: tracklist y streaming salen de la misma fuente, sin depender
de ninguna otra API ni cuenta.
"""
import asyncio
import logging

import yt_dlp

logger = logging.getLogger(__name__)

_YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "source_address": "0.0.0.0",  # evita problemas de IPv6 en algunos hosts
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

_YDL_PLAYLIST_OPTS = {
    "extract_flat": "in_playlist",  # solo lista la playlist, no resuelve audio de cada video
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}


def _extraer(query: str):
    with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
        info = ydl.extract_info(query, download=False)
        if info is None:
            return None
        if "entries" in info:
            entradas = [e for e in info["entries"] if e]
            if not entradas:
                return None
            info = entradas[0]
        return info["url"], info.get("title", query)


async def buscar_audio(query: str):
    """Busca `query` en YouTube y devuelve (stream_url, titulo) o None si no encontró nada.
    También acepta un link directo de video (yt-dlp lo detecta solo)."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _extraer, query)
    except Exception as e:
        logger.error("[YOUTUBE ERROR] query=%s error=%s", query, e)
        return None


def _extraer_playlist(url: str):
    with yt_dlp.YoutubeDL(_YDL_PLAYLIST_OPTS) as ydl:
        info = ydl.extract_info(url, download=False)
    if info is None:
        return "Playlist", []
    entradas = [e for e in info.get("entries", []) if e]
    nombre = info.get("title") or "Playlist"
    tracks = []
    for e in entradas:
        video_url = e.get("url")
        if not video_url and e.get("id"):
            video_url = f"https://www.youtube.com/watch?v={e['id']}"
        if not video_url:
            continue
        tracks.append({"title": e.get("title") or "Sin título", "url": video_url})
    return nombre, tracks


async def get_playlist(url: str):
    """Lee una playlist pública de YouTube o YouTube Music.
    Devuelve (nombre_playlist, [{"title", "url"}, ...])."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(None, _extraer_playlist, url)
    except Exception as e:
        logger.error("[YOUTUBE ERROR][playlist] url=%s error=%s", url, e)
        raise RuntimeError(
            "No se pudo leer la playlist. Verificá que el link sea correcto y sea pública."
        )
