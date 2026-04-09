export type ChatContact = {
  id: string;
  name: string;
  subtitle: string;
  time: string;
  /** Only Reeba is connected to the AI backend */
  messagable: boolean;
  avatar: string;
};

export const CHAT_CONTACTS: ChatContact[] = [
  {
    id: "reeba",
    name: "Health Coach Reeba",
    subtitle: "AI health coach · online",
    time: "",
    messagable: true,
    avatar: "💚",
  },
  {
    id: "clinic-front",
    name: "Clinic front desk",
    subtitle: "Demo contact — messaging disabled",
    time: "Mon",
    messagable: false,
    avatar: "🏥",
  },
  {
    id: "nutrition",
    name: "Nutrition desk",
    subtitle: "Demo contact — messaging disabled",
    time: "Tue",
    messagable: false,
    avatar: "🥗",
  },
  {
    id: "physio",
    name: "Physio follow-up",
    subtitle: "Demo contact — messaging disabled",
    time: "Wed",
    messagable: false,
    avatar: "🧘",
  },
  {
    id: "pharmacy",
    name: "Pharmacy (refill)",
    subtitle: "Demo contact — messaging disabled",
    time: "9:12 AM",
    messagable: false,
    avatar: "💊",
  },
];
