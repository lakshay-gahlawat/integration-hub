import { useEffect, useState } from "react";
import { SyncJobsApi } from "../api/resources";
import type { SyncJob } from "../types";
import { StatusBadge } from "../components/StatusBadge";
import { formatTimestamp } from "../utils/format";

export function SyncJobsPage() {
  const [jobs, setJobs] = useState<SyncJob[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  useEffect(() => {
    SyncJobsApi.list(limit, offset).then((res) => {
      setJobs(res.items);
      setTotal(res.total);
    });
  }, [offset]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-6 py-8">
      <div>
        <h1 className="font-display text-2xl font-semibold">Sync Jobs</h1>
        <p className="mt-1 text-sm text-graphite-400">
          Background synchronization runs, triggered manually, by webhook, or on a schedule.
        </p>
      </div>

      <div className="card divide-y divide-graphite-700">
        {jobs.length === 0 && <p className="p-6 text-sm text-graphite-500">No sync jobs yet.</p>}
        {jobs.map((job) => (
          <div key={job.id} className="flex flex-wrap items-center justify-between gap-3 p-4 text-sm">
            <div>
              <p className="font-mono text-xs text-graphite-500">{job.id}</p>
              <p className="mt-0.5 capitalize">{job.trigger} trigger · attempt {job.attempt_count}</p>
            </div>
            <div className="flex items-center gap-4">
              <span className="text-xs text-graphite-500">{formatTimestamp(job.created_at)}</span>
              <StatusBadge status={job.status} />
            </div>
            {job.error_message && (
              <p className="w-full font-mono text-xs text-wire-red">{job.error_message}</p>
            )}
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm text-graphite-500">
        <span>
          Showing {jobs.length === 0 ? 0 : offset + 1}–{offset + jobs.length} of {total}
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
