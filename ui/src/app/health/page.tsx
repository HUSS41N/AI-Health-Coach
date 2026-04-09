import Link from "next/link";

import { HealthStatus } from "@/components/health-status";

export default function HealthPage() {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center gap-6 bg-zinc-50 p-6 dark:bg-black">
      <div className="w-full max-w-md">
        <HealthStatus />
      </div>
      <Link
        href="/"
        className="text-sm text-emerald-700 underline dark:text-emerald-400"
      >
        ← Back to chat
      </Link>
    </div>
  );
}
