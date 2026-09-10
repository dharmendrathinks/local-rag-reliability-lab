# Contributing

Thanks for helping make local RAG behavior easier to inspect. Bug reports, documentation fixes, lifecycle tests, and reproducible experiments are welcome. Participation follows our [code of conduct](CODE_OF_CONDUCT.md).

## Development setup

Fork this repository, clone your fork, and create a branch from `main`. Use macOS or Linux (WSL on Windows), Python 3.12, and [uv](https://docs.astral.sh/uv/).

```bash
uv sync --frozen
uv run --frozen pytest -q
uv run --frozen python scripts/audit_evidence.py artifacts/20260910T162236Z-9789c2ee
uv build
```

Tests use real persistent Chroma and deterministic test embeddings. They need no Ollama server, model download, or API key. See [README.md](README.md) for real-model setup. Keep runtime dependencies and `uv.lock` together when changing dependencies; explain any pin changes.

## Proposing a change

Open an issue before a substantial feature or protocol change so we can agree on its scope. For a small fix, send a pull request directly. Describe the concrete behavior before and after the change, relevant validation, and remaining limitations. Add a regression test when changing lifecycle or failure behavior. Never hide a failed observation or regenerate the reference results merely to make a test pass.

Preserve these distinctions:

- Source presence, active index records, retrieved evidence, and generated answers are separate observations.
- `ingest` retains absent documents; only explicit `sync` reconciles their deletion.
- Failed scans and interrupted writes must remain visible and recoverable.
- Evaluation ground truth stays outside the searchable corpus and generation prompt.
- Test doubles and actual model observations are reported separately.

## Sharing experiment evidence

Use fictional data. Artifacts include full document text, prompts, answers, absolute paths, and model metadata. New runs and local workspaces are ignored by default. Review every file before explicitly adding a new run, redact personal paths and hostnames consistently, and document the redactions. Never commit credentials, source indexes, model weights, `.env` files, or raw server logs. See [the reference publication notes](artifacts/README.md).

Recompute the evidence audit after any disclosed redaction. Preserve random trial values, responses, counts, failures, IDs, model digests, and settings. Changes to models, retrieval, prompts, or protocol are new experiments and must not overwrite the recorded reference run.

## License and review

By contributing, you agree to license your original contributions under this project's [MIT License](LICENSE). Only submit material you have the right to contribute; preserve third-party notices. No contributor license agreement is required. Maintainers review contributions as time permits.

Report vulnerabilities through [SECURITY.md](SECURITY.md), not a public issue.
