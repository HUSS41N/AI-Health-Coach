"use client";

import { apiBase } from "@/lib/api";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

type Overview = {
  user_id: string;
  profile: Record<string, unknown>;
  summary: string | null;
  episodic: {
    id: number;
    content: string;
    tags: string[];
    created_at: string;
  }[];
  legacy_memory_rows: {
    id: number;
    type: string;
    content: unknown;
    created_at: string;
  }[];
  message_count: number;
  recent_messages: {
    id: number;
    role: string;
    content: string;
    created_at: string;
    user_feedback: string | null;
  }[];
};

type PromptRow = { key: string; title: string; updated_at: string | null };

export default function AdminPage() {
  const [section, setSection] = useState<"users" | "prompts">("users");
  const [users, setUsers] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [tab, setTab] = useState<"messages" | "memory" | "profile">(
    "messages",
  );
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const [promptList, setPromptList] = useState<PromptRow[]>([]);
  const [promptKey, setPromptKey] = useState<string | null>(null);
  const [promptContent, setPromptContent] = useState("");
  const [promptSaving, setPromptSaving] = useState(false);

  const loadUsers = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/admin/users`);
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      const data = await res.json();
      setUsers(data.users || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPrompts = useCallback(async () => {
    setErr(null);
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/admin/prompts`);
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      const data = await res.json();
      setPromptList(data.prompts || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load prompts");
    } finally {
      setLoading(false);
    }
  }, []);

  const loadPromptDetail = async (key: string) => {
    setErr(null);
    setLoading(true);
    setPromptKey(key);
    try {
      const res = await fetch(
        `${apiBase}/admin/prompts/${encodeURIComponent(key)}`,
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      const data = await res.json();
      setPromptContent(data.content || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load prompt");
      setPromptContent("");
    } finally {
      setLoading(false);
    }
  };

  const savePrompt = async () => {
    if (!promptKey) return;
    setErr(null);
    setPromptSaving(true);
    try {
      const res = await fetch(
        `${apiBase}/admin/prompts/${encodeURIComponent(promptKey)}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: promptContent }),
        },
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      await loadPrompts();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setPromptSaving(false);
    }
  };

  const loadOverview = async (userId: string) => {
    setErr(null);
    setLoading(true);
    setSelected(userId);
    try {
      const res = await fetch(
        `${apiBase}/admin/users/${encodeURIComponent(userId)}/overview`,
      );
      if (!res.ok) {
        const b = await res.json().catch(() => ({}));
        throw new Error(b.detail || res.statusText);
      }
      setOverview(await res.json());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load overview");
      setOverview(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    if (section !== "prompts") return;
    void loadPrompts();
  }, [section, loadPrompts]);

  return (
    <div className="min-h-[100dvh] bg-zinc-100 p-4 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      <div className="mx-auto max-w-5xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-xl font-bold">Reeba — Admin</h1>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex rounded-lg border border-zinc-200 bg-zinc-50 p-0.5 dark:border-zinc-700 dark:bg-zinc-900">
              {(["users", "prompts"] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => {
                    setSection(s);
                    if (s === "users") setPromptKey(null);
                  }}
                  className={`rounded-md px-3 py-1 text-xs font-medium capitalize ${section === s ? "bg-white shadow dark:bg-zinc-800" : "text-zinc-600 dark:text-zinc-400"}`}
                >
                  {s === "prompts" ? "Agent prompts" : s}
                </button>
              ))}
            </div>
            <Link href="/" className="text-sm text-emerald-700 underline">
              ← Chat
            </Link>
          </div>
        </div>

        <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
          <p className="mb-2 text-sm text-zinc-600 dark:text-zinc-400">
            Local / personal build: admin routes are open (no token). Do not
            expose this API publicly without adding auth.
          </p>
          <button
            type="button"
            onClick={() =>
              void (section === "prompts" ? loadPrompts() : loadUsers())
            }
            disabled={loading}
            className="rounded-lg border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-600"
          >
            {section === "prompts" ? "Refresh prompts" : "Refresh users"}
          </button>
        </div>

        {err && (
          <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-100">
            {err}
          </div>
        )}

        {section === "prompts" ? (
          <div className="grid gap-4 md:grid-cols-[240px_1fr]">
            <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-2 text-sm font-semibold text-zinc-500">
                Prompt keys
              </h2>
              <ul className="max-h-[60vh] space-y-1 overflow-y-auto text-sm">
                {promptList.map((p) => (
                  <li key={p.key}>
                    <button
                      type="button"
                      onClick={() => void loadPromptDetail(p.key)}
                      className={`w-full rounded-md px-2 py-1.5 text-left ${promptKey === p.key ? "bg-emerald-100 font-medium dark:bg-emerald-900/40" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
                    >
                      <span className="block truncate font-mono text-xs">
                        {p.key}
                      </span>
                      <span className="block truncate text-[11px] text-zinc-500">
                        {p.title}
                      </span>
                    </button>
                  </li>
                ))}
                {!promptList.length && !loading && (
                  <li className="text-zinc-400">
                    No prompts (restart API to seed)
                  </li>
                )}
              </ul>
            </div>
            <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
              {!promptKey ? (
                <p className="text-sm text-zinc-500">
                  Select a prompt to view or edit. Changes apply on the next LLM
                  call (cached for a short time in Redis).
                </p>
              ) : (
                <>
                  <p className="mb-2 font-mono text-xs text-zinc-500">
                    {promptKey}
                  </p>
                  <textarea
                    className="mb-3 min-h-[320px] w-full rounded-lg border border-zinc-300 bg-white p-3 font-mono text-xs dark:border-zinc-700 dark:bg-zinc-950"
                    value={promptContent}
                    onChange={(e) => setPromptContent(e.target.value)}
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    disabled={promptSaving || !promptContent.trim()}
                    onClick={() => void savePrompt()}
                    className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
                  >
                    {promptSaving ? "Saving…" : "Save prompt"}
                  </button>
                </>
              )}
            </div>
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-[220px_1fr]">
            <div className="rounded-xl border border-zinc-200 bg-white p-3 dark:border-zinc-800 dark:bg-zinc-900">
              <h2 className="mb-2 text-sm font-semibold text-zinc-500">
                User IDs
              </h2>
              <ul className="max-h-[50vh] space-y-1 overflow-y-auto text-sm">
                {users.map((u) => (
                  <li key={u}>
                    <button
                      type="button"
                      onClick={() => void loadOverview(u)}
                      className={`w-full truncate rounded-md px-2 py-1.5 text-left ${selected === u ? "bg-emerald-100 font-medium dark:bg-emerald-900/40" : "hover:bg-zinc-100 dark:hover:bg-zinc-800"}`}
                    >
                      {u}
                    </button>
                  </li>
                ))}
                {!users.length && !loading && (
                  <li className="text-zinc-400">No users yet</li>
                )}
              </ul>
            </div>

            <div className="rounded-xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-900">
              {!overview ? (
                <p className="text-sm text-zinc-500">
                  Select a user to see profile, memory rows, and message
                  history.
                </p>
              ) : (
                <>
                  <div className="mb-3 flex flex-wrap gap-2 border-b border-zinc-200 pb-3 dark:border-zinc-800">
                    <span className="text-sm text-zinc-500">
                      <strong className="text-zinc-800 dark:text-zinc-200">
                        {overview.user_id}
                      </strong>{" "}
                      · {overview.message_count} messages
                    </span>
                  </div>
                  <div className="mb-3 flex gap-1">
                    {(["messages", "memory", "profile"] as const).map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setTab(t)}
                        className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${tab === t ? "bg-emerald-700 text-white" : "bg-zinc-100 dark:bg-zinc-800"}`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>

                  {tab === "messages" && (
                    <div className="max-h-[55vh] space-y-2 overflow-y-auto text-sm">
                      {overview.recent_messages.map((m) => (
                        <div
                          key={m.id}
                          className={`rounded-lg border px-2 py-1.5 ${m.role === "user" ? "border-emerald-200 bg-emerald-50/50 dark:border-emerald-900 dark:bg-emerald-950/20" : "border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-950/50"}`}
                        >
                          <div className="mb-0.5 flex justify-between text-[10px] text-zinc-500">
                            <span className="font-semibold uppercase">
                              {m.role}
                            </span>
                            <span>{m.created_at}</span>
                          </div>
                          <p className="whitespace-pre-wrap">{m.content}</p>
                          {m.user_feedback && (
                            <p className="mt-1 text-[10px] text-zinc-500">
                              Feedback: {m.user_feedback}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {tab === "memory" && (
                    <div className="max-h-[55vh] space-y-4 overflow-y-auto text-xs">
                      <div>
                        <h4 className="mb-2 font-semibold text-zinc-600 dark:text-zinc-400">
                          Episodic (tags + text)
                        </h4>
                        <div className="space-y-2">
                          {overview.episodic.map((r) => (
                            <div
                              key={r.id}
                              className="rounded-lg border border-zinc-200 p-2 dark:border-zinc-800"
                            >
                              <div className="mb-1 flex justify-between text-[10px] text-zinc-500">
                                <span>
                                  {(r.tags || []).join(", ") || "—"}
                                </span>
                                <span>{r.created_at}</span>
                              </div>
                              <p className="whitespace-pre-wrap text-[11px]">
                                {r.content}
                              </p>
                            </div>
                          ))}
                          {!overview.episodic.length && (
                            <p className="text-zinc-400">None</p>
                          )}
                        </div>
                      </div>
                      <div>
                        <h4 className="mb-2 font-semibold text-zinc-600 dark:text-zinc-400">
                          Legacy memory table
                        </h4>
                        <div className="space-y-2">
                          {overview.legacy_memory_rows.map((r) => (
                            <div
                              key={r.id}
                              className="rounded-lg border border-zinc-200 p-2 font-mono dark:border-zinc-800"
                            >
                              <div className="mb-1 flex justify-between text-[10px] text-zinc-500">
                                <span className="font-semibold">{r.type}</span>
                                <span>{r.created_at}</span>
                              </div>
                              <pre className="whitespace-pre-wrap break-all text-[11px]">
                                {JSON.stringify(r.content, null, 2)}
                              </pre>
                            </div>
                          ))}
                          {!overview.legacy_memory_rows.length && (
                            <p className="text-zinc-400">None</p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {tab === "profile" && (
                    <div className="space-y-3 text-sm">
                      <div>
                        <h3 className="mb-1 font-semibold text-zinc-600 dark:text-zinc-400">
                          Merged profile (type=profile)
                        </h3>
                        <pre className="max-h-[30vh] overflow-auto rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-950">
                          {JSON.stringify(overview.profile, null, 2)}
                        </pre>
                      </div>
                      <div>
                        <h3 className="mb-1 font-semibold text-zinc-600 dark:text-zinc-400">
                          Rolling summary
                        </h3>
                        <p className="rounded-lg bg-zinc-50 p-3 text-xs dark:bg-zinc-950">
                          {overview.summary || "—"}
                        </p>
                      </div>
                      <div>
                        <h3 className="mb-1 font-semibold text-zinc-600 dark:text-zinc-400">
                          Episodic snippets
                        </h3>
                        <ul className="list-inside list-disc space-y-1 text-xs">
                          {overview.episodic.map((e) => (
                            <li key={e.id}>
                              {e.content}{" "}
                              <span className="text-zinc-400">
                                ({e.created_at})
                              </span>
                            </li>
                          ))}
                          {!overview.episodic.length && (
                            <li className="text-zinc-400">None</li>
                          )}
                        </ul>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
