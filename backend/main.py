from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from predictor import predict
from mock_data import LEAGUES, TEAMS
from poisson_predictor import predict_poisson
from corners_cards_predictor import predict_corners_cards
import football_api as fapi
import api_sports as asports
import weather_api as wapi
import supabase_client as sbc
import players_db
import odds_api
import nba_predictor
import ensemble
from ml import dixon_coles
import result_checker
import asyncio

app = FastAPI(title="Sports Predictor API", version="3.1.0")


async def _result_checker_loop():
    """Revisa resultados pendientes cada hora en segundo plano."""
    await asyncio.sleep(30)  # esperar 30s al arrancar antes del primer check
    while True:
        try:
            n = await asyncio.get_event_loop().run_in_executor(
                None, result_checker.check_and_update_pending
            )
            if n:
                print(f"[Scheduler] {n} resultado(s) actualizados automaticamente")
        except Exception as e:
            print(f"[Scheduler] Error en result_checker: {e}")
        await asyncio.sleep(3600)  # cada hora


def _refresh_national_data() -> dict:
    """
    Descarga el dataset de partidos internacionales (se actualiza a diario en
    GitHub), recalcula Elo + forma de las selecciones del Mundial y recarga
    los caches en memoria. Idempotente; seguro de llamar en producción donde
    ml/data/*.json no existe (está gitignorado).
    """
    from ml.build_national_elo import rebuild
    summary = rebuild(download=True)
    fapi._national_form_cache = None   # invalidar cache de forma de selecciones
    import ml_predictor
    ml_predictor.reload_elo()
    return summary


async def _national_data_loop():
    """
    Refresca Elo y forma de selecciones cada 24h.
    Al arrancar, si los archivos no existen (deploy nuevo en Railway),
    los construye de inmediato.
    """
    from pathlib import Path
    data_dir = Path(__file__).parent / "ml" / "data"
    files_ok = (data_dir / "national_form.json").exists() and \
               (data_dir / "elo_ratings.json").exists()
    if files_ok:
        await asyncio.sleep(86400)  # ya hay datos: primer refresh en 24h
    while True:
        try:
            s = await asyncio.get_event_loop().run_in_executor(
                None, _refresh_national_data
            )
            print(f"[Scheduler] Datos de selecciones refrescados: {s}")
        except Exception as e:
            print(f"[Scheduler] Error refrescando datos de selecciones: {e}")
        await asyncio.sleep(86400)  # cada 24 horas


@app.on_event("startup")
async def warm_cache():
    """Pre-calienta el caché de partidos al arrancar para que la primera
    visita sea instantánea en vez de esperar todas las llamadas a la API."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    priority = [
        "Mundial FIFA",
        "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
        "Champions League", "Brasileirao Serie A", "Copa Libertadores",
    ]

    def fetch_all():
        with ThreadPoolExecutor(max_workers=9) as ex:
            list(ex.map(fapi.get_matches, priority))
        print("[Cache] Partidos pre-cargados al arrancar")

    # Ejecutar en background para no bloquear el arranque
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, fetch_all)

    # Arrancar el checker automático de resultados
    asyncio.create_task(_result_checker_loop())
    print("[Scheduler] Result checker iniciado — revisa resultados cada hora")

    # Refresco diario de Elo + forma de selecciones (y build inicial si faltan)
    asyncio.create_task(_national_data_loop())
    print("[Scheduler] Refresh de datos de selecciones iniciado — cada 24h")

import os

# En producción, FRONTEND_URL viene de la variable de entorno de Railway
# Ejemplo: https://sports-predictor.vercel.app
_frontend_url = os.getenv("FRONTEND_URL", "")
_allowed_origins = ["http://localhost:3000"]
if _frontend_url:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # cualquier deploy de Vercel
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Autenticación / autorización ──────────────────────────────────────────────
# Emails con permisos de administrador (ven toda la información). Se configuran
# en la variable de entorno ADMIN_EMAILS, separados por comas.
_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.getenv("ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def _resolve_user(authorization: str | None) -> dict:
    """Resuelve el usuario desde el header ``Authorization: Bearer <jwt>``.

    Args:
        authorization (str | None): Valor del header HTTP Authorization.

    Returns:
        dict: ``{"id", "email", "is_admin"}``. id/email son None si es anónimo
        (sin token o token inválido).
    """
    user = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1].strip()
        user = sbc.get_user_from_token(token)
    if not user:
        return {"id": None, "email": None, "is_admin": False}
    return {
        "id":       user["id"],
        "email":    user["email"],
        "is_admin": user["email"].lower() in _ADMIN_EMAILS,
    }


@app.get("/")
def root():
    return {"status": "ok", "message": "Sports Predictor API v3.0 — jugadores, estadio y clima"}


@app.get("/leagues")
def get_leagues():
    leagues = [
        {"name": name, "region": fapi.COMPETITION_REGIONS.get(name, "🌍 Internacional")}
        for name in fapi.get_leagues()
    ]
    return {"leagues": leagues}


@app.get("/players/top")
def get_top_players(limit: int = 20):
    """Máximos goleadores (goles internacionales de carrera) desde la base propia."""
    return {"players": players_db.get_top_scorers(limit)}


@app.get("/players/search")
def search_players_endpoint(q: str = ""):
    """Busca jugadores por nombre en la base propia de scouting."""
    return {"players": players_db.search_players(q)}


@app.get("/players/{player_id}")
def get_player(player_id: int):
    """Tarjeta completa de un jugador: ficha, goles de carrera y stats por partido."""
    profile = players_db.get_player_profile(player_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Jugador no encontrado")
    return profile


@app.get("/leagues/{league}/matches")
def get_matches(league: str):
    real_matches = fapi.get_matches(league)
    if real_matches:
        return {"league": league, "matches": real_matches, "source": "live"}
    if league in LEAGUES:
        return {"league": league, "matches": LEAGUES[league]["matches"], "source": "mock"}
    raise HTTPException(status_code=404, detail=f"Liga '{league}' no encontrada")


@app.get("/search")
def search_matches(q: str = ""):
    """Busca partidos próximos donde juegue el equipo indicado."""
    q_clean = q.lower().strip()
    if len(q_clean) < 2:
        return {"matches": []}

    results = []
    for league in fapi.get_leagues():
        matches = fapi.get_matches(league)
        for m in matches:
            home = (m.get("home") or "").lower()
            away = (m.get("away") or "").lower()
            if q_clean in home or q_clean in away:
                results.append({**m, "league": league})

    results.sort(key=lambda x: x.get("date") or "")
    return {"matches": results[:20]}


@app.get("/upcoming")
def get_upcoming():
    """Próximos partidos. Llama a todas las fuentes EN PARALELO para máxima velocidad."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    priority = [
        "Mundial FIFA",
        "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
        "Champions League", "Brasileirao Serie A", "Copa Libertadores",
        "Eredivisie", "Primeira Liga", "Championship", "Eurocopa",
    ]

    def fetch_fapi(league: str):
        matches = fapi.get_matches(league)
        return [(m, league) for m in matches[:4]]

    def fetch_betplay():
        matches = asports.get_betplay_fixtures(next_n=8)
        return [(m, "Liga BetPlay") for m in matches]

    all_matches = []

    with ThreadPoolExecutor(max_workers=14) as executor:
        futures = {executor.submit(fetch_fapi, league): league for league in priority}
        futures[executor.submit(fetch_betplay)] = "Liga BetPlay"

        for future in as_completed(futures):
            try:
                all_matches.extend(future.result())
            except Exception:
                pass

    all_matches.sort(key=lambda x: x[0].get("date") or "")
    result = [{**m, "league": league} for m, league in all_matches]

    # Incluir estado de cuota de API-Sports para que el frontend pueda avisar al usuario
    quota = asports.quota_status()
    return {
        "matches": result[:32],
        "betplay_quota": {
            "exhausted":  quota["exhausted"],
            "remaining":  quota["remaining"],
        },
    }


@app.get("/teams")
def get_teams():
    return {"teams": list(TEAMS.keys())}


@app.get("/teams/search")
def search_teams(q: str = ""):
    """
    Busca equipos por nombre en el índice local (sin llamadas a API externa).
    Devuelve [{"id": int, "name": str}, ...].
    Usado por el frontend para resolver team_id cuando el usuario escribe manualmente.
    """
    if len(q.strip()) < 2:
        return {"teams": []}
    results = fapi.search_teams(q.strip())
    return {"teams": results}


@app.post("/predict")
def post_prediction(body: dict, authorization: str | None = Header(default=None)):
    user = _resolve_user(authorization)
    # Opción B: solo usuarios autenticados pueden predecir.
    if not user["id"]:
        raise HTTPException(status_code=401, detail="Inicia sesión para analizar un partido")
    # Marcamos al usuario como activo (heartbeat implícito al predecir).
    sbc.touch_user_activity(user["id"])
    return run_full_prediction(body, user_id=user["id"])


@app.post("/me/heartbeat")
def heartbeat(authorization: str | None = Header(default=None)):
    """Marca al usuario autenticado como activo ahora (para 'usuarios activos')."""
    user = _resolve_user(authorization)
    if not user["id"]:
        raise HTTPException(status_code=401, detail="No autenticado")
    sbc.touch_user_activity(user["id"])
    return {"ok": True}


@app.get("/admin/stats")
def admin_stats(window_minutes: int = 5, authorization: str | None = Header(default=None)):
    """Estadísticas de usuarios (solo administrador): registrados y activos."""
    user = _resolve_user(authorization)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Solo el administrador puede ver esto")
    return sbc.get_user_stats(window_minutes=window_minutes)


def run_full_prediction(body: dict, user_id: str | None = None):
    home   = body.get("home_team")
    away   = body.get("away_team")
    league = body.get("league", "")
    match_date = (body.get("match_date") or "")[:10]

    if not home or not away:
        raise HTTPException(status_code=400, detail="Se requieren 'home_team' y 'away_team'")
    if home == away:
        raise HTTPException(status_code=400, detail="Los equipos deben ser diferentes")

    home_id = body.get("home_id")
    away_id = body.get("away_id")

    home_stats = None
    away_stats = None
    team_data  = None

    # ── Football-Data.org: forma reciente + rankings + H2H ───────────────
    h2h_data = None
    if home_id and away_id:
        home_stats = fapi.get_team_stats(home, int(home_id), league)
        away_stats = fapi.get_team_stats(away, int(away_id), league)
        standings  = fapi.get_standings(league)

        def find_ranking(name: str) -> int:
            r = standings.get(name)
            if not r:
                for n, p in standings.items():
                    if name.lower() in n.lower() or n.lower() in name.lower():
                        return p
            return r or 99

        home_recent = fapi.get_team_recent_matches(int(home_id))
        away_recent = fapi.get_team_recent_matches(int(away_id))

        # Embeber partidos recientes y team_id en stats
        # (team_id lo usa ml_predictor para buscar el Elo en tiempo real)
        home_stats["recent_matches"] = home_recent
        away_stats["recent_matches"] = away_recent
        home_stats["team_id"] = int(home_id)
        away_stats["team_id"] = int(away_id)

        # Historial directo real
        h2h_data = fapi.get_h2h(int(home_id), int(away_id))

        team_data = {
            "home": {"ranking": find_ranking(home), "league": league, "recent_matches": home_recent},
            "away": {"ranking": find_ranking(away), "league": league, "recent_matches": away_recent},
        }

    # ── API-Sports: lesionados + estadio ─────────────────────────────────
    home_injuries = []
    away_injuries = []
    stadium_info  = None

    home_team_info = asports.search_team(home)
    away_team_info = asports.search_team(away)

    if home_team_info:
        home_injuries = asports.get_injuries(home_team_info["id"])
        stadium_info  = home_team_info["venue"]
        stadium_info["home_team_logo"] = home_team_info.get("logo", "")

    if away_team_info:
        away_injuries = asports.get_injuries(away_team_info["id"])

    # Actualizar stats con lesiones reales
    if home_stats:
        home_stats["injured_players"] = len(home_injuries)
    if away_stats:
        away_stats["injured_players"] = len(away_injuries)

    # ── Open-Meteo: clima en el estadio ──────────────────────────────────
    weather_info = None
    if stadium_info and stadium_info.get("city") and match_date:
        weather_info = wapi.get_weather(stadium_info["city"], match_date)

    # ── Predicción ───────────────────────────────────────────────────────
    result = predict(
        home, away,
        home_stats, away_stats,
        weather_info, stadium_info,
        h2h_data=h2h_data,
        match_date=match_date,
    )

    if team_data:
        result["team_stats"] = team_data

    # ── Mercados Poisson (siempre se calculan) ───────────────────────────────
    poisson_home = home_stats or {"goals_scored_last5": 7, "goals_conceded_last5": 6}
    poisson_away = away_stats or {"goals_scored_last5": 6, "goals_conceded_last5": 7}
    # El Mundial se juega en cancha neutral: sin ventaja de localía
    neutral_venue = league == "Mundial FIFA"
    result["poisson"] = predict_poisson(poisson_home, poisson_away, neutral=neutral_venue)

    # ── Ensamble XGBoost + Poisson + calibración ─────────────────────────────
    # Mejora medida en backtest temporal (ml/tune_ensemble.py): baja el RPS y el
    # log-loss frente al XGBoost solo. Reemplaza las probabilidades 1X2 finales.
    try:
        poi_1x2 = (result.get("poisson") or {}).get("result_1x2")
        if poi_1x2 and result.get("probabilities"):
            result["probabilities"] = ensemble.blend_and_calibrate(
                result["probabilities"], poi_1x2
            )
            result["ensemble"] = True
    except Exception as e:
        print(f"[Ensemble] No se pudo ensamblar: {e}")

    # ── Dixon-Coles (modelo primario donde hay cobertura) ────────────────────
    # Midió mejor que el ensamble en backtest temporal (RPS ~0.195 vs ~0.212).
    # Se mezcla como señal dominante; si la liga/equipos no están cubiertos,
    # se mantiene el ensamble anterior.
    try:
        # Clubes (5 ligas) o, si no aplica, selecciones (modelo nacional).
        dc = dixon_coles.predict_runtime(league, home, away) or \
             dixon_coles.predict_national(home, away)
        if dc and result.get("probabilities"):
            result["probabilities"] = ensemble.weighted_blend(
                dc, result["probabilities"], w_primary=0.7
            )
            result["dixon_coles"] = True
            result["model"] = (result.get("model", "") + " + Dixon-Coles").strip(" +")
    except Exception as e:
        print(f"[DixonColes] No se pudo aplicar: {e}")

    # ── Córners y tarjetas (StatsBomb) ───────────────────────────────────────
    result["corners_cards"] = predict_corners_cards(home, away)

    # ── Cuotas reales + EV automático (The Odds API) ─────────────────────────
    # Best-effort: si no hay ODDS_API_KEY o la liga no está mapeada, se omite
    # sin afectar el resto de la predicción (el usuario puede seguir usando el
    # panel de valor con cuotas estimadas).
    try:
        raw_odds = odds_api.get_match_odds(home, away, league, match_date)
        annotated = odds_api.annotate_markets(
            raw_odds, result.get("probabilities", {}), result.get("poisson")
        )
        if annotated:
            result["odds"] = annotated
    except Exception as e:
        print(f"[OddsAPI] No se pudieron obtener cuotas: {e}")

    result["injuries"] = {
        "home": {"team": home, "players": home_injuries},
        "away": {"team": away, "players": away_injuries},
    }

    if stadium_info:
        result["stadium"] = stadium_info

    if weather_info:
        result["weather"] = weather_info

    # ── Guardar predicción en Supabase ───────────────────────────────────────
    try:
        probs = result.get("probabilities", {})
        ph = probs.get("home_win", 0)
        pd = probs.get("draw", 0)
        pa = probs.get("away_win", 0)

        # Determinar ganador predicho
        best_prob = max(ph, pd, pa)
        if best_prob == ph:
            pred_winner = "Local"
            confidence  = ph
        elif best_prob == pd:
            pred_winner = "Empate"
            confidence  = pd
        else:
            pred_winner = "Visitante"
            confidence  = pa

        # Capturar features del modelo para reentrenamiento futuro
        features_snapshot = None
        if home_stats and away_stats:
            features_snapshot = {
                "home_wins_last5":    home_stats.get("wins_last5", 0),
                "home_draws_last5":   home_stats.get("draws_last5", 0),
                "home_losses_last5":  home_stats.get("losses_last5", 0),
                "home_goals_scored":  home_stats.get("goals_scored_last5", 0),
                "home_goals_conceded":home_stats.get("goals_conceded_last5", 0),
                "home_possession":    home_stats.get("possession_avg", 50),
                "home_shots":         home_stats.get("shots_on_target_avg", 0),
                "home_injured":       home_stats.get("injured_players", 0),
                "away_wins_last5":    away_stats.get("wins_last5", 0),
                "away_draws_last5":   away_stats.get("draws_last5", 0),
                "away_losses_last5":  away_stats.get("losses_last5", 0),
                "away_goals_scored":  away_stats.get("goals_scored_last5", 0),
                "away_goals_conceded":away_stats.get("goals_conceded_last5", 0),
                "away_possession":    away_stats.get("possession_avg", 50),
                "away_shots":         away_stats.get("shots_on_target_avg", 0),
                "away_injured":       away_stats.get("injured_players", 0),
                "h2h_home_wins":      h2h_data.get("wins",   0) if h2h_data else 0,
                "h2h_draws":          h2h_data.get("draws",  0) if h2h_data else 0,
                "h2h_away_wins":      h2h_data.get("losses", 0) if h2h_data else 0,
                "home_elo":           home_stats.get("elo", 1500),
                "away_elo":           away_stats.get("elo", 1500),
            }

        # ── Snapshot de mercados predichos (goles, BTTS, córners, tarjetas, faltas) ──
        poisson = result.get("poisson", {}) or {}
        xg      = poisson.get("expected_goals", {}) or {}
        ou      = poisson.get("over_under", {}) or {}
        cc      = result.get("corners_cards", {}) or {}
        cc_cor  = cc.get("corners", {}) or {}
        cc_yel  = cc.get("yellow_cards", {}) or {}
        cc_fou  = cc.get("fouls", {}) or {}

        xg_home  = xg.get("home")
        xg_away  = xg.get("away")
        xg_total = xg.get("total")

        markets_snapshot = {
            "xg_home":  xg_home,
            "xg_away":  xg_away,
            "xg_total": xg_total,
            "over_under": {
                k: ou.get(k) for k in
                ("over_0.5", "over_1.5", "over_2.5", "over_3.5", "over_4.5")
                if ou.get(k) is not None
            },
            "btts_yes":          poisson.get("btts", {}).get("yes"),
            "corners_expected":  cc_cor.get("expected_total"),
            "yellow_cards_expected": cc_yel.get("expected_total"),
            "fouls_expected":    cc_fou.get("expected_total"),
        }

        pred_record = {
            "home_team":      home,
            "away_team":      away,
            "league":         league or None,
            "match_date":     match_date or None,
            "home_crest":     body.get("home_crest") or None,
            "away_crest":     body.get("away_crest") or None,
            "prob_home_win":  ph,
            "prob_draw":      pd,
            "prob_away_win":  pa,
            "pred_winner":    pred_winner,
            "confidence":     confidence,
            "model_used":     result.get("model", "hybrid"),
            "xg_home":        xg_home,
            "xg_away":        xg_away,
            # IDs para búsqueda automática de resultados
            "fd_home_id":     int(home_id) if home_id else None,
            "fd_away_id":     int(away_id) if away_id else None,
            # Features para reentrenamiento incremental
            "features_json":  features_snapshot,
            "model_version":  result.get("model", "rule-based"),
            # Mercados predichos (para medir acierto por tipo de mercado)
            "markets_json":   markets_snapshot,
            # Dueño de la predicción (null = anónimo)
            "user_id":        user_id,
        }
        saved = sbc.save_prediction(pred_record)
        if saved:
            result["prediction_id"] = saved["id"]
    except Exception as e:
        print(f"[Supabase] No se pudo guardar prediccion: {e}")

    return result


@app.get("/predictions/recent")
def recent_public(limit: int = 10):
    """Feed público: últimos partidos distintos predichos (sin datos de usuario).

    Visible para todo el mundo. Si varias personas predijeron el mismo partido,
    aparece una sola vez.
    """
    rows = sbc.get_recent_public(limit=limit)
    return {"predictions": rows, "count": len(rows)}


@app.get("/predictions/mine")
def my_predictions(limit: int = 100, offset: int = 0,
                   authorization: str | None = Header(default=None)):
    """Historial del usuario autenticado.

    - Usuario normal: solo sus propias predicciones.
    - Administrador: todas las predicciones (``is_admin: true``).
    Requiere ``Authorization: Bearer <jwt>``.
    """
    user = _resolve_user(authorization)
    if not user["id"]:
        raise HTTPException(status_code=401, detail="Inicia sesión para ver tu historial")
    # El admin ve todo (user_id=None → sin filtro); el usuario normal solo lo suyo.
    rows = sbc.get_predictions(
        limit=limit, offset=offset,
        user_id=None if user["is_admin"] else user["id"],
    )
    return {"predictions": rows, "count": len(rows), "is_admin": user["is_admin"]}


@app.get("/predictions")
def list_predictions(limit: int = 50, offset: int = 0,
                     authorization: str | None = Header(default=None)):
    """Historial completo de todas las predicciones (solo administrador)."""
    user = _resolve_user(authorization)
    if not user["is_admin"]:
        raise HTTPException(status_code=403, detail="Solo el administrador puede ver todo el historial")
    rows = sbc.get_predictions(limit=limit, offset=offset)
    return {"predictions": rows, "count": len(rows)}


@app.get("/predictions/stats")
def prediction_stats():
    """Estadísticas globales de precisión del modelo."""
    return sbc.get_stats()


@app.get("/predictions/market-stats")
def prediction_market_stats():
    """Precisión del modelo desglosada por tipo de mercado (1X2, goles, BTTS, córners, tarjetas)."""
    return sbc.get_market_stats()


@app.post("/predictions/check-results")
async def trigger_result_check():
    """Fuerza una búsqueda inmediata de resultados pendientes (sin esperar la hora)."""
    n = await asyncio.get_event_loop().run_in_executor(
        None, result_checker.check_and_update_pending
    )
    return {"updated": n, "message": f"{n} resultado(s) actualizados"}


@app.post("/predictions/retrain")
async def trigger_retrain(body: dict = {}):
    """
    Dispara reentrenamiento incremental manual del modelo.
    También refresca el Elo y la forma de selecciones con el dataset
    internacional más reciente.
    """
    force = body.get("force", False)

    try:
        national = await asyncio.get_event_loop().run_in_executor(
            None, _refresh_national_data
        )
    except Exception as e:
        national = {"error": str(e)}

    def _retrain():
        import sys, os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ml"))
        from ml.incremental_trainer import run_incremental_training
        return run_incremental_training(force=force)
    result = await asyncio.get_event_loop().run_in_executor(None, _retrain)

    if isinstance(result, dict):
        result["national_data"] = national
        return result
    return {"retrain": result, "national_data": national}


@app.get("/predictions/model-evolution")
def model_evolution():
    """Historial de evolución del modelo (accuracy por cada reentrenamiento)."""
    from pathlib import Path
    import json
    meta_path = Path(__file__).parent / "ml" / "data" / "incremental_meta.json"
    if not meta_path.exists():
        return {"history": [], "total_trained": 0, "current_version": "0.0"}
    meta = json.loads(meta_path.read_text())
    return {
        "current_version": meta.get("model_version", "0.0"),
        "total_trained":   meta.get("total_trained", 0),
        "last_run":        meta.get("last_run"),
        "history":         meta.get("accuracy_history", []),
    }


@app.patch("/predictions/{prediction_id}/result")
def update_prediction_result(prediction_id: int, body: dict):
    """
    Registra el resultado real de un partido.
    Body: { "home_goals": 2, "away_goals": 1 }
    """
    home_goals = body.get("home_goals")
    away_goals = body.get("away_goals")
    if home_goals is None or away_goals is None:
        raise HTTPException(status_code=400, detail="Se requieren 'home_goals' y 'away_goals'")
    result = sbc.update_result(prediction_id, int(home_goals), int(away_goals))
    if not result:
        raise HTTPException(status_code=404, detail=f"Prediccion {prediction_id} no encontrada o error al actualizar")
    return result


# ── NBA ───────────────────────────────────────────────────────────────────────
@app.get("/nba/teams")
def nba_teams():
    """Lista de equipos NBA disponibles (para autocompletado)."""
    return {"teams": nba_predictor.list_teams(), "ready": nba_predictor.is_ready()}


@app.get("/nba/upcoming")
def nba_upcoming():
    """Próximos partidos NBA con cuotas (vía The Odds API; vacío fuera de temporada)."""
    return {"matches": odds_api.list_nba_events()}


@app.post("/nba/predict")
def nba_predict(body: dict, authorization: str | None = Header(default=None)):
    """Predicción NBA (Elo + totales + hándicap) con cuotas/EV si hay key.

    Requiere sesión (igual que el fútbol). Body: ``{home_team, away_team}``.
    """
    user = _resolve_user(authorization)
    if not user["id"]:
        raise HTTPException(status_code=401, detail="Inicia sesión para analizar un partido")
    sbc.touch_user_activity(user["id"])

    home = (body.get("home_team") or "").strip()
    away = (body.get("away_team") or "").strip()
    if not home or not away:
        raise HTTPException(status_code=400, detail="Se requieren 'home_team' y 'away_team'")
    if home == away:
        raise HTTPException(status_code=400, detail="Los equipos deben ser diferentes")
    if not nba_predictor.is_ready():
        raise HTTPException(status_code=503, detail="El modelo NBA no está construido (corre ml.build_nba_elo)")

    result = nba_predictor.predict(home, away)

    # Cuotas reales + EV (best-effort)
    try:
        raw = odds_api.get_nba_odds(home, away)
        annotated = nba_predictor.annotate_odds(result, raw)
        if annotated:
            result["odds"] = annotated
    except Exception as e:
        print(f"[NBA] No se pudieron obtener cuotas: {e}")

    # Guardar en Supabase (sport='nba'; puntos esperados en xg_*)
    try:
        probs = result["probabilities"]
        ph, pa = probs["home_win"], probs["away_win"]
        pred_winner = "Local" if ph >= pa else "Visitante"
        ep = result["expected_points"]
        saved = sbc.save_prediction({
            "sport":         "nba",
            "league":        "NBA",
            "home_team":     home,
            "away_team":     away,
            "prob_home_win": ph,
            "prob_draw":     0,
            "prob_away_win": pa,
            "pred_winner":   pred_winner,
            "confidence":    max(ph, pa),
            "model_used":    result.get("model", "NBA Elo v1"),
            "model_version": result.get("model", "NBA Elo v1"),
            "xg_home":       ep["home"],
            "xg_away":       ep["away"],
            "user_id":       user["id"],
        })
        if saved:
            result["prediction_id"] = saved["id"]
    except Exception as e:
        print(f"[NBA] No se pudo guardar prediccion: {e}")

    return result


@app.get("/predict/{home}/{away}")
def get_prediction(home: str, away: str):
    if home == away:
        raise HTTPException(status_code=400, detail="Los equipos deben ser diferentes")
    return predict(home, away)
