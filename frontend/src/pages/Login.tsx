import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not sign in");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 h-2 w-2 rounded-full bg-signal shadow-[0_0_10px_3px_rgba(91,108,255,0.6)]" />
          <h1 className="font-display text-2xl font-semibold">Integration Hub</h1>
          <p className="mt-1 text-sm text-graphite-400">Sign in to your workspace</p>
        </div>
        <form onSubmit={onSubmit} className="card space-y-4 p-6">
          {error && (
            <div className="rounded-lg border border-wire-red/30 bg-wire-red/10 px-3 py-2 text-sm text-wire-red">
              {error}
            </div>
          )}
          <div>
            <label className="label">Email</label>
            <input
              className="input"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
            />
          </div>
          <div>
            <label className="label">Password</label>
            <input
              className="input"
              type="password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
            />
          </div>
          <button type="submit" disabled={submitting} className="btn-primary w-full justify-center">
            {submitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-graphite-400">
          New here?{" "}
          <Link to="/register" className="text-signal-soft hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
