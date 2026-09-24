"""
"Exportador" de playlists de Spotify: no usa la Web API oficial (esa es
la que empezó a exigir cuenta Premium para varios endpoints), sino que
lee la página pública de embed de Spotify (open.spotify.com/embed/...),
que no requiere login, API key ni Premium — solo que la playlist sea
pública. De ahí sacamos título + artista de cada canción para después
buscar y reproducir el audio real desde YouTube (ver services/youtube.py).

Si Spotify cambia el HTML/JSON de esa página esto puede romperse; en ese
caso el error queda logueado con el motivo exacto para poder arreglarlo.
"""
import json
import logging
import re

from services.firebase import _get_session

logger = logging.getLogger(__name__)

_EMBED_BASE = "https://open.spotify.com/embed/playlist"
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


def es_link_spotify(url_or_id: str) -> bool:
    return "spotify.com" in url_or_id or url_or_id.startswith("spotify:playlist:")


def _extract_playlist_id(url_or_id: str) -> str:
    """Acepta un link de playlist de Spotify (con o sin query params), un
    URI (spotify:playlist:ID) o un ID directo."""
    match = re.search(r"playlist[/:]([a-zA-Z0-9]+)", url_or_id)
    return match.group(1) if match else url_or_id.strip()


async def get_playlist(url_or_id: str):
    """Devuelve (nombre_playlist, [{"title", "artist"}, ...]) de una
    playlist pública de Spotify, sin usar la Web API oficial."""
    playlist_id = _extract_playlist_id(url_or_id)
    s = await _get_session()

    async with s.get(f"{_EMBED_BASE}/{playlist_id}") as r:
        if r.status != 200:
            logger.error("[SPOTIFY ERROR][embed %s] status=%s", playlist_id, r.status)
            raise RuntimeError(
                "No se pudo leer esa playlist de Spotify. Verificá que el link sea correcto y sea pública."
            )
        html = await r.text()

    match = _NEXT_DATA_RE.search(html)
    if not match:
        logger.error("[SPOTIFY ERROR][embed %s] no se encontró __NEXT_DATA__ en la página", playlist_id)
        raise RuntimeError("Spotify cambió el formato de su página y no pude leer la playlist. Probá con un link de YouTube/YouTube Music mientras tanto.")

    try:
        data = json.loads(match.group(1))
        entity = data["props"]["pageProps"]["state"]["data"]["entity"]
        nombre_playlist = entity.get("name") or entity.get("title") or "Playlist de Spotify"
        items = entity.get("trackList", [])
    except (KeyError, json.JSONDecodeError) as e:
        logger.error("[SPOTIFY ERROR][embed %s] no se pudo parsear el JSON: %s", playlist_id, e)
        raise RuntimeError("Spotify cambió el formato de su página y no pude leer la playlist. Probá con un link de YouTube/YouTube Music mientras tanto.")

    tracks = []
    for item in items:
        titulo = item.get("title")
        artista = item.get("subtitle")  # nombres de artista separados por coma
        if not titulo:
            continue
        tracks.append({"title": titulo, "artist": artista or ""})

    if not tracks:
        raise RuntimeError("Esa playlist de Spotify parece vacía, privada, o Spotify no me dejó leerla del todo (a veces solo entrega las primeras canciones).")

    return nombre_playlist, tracks
