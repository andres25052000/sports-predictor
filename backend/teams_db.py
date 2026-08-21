"""
teams_db.py
===========
Base propia de equipos (tablas ``scouting_*``): buscador, ranking de selecciones
por Elo y perfil histórico de un equipo.

El perfil sale de los ~221k partidos ya cargados, así que funciona igual para
clubes y selecciones. Para las selecciones se añade el bloque de modelo (Elo y
fuerza de ataque/defensa de Dixon-Coles) que ya calculan los artefactos de `ml/`.
"""

import json
import os
from collections import Counter, defaultdict

from supabase_client import get_client

DATA_DIR = os.path.join(os.path.dirname(__file__), "ml", "data")

# Categorías de torneo en el orden en que se muestran en la ficha.
_CATEGORY_ORDER = ["mundial", "continental", "eliminatoria", "amistoso", "otro"]

_MATCH_FIELDS = ("id,match_date,tournament,category,competition_type,"
                 "home_team_id,away_team_id,home_team,away_team,"
                 "home_goals,away_goals,neutral")


# ── Listado y búsqueda ────────────────────────────────────────────────────────

_teams_cache: list[dict] | None = None


def _load_teams() -> list[dict]:
    """Carga y cachea el catálogo de equipos (970 filas, no cambia en runtime).

    Returns:
        list[dict]: Equipos con id, name, type (national|club) y country.
    """
    global _teams_cache
    if _teams_cache is not None:
        return _teams_cache

    sb = get_client()
    if not sb:
        return []

    rows: list[dict] = []
    page, offset = 1000, 0
    while True:
        try:
            res = (sb.table("scouting_teams")
                     .select("id,name,type,country")
                     .range(offset, offset + page - 1)
                     .execute())
        except Exception as e:
            print(f"[Supabase] Error cargando equipos: {e}")
            break
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    rows.sort(key=lambda t: (t.get("name") or "").lower())
    _teams_cache = rows
    print(f"[Supabase] {len(rows)} equipos cargados en cache")
    return rows


def search_teams(query: str, limit: int = 20) -> list[dict]:
    """Busca equipos por nombre (subcadena, sin distinguir mayúsculas).

    Args:
        query (str): Texto a buscar. Menos de 2 caracteres devuelve vacío.
        limit (int): Número máximo de resultados.

    Returns:
        list[dict]: Equipos que coinciden; los que empiezan por la búsqueda van
            primero (para que "col" muestre Colombia antes que Rocolombia).
    """
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []
    hits = [t for t in _load_teams() if q in (t.get("name") or "").lower()]
    hits.sort(key=lambda t: (not (t.get("name") or "").lower().startswith(q),
                             (t.get("name") or "").lower()))
    return hits[: max(1, min(limit, 100))]


# ── Bloque de modelo (solo selecciones) ───────────────────────────────────────

_form_cache: dict | None = None


def _load_form() -> dict:
    """Carga `ml/data/national_form.json` (forma y Elo por selección)."""
    global _form_cache
    if _form_cache is None:
        try:
            with open(os.path.join(DATA_DIR, "national_form.json"), encoding="utf-8") as f:
                _form_cache = json.load(f)
        except Exception:
            _form_cache = {}
    return _form_cache


def _form_by_name() -> dict[str, dict]:
    """Indexa la forma precalculada por nombre de selección."""
    return {(v.get("name") or "").lower(): v for v in _load_form().values()}


def _dixon_coles_strength(name: str) -> dict | None:
    """Fuerza de ataque y defensa de una selección según el modelo nacional.

    Args:
        name (str): Nombre de la selección tal como está en el modelo.

    Returns:
        dict | None: `attack`/`defense` (parámetros centrados en 0) y su
            percentil entre las 321 selecciones; None si no está en el modelo.
    """
    from ml import dixon_coles

    p = dixon_coles._load_national()
    teams = p.get("teams") or []
    if not teams:
        return None
    match = dixon_coles._match_team(name, teams)
    if not match:
        return None

    i = teams.index(match)
    att, dff = p["att"], p["dff"]
    # Reason: en el modelo, log(goles) = mu + att[equipo] + dff[rival], así que
    # un `dff` alto significa que le meten más goles -> defensa peor. Se invierte
    # el signo para que en la ficha "más alto = mejor" en las dos barras.
    attack, defense = att[i], -dff[i]
    n = len(teams)
    return {
        "attack":            round(attack, 3),
        "defense":           round(defense, 3),
        "attack_pctile":     round(100 * sum(1 for v in att if v < attack) / n),
        "defense_pctile":    round(100 * sum(1 for v in dff if -v < defense) / n),
        "teams_in_model":    n,
    }


def get_team_rankings(limit: int = 25) -> list[dict]:
    """Ranking de selecciones por Elo (del artefacto `national_form.json`).

    Args:
        limit (int): Número de selecciones a devolver.

    Returns:
        list[dict]: Selecciones con id de scouting (para enlazar a su ficha),
            nombre, elo, puntos por partido y forma de los últimos 5.
    """
    by_id = {(t.get("name") or "").lower(): t["id"]
             for t in _load_teams() if t.get("type") == "national"}

    out: list[dict] = []
    for entry in _load_form().values():
        name = entry.get("name") or ""
        elo = entry.get("elo")
        if not name or elo is None:
            continue
        out.append({
            "id":           by_id.get(name.lower()),
            "name":         name,
            "elo":          round(float(elo), 1),
            "pts_per_game": entry.get("pts_per_game"),
            "wins_last5":   entry.get("wins_last5"),
            "draws_last5":  entry.get("draws_last5"),
            "losses_last5": entry.get("losses_last5"),
        })

    out.sort(key=lambda t: t["elo"], reverse=True)
    return out[: max(1, min(limit, 250))]


# ── Perfil de equipo ──────────────────────────────────────────────────────────

def _fetch_team_matches(sb, team_id: int) -> list[dict]:
    """Trae todos los partidos jugados por un equipo (local o visitante).

    Args:
        sb: Cliente de Supabase.
        team_id (int): Id en `scouting_teams`.

    Returns:
        list[dict]: Partidos con marcador, torneo y categoría.
    """
    rows: list[dict] = []
    page, offset = 1000, 0
    while True:
        try:
            res = (sb.table("scouting_matches")
                     .select(_MATCH_FIELDS)
                     .or_(f"home_team_id.eq.{team_id},away_team_id.eq.{team_id}")
                     .order("match_date", desc=True)
                     .range(offset, offset + page - 1)
                     .execute())
        except Exception as e:
            print(f"[Supabase] Error cargando partidos del equipo {team_id}: {e}")
            break
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
        if offset >= 4000:      # Reason: tope de seguridad; ningún equipo llega.
            break
    return rows


def _as_team_view(match: dict, team_id: int) -> dict | None:
    """Reescribe un partido desde la perspectiva del equipo.

    Args:
        match (dict): Fila de `scouting_matches`.
        team_id (int): Equipo desde cuyo punto de vista se mira el partido.

    Returns:
        dict | None: Partido con `goals_for`/`goals_against`/`result`/`opponent`,
            o None si el partido no tiene marcador.
    """
    hg, ag = match.get("home_goals"), match.get("away_goals")
    if hg is None or ag is None:
        return None
    is_home = match.get("home_team_id") == team_id
    gf, ga = (hg, ag) if is_home else (ag, hg)
    return {
        "date":          match.get("match_date"),
        "tournament":    match.get("tournament"),
        "category":      match.get("category") or "otro",
        "opponent":      match.get("away_team") if is_home else match.get("home_team"),
        "was_home":      is_home and not match.get("neutral"),
        "neutral":       bool(match.get("neutral")),
        "goals_for":     gf,
        "goals_against": ga,
        "result":        "V" if gf > ga else "E" if gf == ga else "D",
    }


def _record(views: list[dict]) -> dict:
    """Resume una lista de partidos en récord (V/E/D), goles y puntos.

    Args:
        views (list[dict]): Partidos ya vistos desde el equipo (`_as_team_view`).

    Returns:
        dict: played, wins, draws, losses, goals_for, goals_against, win_pct
            y pts_per_game ({} si la lista está vacía).
    """
    if not views:
        return {}
    n = len(views)
    wins = sum(1 for v in views if v["result"] == "V")
    draws = sum(1 for v in views if v["result"] == "E")
    losses = n - wins - draws
    gf = sum(v["goals_for"] for v in views)
    ga = sum(v["goals_against"] for v in views)
    return {
        "played":        n,
        "wins":          wins,
        "draws":         draws,
        "losses":        losses,
        "goals_for":     gf,
        "goals_against": ga,
        "goals_avg":     round(gf / n, 2),
        "conceded_avg":  round(ga / n, 2),
        "win_pct":       round(100 * wins / n, 1),
        "pts_per_game":  round((3 * wins + draws) / n, 2),
    }


_STAT_FIELDS = ("possession", "shots", "shots_on_target", "corners",
                "fouls_committed", "yellow_cards", "red_cards", "xg")


def _avg_stats(sb, team_id: int) -> dict:
    """Promedios de las stats detalladas del equipo (cuando existen).

    Args:
        sb: Cliente de Supabase.
        team_id (int): Id en `scouting_teams`.

    Returns:
        dict: `matches` (partidos con datos) y `avg` por métrica; {} si no hay.
    """
    rows: list[dict] = []
    page, offset = 1000, 0
    while True:
        try:
            res = (sb.table("scouting_match_team_stats")
                     .select(",".join(_STAT_FIELDS))
                     .eq("team_id", team_id)
                     .range(offset, offset + page - 1)
                     .execute())
        except Exception as e:
            print(f"[Supabase] Error cargando stats del equipo {team_id}: {e}")
            break
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page or offset >= 3000:
            break
        offset += page

    if not rows:
        return {}

    avg: dict[str, float] = {}
    for field in _STAT_FIELDS:
        vals = []
        for r in rows:
            v = r.get(field)
            if v is None:
                continue
            try:
                vals.append(float(v))
            except (TypeError, ValueError):
                continue
        if vals:
            # Reason: cada métrica tiene su propia cobertura (el xG solo existe
            # en los torneos de StatsBomb), así que se guarda el n de cada una.
            avg[field] = {"value": round(sum(vals) / len(vals), 2), "n": len(vals)}

    return {"matches": len(rows), "avg": avg}


def _top_scorers(sb, team_id: int, limit: int = 10) -> list[dict]:
    """Máximos goleadores históricos del equipo.

    Args:
        sb: Cliente de Supabase.
        team_id (int): Id en `scouting_teams`.
        limit (int): Número de goleadores a devolver.

    Returns:
        list[dict]: Goleadores con nombre, goles y penales, de mayor a menor.
    """
    rows: list[dict] = []
    page, offset = 1000, 0
    while True:
        try:
            res = (sb.table("scouting_match_events")
                     .select("event_type,detail")
                     .eq("team_id", team_id)
                     .in_("event_type", ["goal", "penalty_goal"])
                     .range(offset, offset + page - 1)
                     .execute())
        except Exception as e:
            print(f"[Supabase] Error cargando goleadores del equipo {team_id}: {e}")
            break
        batch = res.data or []
        rows.extend(batch)
        if len(batch) < page or offset >= 3000:
            break
        offset += page

    goals: Counter = Counter()
    penalties: Counter = Counter()
    for r in rows:
        scorer = (r.get("detail") or {}).get("scorer")
        if not scorer:
            continue
        goals[scorer] += 1
        if r.get("event_type") == "penalty_goal":
            penalties[scorer] += 1

    return [{"name": name, "goals": n, "penalties": penalties[name]}
            for name, n in goals.most_common(limit)]


def get_team_profile(team_id: int) -> dict | None:
    """Ficha completa de un equipo: histórico, forma, stats y modelo.

    Args:
        team_id (int): Id en `scouting_teams`.

    Returns:
        dict | None: Perfil con `team`, `record`, `splits`, `by_category`,
            `form`, `recent_matches`, `stats`, `top_scorers` y `model`
            (solo selecciones); None si el equipo no existe.
    """
    sb = get_client()
    if not sb:
        return None

    team = next((t for t in _load_teams() if t.get("id") == team_id), None)
    if not team:
        return None

    matches = _fetch_team_matches(sb, team_id)
    views = [v for v in (_as_team_view(m, team_id) for m in matches) if v]
    views.sort(key=lambda v: v["date"] or "", reverse=True)

    by_category: dict[str, list] = defaultdict(list)
    for v in views:
        by_category[v["category"]].append(v)

    name = team.get("name") or ""
    model = None
    if team.get("type") == "national":
        form = _form_by_name().get(name.lower()) or {}
        strength = _dixon_coles_strength(name)
        if form or strength:
            model = {
                "elo":          round(float(form["elo"]), 1) if form.get("elo") else None,
                "pts_per_game": form.get("pts_per_game"),
                "strength":     strength,
            }

    return {
        "team": {
            "id":      team.get("id"),
            "name":    name,
            "type":    team.get("type"),
            "country": team.get("country"),
        },
        "record":  _record(views),
        "splits": {
            "home":    _record([v for v in views if v["was_home"]]),
            "away":    _record([v for v in views if not v["was_home"] and not v["neutral"]]),
            "neutral": _record([v for v in views if v["neutral"]]),
        },
        "by_category": [
            {"category": cat, **_record(by_category[cat])}
            for cat in _CATEGORY_ORDER if by_category.get(cat)
        ],
        "form":           [v["result"] for v in views[:10]],
        "recent_matches": views[:10],
        "stats":          _avg_stats(sb, team_id),
        "top_scorers":    _top_scorers(sb, team_id),
        "model":          model,
    }
