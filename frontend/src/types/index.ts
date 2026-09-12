export type Provider = "github" | "slack";

export type IntegrationStatus =
  | "connected"
  | "disconnected"
  | "syncing"
  | "failed"
  | "needs_reauthorization";

export type WebhookStatus = "pending" | "processing" | "processed" | "failed" | "duplicate";

export type SyncJobStatus = "pending" | "processing" | "success" | "failed" | "retrying";

export type SyncTrigger = "manual" | "webhook" | "scheduled";

export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export interface Integration {
  id: string;
  provider: Provider;
  status: IntegrationStatus;
  external_account_id: string | null;
  external_account_name: string | null;
  last_synced_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
}

export interface WebhookEvent {
  id: string;
  integration_id: string | null;
  provider: Provider;
  external_event_id: string;
  event_type: string;
  status: WebhookStatus;
  attempt_count: number;
  last_error: string | null;
  received_at: string;
  processed_at: string | null;
}

export interface WebhookEventDetail extends WebhookEvent {
  payload: Record<string, unknown>;
}

export interface SyncJob {
  id: string;
  integration_id: string;
  trigger: SyncTrigger;
  status: SyncJobStatus;
  attempt_count: number;
  result_summary: Record<string, unknown> | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AuditLog {
  id: string;
  integration_id: string | null;
  action: string;
  details: Record<string, unknown> | null;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}
