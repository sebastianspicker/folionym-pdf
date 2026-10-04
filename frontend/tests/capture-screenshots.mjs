import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { access, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { extname, join, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";

const here = fileURLToPath(new URL(".", import.meta.url));
const repoRoot = resolve(here, "../..");
const demoDir = join(repoRoot, "dist-demo");
const outputDir = join(repoRoot, "docs/screenshots");
const base = "/folionym-pdf/";

const screenshots = [
  { name: "01-source", path: `${base}`, storage: {} },
  { name: "02-preview", path: `${base}preview`, storage: { plan: "demo-plan" } },
  { name: "03-apply", path: `${base}apply`, storage: { report: "demo-report" } },
  {
    name: "04-preview-dark",
    path: `${base}preview`,
    storage: { plan: "demo-plan", theme: "dark" },
  },
];

const MIME = {
  ".css": "text/css",
  ".html": "text/html",
  ".ico": "image/x-icon",
  ".js": "text/javascript",
  ".json": "application/json",
  ".map": "application/json",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
};

async function findBrowser() {
  const candidates = [
    process.env.FOLIONYM_BROWSER,
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
  ].filter(Boolean);
  for (const candidate of candidates) {
    try {
      await access(candidate);
      return candidate;
    } catch {
      // Check the next installed browser.
    }
  }
  throw Error(
    "Set FOLIONYM_BROWSER to an installed Chromium executable. No browser is downloaded.",
  );
}

function startStaticServer() {
  const server = createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    if (!url.pathname.startsWith(base)) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }
    const relative = url.pathname.slice(base.length);
    const candidate = join(demoDir, relative);
    let file = candidate.endsWith("/") || relative === "" ? join(demoDir, "index.html") : candidate;
    let body;
    try {
      body = await readFile(file);
    } catch {
      file = join(demoDir, "index.html");
      body = await readFile(file);
    }
    response.writeHead(200, { "Content-Type": MIME[extname(file)] ?? "application/octet-stream" });
    response.end(body);
  });
  return new Promise((resolveServer) => {
    server.listen(0, "127.0.0.1", () => resolveServer(server));
  });
}

function connect(webSocketUrl) {
  const socket = new WebSocket(webSocketUrl);
  const pending = new Map();
  const ready = new Promise((resolveReady, rejectReady) => {
    socket.addEventListener("open", () => resolveReady());
    socket.addEventListener("error", () => rejectReady(Error("CDP socket failed.")));
  });
  socket.addEventListener("message", (event) => {
    const message = JSON.parse(event.data);
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id);
    if (message.error) entry.reject(Error(message.error.message));
    else entry.resolve(message.result);
  });
  let nextId = 0;
  const send = async (method, params = {}) => {
    await ready;
    const id = ++nextId;
    const result = new Promise((resolveResult, rejectResult) => {
      pending.set(id, { resolve: resolveResult, reject: rejectResult });
    });
    socket.send(JSON.stringify({ id, method, params }));
    return result;
  };
  return { send, close: () => socket.close() };
}

async function waitForEndpoint(port) {
  for (let attempt = 0; attempt < 100; attempt += 1) {
    try {
      const response = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (response.ok) return;
    } catch {
      // The browser is still starting.
    }
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  throw Error("The browser debugging endpoint did not become ready.");
}

async function openTarget(port) {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: "PUT" });
    return await response.json();
  } catch {
    const response = await fetch(`http://127.0.0.1:${port}/json/list`);
    const targets = await response.json();
    return targets.find((target) => target.type === "page");
  }
}

async function settle(send, timeout = 4000) {
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    const { result } = await send("Runtime.evaluate", {
      expression: "document.readyState === 'complete' && Boolean(document.querySelector('main'))",
      returnByValue: true,
    });
    if (result.value) break;
    await new Promise((resolveWait) => setTimeout(resolveWait, 100));
  }
  await send("Runtime.evaluate", { expression: "document.fonts.ready", awaitPromise: true });
  await new Promise((resolveWait) => setTimeout(resolveWait, 900));
}

async function main() {
  await mkdir(outputDir, { recursive: true });
  const executable = await findBrowser();
  const server = await startStaticServer();
  const origin = `http://127.0.0.1:${server.address().port}`;
  const profile = await mkdtemp(join(tmpdir(), "folionym-shots-"));
  const debugPort = 9333;
  const browser = spawn(
    executable,
    [
      "--headless=new",
      "--disable-gpu",
      "--no-first-run",
      "--no-default-browser-check",
      "--hide-scrollbars",
      `--user-data-dir=${profile}`,
      `--remote-debugging-port=${debugPort}`,
      "about:blank",
    ],
    { stdio: ["ignore", "ignore", "pipe"] },
  );
  try {
    await waitForEndpoint(debugPort);
    const target = await openTarget(debugPort);
    const cdp = connect(target.webSocketDebuggerUrl);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");
    await cdp.send("Emulation.setDeviceMetricsOverride", {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 2,
      mobile: false,
    });
    for (const shot of screenshots) {
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: 1440,
        height: 900,
        deviceScaleFactor: 2,
        mobile: false,
      });
      await cdp.send("Page.navigate", { url: `${origin}${base}` });
      await settle(cdp.send);
      const storage = JSON.stringify(shot.storage);
      await cdp.send("Runtime.evaluate", {
        expression: `(() => { const s = ${storage}; sessionStorage.clear();
          for (const [k, v] of Object.entries(s)) {
            if (k === 'theme') localStorage.setItem('folionym.theme', v);
            else sessionStorage.setItem('folionym.' + k, v);
          } })()`,
      });
      await cdp.send("Page.navigate", { url: `${origin}${shot.path}` });
      await settle(cdp.send);
      const { result } = await cdp.send("Runtime.evaluate", {
        expression: "Math.ceil(document.documentElement.scrollHeight)",
        returnByValue: true,
      });
      const height = Math.min(Math.max(900, result.value), 3000);
      await cdp.send("Emulation.setDeviceMetricsOverride", {
        width: 1440,
        height,
        deviceScaleFactor: 2,
        mobile: false,
      });
      await new Promise((resolveWait) => setTimeout(resolveWait, 350));
      const { data } = await cdp.send("Page.captureScreenshot", { format: "png" });
      const file = join(outputDir, `${shot.name}.png`);
      await writeFile(file, Buffer.from(data, "base64"));
      console.log(`Captured ${file} (${height}px tall)`);
    }
    cdp.close();
  } finally {
    browser.kill();
    await new Promise((resolveClose) => server.close(resolveClose));
    await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 200 });
  }
}

await main();
