"""Lógica de clasificación: cálculo de puntos, búsqueda de pilotos y embeds."""
import discord

from services.firebase import get_firebase


def points_system_default():
    return [25, 18, 15, 12, 10, 8, 6, 4, 2, 1]


def league_id_for(categoria: str) -> str:
    return "junior-league" if categoria.lower() == "junior" else "default-league"


def cat_label_for(categoria: str) -> str:
    return "JUNIOR" if categoria.lower() == "junior" else "PRO"


async def get_league(league_id: str = "default-league") -> dict:
    data = await get_firebase(f"leagues/{league_id}")
    return data or {}


async def get_penalties(league_id: str = "default-league") -> list:
    data = await get_firebase(f"leagues/{league_id}/penalties")
    if not data:
        return []
    if isinstance(data, list):
        return [p for p in data if p]
    return list(data.values())


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
    drivers = league.get("drivers") or []
    if isinstance(drivers, dict):
        drivers = list(drivers.values())
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


def compute_standings(league: dict) -> list:
    drivers = league.get("drivers") or []
    if isinstance(drivers, dict):
        drivers = list(drivers.values())
    results = league.get("results") or {}
    ps = league.get("pointsSystem") or points_system_default()
    fl_pt = league.get("fastestLapPoint", 1)
    fl_req = league.get("fastestLapRequiresPoints", True)

    totals = {d["id"]: {"name": d.get("name", "?"), "total": 0, "wins": 0, "podiums": 0} for d in drivers}

    for race_entries in results.values():
        if isinstance(race_entries, dict):
            race_entries = list(race_entries.values())
        if not isinstance(race_entries, list):
            continue
        for e in race_entries:
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

    return sorted(totals.values(), key=lambda x: (-x["total"], -x["wins"]))


def make_standings_embed(standings: list, league_name: str, league_id: str):
    cat = cat_label_for("junior" if league_id == "junior-league" else "pro")
    embed = discord.Embed(title=f"🏆 Clasificación {cat} — {league_name}", color=0xFFD600)
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, d in enumerate(standings[:15]):
        pos_str = medals[i] if i < 3 else f"`{i+1:2d}.`"
        lines.append(f"{pos_str} **{d['name']}** — `{d['total']} pts`")
    embed.description = "\n".join(lines) if lines else "Sin datos aún."
    embed.set_footer(text="GT3 Cup World Series • Actualizado ahora")
    return embed
