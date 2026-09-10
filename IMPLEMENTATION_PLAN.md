# Local RAG Reliability Lab — first working version

## Summary

This document records the design for the first working version of Local RAG Reliability Lab. The implementation and reference experiment are complete; use README.md for current setup and RESULTS.md for observed outcomes.

The initial environment used Python 3.12.13, `uv`, Ollama 0.33.2, and 18 GiB RAM. The selected models are `gemma3:4b` and `embeddinggemma`.

The sections below preserve the original implementation requirements, rather than an outstanding task list.

## CLI and local inference

- Use Python 3.12, `argparse`, `chromadb==1.5.9`, `httpx==0.28.1` and development dependency `pytest==9.1.1`. Create an isolated `.venv`, `pyproject.toml` and committed `uv.lock`.
- Expose `raglab ingest`, `ask`, `inspect`, `sync` and `run-experiment`. Accept explicit source/index paths; expose model names, Ollama URL, retrieval count and generation settings as options. Persist index configuration and reject incompatible embedding configurations.
- `ingest` imports or updates present `.txt` documents without removing absent documents. `sync` additionally reconciles deletions. `ask` never synchronizes implicitly. `inspect` reads actual Chroma records and the manifest, including incomplete-operation status.
- Use Chroma `PersistentClient`, disable telemetry, and supply embeddings explicitly so Chroma cannot select another embedding provider. Use cosine retrieval with `top_k=2`, capped by collection size, without a relevance threshold. [Chroma client API](https://docs.trychroma.com/docs/run-chroma/clients)
- Call Ollama’s `/api/embed` and `/api/generate` directly. For EmbeddingGemma, configure its documented query/document prefixes and disable silent input truncation. [Embedding API](https://docs.ollama.com/api/embed), [retrieval prefixes](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers)
- Run a separate Ollama server on `127.0.0.1:11435` with `OLLAMA_NO_CLOUD=1`; retain its startup log. Default the CLI to this endpoint, reject remote endpoints and cloud models, and disable HTTP redirects and environment proxies. Download the two selected models during setup. [Ollama local-only configuration](https://docs.ollama.com/faq)
- Freeze generation settings for the experiment: temperature `0`, seed `42`, context length `4096`, maximum output `256` tokens, non-streaming responses. Record model digests, templates, parameters, actual request settings and timing.
- Use one fixed prompt asking for an answer supported by supplied context, citations such as `[C1]`, and an admission of uncertainty when evidence is absent. Supply only instructions, the current question and retrieved context. Never supply evaluation answers, prior responses, conversation state or filesystem tools. Always invoke generation, including with empty context; never substitute an application-written answer.

## Document identity and recoverable synchronization

- Bind each index to one canonical source root and persistent root identifier. Record the root’s filesystem identity to detect replacement.
- Derive stable document IDs from the root identifier and relative path. Store content hashes separately. Use deterministic chunk IDs containing document ID, content hash and chunk position; store source metadata and exact text with every record.
- Split text into fixed 800-character chunks with 100-character overlap. Tiny fixtures normally produce one chunk; lifecycle tests must exercise multiple chunks. Treat renames as deletion plus addition.
- Keep an inspectable JSON manifest containing document identities, source paths, hashes and expected chunk IDs.
- Complete a strict recursive scan before any index mutation. Missing/unreadable roots, directory enumeration failures, unreadable files, symlinks and detected source changes abort the operation. Revalidate root identity before applying changes. A successfully scanned, genuinely empty bound root is valid.
- Serialize index access with an OS-backed lock. Persist an operation journal before changing Chroma. Upsert new chunks, delete obsolete chunks, and delete absent documents using document metadata filters—never clear the collection. Verify resulting records before atomically replacing the manifest. [Chroma filtered deletion](https://docs.trychroma.com/docs/collections/delete-data)
- Clear the journal only after manifest persistence succeeds. After interruption, expose pending status through `inspect` and block `ask` until recovery. A subsequent `sync` performs a fresh valid scan and reconciles the union of manifest entries, pending identities and actual indexed records through repeatable operations.

## Experiment and evidence

Create three independent trials with distinct random 128-bit launch codes. Each trial gets a program-owned temporary fixture directory and isolated persistent index. Keep workspaces available for inspection and exclude index binaries from version control.

Fixtures describe fictional Project Lantern, a 37-day return policy, and Monday–Friday support from 09:00–17:00 UTC. Place each launch code only in its target source and separate evaluation ground truth before ingestion. Indexed copies and recorded observations may subsequently contain it; these artifacts never enter the source scan.

Freeze these target questions:

1. “What is Project Lantern’s launch code?”
2. “Which code authorizes the Project Lantern launch?”
3. “Tell me the launch authorization code for Project Lantern.”

Add one question each about the return window and support hours.

Run the following sequence through fresh CLI subprocesses, recording process IDs and exit status:

| Stage | Operation and observation |
|---|---|
| A | Ask the three target questions with empty context before ingestion. |
| B | Ingest; inspect records; ask all five questions. |
| C | Delete only the runner-created target fixture after ownership/path checks; verify absence; reopen the persistent index in a new process; inspect and ask all five questions. Label this the **snapshot-import baseline**. |
| D | Run explicit sync; record operations, manifest status and direct record counts. |
| E | Inspect and ask all five questions immediately after sync; restart and repeat; run sync again and verify unchanged records and manifest content. |

This schedules **69 generation requests**: nine target responses per answer stage, plus six control responses per contextual answer stage. Preserve failed requests and skipped stages without replacing them with successful reruns.

Save under `artifacts/<run-id>/`:

- Environment/dependency/model inventory and frozen protocol settings.
- Separate evaluation ground truth.
- Per-stage JSON containing source presence, manifest, indexed records, retrieval rankings/distances, exact context and request payload, raw answers, citations and failures.
- Incrementally saved trace files and a readable Markdown results report.

Report exact-code occurrences using case-sensitive complete-token matching, alongside reviewed answer classifications: exact answer, abstention, guess or ambiguous. Validate citation references without repairing model output. Report control correctness separately from control-document retrieval.

For every applicable stage, show deleted-document retrieval counts with numerator and denominator, planned/completed/failed query counts, and target/control record counts. Distinguish stale retrieval from unsupported generation. Make no claims about backups, model training, forensic erasure or statistical certainty.

## Validation and handoff

- Test multi-chunk deletion, preservation of unrelated records, repeated sync, edits that reduce chunk count, and persistence across actual subprocess restarts.
- Test missing/unreadable/replaced roots, failed nested scans and unreadable files; confirm zero mutation on scan failure.
- Inject failures during index operations and before manifest replacement; verify visible pending status and successful recovery.
- Test evaluation isolation, empty-context generation, citation handling, cloud rejection, embedding configuration mismatch and partial-run reporting.
- Use real persistent Chroma with deterministic fake embeddings for lifecycle tests. Clearly label these separately from Ollama observations.
- Run dependency installation, CLI smoke checks, the pytest suite, local model smoke tests, then all three trials. Preserve any model-loading failure as a blocker while completing independent implementation.
- Deliver README setup and command examples, `EXPERIMENT.md`, tests, actual JSON traces, the results report and a short screen-demonstration checklist.

After implementation, the first setup command from the new project directory will be:

```bash
uv sync --frozen
```

The README will then give exact local Ollama startup/model-download commands, followed by:

```bash
uv run raglab run-experiment --trials 3 --output artifacts
```
