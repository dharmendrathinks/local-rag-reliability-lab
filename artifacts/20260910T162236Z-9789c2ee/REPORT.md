# Local RAG Reliability Lab — observed results

Run: `20260910T162236Z-9789c2ee`. Status: **ok**. Planned independent trials: 3.

This is a snapshot-import baseline followed by explicit deletion synchronization. Retained indexed text is an imported copy, not recovery of a deleted disk file or evidence of model training.

## Real local-model observations

| Stage | Exact code / planned targets | Target answers completed | Target evidence retrieved / retrievals observed | Controls correct / planned | Control evidence retrieved | Failed requests |
|---|---:|---:|---:|---:|---:|---:|
| A_no_context | 0/9 | 9 | N/A (no retrieval) | 0/0 | 0 | 0 |
| B_ingested | 9/9 | 9 | 9/9 | 6/6 | 6 | 0 |
| C_source_deleted | 9/9 | 9 | 9/9 | 6/6 | 6 | 0 |
| E_after_sync | 0/9 | 9 | 0/9 | 6/6 | 6 | 0 |
| E_restart | 0/9 | 9 | 0/9 | 6/6 | 6 | 0 |

Exact-code counts use complete, case-sensitive tokens. Denominators include planned target questions; retrieval denominators include only observed retrieval results. Generation failures can still have inspectable retrieval evidence. A no-context request does not count as a retrieval. Missing attempts are not successful deletions.

## Direct index and synchronization checks

| Trial | Status | Target records B / C / E / restart | Final control records | Lifecycle invariants |
|---|---|---|---:|---|
| 1 | ok | 1 / 1 / 0 / 0 | 2 | 9/9 |
| 2 | ok | 1 / 1 / 0 / 0 | 2 | 9/9 |
| 3 | ok | 1 / 1 / 0 / 0 | 2 | 9/9 |

## Environment and settings

```json
{
  "python": "3.12.13 (main, Jul 18 2026, 16:55:18) [Clang 22.1.3 ]",
  "platform": "macOS-26.5.2-arm64-arm-64bit",
  "machine": "arm64",
  "dependencies": {
    "shellingham": "1.5.4",
    "numpy": "2.5.3",
    "multidict": "6.8.0",
    "oauthlib": "3.3.1",
    "rpds-py": "2026.6.3",
    "filelock": "3.32.6",
    "durationpy": "0.11",
    "click": "8.5.0",
    "packaging": "26.3",
    "importlib_resources": "7.1.0",
    "opentelemetry-exporter-otlp-proto-common": "1.44.0",
    "iniconfig": "2.3.0",
    "charset-normalizer": "3.5.1",
    "overrides": "7.7.0",
    "Pygments": "2.21.0",
    "jsonschema-specifications": "2025.9.1",
    "requests": "2.34.2",
    "grpcio": "1.83.1",
    "hf-xet": "1.6.0",
    "rich": "15.0.0",
    "PyPika": "0.51.1",
    "huggingface_hub": "1.31.0",
    "jsonschema": "4.26.0",
    "propcache": "0.5.2",
    "pydantic_core": "2.46.5",
    "yarl": "1.24.5",
    "chromadb": "1.5.9",
    "pybase64": "1.5.0",
    "tokenizers": "0.23.2",
    "build": "1.6.1",
    "tenacity": "9.1.4",
    "httpcore": "1.0.9",
    "aiohappyeyeballs": "2.7.1",
    "local-rag-reliability-lab": "0.1.0",
    "fsspec": "2026.7.0",
    "opentelemetry-exporter-otlp-proto-grpc": "1.44.0",
    "opentelemetry-semantic-conventions": "0.65b0",
    "pytest": "9.1.1",
    "httptools": "0.8.0",
    "h11": "0.16.0",
    "pydantic": "2.13.5",
    "pydantic-settings": "2.15.0",
    "mdurl": "0.1.2",
    "python-dateutil": "2.9.0.post0",
    "PyYAML": "6.0.3",
    "kubernetes": "36.0.3",
    "onnxruntime": "1.29.0",
    "idna": "3.19",
    "frozenlist": "1.8.0",
    "bcrypt": "5.0.0",
    "aiosignal": "1.4.0",
    "certifi": "2026.7.22",
    "googleapis-common-protos": "1.75.3",
    "watchfiles": "1.2.0",
    "opentelemetry-api": "1.44.0",
    "annotated-types": "0.8.0",
    "referencing": "0.37.0",
    "markdown-it-py": "4.2.0",
    "opentelemetry-proto": "1.44.0",
    "annotated-doc": "0.0.5",
    "typing-inspection": "0.4.4",
    "tqdm": "4.70.0",
    "flatbuffers": "25.12.19",
    "pluggy": "1.6.0",
    "attrs": "26.1.0",
    "python-dotenv": "1.2.3",
    "websocket-client": "1.9.2",
    "websockets": "17.1",
    "urllib3": "2.7.0",
    "httpx": "0.28.1",
    "typing_extensions": "4.16.0",
    "mmh3": "5.3.0",
    "uvloop": "0.22.1",
    "aiohttp": "3.14.3",
    "pyproject_hooks": "1.2.0",
    "typer": "0.27.2",
    "uvicorn": "0.52.4",
    "protobuf": "7.36.1",
    "anyio": "4.15.1",
    "orjson": "3.12.0",
    "six": "1.17.0",
    "requests-oauthlib": "2.0.0",
    "opentelemetry-sdk": "1.44.0"
  },
  "settings": {
    "url": "http://127.0.0.1:11435",
    "embed_model": "embeddinggemma:latest",
    "model": "gemma3:4b",
    "temperature": 0.0,
    "seed": 42,
    "num_ctx": 4096,
    "num_predict": 256,
    "top_k": 2,
    "query_prefix": "task: search result | query: ",
    "document_prefix": "title: none | text: "
  },
  "application_answer_cache": false,
  "generation_history": false,
  "inference_endpoint": "http://127.0.0.1:11435"
}
```

Model digests, model metadata/templates, and full settings are in `environment.json`. Exact requests and raw responses are in each trial's stage JSON and `trial.json`. Evaluation ground truth is outside every source root.

## Failures and limitations

No execution failures or lifecycle invariant failures were observed in this run.

Target answer classifications (heuristic labels; review raw text):

- A_no_context: `{"abstention": 9}`; truncated responses: 0.
- B_ingested: `{"exact_answer": 9}`; truncated responses: 0.
- C_source_deleted: `{"exact_answer": 9}`; truncated responses: 0.
- E_after_sync: `{"abstention": 9}`; truncated responses: 0.
- E_restart: `{"abstention": 9}`; truncated responses: 0.

- Three tiny fictional documents and three trials do not establish statistical certainty or broad RAG quality.
- Top-k is 2 with no relevance threshold. Irrelevant control chunks may be supplied after target removal; inspect the exact context.
- An unsupported generated answer is separate from stale retrieval. Missing or invalid citations remain visible; valid citation labels alone do not prove entailment.
- Automatic abstention/control-answer labels are conservative text heuristics, not a semantic judge. Raw answers are the primary evidence.
- Temperature zero and a fixed seed do not guarantee identical output on other runtimes or hardware.
- Claims cover active indexed records and the application retrieval path, not backups, training-data removal, or forensic disk erasure.
- Ground truth and trace artifacts intentionally retain evidence outside the searchable corpus.
- Source scans are checked twice; this CLI assumes files are not edited concurrently during index writes.

## Deterministic tests

Lifecycle tests use real persistent Chroma and deterministic fake embeddings, with injected failures where needed. They are separate from these Ollama observations. See the separately saved pytest results; this report does not claim tests were run merely because a model trial completed.

## Reproduce

```bash
uv sync --frozen
uv run raglab run-experiment --trials 3 --output artifacts
```

Start the local-only Ollama server and install the configured models first, as described in README.md.
