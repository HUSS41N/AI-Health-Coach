export const apiBase =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function getOrCreateUserId(): string {
  if (typeof window === "undefined") return "default";
  let id = localStorage.getItem("ai_coach_uid");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("ai_coach_uid", id);
  }
  return id;
}
