import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { WebhooksApi } from "../api/resources";
import type { WebhookEventDetail } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { ProviderTag } from "../components/ProviderTag";
import { formatTimestamp } from "../utils/format";

export function WebhookDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [event, setEvent] = useState<WebhookEventDetail | null>(null);

  useEffect(() => {
    if (id) WebhooksApi.get(id).then(setEvent);
  }, [id]);

  if (!event) {
    return <div className="p-10 text-center text-graphite-500">Loading event…</div>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 px-6 py-8">
      <Link to="/webhooks" className="text-sm text-graphite-500 hover:text-slate-200">
        ← Back to webhook events
      </Link>

      <div className="card space-y-4 p-6">
        <div className="flex items-start justify-between">
          <div>
            <ProviderTag provider={event.provider} />
            <h1 className="mt-1 font-display text-xl font-semibold">{event.event_type}</h1>
          </div>
          <StatusBadge status={event.status} />
        </div>

        <dl className="grid grid-cols-2 gap-4 border-t border-graphite-700 pt-4 text-sm sm:grid-cols-4">
          <div>
            <dt className="label">Event ID</dt>
            <dd className="font-mono text-xs">{event.id}</dd>
          </div>
          <div>
            <dt className="label">External event ID</dt>
            <dd className="font-mono text-xs">{event.external_event_id}</dd>
          </div>
          <div>
            <dt className="label">Received</dt>
            <dd>{formatTimestamp(event.received_at)}</dd>
          </div>
          <div>
            <dt className="label">Processed</dt>
            <dd>{formatTimestamp(event.processed_at)}</dd>
          </div>
          <div>
            <dt className="label">Attempts</dt>
            <dd>{event.attempt_count}</dd>
          </div>
          {event.integration_id && (
            <div>
              <dt className="label">Integration</dt>
              <dd>
                <Link to={`/integrations/${event.integration_id}`} className="text-signal-soft hover:underline">
                  View →
                </Link>
              </dd>
            </div>
          )}
        </dl>

        {event.last_error && (
          <div className="rounded-lg border border-wire-red/30 bg-wire-red/10 px-4 py-3 text-sm text-wire-red">
            <p className="font-medium">Processing error</p>
            <p className="mt-1 font-mono text-xs">{event.last_error}</p>
          </div>
        )}

        <div>
          <p className="label mb-2">Raw payload</p>
          <pre className="max-h-96 overflow-auto rounded-lg bg-graphite-950 p-4 font-mono text-xs text-graphite-300">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
