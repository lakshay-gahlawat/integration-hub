import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { WebhooksApi } from "../api/resources";
import type { WebhookEvent } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { ProviderTag } from "../components/ProviderTag";
import { formatTimestamp } from "../utils/format";

export function WebhooksPage() {
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  useEffect(() => {
    WebhooksApi.list(limit, offset).then((res) => {
      setEvents(res.items);
      setTotal(res.total);
    });
  }, [offset]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <div>
        <h1 className="font-display text-2xl font-semibold">Webhook Events</h1>
        <p className="mt-1 text-sm text-graphite-400">
          Every delivery received, deduplicated by provider + event ID.
        </p>
      </div>

      <div className="card divide-y divide-graphite-700">
        {events.length === 0 && <p className="p-6 text-sm text-graphite-500">No events received yet.</p>}
        {events.map((event) => (
          <Link
            key={event.id}
            to={`/webhooks/${event.id}`}
            className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm hover:bg-graphite-800/60"
          >
            <div className="flex items-center gap-4">
              <ProviderTag provider={event.provider} />
              <div>
                <p>{event.event_type}</p>
                <p className="font-mono text-xs text-graphite-500">{event.external_event_id}</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs text-graphite-500">{formatTimestamp(event.received_at)}</span>
              <span className="text-xs text-graphite-500">attempt {event.attempt_count}</span>
              <StatusBadge status={event.status} />
            </div>
          </Link>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm text-graphite-500">
        <span>
          Showing {events.length === 0 ? 0 : offset + 1}–{offset + events.length} of {total}
        </span>
        <div className="flex gap-2">
          <button
            className="btn-secondary !py-1.5 text-xs"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - limit))}
          >
            Previous
          </button>
          <button
            className="btn-secondary !py-1.5 text-xs"
            disabled={offset + limit >= total}
            onClick={() => setOffset(offset + limit)}
          >
            Next
          </button>
        </div>
      </div>
    </div>
  );
}
