"use client";

import { useState } from "react";

import { cn } from "@/lib/utils";

import type { ChoiceItem, InteractivePayload, ScaleConfig } from "./types";

type Props = {
  payload: InteractivePayload | null;
  disabled?: boolean;
  onChoice: (label: string) => void;
  onScaleSubmit: (summary: string) => void;
  onClose: () => void;
};

const CHOICE_BTN_CLASS =
  "rounded-full border border-[#008069]/30 bg-[#008069]/10 px-3 py-1.5 text-left text-[13px] font-medium text-[#005c4b] transition active:scale-[0.98] disabled:opacity-50 dark:border-emerald-500/30 dark:bg-emerald-900/40 dark:text-emerald-100";

function ChoiceChips({
  choices,
  disabled,
  onChoice,
}: {
  choices: ChoiceItem[];
  disabled?: boolean;
  onChoice: (label: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {choices.map((c: ChoiceItem) => (
        <button
          key={c.id}
          type="button"
          disabled={disabled}
          onClick={() => onChoice(c.label)}
          className={CHOICE_BTN_CLASS}
        >
          {c.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Quick replies / scale shown under the latest assistant bubble (tap without scrolling to the composer dock).
 */
export function InlineInteractiveAttachments({
  payload,
  disabled,
  onChoice,
  onScaleSubmit,
  onClose,
}: Props) {
  if (!payload || payload.interaction === "none") return null;

  if (payload.interaction === "choices" && payload.choices.length > 0) {
    return (
      <div className="mt-1.5 w-full min-w-0 space-y-1.5">
        <div className="flex items-start justify-between gap-2">
          <p className="text-[12px] font-medium leading-snug text-[#9fb0bd]">
            {payload.prompt || "Tap a quick reply or type below"}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-[11px] text-[#6b7c88] underline"
          >
            Hide
          </button>
        </div>
        <ChoiceChips
          choices={payload.choices}
          disabled={disabled}
          onChoice={onChoice}
        />
      </div>
    );
  }

  if (payload.interaction === "scale" && payload.scale) {
    return (
      <div className="mt-1.5 w-full min-w-0 rounded-xl border border-white/[0.08] bg-[#0f161d]/90 px-2.5 py-2.5">
        <ScaleBlock
          scale={payload.scale}
          prompt={payload.prompt}
          disabled={disabled}
          onSubmit={onScaleSubmit}
          onClose={onClose}
          variant="inline"
        />
      </div>
    );
  }

  return null;
}

export function InteractivePrompt({
  payload,
  disabled,
  onChoice,
  onScaleSubmit,
  onClose,
}: Props) {
  if (!payload || payload.interaction === "none") return null;

  if (payload.interaction === "choices" && payload.choices.length > 0) {
    return (
      <div className="border-t border-black/8 bg-white/95 px-3 py-3 shadow-[0_-4px_12px_rgba(0,0,0,0.06)] dark:border-white/10 dark:bg-zinc-900/95">
        <div className="mb-2 flex items-start justify-between gap-2">
          <p className="text-[13px] font-medium leading-snug text-zinc-800 dark:text-zinc-100">
            {payload.prompt || "Choose a quick reply or type below"}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-xs text-zinc-500 underline"
          >
            Hide
          </button>
        </div>
        <ChoiceChips
          choices={payload.choices}
          disabled={disabled}
          onChoice={onChoice}
        />
      </div>
    );
  }

  if (payload.interaction === "scale" && payload.scale) {
    return (
      <ScaleBlock
        scale={payload.scale}
        prompt={payload.prompt}
        disabled={disabled}
        onSubmit={onScaleSubmit}
        onClose={onClose}
        variant="dock"
      />
    );
  }

  return null;
}

function ScaleBlock({
  scale,
  prompt,
  disabled,
  onSubmit,
  onClose,
  variant,
}: {
  scale: ScaleConfig;
  prompt: string;
  disabled?: boolean;
  onSubmit: (s: string) => void;
  onClose: () => void;
  variant: "dock" | "inline";
}) {
  const shell =
    variant === "dock"
      ? "border-t border-black/8 bg-white/95 px-3 py-3 shadow-[0_-4px_12px_rgba(0,0,0,0.06)] dark:border-white/10 dark:bg-zinc-900/95"
      : "";

  return (
    <div className={shell}>
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p
            className={
              variant === "dock"
                ? "text-xs font-semibold uppercase tracking-wide text-[#008069] dark:text-emerald-400"
                : "text-[10px] font-semibold uppercase tracking-wide text-teal-400/90"
            }
          >
            {scale.title}
          </p>
          <p
            className={
              variant === "dock"
                ? "text-[13px] font-medium text-zinc-800 dark:text-zinc-100"
                : "text-[12px] font-medium leading-snug text-[#c5d0d8]"
            }
          >
            {prompt || "Move the slider, then send"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className={
            variant === "dock"
              ? "shrink-0 text-xs text-zinc-500 underline"
              : "shrink-0 text-[11px] text-[#6b7c88] underline"
          }
        >
          Hide
        </button>
      </div>
      <ScaleSlider
        min={scale.min}
        max={scale.max}
        step={scale.step || 1}
        labelLow={scale.label_low}
        labelHigh={scale.label_high}
        disabled={disabled}
        scaleId={scale.id}
        onSubmit={onSubmit}
        variant={variant}
      />
    </div>
  );
}

function ScaleSlider({
  min,
  max,
  step,
  labelLow,
  labelHigh,
  disabled,
  scaleId,
  onSubmit,
  variant,
}: {
  min: number;
  max: number;
  step: number;
  labelLow: string;
  labelHigh: string;
  disabled?: boolean;
  scaleId: string;
  onSubmit: (s: string) => void;
  variant: "dock" | "inline";
}) {
  const mid = Math.round((min + max) / 2);
  const [value, setValue] = useState(mid);

  const accent =
    variant === "inline"
      ? "accent-teal-500"
      : "accent-[#008069]";
  const valueClass =
    variant === "inline"
      ? "text-xl font-semibold tabular-nums text-teal-400"
      : "text-2xl font-semibold tabular-nums text-[#008069] dark:text-emerald-400";
  const sendClass =
    variant === "inline"
      ? "rounded-full bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white active:opacity-90 disabled:opacity-50"
      : "rounded-full bg-[#008069] px-4 py-2 text-sm font-semibold text-white shadow-sm active:opacity-90 disabled:opacity-50 dark:bg-emerald-600";

  return (
    <div className="space-y-2">
      <div
        className={
          variant === "inline"
            ? "flex justify-between text-[10px] text-[#7a8b98]"
            : "flex justify-between text-[11px] text-zinc-500 dark:text-zinc-400"
        }
      >
        <span>{labelLow}</span>
        <span>{labelHigh}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => setValue(Number(e.target.value))}
        className={cn("h-2 w-full cursor-pointer", accent)}
      />
      <div className="flex items-center justify-between gap-2">
        <span className={valueClass}>
          {value}
          <span
            className={
              variant === "inline"
                ? "text-xs font-normal text-[#6b7c88]"
                : "text-sm font-normal text-zinc-500"
            }
          >
            {" "}
            / {max}
          </span>
        </span>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            onSubmit(
              `[${scaleId}] I’d rate it ${value} out of ${max} — ${labelLow} to ${labelHigh}.`,
            )
          }
          className={sendClass}
        >
          Send
        </button>
      </div>
    </div>
  );
}
