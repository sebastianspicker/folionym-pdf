# Support

Thanks for using Folionym. Here is where to look first.

## Documentation

- [README](README.md): installation, configuration, commands, and known limits.
- [Browser guide](docs/frontend.md) and [terminal guide](docs/tui.md): the
  reviewed workflows for each interface.
- [Resource limits and performance](docs/performance.md): extraction, cache,
  model, and browser limits.
- [Documentation index](docs/README.md): everything else.

## Diagnostics

Run `folionym --doctor` to inspect optional dependencies, data files, and LLM
connectivity. Add `--no-llm` to a run when the configured endpoint is
unavailable.

## Asking a question or reporting a problem

This project uses GitHub Issues:

- **Bug:** open a bug report. Include the Folionym version or commit, operating
  system, Python version, install method, and the command you ran.
- **Feature request:** open a feature request and describe the workflow you want.
- **Security issue:** do not open a public issue. Follow
  [SECURITY.md](SECURITY.md) and use the private advisory form.

Before posting logs or file details, redact paths, filenames, document text,
model request or response content, summaries, keywords, and secrets. Never attach
private PDFs.

## Status

Folionym is an alpha (`0.4.0a1`). Compatibility is intentionally limited, and
earlier development milestones are not supported.
