import { useEffect, useState } from "react";

export type Route = "source" | "preview" | "apply";

const appBase = import.meta.env.BASE_URL.replace(/\/$/, "");

function routePathname(): string {
  const pathname = window.location.pathname;
  return appBase && pathname.startsWith(appBase)
    ? pathname.slice(appBase.length) || "/"
    : pathname;
}

export function currentRoute(): Route {
  const pathname = routePathname();
  if (pathname.startsWith("/preview")) return "preview";
  if (pathname.startsWith("/apply")) return "apply";
  return "source";
}

export function navigate(route: Route) {
  const path = route === "source" ? `${appBase}/` || "/" : `${appBase}/${route}`;
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export function useRoute() {
  const [route, setRoute] = useState<Route>(currentRoute());
  useEffect(() => {
    const update = () => setRoute(currentRoute());
    window.addEventListener("popstate", update);
    return () => window.removeEventListener("popstate", update);
  }, []);
  return route;
}
