import "./tour.css";

const root = document.documentElement;
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

// Follow the system theme for the whole page. The inline script in tour.html
// sets the first value before paint; this keeps it in sync afterwards.
function followSystemTheme(): void {
  const dark = window.matchMedia("(prefers-color-scheme: dark)");
  const apply = (): void => {
    root.dataset.theme = dark.matches ? "dark" : "light";
  };
  apply();
  dark.addEventListener("change", apply);
}

// Each rename slip sweeps its highlights once when it enters the viewport.
// Without motion, or before this runs, the highlights render statically.
function setUpSlipSweep(): void {
  const list = document.querySelector<HTMLElement>("[data-slips]");
  if (!list || reducedMotion.matches || !("IntersectionObserver" in window)) return;
  list.classList.add("is-armed");
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-swept");
        observer.unobserve(entry.target);
      }
    },
    { threshold: 0.6 },
  );
  list.querySelectorAll<HTMLElement>(".slip").forEach((slip) => observer.observe(slip));
}

// Scroll reveal fallback for browsers without scroll-driven animations.
function setUpRevealFallback(): void {
  if (reducedMotion.matches || !("IntersectionObserver" in window)) return;
  if (typeof CSS !== "undefined" && CSS.supports("animation-timeline: view()")) return;
  const targets = document.querySelectorAll<HTMLElement>(".reveal");
  if (!targets.length) return;
  root.classList.add("reveal-fallback");
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -10% 0px" },
  );
  targets.forEach((target) => observer.observe(target));
}

// WAI-ARIA tabs with automatic activation and a roving tabindex.
function setUpTabs(): void {
  const tablist = document.querySelector<HTMLElement>('[role="tablist"]');
  if (!tablist) return;
  const tabs = Array.from(tablist.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
  // Inactive panels are hidden only once the tabs work; until then all show.
  const container = tablist.closest<HTMLElement>("[data-tabs]");

  const select = (next: HTMLButtonElement, focus: boolean): void => {
    for (const tab of tabs) {
      const selected = tab === next;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      const panelId = tab.getAttribute("aria-controls");
      const panel = panelId ? document.getElementById(panelId) : null;
      panel?.classList.toggle("is-active", selected);
    }
    if (focus) next.focus();
  };

  tablist.addEventListener("click", (event) => {
    const tab = (event.target as Element).closest<HTMLButtonElement>('[role="tab"]');
    if (tab) select(tab, false);
  });

  tablist.addEventListener("keydown", (event) => {
    const current = tabs.indexOf(document.activeElement as HTMLButtonElement);
    if (current < 0) return;
    let next: number;
    switch (event.key) {
      case "ArrowRight":
        next = (current + 1) % tabs.length;
        break;
      case "ArrowLeft":
        next = (current - 1 + tabs.length) % tabs.length;
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = tabs.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    const tab = tabs[next];
    if (tab) select(tab, true);
  });

  container?.classList.add("tabs-ready");
}

// Copy buttons for the install commands. Without a clipboard API the buttons
// are hidden and the commands stay selectable.
function setUpCopyButtons(): void {
  const buttons = document.querySelectorAll<HTMLButtonElement>("[data-copy]");
  const status = document.querySelector<HTMLElement>("[data-copy-status]");
  const clipboard = window.isSecureContext ? navigator.clipboard : undefined;
  if (!clipboard) {
    buttons.forEach((button) => {
      button.hidden = true;
    });
    return;
  }
  let resetTimer: number | undefined;
  // Alternate the wording so a repeated copy is announced again.
  let copies = 0;
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      const code = button.closest(".cmd")?.querySelector("code")?.textContent ?? "";
      clipboard.writeText(code).then(
        () => {
          buttons.forEach((other) => {
            other.textContent = "Copy";
          });
          button.textContent = "Copied";
          copies += 1;
          if (status) status.textContent = copies % 2 ? "Copied." : "Copied to the clipboard.";
          window.clearTimeout(resetTimer);
          resetTimer = window.setTimeout(() => {
            button.textContent = "Copy";
            if (status) status.textContent = "";
          }, 2000);
        },
        () => {
          if (status) status.textContent = "Copy is unavailable here. Select the command instead.";
        },
      );
    });
  });
}

followSystemTheme();
setUpSlipSweep();
setUpRevealFallback();
setUpTabs();
setUpCopyButtons();
