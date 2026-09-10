# Results: source deletion retained the snapshot; sync removed it

On September 10, 2026, all three independent local-model trials completed: **69 generation requests, zero request failures and zero truncated responses**.

Deleting the source file did not remove its imported Chroma record. After explicit synchronization, every trial had **zero active target records and both unrelated control records intact**. The model then abstained on every target question, including after application restart.

| Stage | Exact launch-code answers | Target queries retrieving target chunks | Correct control answers |
|---|---:|---:|---:|
| A: no context | 0/9 | N/A: no retrieval | N/A |
| B: ingested baseline | 9/9 | 9/9 | 6/6 |
| C: source deleted, application restarted, before sync | 9/9 | 9/9 | 6/6 |
| E: after sync | 0/9 | 0/9 | 6/6 |
| E: after another application restart | 0/9 | 0/9 | 6/6 |

Across **all** contextual questions, including controls, target chunks were retrieved in 9/15 queries at B, 9/15 at C, 0/15 after sync and 0/15 after restart. The target-only rates above keep the three launch-code phrasings separate from the unrelated controls.

Each trial's direct target-record count was **1 → 1 → 0 → 0** at B/C/E/restart. All nine recorded lifecycle invariants passed in each trial. Second syncs performed zero upserts/deletions and preserved the manifest content. The source deletion helper removed only each run's generated `project.txt`; both control files remained on disk.

I reviewed all 69 recorded answers and their contexts. The 27 no-context/post-sync target responses were explicit abstentions; the 18 baseline/pre-sync target responses contained the correct full code. All 24 control responses were correct. There were no invalid numbered citation references. Some abstentions cited unrelated supplied chunks while stating that they lacked launch-code information; those raw outputs are retained rather than repaired.

This is expected **snapshot-import retention before synchronization**, followed by successful deletion from the active index. It is not evidence that the model recovered a deleted disk file. No unsupported launch code was observed after evidence removal. Three trials of tiny fictional documents do not establish statistical certainty or performance on larger corpora.

## Actual environment

- Apple M3 Pro, 18 GiB system memory; local Metal inference.
- Python 3.12.13, Ollama server 0.33.2, Chroma 1.5.9, HTTPX 0.28.1, pytest 9.1.1.
- Embeddings: `embeddinggemma:latest`, 307.58M parameters, BF16, 768 dimensions; digest `85462619ee721b466c5927d109d4cb765861907d5417b9109caebc4e614679f1`.
- Generation: `gemma3:4b`, 4.3B parameters, Q4_K_M; digest `a2af6cc3eb7fa8be8504abaf9b04e88f17a119ec3f04a3addf55f92841195f5a`.
- Temperature 0, seed 42, context 4096, maximum output 256, cosine top-k 2, no threshold, no application answer cache or conversation history.
- The separate server on `127.0.0.1:11435` logged `Ollama cloud disabled: true`. Model downloads used the network; experiment inference was local.

## Evidence and validation

Run ID: `20260910T162236Z-9789c2ee`.

- [Full run report](artifacts/20260910T162236Z-9789c2ee/REPORT.md)
- [Raw run JSON](artifacts/20260910T162236Z-9789c2ee/run.json)
- [Environment, settings and model metadata](artifacts/20260910T162236Z-9789c2ee/environment.json)
- [Trial 1 source-deletion trace](artifacts/20260910T162236Z-9789c2ee/trial-1/C_source_deleted.json)
- [Trial 1 post-sync trace](artifacts/20260910T162236Z-9789c2ee/trial-1/E_after_sync.json)
- [Evidence audit](artifacts/evidence-audit.json): **443 checks passed**, including recomputed counts, exact prompt/context assembly, process separation and absence of the code from active records and requests after sync. This audit makes no inference requests.
- [Deterministic pytest results](artifacts/pytest-results.xml): **37 tests passed**, zero failures/errors/skips. These tests use real persistent Chroma with fake embeddings and injected failures, including a forced process crash. They are not local-model experiments.
- Source distribution and wheel built successfully with `uv build`; `uv sync --frozen` also passed.

The original source fixtures/index workspaces are retained locally under the trial directories and excluded from Git. Ground truth and traces deliberately retain evidence outside the searchable corpus. Claims do not cover backups, model training or forensic erasure.

## Reproduce

From the project directory, first run:

```bash
uv sync --frozen
```

With the local-only server running and models installed as shown in [README.md](README.md):

```bash
uv run raglab run-experiment --trials 3 --output artifacts
```

To recheck the saved evidence without running inference:

```bash
uv run python scripts/audit_evidence.py artifacts/20260910T162236Z-9789c2ee
```
