const STATUS_STYLES: Record<string, string> = {
  connected: "bg-wire-green/10 text-wire-green border-wire-green/30",
  processed: "bg-wire-green/10 text-wire-green border-wire-green/30",
  success: "bg-wire-green/10 text-wire-green border-wire-green/30",

  syncing: "bg-signal/10 text-signal-soft border-signal/30",
  processing: "bg-signal/10 text-signal-soft border-signal/30",
  pending: "bg-graphite-600/30 text-graphite-300 border-graphite-500/40",
  retrying: "bg-wire-amber/10 text-wire-amber border-wire-amber/30",

  disconnected: "bg-graphite-600/30 text-graphite-400 border-graphite-500/40",
  duplicate: "bg-graphite-600/30 text-graphite-400 border-graphite-500/40",

  failed: "bg-wire-red/10 text-wire-red border-wire-red/30",
  needs_reauthorization: "bg-wire-amber/10 text-wire-amber border-wire-amber/30",
};

export function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] ?? "bg-graphite-600/30 text-graphite-300 border-graphite-500/40";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium font-mono ${style}`}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {status.replace(/_/g, " ")}
    </span>
  );
}
