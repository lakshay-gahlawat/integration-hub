import { NavLink } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

const LINKS = [
  { to: "/", label: "Overview", end: true },
  { to: "/webhooks", label: "Webhook Events" },
  { to: "/sync-jobs", label: "Sync Jobs" },
  { to: "/activity", label: "Activity" },
];

export function NavBar() {
  const { user, logout } = useAuth();

  return (
    <header className="border-b border-graphite-700 bg-graphite-900/80 backdrop-blur sticky top-0 z-10">
      <div className="mx-auto max-w-6xl px-6">
        <div className="flex h-16 items-center justify-between">
          <div className="flex items-center gap-10">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-signal shadow-[0_0_8px_2px_rgba(91,108,255,0.6)]" />
              <span className="font-display text-lg font-semibold tracking-tight">
                Integration Hub
              </span>
            </div>
            <nav className="hidden gap-6 md:flex">
              {LINKS.map((link) => (
                <NavLink
                  key={link.to}
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    `text-sm font-medium transition-colors ${
                      isActive ? "text-signal-soft" : "text-graphite-400 hover:text-slate-200"
                    }`
                  }
                >
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-graphite-400 sm:inline">{user?.email}</span>
            <button onClick={logout} className="btn-secondary !px-3 !py-1.5 text-xs">
              Sign out
            </button>
          </div>
        </div>
      </div>
      <div className="pulse-line" />
    </header>
  );
}
