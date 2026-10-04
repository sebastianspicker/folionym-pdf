# Folionym design brief

This brief records the evidence, decisions, and assumptions behind the 2026
redesign of the browser interface (`frontend/`), its static Pages demo, and the
screenshot tour (`docs/tour.html`). The Textual TUI keeps its own terminal
styling and is out of scope.

## 1. Product

Folionym renames PDFs from what is inside them. It extracts text and metadata
(optionally OCR or a vision model), applies deterministic rules and optional
local-LLM enrichment, and proposes names shaped like
`YYYYMMDD-category-keywords-summary.pdf`. Nothing on disk changes until the
operator has reviewed the proposals and applied exact, selected targets.

The browser interface is a three-stage loopback application:

1. **Source**: choose a folder or a single PDF; naming, extraction, endpoint,
   and output settings sit behind *Fine-tune*.
2. **Preview**: a process-local immutable plan. A paged ledger (50 rows) of
   current name → proposed name with status `ready`, `review`, `skipped`,
   `failed`; an evidence inspector with first-page thumbnail, metadata, and the
   reason for the name; selection, filter, search, keyboard shortcuts.
3. **Apply**: confirmation dialog (Cancel first), progress overlay, then a
   per-file report (`renamed`, `skipped`, `unchanged`, `failed`, `cancelled`).

**Moment of value:** the Preview ledger, when a column of `scan_0047.pdf`,
`Kontoauszug_01_2024 (1).pdf`, `Vertrag_final_FINAL_v2.pdf` turns into a column
of dated, legible names, and the operator can see *why* each one was chosen.
The Apply report is the second moment: proof of exactly what moved.

## 2. Audience

**Primary: the careful archivist of their own paperwork.** A technically
literate individual (developer, researcher, freelancer, small-office admin)
who keeps years of invoices, bank statements, contracts, receipts, and papers
as PDFs on their own disk, and who installs a Python package from source to
fix it. Many work in German and English (default language `de`, demo files
like `Kontoauszug`, `Vertrag`).

- **Goals:** a folder they can scan by eye and sort by name; consistent dates;
  no manual retyping.
- **Anxieties:** a tool silently mangling hundreds of files; financial
  documents leaving the machine; an "AI" guessing confidently and wrongly.
- **Distrusts:** cloud upload, magic, sparkle-AI marketing, opaque batch
  actions, dashboards that hide the actual filename.
- **Daily tools:** terminal, file manager, text editor, Ollama or llama.cpp,
  maybe Paperless-ngx or DEVONthink.
- **What signals quality to them:** exactness. The real filename rendered in
  full and legibly; unambiguous characters (`0/O`, `1/l/I`); visible
  consequences before an action; keyboard operation; respect for their
  attention. Quiet confidence reads as competence; decoration reads as a
  product trying to sell them something.

**Secondary:** visitors to the Pages demo evaluating the project. They need the
same screens, clearly marked as simulated.

## 3. Key journeys

1. Folder → Build preview → scan ledger → inspect *Review* rows → select →
   Apply → read report. (Primary; most design effort.)
2. Single PDF by absolute path → Preview → Apply one name.
3. First run against a non-loopback endpoint → acknowledgement dialog.
4. Long-running preview → progress → cancel or reconnect after failure.
5. Expired plan or report → recover back to Source.

## 4. Brand traits

| Trait | Not |
| --- | --- |
| **Exact**: every name, count, and consequence is stated precisely | pedantic or legalistic |
| **Candid**: shows uncertainty and failure plainly | alarmist |
| **Calm**: unhurried, quiet surfaces, one accent | sleepy or vague |
| **Private by construction**: local is the default state, not a feature to sell | secretive or paranoid |
| **Crafted**: the care of a well-kept register | precious, nostalgic, or costume-like |

## 5. Market observations

Closest alternatives: AI renamers (renamr, ai-renamer, pdf-renamer-ai CLIs;
PDF AI Renamer and NameQuick on macOS; Renamer.ai as a hosted service),
classic batch renamers (A Better Finder Rename, Hazel rules), and document
managers (Paperless-ngx, DEVONthink).

- **AI renamers** sell with sparkles, purple-to-blue gradients, rounded macOS
  cards, and "magic" copy. Their before/after demos crop or truncate the
  filenames they are supposed to fix.
- **CLI renamers** present as terminal transcripts: honest, but no review
  surface beyond scrolling text.
- **Batch renamers** use dense two-column *original → new* tables. This
  convention is load-bearing; users already read renames this way.
- **Document managers** look like admin dashboards (Bootstrap sidebars, tag
  chips, cards).

**Honor:** the two-column *current → proposed* reading order, a dry run before
any write, monospace for real filenames, light and dark themes.
**Break:** AI theatrics, cards-and-chips dashboards, truncated filenames,
status-pill confetti, SaaS hero framing.

## 6. Current state

Stack: React 19, TypeScript, Vite, plain CSS split into modules (`styles/`),
`@fontsource` IBM Plex Sans/Mono, no component library. A restrictive CSP
(`style-src 'self'`, `font-src 'self'`, `img-src 'self' blob:`) rules out
external fonts, inline `<style>`, and `data:` images in CSS.

**Worth keeping:** the verdigris accent `#0e6b57` (favicon, README badge,
existing screenshots: real if modest brand equity); warm paper neutrals; the
three-stage model; the filename diff (`lib/filenameDiff.ts`); keyboard model;
the document-leaf mark.

**Weaknesses found in the rendered UI:**

- IBM Plex everywhere with pill buttons, pill stepper, pill statuses: competent
  but generic "calm SaaS"; type carries no character.
- The ledger strikes through *every* current name, including skipped and
  failed rows that will not change, and truncates long proposed names: the
  product's core artifact is the least legible thing on screen.
- Apply report renders every reason in error red, including neutral ones
  ("Not selected in this demo run").
- "Naming: kebab · MMDDYYYY" and "MDY date" imply the output date format; the
  setting only controls how ambiguous dates are *read*. Output always starts
  `YYYYMMDD`.
- The Source page's right rail and the Preview's left rail repeat the same
  facts; the Preview rail shows the source twice.
- Status filter labels are centred against left-aligned dots; four metric boxes
  on Apply look like a dashboard.
- About 3,900 lines of CSS, a quarter of it (`reading-room.css`) overriding the
  rest.

## 7. Constraints

- Routes `/`, `/preview`, `/apply` (with demo base `/folionym-pdf/`), the
  `/api/v1` contract in `api.ts`, `sessionStorage` keys, `localStorage`
  `folionym.theme`.
- Tests depend on: `role="option"` rows with `aria-posinset/setsize`,
  `class="result-row"`, button labels *Select page*, *Next page*, text
  *First page unavailable*, *N PDFs in this folder*, *Automatic retries
  paused*, `aria-label="Folder path"`.
- Product rules (PRODUCT.md): source paths, proposed names, statuses, and
  consequences visible; Preview before Apply; Cancel first in destructive
  confirmation; colour always paired with text; advanced settings out of the
  initial selection; loopback described honestly; demo data labelled.
- WCAG 2.2 AA, full keyboard use, `prefers-reduced-motion`, mobile as its own
  layout. `src/folionym/web_dist/` must be rebuilt and committed.

## 8. Assumptions log

| Assumption | Evidence | Confidence |
| --- | --- | --- |
| Primary users are technical individuals managing personal or small-office archives | install-from-source only, CLI first, loopback-only UI, demo documents are invoices/statements/contracts | high |
| German–English bilingual users are common | default `language: de`, German demo filenames, German date-label parsing | medium |
| Filenames usually follow the default `date-category-keywords` shape | README, default composer; but templates and camelCase exist | medium (designs must not depend on it) |
| Typical runs are tens to low hundreds of files; thousands are possible | pagination at 50, 10,000-item tests | medium |
| Desktop is primary; mobile is used to glance at the demo, rarely to run a local service | loopback-only service, demo published on Pages | medium |
| Verdigris has brand equity worth keeping | favicon, README licence badge colour, tour page | medium |
| Dark mode matters to this audience | existing toggle and dark screenshot in README | high |

## Design Direction

Three directions were developed from the domain: registry and archival
practice (folio = numbered leaf, *-onym* = name), the act of composing a name,
and the precision of a measuring instrument.

### Direction A: The Register *(chosen)*

**Concept.** Folionym is a registrar. Each run is an accession register: every
document gets a numbered entry, its old name is recorded, its new name is
written in a clear hand, and the reason is noted in the margin. The interface
borrows the *discipline* of a register (ruled lines, entry numbers, marginal
notes, a running head) without imitating paper. It fits because the audience's
fear is losing track of what happened to their files; a register is the
oldest tool built to answer exactly that.

- **Typography.** Three open-licensed families, each with one job.
  *Newsreader* (Production Type, OFL) for headings, numerals in tallies, and
  the explanatory "why this name" notes: a reading serif with optical sizes,
  scholarly rather than literary. *Atkinson Hyperlegible Next* (Braille
  Institute, OFL) for interface text. *Atkinson Hyperlegible Mono* for every
  real filename and path: designed so that `0 O o`, `1 l I`, `rn m` can never
  be confused, which is the one typographic property this product truly
  needs. Scale: 12 / 13 / 14 / 16 / 20 / 28 / 40 px, tight serif headings,
  generous UI leading.
- **Colour.** Archive paper `#f5f2ea`, sheet `#fcfbf7`; iron-gall ink
  `#1d2129` (a blue-black instead of neutral black); verdigris `#0d6b57` kept
  as the single action and "ready" colour; ochre `#8a5800` for *review*;
  madder `#a42a2f` for *failed* only; graphite for skipped. Dark mode is a
  night reading room: ink-blue `#13161b` with paper-tinted text, not inverted
  grey.
- **Layout.** A ruled register: rows on a fixed rhythm separated by hairlines,
  with a narrow margin column of entry numbers (`001`, `002`) in old-style
  serif figures. Each entry stacks the old name above the new one, so long
  names wrap instead of truncating. Source is asymmetric: the source slip and
  the naming rules on the left, and a "before anything moves" column on the
  right. Preview keeps three columns at desktop (index · register · evidence).
- **Motion.** Almost none. The active-entry marker and focus ring transition in
  120 ms; the drawer slides 200 ms; the progress rule scales on `transform`.
  No entrance animations.
- **Signature details.** (1) *Name anatomy*: on Source, an example filename
  built from the current case, project, and version settings, with each segment
  labelled underneath in small caps (date · category · keywords · summary); it
  teaches the format and changes as settings change. (2) *Entry numerals and
  the date column*: entry numbers in the margin, and the leading `YYYYMMDD` of
  proposed names set as a distinct column so a page of dates scans like a
  register.
- **Against category conventions.** No sparkle-AI, no cards, no pills for
  everything; filenames are the largest, most legible text on the screen.
- **Refuses.** Paper textures, fake stamps, handwriting fonts, sepia nostalgia,
  skeuomorphic leather, decorative illustration.

### Direction B: Composing stick

**Concept.** A filename is composed like a line of type: each field (date,
category, keywords) is a slug set into a stick. The UI presents names as rows
of segmented slugs that the user can inspect and reorder.

- **Typography.** A grotesk with ink-trap detail (Schibsted Grotesk) and
  Martian Mono for slugs; large numerals.
- **Colour.** Black, newsprint, and a cadmium orange for selection.
- **Layout.** Strict 12-column Swiss grid, big section numbers, filenames as
  segmented bars.
- **Motion.** Slugs slide into place when a proposal arrives.
- **Signature.** Segmented filename bars with field labels.
- **Refuses.** Rounded corners and shadows.
- **Why not.** It depends on parsing every name into fields, which breaks for
  templates, camelCase, and truncated names (a medium-confidence assumption),
  and segmented bars make long names *wider*, which worsens the core
  legibility problem. Printer's-slug imagery also leans decorative.

### Direction C: Bench instrument

**Concept.** A precision instrument: dark-first console, indicator lamps for
status, every value monospaced, dense tables like a logic analyser.

- **Typography.** JetBrains Mono throughout, with a condensed sans for labels.
- **Colour.** Graphite console, phosphor-green readouts, amber and red lamps.
- **Layout.** Dense, edge-to-edge panels, small type, keyboard-first.
- **Motion.** Lamp flicker on status change, scrolling event log.
- **Signature.** Status lamps and a live event tape during Preview.
- **Refuses.** Light mode as default, serif type.
- **Why not.** It is the developer-tool default (terminal cosplay) that makes
  CLI renamers look alike, it reads as "for engineers only" to the
  freelancer-with-receipts half of the audience, and phosphor-on-dark sits too
  close to neon-glow clichés.

### Choice

**A, the Register.** It grows from the product's own name and its central
promise (a reviewable, numbered record of what will change and what did). It
keeps the brand's paper and verdigris while giving type a real job: the serif
for explanation, a hyperlegible mono for the artifact itself. It is also the
most robust direction: nothing in it requires parsing filenames correctly.
The date column falls back to plain text, and name anatomy is shown only as a
labelled example.

**Trade-offs.** A loses B's graphic punch and C's density at 10,000 rows. Two
lines per entry fit fewer rows on screen than one; legibility of full names
is judged more valuable than density for runs of tens to hundreds. A serif in
a utility interface risks feeling bookish, so it is limited to headings,
numerals, and explanatory notes.
