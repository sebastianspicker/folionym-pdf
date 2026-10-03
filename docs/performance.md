# Resource limits and performance

Folionym bounds work at the extraction, model, cache, and browser boundaries.
Exact reviewed targets, source fingerprints, private backups, and no-overwrite
checks remain part of every applicable rename flow.

## Extraction and model sessions

Text extraction accumulates pages until it reaches the configured token budget,
then truncates what it keeps. The default budget is 28,000 tokens.
`--max-pages-for-extraction` limits visited pages separately. A single unusually
dense page still has to be extracted before its text can be measured.

`--full-text-extraction` reads all selected pages before truncation, preserving
the previous extraction strategy. Use it when comparing against established
naming results: early stopping can change the retained text near the truncation
boundary. It does not disable the final token cap. OCR work is not interrupted
by the text budget and has no application-level timeout.

`--workers` bounds parallel proposal work. Model requests use one independently
owned session by default. `--llm-concurrency N` opts into a session pool, limited
by the effective worker count; interactive CLI processing uses one worker. Each
session serves one request at a time. Cancellation stops waiting model calls,
while an already-running HTTP request must finish or time out before shutdown
completes. Raising concurrency only helps when the endpoint can process requests
concurrently, so benchmark it against the default with the same model and inputs.

Heuristic-only naming does not initialize the response cache or read the source
again to calculate an LLM cache key. LLM response caching keeps full-file
hashing and the checks that detect a source change during hashing.

## Cache and image budgets

These CLI options also work as underscore-separated keys in a CLI JSON/YAML
configuration file. The browser and TUI use the defaults for limits their forms
do not expose.

| Option | Default |
| --- | --- |
| `--cache-max-memory-entries` | 256 responses per shared cache |
| `--cache-max-memory-bytes` | 16 MiB of UTF-8 response and key bytes |
| `--cache-max-disk-entries` | 2,048 entries per cache directory |
| `--cache-max-disk-bytes` | 256 MiB per cache directory |
| `--cache-ttl-s` | 2,592,000 seconds (30 days) |
| `--vision-max-pixels` | 4,000,000 rendered pixels |
| `--vision-render-dpi` | 300 DPI before pixel and dimension limits |
| `--vision-max-dimension-pixels` | 4,096 pixels per dimension |
| `--vision-max-encoded-bytes` | 8 MiB of encoded image bytes |

The memory byte budget measures payload bytes, not total Python-process memory.
The process keeps at most 16 shared response-cache instances. Cache limits do not
cap extracted text, model responses in flight, or the whole application's memory.
A zero memory or disk capacity disables that storage tier, and a zero cache TTL
disables age expiry. `--no-cache` disables response caching entirely.

Persistent cache maintenance removes only regular files named
`folionym-<sha256>.json` that carry a validated Folionym ownership marker. It
preserves unrelated files, symlinks, and unmarked legacy entries. The disk budget
applies to managed entries; preserved legacy or foreign files sit outside it.
Legacy cache responses stay readable until the first new-format cache write marks
the directory as migrated, after which reads ignore legacy entries so an evicted
replacement cannot expose an older response. Responses are still written
atomically with owner-only permissions where supported. Disk eviction uses entry
age; memory eviction uses recency.

Vision images are downscaled before rasterization to satisfy the pixel and
dimension bounds, and oversized encoded images are refused before a base64
request is built. These are allocation controls, not a PDF sandbox.

Browser thumbnails have their own limits: 900 by 1,200 pixels, 4 MiB per encoded
image, and a cache of at most 128 entries and 16 MiB. Entries expire after five
minutes and are removed on later cache access. Every request validates the
reviewed source identity. Thumbnail bytes stay in process memory, and HTTP
responses keep `no-store`.

## Large directories and plans

Discovery uses directory-entry metadata and prunes descent at the configured
depth. Watch mode remains polling-based and must scan its selected scope each
cycle. The folder picker defers child-directory counts until a folder is opened
and keeps a short-lived bounded listing cache with an explicit Refresh action.

The browser loads plan summaries without document metadata or per-item live
filesystem reads. Selecting an item loads its evidence separately. Ledgers render
50 rows per page, and selection persists across pages. See the
[browser guide](frontend.md) for selection and connection-recovery behavior.

The backend retains up to 32 completed runs for one hour, with at most 256 recent
events per run. Active operations keep their inputs. Expired plans need a new
Preview. Old event cursors receive a current snapshot instead of requiring
unlimited event retention. These count limits do not limit the size of one plan.

## Verification

Run focused Python tests with `uv run pytest`, frontend tests with `npm test`
inside `frontend/`, and the real-browser suite with `npm run test:browser`. The
browser suite uses an installed Chromium executable and an isolated profile; it
downloads no browser or test framework. `make release-check` includes Node tests,
Python checks, application tests, and built-distribution verification. CI also
runs the browser suite.

Synthetic tests cover early extraction termination, cache bounds, isolated model
sessions, cancellation, bounded event history, stale sources, directory pruning,
and selection across large plans. They verify mechanisms; they do not establish
OCR speed or throughput for a particular model endpoint.

For a synthetic 1,000-item plan with 10,000 metadata characters per item,
lightweight summaries reduced JSON output from 10,335,180 to 321,180 bytes.
Across five serializations on local CPython 3.14.7, median elapsed time was
22.4 ms for full payloads (20.66–25.89 ms range) and 3.77 ms for summaries
(3.66–3.83 ms range). These figures depend on metadata size and hardware.

Dependency CI exports all extras from the frozen `uv.lock`, including the web
interface, for a hashed-requirements audit using the supported
[pip-audit options](https://github.com/pypa/pip-audit#usage). A separate
[npm audit](https://docs.npmjs.com/cli/v11/commands/npm-audit/) checks the
frontend lockfile. Configuring these jobs does not establish that a remote run
passed.
