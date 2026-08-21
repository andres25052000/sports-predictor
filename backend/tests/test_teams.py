"""
Tests de la ficha de equipos (teams_db.py) y sus endpoints, sin tocar la base.

Cubren la perspectiva del equipo en un partido, el resumen de récord, el
buscador del catálogo, el ranking por Elo y el perfil completo con un cliente
de Supabase falso. Incluye una regresión del orden de rutas en main.py.
"""

import main
import teams_db


# ── Perspectiva del equipo ────────────────────────────────────────────────────

def test_vista_del_equipo_como_local_y_visitante():
    """Uso esperado: goles a favor/en contra y rival según el lado del equipo."""
    partido = {"home_team_id": 1, "away_team_id": 2, "home_team": "Colombia",
               "away_team": "Brasil", "home_goals": 2, "away_goals": 1,
               "match_date": "2026-06-27", "tournament": "FIFA World Cup",
               "category": "mundial", "neutral": False}

    local = teams_db._as_team_view(partido, 1)
    assert local["goals_for"] == 2 and local["goals_against"] == 1
    assert local["opponent"] == "Brasil" and local["result"] == "V"
    assert local["was_home"] is True

    visita = teams_db._as_team_view(partido, 2)
    assert visita["goals_for"] == 1 and visita["goals_against"] == 2
    assert visita["opponent"] == "Colombia" and visita["result"] == "D"


def test_vista_en_cancha_neutral_no_cuenta_como_local():
    """Caso límite: en cancha neutral el partido no es 'de local'."""
    partido = {"home_team_id": 1, "away_team_id": 2, "home_team": "A",
               "away_team": "B", "home_goals": 0, "away_goals": 0,
               "match_date": "2026-01-01", "category": "mundial", "neutral": True}
    v = teams_db._as_team_view(partido, 1)
    assert v["was_home"] is False and v["neutral"] is True and v["result"] == "E"


def test_vista_de_partido_sin_marcador():
    """Caso de fallo: un partido sin goles cargados se descarta (None)."""
    partido = {"home_team_id": 1, "away_team_id": 2, "home_goals": None,
               "away_goals": None, "match_date": "2026-01-01"}
    assert teams_db._as_team_view(partido, 1) is None


# ── Récord ────────────────────────────────────────────────────────────────────

def _v(result, gf, ga):
    """Construye una vista de partido mínima para los tests de récord."""
    return {"result": result, "goals_for": gf, "goals_against": ga}


def test_record_suma_puntos_y_promedios():
    """Uso esperado: V/E/D, goles, % de victoria y puntos por partido."""
    r = teams_db._record([_v("V", 3, 0), _v("E", 1, 1), _v("D", 0, 2), _v("V", 2, 1)])
    assert r["played"] == 4 and r["wins"] == 2 and r["draws"] == 1 and r["losses"] == 1
    assert r["goals_for"] == 6 and r["goals_against"] == 4
    assert r["win_pct"] == 50.0
    assert r["pts_per_game"] == 1.75      # (3*2 + 1) / 4


def test_record_vacio():
    """Caso límite: sin partidos devuelve {} (la ficha oculta el bloque)."""
    assert teams_db._record([]) == {}


# ── Buscador del catálogo ─────────────────────────────────────────────────────

def test_buscador_prioriza_los_que_empiezan_por_la_query(monkeypatch):
    """Uso esperado: 'col' pone Colombia antes que Recoleta."""
    monkeypatch.setattr(teams_db, "_load_teams", lambda: [
        {"id": 1, "name": "Recoleta Colegial", "type": "club", "country": "AR"},
        {"id": 2, "name": "Colombia", "type": "national", "country": "Colombia"},
    ])
    assert [t["name"] for t in teams_db.search_teams("col")] == [
        "Colombia", "Recoleta Colegial"]


def test_buscador_ignora_query_corta():
    """Caso de fallo: menos de 2 caracteres no busca nada."""
    assert teams_db.search_teams("c") == []


# ── Ranking por Elo ───────────────────────────────────────────────────────────

def test_ranking_ordena_por_elo_y_enlaza_el_id(monkeypatch):
    """Uso esperado: ordena por Elo desc y adjunta el id de scouting."""
    monkeypatch.setattr(teams_db, "_load_form", lambda: {
        "1": {"name": "Colombia", "elo": 1900.4, "pts_per_game": 2.1},
        "2": {"name": "Brasil", "elo": 2050.9, "pts_per_game": 2.4},
        "3": {"name": "SinElo"},
    })
    monkeypatch.setattr(teams_db, "_load_teams", lambda: [
        {"id": 11, "name": "Colombia", "type": "national"},
        {"id": 22, "name": "Brasil", "type": "national"},
    ])
    ranking = teams_db.get_team_rankings(10)
    assert [t["name"] for t in ranking] == ["Brasil", "Colombia"]
    assert ranking[0]["id"] == 22 and ranking[0]["elo"] == 2050.9


# ── Perfil completo ───────────────────────────────────────────────────────────

class _FakeQuery:
    """Consulta encadenable que imita a postgrest-py."""

    def __init__(self, rows):
        self._rows = rows
        self._served = False

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def or_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def range(self, start, end):
        # Devuelve las filas solo en la primera página (corta la paginación).
        self._served = start > 0
        return self

    def execute(self):
        return type("Res", (), {"data": [] if self._served else self._rows})()


class _FakeSupabase:
    """Cliente falso: devuelve filas preparadas por nombre de tabla."""

    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def test_perfil_de_equipo(monkeypatch):
    """Uso esperado: récord, splits, forma, goleadores y bloque de modelo."""
    monkeypatch.setattr(teams_db, "_load_teams", lambda: [
        {"id": 7, "name": "Colombia", "type": "national", "country": "Colombia"}])
    monkeypatch.setattr(teams_db, "_form_by_name", lambda: {
        "colombia": {"name": "Colombia", "elo": 1900.4, "pts_per_game": 2.1}})
    monkeypatch.setattr(teams_db, "_dixon_coles_strength", lambda n: {
        "attack": 0.3, "defense": 0.2, "attack_pctile": 88,
        "defense_pctile": 80, "teams_in_model": 321})
    monkeypatch.setattr(teams_db, "get_client", lambda: _FakeSupabase({
        "scouting_matches": [
            {"id": 1, "match_date": "2026-06-27", "tournament": "FIFA World Cup",
             "category": "mundial", "home_team_id": 7, "away_team_id": 8,
             "home_team": "Colombia", "away_team": "Brasil",
             "home_goals": 2, "away_goals": 1, "neutral": False},
            {"id": 2, "match_date": "2026-03-01", "tournament": "Friendly",
             "category": "amistoso", "home_team_id": 9, "away_team_id": 7,
             "home_team": "Perú", "away_team": "Colombia",
             "home_goals": 3, "away_goals": 0, "neutral": False},
        ],
        "scouting_match_team_stats": [
            {"possession": 55.0, "shots": 12, "shots_on_target": 5,
             "corners": 6, "fouls_committed": 10, "yellow_cards": 2,
             "red_cards": 0, "xg": "1.8"},
        ],
        "scouting_match_events": [
            {"event_type": "goal", "detail": {"scorer": "Luis Díaz"}},
            {"event_type": "penalty_goal", "detail": {"scorer": "Luis Díaz"}},
            {"event_type": "goal", "detail": {"scorer": "James Rodríguez"}},
        ],
    }))

    p = teams_db.get_team_profile(7)

    assert p["team"]["name"] == "Colombia"
    assert p["record"]["played"] == 2 and p["record"]["wins"] == 1
    assert p["splits"]["home"]["played"] == 1 and p["splits"]["away"]["played"] == 1
    assert p["form"] == ["V", "D"]                    # más reciente primero
    assert p["recent_matches"][0]["opponent"] == "Brasil"
    assert [c["category"] for c in p["by_category"]] == ["mundial", "amistoso"]
    assert p["stats"]["avg"]["xg"] == {"value": 1.8, "n": 1}
    assert p["top_scorers"][0] == {"name": "Luis Díaz", "goals": 2, "penalties": 1}
    assert p["model"]["elo"] == 1900.4
    assert p["model"]["strength"]["attack_pctile"] == 88


def test_perfil_de_equipo_inexistente(monkeypatch):
    """Caso de fallo: un id que no existe devuelve None (el endpoint da 404)."""
    monkeypatch.setattr(teams_db, "_load_teams", lambda: [])
    monkeypatch.setattr(teams_db, "get_client", lambda: _FakeSupabase({}))
    assert teams_db.get_team_profile(123) is None


# ── Endpoints ─────────────────────────────────────────────────────────────────

def test_endpoint_ficha_de_equipo(monkeypatch):
    """Uso esperado: GET /teams/{id} responde 200 con la ficha."""
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.teams_db, "get_team_profile",
                        lambda tid: {"team": {"id": tid, "name": "Colombia"}})
    res = TestClient(main.app).get("/teams/7")
    assert res.status_code == 200 and res.json()["team"]["name"] == "Colombia"


def test_endpoint_equipo_inexistente(monkeypatch):
    """Caso de fallo: un equipo que no existe responde 404, no 500."""
    from fastapi.testclient import TestClient
    monkeypatch.setattr(main.teams_db, "get_team_profile", lambda tid: None)
    assert TestClient(main.app).get("/teams/999999").status_code == 404


def test_la_ruta_dinamica_no_tapa_las_estaticas():
    """Regresión: /teams/{id} se declara al final para no capturar /teams/search.

    Si la ruta dinámica se declara antes, FastAPI intenta convertir "search" a
    int y responde 422 sin probar la ruta estática, rompiendo el buscador que
    usa el formulario de partido manual.
    """
    from fastapi.testclient import TestClient
    c = TestClient(main.app)
    assert c.get("/teams/search?q=re").status_code == 200
    assert c.get("/teams/directory?q=re").status_code == 200
    assert c.get("/teams/rankings?limit=3").status_code == 200
