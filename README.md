# Bot1 — Bot de Discord GT3 Cup World Series

Bot de Discord para administrar la liga GT3 Cup World Series: clasificación,
penalizaciones, resultados de carreras, protestas y una IA con personalidad
propia que responde al mencionarla. Usa Firebase Realtime Database como
fuente de datos (compartida con las apps GT3 Pro / GT3 Junior) y Groq para
las respuestas de IA.

## Estructura

```
bot.py                  # entry point: carga config, cogs y arranca el bot
config.py                # variables de entorno y validación
services/
  firebase.py             # login/refresh de Firebase Auth + get/set/push/patch/delete
  groq.py                  # cliente de la API de Groq
utils/
  standings.py             # cálculo de puntos, búsqueda de pilotos, embeds de clasificación
cogs/
  ia.py                     # auto-rol al registrarse + IA al mencionar/responder al bot
  clasificacion.py          # !clasificacion
  penalizaciones.py         # !penalizar, !penalizaciones, !borrar_penalizacion(_junior)
  resultados.py             # !resultado, !resultado_junior
  protestas.py              # !protesta
  admin_mensajes.py         # !enviar, !dm, !canales
  info.py                   # !stats, !ayuda
tests/
  test_standings.py         # tests del cálculo de puntos
```

## Variables de entorno

| Variable | Descripción |
|---|---|
| `TOKEN` | Token del bot de Discord (Developer Portal → Bot) |
| `GROQ_API_KEY` | API key de [Groq](https://console.groq.com) |
| `FIREBASE_BOT_EMAIL` | Email de un usuario creado en Firebase Console → Authentication |
| `FIREBASE_BOT_PASSWORD` | Password de ese usuario |
| `CREADOR_ID` | *(Opcional)* ID de Discord del creador. Si está seteado, la IA le habla con respeto/cariño a ese usuario (en vez del modo sarcástico estándar). |

Copiá `.env.example` a `.env` para correrlo en local (con `python-dotenv` o
exportando las variables manualmente). En Railway se cargan desde
**Settings → Variables**.

## Correr en local

```bash
pip install -r requirements.txt
export $(cat .env | xargs)   # o usá python-dotenv
python bot.py
```

## Tests

```bash
python -m unittest
```

Cubren el cálculo de puntos (`compute_standings`) y la lógica de búsqueda
de pilotos/carreras (`find_driver`, `find_race`). El segundo set es
importante porque previene el bug clásico de "pisar al piloto equivocado"
cuando dos nombres son similares (ej. "Gonzalez A" vs "Gonzalez B").

## Comandos

- `!clasificacion [pro|junior]` — clasificación de pilotos
- `!penalizar <pro|junior> "Piloto" <tipo> "Carrera" <motivo>` — admins
- `!penalizaciones [pro|junior]` — sanciones activas agrupadas por carrera
- `!borrar_penalizacion <id>` / `!borrar_penalizacion_junior <id>` — admins
- `!resultado "Carrera" 1:Piloto 2:Piloto dnf:Piloto vr:Piloto` — admins, PRO. Opcional: agregar fecha antes de las posiciones, ej `!resultado "Monaco" 2026-03-15 1:Gonzalez 2:Martinez`
- `!resultado_junior "Carrera" ...` — admins, Junior (acepta la misma fecha opcional)
- `!protesta @piloto <motivo>` — protesta formal
- `!enviar #canal <mensaje>` / `!dm @usuario <mensaje>` — admins
- `!canales` — lista canales del servidor
- `!stats` — resumen de la liga generado por IA
- `!ayuda` — lista completa de comandos
- Mencioná al bot o respondele un mensaje para hablar con su IA (1 pregunta cada 15s por usuario)

## Deploy (Railway)

- `railway.json` define `startCommand: python bot.py` y restart on failure.
- `runtime.txt` fija Python 3.12.
- Las env vars se cargan desde **Railway → Settings → Variables** (no hace falta `.env` en prod).
- Si querés que el trato especial del creador funcione en producción, agregá `CREADOR_ID` con el ID numérico de Discord del creador.

## Notas de diseño

- El token de Firebase se refresca automáticamente y con lock (evita logins
  duplicados en requests concurrentes).
- Los resultados de cada carrera se guardan con `PATCH` a su propia key
  (`results/{raceId}`), no reescribiendo todo el objeto — así dos cargas
  simultáneas de carreras distintas no se pisan entre sí.
- `!penalizaciones` pagina automáticamente si una carrera junta muchas
  sanciones (límite de Discord: 1024 caracteres por field de embed).
- Groq reusa la misma sesión aiohttp global que Firebase (un solo
  `ClientSession` para todo el bot, en vez de crear uno nuevo por request).
- El logging se hace con el módulo `logging` (niveles, formato, fácil de
  redirigir a Sentry/etc), no con `print()`. Cada módulo define su
  `logger = logging.getLogger(__name__)`.
- Las respuestas de la IA se truncan a 30 palabras como red de seguridad
  contra respuestas largas, además del límite de 1-2 oraciones que ya viene
  en el system prompt.
