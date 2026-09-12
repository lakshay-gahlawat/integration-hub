import { apiRequest } from "./client";
import type {
  AuditLog,
  Integration,
  Page,
  Provider,
  SyncJob,
  WebhookEvent,
  WebhookEventDetail,
} from "../types";

export const IntegrationsApi = {
  list: () => apiRequest<Integration[]>("/integrations"),
  get: (id: string) => apiRequest<Integration>(`/integrations/${id}`),
  connect: (provider: Provider, accessToken: string) =>
    apiRequest<Integration>("/integrations", {
      method: "POST",
      body: { provider, access_token: accessToken },
    }),
  disconnect: (id: string) => apiRequest<void>(`/integrations/${id}`, { method: "DELETE" }),
  sync: (id: string) =>
    apiRequest<{ sync_job_id: string; status: string }>(`/integrations/${id}/sync`, {
      method: "POST",
    }),
  webhooks: (id: string) => apiRequest<WebhookEvent[]>(`/integrations/${id}/webhooks`),
  syncJobs: (id: string) => apiRequest<SyncJob[]>(`/integrations/${id}/sync-jobs`),
};

export const WebhooksApi = {
  list: (limit = 20, offset = 0) =>
    apiRequest<Page<WebhookEvent>>(`/webhooks?limit=${limit}&offset=${offset}`),
  get: (id: string) => apiRequest<WebhookEventDetail>(`/webhooks/${id}`),
};

export const SyncJobsApi = {
  list: (limit = 20, offset = 0) =>
    apiRequest<Page<SyncJob>>(`/sync-jobs?limit=${limit}&offset=${offset}`),
  get: (id: string) => apiRequest<SyncJob>(`/sync-jobs/${id}`),
};

export const ActivityApi = {
  list: (limit = 50, offset = 0) =>
    apiRequest<Page<AuditLog>>(`/activity?limit=${limit}&offset=${offset}`),
};
