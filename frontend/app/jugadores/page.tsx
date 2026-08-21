"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Search, X } from "lucide-react";
import { fetchTopScorers, searchPlayers, Player } from "@/lib/api";

function initials(name: string): string {
  const parts = name.split(/\s+/).filter(Boolean);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function PlayerRow({ player, rank }: { player: Player; rank?: number }) {
  return (
    <Link
      href={`/jugadores/${player.id}`}
      className="flex items-center gap-3 sm:gap-4 rounded-2xl px-2 sm:px-3 py-3 hover:bg-white/[0.03] transition-colors"
    >
      {rank != null && (
        <span className="w-8 text-center font-mono text-sm text-muted-2 shrink-0">
          #{rank}
        </span>
      )}
      <span className="grid place-items-center h-10 w-10 rounded-full bg-accent/15 text-accent font-mono text-xs font-bold shrink-0">
        {initials(player.name)}
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-semibold text-white truncate">{player.name}</p>
        <p className="text-xs text-muted-2 truncate">
          {player.national_team ?? "—"}
          {player.position ? ` · ${player.position}` : ""}
        </p>
      </div>
      <div className="text-right shrink-0">
        <p className="font-mono text-xl font-bold text-accent leading-none">
          {player.goals}
        </p>
        <p className="text-[10px] text-muted-2 mt-1">
          {player.penalties > 0 ? `${player.penalties} pen · ` : ""}
          {player.first_year}–{player.last_year}
        </p>
      </div>
    </Link>
  );
}

export default function JugadoresPage() {
  const [top, setTop] = useState<Player[] | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Player[]>([]);
  const [searching, setSearching] = useState(false);
  const showSearch = query.trim().length >= 2;

  useEffect(() => {
    let alive = true;
    fetchTopScorers(20)
      .then((p) => alive && setTop(p))
      .catch(() => alive && setTop([]));
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
        setResults(await searchPlayers(q));
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
        <p className="eyebrow text-accent">Base de jugadores</p>
        <h1 className="text-2xl sm:text-3xl font-black tracking-tight text-white mt-1">
          Jugadores
        </h1>
        <p className="text-sm text-muted-2 mt-1 max-w-2xl">
          Goles internacionales de carrera de miles de jugadores, desde la base
          de datos propia. Toca un jugador para ver su tarjeta completa.
        </p>
      </div>

      {/* Buscador */}
      <div className="flex items-center gap-2 rounded-2xl border border-border bg-surface px-4 focus-within:border-border-strong transition-colors">
        <Search size={17} className="text-muted-2 shrink-0" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar jugador…"
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

      {/* Resultados de búsqueda */}
      {showSearch ? (
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-4">
          <p className="eyebrow px-2 sm:px-3 mb-1">
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
              {results.map((p, i) => (
                <PlayerRow key={p.id ?? `${p.name}-${i}`} player={p} />
              ))}
            </div>
          )}
        </section>
      ) : (
        /* Ranking de máximos goleadores */
        <section className="rounded-3xl border border-border bg-surface p-3 sm:p-5">
          <p className="eyebrow px-2 sm:px-3 mb-2">Máximos goleadores</p>
          {top === null ? (
            <div className="space-y-1">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-14 rounded-2xl bg-white/[0.03] animate-pulse" />
              ))}
            </div>
          ) : (
            <div className="divide-y divide-border">
              {top.map((p, i) => (
                <PlayerRow key={p.id ?? `${p.name}-${i}`} player={p} rank={i + 1} />
              ))}
            </div>
          )}
        </section>
      )}
    </div>
  );
}
