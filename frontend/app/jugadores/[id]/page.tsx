"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Target, Trophy, Calendar, Shirt } from "lucide-react";
import { fetchPlayerProfile, PlayerProfile } from "@/lib/api";

/** Iniciales del jugador para el avatar (mismo criterio que el listado). */
function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

const CATEGORY_LABEL: Record<string, string> = {
  mundial: "Mundial",
  eliminatoria: "Eliminatorias",
  continental: "Continental",
  amistoso: "Amistosos",
  otro: "Otros",
};

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="rounded-2xl bg-surface-2 border border-border px-3 py-3 text-center">
      <p className="font-mono text-2xl font-bold text-accent leading-none">{value}</p>
      <p className="eyebrow mt-2">{label}</p>
      {hint && <p className="text-[10px] text-muted-2 mt-0.5">{hint}</p>}
    </div>
  );
}

/** Barras de goles por categoría de torneo (proporción sobre el máximo). */
function CategoryBars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  if (entries.length === 0) return null;
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-2">
      {entries.map(([cat, n]) => (
        <div key={cat} className="flex items-center gap-3">
          <span className="w-28 shrink-0 text-xs text-muted truncate">
            {CATEGORY_LABEL[cat] ?? cat}
          </span>
          <div className="flex-1 h-2 rounded-full bg-white/[0.06] overflow-hidden">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${(n / max) * 100}%` }}
            />
          </div>
          <span className="w-8 text-right font-mono text-xs text-white">{n}</span>
        </div>
      ))}
    </div>
  );
}

export default function PlayerCardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [profile, setProfile] = useState<PlayerProfile | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchPlayerProfile(Number(id))
      .then((p) => alive && setProfile(p))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) {
    return (
      <div className="px-4 py-16 text-center space-y-3">
        <p className="text-sm text-muted">No encontramos a ese jugador.</p>
        <Link href="/jugadores" className="text-sm text-accent hover:underline">
          Volver a jugadores
        </Link>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-4">
        <div className="h-48 rounded-3xl bg-white/[0.03] animate-pulse" />
        <div className="h-32 rounded-3xl bg-white/[0.03] animate-pulse" />
      </div>
    );
  }

  const { player, career, goals_breakdown, recent_goals, match_stats_summary, recent_matches } = profile;
  const summary = match_stats_summary ?? {};
  const totals = summary.totals ?? {};
  const perMatch = summary.per_match ?? {};

  return (
    <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-6">
      <Link
        href="/jugadores"
        className="inline-flex items-center gap-2 text-sm text-muted hover:text-white transition-colors"
      >
        <ArrowLeft size={16} /> Jugadores
      </Link>

      {/* Tarjeta principal */}
      <section className="rounded-3xl border border-border bg-gradient-to-br from-accent/[0.12] via-surface to-surface p-5 sm:p-7">
        <div className="flex items-start gap-4 sm:gap-6">
          <span className="grid place-items-center h-20 w-20 sm:h-24 sm:w-24 rounded-2xl bg-accent/15 text-accent font-mono text-2xl font-black shrink-0">
            {initials(player.name)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="eyebrow text-accent">
              {player.national_team ?? player.nationality ?? "Selección"}
            </p>
            <h1 className="text-2xl sm:text-4xl font-black tracking-tight text-white mt-1 break-words">
              {player.name}
            </h1>
            <p className="text-sm text-muted mt-2">
              {[
                player.position,
                player.age != null ? `${player.age} años` : null,
                player.current_club,
              ]
                .filter(Boolean)
                .join(" · ") || "Sin ficha detallada"}
            </p>
          </div>
        </div>

        {/* Números de carrera (goles internacionales) */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mt-6">
          <Stat label="Goles" value={career.goals ?? "—"} />
          <Stat label="Penales" value={career.penalties ?? 0} />
          <Stat label="Partidos con gol" value={career.matches_scored ?? "—"} />
          <Stat
            label="Trayectoria"
            value={
              career.first_year && career.last_year
                ? `${career.first_year}–${career.last_year}`
                : "—"
            }
          />
        </div>
        <p className="text-[11px] text-muted-2 mt-3">
          Goles internacionales con su selección (base propia, 1872–hoy).
        </p>
      </section>

      {/* Reparto de goles */}
      {Object.keys(goals_breakdown.by_category).length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-5">
          <p className="eyebrow flex items-center gap-2 mb-3">
            <Trophy size={13} /> Goles por competición
          </p>
          <CategoryBars data={goals_breakdown.by_category} />
        </section>
      )}

      {/* Stats por partido (StatsBomb) */}
      {summary.matches ? (
        <section className="rounded-3xl border border-border bg-surface p-5">
          <p className="eyebrow flex items-center gap-2 mb-1">
            <Target size={13} /> Rendimiento por partido
          </p>
          <p className="text-xs text-muted-2 mb-4">
            {summary.matches} partidos con datos detallados
            {summary.position ? ` · posición habitual: ${summary.position}` : ""}
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            <Stat label="xG total" value={totals.xg ?? "—"} hint={`${perMatch.xg ?? "—"} / partido`} />
            <Stat label="Asistencias" value={totals.assists ?? 0} hint={`${perMatch.assists ?? 0} / partido`} />
            <Stat label="Tiros" value={totals.shots ?? 0} hint={`${perMatch.shots ?? 0} / partido`} />
            <Stat label="Pases clave" value={totals.key_passes ?? 0} hint={`${perMatch.key_passes ?? 0} / partido`} />
          </div>
        </section>
      ) : null}

      {/* Últimos partidos con datos */}
      {recent_matches.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 mb-2 flex items-center gap-2">
            <Shirt size={13} /> Últimos partidos
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[520px]">
              <thead>
                <tr className="text-muted-2 text-[11px] uppercase tracking-wider">
                  <th className="text-left font-medium px-2 py-2">Partido</th>
                  <th className="text-right font-medium px-2 py-2">G</th>
                  <th className="text-right font-medium px-2 py-2">A</th>
                  <th className="text-right font-medium px-2 py-2">Tiros</th>
                  <th className="text-right font-medium px-2 py-2">xG</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {recent_matches.map((m, i) => (
                  <tr key={i} className="hover:bg-white/[0.02]">
                    <td className="px-2 py-2.5">
                      <p className="text-white truncate">
                        {m.home_team} {m.score ?? "vs"} {m.away_team}
                      </p>
                      <p className="text-[11px] text-muted-2">
                        {m.date} · {m.tournament}
                      </p>
                    </td>
                    <td className="px-2 py-2.5 text-right font-mono text-accent">{m.goals}</td>
                    <td className="px-2 py-2.5 text-right font-mono text-white">{m.assists}</td>
                    <td className="px-2 py-2.5 text-right font-mono text-muted">{m.shots}</td>
                    <td className="px-2 py-2.5 text-right font-mono text-muted">
                      {m.xg != null ? m.xg.toFixed(2) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Últimos goles */}
      {recent_goals.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 mb-2 flex items-center gap-2">
            <Calendar size={13} /> Últimos goles
          </p>
          <div className="divide-y divide-border">
            {recent_goals.map((g, i) => (
              <div key={i} className="flex items-center gap-3 px-2 py-2.5">
                <span className="font-mono text-xs text-accent w-10 shrink-0">
                  {g.minute != null ? `${g.minute}'` : "—"}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white truncate">
                    {g.opponent ? `vs ${g.opponent}` : `${g.home_team} - ${g.away_team}`}
                    {g.penalty && (
                      <span className="ml-2 text-[10px] text-muted-2 uppercase">penal</span>
                    )}
                  </p>
                  <p className="text-[11px] text-muted-2 truncate">
                    {g.date} · {g.tournament}
                    {g.score ? ` · ${g.score}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Trayectoria de clubes (Wikidata) */}
      {profile.club_history.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-5">
          <p className="eyebrow mb-3">Trayectoria de clubes</p>
          <ol className="space-y-2">
            {profile.club_history.map((t, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <span className="font-mono text-xs text-muted-2 w-24 shrink-0">
                  {t.start ?? "?"}–{t.end ?? "hoy"}
                </span>
                <span className="text-white truncate">{t.team}</span>
              </li>
            ))}
          </ol>
          <p className="text-[11px] text-muted-2 mt-3">
            Fuente: Wikidata. Puede tener imprecisiones en el club actual.
          </p>
        </section>
      )}
    </div>
  );
}
