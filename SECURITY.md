# Security policy

## Scope and supported versions

Security fixes are made on `main`; older snapshots have no guaranteed backports. This is an experimental, single-machine CLI with no authentication, hosted service, or production security guarantee.

The CLI restricts inference to a loopback Ollama endpoint, disables environment proxies and redirects, and supplies local embeddings to Chroma with telemetry disabled. Keep Ollama bound to loopback and enable `OLLAMA_NO_CLOUD=1` in the server process as documented in the [setup](README.md#setup).

Source documents are untrusted model input. Prompt instructions do not guarantee resistance to prompt injection or factual correctness. Indexes and artifacts store document text in plaintext; local inference does not make those files safe to publish. Active-index deletion does not erase saved traces, backups, model training data, or forensic disk remnants.

## Reporting a vulnerability

Use GitHub's private **Report a vulnerability** action on the repository's [Security page](https://github.com/dharmendrathinks/local-rag-reliability-lab/security/advisories/new). Do not post exploit details, sensitive documents, credentials, or affected private paths in a public issue.

Include the affected commit, operating system and dependency versions, a minimal reproduction using fictional data, the impact, and any suggested fix. Reports are handled on a best-effort basis; there is no guaranteed response time or bug bounty. If the private reporting form is unavailable, open a public issue requesting a private contact channel without disclosing the vulnerability.

For ordinary bugs and setup questions, use [SUPPORT.md](SUPPORT.md).
