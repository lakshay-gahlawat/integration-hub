import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { IntegrationsApi } from "../api/resources";
import type { Integration, SyncJob, WebhookEvent } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { ProviderTag } from "../components/ProviderTag";
import { formatTimestamp, timeAgo } from "../utils/format";
import { ApiError } from "../api/client";

export function IntegrationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [integration, setIntegration] = useState<Integration | null>(null);
  const [webhooks, setWebhooks] = useState<WebhookEvent[]>([]);
  const [syncJobs, setSyncJobs] = useState<SyncJob[]>([]);
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    const [integrationRes, webhooksRes, syncJobsRes] = await Promise.all([
      IntegrationsApi.get(id),
      IntegrationsApi.webhooks(id),
      IntegrationsApi.syncJobs(id),
    ]);
    setIntegration(integrationRes);
    setWebhooks(webhooksRes);
    setSyncJobs(syncJobsRes);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  if (!integration) {
    return <div className="p-10 text-center text-graphite-500">Loading integration…</div>;
  }

  const handleSync = async () => {
    setSyncing(true);
    setToast(null);
    try {
      await IntegrationsApi.sync(integration.id);
      setToast("Sync started. This page will refresh automatically.");
      setTimeout(load, 2500);
    } catch (err) {
      setToast(err instanceof ApiError ? err.message : "Could not start sync");
    } finally {
      setSyncing(false);
    }
  };

  const handleDisconnect = async () => {
    await IntegrationsApi.disconnect(integration.id);
    navigate("/");
  };

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-8">
      <Link to="/" className="text-sm text-graphite-500 hover:text-slate-200">
        ← Back to overview
      </Link>

      <div className="card flex flex-col gap-4 p-6 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <ProviderTag provider={integration.provider} />
          <p className="mt-1 text-sm text-graphite-500">
            {integration.external_account_name ?? "No account name recorded"}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <StatusBadge status={integration.status} />
          <button
            className="btn-secondary text-xs"
            disabled={syncing || integration.status === "disconnected"}
            onClick={handleSync}
          >
            {syncing ? "Starting…" : "Sync now"}
          </button>
          <button className="btn-danger" onClick={handleDisconnect}>
            Disconnect
          </button>
        </div>
      </div>

      {toast && (
        <div className="rounded-lg border border-signal/30 bg-signal/10 px-4 py-2.5 text-sm text-signal-soft">
          {toast}
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="card p-4">
          <p className="label">Last synced</p>
          <p className="text-sm">{timeAgo(integration.last_synced_at)}</p>
        </div>
        <div className="card p-4">
          <p className="label">Connected since</p>
          <p className="text-sm">{formatTimestamp(integration.created_at)}</p>
        </div>
        <div className="card p-4">
          <p className="label">External account ID</p>
          <p className="truncate font-mono text-sm">{integration.external_account_id ?? "—"}</p>
        </div>
      </div>

      {integration.last_error && (
        <div className="rounded-lg border border-wire-red/30 bg-wire-red/10 px-4 py-3 text-sm text-wire-red">
          <p className="font-medium">Last error</p>
          <p className="mt-1 font-mono text-xs">{integration.last_error}</p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Recent events</h2>
          <div className="card divide-y divide-graphite-700">
            {webhooks.length === 0 && <p className="p-5 text-sm text-graphite-500">No events yet.</p>}
            {webhooks.map((event) => (
              <Link
                key={event.id}
                to={`/webhooks/${event.id}`}
                className="flex items-center justify-between gap-3 p-4 text-sm hover:bg-graphite-800/60"
              >
                <div className="min-w-0">
                  <p className="truncate">{event.event_type}</p>
                  <p className="text-xs text-graphite-500">{timeAgo(event.received_at)}</p>
                </div>
                <StatusBadge status={event.status} />
              </Link>
            ))}
          </div>
        </section>

        <section className="space-y-3">
          <h2 className="font-display text-lg font-semibold">Activity history</h2>
          <div className="card divide-y divide-graphite-700">
            {syncJobs.length === 0 && <p className="p-5 text-sm text-graphite-500">No sync jobs yet.</p>}
            {syncJobs.map((job) => (
              <div key={job.id} className="p-4 text-sm">
                <div className="flex items-center justify-between">
                  <span className="capitalize text-graphite-300">{job.trigger} sync</span>
                  <StatusBadge status={job.status} />
                </div>
                <p className="mt-1 text-xs text-graphite-500">{formatTimestamp(job.created_at)}</p>
                {job.error_message && (
                  <p className="mt-1.5 truncate font-mono text-xs text-wire-red">{job.error_message}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
