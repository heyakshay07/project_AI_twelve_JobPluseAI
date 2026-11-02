import { useEffect, useState } from "react";
import { api, tokens } from "./api.js";
import Auth from "./pages/Auth.jsx";
import Jobs from "./pages/Jobs.jsx";

export default function App() {
  const [user, setUser] = useState(null);
  const [view, setView] = useState("jobs");

  useEffect(() => {
    if (tokens.get()) api("/auth/me").then(setUser).catch(() => tokens.clear());
  }, []);

  const logout = () => { tokens.clear(); setUser(null); };

  return (
    <>
      <header className="border-b border-line bg-ink text-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <button className="text-lg font-semibold" onClick={() => setView("jobs")}>JobPulse AI</button>
          <nav className="flex items-center gap-4 text-sm">
            {user ? (
              <>
                <span className="text-white/80">{user.full_name || user.email}</span>
                <button className="underline" onClick={logout}>Log out</button>
              </>
            ) : (
              <button className="underline" onClick={() => setView("auth")}>Log in / Register</button>
            )}
          </nav>
        </div>
      </header>
      {view === "auth" && !user ? (
        <Auth onDone={() => { api("/auth/me").then(setUser); setView("jobs"); }} />
      ) : (
        <Jobs loggedIn={!!user} />
      )}
    </>
  );
}
