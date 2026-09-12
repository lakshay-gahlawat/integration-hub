import type { Provider } from "../types";

const PROVIDER_META: Record<Provider, { label: string; glyph: string; color: string }> = {
  github: { label: "GitHub", glyph: "\u25C8", color: "text-slate-200" },
  slack: { label: "Slack", glyph: "\u2726", color: "text-wire-amber" },
};

export function ProviderTag({ provider }: { provider: Provider }) {
  const meta = PROVIDER_META[provider];
  return (
    <span className="inline-flex items-center gap-2 font-display text-sm font-medium">
      <span className={`text-base ${meta.color}`}>{meta.glyph}</span>
      {meta.label}
    </span>
  );
}
