"""Audit captured evidence without making inference requests or changing an index.

Usage: uv run python scripts/audit_evidence.py artifacts/<run-id>
This checks the actual result of this protocol, not an assumed model answer.
"""

import hashlib
import json
import sys
from pathlib import Path

from raglab.experiment import ANSWER_STAGES, QUESTIONS, evaluate, summarize
from raglab.ollama import Settings, generation_request


def audit(directory):
    run = json.loads((directory / "run.json").read_text())
    settings = Settings(**run["environment"]["settings"])
    checks = []
    codes = []
    responses = []

    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})

    check("run completed", run["status"] == "ok")
    check("all planned trials present", len(run["trials"]) == run["planned_trials"])
    check("summary recomputes from raw observations", run["summary"] == summarize(run["trials"], run["planned_trials"]))
    for trial in run["trials"]:
        prefix = f"trial {trial['trial']}: "
        truth = json.loads((directory / f"trial-{trial['trial']}" / "evaluation" / "ground_truth.json").read_text())
        code = truth["launch_code"]
        codes.append(code)
        check(prefix + "lifecycle invariants", bool(trial["invariants"]) and all(trial["invariants"].values()))
        pids = []
        baseline_records = trial["stages"]["B_ingested"]["inspection"]["result"]["records"]
        check(prefix + "code occurs only in target indexed document", all(
            (code in r["text"]) == (r["metadata"]["source_path"] == "project.txt") for r in baseline_records))
        for stage in ANSWER_STAGES:
            data = trial["stages"][stage]
            expected_questions = QUESTIONS[:3] if stage == "A_no_context" else QUESTIONS
            check(prefix + stage + " complete frozen questions", [q["question"] for q in data["questions"]] == expected_questions)
            if stage != "A_no_context":
                pids.append(data["inspection"]["result"]["pid"])
            for item in data["questions"]:
                result = item["call"]["result"]
                label = prefix + stage + "/" + item["question"]["id"]
                pids.append(result["pid"])
                check(label + " fresh stateless request", result["request"] == generation_request(settings, item["question"]["text"], result["context"]))
                check(label + " evaluator recomputes", item["evaluation"] == evaluate(item["question"], result, truth))
                check(label + " exact context assembled from retrieved text", result["context"] == "\n\n".join(
                    f"[{r['citation']}] source={r['metadata']['source_path']} chunk_id={r['id']}\n{r['text']}" for r in result["retrieved"]))
                check(label + " successful untruncated response", result["status"] == "ok" and not result["truncated"])
                check(label + " citation references", all(c["valid_reference"] for c in result["citations"]))
                if stage in ("A_no_context", "E_after_sync", "E_restart"):
                    check(label + " no code in supplied request", code not in json.dumps(result["request"]))
                if stage in ("E_after_sync", "E_restart"):
                    records = data["inspection"]["result"]["records"]
                    check(label + " no code anywhere in active records", code not in json.dumps(records))
                responses.append({"trial": trial["trial"], "stage": stage,
                                  "question_id": item["question"]["id"], "answer": result.get("answer"),
                                  "classification": item["evaluation"]["classification"],
                                  "control_correct": item["evaluation"].get("control_correct")})
        check(prefix + "unique application process IDs", len(pids) == len(set(pids)))
    check("unique independent 128-bit codes", len(codes) == len(set(codes)) and all(len(c) == 32 for c in codes))
    check("all planned generation observations", len(responses) == run["planned_generation_requests"])
    files = sorted(p for p in directory.rglob("*.json") if not any(part.startswith("work-") for part in p.parts))
    return {"status": "ok" if all(c["passed"] for c in checks) else "failed",
            "run_id": run["run_id"], "check_count": len(checks),
            "failed_checks": [c for c in checks if not c["passed"]],
            "checks": checks, "answers_for_review": responses,
            "audited_file_sha256": {str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}


if __name__ == "__main__":
    result = audit(Path(sys.argv[1]))
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "ok" else 1)
