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

/** Chip styles for dark chat surface (no `dark:` — app uses forced dark theme). */
const CHOICE_BTN_CLASS =
  "rounded-full border border-teal-500/35 bg-teal-950/45 px-3 py-1.5 text-left text-[13px] font-medium text-teal-100 transition active:scale-[0.98] disabled:opacity-50";

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
 * Quick replies / scale under the latest assistant bubble only (no dock above the composer).
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
        />
      </div>
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
}: {
  scale: ScaleConfig;
  prompt: string;
  disabled?: boolean;
  onSubmit: (s: string) => void;
  onClose: () => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-start justify-between gap-2">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-wide text-teal-400/90">
            {scale.title}
          </p>
          <p className="text-[12px] font-medium leading-snug text-[#c5d0d8]">
            {prompt || "Move the slider, then send"}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="shrink-0 text-[11px] text-[#6b7c88] underline"
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
        onSubmit={onSubmit}
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
  onSubmit,
}: {
  min: number;
  max: number;
  step: number;
  labelLow: string;
  labelHigh: string;
  disabled?: boolean;
  onSubmit: (s: string) => void;
}) {
  const mid = Math.round((min + max) / 2);
  const [value, setValue] = useState(mid);

  return (
    <div className="space-y-2">
      <div className="flex justify-between text-[10px] text-[#7a8b98]">
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
        className={cn("h-2 w-full cursor-pointer accent-teal-500")}
      />
      <div className="flex items-center justify-between gap-2">
        <span className="text-xl font-semibold tabular-nums text-teal-400">
          {value}
          <span className="text-xs font-normal text-[#6b7c88]"> / {max}</span>
        </span>
        <button
          type="button"
          disabled={disabled}
          onClick={() =>
            onSubmit(
              `I’d rate it ${value} out of ${max} (${labelLow} to ${labelHigh}).`,
            )
          }
          className="rounded-full bg-teal-600 px-3 py-1.5 text-xs font-semibold text-white active:opacity-90 disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
