"""Lógica de clasificación: categorías, temporada, cálculo de puntos,
búsqueda de pilotos/carreras, y embeds.

Categorías reales de la app "GT3 Platinum Cup" (temporada 2): GT3 Pro, GT3
y Porsche Cup. Antes eran solo "pro" y "junior" contra otro proyecto de
Firebase — la liga vieja quedó archivada, esto lee la app nueva.
"""
import discord

from services.firebase import get_firebase

CATEGORIES = {
    "pro":     {"db_id": "gt3-pro-league",    "label": "GT3 Pro",     "color": 0xD6293F},
    "gt3":     {"db_id": "gt3-league",        "label": "GT3",         "color": 0x3D6BFF},
    "porsche": {"db_id": "porsche-cup-league", "label": "Porsche Cup", "color": 0xE0932E},
}

# Alias que puede escribir un usuario/admin en Discord -> key interna de CATEGORIES.
_ALIASES = {
    "pro": "pro", "gt3pro": "pro", "gt3-pro": "pro", "gt3_pro": "pro",
    "gt3": "gt3", "gt": "gt3",
    "porsche": "porsche", "porschecup": "porsche", "porsche-cup": "porsche",
    "porsche_cup": "porsche", "cup": "porsche", "porschecupp": "porsche",
}


def resolve_categoria(categoria: str):
    """Normaliza texto libre ("Porsche Cup", "gt3-pro", etc.) a una key de
    CATEGORIES ("pro"/"gt3"/"porsche"), o None si no matchea ninguna."""
    if not categoria:
        return None
    limpio = categoria.strip().lower().replace(" ", "")
    return _ALIASES.get(limpio)


def cat_label_for(categoria_key: str) -> str:
    return CATEGORIES.get(categoria_key, CATEGORIES["pro"])["label"]


def cat_color_for(categoria_key: str) -> int:
    return CATEGORIES.get(categoria_key, CATEGORIES["pro"])["color"]


def categorias_disponibles_str() -> str:
    return ", ".join(f"`{k}`" for k in CATEGORIES)


def points_system_default():
    return [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


async def get_league_id(categoria_key: str) -> str:
    """Resuelve el id real del documento en Firebase para la temporada
    ACTIVA de esa categoría (leagues/<db_id>__seasons -> current). La app
    guarda cada temporada nueva como <db_id>-s<N> (temporada 1 = <db_id> a
    secas). Si no hay metadata de temporada todavía, asume temporada 1."""
    db_id = CATEGORIES[categoria_key]["db_id"]
    meta = await get_firebase(f"leagues/{db_id}__seasons")
    current = meta.get("current") if isinstance(meta, dict) else None
    current = current if isinstance(current, int) and current > 0 else 1
    return db_id if current <= 1 else f"{db_id}-s{current}"


async def get_league(league_id: str) -> dict:
    data = await get_firebase(f"leagues/{league_id}")
    return data or {}


async def get_penalties(league_id: str) -> list:
    data = await get_firebase(f"leagues/{league_id}/penalties")
    if not data:
        return []
    if isinstance(data, list):
        return [p for p in data if p]
    return [p for p in data.values() if p]


def _as_list(value):
    """La RTDB devuelve arrays como dict {'0': ..., '1': ...} cuando hay
    huecos, o como list normal. Esto normaliza cualquiera de los dos casos
    (y None) a una list de valores no vacíos."""
    if isinstance(value, dict):
        return [v for v in value.values() if v]
    if isinstance(value, list):
        return [v for v in value if v]
    return []


def find_race(races: list, name_query: str):
    """Busca una carrera por nombre, priorizando coincidencia exacta antes
    que substring, para evitar pisar la carrera equivocada cuando hay
    nombres solapados (ej. "Monaco" vs "Monaco Sprint")."""
    q = name_query.lower().strip()

    for r in races:
        if r.get("name", "").lower() == q:
            return r

    for r in races:
        if q in r.get("name", "").lower():
            return r
    return None


def find_driver(league: dict, name_query: str):
    drivers = _as_list(league.get("drivers"))
    q = name_query.lower().strip()

    # 1) Coincidencia exacta primero. Evita que un substring compartido entre
    #    dos pilotos (ej. "Gonzalez A" / "Gonzalez B") agarre el equivocado
    #    cuando el usuario escribió el nombre completo y exacto.
    for d in drivers:
        if d.get("name", "").lower() == q:
            return d

    # 2) Coincidencia parcial como fallback.
    matches = [d for d in drivers if q in d.get("name", "").lower()]
    if matches:
        return matches[0]
    return None


def compute_standings(league: dict, solo_activos: bool = True) -> list:
    """Clasificación ordenada (total desc, wins desc, nombre asc). Por
    defecto excluye pilotos marcados active=False, igual que la app (un
    piloto dado de baja no desaparece de la base, pero sí de la tabla)."""
    drivers = _as_list(league.get("drivers"))
    results = league.get("results") or {}
    ps = league.get("pointsSystem") or points_system_default()
    fl_pt = league.get("fastestLapPoint", 1)
    fl_req = league.get("fastestLapRequiresPoints", True)

    totals = {
        d["id"]: {
            "name": d.get("name", "?"),
            "active": d.get("active", True),
            "total": 0,
            "wins": 0,
            "podiums": 0,
        }
        for d in drivers
        if d.get("id")
    }

    for race_entries in results.values():
        for e in _as_list(race_entries):
            did = e.get("driverId")
            if did not in totals:
                continue
            pos = e.get("position")
            dnf = e.get("dnf", False)
            pts = 0
            earned = False
            if not dnf and pos and 1 <= pos <= len(ps):
                pts += ps[pos - 1]
                earned = True
            if e.get("fastestLap") and (not fl_req or earned):
                pts += fl_pt
            totals[did]["total"] += pts
            if not dnf and pos == 1:
                totals[did]["wins"] += 1
            if not dnf and pos and pos <= 3:
                totals[did]["podiums"] += 1

    standings = sorted(totals.values(), key=lambda x: (-x["total"], -x["wins"], x["name"]))
    if solo_activos:
        standings = [d for d in standings if d.get("active", True) is not False]
    return standings


def last_winner(league: dict):
    """(nombre_ganador, nombre_carrera) de la última carrera con resultados
    cargados, u None si todavía no se corrió ninguna. Misma lógica que usa
    la app: entre las carreras que ya tienen resultados, la de fecha más
    reciente; de ahí, el piloto en P1 que no marcó DNF."""
    races = _as_list(league.get("races"))
    results = league.get("results") or {}

    con_resultados = [r for r in races if r.get("id") and _as_list(results.get(r["id"]))]
    if not con_resultados:
        return None

    con_resultados.sort(key=lambda r: r.get("date") or "")
    ultima = con_resultados[-1]
    entradas = _as_list(results.get(ultima["id"]))
    ganador_entry = next((e for e in entradas if not e.get("dnf") and e.get("position") == 1), None)
    if not ganador_entry:
        return None

    drivers = _as_list(league.get("drivers"))
    driver = next((d for d in drivers if d.get("id") == ganador_entry.get("driverId")), None)
    if not driver:
        return None
    return driver.get("name", "?"), ultima.get("name", "?")


def make_standings_embed(standings: list, league_name: str, categoria_key: str):
    cat = cat_label_for(categoria_key)
    embed = discord.Embed(
        title=f"🏆 Clasificación {cat} — {league_name}",
        color=cat_color_for(categoria_key),
    )
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, d in enumerate(standings[:15]):
        pos_str = medals[i] if i < 3 else f"`{i+1:2d}.`"
        lines.append(f"{pos_str} **{d['name']}** — `{d['total']} pts`")
    embed.description = "\n".join(lines) if lines else "Sin datos aún."
    embed.set_footer(text="GT3 Platinum Cup • Actualizado ahora")
    return embed


def build_ai_context(league: dict, categoria_key: str) -> str:
    """Resumen LIMPIO en texto plano para pasarle a la IA — sin IDs internos
    de Firebase ni JSON crudo. Antes se le mandaba el dump JSON completo de
    la liga truncado a N caracteres: eso filtraba los ids de piloto/equipo/
    carrera, y si el corte caía a mitad de un objeto la IA alucinaba
    respuestas raras a partir de JSON roto. Ahora recibe solo nombres,
    posiciones y puntos ya calculados."""
    label = cat_label_for(categoria_key)
    league_name = league.get("leagueName") or label
    standings = compute_standings(league)

    lines = [f"Categoría: {label} ({league_name})", ""]

    if standings:
        lines.append("Clasificación actual (posición — piloto — puntos):")
        for i, d in enumerate(standings[:10], start=1):
            lines.append(f"{i}. {d['name']} — {d['total']} pts")
    else:
        lines.append("Todavía no hay pilotos con puntos en esta categoría.")

    winner = last_winner(league)
    lines.append("")
    if winner:
        nombre, carrera = winner
        lines.append(f"Último ganador: {nombre} (carrera: {carrera})")
    else:
        lines.append("Todavía no se cargó el resultado de ninguna carrera.")

    return "\n".join(lines)
