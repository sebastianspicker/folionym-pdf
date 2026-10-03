const palette = ["#0b6a5a", "#496a92", "#9b5d32", "#72548c", "#526d46", "#7d4c4c", "#667068", "#a62633"];

function svgData(label: string, accent: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="640" height="860" viewBox="0 0 640 860" role="img" aria-label="Demo document preview"><rect width="640" height="860" fill="#eef0ea"/><rect x="72" y="54" width="496" height="752" rx="8" fill="#fffdf8" stroke="#d5d8d0" stroke-width="3"/><rect x="112" y="112" width="260" height="18" rx="9" fill="${accent}"/><rect x="112" y="156" width="386" height="10" rx="5" fill="#c9cec5"/><rect x="112" y="184" width="336" height="10" rx="5" fill="#d9ddd5"/><rect x="112" y="258" width="416" height="128" rx="6" fill="#f1f3ed"/><rect x="136" y="286" width="186" height="12" rx="6" fill="#bcc5b9"/><rect x="136" y="318" width="310" height="12" rx="6" fill="#cbd2c9"/><rect x="136" y="350" width="252" height="12" rx="6" fill="#cbd2c9"/><rect x="112" y="438" width="356" height="10" rx="5" fill="#d9ddd5"/><rect x="112" y="466" width="404" height="10" rx="5" fill="#d9ddd5"/><rect x="112" y="494" width="278" height="10" rx="5" fill="#d9ddd5"/><text x="112" y="690" fill="#455148" font-family="ui-monospace, monospace" font-size="22">${label}</text><text x="112" y="726" fill="#768177" font-family="ui-monospace, monospace" font-size="15">DEMO DOCUMENT · NO FILE ACCESS</text></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

export function demoThumbnail(itemId: string): string {
  const index = Math.max(0, ["demo-invoice", "demo-statement", "demo-contract", "demo-receipt", "demo-hetzner", "demo-paper", "demo-archived", "demo-scan"].indexOf(itemId));
  return svgData(`FOLIONYM / ${String(index + 1).padStart(2, "0")}`, palette[index] ?? palette[0]);
}
