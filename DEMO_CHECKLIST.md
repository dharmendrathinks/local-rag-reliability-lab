# Screen demonstration checklist

## Before the YouTube launch

- Keep the repository private until you choose to launch. The documentation and CI can be reviewed while it is private.
- Confirm the CI run for the commit shown in the video is green. Record that commit and the experiment run ID in the video description.
- Review what will be visible on screen: terminal paths, tabs, account details, source text, and server logs. Use the fictional fixtures and the sanitized published evidence for recorded examples.
- When ready, change repository visibility in GitHub Settings. Then enable private vulnerability reporting in Settings → Security → Advanced Security and verify the reporting link in SECURITY.md works.
- Link the repository and RESULTS.md in the video description. Add the published video link to README.md once it exists.

## Walkthrough

- Open the current results report. State the observed outcome before choosing a title; successful deletion is a useful result.
- Show `uv run raglab doctor`: local endpoint, model names and digests. Show the server log confirming cloud is disabled.
- Run `uv run raglab run-experiment --trials 3 --output artifacts` and note the report path it prints.
- Open one trial's `evaluation/ground_truth.json`. Explain that it is evaluator-only and outside `work-*/sources`; it is never a separate answer hint in the prompt.
- Show `A_no_context.json`: empty supplied context and the actual answers.
- Show `B_ingested.json`: target record text, source metadata, retrieved chunk and exact request alongside its answer.
- Show `C_source_deleted.json`: target source absent, same retained indexed record after a fresh process, and actual target answers. Call it a **snapshot-import baseline**.
- In `trial.json`, show `operations.D_sync.result`: the deleted document/chunk IDs and before/after counts.
- Show `E_after_sync.json`: direct record inspection, supplied context and model answers. Check the two unrelated controls.
- Show `E_restart.json` and the second-sync operation: persistence across restart, zero additional record operations and unchanged manifest content.
- Run `uv run raglab inspect --index '<index path from trial.json>'` to display the final active index directly.
- Show the aggregate raw counts for all three trials and the separately saved pytest results. Distinguish real Ollama observations from deterministic test doubles.
- Close with the scope: active index/retrieval deletion, not model unlearning or forensic disk erasure. No full video script or predetermined dramatic failure is needed.

The historical stage files are evidence captured during execution; opening them does not restore the earlier index state. Run a new experiment for another live demonstration. The runner deletes only its newly generated target fixture.
