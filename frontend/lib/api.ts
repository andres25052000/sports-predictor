import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const api = axios.create({ baseURL: API_URL });

export interface Match {
  home: string;
  away: string;
  home_id?: number;
  away_id?: number;
  date?: string;
  home_crest?: string;
  away_crest?: string;
}

export interface Factor {
  name: string;
  weight: number;
  advantage: string;
  detail: string;
}

export interface RecentMatch {
  opponent: string;
  goals_for: number;
  goals_against: number;
  result: "V" | "E" | "D";
  was_home: boolean;
  date: string;
}

export interface TeamData {
  ranking: number;
  league: string;
  recent_matches: RecentMatch[];
}

export interface InjuredPlayer {
  name: string;
  reason: string;
  photo?: string;
}

export interface Stadium {
  name: string;
  city: string;
  capacity?: number;
  surface?: string;
  image?: string;
  home_team_logo?: string;
}

export interface Weather {
  city: string;
  date: string;
  temp_max: number;
  temp_min: number;
  precipitation: number;
  windspeed: number;
  description: string;
  emoji: string;
  impact: string;
}

export interface PoissonData {
  expected_goals:   { home: number; away: number; total: number };
  result_1x2:       { home_win: number; draw: number; away_win: number };
  over_under:       Record<string, number>;
  btts:             { yes: number; no: number };
  exact_score:      { score: string; home: number; away: number; prob: number }[];
  half_time:        { home_win: number; draw: number; away_win: number };
  handicap?:        Record<string, number>;
  home_goals:       Record<string, number>;
  away_goals:       Record<string, number>;
  home_clean_sheet: { yes: number; no: number };
  away_clean_sheet: { yes: number; no: number };
}

export interface CornerCardsData {
  data_source: "statsbomb" | "global_average";
  corners: {
    expected_home: number;
    expected_away: number;
    expected_total: number;
    over_under: Record<string, number>;
    home_more: number;
    away_more: number;
    equal: number;
  };
  yellow_cards: {
    expected_home: number;
    expected_away: number;
    expected_total: number;
    over_under: Record<string, number>;
    home_dist: Record<string, number>;
    away_dist: Record<string, number>;
  };
  fouls: {
    expected_home: number;
    expected_away: number;
    expected_total: number;
  };
}

export interface OddsMarket {
  odds: number;   // mejor cuota decimal disponible
  prob: number;   // probabilidad del modelo (%)
  ev: number;     // valor esperado por unidad apostada (>0 = hay valor)
  value: boolean; // true si ev > 0
}

export interface OddsData {
  source: string;
  bookmaker_count: number;
  commence_time?: string | null;
  // claves: "1" | "X" | "2" | "over_2.5" | "under_2.5" ...
  markets: Record<string, OddsMarket>;
  best_value: ({ market: string } & OddsMarket)[];
}

export interface Prediction {
  home_team: string;
  away_team: string;
  probabilities: {
    home_win: number;
    draw: number;
    away_win: number;
  };
  factors: Factor[];
  model: string;
  poisson?: PoissonData;
  corners_cards?: CornerCardsData;
  odds?: OddsData;
  team_stats?: {
    home: TeamData;
    away: TeamData;
  };
  injuries?: {
    home: { team: string; players: InjuredPlayer[] };
    away: { team: string; players: InjuredPlayer[] };
  };
  stadium?: Stadium;
  weather?: Weather;
}

export interface League {
  name: string;
  region: string;
}

export interface UpcomingMatch extends Match {
  league: string;
}

export async function fetchLeagues(): Promise<League[]> {
  const { data } = await api.get("/leagues");
  return data.leagues;
}

export interface UpcomingResponse {
  matches: UpcomingMatch[];
  betplay_quota: { exhausted: boolean; remaining: number | null };
}

export async function fetchUpcoming(): Promise<UpcomingResponse> {
  const { data } = await api.get("/upcoming");
  return data;
}

export async function fetchMatches(league: string): Promise<Match[]> {
  const { data } = await api.get(`/leagues/${encodeURIComponent(league)}/matches`);
  return data.matches;
}


/* ── Track record / estadísticas públicas ────────────────────────────────── */

export interface GlobalStats {
  total_predictions: number;
  evaluated: number;
  correct: number;
  accuracy: number | null;
  pending: number;
  by_league: Record<string, { total: number; correct: number }>;
}

export interface MarketStats {
  result_1x2:    { n: number; accuracy: number | null };
  over_under_25: { n: number; accuracy: number | null };
  btts:          { n: number; accuracy: number | null };
  corners:       { n: number; line_9_5_accuracy: number | null; avg_error: number | null };
  yellow_cards:  { n: number; line_3_5_accuracy: number | null; avg_error: number | null };
}

export interface PredictionRecord {
  id: number;
  home_team: string;
  away_team: string;
  league: string | null;
  match_date: string | null;
  created_at: string;
  home_crest: string | null;
  away_crest: string | null;
  pred_winner: string | null;
  confidence: number | null;
  result_actual: string | null;
  result_home_goals: number | null;
  result_away_goals: number | null;
  was_correct: boolean | null;
}

export async function fetchStats(): Promise<GlobalStats> {
  const { data } = await api.get("/predictions/stats");
  return data;
}

export async function fetchMarketStats(): Promise<MarketStats> {
  const { data } = await api.get("/predictions/market-stats");
  return data;
}

/** Feed público: últimos partidos distintos predichos (sin datos de usuario). */
export async function fetchRecentPublic(limit = 10): Promise<PredictionRecord[]> {
  const { data } = await api.get(`/predictions/recent?limit=${limit}`);
  return data.predictions ?? [];
}

export interface MyPredictionsResponse {
  predictions: PredictionRecord[];
  is_admin: boolean;
}

/** Historial del usuario autenticado (o todo, si es administrador). */
export async function fetchMyPredictions(token: string, limit = 100): Promise<MyPredictionsResponse> {
  const { data } = await api.get(`/predictions/mine?limit=${limit}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  return { predictions: data.predictions ?? [], is_admin: !!data.is_admin };
}

export interface AdminUserStats {
  registered: number;
  active: number;
  window_minutes: number;
}

/** Estadísticas de usuarios (solo admin): registrados y activos ahora. */
export async function fetchAdminStats(token: string): Promise<AdminUserStats> {
  const { data } = await api.get("/admin/stats", {
    headers: { Authorization: `Bearer ${token}` },
  });
  return data;
}

/* ── NBA ──────────────────────────────────────────────────────────────────── */

export interface NbaTeam {
  name: string;
  logo: string;
}

export interface NbaPrediction {
  sport: "nba";
  home_team: string;
  away_team: string;
  model: string;
  probabilities: { home_win: number; away_win: number };
  elo: { home: number; away: number; matched_home: string; matched_away: string };
  expected_points: { home: number; away: number; total: number; margin: number };
  over_under: Record<string, { over: number; under: number }>;
  handicap: Record<string, number>;
  meta: { scoring_season: string | null; has_home_stats: boolean; has_away_stats: boolean };
  odds?: OddsData;
  prediction_id?: number;
}

export async function fetchNbaTeams(): Promise<{ teams: NbaTeam[]; ready: boolean }> {
  const { data } = await api.get("/nba/teams");
  return { teams: data.teams ?? [], ready: !!data.ready };
}

export async function fetchNbaPrediction(home: string, away: string, token: string): Promise<NbaPrediction> {
  const { data } = await api.post(
    "/nba/predict",
    { home_team: home, away_team: away },
    { headers: { Authorization: `Bearer ${token}` } },
  );
  return data;
}

/* ── Jugadores (tarjeta de goleador) ──────────────────────────────────────── */

export interface Player {
  id: number;
  name: string;
  national_team: string | null;
  current_club: string | null;
  position: string | null;
  goals: number;
  penalties: number;
  own_goals: number;
  matches_scored: number | null;
  first_year: number | null;
  last_year: number | null;
}

/** Máximos goleadores (goles internacionales de carrera) desde la base propia. */
export async function fetchTopScorers(limit = 20): Promise<Player[]> {
  const { data } = await api.get(`/players/top?limit=${limit}`);
  return data.players ?? [];
}

/** Busca jugadores por nombre en la base propia. */
export async function searchPlayers(q: string): Promise<Player[]> {
  const { data } = await api.get(`/players/search?q=${encodeURIComponent(q)}`);
  return data.players ?? [];
}

/* ── Tarjeta de jugador (perfil completo) ─────────────────────────────────── */

export interface PlayerGoal {
  date: string | null;
  tournament: string | null;
  category: string | null;
  team: string | null;
  opponent: string | null;
  home_team: string | null;
  away_team: string | null;
  score: string | null;
  minute: number | null;
  penalty: boolean;
  own_goal: boolean;
}

export interface PlayerMatchStat {
  date: string | null;
  tournament: string | null;
  home_team: string | null;
  away_team: string | null;
  score: string | null;
  position: string | null;
  minutes: number | null;
  goals: number;
  assists: number;
  shots: number;
  shots_on_target: number;
  xg: number | null;
  passes: number;
  key_passes: number;
  fouls: number;
}

export interface TeamSpell {
  team: string;
  start: string | null;
  end: string | null;
  national: boolean;
}

export interface PlayerProfile {
  player: {
    id: number;
    name: string;
    birthdate: string | null;
    age: number | null;
    nationality: string | null;
    position: string | null;
    national_team: string | null;
    current_club: string | null;
    wikidata_id: string | null;
  };
  career: {
    goals: number | null;
    penalties: number;
    own_goals: number;
    matches_scored: number | null;
    first_year: number | null;
    last_year: number | null;
  };
  club_history: TeamSpell[];
  national_history: TeamSpell[];
  goals_breakdown: {
    by_category: Record<string, number>;
    by_year: { year: string; goals: number }[];
  };
  recent_goals: PlayerGoal[];
  match_stats_summary: {
    matches?: number;
    totals?: Record<string, number | null>;
    per_match?: Record<string, number>;
    position?: string | null;
  };
  recent_matches: PlayerMatchStat[];
}

/** Tarjeta completa de un jugador (ficha, goles de carrera y stats por partido). */
export async function fetchPlayerProfile(id: number): Promise<PlayerProfile> {
  const { data } = await api.get(`/players/${id}`);
  return data;
}

export async function fetchPrediction(match: Match, league: string, token?: string | null): Promise<Prediction> {
  const { data } = await api.post(
    "/predict",
    {
      home_team:  match.home,
      away_team:  match.away,
      home_id:    match.home_id,
      away_id:    match.away_id,
      match_date: match.date,
      league,
    },
    token ? { headers: { Authorization: `Bearer ${token}` } } : undefined,
  );
  return data;
}
