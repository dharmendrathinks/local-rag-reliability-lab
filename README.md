# Local RAG Reliability Lab

[![CI](https://github.com/dharmendrathinks/local-rag-reliability-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/dharmendrathinks/local-rag-reliability-lab/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**When I delete a source document, does its information remain in my local RAG system?**

This small Python CLI makes four different things visible: the source file, imported Chroma records, retrieved evidence, and the generated answer. It compares a snapshot importer with explicit deletion synchronization. A retained imported copy is expected snapshot behavior; it is not a model recovering a deleted disk file.

All embeddings and answer generation run through local Ollama. No agents, cloud inference, hosted databases, website, or application answer cache are involved.

**Observed result:** three trials and 69 local-model requests completed. Before sync, all 9 target queries retrieved the deleted source's imported record; after sync and restart, 0/9 did, while both unrelated documents remained available. Read [RESULTS.md](RESULTS.md) for the raw counts and evidence links.

## Setup

Requirements: macOS or Linux (the local lock uses `fcntl`), [uv](https://docs.astral.sh/uv/getting-started/installation/) and [Ollama](https://ollama.com/download). The initial environment was an Apple M3 Pro Mac with 18 GiB RAM, Python 3.12.13 and Ollama 0.33.2. Windows users should use WSL; native Windows is not supported in v1.

Clone the repository and install the locked environment:

```bash
git clone https://github.com/dharmendrathinks/local-rag-reliability-lab.git
cd local-rag-reliability-lab
uv sync --frozen
```

This installs the locked dependencies in `.venv`. The project pins Python 3.12.13; `uv` can obtain it if needed. Chroma 1.5.9 and HTTPX 0.28.1 are runtime dependencies; pytest 9.1.1 is a development dependency.

Start a separate local-only Ollama server in a terminal and keep it running:

```bash
mkdir -p artifacts/setup
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_NO_CLOUD=1 OLLAMA_NUM_PARALLEL=1 ollama serve 2>&1 | tee artifacts/setup/ollama-server.log
```

Check its startup output for `Ollama cloud disabled: true`. Port 11435 avoids changing an existing Ollama application on port 11434. If 11435 is already occupied by the lab server, reuse that server; do not start another. Changing an environment variable in a client shell does not reconfigure a running server.

In another terminal, download the models (about 3.9 GB combined for the default tags):

```bash
OLLAMA_HOST=127.0.0.1:11435 ollama pull embeddinggemma
OLLAMA_HOST=127.0.0.1:11435 ollama pull gemma3:4b
uv run raglab doctor
```

Downloads require internet access. Inference uses only the local server. The CLI rejects remote endpoints, cloud names and model metadata that delegates to a remote host. Chroma receives explicit local embeddings and has telemetry disabled. Running the server with cloud disabled provides the additional server-side restriction.

`embeddinggemma` requires Ollama 0.11.10 or newer. The runtime reports model digests so a mutable model tag is not mistaken for a permanently pinned weight version. [Official model requirements](https://ollama.com/library/embeddinggemma)

## Run the experiment

```bash
uv run --frozen pytest -q
uv run raglab run-experiment --trials 3 --output artifacts
```

The experiment makes 69 generation requests across three trials. Progress goes to stderr; stdout ends with JSON containing the report and evidence paths. Every run uses new random launch codes and new fixture/index directories. A failed run exits nonzero and still writes its report. Model errors and skipped observations are never converted into successful outcomes.

The runner creates its own temporary workspaces under the new run directory and deletes only its owned `project.txt` fixture. It has no option to run its deletion experiment on a user-supplied source directory. Workspaces are retained for inspection; no automatic cleanup or arbitrary source deletion is performed.

See [EXPERIMENT.md](EXPERIMENT.md) for the fixed questions, stage protocol, metrics and invariants, and [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) for a short screen demonstration.

## Use individual operations

Point ingestion at a dedicated directory of UTF-8 `.txt` files. The index must be outside the source directory. Examples use `demo-sources` and `.lab-index`; create/populate `demo-sources` first.

```bash
uv run raglab ingest --source demo-sources --index .lab-index
uv run raglab ask 'What does the document say?' --index .lab-index
uv run raglab inspect --index .lab-index
uv run raglab sync --source demo-sources --index .lab-index
uv run raglab ask 'What does the document say?' --index .lab-index --no-context
```

- `ingest` imports new/changed documents and replaces obsolete chunks of changed documents. It deliberately retains documents absent from the source scan.
- `ask` retrieves from the persistent snapshot and calls the model. It never silently synchronizes or reads original source text. `--no-context` bypasses index access and still calls the model.
- `inspect` reads records directly without similarity search or Ollama inference. It reports the manifest, source presence, pending operation and record-ID consistency.
- `sync` imports present changes and removes all chunks of absent documents. Deletion-only sync and repeated no-op sync do not require Ollama to be available. Source files themselves are never deleted by `sync`.
- `doctor` records local server and model metadata without generating an answer.

All operations emit JSON. Use `uv run raglab <command> --help` for arguments. Use a new index when changing embedding weights, prefixes or chunking. Common configurable options, placed after the subcommand:

```text
--model gemma3:4b
--embed-model embeddinggemma:latest
--ollama-url http://127.0.0.1:11435
--temperature 0 --seed 42 --num-ctx 4096 --num-predict 256 --top-k 2
--query-prefix 'task: search result | query: '
--document-prefix 'title: none | text: '
```

The defaults use EmbeddingGemma's retrieval prefixes. When intentionally selecting another embedding model, supply that model's documented prefixes, or empty strings if appropriate, and use a separate index. Model substitutions constitute a different experiment configuration.

## Evidence layout

```text
artifacts/<run-id>/
  REPORT.md                 readable counts, invariants and limitations
  run.json                  run configuration, all trials and summary counts
  environment.json          versions, settings, model digests and templates
  trial-1/                  also trial-2 and trial-3
    evaluation/ground_truth.json
    trial.json              incrementally saved operations and observations
    A_no_context.json
    B_ingested.json
    C_source_deleted.json
    E_after_sync.json
    E_restart.json
    work-<random>/          retained temporary workspace, excluded from Git
      owner.json
      sources/              only the two controls remain after completion
      index/
        binding.json        root identity and embedding/chunk configuration
        manifest.json       committed document-to-chunk mapping
        pending.json        exists only while an operation is incomplete
        chroma/             persistent Chroma collection
```

`run.json` and per-stage files include full retrieved text, metadata, distances, supplied context, exact generation requests, raw responses, citations, source-file presence, subprocess IDs and exit codes. Records are read through Chroma's `get` API, independently of retrieved top-k evidence. A valid citation label identifies a supplied chunk; it does not itself establish that the chunk supports the answer.

Evaluation files and traces intentionally retain launch-code evidence outside the searchable source roots. Do not point ingestion at the artifacts directory. No evaluation answer is passed separately into the generation prompt.

New runs record absolute paths and complete retrieved text. The checked-in reference run replaces personal path prefixes with placeholders; see [evidence publication notes](artifacts/README.md). New runs, setup logs, and index workspaces are ignored by Git. Review and sanitize any artifacts before sharing them. A fresh run is the reproducible artifact; copying a saved index to another source root is deliberately rejected by sync's root binding.

## Failure handling and limits

A complete scan must succeed before record mutations. Missing/unreadable/replaced roots, symlinks, failed directory scans and invalid UTF-8 produce errors, not empty source inventories. A genuinely empty, successfully scanned bound source directory is valid. Source renames are delete-plus-add; identity survives content edits but not path changes.

A filesystem lock serializes application operations. Before writing records, the app persists an operation journal. It verifies the resulting records, then atomically commits the manifest and clears the journal. An interrupted operation remains visible through `inspect`; `ask` refuses that index until `sync` rescans and repairs it. Recovery reconciles actual records as well as the manifest, including chunks left behind before a manifest update.

Chroma and the JSON manifest are not one atomic database transaction. Recovery can require embeddings again if an interrupted content update is incomplete. This is a small single-machine CLI, not a continuously synchronized service; do not modify its source tree or Chroma collection concurrently with a sync. It checks scans twice but does not lock external editors.

Claims cover the active index and retrieval path. They do not cover backups, forensic disk erasure or removal from model training. Temperature zero and a fixed seed reduce variation but do not guarantee bit-identical answers across runtime/hardware changes.

## Development

```bash
uv sync --frozen
uv run pytest -q
uv build
```

Lifecycle tests use real persistent Chroma with a deterministic test-only embedding backend. Failure tests inject scan/index/manifest errors and a real process crash. These are separate from the actual Ollama trial traces, and the production CLI cannot select the test backend.

CI runs deterministic tests, the saved-evidence audit, and a package build on Linux and macOS. It does not download models or repeat the Ollama experiment. See [CONTRIBUTING.md](CONTRIBUTING.md) for the contribution workflow.

## Troubleshooting

| Symptom | Next step |
|---|---|
| Connection refused | Keep the dedicated server running on port 11435 and run `uv run raglab doctor`. All model commands must use the same port. |
| Model missing | Run the two `ollama pull` commands above against port 11435. |
| Address already in use | Reuse your existing lab server after checking its settings, or choose another loopback port and pass `--ollama-url` to each CLI command. |
| Out of memory or slow inference | Close other model workloads. The recorded run used 18 GiB RAM; it is not a minimum hardware guarantee. A smaller model requires a separate run and results. |
| Embedding/configuration mismatch | Create a new index for changed weights or prefixes; preserve the old index for inspection. |
| Pending operation | Inspect the index, then run `sync` with the original, available source root to recover. |
| Missing/replaced source root | Restore the bound root or create a new index. Do not treat an inaccessible root as an empty corpus. |
| `fcntl` import error on Windows | Use a Python environment inside WSL. |

## Project and community

This is an educational research CLI for the accompanying YouTube demonstration. Start with [RESULTS.md](RESULTS.md) to read the recorded outcome without installing models, or follow [DEMO_CHECKLIST.md](DEMO_CHECKLIST.md) for a live walkthrough. The project is experimental and maintained on a best-effort basis.

- [Experiment protocol](EXPERIMENT.md) and [implementation design](IMPLEMENTATION_PLAN.md)
- [Contributing](CONTRIBUTING.md), [code of conduct](CODE_OF_CONDUCT.md), and [support](SUPPORT.md)
- [Security and private vulnerability reporting](SECURITY.md)
- [Changelog](CHANGELOG.md) and [citation metadata](CITATION.cff)

## License

Original project code and documentation are available under the [MIT License](LICENSE), copyright 2026 Dharmendra Thinks. Dependencies, model weights, and third-party notices retain their own terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Model weights are downloaded separately and are not included in this repository. Lab commands do not publish anything.
