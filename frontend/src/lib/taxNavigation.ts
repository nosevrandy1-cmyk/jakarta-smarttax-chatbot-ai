import type { TaxThemeCode } from "@/config/smarttaxConfig";

// Only validated model metadata can supply a navigation destination.
export function suggestedTaxTargets(value: unknown, current: TaxThemeCode): TaxThemeCode[] {
  const allowed: TaxThemeCode[] = ["PBB-P2", "PBJT", "BPHTB", "REKLAME", "PAT"];
  const values = Array.isArray(value) ? value : [value];
  return [...new Set(values.filter((item): item is TaxThemeCode =>
    typeof item === "string" && item !== current && allowed.includes(item as TaxThemeCode)))].slice(0, 2);
}

export function precedingQuestion(messages: readonly {role: string; content: string}[], index: number): string {
  for (let i = index - 1; i >= 0; i--) {
    if (messages[i].role === "user") return messages[i].content;
  }
  return "";
}
