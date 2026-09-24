"""
Cliente Firebase (Realtime Database + Auth) usado por todo el bot.

Usa Firebase Auth (email/password) con refresh de token automático, en vez
de llamadas REST sin autenticar. Incluye:
- Lock para que dos requests concurrentes no disparen 2 logins/refresh en paralelo.
- Logging de errores también en respuestas non-200 (antes se silenciaban).
"""
import logging
import time
import asyncio
import aiohttp

from config import FIREBASE_URL, FIREBASE_API_KEY, FIREBASE_BOT_EMAIL, FIREBASE_BOT_PASSWORD

logger = logging.getLogger(__name__)

_FB_TIMEOUT = aiohttp.ClientTimeout(total=10)

_fb_id_token = None
_fb_refresh_token = None
_fb_token_expiry = 0.0
_fb_lock = asyncio.Lock()

_session: aiohttp.ClientSession | None = None


async def _get_session() -> aiohttp.ClientSession:
    # Sesión aiohttp global reutilizada entre requests, en vez de crear una
    # nueva por cada llamada a Firebase (evita overhead de conexión/TLS).
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(timeout=_FB_TIMEOUT)
    return _session


async def close_session():
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
    _session = None


async def firebase_login():
    global _fb_id_token, _fb_refresh_token, _fb_token_expiry
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = {"email": FIREBASE_BOT_EMAIL, "password": FIREBASE_BOT_PASSWORD, "returnSecureToken": True}
    s = await _get_session()
    async with s.post(url, json=payload) as r:
        data = await r.json()
        if r.status != 200:
            raise RuntimeError(f"No se pudo iniciar sesión en Firebase: {data}")
        _fb_id_token = data["idToken"]
        _fb_refresh_token = data["refreshToken"]
        _fb_token_expiry = time.time() + int(data.get("expiresIn", 3600)) - 60


async def _firebase_refresh():
    global _fb_id_token, _fb_refresh_token, _fb_token_expiry
    url = f"https://securetoken.googleapis.com/v1/token?key={FIREBASE_API_KEY}"
    payload = {"grant_type": "refresh_token", "refresh_token": _fb_refresh_token}
    s = await _get_session()
    async with s.post(url, data=payload) as r:
        data = await r.json()
        if r.status != 200:
            # El refresh token puede haber expirado/sido revocado: reintentamos con login completo.
            await firebase_login()
            return
        _fb_id_token = data["id_token"]
        _fb_refresh_token = data["refresh_token"]
        _fb_token_expiry = time.time() + int(data.get("expires_in", 3600)) - 60


async def _get_fb_token():
    # Lock: evita que 2 requests concurrentes, al ver el token vencido al
    # mismo tiempo, disparen 2 logins/refresh en paralelo innecesariamente.
    async with _fb_lock:
        if not _fb_id_token or time.time() >= _fb_token_expiry:
            if _fb_refresh_token:
                await _firebase_refresh()
            else:
                await firebase_login()
        return _fb_id_token


async def get_firebase(path: str):
    url = f"{FIREBASE_URL}/{path}.json"
    params = {"auth": await _get_fb_token()}
    try:
        s = await _get_session()
        async with s.get(url, params=params) as r:
            if r.status == 200:
                return await r.json()
            body = await r.text()
            logger.error("[FIREBASE ERROR][GET %s] status=%s body=%s", path, r.status, body[:300])
            return {}
    except Exception as e:
        logger.error("[FIREBASE ERROR][GET %s] %s", path, e)
        return {}


async def set_firebase(path: str, data) -> bool:
    url = f"{FIREBASE_URL}/{path}.json"
    params = {"auth": await _get_fb_token()}
    try:
        s = await _get_session()
        async with s.put(url, params=params, json=data) as r:
            if r.status == 200:
                return True
            body = await r.text()
            logger.error("[FIREBASE ERROR][PUT %s] status=%s body=%s", path, r.status, body[:300])
            return False
    except Exception as e:
        logger.error("[FIREBASE ERROR][PUT %s] %s", path, e)
        return False


async def push_firebase(path: str, data):
    url = f"{FIREBASE_URL}/{path}.json"
    params = {"auth": await _get_fb_token()}
    try:
        s = await _get_session()
        async with s.post(url, params=params, json=data) as r:
            if r.status == 200:
                result = await r.json()
                return result.get("name")
            body = await r.text()
            logger.error("[FIREBASE ERROR][POST %s] status=%s body=%s", path, r.status, body[:300])
    except Exception as e:
        logger.error("[FIREBASE ERROR][POST %s] %s", path, e)
    return None


async def patch_firebase(path: str, data) -> bool:
    url = f"{FIREBASE_URL}/{path}.json"
    params = {"auth": await _get_fb_token()}
    try:
        s = await _get_session()
        async with s.patch(url, params=params, json=data) as r:
            if r.status == 200:
                return True
            body = await r.text()
            logger.error("[FIREBASE ERROR][PATCH %s] status=%s body=%s", path, r.status, body[:300])
            return False
    except Exception as e:
        logger.error("[FIREBASE ERROR][PATCH %s] %s", path, e)
        return False


async def delete_firebase(path: str) -> bool:
    url = f"{FIREBASE_URL}/{path}.json"
    params = {"auth": await _get_fb_token()}
    try:
        s = await _get_session()
        async with s.delete(url, params=params) as r:
            if r.status == 200:
                return True
            body = await r.text()
            logger.error("[FIREBASE ERROR][DELETE %s] status=%s body=%s", path, r.status, body[:300])
            return False
    except Exception as e:
        logger.error("[FIREBASE ERROR][DELETE %s] %s", path, e)
        return False
