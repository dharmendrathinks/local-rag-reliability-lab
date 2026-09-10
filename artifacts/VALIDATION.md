# Validation

## Reference experiment

The September 10, 2026 reference run recorded 69/69 completed generation requests across three local Ollama trials, with zero request failures or truncations. The historical pytest XML records 37 passing deterministic tests. See [RESULTS.md](../RESULTS.md) for counts, model digests, scope, and evidence links.

The deterministic lifecycle tests use fake embeddings with real persistent Chroma. Model observations use local EmbeddingGemma and Gemma 3. The evidence audit re-reads saved observations without inference. These are separate forms of validation.

## Public-repository preparation

The following checks passed after adding public documentation, package metadata, and the disclosed evidence redactions:

- `uv lock --check` and `uv sync --frozen`.
- `uv run --frozen pytest -q`: 37 passed.
- `uv run --frozen python scripts/audit_evidence.py artifacts/20260910T162236Z-9789c2ee`: 443 checks passed, no failed checks. The published audit includes refreshed SHA-256 hashes.
- `uv build`: source distribution and wheel built. The wheel contains the MIT license and `License-Expression: MIT`; the source distribution excludes local evidence, logs, indexes, and private backups.
- `uv run --frozen raglab --help`: CLI entry point works.
- Local Markdown file links resolve, and publication files contain no original personal home paths or hostnames.
- Gitleaks 8.30.1 scanned the publication snapshot (about 4.12 MB): no leaks found. This is a detection result, not a guarantee that arbitrary future data is safe to share.
- PR readiness analyzer: **PR READY** for the staged initial implementation against the MIT-license baseline. Build, 37 tests, and static compilation passed; no suspicious files or blockers were detected. Lint was skipped because no lint check is configured.

The GitHub Actions workflow runs tests, evidence auditing, source compilation, and builds on Linux and macOS. These checks do not rerun model inference. Local preparation reused the historical model evidence; it did not produce a new 69-request experiment.
