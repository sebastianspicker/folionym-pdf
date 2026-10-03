import { type MouseEvent, type ReactNode, useEffect, useState } from "react";
import { isDemo } from "../api";
import { BrandMark, MoonIcon, SunIcon } from "../icons";
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
  const nextTheme = theme === "light" ? "dark" : "light";
  return (
    <>
      {isDemo ? (
        <p className="demo-band">
          <strong>Demo.</strong> Simulated documents in your browser. Nothing on your computer is read or renamed.{" "}
          <a href={`${import.meta.env.BASE_URL}tour.html`}>Screenshot tour</a>
        </p>
      ) : null}
      <header className="masthead">
        <a
          aria-label="Folionym, back to Source"
          className="brand"
          href={import.meta.env.BASE_URL}
          onClick={navigateHome}
        >
          <BrandMark className="brand-mark" size={22} />
          <span className="brand-word">Folionym</span>
        </a>

        <Stepper active={active} />

        {source ? (
          <span className="visually-hidden">
            Scope: {compactPath(source)}
            {sourceMeta ? `, ${sourceMeta}` : ""}
          </span>
        ) : null}

        <div className="header-actions">
          <PrivacyChip external={external} />
          <button
            aria-label={`Switch to ${nextTheme} theme`}
            className="icon-button theme-toggle"
            onClick={onThemeChange}
            title={`Switch to ${nextTheme} theme`}
            type="button"
          >
            {theme === "light" ? <MoonIcon /> : <SunIcon />}
          </button>
        </div>
      </header>
    </>
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
  // Preview fills the register's three columns (index · ledger · evidence).
  // Source and Apply use a single content surface under the shared header.
  const bodyClass = active === 2 ? "body-grid body-grid--preview" : "body-grid body-grid--simple";

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
