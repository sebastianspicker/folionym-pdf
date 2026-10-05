import type {
  Bootstrap,
  DirectoryListing,
  Plan,
  PreviewItem,
  Report,
  Settings,
} from "../types";

const DEMO_SOURCE = "/Users/demo/Documents/statements-2024";

export const demoSettings: Settings = {
  directory: DEMO_SOURCE,
  single_file: "",
  language: "en",
  case: "kebabCase",
  date_format: "mdy",
  preset: "",
  project: "",
  version: "",
  template: "",
  backup_dir: "",
  rename_log: "",
  export_metadata: "",
  summary_json: "",
  rules_file: "",
  post_rename_hook: "",
  llm_url: "http://127.0.0.1:11434/v1/completions",
  llm_model: "qwen2.5",
  llm_timeout: "",
  max_tokens: "",
  max_content_chars: "",
  max_content_tokens: "",
  workers: "2",
  max_filename_chars: "120",
  acknowledged_external_endpoint: "",
  dry_run: false,
  use_llm: true,
  use_ocr: true,
  recursive: true,
  skip_already_named: true,
  use_pdf_metadata_date: true,
  use_structured_fields: true,
  write_pdf_metadata: false,
  use_vision_fallback: false,
  simple_naming_mode: true,
  vision_first: false,
};

export const demoBootstrap: Bootstrap = {
  settings: demoSettings,
  roots: [
    { name: "Documents", path: "/Users/demo/Documents", pdf_count: 8 },
  ],
  capabilities: {
    ocr: true,
    pdf_metadata: true,
    vision: false,
  },
};

const demoItems: PreviewItem[] = [
  {
    id: "demo-invoice",
    current_name: "scan_0047.pdf",
    source_path: `${DEMO_SOURCE}/scan_0047.pdf`,
    proposed_name: "20240115-invoice-brightwell-hosting-129-00-eur.pdf",
    status: "ready",
    included: true,
    reason:
      "Invoice INV-2024-0117 for 129,00 € dated 15 Jan 2024 was found on page 1; Brightwell Hosting matched the vendor rule.",
    size: 188_416,
    modified_at: "2024-01-15T08:12:00Z",
    metadata: {
      producer: "Brightwell Billing 4.2",
      invoice_id: "INV-2024-0117",
      pages: 2,
    },
  },
  {
    id: "demo-statement",
    current_name: "Kontoauszug_01_2024 (1).pdf",
    source_path: `${DEMO_SOURCE}/Kontoauszug_01_2024 (1).pdf`,
    proposed_name: "20240131-statement-deutsche-bank-giro-january.pdf",
    status: "ready",
    included: true,
    reason:
      "The account statement period, bank name, and account type produced a unique exact target.",
    size: 421_760,
    modified_at: "2024-01-31T16:42:00Z",
    metadata: { bank: "Deutsche Bank", period: "January 2024", pages: 4 },
  },
  {
    id: "demo-contract",
    current_name: "Vertrag_final_FINAL_v2.pdf",
    source_path: `${DEMO_SOURCE}/Vertrag_final_FINAL_v2.pdf`,
    proposed_name: "20240301-contract-freelance-meridian-design-system.pdf",
    status: "ready",
    included: true,
    reason:
      "The signature date, contract type, counterparty, and project were found in the agreement.",
    size: 712_640,
    modified_at: "2024-03-01T10:03:00Z",
    metadata: { counterparty: "Meridian", project: "Design system", pages: 8 },
  },
  {
    id: "demo-receipt",
    current_name: "IMG_20240312_1441.pdf",
    source_path: `${DEMO_SOURCE}/IMG_20240312_1441.pdf`,
    proposed_name: "20240312-receipt-unknown-vendor-84-20-eur.pdf",
    status: "review",
    included: false,
    reason:
      "The date and total are clear, but the merchant could not be identified reliably.",
    size: 96_180,
    modified_at: "2024-03-12T13:41:00Z",
    metadata: { amount: "84,20 €", extraction: "OCR", pages: 1 },
  },
  {
    id: "demo-hetzner",
    current_name: "invoice (22).pdf",
    source_path: `${DEMO_SOURCE}/invoice (22).pdf`,
    proposed_name: "20240220-invoice-hetzner-cloud-inv-2024-0184.pdf",
    status: "ready",
    included: true,
    reason:
      "Invoice ID INV-2024-0184, issue date, and Hetzner Cloud were found in structured fields.",
    size: 205_312,
    modified_at: "2024-02-20T07:28:00Z",
    metadata: {
      vendor: "Hetzner Cloud",
      invoice_id: "INV-2024-0184",
      pages: 2,
    },
  },
  {
    id: "demo-paper",
    current_name: "1706.03762v7.pdf",
    source_path: `${DEMO_SOURCE}/1706.03762v7.pdf`,
    proposed_name: "20240405-paper-attention-mechanisms-transformer-architecture.pdf",
    status: "review",
    included: false,
    reason:
      "The publication date and subject are clear; the compact summary needs review.",
    size: 2_428_928,
    modified_at: "2024-04-05T09:15:00Z",
    metadata: { title: "Attention Is All You Need", pages: 15 },
  },
  {
    id: "demo-archived",
    current_name: "20231231-statement-deutsche-bank-giro-december.pdf",
    source_path: `${DEMO_SOURCE}/20231231-statement-deutsche-bank-giro-december.pdf`,
    proposed_name: null,
    status: "skipped",
    included: false,
    reason: "Already matches the selected naming style.",
    size: 84_320,
    modified_at: "2023-12-31T18:11:00Z",
    metadata: { pages: 1 },
  },
  {
    id: "demo-scan",
    current_name: "attachment_scan_99.pdf",
    source_path: `${DEMO_SOURCE}/attachment_scan_99.pdf`,
    proposed_name: null,
    status: "failed",
    included: false,
    reason:
      "No extractable text was found and OCR did not produce enough naming evidence.",
    size: 1_024_000,
    modified_at: "2024-04-21T08:20:00Z",
    metadata: { pages: 2 },
  },
];

export const demoPlan: Plan = {
  id: "demo-plan",
  revision: 1,
  source: DEMO_SOURCE,
  source_kind: "directory",
  created_at: "2024-05-02T10:00:00Z",
  items: demoItems,
  counts: { all: 8, ready: 4, review: 2, skipped: 1, failed: 1 },
};

const listings: Record<string, DirectoryListing> = {
  "/Users/demo/Documents": {
    path: "/Users/demo/Documents",
    parent: null,
    pdf_count: 8,
    entries: [
      { name: "statements-2024", path: DEMO_SOURCE, pdf_count: 8 },
      {
        name: "Archive",
        path: "/Users/demo/Documents/Archive",
        pdf_count: 12,
      },
    ],
  },
  [DEMO_SOURCE]: {
    path: DEMO_SOURCE,
    parent: "/Users/demo/Documents",
    pdf_count: 8,
    entries: [],
  },
  "/Users/demo/Documents/Archive": {
    path: "/Users/demo/Documents/Archive",
    parent: "/Users/demo/Documents",
    pdf_count: 12,
    entries: [],
  },
};

export function demoListing(path: string): DirectoryListing {
  return listings[path] ?? listings[DEMO_SOURCE];
}

export function clonePlan(plan: Plan): Plan {
  return {
    ...plan,
    counts: { ...plan.counts },
    items: plan.items.map((item) => ({
      ...item,
      metadata: { ...item.metadata },
    })),
  };
}

export function cloneReport(report: Report): Report {
  return {
    ...report,
    counts: { ...report.counts },
    items: report.items.map((item) => ({ ...item })),
  };
}
