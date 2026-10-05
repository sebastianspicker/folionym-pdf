import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/fonts.css";
import { App } from "./App";
import "./styles.css";

try {
  const savedTheme = localStorage.getItem("folionym.theme");
  document.documentElement.dataset.theme = savedTheme === "light" || savedTheme === "dark"
    ? savedTheme
    : window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
} catch {
  // Theme preference is an enhancement; private storage modes still render safely.
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Folionym could not find its root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
