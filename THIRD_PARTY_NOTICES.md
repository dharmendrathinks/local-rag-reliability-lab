# Third-party software and models

The [MIT License](LICENSE) applies to this project's original code and documentation. It does not replace the terms of dependencies, model weights, or third-party material recorded in model metadata.

| Component | Role | Upstream terms |
|---|---|---|
| Chroma | Persistent local vector store | [Apache-2.0](https://github.com/chroma-core/chroma/blob/main/LICENSE) |
| HTTPX | Local HTTP client | [BSD-3-Clause](https://github.com/encode/httpx/blob/master/LICENSE.md) |
| pytest | Development tests | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| Hatchling | Package build backend | [MIT](https://github.com/pypa/hatch/blob/master/LICENSE.txt) |
| uv | Environment and dependency tooling, installed separately | [MIT or Apache-2.0](https://github.com/astral-sh/uv#license) |
| Ollama | Inference runtime, installed separately | [MIT](https://github.com/ollama/ollama/blob/main/LICENSE) |
| EmbeddingGemma and Gemma 3 | Default embedding and generation weights, downloaded separately | [Gemma Terms of Use](https://ai.google.dev/gemma/terms) and [Prohibited Use Policy](https://ai.google.dev/gemma/prohibited_use_policy) |

`uv.lock` records the Python dependency graph, including transitive dependencies. Their distributions contain their own license notices; this table is a guide to direct components, not an exhaustive dependency inventory. No dependency source or model weights are vendored here.

The reference evidence includes model metadata, prompt templates, and license text returned by Ollama. Those third-party notices remain under their original terms. The recorded metadata is a historical snapshot; consult the linked upstream terms for the models you download. The repository's MIT license does not relicense Gemma weights.

This is an independent educational project and is not endorsed by Google, Ollama, Chroma, or other upstream projects.
