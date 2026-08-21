# Predictor Deportivo

Aplicación full-stack para predecir resultados de partidos de fútbol. Combina un modelo **XGBoost** entrenado sobre ~3 300 partidos históricos con reglas contextuales (lesiones, clima, estadio) y distribución de **Poisson** para calcular probabilidades de múltiples mercados de apuesta.

---

## Tabla de contenidos

- [Arquitectura](#arquitectura)
- [Funcionalidades](#funcionalidades)
- [Interfaz (rediseño Statix)](#interfaz-rediseño-statix)
- [Stack tecnológico](#stack-tecnológico)
- [APIs externas](#apis-externas)
- [Configuración local](#configuración-local)
- [Variables de entorno](#variables-de-entorno)
- [Comandos del backend](#comandos-del-backend)
- [Comandos del frontend](#comandos-del-frontend)
- [Endpoints de la API](#endpoints-de-la-api)
- [Modelos de predicción](#modelos-de-predicción)
- [Base de datos (Supabase)](#base-de-datos-supabase)
- [Pipeline de ML](#pipeline-de-ml)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Despliegue](#despliegue)
- [Limitaciones conocidas](#limitaciones-conocidas)

---

## Arquitectura

```
┌─────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                 │
│  / (búsqueda, próximos partidos, partido manual)         │
│  /match (predicción detallada)  /history (historial)     │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / REST
┌────────────────────────▼────────────────────────────────┐
│                    Backend (FastAPI)                      │
│                                                          │
│  predictor.py          ← reglas ponderadas (7 factores)  │
│  ml_predictor.py       ← XGBoost (si el modelo existe)   │
│  poisson_predictor.py  ← mercados Poisson (goles, BTTS…) │
│  corners_cards_predictor.py ← córners/tarjetas (Poisson) │
│                                                          │
│  Tareas en background (asyncio):                         │
│  • result_checker     — busca resultados reales c/hora   │
│  • national_data_loop — refresca Elo/selecciones c/24h   │
└──────┬──────────────────────────────────────────────────┘
       │
       ├── football-data.org  (partidos, H2H, standings)
       ├── API-Sports          (lesionados, estadios, stats)
       ├── Open-Meteo          (clima gratuito, sin key)
       └── Supabase            (guardar/leer predicciones)
```

### Flujo de una predicción

1. El usuario selecciona un partido (búsqueda, próximos partidos, o manual).
2. El frontend llama a `POST /predict` con equipos, liga, fecha e IDs.
3. El backend orquesta en paralelo:
   - Forma reciente y H2H desde **football-data.org**
   - Lesionados y datos del estadio desde **API-Sports**
   - Clima en la ciudad del estadio desde **Open-Meteo**
4. El modelo **XGBoost** genera probabilidades 1X2 usando 22 features.
   Si el modelo no está disponible, usa las reglas ponderadas como fallback.
5. El predictor **Poisson** calcula todos los mercados derivados.
6. El predictor de **córners/tarjetas** añade esos mercados.
7. El resultado completo se guarda en **Supabase** y se devuelve al frontend.
8. Cada hora el `result_checker` busca el resultado real y, cuando lo encuentra,
   lanza un reentrenamiento incremental del modelo.

---

## Funcionalidades

| Funcionalidad | Descripción |
|---|---|
| Interfaz Statix | Rediseño completo de la UI: barra superior fija, sidebar (desktop), navegación inferior (móvil) y tema oscuro con acento verde esmeralda (ver [Interfaz](#interfaz-rediseño-statix)) |
| Home rediseñada | Hero + 4 KPIs en vivo + próximos partidos + precisión real por mercado + feed de la comunidad + ligas principales, todo con datos reales |
| Mi cuenta | Página `/cuenta`: perfil (email, miembro desde), KPIs propios, últimas predicciones y cambio de contraseña |
| Directorio de ligas | Página `/ligas`: todas las competiciones cubiertas con su conteo de próximos partidos |
| Calendario de partidos | Página `/partidos`: fixtures reales con filtros por fecha (hoy / mañana / esta semana) |
| Tarjeta de goleadores | Página `/jugadores`: buscador + ranking de máximos goleadores (goles de carrera, penales, años) desde la base propia |
| Cuotas reales + EV | Trae cuotas reales (The Odds API) y calcula el valor esperado de cada mercado automáticamente |
| Cuentas de usuario | Registro/login con Supabase Auth (email + contraseña); requiere sesión para predecir |
| Cambio de contraseña | Cualquier usuario puede cambiar su contraseña desde la app |
| Panel de admin | Usuarios registrados y activos en este momento (solo administrador) |
| Predicción NBA | Modelo Elo + totales (over/under) + hándicap para partidos NBA, con cuotas/EV |
| Historial general | Sección pública en la home: últimos 10 partidos distintos predichos por la comunidad (sin datos de usuario) |
| Mi historial | Cada usuario ve solo sus propias predicciones; el administrador ve todas |
| Track record público | Página `/track-record` con el historial verificable de aciertos en vivo |
| Búsqueda de partidos | Búsqueda por nombre de equipo en tiempo real |
| Próximos partidos | Panel con los próximos ~32 partidos de ligas top + BetPlay |
| Partido personalizado | Formulario para ingresar cualquier equipo manualmente |
| Predicción 1X2 | Probabilidades local/empate/visitante (XGBoost + reglas) |
| Mercados Poisson | Over/Under, BTTS, marcador exacto, hándicap, primera mitad, portería a cero |
| Córners y tarjetas | Esperado total, Over/Under, distribución por equipo |
| Panel de valor | Evalúa múltiples patas de combinadas ingresando cuotas |
| Historial | Todas las predicciones con resultado real y acierto |
| Estadísticas globales | Precisión por liga y por tipo de mercado |
| Reentrenamiento auto | El modelo mejora con cada resultado real recibido |
| Clima en estadio | Pronóstico Open-Meteo con impacto en el partido |
| Lesionados | Lista de jugadores no disponibles en tiempo real |
| Evolución del modelo | Historial de versiones y accuracy por iteración |

---

## Interfaz (rediseño Statix)

La interfaz sigue el sistema de diseño **"Statix — Sports Intelligence"** (tema oscuro
negro-verdoso, acento verde esmeralda `#34d399`, azul secundario, tarjetas muy
redondeadas y etiquetas de sección en mayúsculas monoespaciadas). Los tokens viven en
`app/globals.css` (Tailwind v4, `@theme`).

**Shell global** (`components/layout/`, montado en `app/layout.tsx`):

- **Barra superior fija** — logo, navegación horizontal (desktop ancho), búsqueda global
  (`⌘K`, visual por ahora), notificaciones y menú de sesión.
- **Sidebar** (desktop) — navegación principal con ítem activo resaltado y "ligas seguidas".
- **Navegación inferior** (móvil) — Inicio · Partidos · IA · Stats · Perfil.

**Páginas con datos reales:**

| Ruta | Contenido | Fuente |
|---|---|---|
| `/` | Hero, 4 KPIs, próximos partidos, precisión por mercado, feed, ligas | `/predictions/stats`, `/leagues`, `/upcoming`, `/predictions/market-stats`, `/predictions/recent` |
| `/cuenta` | Perfil + KPIs del usuario + últimas predicciones | Supabase Auth + `/predictions/mine` |
| `/ligas` | Ligas cubiertas + conteo de próximos partidos | `/leagues` + `/upcoming` |
| `/partidos` | Fixtures con filtros por fecha | `/upcoming` |
| `/equipos` | Ranking de selecciones por Elo + buscador de clubes y selecciones | `/teams/rankings`, `/teams/directory` |
| `/equipos/[id]` | **Ficha de equipo**: histórico completo, forma, local/visitante, por competición, promedios por partido, goleadores y bloque de modelo (Elo + ataque/defensa Dixon-Coles) | `/teams/{id}` |
| `/jugadores` | Ranking de goleadores + buscador | `/players/top`, `/players/search` |
| `/jugadores/[id]` | **Tarjeta de jugador**: ficha (edad, posición, club), goles por competición, rendimiento por partido, últimos goles y trayectoria de clubes | `/players/{id}` |
| `/track-record` | Precisión verificable en vivo (ítem "Estadísticas") | `/predictions/stats` + `/predictions/market-stats` |

`/comunidad` y `/predicciones` siguen siendo placeholders ("próximamente"): un feed
social completo requiere features que aún no existen.

**Mensaje honesto:** a diferencia del prototipo (datos ficticios, precisión 71.4%), la app
muestra las cifras reales del backend (p. ej. acierto 1X2 ~33.7% en vivo) y presenta el EV
como información, no como ganancia asegurada (ver [Limitaciones conocidas](#limitaciones-conocidas)).

---

## Stack tecnológico

**Backend**
- Python 3.11+
- FastAPI + Uvicorn
- XGBoost, scikit-learn, NumPy, pandas
- Supabase Python SDK
- python-dotenv, requests, joblib

**Frontend**
- Next.js 15 (App Router)
- TypeScript
- Tailwind CSS + shadcn/ui
- Framer Motion
- Axios

---

## APIs externas

| API | Uso | Plan gratuito |
|---|---|---|
| [football-data.org](https://www.football-data.org/) | Partidos, resultados, H2H, standings | 10 req/min, ~15 ligas |
| [API-Sports](https://www.api-sports.io/) | Lesionados, estadios, stats post-partido | 100 req/día |
| [Open-Meteo](https://open-meteo.com/) | Clima y geocodificación | Sin límite, sin key |
| [The Odds API](https://the-odds-api.com/) | Cuotas reales de casas de apuestas (fútbol 1X2/OU y NBA h2h/totales) | 500 req/mes |
| [API-Sports Basketball](https://www.api-sports.io/) | Partidos NBA históricos para el modelo Elo (misma key que fútbol) | Plan free: temporadas 2022–2024 |
| [Supabase](https://supabase.com/) | Base de datos PostgreSQL + Auth (cuentas de usuario) | Free tier |
| [StatsBomb Open Data](https://github.com/statsbomb/open-data) | Datos históricos córners/tarjetas | Abierto |

---

## Configuración local

### Requisitos previos

- Python 3.11+
- Node.js 18+
- Cuenta gratuita en football-data.org, API-Sports y Supabase

### 1. Clonar y preparar el entorno

```bash
git clone <repo-url>
cd sports-predictor

# Crear entorno virtual
python -m venv venv_linux

# Activar (Windows)
venv_linux\Scripts\activate
# Activar (Linux/Mac)
source venv_linux/bin/activate

pip install -r backend/requirements.txt
```

### 2. Configurar variables de entorno

Crear `backend/.env` con las claves de API (ver sección [Variables de entorno](#variables-de-entorno)).

Crear `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3. Construir los datos del modelo (primera vez)

```bash
cd backend

# 1. Descargar partidos históricos de 5 ligas (2023 y 2024)
python -m ml.collect

# 2. Construir dataset con feature engineering
python -m ml.build_dataset

# 3. Entrenar el modelo XGBoost
python -m ml.train

# 4. Datos de StatsBomb para córners y tarjetas
python -m ml.collect_statsbomb
python -m ml.build_statsbomb_profiles

# 5. Elo y forma de selecciones nacionales (Mundial FIFA)
python -m ml.build_national_elo
```

### 4. Levantar el backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Disponible en `http://localhost:8000`. Documentación interactiva en `http://localhost:8000/docs`.

### 5. Levantar el frontend

```bash
cd frontend
npm install
npm run dev
```

Disponible en `http://localhost:3000`.

---

## Variables de entorno

### `backend/.env`

```env
# football-data.org — partidos, resultados, H2H, standings
# Registro gratuito en https://www.football-data.org/
FOOTBALL_API_KEY=tu_clave_aqui

# API-Sports — lesionados, estadios, estadísticas post-partido
# Registro gratuito en https://www.api-sports.io/
API_SPORTS_KEY=tu_clave_aqui

# Supabase — base de datos de predicciones
# Crear proyecto en https://supabase.com/
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_SECRET_KEY=eyJhbGci...

# The Odds API — cuotas reales para el cálculo automático de valor esperado (EV)
# Registro gratuito en https://the-odds-api.com/ (500 req/mes en el plan free)
# Si se omite, el panel de valor funciona con cuotas estimadas (entrada manual).
ODDS_API_KEY=tu_clave_aqui
# Opcional: regiones de casas de apuestas a consultar (default: eu,uk)
ODDS_API_REGIONS=eu,uk

# Emails con permiso de administrador (ven TODAS las predicciones de todos los
# usuarios). Separados por comas. Si se omite, no hay administradores.
ADMIN_EMAILS=tu-email-admin@gmail.com

# (Solo producción) URL del frontend para CORS
FRONTEND_URL=https://tu-app.vercel.app
```

### `frontend/.env.local`

```env
# URL del backend (local o Railway en producción)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Supabase — cliente del navegador (predicciones + Auth)
NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=eyJhbGci...
```

---

## Comandos del backend

```bash
# Servidor de desarrollo con hot reload
uvicorn main:app --reload --port 8000

# ── Pipeline de ML ──────────────────────────────────────────────────────────

# Recolectar datos históricos (football-data.org → ml/data/*.json)
python -m ml.collect

# Feature engineering → ml/data/dataset.csv
python -m ml.build_dataset

# Entrenar modelo XGBoost → ml/model.pkl
python -m ml.train

# Datos StatsBomb (córners/tarjetas) → ml/data/team_profiles_statsbomb.json
python -m ml.collect_statsbomb
python -m ml.build_statsbomb_profiles

# Elo de selecciones → ml/data/elo_ratings.json + national_form.json
python -m ml.build_national_elo

# Modelo NBA (Elo + anotación) → ml/data/nba_elo.json, nba_team_stats.json, nba_meta.json
# Descarga partidos históricos de API-Sports (temporadas 2022–2024 en plan free)
python -m ml.build_nba_elo

# Liga BetPlay → ml/data/betplay_*.csv
python -m ml.collect_betplay_stats
python -m ml.build_betplay_profiles

# ── Mantenimiento ────────────────────────────────────────────────────────────

# Verificar resultados pendientes manualmente
python result_checker.py

# Reentrenamiento incremental manual
python -m ml.incremental_trainer

# Evaluacion honesta del modelo 1X2 (holdout temporal): accuracy, log-loss, RPS
python -m ml.backtest

# Afinar el ensamble XGBoost + Poisson + calibracion -> ml/data/ensemble_config.json
python -m ml.tune_ensemble

# Ajustar Dixon-Coles por liga -> ml/data/dixon_coles.json  (modelo primario 1X2)
python -m ml.build_dixon_coles
# Ajustar Dixon-Coles de SELECCIONES -> ml/data/dixon_coles_national.json (Mundial)
python -m ml.build_dixon_coles_national
# Backtest del modelo nacional (RPS sobre partidos competitivos recientes)
python -m ml.backtest_national
# Backtest de Dixon-Coles (accuracy, log-loss, RPS por valor de decaimiento xi)
python -m ml.dixon_coles

# Cuotas historicas (espejo GitHub de football-data.co.uk) -> ml/data/market_odds.csv
python -m ml.collect_odds
# Benchmark del modelo vs el mercado + ROI de la estrategia de valor
python -m ml.market_backtest
```

---

## Comandos del frontend

```bash
npm run dev      # servidor de desarrollo (hot reload, puerto 3000)
npm run build    # build de producción optimizado
npm run start    # servir el build de producción
npm run lint     # linting con ESLint
```

---

## Endpoints de la API

La documentación interactiva completa (Swagger UI) está en `/docs`.

### Partidos y ligas

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/leagues` | Lista de ligas disponibles con región |
| `GET` | `/leagues/{league}/matches` | Próximos partidos de una liga |
| `GET` | `/upcoming` | ~32 próximos partidos de todas las ligas en paralelo |
| `GET` | `/search?q={nombre}` | Busca partidos donde juegue un equipo |
| `GET` | `/teams/search?q={nombre}` | Busca equipos por nombre (índice local) |
| `GET` | `/players/top?limit={n}` | **Público** — máximos goleadores (goles internacionales de carrera) desde la base propia `scouting_players` |
| `GET` | `/players/search?q={nombre}` | **Público** — busca jugadores por nombre en la base propia |
| `GET` | `/teams/rankings?limit={n}` | **Público** — ranking de selecciones por Elo (artefacto `national_form.json`) |
| `GET` | `/teams/directory?q={nombre}` | **Público** — busca en el catálogo de `scouting_teams` (clubes y selecciones). Distinto de `/teams/search`, que resuelve ids de football-data para el predictor |
| `GET` | `/teams/{team_id}` | **Público** — ficha del equipo: récord histórico, splits local/visitante, por competición, promedios de stats, goleadores y, en selecciones, Elo + fuerza Dixon-Coles. 404 si no existe |
| `GET` | `/players/{player_id}` | **Público** — tarjeta completa de un jugador: ficha Wikidata, goles internacionales con fecha/rival/minuto, reparto por competición y stats por partido (StatsBomb). 404 si no existe |

### Predicciones

| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/predict` | Predicción completa (XGBoost + Poisson + córners + clima + lesiones). **Requiere `Authorization: Bearer <jwt>`** (401 si no hay sesión); la predicción se atribuye al usuario |
| `POST` | `/me/heartbeat` | **Requiere sesión** — marca al usuario como activo (para la métrica de usuarios activos) |
| `GET` | `/admin/stats` | **Solo admin** — usuarios registrados y activos (`?window_minutes=5`) |
| `GET` | `/nba/teams` | Equipos NBA disponibles (para autocompletado) |
| `GET` | `/nba/upcoming` | Próximos partidos NBA con cuotas (vía The Odds API) |
| `POST` | `/nba/predict` | **Requiere sesión** — predicción NBA (Elo + totales + hándicap + EV) |
| `GET` | `/predict/{home}/{away}` | Predicción rápida sin datos de API externa |
| `GET` | `/predictions/recent` | **Público** — últimos partidos distintos predichos (`?limit=10`), deduplicados, sin datos de usuario |
| `GET` | `/predictions/mine` | **Requiere sesión** — historial del usuario; si es admin, devuelve todo (`is_admin: true`) |
| `GET` | `/predictions` | **Solo admin** — historial completo de todos (`?limit=50&offset=0`) |
| `GET` | `/predictions/stats` | Precisión global por liga |
| `GET` | `/predictions/market-stats` | Precisión desglosada por tipo de mercado |
| `PATCH` | `/predictions/{id}/result` | Registra resultado real manualmente |
| `POST` | `/predictions/check-results` | Fuerza búsqueda inmediata de resultados |
| `POST` | `/predictions/retrain` | Lanza reentrenamiento incremental |
| `GET` | `/predictions/model-evolution` | Historial de versiones y accuracy |

### Body de `POST /predict`

```json
{
  "home_team": "Real Madrid",
  "away_team": "Barcelona",
  "league": "La Liga",
  "match_date": "2025-10-15",
  "home_id": 86,
  "away_id": 81,
  "home_crest": "https://crests.football-data.org/86.png",
  "away_crest": "https://crests.football-data.org/81.png"
}
```

`home_id` y `away_id` son los IDs de football-data.org. Sin ellos el backend usa
solo las reglas ponderadas (sin datos reales de forma, H2H ni lesiones).

### Respuesta de `POST /predict`

```json
{
  "home_team": "Real Madrid",
  "away_team": "Barcelona",
  "model": "XGBoost v1",
  "probabilities": {
    "home_win": 48.2,
    "draw": 25.1,
    "away_win": 26.7
  },
  "factors": [
    {
      "name": "Forma reciente",
      "weight": 25,
      "advantage": "Real Madrid",
      "detail": "Real Madrid: 4V/1E/0D — Barcelona: 3V/1E/1D"
    }
  ],
  "poisson": {
    "expected_goals": { "home": 1.82, "away": 1.41, "total": 3.23 },
    "result_1x2": { "home_win": 46.1, "draw": 27.3, "away_win": 26.6 },
    "over_under": { "over_2.5": 63.4, "under_2.5": 36.6 },
    "btts": { "yes": 54.2, "no": 45.8 },
    "exact_score": [{ "score": "2-1", "home": 2, "away": 1, "prob": 12.3 }],
    "half_time": { "home_win": 41.0, "draw": 35.0, "away_win": 24.0 },
    "handicap": {
      "home_-1.5": 38.2, "home_+1.5": 72.1,
      "away_-1.5": 22.4, "away_+1.5": 61.8
    },
    "home_goals": { "home_over_0_5": 84.1, "home_over_1_5": 58.3 },
    "away_goals": { "away_over_0_5": 75.9, "away_over_1_5": 46.1 },
    "home_clean_sheet": { "yes": 24.4, "no": 75.6 },
    "away_clean_sheet": { "yes": 19.3, "no": 80.7 }
  },
  "corners_cards": {
    "data_source": "statsbomb",
    "corners": {
      "expected_home": 5.2, "expected_away": 4.6, "expected_total": 9.8,
      "over_under": { "9.5": 0.52, "10.5": 0.38 },
      "home_more": 0.48, "away_more": 0.41, "equal": 0.11
    },
    "yellow_cards": {
      "expected_home": 1.7, "expected_away": 1.9, "expected_total": 3.6,
      "over_under": { "3.5": 0.44, "4.5": 0.28 }
    },
    "fouls": { "expected_home": 11.8, "expected_away": 12.3, "expected_total": 24.1 }
  },
  "injuries": {
    "home": { "team": "Real Madrid", "players": [{ "name": "Carvajal", "reason": "Ligamento" }] },
    "away": { "team": "Barcelona", "players": [] }
  },
  "stadium": {
    "name": "Santiago Bernabéu", "city": "Madrid",
    "capacity": 81044, "surface": "grass"
  },
  "weather": {
    "city": "Madrid", "date": "2025-10-15",
    "temp_max": 22, "temp_min": 14, "precipitation": 0,
    "windspeed": 18, "description": "Despejado", "emoji": "☀️",
    "impact": "Condiciones ideales para el juego"
  },
  "odds": {
    "source": "the-odds-api",
    "bookmaker_count": 8,
    "commence_time": "2025-10-15T19:00:00Z",
    "markets": {
      "1":          { "odds": 1.95, "prob": 48.2, "ev": 0.094, "value": true },
      "X":          { "odds": 3.60, "prob": 25.1, "ev": -0.096, "value": false },
      "2":          { "odds": 4.20, "prob": 26.7, "ev": 0.121, "value": true },
      "over_2.5":   { "odds": 1.90, "prob": 63.4, "ev": 0.205, "value": true },
      "under_2.5":  { "odds": 1.95, "prob": 36.6, "ev": -0.286, "value": false }
    },
    "best_value": [
      { "market": "over_2.5", "odds": 1.90, "prob": 63.4, "ev": 0.205, "value": true }
    ]
  },
  "prediction_id": 142
}
```

> El bloque `odds` solo aparece si `ODDS_API_KEY` está configurada, la liga está
> mapeada en `odds_api.LEAGUE_SPORT_KEYS` y el partido se encuentra en la API.
> `ev` es el valor esperado por unidad apostada (`prob/100 × cuota − 1`);
> `value: true` indica EV positivo (apuesta con valor matemático).

### Body de `PATCH /predictions/{id}/result`

```json
{ "home_goals": 2, "away_goals": 1 }
```

### Body de `POST /predictions/retrain`

```json
{ "force": false }
```

Si `force: true`, el reentrenamiento corre aunque haya menos de 5 muestras nuevas.

---

## Modelos de predicción

### 1. Modelo de reglas ponderadas (fallback)

Calcula un puntaje para cada equipo sumando 7 factores con pesos fijos.
Se usa cuando no hay datos de API disponibles o el modelo XGBoost no está entrenado.

| Factor | Peso | Descripción |
|---|---|---|
| Forma reciente | 25% | Victorias/empates/derrotas últimos 5 partidos + diferencia de goles |
| Calidad del plantel | 22% | Ranking en liga + posesión promedio + tiros al arco |
| Ventaja de localía | 15% | Base 10 pts, ajustada por capacidad del estadio |
| Lesiones | 13% | Penalización por jugadores no disponibles y tarjetas rojas |
| Historial directo | 12% | H2H real de football-data.org, o datos mock como fallback |
| Forma en casa/fuera | 8% | Rendimiento específico como local o visitante |
| Clima y condiciones | 5% | Lluvia, viento, nieve, superficie del estadio |

**Ajuste por días de descanso:** si un equipo jugó hace ≤ 2 días se penaliza; ≥ 10 días recibe bonus.

**Cálculo del empate:** se estima dinámicamente; cuanto mayor la diferencia entre equipos, menor la probabilidad de empate (mín. 10%).

**Efecto del estadio:** estadios de +70 000 personas dan +4 pts de localía; estadios pequeños (-20 000) restan 2 pts.

### 2. Modelo XGBoost (principal)

Entrenado sobre partidos de Premier League, La Liga, Bundesliga, Serie A y Ligue 1
(temporadas 2023 y 2024, ~3 300 partidos FINISHED). Se activa cuando hay datos reales
de ambos equipos disponibles.

**22 features de entrada:**

| Grupo | Features |
|---|---|
| Forma global (últimos 5) | Victorias, empates, derrotas, goles marcados, goles recibidos — local y visitante |
| Forma específica | Victorias/empates/derrotas del local jugando en casa (últimos 3) y del visitante fuera (últimos 3) |
| H2H | Ratio de victorias del local y ratio de empates en el historial directo |
| Elo | Diferencia de Elo entre equipos y probabilidad esperada según Elo estándar |
| PPG | Puntos por partido del local y del visitante en la temporada actual |

**Clases de salida:** `0 = Local gana`, `1 = Empate`, `2 = Visitante gana`.

**Ajuste post-predicción por lesiones:** como el modelo no vio lesiones durante el entrenamiento,
se aplica un pequeño shift de probabilidades basado en la diferencia de penalización por lesiones
entre los dos equipos.

**Precisión:** ~67% en un split aleatorio, pero ese número es optimista. En un
**holdout temporal** (evaluando partidos futuros, como en uso real) la precisión
honesta es **~49%** con RPS ≈ 0.21 (ver `ml/backtest.py`). El techo del fútbol en
3 clases ronda 50-55%; lo que importa para apostar es la calibración (RPS/log-loss),
no solo el acierto.

### 2c. Dixon-Coles con time-decay (modelo primario 1X2)

Modelo estadístico específico de fútbol (Dixon & Coles, 1997). Ajusta por **máxima
verosimilitud** una fuerza de ataque y una de defensa por equipo, una ventaja de
localía global (γ) y una corrección de marcadores bajos (ρ), **pesando más los
partidos recientes** (decaimiento temporal ξ). Se ajusta **por liga** (los equipos
solo son comparables dentro de su liga: PL, PD, BL1, SA, FL1).

En backtest temporal midió **mejor que el ensamble XGBoost** (accuracy ~55%, RPS
~0.195, log-loss ~0.955 vs RPS 0.212 del ensamble). Por eso es el **modelo primario**
del 1X2 (peso 0.7) para las ligas cubiertas. Implementado en `ml/dixon_coles.py`,
integrado en `/predict`. Un RPS ≈ 0.19 está cerca del nivel de las casas de apuestas.

**Modelo nacional (selecciones / Mundial):** un Dixon-Coles aparte, ajustado sobre
~25.000 partidos internacionales desde 2000 (`dixon_coles_national.json`). En
backtest sobre partidos competitivos recientes dio **RPS 0.179** (accuracy 58.9%),
mejor aún que el de clubes. Se aplica automáticamente cuando los equipos son
selecciones (Mundial, etc.), como señal primaria (peso 0.7). Datos construidos con
el pipeline de recolección propio (esquema `scouting_*`, ver TASK.md).

### 2b. Ensamble (XGBoost + Poisson) + calibración

Las probabilidades 1X2 finales no son solo del XGBoost: se **mezclan con el 1X2 del
Poisson** (60% XGBoost / 40% Poisson) y se **calibran por temperatura** (T≈1.1). Esta
combinación, validada en holdout temporal (`ml/tune_ensemble.py`), baja el RPS de
0.217 a 0.212 y el log-loss de 1.042 a 1.009 frente al XGBoost solo. Se aplica en
`ensemble.py` dentro de `/predict`.

### 3. Predictor Poisson (mercados de goles)

Calcula goles esperados (λ) usando el método Dixon-Coles simplificado:

```
λ_local    = (goles_marcados_local   + goles_recibidos_visitante) / 2  × HOME_ADVANTAGE(1.15)
λ_visitante = (goles_marcados_visitante + goles_recibidos_local)   / 2
```

**Prior bayesiano:** la tasa de goles de cada equipo se mezcla con el promedio de liga
(PRIOR_WEIGHT = 2 partidos equivalentes), lo que suaviza el impacto de muestras pequeñas.

**Ajuste por Elo (ELO_BLEND = 0.5):** si ambos equipos tienen Elo rating, el total de
goles se conserva pero se reparte según una mezcla 50% forma / 50% Elo. El Elo refleja
la fuerza histórica relativa, no solo la forma reciente.

**Cancha neutral (Mundial FIFA):** se omite la ventaja de localía y los λ se reducen 10%
(calibrado a partir del comportamiento real de la fase de grupos del Mundial).

**Mercados calculados:**
- 1X2 (Poisson puro, complementario al XGBoost)
- Over/Under para líneas 0.5, 1.5, 2.5, 3.5 y 4.5
- BTTS (ambos equipos marcan)
- Marcador exacto (top 10 más probables)
- Resultado al descanso (λ × 0.38, fracción histórica de goles en 1ª mitad)
- Hándicap asiático (±1.5 y ±2.5) para local y visitante
- Goles individuales por equipo (over/under 0.5 y 1.5)
- Portería a cero para cada equipo

### 5. Modelo NBA (Elo + totales + hándicap)

Deporte aparte del fútbol (columna `sport='nba'` en la tabla). Construido por
`ml/build_nba_elo.py` a partir de partidos históricos de API-Sports:

- **Resultado (moneyline):** Elo por equipo (K=20, ventaja de localía +100, regresión
  a la media entre temporadas y multiplicador por margen de victoria estilo 538).
  No hay empate — la probabilidad es local vs visitante.
- **Total de puntos (over/under):** total esperado a partir de los promedios de
  anotación de cada equipo, con aproximación normal calibrada con la liga
  (`total_std` ≈ 21 pts).
- **Hándicap (spread):** margen esperado con aproximación normal (`margin_std` ≈ 16 pts).
- **Cuotas/EV:** vía The Odds API (`basketball_nba`), recalculando la probabilidad
  del modelo en la línea exacta de cada casa.

Equipos no-NBA (All-Star, Rising Stars) se filtran exigiendo ≥20 partidos por
temporada. **Limitación:** el plan gratuito de API-Sports solo da temporadas
2022–2024, así que el Elo no refleja la temporada en curso (sirve como prior).

### 4. Predictor Córners y Tarjetas

Usa perfiles por equipo generados desde el dataset abierto de StatsBomb.
Para cada equipo: `corners_for_avg`, `corners_against_avg`, `yellow_for_avg`,
`yellow_against_avg`, `fouls_for_avg`, `fouls_against_avg`.

Si el equipo no está en el dataset, usa promedios globales de fallback:
5.1 córners/equipo, 1.9 tarjetas amarillas/equipo, 12.5 faltas/equipo.

**Mercados calculados:**
- Córners: esperado por equipo y total, Over/Under (6.5 a 11.5), cuál equipo saca más
- Tarjetas amarillas: esperado por equipo y total, Over/Under (1.5 a 5.5), distribución de 0 a 5 por equipo
- Faltas: esperado por equipo y total

---

## Base de datos (Supabase)

### Tabla `predictions`

| Columna | Tipo | Descripción |
|---|---|---|
| `id` | int | PK autoincremental |
| `home_team` / `away_team` | text | Nombres de los equipos |
| `league` | text | Liga del partido |
| `match_date` | date | Fecha del partido |
| `home_crest` / `away_crest` | text | URLs de escudos |
| `prob_home_win` / `prob_draw` / `prob_away_win` | float | Probabilidades predichas (%) |
| `pred_winner` | text | "Local", "Empate" o "Visitante" |
| `confidence` | float | Probabilidad de la predicción ganadora |
| `model_used` | text | "XGBoost v1" o "rule-based v2" |
| `xg_home` / `xg_away` | float | Goles esperados (Poisson) |
| `fd_home_id` / `fd_away_id` | int | IDs de football-data.org para lookup automático |
| `features_json` | jsonb | Vector de features al momento de predecir (para reentrenamiento) |
| `markets_json` | jsonb | Snapshot de todos los mercados predichos |
| `result_home_goals` / `result_away_goals` | int | Marcador real (automático vía result_checker) |
| `result_actual` | text | "Local", "Empate" o "Visitante" real |
| `was_correct` | bool | Calculado por trigger de Supabase |
| `result_corners` / `result_yellow_cards` / `result_fouls` | int | Stats reales (API-Sports, best-effort) |
| `auto_updated` | bool | `true` si el resultado lo llenó el result_checker automáticamente |
| `retrain_used` | bool | `true` si ya se incluyó en un reentrenamiento del modelo |
| `model_version` | text | Versión del modelo que hizo la predicción |
| `user_id` | uuid | Dueño de la predicción (FK a `auth.users`; `null` = anónimo) |
| `created_at` | timestamptz | Timestamp de creación |

**Trigger de Supabase:** cuando se registra un resultado real, un trigger de base de datos
calcula `result_actual` y `was_correct` comparando `result_home_goals / result_away_goals`
con `pred_winner`.

### Tabla `user_activity` y función `admin_user_stats`

Para medir "usuarios activos ahora" existe la tabla `user_activity (user_id, last_seen)`:
el frontend hace un *heartbeat* (`POST /me/heartbeat`) al cargar y cada 60 s, y el
backend hace upsert de `last_seen`. La función `admin_user_stats(window_minutes)`
(SECURITY DEFINER, solo ejecutable por `service_role`) devuelve los usuarios
registrados (`count(*)` de `auth.users`) y los activos en la ventana dada.

**Row Level Security (RLS):** la tabla tiene RLS **activado** (ver `add_user_id_column.sql`).
El backend usa la clave `service_role`, que bypassa RLS, por lo que sus lecturas y
escrituras no cambian. RLS solo bloquea el acceso directo con la clave pública (anon)
desde el navegador, evitando que alguien lea las predicciones de otros usuarios. La
separación por usuario y el rol de administrador se aplican en el backend
(ver `ADMIN_EMAILS` y los endpoints `/predictions/recent`, `/predictions/mine`).

---

## Pipeline de ML

### Paso 1 — Recolección de datos

```
ml/collect.py
  Input:  football-data.org API (FOOTBALL_API_KEY)
  Output: ml/data/{LIGA}_{AÑO}.json  (PL, PD, BL1, SA, FL1 — 2023 y 2024)

ml/collect_statsbomb.py
  Input:  StatsBomb Open Data (GitHub, sin key)
  Output: ml/data/statsbomb_matches.csv

ml/collect_betplay_stats.py
  Input:  API-Sports (API_SPORTS_KEY)
  Output: ml/data/betplay_matches.csv
```

### Paso 2 — Feature engineering

```
ml/build_dataset.py
  Input:  ml/data/*.json
  Output: ml/data/dataset.csv  (~3300 filas, 22+ columnas)

  Garantía de no-filtración: itera los partidos en orden cronológico.
  Los stats de los últimos 5 partidos se calculan con una ventana deslizante
  que solo usa partidos ANTERIORES a la fecha del partido objetivo.

  El sistema Elo (ml/elo.py) también se actualiza secuencialmente:
  se usa el Elo ANTES del partido como feature, luego se actualiza con el resultado.

ml/build_statsbomb_profiles.py
  Input:  ml/data/statsbomb_matches.csv
  Output: ml/data/team_profiles_statsbomb.json

ml/build_national_elo.py
  Input:  Dataset internacional público (descargado de GitHub)
  Output: ml/data/elo_ratings.json   (team_id → elo_rating)
          ml/data/national_form.json  (últimos 5 partidos por selección)
```

### Paso 3 — Entrenamiento inicial

```
ml/train.py
  Input:  ml/data/dataset.csv
  Modelo: XGBoostClassifier
  Tuning: GridSearchCV (3-fold CV) sobre n_estimators, max_depth, learning_rate
  Output: ml/model.pkl  (con: model, features, labels, accuracy)
  Precisión: ~67% en test set
```

### Paso 4 — Reentrenamiento incremental (automático)

```
ml/incremental_trainer.py
  Trigger: result_checker.py → cada vez que hay ≥ 5 resultados reales nuevos
  Input:   Predicciones de Supabase donde retrain_used=False y result_actual≠null
  Modo:
    • Si existe ml/data/xgb_model.json → fine-tuning del modelo existente
    • Si no existe → entrenamiento desde cero con todos los datos disponibles
  Output:  ml/data/xgb_model.json (modelo actualizado)
           ml/data/incremental_meta.json (historial de accuracy y versiones)
  Post:    Marca retrain_used=True en Supabase para no reutilizar las mismas filas
```

### Sistema Elo (`ml/elo.py`)

Sistema Elo estándar con:
- Rating inicial: **1500** para todos los equipos
- Factor K: **32** (mismo ajuste por victoria independiente del margen)
- Ventaja de localía: **+100 puntos** al calcular la probabilidad esperada
- Se recalcula sobre todos los partidos históricos en orden cronológico

---

## Estructura del proyecto

```
sports-predictor/
├── README.md
├── CLAUDE.md              # instrucciones para el asistente de IA
├── backend/
│   ├── main.py            # FastAPI: endpoints + tareas background (asyncio)
│   ├── predictor.py       # Modelo de reglas ponderadas (7 factores)
│   ├── ml_predictor.py    # Inferencia XGBoost en producción
│   ├── poisson_predictor.py        # Mercados de goles (Poisson)
│   ├── corners_cards_predictor.py  # Mercados de córners/tarjetas (Poisson)
│   ├── football_api.py    # Cliente football-data.org (caché 30 min)
│   ├── api_sports.py      # Cliente API-Sports (100 req/día, caché 1h)
│   ├── odds_api.py        # Cliente The Odds API (cuotas reales + cálculo de EV)
│   ├── weather_api.py     # Cliente Open-Meteo (geocodificación + pronóstico)
│   ├── supabase_client.py # CRUD de predicciones + estadísticas + auth
│   ├── players_db.py      # Base de jugadores: goleadores, búsqueda y tarjeta (get_player_profile)
│   ├── teams_db.py       # Base de equipos: catálogo, ranking Elo y ficha (get_team_profile)
│   ├── tests/             # Pytest (test_odds_api.py, test_players.py, …)
│   ├── result_checker.py  # Busca y guarda resultados reales cada hora
│   ├── mock_data.py       # Datos de fallback cuando las APIs fallan
│   ├── predict_ultra.py   # (experimental) variante alternativa de predicción
│   └── ml/
│       ├── __init__.py
│       ├── elo.py                       # Sistema Elo propio
│       ├── collect.py                   # Descarga datos de football-data.org
│       ├── collect_statsbomb.py         # Descarga dataset StatsBomb
│       ├── collect_betplay_stats.py     # Stats de BetPlay vía API-Sports
│       ├── build_dataset.py             # Feature engineering → dataset.csv
│       ├── build_statsbomb_profiles.py  # Perfiles de equipo (córners/tarjetas)
│       ├── build_betplay_profiles.py    # Perfiles BetPlay
│       ├── build_national_elo.py        # Elo de selecciones nacionales
│       ├── train.py                     # Entrenamiento XGBoost inicial
│       ├── incremental_trainer.py       # Reentrenamiento con resultados reales
│       └── data/                        # Generado por los scripts (gitignorado)
│           ├── dataset.csv
│           ├── elo_ratings.json
│           ├── national_form.json
│           ├── team_profiles_statsbomb.json
│           ├── incremental_meta.json
│           ├── betplay_matches.csv
│           ├── statsbomb_matches.csv
│           └── {PL|PD|BL1|SA|FL1}_{2023|2024}.json
│
└── frontend/
    ├── app/
    │   ├── page.tsx              # Home rediseñada (hero + KPIs + partidos + rankings)
    │   ├── match/page.tsx        # Predicción detallada con todos los mercados
    │   ├── history/page.tsx      # Historial de predicciones
    │   ├── track-record/page.tsx # Track record público (precisión en vivo)
    │   ├── cuenta/page.tsx       # Mi cuenta (perfil + KPIs del usuario)
    │   ├── ligas/page.tsx        # Directorio de ligas (datos reales)
    │   ├── partidos/page.tsx     # Calendario de fixtures con filtros por fecha
    │   ├── jugadores/page.tsx    # Ranking de goleadores + buscador (datos reales)
    │   ├── equipos/ · comunidad/ · predicciones/  # placeholders "próximamente"
    │   └── layout.tsx            # Layout global: envuelve todo en <AppShell> (AuthProvider)
    ├── components/
    │   ├── layout/              # Shell Statix
    │   │   ├── AppShell.tsx     #   compone barra + sidebar + nav inferior
    │   │   ├── TopBar.tsx       #   barra superior fija (logo, búsqueda, sesión)
    │   │   ├── Sidebar.tsx      #   navegación lateral (desktop) + ligas seguidas
    │   │   ├── BottomNav.tsx    #   navegación inferior tipo app (móvil)
    │   │   ├── ComingSoon.tsx   #   pantalla placeholder de secciones futuras
    │   │   └── nav.ts           #   configuración de navegación
    │   ├── home/                # Secciones de la home Statix
    │   │   ├── Hero.tsx · KpiRow.tsx · UpcomingStatix.tsx
    │   │   └── ModelPerformance.tsx · LeaguesGrid.tsx
    │   ├── TeamSearch.tsx       # Input de búsqueda con debounce
    │   ├── UpcomingMatches.tsx  # Panel de próximos partidos agrupados por liga
    │   ├── CustomMatchForm.tsx  # Formulario de partido manual con autocompletado
    │   ├── ProbabilityBar.tsx   # Barras animadas de probabilidad 1X2
    │   ├── ValuePanel.tsx       # Panel de valor: cuotas reales + EV automático
    │   ├── ParlaySuggestions.tsx # Sugerencias automáticas de combinadas
    │   ├── AuthMenu.tsx         # Botón de sesión (entrar / email + salir)
    │   ├── AuthModal.tsx        # Modal de login/registro (Supabase Auth)
    │   ├── ChangePasswordModal.tsx # Modal de cambio de contraseña
    │   └── ui/                  # Componentes base (shadcn/ui): badge, card, tabs, progress
    └── lib/
        ├── api.ts      # Cliente axios + interfaces (incluye Player + fetchTopScorers/searchPlayers)
        ├── auth.tsx    # AuthProvider + hook useAuth (Supabase Auth)
        ├── config.ts   # Configuración global del frontend
        ├── markets.ts  # Helpers para formatear y mostrar mercados de apuesta
        ├── supabase.ts # Cliente Supabase del lado del cliente
        └── utils.ts    # Utilidad cn() para clases condicionales de Tailwind
```

---

## Despliegue

> **En producción.** La app está desplegada y en vivo:
> - **Frontend (Vercel):** https://sports-predictor-pi-gilt.vercel.app
> - **Backend (Railway):** https://sports-predictor-production-9144.up.railway.app
> - **Repositorio:** `github.com/andrescamacho25052000-max/sports-predictor` (cuenta personal)
>
> Cada `git push` a `master` redespliega automáticamente ambos (Railway el backend, Vercel el frontend). Los artefactos de modelo pequeños (`dixon_coles`, Elo, NBA, etc.) están versionados en `backend/ml/data/`, así que el backend arranca en producción sin reconstruirlos.

### Backend — Railway

1. Conectar el repositorio a Railway y apuntar al directorio `/backend`.
2. Configurar todas las variables de entorno en el dashboard de Railway.
3. Railway detecta automáticamente uvicorn como punto de entrada.
4. Al arrancar en un entorno sin `ml/data/`, el backend descarga y construye
   los datos de Elo de selecciones automáticamente (`_national_data_loop`).

> El archivo `ml/model.pkl` no existe en producción hasta que se corran los scripts
> de ML. Sin él el backend usa las reglas ponderadas como fallback sin interrupciones.

### Frontend — Vercel

1. Importar el repositorio en Vercel apuntando a la carpeta `/frontend`.
2. Agregar la variable `NEXT_PUBLIC_API_URL` con la URL del backend de Railway.
3. Vercel detecta Next.js y construye automáticamente en cada push a `master`.

**CORS:** el backend acepta requests desde `http://localhost:3000`, desde la URL en
`FRONTEND_URL` y desde cualquier dominio `*.vercel.app` (para previews de PR).

---

## Limitaciones conocidas

- **API-Sports 100 req/día:** el backend rastrea la cuota con los headers de respuesta y
  deja de hacer llamadas cuando se agota. Los lesionados y stats post-partido no estarán
  disponibles hasta el día siguiente.
- **football-data.org 10 req/min:** el caché en memoria de 30 minutos asegura que el límite
  no se supere en condiciones normales de uso.
- **Precisión del modelo:** ~67% en datos de test de ligas europeas. El fútbol tiene alta
  varianza intrínseca; los mejores modelos del mundo rara vez superan el 65-70%.
- **StatsBomb:** los perfiles de córners y tarjetas cubren equipos del dataset open source
  de StatsBomb, principalmente clubes de élite europeos. Para otros equipos se usan promedios globales.
- **Selecciones nacionales:** el Elo se actualiza cada 24h; los perfiles StatsBomb no tienen
  cobertura de selecciones, por lo que córners y tarjetas usan siempre promedios globales.
- **Reentrenamiento incremental:** requiere al menos 5 partidos con resultado real nuevos para
  dispararse. Con pocos datos Supabase el modelo no se actualiza automáticamente.
