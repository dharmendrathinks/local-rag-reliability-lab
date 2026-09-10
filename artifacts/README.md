# Published experiment evidence

`20260910T162236Z-9789c2ee` is the reference run used in [RESULTS.md](../RESULTS.md). It contains three trials and 69 actual Ollama generation observations. `evidence-audit.json` recomputes 443 checks from those observations without inference. `pytest-results.xml` records a separate 37-test deterministic suite.

## Privacy edits for publication

Before the first public commit, personal path prefixes were replaced consistently throughout the published JSON and Markdown:

- The original checkout directory became `/workspace/local-rag-reliability-lab`.
- Remaining paths beneath the operator's home became `/home/lab-user`.
- The pytest XML hostname became `redacted-local-host`.

These are publication placeholders, not directories you need to create. The edits change recorded command/path metadata, including source-root paths and model blob paths. They do not change source text, random launch codes, record IDs, model digests, settings, prompts, responses, counts, or timings. The evidence audit and its SHA-256 inventory were regenerated after redaction and refer to the published bytes, not the original private files.

The launch codes are fictional random experiment fixtures, not credentials. Full model responses and third-party license notices are retained. Raw setup/server logs, model downloads, historical local readiness reports, final local index inspections, and live `work-*` directories are not published. The local-only server startup observation is reported in RESULTS.md; its raw server log is retained locally rather than distributed.

## Recheck or reproduce

```bash
uv sync --frozen
uv run --frozen python scripts/audit_evidence.py artifacts/20260910T162236Z-9789c2ee
```

The audit reads saved JSON; it cannot reopen the original index or attest to a running server. Follow the [README](../README.md) to create a new experiment with live indexes on your own machine.

New runs, logs, and temporary indexes are ignored by Git. Review, sanitize, and document any new evidence before explicitly adding it. Never ingest the artifacts directory: ground truth and traces deliberately retain information after the source and active target record are deleted.
