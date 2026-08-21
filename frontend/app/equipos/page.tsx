"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, X } from "lucide-react";
import {
  fetchTeamRankings,
  searchScoutingTeams,
  ScoutingTeam,
  TeamRanking,
} from "@/lib/api";

/** Cuadritos V/E/D de los últimos 5 partidos a partir del conteo del artefacto. */
function FormDots({ w, d, l }: { w: number; d: number; l: number }) {
  const dots = [
    ...Array(w).fill("V"),
    ...Array(d).fill("E"),
    ...Array(l).fill("D"),
  ];
  const color: Record<string, string> = {
    V: "bg-accent",
    E: "bg-muted-2",
    D: "bg-danger",
  };
  return (
    <div className="flex gap-1">
      {dots.map((r, i) => (
        <span key={i} className={`h-1.5 w-4 rounded-full ${color[r]}`} />
      ))}
    </div>
  );
}

function TeamResultRow({ team }: { team: ScoutingTeam }) {
  return (
    <Link
      href={`/equipos/${team.id}`}
      className="flex items-center gap-3 rounded-2xl px-3 py-3 hover:bg-white/[0.03] transition-colors"
    >
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-white truncate">{team.name}</p>
        <p className="text-xs text-muted-2 truncate">
          {team.type === "national" ? "Selección" : "Club"}
          {team.country ? ` · ${team.country}` : ""}
        </p>
      </div>
    </Link>
  );
}

export default function EquiposPage() {
  const [ranking, setRanking] = useState<TeamRanking[] | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<ScoutingTeam[]>([]);
  const [searching, setSearching] = useState(false);
  const showSearch = query.trim().length >= 2;

  useEffect(() => {
    let alive = true;
    fetchTeamRankings(25)
      .then((t) => alive && setRanking(t))
      .catch(() => alive && setRanking([]));
    return () => {
      alive = false;
    };
  }, []);

  useEffect(() => {
    const q = query.trim();
    if (q.length < 2) return;
    const t = setTimeout(async () => {
      setSearching(true);
      try {
        setResults(await searchScoutingTeams(q));
      } catch {
        setResults([]);
      } finally {
        setSearching(false);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [query]);

  return (
    <div className="px-4 sm:px-6 py-6 max-w-4xl mx-auto space-y-6">
      <div>
        <p className="eyebrow text-accent">Base de equipos</p>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white mt-1">
          Equipos
        </h1>
        <p className="text-sm text-muted-2 mt-1 max-w-2xl">
          970 equipos entre clubes y selecciones, con su historial completo desde
          la base propia. El ranking usa el Elo del modelo, no el de la FIFA.
        </p>
      </div>

      <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface px-4 focus-within:border-border-strong transition-colors">
        <Search size={17} className="text-muted-2 shrink-0" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar equipo o selección…"
          className="flex-1 bg-transparent py-3.5 text-sm text-white placeholder-muted-2 focus:outline-none"
        />
        {query && (
          <button
            onClick={() => setQuery("")}
            className="text-muted-2 hover:text-white shrink-0"
            aria-label="Limpiar"
          >
            <X size={16} />
          </button>
        )}
      </div>

      {showSearch ? (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-4">
          <p className="eyebrow px-3 mb-1">
            {searching
              ? "Buscando…"
              : `${results.length} resultado${results.length !== 1 ? "s" : ""}`}
          </p>
          {results.length === 0 && !searching ? (
            <p className="text-sm text-muted-2 px-3 py-6 text-center">
              Sin coincidencias para “{query}”.
            </p>
          ) : (
            <div className="divide-y divide-border">
              {results.map((t) => (
                <TeamResultRow key={t.id} team={t} />
              ))}
            </div>
          )}
        </section>
      ) : (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-3 mb-1">Selecciones por Elo</p>
          <p className="text-xs text-muted-2 px-3 mb-3">
            Elo calculado sobre 49.475 partidos internacionales.
          </p>
          {ranking === null ? (
            <div className="space-y-1">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-14 rounded-2xl bg-white/[0.03] animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="divide-y divide-border">
              {ranking.map((t, i) => {
                const row = (
                  <>
                    <span className="w-8 text-center font-mono text-sm text-muted-2 shrink-0">
                      #{i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-white truncate">
                        {t.name}
                      </p>
                      {t.wins_last5 != null && (
                        <div className="mt-1.5">
                          <FormDots
                            w={t.wins_last5 ?? 0}
                            d={t.draws_last5 ?? 0}
                            l={t.losses_last5 ?? 0}
                          />
                        </div>
                      )}
                    </div>
                    <div className="text-right shrink-0">
                      <p className="font-mono text-lg font-bold text-accent leading-none">
                        {Math.round(t.elo)}
                      </p>
                      <p className="text-[10px] text-muted-2 mt-1">
                        {t.pts_per_game != null ? `${t.pts_per_game} pts/p` : "Elo"}
                      </p>
                    </div>
                  </>
                );
                return t.id ? (
                  <Link
                    key={t.name}
                    href={`/equipos/${t.id}`}
                    className="flex items-center gap-3 rounded-2xl px-2 sm:px-3 py-3 hover:bg-white/[0.03] transition-colors"
                  >
                    {row}
                  </Link>
                ) : (
                  <div
                    key={t.name}
                    className="flex items-center gap-3 rounded-2xl px-2 sm:px-3 py-3"
                  >
                    {row}
                  </div>
                );
              })}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
