import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ApiError } from "../api/client";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await register(email, password, fullName);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create account");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 h-2 w-2 rounded-full bg-signal shadow-[0_0_10px_3px_rgba(91,108,255,0.6)]" />
          <h1 className="font-display text-2xl font-semibold">Create your workspace</h1>
          <p className="mt-1 text-sm text-graphite-400">Start connecting external services</p>
        </div>
        <form onSubmit={onSubmit} className="card space-y-4 p-6">
          {error && (
            <div className="rounded-lg border border-wire-red/30 bg-wire-red/10 px-3 py-2 text-sm text-wire-red">
              {error}
            </div>
          )}
          <div>
            <label className="label">Full name</label>
            <input
              className="input"
              required
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Ada Lovelace"
            />
          </div>
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
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          <button type="submit" disabled={submitting} className="btn-primary w-full justify-center">
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-graphite-400">
          Already have an account?{" "}
          <Link to="/login" className="text-signal-soft hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
