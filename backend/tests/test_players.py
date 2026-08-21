"""
Tests de la lógica de jugadores en players_db.py (sin llamadas a la base).

Cubren get_top_scorers (orden y límite), search_players (subcadena y longitud
mínima) y los ayudantes de la tarjeta de jugador (edad, agregados de stats y
reparto de goles), inyectando el cache en memoria para no depender de Supabase.
"""

from datetime import date

import players_db as sbc


def _player(name, goals, nat="X"):
    """Construye un jugador mínimo para los tests."""
    return {
        "id": abs(hash(name)) % 100000,
        "name": name,
        "national_team": nat,
        "current_club": None,
        "position": None,
        "goals": goals,
        "penalties": 0,
        "own_goals": 0,
        "matches_scored": None,
        "first_year": 2000,
        "last_year": 2026,
    }


def _seed(players):
    """Ordena e inyecta el cache como lo hace _load_players()."""
    sbc._players_cache = sorted(players, key=lambda p: p["goals"], reverse=True)


def test_top_scorers_orden_y_limite():
    """Uso esperado: devuelve los N con más goles, ordenados desc."""
    _seed([_player("A", 10), _player("B", 30), _player("C", 20)])
    top = sbc.get_top_scorers(2)
    assert [p["name"] for p in top] == ["B", "C"]


def test_search_ignora_query_corta():
    """Caso límite: una query de menos de 2 caracteres no busca nada."""
    _seed([_player("Messi", 71)])
    assert sbc.search_players("m") == []


def test_search_sin_coincidencias():
    """Caso de fallo: sin coincidencias devuelve lista vacía."""
    _seed([_player("Messi", 71), _player("Ronaldo", 124)])
    assert sbc.search_players("zzz") == []


def test_search_encuentra_subcadena_case_insensitive():
    """Uso esperado: encuentra por subcadena sin distinguir mayúsculas."""
    _seed([_player("Lionel Messi", 71), _player("Cristiano Ronaldo", 124)])
    names = [p["name"] for p in sbc.search_players("MESS")]
    assert names == ["Lionel Messi"]


# ── Tarjeta de jugador ────────────────────────────────────────────────────────

def test_edad_desde_fecha_de_nacimiento():
    """Uso esperado: la edad se calcula respetando si ya cumplió años."""
    hoy = date.today()
    assert sbc._age_from(f"{hoy.year - 30:04d}-01-01") in (29, 30)
    assert sbc._age_from(f"{hoy.year - 30:04d}-{hoy.month:02d}-{hoy.day:02d}") == 30


def test_edad_con_fecha_invalida_o_vacia():
    """Caso de fallo: una fecha ausente o corrupta no rompe la tarjeta."""
    assert sbc._age_from(None) is None
    assert sbc._age_from("no-es-fecha") is None


def _stat(goals=0, assists=0, xg=None, position=None):
    """Construye una fila de stats por partido para los tests."""
    return {
        "date": "2022-12-18", "goals": goals, "assists": assists, "shots": 3,
        "shots_on_target": 1, "xg": xg, "passes": 40, "key_passes": 2,
        "fouls": 1, "position": position,
    }


def test_resumen_de_stats_totales_y_promedios():
    """Uso esperado: suma totales, promedia por partido y toma la posición usual."""
    resumen = sbc._summarize_stats([
        _stat(goals=2, assists=1, xg=1.5, position="Right Wing"),
        _stat(goals=0, assists=1, xg=0.5, position="Right Wing"),
        _stat(goals=1, assists=0, xg=None, position="Center Forward"),
    ])
    assert resumen["matches"] == 3
    assert resumen["totals"]["goals"] == 3
    assert resumen["totals"]["xg"] == 2.0
    assert resumen["per_match"]["goals"] == 1.0
    assert resumen["position"] == "Right Wing"


def test_resumen_sin_stats_devuelve_vacio():
    """Caso límite: un jugador sin partidos de StatsBomb no rompe el perfil."""
    assert sbc._summarize_stats([]) == {}


def test_reparto_de_goles_por_categoria_y_ano():
    """Uso esperado: agrupa por torneo y por año, ignorando los autogoles."""
    goles = [
        {"date": "2022-12-18", "category": "mundial", "own_goal": False},
        {"date": "2022-11-26", "category": "mundial", "own_goal": False},
        {"date": "2021-07-10", "category": "continental", "own_goal": False},
        {"date": "2021-07-06", "category": "continental", "own_goal": True},
    ]
    reparto = sbc._goals_breakdown(goles)
    assert reparto["by_category"] == {"mundial": 2, "continental": 1}
    assert reparto["by_year"] == [{"year": "2021", "goals": 1}, {"year": "2022", "goals": 2}]


def test_perfil_sin_conexion_devuelve_none(monkeypatch):
    """Caso de fallo: sin cliente de Supabase el perfil devuelve None (no explota)."""
    monkeypatch.setattr(sbc, "get_client", lambda: None)
    assert sbc.get_player_profile(1) is None


class _FakeQuery:
    """Consulta encadenable que imita a postgrest-py y devuelve filas fijas."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):  # noqa: D102 - imita la API de postgrest
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        return type("Res", (), {"data": self._rows})()


class _FakeSupabase:
    """Cliente falso: devuelve filas preparadas por nombre de tabla."""

    def __init__(self, tables):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def test_perfil_completo_cruza_ficha_goles_y_stats(monkeypatch):
    """Uso esperado: el perfil junta ficha, goles con rival y stats por partido."""
    fake = _FakeSupabase({
        "scouting_players": [{
            "id": 9081, "name": "Lionel Messi", "birthdate": "1987-06-24",
            "nationality": "Argentina", "position": "centrocampista",
            "national_team": "Argentina", "current_club": "Inter de Miami",
            "wikidata_id": "Q615",
            "career_stats": {"goals": 71, "penalties": 14, "own_goals": 0,
                             "matches_scored": 53, "first_year": 2006,
                             "last_year": 2026},
            "team_history": [
                {"team": "FC Barcelona", "start": "2004", "end": "2021", "national": False},
                {"team": "Argentina", "start": "2005", "end": None, "national": True},
            ],
        }],
        "scouting_match_events": [{
            "match_id": 964, "minute": 23, "event_type": "goal",
            "detail": {"scorer": "Lionel Messi", "scoring_team": "Argentina"},
        }],
        "scouting_matches": [{
            "id": 964, "match_date": "2022-12-18", "tournament": "FIFA World Cup",
            "category": "mundial", "home_team": "Argentina", "away_team": "France",
            "home_goals": 3, "away_goals": 3, "city": "Lusail",
            "country": "Qatar", "neutral": True,
        }],
        "scouting_player_match_stats": [{
            "match_id": 964, "minutes": None, "goals": 3, "assists": 0, "shots": 6,
            "shots_on_target": 5, "xg": "2.239", "passes": 60, "passes_completed": 50,
            "key_passes": 2, "fouls": 2, "raw": {"position": "Right Wing"},
        }],
    })
    monkeypatch.setattr(sbc, "get_client", lambda: fake)

    perfil = sbc.get_player_profile(9081)

    assert perfil["player"]["name"] == "Lionel Messi"
    assert perfil["player"]["age"] >= 38
    assert perfil["career"]["goals"] == 71
    # El rival sale del otro lado del partido, no del equipo del goleador.
    gol = perfil["recent_goals"][0]
    assert gol["opponent"] == "France" and gol["minute"] == 23
    assert perfil["goals_breakdown"]["by_category"] == {"mundial": 1}
    assert perfil["match_stats_summary"]["totals"]["xg"] == 2.24
    assert perfil["match_stats_summary"]["position"] == "Right Wing"
    # Solo los clubes van a la trayectoria de clubes.
    assert [c["team"] for c in perfil["club_history"]] == ["FC Barcelona"]


def test_perfil_de_jugador_inexistente(monkeypatch):
    """Caso de fallo: un id que no existe devuelve None (el endpoint responde 404)."""
    monkeypatch.setattr(sbc, "get_client", lambda: _FakeSupabase({"scouting_players": []}))
    assert sbc.get_player_profile(999999) is None


# ── Endpoint HTTP ─────────────────────────────────────────────────────────────

def test_endpoint_devuelve_la_tarjeta(monkeypatch):
    """Uso esperado: GET /players/{id} responde 200 con el perfil."""
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setattr(main.players_db, "get_player_profile",
                        lambda pid: {"player": {"id": pid, "name": "Lionel Messi"}})
    res = TestClient(main.app).get("/players/9081")
    assert res.status_code == 200
    assert res.json()["player"]["name"] == "Lionel Messi"


def test_endpoint_404_si_no_existe(monkeypatch):
    """Caso de fallo: un jugador inexistente responde 404, no 500."""
    from fastapi.testclient import TestClient
    import main

    monkeypatch.setattr(main.players_db, "get_player_profile", lambda pid: None)
    res = TestClient(main.app).get("/players/999999")
    assert res.status_code == 404
