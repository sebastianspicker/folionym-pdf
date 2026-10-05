// First pages rendered from simulated sample PDFs (see docs/frontend.md).
// They ship only in the demo build, through the demo-only public directory.
const ITEMS = new Set([
  "demo-invoice",
  "demo-statement",
  "demo-contract",
  "demo-receipt",
  "demo-hetzner",
  "demo-paper",
  "demo-archived",
  "demo-scan",
]);

export function demoThumbnail(itemId: string): string {
  const name = ITEMS.has(itemId) ? itemId : "demo-invoice";
  return `${import.meta.env.BASE_URL}demo-thumbnails/${name}.webp`;
}
