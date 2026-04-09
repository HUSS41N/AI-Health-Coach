export type ScaleConfig = {
  id: string;
  min: number;
  max: number;
  step: number;
  label_low: string;
  label_high: string;
  title: string;
};

export type ChoiceItem = { id: string; label: string };

export type InteractivePayload = {
  interaction: "none" | "scale" | "choices";
  prompt: string;
  scale: ScaleConfig | null;
  choices: ChoiceItem[];
};
