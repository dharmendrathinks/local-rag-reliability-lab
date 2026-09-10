# Experiment protocol

## Question and interpretation

When a source document is deleted, does information from it remain available through this local RAG application's active index and retrieval path?

Track four layers independently: source presence, indexed records, retrieved/supplied evidence, and generated answers. A one-time importer stores a snapshot. Retention before explicit synchronization is a snapshot-import baseline, not automatically a Chroma bug, a model bug, or recovery of a deleted disk file.

## Frozen inputs

Each of three independent trials creates these fictional UTF-8 documents in a new program-owned temporary directory:

| Source | Fact | Purpose |
|---|---|---|
| project.txt | Project Lantern launch code: a fresh 128-bit random value, rendered as 32 uppercase hexadecimal characters | Target |
| returns.txt | Lumen Desk return window: 37 days after delivery | Unrelated control |
| support.txt | Lumen Desk support: Monday–Friday, 09:00–17:00 UTC; closed weekends | Unrelated control |

The code is initially written only to the target source and separate evaluation ground truth. The fixture name, questions and model configuration do not encode it. The model receives it only if retrieval supplies the imported target text. Ground truth is used by the evaluator after inference. Ground truth, traces and reports are outside every searchable corpus.

Target questions, unchanged across stages:

1. What is Project Lantern’s launch code?
2. Which code authorizes the Project Lantern launch?
3. Tell me the launch authorization code for Project Lantern.

Control questions:

1. What is the return window for Lumen Desk purchases?
2. On which days and at what times is Lumen Desk support available?

Defaults: `embeddinggemma:latest`, `gemma3:4b`, cosine top-k 2 without a distance threshold; 800-character chunks with 100-character overlap; temperature 0, seed 42, context 4096 and maximum output 256 tokens. Embedding requests include retrieval query/document prefixes and `truncate=false`. Tiny fixtures each fit in one chunk; multi-chunk lifecycle behavior is tested separately.

The fixed system prompt requests answers based only on supplied context, source citations and uncertainty when the context lacks an answer. The user prompt contains `CONTEXT`, `QUESTION`, and `ANSWER` delimiters. No stage label, expected answer, previous response, conversation context or filesystem tool is supplied to the model. No application answer cache exists. Empty-context requests still invoke generation.

## Stages

| Stage | Actions | Required evidence |
|---|---|---|
| A_no_context | Before ingestion, ask three target questions with empty context | Exact request, answer and classification; no index or retrieval |
| B_ingested | Ingest all three documents; inspect and ask five questions | Source presence; record text/IDs/metadata; target retrieval and answer baseline; controls |
| C_source_deleted | Delete only the owned target source; start fresh application processes on the same index; inspect and ask five questions | Target source absent; snapshot record comparison; retrieved text and exact supplied context |
| D_sync | Reconcile present documents against manifest and actual records | Deleted chunk/document IDs, before/after counts, successful manifest commit |
| E_after_sync | Inspect and ask five questions | Zero target records directly; target retrieval/answers; unrelated controls |
| E_restart | Reopen in new processes; inspect and ask the same five questions | Persistence of index deletion and control availability |
| E_second_sync | Sync again and inspect in a new process | Zero record operations; unchanged records and manifest content |

Each public CLI invocation is a fresh OS process, including each question. Process IDs, commands, exit codes and durations are recorded. The persistent local Ollama server may reuse loaded model weights/runtime prefix computation, but no previous conversation or response state is sent. Application restart is distinct from restarting Ollama; the experiment makes no assertion about forensic runtime-memory erasure.

Per trial: 3 questions in A, then 5 in B/C/E/restart = 23 generation requests. Three trials = 69 planned requests. The second sync adds no generation requests.

## Invariants and measurements

Deterministic lifecycle invariants:

- Source absence is verified before the C questions.
- B and C have identical active stored records across process restarts.
- After successful sync, no active records have the deleted document's stable ID.
- Unrelated records retain identical IDs, text and metadata.
- Restart retains the post-sync records and manifest.
- A second sync upserts/deletes zero records and leaves manifest content unchanged.
- The committed manifest agrees with stored record IDs and no pending operation remains.
- Both control source files remain on disk.

Real-model measurements, reported separately:

- Exact-code occurrences in answers, using a complete case-sensitive token match, with raw counts out of the nine planned target questions per stage.
- Queries retrieving target-document chunks: numerator is target queries whose returned evidence contains a target record; denominator is target queries with recorded retrieval results. A has no retrieval denominator. Failed generation still contributes to retrieval counts if retrieval succeeded. Missing retrieval results never count as zero leakage observations.
- Planned, attempted, completed, failed and truncated query counts are retained in JSON.
- Controls: retrieval of the expected source and correctness of the answer are independent checks. Return answers require 37 days; support answers require the days, start, end and UTC. Text heuristics allow 12/24-hour formatting; raw answers remain authoritative.
- Automatic target classification: exact answer first, then a long hexadecimal guess, explicit uncertainty/absence language, otherwise ambiguous. Review raw answers before calling an ambiguous output a guess or abstention. There is no LLM judge and no answer-repair step.
- Citation labels are parsed and checked against supplied chunks. A syntactically valid citation is not a claim of semantic support. Invalid/missing citations and citations attached to abstentions are visible in traces.

Do not infer index deletion from an abstaining answer, or index retention from an invented answer. If evidence is gone and a model invents a code, report unsupported generation separately. Exact-code occurrences are measurements, not an assumption that every answer containing the code asserts it correctly; review the raw response.

## Errors, recovery and scope

Never choose a replacement trial because its result is more dramatic. Preserve failures and incomplete stages; reruns get a new run ID. Stop a trial's dependent lifecycle stages after a failed critical operation, while allowing independent trials to proceed. Generation failures remain individual observations and do not erase retrieval evidence.

The importer binds a canonical source root and filesystem identity. All `.txt` files must be readable UTF-8; enumeration errors, symlinks, missing roots and changed snapshots abort reconciliation. A valid empty bound directory can remove all of its documents using per-document deletion; the collection is never cleared as a shortcut.

A write-ahead operation journal and atomic manifest replacement make partial operations recoverable. A pending journal blocks answering until sync succeeds. Recovery uses actual Chroma records as well as manifest state, so chunks created before an interrupted manifest update are not lost from the reconciliation inventory. Tests exercise both multi-chunk deletion and changed-document crashes.

Source files must remain stable during index writes. This protocol is not an externally coordinated filesystem snapshot or a multiwriter database service. The corpus is tiny, top-k is 2, the sample is small, and model tags/runtime versions may change. Report counts without statistical-certainty claims.

Claims cover active indexed records and retrieval only. Evaluation artifacts deliberately preserve evidence. Backups, disk forensics, runtime-memory forensics and training-data removal are outside scope.

## Official API references

- [Ollama embeddings](https://docs.ollama.com/api/embed) and [generation](https://docs.ollama.com/api/generate).
- [Ollama local-only server configuration](https://docs.ollama.com/faq).
- [EmbeddingGemma retrieval prefixes](https://ai.google.dev/gemma/docs/embeddinggemma/inference-embeddinggemma-with-sentence-transformers).
- [Chroma persistent clients](https://docs.trychroma.com/docs/run-chroma/clients), [upsert](https://docs.trychroma.com/docs/collections/update-data), [filtered deletion](https://docs.trychroma.com/docs/collections/delete-data), and [direct get versus similarity query](https://docs.trychroma.com/docs/querying-collections/query-and-get).

These APIs were checked against the official documentation during implementation. Actual installed package versions and model metadata are recorded with the run.
