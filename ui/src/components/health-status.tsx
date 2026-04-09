"use client";

import { useEffect, useState } from "react";

const apiBase = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type HealthPayload = {
  status: string;
  database: { ok: boolean };
  redis: { ok: boolean };
};

export function HealthStatus() {
  const [data, setData] = useState<HealthPayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${apiBase}/health`, { cache: "no-store" })
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<HealthPayload>;
      })
      .then((json) => {
        if (!cancelled) {
          setData(json);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setData(null);
          setError(e instanceof Error ? e.message : "Request failed");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <p className="text-sm text-red-600 dark:text-red-400">
        API health: unreachable ({error})
      </p>
    );
  }

  if (!data) {
    return (
      <p className="text-sm text-zinc-500 dark:text-zinc-400">
        Checking API health…
      </p>
    );
  }

  const badge =
    data.status === "healthy"
      ? "bg-emerald-600 text-white"
      : "bg-amber-600 text-white";

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-zinc-200 bg-zinc-50 p-4 text-left dark:border-zinc-800 dark:bg-zinc-950">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          Backend
        </span>
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${badge}`}
        >
          {data.status}
        </span>
      </div>
      <ul className="text-sm text-zinc-600 dark:text-zinc-400">
        <li>PostgreSQL: {data.database.ok ? "ok" : "down"}</li>
        <li>Redis (Upstash): {data.redis.ok ? "ok" : "down"}</li>
      </ul>
    </div>
  );
}
