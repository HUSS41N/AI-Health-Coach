"use client";

import { CHAT_CONTACTS } from "@/components/chat/contacts-data";
import { InlineInteractiveAttachments } from "@/components/chat/interactive-prompt";
import type { InteractivePayload } from "@/components/chat/types";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { apiBase, getOrCreateUserId } from "@/lib/api";
import {
  ArrowLeft,
  HeartPulse,
  MessageCircle,
  Mic,
  MoreVertical,
  Paperclip,
  Phone,
  Search,
  SendHorizontal,
  Smile,
  Video,
} from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";

/** Matches server `guardrail_max_message_chars` default. */
const MAX_MESSAGE_CHARS = 2000;

/** Hide internal prefixes in the bubble (scale id, quick-reply wrapper). */
function displayUserBubbleText(raw: string): string {
  let s = raw.replace(/^\[[a-zA-Z0-9_]+\]\s*/, "");
  const lower = s.toLowerCase();
  if (lower.startsWith("selected:")) {
    const i = s.indexOf(":");
    s = (i >= 0 ? s.slice(i + 1) : s).trim();
  }
  return s;
}

const CHAT_BG_STYLE: CSSProperties = {
  backgroundColor: "#080c10",
  backgroundImage: `
    radial-gradient(ellipse 120% 80% at 50% -15%, rgba(20, 184, 166, 0.09), transparent 52%),
    radial-gradient(ellipse 80% 50% at 100% 100%, rgba(56, 189, 248, 0.05), transparent 48%),
    linear-gradient(180deg, #0a1016 0%, #070a0e 100%)
  `,
};

type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  user_feedback?: string | null;
  streaming?: boolean;
};

function TypingDots() {
  return (
    <div className="flex gap-1 px-1 py-2" aria-label="Typing">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="h-2 w-2 animate-bounce rounded-full bg-zinc-400"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </div>
  );
}

function MessageSkeleton() {
  return (
    <div className="flex flex-col gap-3 px-3 py-4">
      <div className="h-9 w-[72%] animate-pulse self-end rounded-lg bg-black/5 dark:bg-white/10" />
      <div className="h-14 w-[88%] animate-pulse self-start rounded-lg bg-black/5 dark:bg-white/10" />
      <div className="h-9 w-[55%] animate-pulse self-end rounded-lg bg-black/5 dark:bg-white/10" />
    </div>
  );
}

type PanelProps = {
  /** Mobile: return to chat list (desktop hides back button). */
  onBackToList?: () => void;
};

function ReebaChatPanel({ onBackToList }: PanelProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFailedText, setLastFailedText] = useState<string | null>(null);
  const [interactive, setInteractive] = useState<InteractivePayload | null>(
    null,
  );
  const [searchOpen, setSearchOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [searchDebounced, setSearchDebounced] = useState("");
  const [searchResults, setSearchResults] = useState<
    { id: number; role: string; content: string; created_at: string }[]
  >([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [highlightMessageId, setHighlightMessageId] = useState<number | null>(
    null,
  );
  const searchInputRef = useRef<HTMLInputElement>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const userId = useRef<string>("");
  if (typeof window !== "undefined" && !userId.current) {
    userId.current = getOrCreateUserId();
  }

  const scrollToBottom = useCallback(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  const fetchPage = useCallback(
    async (beforeId?: number) => {
      const params = new URLSearchParams({
        limit: "30",
        user_id: userId.current || getOrCreateUserId(),
      });
      if (beforeId) params.set("before_id", String(beforeId));
      const res = await fetch(`${apiBase}/chat/messages?${params}`);
      if (!res.ok) throw new Error("Failed to load messages");
      return res.json() as Promise<{
        messages: ChatMessage[];
        has_more: boolean;
      }>;
    },
    [],
  );

  useEffect(() => {
    const t = window.setTimeout(() => setSearchDebounced(searchInput.trim()), 320);
    return () => window.clearTimeout(t);
  }, [searchInput]);

  useEffect(() => {
    if (!searchOpen) return;
    const id = window.setTimeout(() => searchInputRef.current?.focus(), 50);
    return () => window.clearTimeout(id);
  }, [searchOpen]);

  useEffect(() => {
    if (!searchOpen || searchDebounced.length < 2) {
      setSearchResults([]);
      setSearchLoading(false);
      return;
    }
    let cancelled = false;
    setSearchLoading(true);
    const uid = userId.current || getOrCreateUserId();
    const params = new URLSearchParams({
      q: searchDebounced,
      user_id: uid,
      limit: "40",
    });
    void fetch(`${apiBase}/chat/messages/search?${params}`)
      .then((r) => r.json())
      .then((data: { matches?: typeof searchResults }) => {
        if (cancelled) return;
        setSearchResults(data.matches || []);
      })
      .catch(() => {
        if (!cancelled) setSearchResults([]);
      })
      .finally(() => {
        if (!cancelled) setSearchLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [searchOpen, searchDebounced]);

  useEffect(() => {
    userId.current = getOrCreateUserId();
    let cancelled = false;
    (async () => {
      try {
        const data = await fetchPage();
        if (cancelled) return;
        setMessages(data.messages);
        setHasMore(data.has_more);
      } catch {
        if (!cancelled) setError("Could not load chat history.");
      } finally {
        if (!cancelled) setLoadingInitial(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [fetchPage]);

  useLayoutEffect(() => {
    if (!loadingInitial && messages.length) {
      scrollToBottom();
    }
  }, [loadingInitial, messages.length, scrollToBottom]);

  const loadOlder = useCallback(async () => {
    if (!hasMore || loadingMore || messages.length === 0) return;
    const first = messages[0];
    const el = scrollRef.current;
    const prevHeight = el?.scrollHeight ?? 0;
    setLoadingMore(true);
    try {
      const data = await fetchPage(first.id);
      setMessages((prev) => [...data.messages, ...prev]);
      setHasMore(data.has_more);
      requestAnimationFrame(() => {
        if (el) {
          const h = el.scrollHeight - prevHeight;
          el.scrollTop += h;
        }
      });
    } catch {
      setError("Could not load older messages.");
    } finally {
      setLoadingMore(false);
    }
  }, [fetchPage, hasMore, loadingMore, messages]);

  useEffect(() => {
    const root = scrollRef.current;
    const node = loadMoreRef.current;
    if (!root || !node || loadingInitial) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) loadOlder();
      },
      { root, rootMargin: "80px" },
    );
    io.observe(node);
    return () => io.disconnect();
  }, [loadOlder, loadingInitial]);

  const sendFeedback = async (messageId: number, vote: "up" | "down") => {
    const uid = userId.current || getOrCreateUserId();
    const res = await fetch(
      `${apiBase}/chat/messages/${messageId}/feedback?user_id=${encodeURIComponent(uid)}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vote }),
      },
    );
    if (!res.ok) return;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === messageId ? { ...m, user_feedback: vote } : m,
      ),
    );
  };

  const parseSseBuffer = (buffer: string) => {
    const events: Record<string, unknown>[] = [];
    const parts = buffer.split("\n\n");
    const rest = parts.pop() ?? "";
    for (const block of parts) {
      const line = block
        .split("\n")
        .find((l) => l.startsWith("data: "));
      if (!line) continue;
      try {
        events.push(JSON.parse(line.slice(6).trim()));
      } catch {
        /* ignore */
      }
    }
    return { events, rest };
  };

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || sending) return;
      setError(null);
      setSending(true);
      setTyping(true);
      setLastFailedText(null);
      setInteractive(null);

      const clientRequestId = crypto.randomUUID();
      let assistantId = -1;
      const optimisticUserId = -Date.now();

      setMessages((prev) => [
        ...prev,
        {
          id: optimisticUserId,
          role: "user",
          content: trimmed,
          created_at: new Date().toISOString(),
        },
        {
          id: -2,
          role: "assistant",
          content: "",
          created_at: new Date().toISOString(),
          streaming: true,
        },
      ]);
      setTyping(false);
      scrollToBottom();

      try {
        const res = await fetch(`${apiBase}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: userId.current || getOrCreateUserId(),
            content: trimmed,
            client_request_id: clientRequestId,
          }),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          const detail =
            typeof body.detail === "string"
              ? body.detail
              : Array.isArray(body.detail)
                ? body.detail.map((d: { msg?: string }) => d.msg).join(", ")
                : res.statusText;
          throw new Error(detail || `Error ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response body");

        const dec = new TextDecoder();
        let buf = "";
        let sawMeta = false;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buf += dec.decode(value, { stream: true });
          const { events, rest } = parseSseBuffer(buf);
          buf = rest;

          for (const evt of events) {
            const type = evt.type as string;
            if (type === "meta") {
              sawMeta = true;
              const uid = evt.user_message_id as number;
              const content =
                typeof evt.user_content === "string"
                  ? evt.user_content
                  : trimmed;
              setMessages((prev) => {
                const copy = [...prev];
                const uIdx = copy.findIndex((m) => m.id === optimisticUserId);
                if (uIdx >= 0) {
                  copy[uIdx] = {
                    id: uid,
                    role: "user",
                    content,
                    created_at: copy[uIdx].created_at,
                  };
                  return copy;
                }
                return [
                  ...prev,
                  {
                    id: uid,
                    role: "user",
                    content,
                    created_at: new Date().toISOString(),
                  },
                  {
                    id: -2,
                    role: "assistant",
                    content: "",
                    created_at: new Date().toISOString(),
                    streaming: true,
                  },
                ];
              });
            } else if (type === "ui") {
              const raw = evt.interactive as InteractivePayload | undefined;
              if (raw && typeof raw === "object") {
                setInteractive({
                  interaction: raw.interaction ?? "none",
                  prompt: String(raw.prompt ?? ""),
                  scale: raw.scale ?? null,
                  choices: Array.isArray(raw.choices) ? raw.choices : [],
                });
              }
            } else if (type === "stream_error") {
              const partial = Boolean(evt.partial);
              const msg =
                (evt.message as string) ||
                (partial
                  ? "Stream interrupted — you can retry if the reply looks incomplete."
                  : "Something went wrong while streaming.");
              setError(msg);
            } else if (type === "token") {
              const t = (evt.text as string) || "";
              setMessages((prev) => {
                const copy = [...prev];
                const idx = copy.findIndex((m) => m.streaming);
                if (idx >= 0) {
                  copy[idx] = {
                    ...copy[idx],
                    content: copy[idx].content + t,
                  };
                }
                return copy;
              });
              scrollToBottom();
            } else if (type === "done") {
              assistantId = evt.assistant_message_id as number;
              setMessages((prev) => {
                const copy = [...prev];
                const idx = copy.findIndex((m) => m.streaming);
                if (idx >= 0) {
                  copy[idx] = {
                    ...copy[idx],
                    id: assistantId,
                    streaming: false,
                  };
                }
                return copy;
              });
            }
          }
        }
        if (!sawMeta) {
          throw new Error("Incomplete response from server");
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Send failed");
        setLastFailedText(trimmed);
        setMessages((prev) =>
          prev.filter(
            (m) => m.id !== optimisticUserId && !m.streaming,
          ),
        );
      } finally {
        setSending(false);
        setTyping(false);
        setMessages((prev) =>
          prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
        );
      }
    },
    [sending, scrollToBottom],
  );

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const t = input;
    setInput("");
    void sendMessage(t);
  };

  const jumpToMessage = (messageId: number) => {
    setSearchOpen(false);
    setSearchInput("");
    setHighlightMessageId(messageId);
    window.setTimeout(() => {
      document
        .getElementById(`msg-${messageId}`)
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    }, 80);
    window.setTimeout(() => setHighlightMessageId(null), 2200);
  };

  return (
    <div
      className="relative flex h-full min-h-0 flex-col font-[system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',Roboto,sans-serif]"
      style={CHAT_BG_STYLE}
    >
      {/* WhatsApp-style header */}
      <header className="flex h-[59px] shrink-0 items-center gap-2 border-b border-white/[0.06] bg-[#0f161d]/95 px-2 pr-3 text-[#e8eef2] shadow-sm backdrop-blur-md dark:bg-[#0f161d]/95">
        {onBackToList ? (
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full hover:bg-white/10 md:hidden"
            aria-label="Back to chats"
            onClick={onBackToList}
          >
            <ArrowLeft className="h-6 w-6" strokeWidth={2} />
          </button>
        ) : (
          <span className="w-2 shrink-0 md:w-0" aria-hidden />
        )}
        <div className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full bg-teal-600/35 ring-2 ring-teal-400/25">
          <HeartPulse className="h-5 w-5 text-teal-100" strokeWidth={2} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[17px] font-semibold leading-tight tracking-tight">
            Health Coach Reeba
          </h1>
          <p className="truncate text-[13px] text-[#9fb0bd]">
            {sending || typing ? "typing…" : "online"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-0.5">
          <span className="hidden sm:inline-flex">
            <button
              type="button"
              className="flex h-10 w-10 items-center justify-center rounded-full text-[#b8c5ce] hover:bg-white/10 hover:text-white"
              aria-label="Video call"
            >
              <Video className="h-5 w-5" strokeWidth={2} />
            </button>
            <button
              type="button"
              className="flex h-10 w-10 items-center justify-center rounded-full text-[#b8c5ce] hover:bg-white/10 hover:text-white"
              aria-label="Voice call"
            >
              <Phone className="h-5 w-5" strokeWidth={2} />
            </button>
          </span>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full text-[#b8c5ce] hover:bg-white/10 hover:text-white"
            aria-label="Search messages"
            onClick={() => {
              setSearchOpen(true);
              setSearchInput("");
            }}
          >
            <Search className="h-5 w-5" strokeWidth={2} />
          </button>
          <button
            type="button"
            className="flex h-10 w-10 items-center justify-center rounded-full text-[#b8c5ce] hover:bg-white/10 hover:text-white"
            aria-label="Menu"
          >
            <MoreVertical className="h-5 w-5" strokeWidth={2} />
          </button>
        </div>
      </header>

      {searchOpen ? (
        <div
          className="absolute inset-0 z-40 flex flex-col bg-[#05080b]/75 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          aria-label="Search messages"
        >
          <div className="flex shrink-0 items-center gap-2 border-b border-white/10 bg-[#0f161d] px-3 py-2">
            <button
              type="button"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[#b8c5ce] hover:bg-white/10"
              aria-label="Close search"
              onClick={() => {
                setSearchOpen(false);
                setSearchInput("");
              }}
            >
              <ArrowLeft className="h-5 w-5" />
            </button>
            <input
              ref={searchInputRef}
              type="search"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search in this chat…"
              className="min-w-0 flex-1 rounded-lg border border-white/10 bg-[#1a222c] px-3 py-2 text-sm text-[#e8eef2] outline-none placeholder:text-[#6b7c88] focus:border-teal-500/50"
            />
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto bg-[#080c10]/95 p-2">
            {searchLoading && (
              <p className="py-4 text-center text-xs text-[#6b7c88]">
                Searching…
              </p>
            )}
            {!searchLoading && searchDebounced.length >= 2 && !searchResults.length && (
              <p className="py-6 text-center text-sm text-[#6b7c88]">
                No messages match.
              </p>
            )}
            {searchDebounced.length < 2 && (
              <p className="py-6 text-center text-sm text-[#6b7c88]">
                Type at least 2 characters.
              </p>
            )}
            <ul className="space-y-1">
              {searchResults.map((hit) => (
                <li key={hit.id}>
                  <button
                    type="button"
                    onClick={() => jumpToMessage(hit.id)}
                    className="w-full rounded-lg border border-white/[0.06] bg-[#121a22]/90 px-3 py-2 text-left transition hover:border-teal-500/30 hover:bg-[#161e28]"
                  >
                    <div className="mb-1 flex justify-between gap-2 text-[10px] uppercase tracking-wide text-[#6b7c88]">
                      <span>{hit.role}</span>
                      <span className="shrink-0 font-normal normal-case text-[#5a6a75]">
                        {hit.created_at}
                      </span>
                    </div>
                    <p className="line-clamp-3 text-left text-[13px] leading-snug text-[#d5dde3]">
                      {hit.content}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 overflow-y-auto overscroll-y-contain"
      >
        {loadingInitial ? (
          <MessageSkeleton />
        ) : (
          <>
            <div ref={loadMoreRef} className="h-1 w-full" />
            {loadingMore && (
              <p className="pb-1 text-center text-[11px] text-zinc-500">
                Loading older messages…
              </p>
            )}
            <div className="flex flex-col gap-1.5 px-2 py-2 pb-3">
              {(() => {
                let lastAssistantIndex = -1;
                for (let i = messages.length - 1; i >= 0; i--) {
                  if (messages[i].role === "assistant") {
                    lastAssistantIndex = i;
                    break;
                  }
                }
                return messages.map((m, index) => {
                  const showInlineQuickReplies =
                    m.role === "assistant" &&
                    index === lastAssistantIndex &&
                    interactive !== null &&
                    interactive.interaction !== "none";
                  return (
                    <div
                      key={`${m.id}-${m.streaming ? "s" : ""}`}
                      id={m.id > 0 ? `msg-${m.id}` : undefined}
                      className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                    >
                      <div
                        className={cn(
                          "flex max-w-[82%] flex-col",
                          m.role === "user" ? "items-end" : "items-start",
                        )}
                      >
                        <div
                          className={cn(
                            "w-full rounded-2xl px-3 py-2 text-[14.2px] leading-[1.45] shadow-sm",
                            m.role === "user"
                              ? "rounded-br-md border border-teal-600/25 bg-gradient-to-br from-teal-800/95 to-teal-900/90 text-[#ecf8f4]"
                              : "rounded-bl-md border border-white/[0.07] bg-[#141c26]/95 text-[#e4eaef]",
                            highlightMessageId === m.id &&
                              "ring-2 ring-teal-400/70 ring-offset-2 ring-offset-[#080c10]",
                          )}
                        >
                          <p className="whitespace-pre-wrap break-words">
                            {m.role === "user"
                              ? displayUserBubbleText(m.content)
                              : m.content}
                            {m.streaming && m.content === "" && <TypingDots />}
                          </p>
                        </div>
                        {m.role === "assistant" && !m.streaming && m.id > 0 && (
                          <div
                            className="mt-1 flex gap-1 px-0.5"
                            role="group"
                            aria-label="Message feedback"
                          >
                            <button
                              type="button"
                              className={`min-h-[36px] min-w-[36px] rounded-full border border-white/[0.08] bg-[#141c26]/80 px-2 py-1.5 text-[15px] leading-none transition active:scale-95 ${m.user_feedback === "up" ? "border-emerald-500/40 bg-emerald-900/35" : "opacity-85 hover:bg-white/10"}`}
                              onClick={() => sendFeedback(m.id, "up")}
                              aria-label="Helpful"
                            >
                              👍
                            </button>
                            <button
                              type="button"
                              className={`min-h-[36px] min-w-[36px] rounded-full border border-white/[0.08] bg-[#141c26]/80 px-2 py-1.5 text-[15px] leading-none transition active:scale-95 ${m.user_feedback === "down" ? "border-rose-500/40 bg-rose-900/35" : "opacity-85 hover:bg-white/10"}`}
                              onClick={() => sendFeedback(m.id, "down")}
                              aria-label="Not helpful"
                            >
                              👎
                            </button>
                          </div>
                        )}
                        {showInlineQuickReplies ? (
                          <InlineInteractiveAttachments
                            payload={interactive}
                            disabled={sending}
                            onChoice={(label) =>
                              void sendMessage(`Selected: ${label}`)
                            }
                            onScaleSubmit={(summary) =>
                              void sendMessage(summary)
                            }
                            onClose={() => setInteractive(null)}
                          />
                        ) : null}
                      </div>
                    </div>
                  );
                });
              })()}
            </div>
            <div ref={bottomRef} className="h-1" />
          </>
        )}
      </div>

      {error && (
        <div className="shrink-0 border-t border-black/10 bg-amber-100 px-3 py-2 text-[13px] text-amber-950 dark:border-white/10 dark:bg-amber-950/40 dark:text-amber-100">
          <div className="flex flex-wrap items-center gap-2">
            <span>{error}</span>
            {lastFailedText && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-7 text-xs"
                onClick={() => void sendMessage(lastFailedText)}
              >
                Retry
              </Button>
            )}
          </div>
        </div>
      )}

      <form
        onSubmit={onSubmit}
        className="flex shrink-0 items-end gap-1.5 border-t border-white/[0.08] bg-[#0c1218]/95 px-2 py-2 backdrop-blur-md"
      >
        <button
          type="button"
          className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#7a8b98] hover:bg-white/5 hover:text-[#b8c5ce]"
          aria-label="Attach"
        >
          <Paperclip className="h-6 w-6" strokeWidth={1.8} />
        </button>
        <button
          type="button"
          className="mb-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#7a8b98] hover:bg-white/5 hover:text-[#b8c5ce]"
          aria-label="Emoji"
        >
          <Smile className="h-6 w-6" strokeWidth={1.8} />
        </button>
        <div className="mb-0.5 flex min-h-[42px] flex-1 flex-col rounded-3xl border border-white/[0.08] bg-[#141c26] px-3 py-2">
          <input
            className="w-full bg-transparent text-[15px] text-[#e8eef2] outline-none placeholder:text-[#5c6d7a]"
            placeholder={`Message (max ${MAX_MESSAGE_CHARS} characters)`}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={sending}
            maxLength={MAX_MESSAGE_CHARS}
            aria-describedby="reeba-msg-limit"
          />
          <div
            id="reeba-msg-limit"
            className="mt-1 text-right text-[10px] tabular-nums text-[#5c6d7a]"
          >
            {input.length}/{MAX_MESSAGE_CHARS}
          </div>
        </div>
        {input.trim() ? (
          <button
            type="submit"
            disabled={sending}
            className="mb-0.5 flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-teal-600 text-white shadow-md shadow-teal-900/40 transition hover:bg-teal-500 disabled:opacity-50"
            aria-label="Send"
          >
            <SendHorizontal className="h-5 w-5" strokeWidth={2.2} />
          </button>
        ) : (
          <button
            type="button"
            className="mb-0.5 flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-[#7a8b98] hover:bg-white/5 hover:text-[#b8c5ce]"
            aria-label="Voice message"
          >
            <Mic className="h-6 w-6" strokeWidth={1.8} />
          </button>
        )}
      </form>

      <div className="flex shrink-0 justify-center gap-4 border-t border-white/[0.06] bg-[#0a0f14] py-1.5 text-[11px] text-[#6b7c88] md:hidden">
        <Link href="/health" className="hover:underline">
          API health
        </Link>
        <Link href="/admin" className="hover:underline">
          Admin
        </Link>
      </div>
    </div>
  );
}

function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState<boolean | null>(null);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const apply = () => setIsDesktop(mq.matches);
    apply();
    mq.addEventListener("change", apply);
    return () => mq.removeEventListener("change", apply);
  }, []);
  return isDesktop;
}

/** WhatsApp Web–style: sidebar + chat on desktop; list ↔ chat on mobile. */
export function CoachChat() {
  const isDesktop = useIsDesktop();
  const [mobileView, setMobileView] = useState<"list" | "chat">("list");
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    if (isDesktop) setMobileView("chat");
  }, [isDesktop]);

  const showSidebar = isDesktop === true || mobileView === "list";
  const showChat = isDesktop === true || mobileView === "chat";

  const openReeba = () => setMobileView("chat");

  const onContactClick = (messagable: boolean) => {
    if (messagable) openReeba();
    else {
      setToast(
        "You can only message Health Coach Reeba. Other contacts are demo entries.",
      );
      window.setTimeout(() => setToast(null), 4500);
    }
  };

  if (isDesktop === null) {
    return (
      <div className="flex h-[100dvh] w-full items-center justify-center bg-[#0a0f14] text-sm text-[#6b7c88]">
        Loading…
      </div>
    );
  }

  return (
    <div className="relative flex h-[100dvh] w-full max-w-[1680px] overflow-hidden border border-white/[0.06] bg-[#06090d] font-[system-ui,-apple-system,BlinkMacSystemFont,'Segoe_UI',Roboto,sans-serif] md:mx-auto md:shadow-2xl md:shadow-black/50">
      {/* Sidebar — chat list (desktop WhatsApp left rail) */}
      <aside
        className={cn(
          "flex min-w-0 flex-col border-[#1e2832] bg-[#0c1218] md:w-[min(400px,32vw)] md:max-w-[420px] md:border-r",
          showSidebar ? "flex w-full" : "hidden",
          "md:flex",
        )}
      >
        <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-white/[0.06] bg-[#0f161d] px-4">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#1a222c]">
            <MessageCircle className="h-5 w-5 text-[#7a8b98]" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-lg font-semibold text-[#e8eef2]">
              Chats
            </h2>
            <p className="truncate text-xs text-[#6b7c88]">Health Coach</p>
          </div>
          <div className="hidden gap-1 sm:flex">
            <Link
              href="/health"
              className="rounded-full px-2 py-1 text-[11px] text-teal-400/90 hover:bg-white/10"
            >
              API
            </Link>
            <Link
              href="/admin"
              className="rounded-full px-2 py-1 text-[11px] text-teal-400/90 hover:bg-white/10"
            >
              Admin
            </Link>
          </div>
        </header>
        <div className="border-b border-white/[0.06] px-3 py-2">
          <div className="flex items-center gap-2 rounded-lg border border-white/[0.06] bg-[#141c26] px-3 py-1.5">
            <Search className="h-4 w-4 shrink-0 text-[#6b7c88]" />
            <input
              type="search"
              readOnly
              placeholder="Filter chats (demo)"
              className="w-full cursor-default bg-transparent text-sm text-[#b8c5ce] outline-none placeholder:text-[#5c6d7a]"
              aria-label="Search placeholder"
            />
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {CHAT_CONTACTS.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => onContactClick(c.messagable)}
              className={cn(
                "flex w-full gap-3 border-b border-white/[0.05] px-3 py-3 text-left transition hover:bg-[#141c26]",
                c.messagable && "bg-[#121a22]",
              )}
            >
              <span
                className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-[#1a222c] text-xl"
                aria-hidden
              >
                {c.avatar}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="truncate font-medium text-[#e8eef2]">
                    {c.name}
                  </span>
                  {c.time ? (
                    <span className="shrink-0 text-[11px] text-[#6b7c88]">
                      {c.time}
                    </span>
                  ) : null}
                </div>
                <p className="truncate text-sm text-[#7a8b98]">
                  {c.subtitle}
                </p>
                {!c.messagable && (
                  <span className="mt-0.5 inline-block rounded bg-[#1a222c] px-1.5 py-0.5 text-[10px] font-medium text-[#8a9aa8]">
                    View only
                  </span>
                )}
              </div>
            </button>
          ))}
        </div>
        <p className="shrink-0 border-t border-white/[0.06] px-3 py-2 text-center text-[10px] text-[#5c6d7a]">
          Demo contacts cannot receive messages. Only Reeba is live.
        </p>
      </aside>

      {/* Main conversation */}
      <main
        className={cn(
          "min-h-0 min-w-0 flex-1 flex-col",
          showChat ? "flex" : "hidden",
          "md:flex",
        )}
      >
        <ReebaChatPanel
          onBackToList={
            isDesktop
              ? undefined
              : () => {
                  setMobileView("list");
                }
          }
        />
      </main>

      {toast && (
        <div
          role="status"
          className="fixed bottom-6 left-1/2 z-50 max-w-[90vw] -translate-x-1/2 rounded-lg bg-[#323232] px-4 py-2.5 text-center text-sm text-white shadow-lg"
        >
          {toast}
        </div>
      )}
    </div>
  );
}
