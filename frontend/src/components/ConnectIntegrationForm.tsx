import { useState, type FormEvent } from "react";
import type { Provider } from "../types";
import { IntegrationsApi } from "../api/resources";
import { ApiError } from "../api/client";

const PROVIDER_HELP: Record<Provider, string> = {
  github:
    "Paste a GitHub personal access token (repo, gist, read:user scopes). Settings → Developer settings → Personal access tokens.",
  slack:
    "Paste a Slack bot token (xoxb-...) with channels:read and chat:write scopes, from your Slack app's OAuth & Permissions page.",
};

export function ConnectIntegrationForm({ onConnected }: { onConnected: () => void }) {
  const [open, setOpen] = useState(false);
  const [provider, setProvider] = useState<Provider>("github");
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await IntegrationsApi.connect(provider, token);
      setToken("");
      setOpen(false);
      onConnected();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not connect integration");
    } finally {
      setSubmitting(false);
    }
  };

  if (!open) {
    return (
      <button className="btn-primary" onClick={() => setOpen(true)}>
        + Connect integration
      </button>
    );
  }

  return (
    <form onSubmit={onSubmit} className="card w-full max-w-md space-y-4 p-5">
      <div className="flex items-center justify-between">
        <h3 className="font-display text-sm font-semibold">Connect a provider</h3>
        <button type="button" onClick={() => setOpen(false)} className="text-graphite-500 hover:text-slate-200">
          ✕
        </button>
      </div>
      {error && (
        <div className="rounded-lg border border-wire-red/30 bg-wire-red/10 px-3 py-2 text-sm text-wire-red">
          {error}
        </div>
      )}
      <div>
        <label className="label">Provider</label>
        <select
          className="input"
          value={provider}
          onChange={(e) => setProvider(e.target.value as Provider)}
        >
          <option value="github">GitHub</option>
          <option value="slack">Slack</option>
        </select>
      </div>
      <div>
        <label className="label">Access token</label>
        <input
          className="input font-mono"
          required
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder={provider === "github" ? "ghp_..." : "xoxb-..."}
        />
        <p className="mt-1.5 text-xs text-graphite-500">{PROVIDER_HELP[provider]}</p>
      </div>
      <button type="submit" disabled={submitting} className="btn-primary w-full justify-center">
        {submitting ? "Connecting…" : "Connect"}
      </button>
    </form>
  );
}
