export type TaxThemeCode = "PBB-P2" | "PBJT" | "BPHTB" | "REKLAME" | "PAT";

export type CapabilityModeCode = "konsultasi" | "pasal_hukum" | "perumusan_hukum";

export interface StarterPrompt {
  title: string;
  desc: string;
  prompt: string;
}

export interface TaxThemeConfig {
  code: TaxThemeCode;
  shortLabel: string;
  fullName: string;
  badgeDesc: string;
  dotColor: string;
  placeholder: string;
  starters: StarterPrompt[];
  legalStarters: StarterPrompt[];
  draftingStarters: StarterPrompt[];
}

export interface CapabilityModeConfig {
  code: CapabilityModeCode;
  shortLabel: string;
  fullLabel: string;
  engineBadge: string;
  description: string;
  placeholderPrefix: string;
}

export const CAPABILITY_MODES: CapabilityModeConfig[] = [
  {
    code: "konsultasi",
    shortLabel: "Tarif & Data Pajak",
    fullLabel: "Konsultasi Tarif, Rumus & Objek Pajak",
    engineBadge: "Model lokal",
    description: "Bahas informasi pajak berdasarkan dokumen yang tersedia.",
    placeholderPrefix: "Tanyakan tarif, rumus, atau cek NOP/NPWPD",
  },
  {
    code: "pasal_hukum",
    shortLabel: "Pasal & Dasar Hukum",
    fullLabel: "Telusur Pasal, Ayat & Dasar Hukum",
    engineBadge: "Model lokal",
    description: "Telusuri bunyi pasal, ayat, hierarki dasar hukum, dan norma regulasi pajak daerah.",
    placeholderPrefix: "Telusuri bunyi pasal, ayat, atau dasar hukum",
  },
  {
    code: "perumusan_hukum",
    shortLabel: "Perumusan Hukum",
    fullLabel: "Perumusan Dasar Hukum Baru (Legal Drafting)",
    engineBadge: "Model lokal",
    description: "Susun draf pasal baru, konsiderans Menimbang/Mengingat, dan matriks harmonisasi aturan.",
    placeholderPrefix: "Rumuskan draf pasal, konsiderans, atau kajian aturan",
  },
];

export const TAX_THEMES: TaxThemeConfig[] = [
  {
    code: "PBB-P2",
    shortLabel: "PBB-P2",
    fullName: "Pajak Bumi dan Bangunan (PBB-P2)",
    badgeDesc: "SPPT, NOP, NJOP, Pasal & Perumusan PBB-P2 DKI Jakarta",
    dotColor: "#10b981",
    placeholder: "PBB-P2 DKI Jakarta (misal: NOP, pasal NJOPTKP, atau draf insentif)...",
    starters: [],
    legalStarters: [],
    draftingStarters: [],
  },
  {
    code: "PBJT",
    shortLabel: "PBJT",
    fullName: "PBJT (Restoran, Hotel, Parkir, Hiburan)",
    badgeDesc: "Makanan/Minuman, Hotel, Parkir, Hiburan, Pasal & Perumusan PBJT",
    dotColor: "#3b82f6",
    placeholder: "PBJT DKI Jakarta (Restoran, Hotel, Parkir, Pasal, atau Perumusan)...",
    starters: [],
    legalStarters: [],
    draftingStarters: [],
  },
  {
    code: "BPHTB",
    shortLabel: "BPHTB",
    fullName: "Bea Perolehan Hak atas Tanah & Bangunan (BPHTB)",
    badgeDesc: "SSPD, AJB, Waris/Hibah, Pasal & Perumusan BPHTB DKI Jakarta",
    dotColor: "#8b5cf6",
    placeholder: "BPHTB DKI Jakarta (NPOPTKP, AJB, Waris, Pasal, atau Perumusan)...",
    starters: [],
    legalStarters: [],
    draftingStarters: [],
  },
  {
    code: "REKLAME",
    shortLabel: "Reklame",
    fullName: "Pajak Reklame DKI Jakarta",
    badgeDesc: "Videotron, Billboard, NSR, Pasal & Perumusan Pajak Reklame",
    dotColor: "#f59e0b",
    placeholder: "Pajak Reklame DKI (Videotron, NSR, Kawasan Protokol, atau Pasal)...",
    starters: [],
    legalStarters: [],
    draftingStarters: [],
  },
  {
    code: "PAT",
    shortLabel: "Air Tanah",
    fullName: "Pajak Air Tanah (PAT) DKI Jakarta",
    badgeDesc: "Sumur Bor, Volume m³, NPAT, Pasal & Perumusan PAT DKI",
    dotColor: "#06b6d4",
    placeholder: "Tanyakan isi dokumen terkait Pajak Air Tanah...",
    starters: [],
    legalStarters: [],
    draftingStarters: [],
  },
];

export function getStartersForThemeAndMode(
  theme: TaxThemeConfig,
  mode: CapabilityModeCode
): StarterPrompt[] {
  if (mode === "pasal_hukum") {
    return theme.legalStarters;
  }
  if (mode === "perumusan_hukum") {
    return theme.draftingStarters;
  }
  return theme.starters;
}
