"""
players_db.py
=============
Base propia de jugadores (tablas ``scouting_*``): ranking de goleadores,
búsqueda por nombre y perfil completo tipo "tarjeta FIFA".

Se separó de ``supabase_client.py`` para respetar el límite de 500 líneas por
archivo y agrupar por responsabilidad.
"""

from collections import Counter
from datetime import date

from supabase_client import get_client


# ── Jugadores (tarjeta de goleador) ───────────────────────────────────────────
# La tabla scouting_players guarda los goles en career_stats (jsonb), por lo que
# PostgREST no puede ordenar numéricamente. Cargamos una vez todos los jugadores
# con goles, los ordenamos en memoria y cacheamos (los datos son históricos y no
# cambian entre reinicios).

_players_cache: list[dict] | None = None


def _load_players() -> list[dict]:
    """Carga y cachea todos los jugadores con goles, ordenados por goles desc.

    Returns:
        list[dict]: Jugadores con id, name, national_team, current_club,
            position, goals, penalties, own_goals, matches_scored, first_year
            y last_year. El `id` enlaza con la tarjeta (`get_player_profile`).
    """
    global _players_cache
    if _players_cache is not None:
        return _players_cache

    sb = get_client()
    if not sb:
        return []

    rows: list[dict] = []
    page = 1000
    offset = 0
    while True:
        try:
            res = (
                sb.table("scouting_players")
                .select("id,name,national_team,current_club,position,career_stats")
                .range(offset, offset + page - 1)
                .execute()
            )
        except Exception as e:
            print(f"[Supabase] Error cargando jugadores: {e}")
            break
        batch = res.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page

    players: list[dict] = []
    for r in rows:
        cs = r.get("career_stats") or {}
        goals = cs.get("goals")
        if goals is None:
            continue
        try:
            goals = int(goals)
        except (TypeError, ValueError):
            continue
        players.append({
            "id":             r.get("id"),
            "name":           r.get("name"),
            "national_team":  r.get("national_team"),
            "current_club":   r.get("current_club"),
            "position":       r.get("position"),
            "goals":          goals,
            "penalties":      cs.get("penalties", 0),
            "own_goals":      cs.get("own_goals", 0),
            "matches_scored": cs.get("matches_scored"),
            "first_year":     cs.get("first_year"),
            "last_year":      cs.get("last_year"),
        })

    players.sort(key=lambda p: p["goals"], reverse=True)
    _players_cache = players
    print(f"[Supabase] {len(players)} jugadores cargados en cache")
    return players


def get_top_scorers(limit: int = 20) -> list[dict]:
    """Devuelve los máximos goleadores (goles internacionales de carrera).

    Args:
        limit (int): Número máximo de jugadores a devolver.

    Returns:
        list[dict]: Jugadores ordenados por goles desc.
    """
    return _load_players()[: max(1, min(limit, 200))]


def search_players(query: str, limit: int = 20) -> list[dict]:
    """Busca jugadores por nombre (subcadena, sin distinguir acentos básicos).

    Args:
        query (str): Texto a buscar en el nombre.
        limit (int): Número máximo de resultados.

    Returns:
        list[dict]: Jugadores que coinciden, ordenados por goles desc.
    """
    q = (query or "").strip().lower()
    if len(q) < 2:
        return []
    out = [p for p in _load_players() if q in (p["name"] or "").lower()]
    return out[: max(1, min(limit, 100))]


# ── Tarjeta de jugador (perfil completo) ──────────────────────────────────────
# El perfil cruza tres fuentes ya cargadas en la base propia:
#   1. scouting_players            -> ficha (edad, posición, club, historial Wikidata)
#   2. scouting_match_events       -> cada gol internacional con fecha, rival y minuto
#   3. scouting_player_match_stats -> stats por partido de StatsBomb (xG, pases…)
# Reason: los goles se guardaron con el nombre del goleador en `detail->>scorer`
# (el ingest no resolvió player_id), así que la línea de tiempo se cruza por nombre.

_MATCH_FIELDS = ("id,match_date,tournament,category,home_team,away_team,"
                 "home_goals,away_goals,city,country,neutral")


def _fetch_matches(sb, match_ids: list[int]) -> dict[int, dict]:
    """Trae los partidos indicados y los indexa por id.

    Args:
        sb: Cliente de Supabase.
        match_ids (list[int]): Ids de partidos a buscar.

    Returns:
        dict[int, dict]: Partido por id (vacío si falla la consulta).
    """
    out: dict[int, dict] = {}
    ids = [i for i in match_ids if i]
    for chunk in (ids[i:i + 200] for i in range(0, len(ids), 200)):
        try:
            res = (sb.table("scouting_matches")
                     .select(_MATCH_FIELDS)
                     .in_("id", chunk)
                     .execute())
        except Exception as e:
            print(f"[Supabase] Error cargando partidos del jugador: {e}")
            continue
        for m in res.data or []:
            out[m["id"]] = m
    return out


def _age_from(birthdate: str | None) -> int | None:
    """Calcula la edad en años a partir de una fecha ISO (YYYY-MM-DD)."""
    if not birthdate:
        return None
    try:
        born = date.fromisoformat(str(birthdate)[:10])
    except ValueError:
        return None
    today = date.today()
    return today.year - born.year - ((today.month, today.day) < (born.month, born.day))


def _goal_timeline(sb, name: str) -> list[dict]:
    """Devuelve los goles internacionales del jugador, del más reciente al más antiguo.

    Args:
        sb: Cliente de Supabase.
        name (str): Nombre exacto del jugador tal como aparece en `detail->>scorer`.

    Returns:
        list[dict]: Goles con fecha, torneo, rival, minuto y si fue de penal.
    """
    try:
        res = (sb.table("scouting_match_events")
                 .select("match_id,minute,event_type,detail")
                 .eq("detail->>scorer", name)
                 .limit(400)
                 .execute())
    except Exception as e:
        print(f"[Supabase] Error cargando goles de {name}: {e}")
        return []

    events = res.data or []
    matches = _fetch_matches(sb, [e.get("match_id") for e in events])

    goals: list[dict] = []
    for e in events:
        m = matches.get(e.get("match_id")) or {}
        detail = e.get("detail") or {}
        team = detail.get("team")
        # El rival es el otro equipo del partido; si no sabemos el equipo del
        # goleador, mostramos el enfrentamiento completo.
        home, away = m.get("home_team"), m.get("away_team")
        opponent = away if team and team == home else home if team else None
        goals.append({
            "date":       m.get("match_date"),
            "tournament": m.get("tournament"),
            "category":   m.get("category"),
            "team":       team,
            "opponent":   opponent,
            "home_team":  home,
            "away_team":  away,
            "score":      (f"{m['home_goals']}-{m['away_goals']}"
                           if m.get("home_goals") is not None else None),
            "minute":     e.get("minute"),
            "penalty":    e.get("event_type") == "penalty_goal" or bool(detail.get("penalty")),
            "own_goal":   e.get("event_type") == "own_goal",
        })

    goals.sort(key=lambda g: g["date"] or "", reverse=True)
    return goals


def _match_stats(sb, player_id: int) -> list[dict]:
    """Stats por partido (StatsBomb) del jugador, del más reciente al más antiguo.

    Args:
        sb: Cliente de Supabase.
        player_id (int): Id en `scouting_players`.

    Returns:
        list[dict]: Una fila por partido con goles, asistencias, tiros, xG y pases.
    """
    try:
        res = (sb.table("scouting_player_match_stats")
                 .select("match_id,minutes,goals,assists,shots,shots_on_target,xg,"
                         "passes,passes_completed,key_passes,fouls,raw")
                 .eq("player_id", player_id)
                 .limit(300)
                 .execute())
    except Exception as e:
        print(f"[Supabase] Error cargando stats por partido: {e}")
        return []

    rows = res.data or []
    matches = _fetch_matches(sb, [r.get("match_id") for r in rows])

    out: list[dict] = []
    for r in rows:
        m = matches.get(r.get("match_id")) or {}
        raw = r.get("raw") or {}
        out.append({
            "date":            m.get("match_date"),
            "tournament":      m.get("tournament"),
            "home_team":       m.get("home_team"),
            "away_team":       m.get("away_team"),
            "score":           (f"{m['home_goals']}-{m['away_goals']}"
                                if m.get("home_goals") is not None else None),
            "position":        raw.get("position"),
            "minutes":         r.get("minutes"),
            "goals":           r.get("goals") or 0,
            "assists":         r.get("assists") or 0,
            "shots":           r.get("shots") or 0,
            "shots_on_target": r.get("shots_on_target") or 0,
            "xg":              _num(r.get("xg")),
            "passes":          r.get("passes") or 0,
            "key_passes":      r.get("key_passes") or 0,
            "fouls":           r.get("fouls") or 0,
        })

    out.sort(key=lambda s: s["date"] or "", reverse=True)
    return out


def _num(value) -> float | None:
    """Convierte a float los numéricos que PostgREST devuelve como texto."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summarize_stats(stats: list[dict]) -> dict:
    """Agrega las stats por partido en totales y promedios por partido.

    Args:
        stats (list[dict]): Filas devueltas por `_match_stats`.

    Returns:
        dict: Totales, promedios y la posición más frecuente ({} si no hay datos).
    """
    if not stats:
        return {}

    n = len(stats)
    total = {k: sum(s[k] for s in stats)
             for k in ("goals", "assists", "shots", "shots_on_target",
                       "passes", "key_passes", "fouls")}
    xg_vals = [s["xg"] for s in stats if s["xg"] is not None]
    total["xg"] = round(sum(xg_vals), 2) if xg_vals else None

    per_match = {k: round(v / n, 2) for k, v in total.items()
                 if k != "xg" and v is not None}
    if total["xg"] is not None:
        per_match["xg"] = round(total["xg"] / n, 2)

    positions = Counter(s["position"] for s in stats if s.get("position"))
    return {
        "matches":   n,
        "totals":    total,
        "per_match": per_match,
        "position":  positions.most_common(1)[0][0] if positions else None,
    }


def _goals_breakdown(goals: list[dict]) -> dict:
    """Reparte los goles por categoría de torneo y por año.

    Args:
        goals (list[dict]): Goles devueltos por `_goal_timeline`.

    Returns:
        dict: `by_category` (mundial, eliminatoria…) y `by_year` ordenado por año.
    """
    by_category = Counter(g["category"] or "otro" for g in goals if not g["own_goal"])
    by_year: Counter = Counter()
    for g in goals:
        if g["date"] and not g["own_goal"]:
            by_year[str(g["date"])[:4]] += 1
    return {
        "by_category": dict(by_category.most_common()),
        "by_year":     [{"year": y, "goals": by_year[y]} for y in sorted(by_year)],
    }


def get_player_profile(player_id: int) -> dict | None:
    """Perfil completo de un jugador para la tarjeta tipo FIFA/EA FC.

    Cruza la ficha (Wikidata), la línea de tiempo de goles internacionales y las
    stats por partido de StatsBomb cuando existen.

    Args:
        player_id (int): Id del jugador en `scouting_players`.

    Returns:
        dict | None: Perfil con `player`, `career`, `goals_breakdown`,
            `recent_goals`, `match_stats_summary` y `recent_matches`;
            None si el jugador no existe o no hay conexión a la base.
    """
    sb = get_client()
    if not sb:
        return None

    try:
        res = (sb.table("scouting_players")
                 .select("id,name,birthdate,nationality,position,national_team,"
                         "current_club,career_stats,team_history,wikidata_id")
                 .eq("id", player_id)
                 .limit(1)
                 .execute())
    except Exception as e:
        print(f"[Supabase] Error cargando jugador {player_id}: {e}")
        return None

    rows = res.data or []
    if not rows:
        return None
    row = rows[0]

    career = row.get("career_stats") or {}
    goals = _goal_timeline(sb, row.get("name") or "")
    stats = _match_stats(sb, player_id)

    # Reason: team_history viene de Wikidata; separamos clubes de selecciones
    # porque la tarjeta muestra la trayectoria de clubes en orden cronológico.
    history = row.get("team_history") or []
    clubs = [t for t in history if not t.get("national")]
    clubs.sort(key=lambda t: str(t.get("start") or ""))

    return {
        "player": {
            "id":            row.get("id"),
            "name":          row.get("name"),
            "birthdate":     row.get("birthdate"),
            "age":           _age_from(row.get("birthdate")),
            "nationality":   row.get("nationality"),
            "position":      row.get("position"),
            "national_team": row.get("national_team"),
            "current_club":  row.get("current_club"),
            "wikidata_id":   row.get("wikidata_id"),
        },
        "career": {
            "goals":          career.get("goals"),
            "penalties":      career.get("penalties", 0),
            "own_goals":      career.get("own_goals", 0),
            "matches_scored": career.get("matches_scored"),
            "first_year":     career.get("first_year"),
            "last_year":      career.get("last_year"),
        },
        "club_history":        clubs,
        "national_history":    [t for t in history if t.get("national")],
        "goals_breakdown":     _goals_breakdown(goals),
        "recent_goals":        goals[:25],
        "match_stats_summary": _summarize_stats(stats),
        "recent_matches":      stats[:15],
    }
