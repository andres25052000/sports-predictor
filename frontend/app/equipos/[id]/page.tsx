"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, BarChart3, Target, Trophy } from "lucide-react";
import { fetchTeamProfile, TeamProfile, TeamRecord } from "@/lib/api";

const CATEGORY_LABEL: Record<string, string> = {
  mundial: "Mundial",
  eliminatoria: "Eliminatorias",
  continental: "Continental",
  amistoso: "Amistosos",
  otro: "Otros",
};

const STAT_LABEL: Record<string, string> = {
  possession: "Posesión %",
  shots: "Tiros",
  shots_on_target: "Tiros al arco",
  corners: "Córners",
  fouls_committed: "Faltas",
  yellow_cards: "Amarillas",
  red_cards: "Rojas",
  xg: "xG",
};

const RESULT_COLOR: Record<string, string> = {
  V: "bg-accent text-black",
  E: "bg-white/10 text-muted",
  D: "bg-danger/80 text-black",
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

/** Fila V/E/D con la proporción de cada resultado. */
function RecordBar({ record }: { record: TeamRecord }) {
  const n = record.played ?? 0;
  if (!n) return null;
  const parts = [
    { key: "V", n: record.wins ?? 0, color: "bg-accent" },
    { key: "E", n: record.draws ?? 0, color: "bg-white/25" },
    { key: "D", n: record.losses ?? 0, color: "bg-danger" },
  ];
  return (
    <div className="flex h-2 rounded-full overflow-hidden bg-white/[0.06]">
      {parts.map((p) => (
        <span key={p.key} className={p.color} style={{ width: `${(p.n / n) * 100}%` }} />
      ))}
    </div>
  );
}

function SplitCard({ title, record }: { title: string; record: TeamRecord }) {
  if (!record?.played) return null;
  return (
    <div className="rounded-2xl bg-surface-2 border border-border px-4 py-3 space-y-2">
      <div className="flex items-baseline justify-between">
        <p className="eyebrow">{title}</p>
        <p className="font-mono text-xs text-muted">{record.played} PJ</p>
      </div>
      <p className="font-mono text-sm text-white">
        {record.wins}V <span className="text-muted-2">·</span> {record.draws}E{" "}
        <span className="text-muted-2">·</span> {record.losses}D
      </p>
      <RecordBar record={record} />
      <p className="text-[11px] text-muted-2">
        {record.goals_avg} goles a favor · {record.conceded_avg} en contra por partido
      </p>
    </div>
  );
}

export default function TeamProfilePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [profile, setProfile] = useState<TeamProfile | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let alive = true;
    fetchTeamProfile(Number(id))
      .then((p) => alive && setProfile(p))
      .catch(() => alive && setError(true));
    return () => {
      alive = false;
    };
  }, [id]);

  if (error) {
    return (
      <div className="px-4 py-16 text-center space-y-3">
        <p className="text-sm text-muted">No encontramos ese equipo.</p>
        <Link href="/equipos" className="text-sm text-accent hover:underline">
          Volver a equipos
        </Link>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-4">
        <div className="h-44 rounded-3xl bg-white/[0.03] animate-pulse" />
        <div className="h-32 rounded-3xl bg-white/[0.03] animate-pulse" />
      </div>
    );
  }

  const { team, record, splits, by_category, form, recent_matches, stats, top_scorers, model } =
    profile;
  const avg = stats?.avg ?? {};

  return (
    <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-6">
      <Link
        href="/equipos"
        className="inline-flex items-center gap-2 text-sm text-muted hover:text-white transition-colors"
      >
        <ArrowLeft size={16} /> Equipos
      </Link>

      {/* Cabecera */}
      <section className="rounded-3xl border border-border bg-gradient-to-br from-accent/[0.12] via-surface to-surface p-5 sm:p-7">
        <p className="eyebrow text-accent">
          {team.type === "national" ? "Selección" : "Club"}
          {team.country ? ` · ${team.country}` : ""}
        </p>
        <h1 className="text-2xl sm:text-4xl font-black tracking-tight text-white mt-1">
          {team.name}
        </h1>

        {form.length > 0 && (
          <div className="flex items-center gap-1.5 mt-4">
            <span className="eyebrow mr-1">Forma</span>
            {form.map((r, i) => (
              <span
                key={i}
                className={`grid place-items-center h-6 w-6 rounded-md text-[11px] font-bold ${RESULT_COLOR[r]}`}
              >
                {r}
              </span>
            ))}
          </div>
        )}

        {record.played ? (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3 mt-6">
              <Stat label="Partidos" value={record.played} />
              <Stat label="% victorias" value={`${record.win_pct}%`} />
              <Stat label="Goles/partido" value={record.goals_avg ?? "—"} />
              <Stat label="Pts/partido" value={record.pts_per_game ?? "—"} />
            </div>
            <div className="mt-4">
              <RecordBar record={record} />
              <p className="text-[11px] text-muted-2 mt-2">
                {record.wins}V · {record.draws}E · {record.losses}D — {record.goals_for} goles
                a favor y {record.goals_against} en contra en toda su historia registrada.
              </p>
            </div>
          </>
        ) : (
          <p className="text-sm text-muted mt-6">
            Todavía no hay partidos con marcador cargados para este equipo.
          </p>
        )}
      </section>

      {/* Modelo (solo selecciones) */}
      {model && (
        <section className="rounded-3xl border border-border bg-surface p-5">
          <p className="eyebrow flex items-center gap-2 mb-4">
            <BarChart3 size={13} /> Según el modelo
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 sm:gap-3">
            {model.elo != null && <Stat label="Elo" value={Math.round(model.elo)} />}
            {model.strength && (
              <>
                <Stat
                  label="Ataque"
                  value={`${model.strength.attack_pctile}`}
                  hint={`percentil de ${model.strength.teams_in_model}`}
                />
                <Stat
                  label="Defensa"
                  value={`${model.strength.defense_pctile}`}
                  hint={`percentil de ${model.strength.teams_in_model}`}
                />
              </>
            )}
          </div>
          <p className="text-[11px] text-muted-2 mt-3">
            Ataque y defensa salen de los parámetros Dixon-Coles del modelo nacional
            (partidos desde 2000). Percentil alto = mejor que el resto de selecciones.
          </p>
        </section>
      )}

      {/* Local / visitante / neutral */}
      <section className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <SplitCard title="De local" record={splits.home} />
        <SplitCard title="De visitante" record={splits.away} />
        <SplitCard title="Cancha neutral" record={splits.neutral} />
      </section>

      {/* Por competición */}
      {by_category.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 mb-3 flex items-center gap-2">
            <Trophy size={13} /> Por competición
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm min-w-[460px]">
              <thead>
                <tr className="text-muted-2 text-[11px] uppercase tracking-wider">
                  <th className="text-left font-medium px-2 py-2">Competición</th>
                  <th className="text-right font-medium px-2 py-2">PJ</th>
                  <th className="text-right font-medium px-2 py-2">V-E-D</th>
                  <th className="text-right font-medium px-2 py-2">% vict.</th>
                  <th className="text-right font-medium px-2 py-2">Goles</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {by_category.map((c) => (
                  <tr key={c.category} className="hover:bg-white/[0.02]">
                    <td className="px-2 py-2.5 text-white">
                      {CATEGORY_LABEL[c.category] ?? c.category}
                    </td>
                    <td className="px-2 py-2.5 text-right font-mono text-muted">{c.played}</td>
                    <td className="px-2 py-2.5 text-right font-mono text-white">
                      {c.wins}-{c.draws}-{c.losses}
                    </td>
                    <td className="px-2 py-2.5 text-right font-mono text-accent">
                      {c.win_pct}%
                    </td>
                    <td className="px-2 py-2.5 text-right font-mono text-muted">
                      {c.goals_for}:{c.goals_against}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Promedios por partido */}
      {Object.keys(avg).length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-5">
          <p className="eyebrow flex items-center gap-2 mb-1">
            <Target size={13} /> Promedios por partido
          </p>
          <p className="text-xs text-muted-2 mb-4">
            Solo sobre los partidos con estadísticas detalladas cargadas.
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-3">
            {Object.entries(avg).map(([key, v]) => (
              <Stat
                key={key}
                label={STAT_LABEL[key] ?? key}
                value={v.value}
                hint={`${v.n} partidos`}
              />
            ))}
          </div>
        </section>
      )}

      {/* Últimos partidos */}
      {recent_matches.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 mb-2">Últimos partidos</p>
          <div className="divide-y divide-border">
            {recent_matches.map((m, i) => (
              <div key={i} className="flex items-center gap-3 px-2 py-2.5">
                <span
                  className={`grid place-items-center h-6 w-6 rounded-md text-[11px] font-bold shrink-0 ${RESULT_COLOR[m.result]}`}
                >
                  {m.result}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-white truncate">
                    {m.was_home ? "vs" : m.neutral ? "vs" : "en"} {m.opponent}
                  </p>
                  <p className="text-[11px] text-muted-2 truncate">
                    {m.date} · {m.tournament}
                    {m.neutral ? " · cancha neutral" : ""}
                  </p>
                </div>
                <span className="font-mono text-sm text-white shrink-0">
                  {m.goals_for}-{m.goals_against}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Goleadores históricos */}
      {top_scorers.length > 0 && (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 mb-2">Máximos goleadores</p>
          <div className="divide-y divide-border">
            {top_scorers.map((s, i) => (
              <div key={s.name} className="flex items-center gap-3 px-2 py-2.5">
                <span className="w-6 text-center font-mono text-xs text-muted-2 shrink-0">
                  {i + 1}
                </span>
                <p className="text-sm text-white truncate flex-1">{s.name}</p>
                <div className="text-right shrink-0">
                  <span className="font-mono text-sm font-bold text-accent">{s.goals}</span>
                  {s.penalties > 0 && (
                    <span className="text-[10px] text-muted-2 ml-2">{s.penalties} pen</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
