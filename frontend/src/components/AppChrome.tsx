import { type MouseEvent, type ReactNode, useEffect, useState } from "react";
import { isDemo } from "../api";
import { navigate } from "../lib/routing";
import { compactPath } from "./format";
import { PrivacyChip } from "./PrivacyChip";
import { Stepper } from "./Stepper";

type AppChromeProps = {
  active: 1 | 2 | 3;
  source?: string;
  sourceMeta?: string;
  external: boolean;
  children: ReactNode;
  footer?: ReactNode;
  overlays?: ReactNode;
};

function navigateHome(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  navigate("source");
}

type Theme = "light" | "dark";

function preferredTheme(): Theme {
  try {
    const saved = localStorage.getItem("folionym.theme");
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    // Storage can be unavailable in private browser contexts.
  }
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

function AppHeader({
  active,
  source,
  sourceMeta,
  external,
  theme,
  onThemeChange,
}: Pick<AppChromeProps, "active" | "source" | "sourceMeta" | "external"> & {
  theme: Theme;
  onThemeChange: () => void;
}) {
  return (
    <header className="instrument-bar">
      <div className="brand-block">
        <a
          aria-label="Folionym"
          className="brand"
          href={import.meta.env.BASE_URL}
          onClick={navigateHome}
        >
          <span aria-hidden="true" className="brand-mark">
            <svg fill="none" viewBox="0 0 24 24">
              <rect
                height="18"
                rx="1.5"
                stroke="currentColor"
                strokeWidth="1.6"
                width="16"
                x="4"
                y="3"
              />
              <path
                d="M8 8h8M8 12h8M8 16h5"
                stroke="currentColor"
                strokeLinecap="round"
                strokeWidth="1.6"
              />
            </svg>
          </span>
          <span className="brand-word">Folionym</span>
        </a>
        <span className="brand-meta">
          {isDemo ? "Interactive mock demo" : "Local rename instrument"}
        </span>
      </div>

      <Stepper active={active} />

      {source ? (
        <span className="visually-hidden">
          Scope: {compactPath(source)}
          {sourceMeta ? `, ${sourceMeta}` : ""}
        </span>
      ) : null}

      <div className="header-actions">
        {isDemo ? (
          <a className="demo-tour-link" href={`${import.meta.env.BASE_URL}tour.html`}>
            Screenshot tour
          </a>
        ) : null}
        <button
          aria-label={`Switch to ${theme === "light" ? "dark" : "light"} theme`}
          className="theme-toggle"
          onClick={onThemeChange}
          type="button"
        >
          <span aria-hidden="true">{theme === "light" ? "◐" : "☼"}</span>
          <span>{theme === "light" ? "Dark" : "Light"}</span>
        </button>
        <PrivacyChip external={external} />
      </div>
    </header>
  );
}

export function AppChrome({
  active,
  source,
  sourceMeta,
  external,
  children,
  footer,
  overlays,
}: AppChromeProps) {
  const [theme, setTheme] = useState<Theme>(preferredTheme);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  const toggleTheme = () => {
    setTheme((current) => {
      const next = current === "light" ? "dark" : "light";
      try {
        localStorage.setItem("folionym.theme", next);
      } catch {
        // A session-only choice still works when persistence is unavailable.
      }
      return next;
    });
  };
  // Preview fills Reading Room columns (filter rail · ledger · inspector).
  // Source and Apply use a single content surface under the shared header.
  const bodyClass =
    active === 2
      ? "body-grid body-grid--preview"
      : "body-grid body-grid--simple";

  return (
    <div className="app" data-theme={theme}>
      <AppHeader
        active={active}
        external={external}
        onThemeChange={toggleTheme}
        source={source}
        sourceMeta={sourceMeta}
        theme={theme}
      />

      <div className={bodyClass}>
        {active === 2 ? (
          children
        ) : (
          <div className="app-content">{children}</div>
        )}
      </div>

      {footer ? <footer className="consequence">{footer}</footer> : null}
      {overlays}
    </div>
  );
}
