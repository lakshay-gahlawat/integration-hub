import { useEffect, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { IntegrationsApi, SyncJobsApi, WebhooksApi } from "../api/resources";
import type { Integration, SyncJob, WebhookEvent } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { ProviderTag } from "../components/ProviderTag";
import { ConnectIntegrationForm } from "../components/ConnectIntegrationForm";
import { timeAgo } from "../utils/format";
import { ApiError } from "../api/client";

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div className="card p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-graphite-500">{label}</p>
      <p className={`mt-2 font-display text-3xl font-semibold ${accent ?? "text-slate-100"}`}>{value}</p>
    </div>
  );
}

export function DashboardPage() {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [recentWebhooks, setRecentWebhooks] = useState<WebhookEvent[]>([]);
  const [recentSyncJobs, setRecentSyncJobs] = useState<SyncJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncingIds, setSyncingIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [integrationsRes, webhooksRes, syncJobsRes] = await Promise.all([
      IntegrationsApi.list(),
      WebhooksApi.list(8, 0),
      SyncJobsApi.list(8, 0),
    ]);
    setIntegrations(integrationsRes);
    setRecentWebhooks(webhooksRes.items);
    setRecentSyncJobs(syncJobsRes.items);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const activeCount = integrations.filter((i) => i.status === "connected" || i.status === "syncing").length;
  const failedCount = integrations.filter(
    (i) => i.status === "failed" || i.status === "needs_reauthorization"
  ).length;
  const recentErrors = recentSyncJobs.filter((j) => j.status === "failed");

  const handleSync = async (integration: Integration) => {
    setSyncingIds((prev) => new Set(prev).add(integration.id));
    setToast(null);
    try {
      await IntegrationsApi.sync(integration.id);
      setToast(`Sync started for ${integration.provider}. Refresh in a few seconds to see results.`);
      setTimeout(load, 2500);
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : "Could not start sync");
    } finally {
      setSyncingIds((prev) => {
        const next = new Set(prev);
        next.delete(integration.id);
        return next;
      });
    }
  };

  const handleDisconnect = async (integration: Integration) => {
    await IntegrationsApi.disconnect(integration.id);
    load();
  };

  if (loading) {
    return <div className="p-10 text-center text-graphite-500">Loading workspace…</div>;
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-8">
      <div>
        <h1 className="font-display text-2xl font-semibold">Overview</h1>
        <p className="mt-1 text-sm text-graphite-400">
          Connected systems, recent events, and sync health at a glance.
        </p>
      </div>

      {toast && (
        <div className="rounded-lg border border-signal/30 bg-signal/10 px-4 py-2.5 text-sm text-signal-soft">
          {toast}
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total integrations" value={integrations.length} />
        <StatCard label="Active" value={activeCount} accent="text-wire-green" />
        <StatCard label="Failed / needs auth" value={failedCount} accent={failedCount ? "text-wire-red" : undefined} />
        <StatCard label="Recent sync errors" value={recentErrors.length} accent={recentErrors.length ? "text-wire-amber" : undefined} />
      </div>

      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-display text-lg font-semibold">Integrations</h2>
          <ConnectIntegrationForm onConnected={load} />
        </div>

        {integrations.length === 0 ? (
          <div className="card p-8 text-center text-sm text-graphite-500">
            No integrations connected yet. Connect GitHub or Slack to see live sync activity here.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2">
            {integrations.map((integration) => (
              <div key={integration.id} className="card flex flex-col gap-4 p-5">
                <div className="flex items-start justify-between">
                  <Link to={`/integrations/${integration.id}`} className="hover:underline">
                    <ProviderTag provider={integration.provider} />
                  </Link>
                  <StatusBadge status={integration.status} />
                </div>
                <div className="text-xs text-graphite-500">
                  <p>Account: {integration.external_account_name ?? "—"}</p>
                  <p>Last synced: {timeAgo(integration.last_synced_at)}</p>
                </div>
                {integration.last_error && (
                  <p className="rounded-md bg-wire-red/10 px-2.5 py-1.5 text-xs text-wire-red">
                    {integration.last_error}
                  </p>
                )}
                <div className="mt-auto flex gap-2">
                  <button
                    className="btn-secondary flex-1 justify-center !py-1.5 text-xs"
                    disabled={syncingIds.has(integration.id) || integration.status === "disconnected"}
                    onClick={() => handleSync(integration)}
                  >
                    {syncingIds.has(integration.id) ? "Starting…" : "Sync now"}
                  </button>
                  <button className="btn-danger" onClick={() => handleDisconnect(integration)}>
                    Disconnect
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Recent webhook events</h2>
          <div className="card divide-y divide-graphite-700">
            {recentWebhooks.length === 0 && (
              <p className="p-5 text-sm text-graphite-500">No webhook events received yet.</p>
            )}
            {recentWebhooks.map((event) => (
              <Link
                key={event.id}
                to={`/webhooks/${event.id}`}
                className="flex items-center justify-between gap-3 p-4 text-sm hover:bg-graphite-800/60"
              >
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs text-graphite-400">{event.external_event_id}</p>
                  <p className="truncate">{event.event_type}</p>
                </div>
                <StatusBadge status={event.status} />
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Recent sync jobs</h2>
          <div className="card divide-y divide-graphite-700">
            {recentSyncJobs.length === 0 && (
              <p className="p-5 text-sm text-graphite-500">No sync jobs run yet.</p>
            )}
            {recentSyncJobs.map((job) => (
              <div key={job.id} className="flex items-center justify-between gap-3 p-4 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-mono text-xs text-graphite-400">{job.id.slice(0, 8)}</p>
                  <p className="truncate capitalize">{job.trigger} trigger</p>
                </div>
                <StatusBadge status={job.status} />
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
