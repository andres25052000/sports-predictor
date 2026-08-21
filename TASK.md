# TASK.md

Registro de tareas del proyecto Predictor Deportivo.

## Completadas — 2026-06-15

### Comercialización: 3 features base

- [x] **Odds API real + EV automático** — `backend/odds_api.py` trae cuotas
  reales de The Odds API y calcula el EV de cada mercado; se adjunta como bloque
  `odds` en la respuesta de `/predict`. El `ValuePanel` muestra cuota real + EV y
  una sección de "valor real detectado". Tests en `backend/tests/test_odds_api.py`.
- [x] **Supabase Auth** — `frontend/lib/auth.tsx` (AuthProvider + useAuth),
  `AuthModal` (login/registro) y `AuthMenu` (en cabecera). Layout envuelto en
  `AuthProvider`.
- [x] **Página pública de track record en vivo** — `frontend/app/track-record/page.tsx`
  consume `/predictions/stats`, `/predictions/market-stats` y `/predictions`.
  Enlazada desde la barra superior y la navegación inferior.

### Multiusuario (historial general + por usuario + admin) — 2026-06-15

- [x] **Migración Supabase** — columna `user_id` (FK a `auth.users`), índice,
  RLS activado + política "users select own predictions". Aplicada en producción
  y versionada en `add_user_id_column.sql`.
- [x] **Backend** — `supabase_client.get_user_from_token`, `get_recent_public`
  (deduplicado por partido), `get_predictions(user_id=...)`. En `main.py`:
  `_resolve_user` (admin vía `ADMIN_EMAILS`), `/predict` atribuye al usuario,
  nuevos `/predictions/recent` (público) y `/predictions/mine` (sesión),
  `/predictions` ahora solo admin. Tests: `test_supabase_client.py`, `test_auth.py`.
- [x] **Historial general público** — `components/GeneralHistory.tsx` en la home:
  últimos 10 partidos distintos, sin mostrar quién los generó.
- [x] **Historial por usuario** — `/history` ahora exige sesión y muestra solo
  las predicciones del usuario; el admin ve todas + herramientas del modelo.
- [x] **Atribución** — `match/page.tsx` envía el token al predecir (espera a que
  la sesión cargue para no guardar como anónimo).
- [x] **Cambio de contraseña** — `changePassword` en `lib/auth.tsx` +
  `ChangePasswordModal.tsx`, accesible desde `AuthMenu` con sesión iniciada.
- [x] **Exigir sesión para predecir (Opción B)** — `/predict` devuelve 401 sin
  token; la home bloquea con modal de login y la página de partido muestra un
  gate. Verificado end-to-end (401 sin token, 200 con token).
- [x] **Panel de admin: usuarios registrados y activos** — tabla `user_activity`
  + función `admin_user_stats` (migración aplicada), heartbeat en `AuthProvider`,
  endpoints `/me/heartbeat` y `/admin/stats`, tarjeta en `/history` (solo admin).

### NBA (multideporte) — 2026-06-16

- [x] **Datos:** API-Sports basketball (misma key) — confirmado acceso a temporadas
  2022–2024 en plan free. `basketball_api.py` trae partidos históricos.
- [x] **Modelo:** `ml/build_nba_elo.py` (Elo + promedios de anotación + calibración
  de liga) → `nba_elo.json`, `nba_team_stats.json`, `nba_meta.json`. `nba_predictor.py`
  (win prob, totales over/under, hándicap, anotación de EV). Tests: `test_nba_predictor.py`.
- [x] **Cuotas NBA:** `odds_api.get_nba_odds` (h2h 2 vías + totales) y `list_nba_events`.
- [x] **Backend:** endpoints `/nba/teams`, `/nba/upcoming`, `/nba/predict` (requiere sesión,
  guarda con `sport='nba'`). Verificado en vivo (401 sin token, 200 con token, id guardado).
- [x] **DB:** columna `sport` (default 'soccer'); `xg_*` ampliadas a numeric(6,2) para puntos.
  Stats/feeds de fútbol filtrados a `sport='soccer'` para no mezclar.
- [x] **Frontend:** página `/nba` (selección de equipos, prob, puntos, O/U, hándicap, EV),
  enlaces en barra superior y nav inferior.
- [x] **Filtro:** equipos no-NBA (All-Star) descartados exigiendo ≥20 partidos/temporada.

### Mejora del modelo de futbol - Fase 12 (2 Jul 2026)

- [x] **Medicion honesta (RPS/log-loss)** - `ml/backtest.py` con holdout TEMPORAL.
  Hallazgo: la accuracy real out-of-sample es ~49% (no el 67% del split aleatorio).
  Linea base: accuracy 0.489, log-loss 1.03, RPS 0.213.
- [x] **Ensamble XGBoost + Poisson + calibracion por temperatura** - `ml/tune_ensemble.py`
  busca el peso w y la temperatura T optimos por RPS en validacion. Ganador:
  w=0.6 (60% XGBoost / 40% Poisson), T=1.1. Mejora en test: accuracy 0.480->0.492,
  RPS 0.217->0.212, log-loss 1.042->1.009. Runtime en `ensemble.py`, integrado en
  `/predict`. Tests: `test_ensemble.py`. Verificado en vivo (ensemble: true).
- [x] **Dixon-Coles con time-decay (#5)** - `ml/dixon_coles.py` (fit por liga por
  maxima verosimilitud + correccion de marcadores bajos + decaimiento temporal xi).
  Backtest temporal: accuracy ~55%, RPS ~0.195, log-loss ~0.955 -> MEJOR que el
  ensamble XGBoost (RPS 0.212). Se integro como modelo PRIMARIO (peso 0.7) para las
  5 ligas cubiertas (PL/PD/BL1/SA/FL1), con fallback al ensamble donde no hay
  cobertura (Mundial, BetPlay). Parametros en `ml/data/dixon_coles.json` (build:
  `python -m ml.build_dixon_coles`). Tests: `test_dixon_coles.py`. Verificado en vivo.
- [x] **Cuota del mercado (#3) - benchmark + backtest de valor** - Fuente directa
  (football-data.co.uk) BLOQUEADA por el ISP (Coljuegos). Se uso un espejo en GitHub
  (`ml/collect_odds.py` -> `market_odds.csv`, 3504 partidos con cuotas). Decision de
  diseno: NO usar la cuota como feature (haria que el modelo copie al mercado y el EV
  daria ~0). En su lugar `ml/market_backtest.py`: benchmark vs mercado + ROI de la
  estrategia de valor. HALLAZGO CLAVE: el mercado (RPS 0.198) es mejor que Dixon-Coles
  (RPS 0.207); la estrategia de valor pierde (-11% ROI en todos los umbrales) -> el
  modelo NO tiene ventaja sobre el mercado. El EV debe presentarse como informativo,
  no como estrategia de ganancia.
- [ ] Pendiente del plan de 5 puntos: xG (#2), datos de jugadores. Nota: sin xG u
  otra ventaja informacional, es muy improbable batir al mercado.
- [ ] Deploy: `dixon_coles.json` está gitignoreado; correr el build en produccion
  (como build_nba_elo). Evaluar auto-build al arrancar si falta.

### Base de datos propia (scouting) - Fase 13 (4 Jul 2026)

- [x] **Diseno del esquema** - 8 tablas `scouting_*` (public, prefijo para separar de
  predicciones) en 3 niveles: nucleo (teams, matches, match_team_stats), contexto
  (players, lineups, match_events, match_odds) y granular (player_match_stats con
  campos tipo tracking). Cada tabla con columna `raw` jsonb para guardar TODO crudo.
  `matches` incluye fecha, estadio, ciudad, pais, clima y sensacion termica.
  SQL en `scouting_schema.sql` (corrido manualmente en el dashboard; MCP caido).
- [x] **Ingesta de selecciones** - `ml/ingest_national.py` desde el dataset local
  martj42 (international_results.csv, 49.477 partidos 1872-2026), categorizado
  (mundial/eliminatoria/continental/amistoso/otro). Cargados prioritarios COMPLETOS:
  mundiales 1036, eliminatorias 8772, continentales 10665. COMPLETO: 49.475
  partidos totales (amistosos 18386, otros 10616), 336 selecciones. 2 duplicados
  descartados. Dedup por (tournament, match_date, home_team, away_team).
- [x] **Goleadores** - `ml/ingest_goalscorers.py` (martj42 goalscorers.csv) ->
  47.821 goles en scouting_match_events (jugador, minuto, penal/autogol).
- [x] **Clima historico** - `ml/enrich_weather.py` (Open-Meteo archive, sensacion
  termica incluida; geocodificacion cacheada; resumible por tandas/prioridad).
  Enriquecidos 978 Mundiales (desde 1950; pre-1940 sin datos). Pendiente: correr
  para eliminatorias/continentales (`--category ...`).
- [x] **Stats detalladas + xG (StatsBomb)** - FBref daba 403 (anti-bot); se uso
  StatsBomb Open Data (GitHub). `ml/ingest_statsbomb_stats.py` agrega por equipo
  posesion/tiros/xG/pases/corners/faltas/tarjetas de WC 2022, WC 2018, Euro 2024,
  Euro 2020, Copa America 2024, AFCON 2023 -> scouting_match_team_stats. (Cargando.)
- [x] **Clima continentales/eliminatorias** - `enrich_weather.py --category ...`
  (en curso, resumible; rate-limited ~10k/dia).
- [x] **Mundiales historicos StatsBomb (1958-1990)** - `--historical`. Solo +36 filas
  (18 partidos); StatsBomb tiene poca data antigua con xG.
- [x] **Clubes** - `ml/ingest_clubs.py` desde el espejo GitHub (15 ligas, resultados
  + cuotas compactas en raw). Cargando en background.
- [x] **#4 Reentrenar+medir (selecciones)** - `ml/backtest_national.py`: Dixon-Coles
  sobre 21.745 partidos (desde 2000), holdout 2.684 competitivos 2023-2026.
  RESULTADO: acc 58.9%, RPS 0.179 (baseline 0.233) -> la base ampliada permite un
  modelo NACIONAL solido, que antes no existia. Falta el reentrenamiento de CLUBES
  (espera a que termine la carga) + medir vs mercado.
- [x] **#4 Reentrenar+medir (CLUBES)** - 171.507 partidos de clubes cargados
  (`ml/ingest_clubs.py`, 15 ligas). Cuotas ampliadas a todas las temporadas
  (`ODDS_ALL_SEASONS=1`, 43.300 partidos con cuota). `ml/market_backtest.py`:
  Dixon-Coles con toda la historia RPS 0.210 vs mercado 0.196; valor ROI -8%
  (mejoro desde -11% pero SIGUE perdiendo). CONCLUSION: mas datos de clubes NO
  crea ventaja sobre el mercado (mercado eficiente). La ventaja plausible esta en
  SELECCIONES / mercados flojos (RPS nacional 0.179), no en clubes de ligas grandes.

### Stats de clubes + xG - Fase 14

- [x] **Stats de clubes** (`ml/ingest_club_stats.py`) - tiros, tiros al arco, corners,
  faltas, tarjetas desde los mismos CSV del espejo. 173.722 filas (~87k partidos)
  en scouting_match_team_stats.
- [~] **xG de clubes (understat)** - understat cambio su API en 2026; se encontro el
  nuevo endpoint: GET https://understat.com/getLeagueData/{league}/{season} con
  headers Referer=https://understat.com/league/{league}/{season} y
  X-Requested-With=XMLHttpRequest -> JSON {teams, players, dates[]}; cada match trae
  h/a title, goals, xG.h/a, datetime. FUNCIONA. NO integrado: requiere update por
  fila (lento) o restriccion unica (match_id,is_home) + recarga; y el xG de clubes
  no da ventaja sobre el mercado (bajo ROI). Documentado para retomar.

- [x] **Integrar modelo nacional al /predict** - `dixon_coles.build_national()` +
  `predict_national()`; `ml/build_dixon_coles_national.py` genera
  dixon_coles_national.json (321 selecciones, 25.359 partidos desde 2000). En
  `main.py`: se aplica como señal primaria (peso 0.7) cuando los equipos son
  selecciones. Verificado en vivo (Argentina vs Brasil, Mundial FIFA). Tests en
  `test_dixon_coles.py`. Deploy: correr `python -m ml.build_dixon_coles_national`.

## TOTAL base de datos scouting: ~221k partidos (171.507 clubes + 49.475
## selecciones), 970 equipos, 47.821 goles, ~174k filas de stats.

## HOJA DE RUTA / PENDIENTES (objetivos - ver seccion 19 del docx)

- [ ] **Completar la base de datos (PRIORIDAD)**: clima eliminatorias/amistosos/clubes;
  xG de clubes (understat, endpoint resuelto); estadio/arbitro/asistencia; eventos de
  tarjetas y cambios; mejorar cruce de nombres entre fuentes.
- [~] **Tabla de JUGADORES tipo tarjeta FIFA/EA FC**:
  - [x] v1 (goleadores): 15.388 jugadores en scouting_players con career_stats
    (goles, penales, autogoles, partidos, años, seleccion). Fuente: goalscorers.csv.
    Campos national_team/current_club/career_stats agregados (add_player_fields.sql).
    Codigo: ml/ingest_players.py.
  - [x] v2: StatsBomb -> scouting_player_match_stats (posicion, goles, asistencias,
    tiros, xG, pases, pases clave, faltas, tarjetas) de 6 torneos de selecciones.
    7.707 filas; 16.261 jugadores (15.388 goleadores + 873 no-goleadores nuevos).
    Codigo: ml/ingest_player_stats.py. Emparejamiento de nombres corregido (indexar
    por todos los tokens; se limpiaron duplicados). Verificado: Messi/James/Mbappe
    enlazan goles de carrera + stats por partido. [ ] Pendiente: scouting_lineups
    (titular/minutos) y clubes.
  - [x] v3: perfil desde WIKIDATA (SPARQL, gratis) -> edad/fecha nacimiento, posicion,
    club actual, historial de equipos (team_history jsonb), wikidata_id.
    Codigo: ml/enrich_players_wikidata.py. Columnas team_history/wikidata_id agregadas.
    Enriquecidos 944 jugadores prioritarios (los que tienen stats de partido); 78
    ambiguos, 478 sin ficha. Resumible/ampliable en tandas. Verificado: tarjeta
    completa de James Rodriguez (35 años, Minnesota United, 16 equipos, 23 goles, 7 asist).
  - [x] App: endpoint + pagina de "tarjeta de jugador" (2026-08-21). Backend:
    `players_db.py` (modulo nuevo; se saco de `supabase_client.py` que llegaba al
    limite de 500 lineas) con `get_player_profile()` -> ficha Wikidata + linea de
    tiempo de goles reales (cruce por `detail->>scorer` en scouting_match_events,
    con fecha/rival/minuto/penal) + stats por partido de StatsBomb agregadas
    (totales, promedio por partido, posicion habitual) + trayectoria de clubes.
    Endpoint `GET /players/{player_id}` (404 si no existe). Frontend:
    `/jugadores/[id]` con la tarjeta (numeros de carrera, barras de goles por
    competicion, tabla de ultimos partidos, ultimos goles, trayectoria); las filas
    del ranking y del buscador ahora enlazan a la tarjeta (el listado expone `id`).
    Tests: 12 en `test_players.py` (helpers, perfil con cliente falso, endpoint
    200/404). Suite completa: 53 pasan. Build de Next 16 OK.
  - [ ] Ampliar el perfil Wikidata a mas jugadores (hoy 944 de 16.261).
- [ ] **Ligas colombianas / BetPlay**: seleccion Colombia SI (641 partidos); Liga BetPlay
  de clubes NO (football-data.co.uk no cubre Colombia). Traer de API-Sports (league 239).
- [ ] **Basquetbol**: base de datos propia estilo scouting_* (partidos, stats, jugadores).
- [ ] **Despliegue**: publicar en internet (Railway + Vercel), no solo localhost; configurar
  env vars y correr builds de modelos en produccion.
- [ ] **Rediseno frontend**: home = landing/login (no mostrar proximos partidos hasta entrar);
  mejorar menu de deportes; mejorar estilo visual general.
- [ ] **Modelo/producto**: reentrenar periodicamente; mensaje honesto (no vender "ganarle al
  mercado"); explorar edge en selecciones y mercados flojos.

## Descubierto durante el trabajo

## Descubierto durante el trabajo

- No existían `PLANNING.md` ni `TASK.md`; se creó este `TASK.md` para cumplir
  con las reglas de `CLAUDE.md`.
- No existía `venv_linux`; los tests se corrieron con el Python base (3.13) +
  pytest. Considerar crear el venv documentado en `CLAUDE.md`.
- The Odds API solo cubre 1X2 y Over/Under de goles; córners, tarjetas y
  marcador exacto siguen usando la "cuota mínima" estimada (sin cuota real).

## Pendientes / próximos pasos sugeridos

- [ ] Configurar `ADMIN_EMAILS` en el `.env` del backend (local y Railway) con el
  email administrador, y registrar ese usuario en Supabase Auth.
- [ ] `/track-record` y `/predictions/stats` siguen mostrando precisión **global**
  del modelo (de todos los usuarios). Evaluar si conviene una vista por usuario.
- [ ] Verificación visual del frontend con dev server controlable (Next 16 bloquea
  un segundo `next dev` sobre el mismo directorio).
- [x] `venv_linux` creado (lo pedía `CLAUDE.md`) y añadido al `.gitignore`; los
  tests del backend se corren con `./venv_linux/bin/python -m pytest`.
- [ ] La tarjeta de jugador no se pudo verificar contra la base real desde el
  entorno remoto (no hay `SUPABASE_SECRET_KEY` local y las tablas `scouting_*`
  tienen RLS). Se validó la consulta equivalente en SQL (69 goles de Messi con
  fecha y rival) y el armado del perfil con un cliente falso en los tests;
  falta abrir `/jugadores/<id>` en producción para confirmarlo de punta a punta.
</content>
</invoke>

## Despliegue a producción — 2026-07-20 (en curso)

- [x] **Código subido a GitHub** — commit con las fases 11+ (64 archivos: NBA,
  auth, EV, Dixon-Coles, base scouting, tests). Verificado que `.env` no está
  versionado y sin secretos en el código.
- [x] **Artefactos de modelo versionados** — los 8 JSON pequeños del runtime
  (dixon_coles, nacional, ensemble, elo, forma, NBA) se excluyeron del gitignore
  y viajan con el repo (~50 KB); Railway no necesita reconstruirlos.
- [x] **`scipy` declarado en requirements.txt** (lo usa `ml/dixon_coles.py`).
- [x] **Repo transferido a la cuenta personal** — de `andres25052000`
  (universitaria, correo deshabilitado) a `andrescamacho25052000-max` (Gmail).
  Remote local y `user.email` actualizados.
- [x] **Railway desplegado** — proyecto `dynamic-motivation`, root `/backend`,
  5 variables configuradas. Backend ACTIVE en
  https://sports-predictor-production-9144.up.railway.app (endpoints /leagues,
  /predictions/recent, /nba/teams verificados 200; /predict sin token 401 ✓).
- [x] **Vercel desplegado** — root `/frontend` + 3 variables `NEXT_PUBLIC_*`.
  App en vivo: https://sports-predictor-pi-gilt.vercel.app (home con partidos
  reales, track record con datos de Supabase y página NBA verificados).
- [x] **CORS verificado** — el backend acepta el dominio de Vercel vía la regla
  `*.vercel.app`; `FRONTEND_URL` queda opcional.
- [ ] Probar registro/login + predicción con sesión en producción (manual).
- [ ] `ODDS_API_KEY` en Railway cuando se cree la cuenta de The Odds API.
- [ ] Supabase: evitar pausa del plan gratis (UptimeRobot/cron sobre el backend
  y ping a Supabase).
- [ ] Opcional: dominio propio y monitoreo de uptime (paso 8-9 del doc).

## Rediseño Statix + página de jugadores — 2026-07-20

Rediseño de la interfaz según el prototipo aprobado en Lovable ("Statix — Sports
Intelligence"), replicado a partir de capturas y alimentado con datos reales.
Desplegado a producción (commit `cdb2b79`).

### Layout global (shell Statix)
- [x] **Tokens de diseño** en `app/globals.css` (tema negro-verdoso, acento verde
  `#34d399`, azul secundario, utilidad `.eyebrow` mono en mayúsculas).
- [x] **`components/layout/`**: `TopBar`, `Sidebar`, `BottomNav`, `AppShell`,
  `ComingSoon`, `nav.ts`. Montado en `app/layout.tsx` (envuelve toda la app).
- [x] Se retiran las navs inferiores duplicadas de `page`, `match`, `nba`,
  `track-record`, `history` (ahora las provee el shell).

### Home rediseñada (`components/home/`)
- [x] `Hero`, `KpiRow`, `UpcomingStatix`, `ModelPerformance`, `LeaguesGrid`.
  4 KPIs en vivo, precisión real por mercado, feed de la comunidad y ligas —
  **datos reales, mensaje honesto** (acierto 1X2 ~33.7%, sin el 71.4% ficticio).

### Páginas nuevas
- [x] **`/cuenta`** — Mi cuenta: perfil (Supabase Auth) + KPIs propios + últimas
  predicciones (`/predictions/mine`) + cambio de contraseña. Ítem "Mi cuenta" en
  el sidebar y "Perfil" de la nav móvil apunta aquí.
- [x] **`/ligas`** — ligas reales (`/leagues`) + conteo de próximos partidos.
- [x] **`/partidos`** — fixtures reales (`/upcoming`) con filtros por fecha.
- [x] **`/jugadores`** — buscador + ranking de máximos goleadores (datos reales).
- [x] Placeholders coherentes con el prototipo: `/equipos`, `/comunidad`, `/predicciones`.

### Backend — base de jugadores expuesta (doc 22.1)
- [x] `supabase_client.get_top_scorers()` y `search_players()` — leen
  `scouting_players` (goles de carrera), con caché en memoria (~15.388 jugadores).
- [x] Endpoints `GET /players/top` y `GET /players/search` en `main.py`.
- [x] Tests: `backend/tests/test_players.py` (orden, límite, búsqueda) — pasan.
- [x] Verificado en producción: Railway sirve el endpoint con datos correctos
  (Cristiano 124, Kane 75, Messi 71…, acentos UTF-8 OK).

### Descubierto durante el trabajo
- **Bug corregido en la tarjeta de jugador**: `ml/ingest_goalscorers.py` guarda el
  equipo del goleador como `detail->>scoring_team`, no `team`, asi que el rival de
  cada gol salia vacio. Corregido en `players_db.py` (con fallback a `team`).
- **Colision de rutas en FastAPI**: `/teams/{team_id}` declarada antes que
  `/teams/search` capturaba ese path y devolvia 422 (no hay fallback tras un fallo
  de validacion), rompiendo el buscador del formulario de partido manual. La ruta
  dinamica va al final; hay un test de regresion (`test_teams.py`).
- El buscador nuevo de equipos vive en `/teams/directory` para no pisar el
  `/teams/search` existente, que resuelve ids de football-data para el predictor.
- El "mojibake" en nombres de jugadores era un artefacto de la consola de Windows
  (`json.tool` / cp1252), **no de los datos**: la base está bien codificada. No hizo
  falta `ftfy`.
- El dev server vía `launch.json` corre desde la raíz del repo y **no carga
  `frontend/.env.local`**; para verificar en local hay que correr `next dev` desde
  `frontend/`.

### Pendientes de este rediseño
- [x] **Equipos** (2026-08-21): `teams_db.py` + `/teams/rankings`, `/teams/directory`
  y `/teams/{id}`; paginas `/equipos` (ranking de selecciones por Elo + buscador de
  los 970 equipos) y `/equipos/[id]` (ficha: record historico completo, forma,
  splits local/visitante/neutral, desglose por competicion, promedios de stats
  detalladas con el n de cada metrica, maximos goleadores y — en selecciones —
  Elo + fuerza de ataque/defensa Dixon-Coles en percentiles). 13 tests nuevos.
- [ ] **Comunidad**: feature social completa (posts, seguir) desde cero.
- [ ] `current_club` (Wikidata) tiene errores (p. ej. Lewandowski→"Chicago Fire");
  por eso las tarjetas de jugador muestran la selección, no el club.
- [ ] Búsqueda global `⌘K` de la barra superior: hoy es visual, falta la lógica.
