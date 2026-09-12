import { useEffect, useState } from "react";
import { ActivityApi } from "../api/resources";
import type { AuditLog } from "../types";
import { formatTimestamp } from "../utils/format";

const ACTION_LABELS: Record<string, string> = {
  "integration.connected": "Integration connected",
  "integration.disconnected": "Integration disconnected",
  "sync.started": "Sync started",
  "sync.completed": "Sync completed",
  "webhook.received": "Webhook received",
  "webhook.processed": "Webhook processed",
};

export function ActivityPage() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [total, setTotal] = useState(0);

  useEffect(() => {
    ActivityApi.list(50, 0).then((res) => {
      setLogs(res.items);
      setTotal(res.total);
    });
  }, []);

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <div>
        <h1 className="font-display text-2xl font-semibold">Activity</h1>
        <p className="mt-1 text-sm text-graphite-400">{total} events recorded for your workspace.</p>
      </div>

      <div className="card divide-y divide-graphite-700">
        {logs.length === 0 && <p className="p-6 text-sm text-graphite-500">No activity recorded yet.</p>}
        {logs.map((log) => (
          <div key={log.id} className="flex items-start justify-between gap-4 p-4 text-sm">
            <div className="min-w-0">
              <p>{ACTION_LABELS[log.action] ?? log.action}</p>
              {log.details && (
                <p className="mt-1 break-all font-mono text-xs text-graphite-500">
                  {JSON.stringify(log.details)}
                </p>
              )}
            </div>
            <span className="shrink-0 text-xs text-graphite-500">{formatTimestamp(log.created_at)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
