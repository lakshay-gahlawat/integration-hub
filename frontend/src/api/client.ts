const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getStoredTokens() {
  const access = localStorage.getItem("ih_access_token");
  const refresh = localStorage.getItem("ih_refresh_token");
  return { access, refresh };
}

export function setStoredTokens(access: string, refresh: string) {
  localStorage.setItem("ih_access_token", access);
  localStorage.setItem("ih_refresh_token", refresh);
}

export function clearStoredTokens() {
  localStorage.removeItem("ih_access_token");
  localStorage.removeItem("ih_refresh_token");
}

// Refresh tokens rotate server-side: each successful /auth/refresh call
// invalidates the token it was given and returns a new one. If two
// requests 401 at the same moment (e.g. two components fetching in
// parallel), naively calling refresh twice would have the second call
// fail -- the first already consumed and replaced the refresh token. This
// promise cache makes concurrent callers share a single in-flight refresh.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const { refresh } = getStoredTokens();
    if (!refresh) return null;

    const resp = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!resp.ok) return null;

    const data = await resp.json();
    // The response always contains a *new* refresh token (rotation) --
    // both must be persisted, or the next refresh attempt will present
    // the now-revoked old one and fail.
    setStoredTokens(data.access_token, data.refresh_token);
    return data.access_token as string;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  skipAuth?: boolean;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, skipAuth = false } = options;

  const doFetch = async (accessToken: string | null): Promise<Response> => {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (accessToken && !skipAuth) headers.Authorization = `Bearer ${accessToken}`;

    return fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  };

  const { access } = getStoredTokens();
  let resp = await doFetch(access);

  if (resp.status === 401 && !skipAuth) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      resp = await doFetch(newAccess);
    } else {
      clearStoredTokens();
      window.location.href = "/login";
      throw new ApiError(401, "Session expired");
    }
  }

  if (!resp.ok) {
    let message = resp.statusText;
    try {
      const errBody = await resp.json();
      message = errBody.message || errBody.detail || message;
    } catch {
      /* response had no JSON body */
    }
    throw new ApiError(resp.status, message);
  }

  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export { ApiError };
