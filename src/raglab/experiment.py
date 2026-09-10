"""Independent fixture trials, public CLI subprocesses, and inspectable evidence.

Ground truth is read only here, never in the retrieval/generation implementation.
"""

import importlib.metadata
import json
import os
import platform
import re
import secrets
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .common import LabError, atomic_json, read_json
from .ollama import Ollama, Settings

QUESTIONS = [
    {"id": "target_1", "kind": "target", "text": "What is Project Lantern’s launch code?", "source": "project.txt"},
    {"id": "target_2", "kind": "target", "text": "Which code authorizes the Project Lantern launch?", "source": "project.txt"},
    {"id": "target_3", "kind": "target", "text": "Tell me the launch authorization code for Project Lantern.", "source": "project.txt"},
    {"id": "returns", "kind": "control", "text": "What is the return window for Lumen Desk purchases?", "source": "returns.txt"},
    {"id": "support", "kind": "control", "text": "On which days and at what times is Lumen Desk support available?", "source": "support.txt"},
]
ANSWER_STAGES = ("A_no_context", "B_ingested", "C_source_deleted", "E_after_sync", "E_restart")


def settings_flags(settings):
    flags = []
    for key, value in settings.to_dict().items():
        flags.extend(["--ollama-url" if key == "url" else "--" + key.replace("_", "-"), str(value)])
    return flags


def invoke(arguments, *, timeout=360):
    command = [sys.executable, "-m", "raglab", *map(str, arguments)]
    start = time.monotonic()
    result = {"command": command, "started_at": datetime.now(timezone.utc).isoformat()}
    try:
        process = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
        result.update(exit_code=process.returncode, stderr=process.stderr)
        try:
            result["result"] = json.loads(process.stdout)
        except ValueError:
            result.update(result={"status": "error", "error": "CLI returned invalid JSON"}, stdout=process.stdout)
    except subprocess.TimeoutExpired as exc:
        result.update(exit_code=None, result={"status": "error", "error": "CLI process timed out"},
                      stdout=(exc.stdout or b"").decode() if isinstance(exc.stdout, bytes) else exc.stdout,
                      stderr=(exc.stderr or b"").decode() if isinstance(exc.stderr, bytes) else exc.stderr)
    result["elapsed_seconds"] = time.monotonic() - start
    return result


def create_trial(directory: Path, number: int, code: str):
    directory.mkdir(parents=True)
    work = Path(tempfile.mkdtemp(prefix="work-", dir=directory))
    source = work / "sources"
    source.mkdir()
    trial_id = str(uuid.uuid4())
    atomic_json(work / "owner.json", {"trial_id": trial_id, "source": str(source), "target": "project.txt"})
    (source / "project.txt").write_text(
        f"Project Lantern is a fictional internal launch rehearsal.\n"
        f"The launch authorization code for Project Lantern is {code}.\n"
        "This code is used only for the fictional rehearsal.\n", encoding="utf-8")
    (source / "returns.txt").write_text(
        "Lumen Desk is a fictional stationery company.\n"
        "The return window for Lumen Desk purchases is 37 days after delivery.\n", encoding="utf-8")
    (source / "support.txt").write_text(
        "Lumen Desk is a fictional stationery company.\n"
        "Lumen Desk support is available Monday through Friday, 09:00 to 17:00 UTC.\n"
        "Support is closed on Saturday and Sunday.\n", encoding="utf-8")
    truth = {"trial_id": trial_id, "launch_code": code, "return_days": 37,
             "support_days": "Monday through Friday", "support_start": "09:00",
             "support_end": "17:00", "support_timezone": "UTC"}
    atomic_json(directory / "evaluation" / "ground_truth.json", truth)
    return {"trial": number, "trial_id": trial_id, "source": str(source),
            "index": str(work / "index"), "work": str(work), "status": "running",
            "stages": {}, "operations": {}, "invariants": {}, "failures": []}


def delete_owned_target(trial):
    work = Path(trial["work"])
    source = Path(trial["source"])
    owner = read_json(work / "owner.json")
    if owner != {"trial_id": trial["trial_id"], "source": str(source), "target": "project.txt"}:
        raise LabError("Fixture ownership check failed; refusing deletion")
    if work.is_symlink() or source.is_symlink() or source.parent != work or source.name != "sources":
        raise LabError("Unsafe fixture directory; refusing deletion")
    target = source / "project.txt"
    if target.is_symlink() or not target.is_file() or target.resolve().parent != source.resolve():
        raise LabError("Target is not the owned regular fixture file; refusing deletion")
    target.unlink()
    if target.exists():
        raise LabError("Fixture deletion failed")
    return {"status": "ok", "deleted_path": str(target), "target_present": False}


def source_presence(source):
    return {name: (Path(source) / name).is_file() for name in ("project.txt", "returns.txt", "support.txt")}


def evaluate(question, result, truth):
    text = result.get("answer") or ""
    retrieved = result.get("retrieved", [])
    evaluation = {
        "retrieval_observed": "retrieved" in result,
        "retrieved_target": any(r["metadata"]["source_path"] == "project.txt" for r in retrieved),
        "retrieved_expected_source": any(r["metadata"]["source_path"] == question["source"] for r in retrieved),
        "exact_code": bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(truth["launch_code"]) + r"(?![A-Za-z0-9])", text)),
        "classification_method": "documented heuristic; inspect raw answer for ambiguous cases",
    }
    if result.get("status") != "ok":
        evaluation["classification"] = "error"
    elif evaluation["exact_code"]:
        evaluation["classification"] = "exact_answer"
    elif re.search(r"\b[0-9A-Fa-f]{16,}\b", text):
        evaluation["classification"] = "guess"
    elif re.search(r"do(?:es)?(?:n[’']t| not) (?:know|contain|provide|include|specify|mention)|don[’']t have|not (?:provided|specified|mentioned|available|included)|cannot (?:determine|answer|provide)|can[’']t (?:determine|answer|provide)|no (?:information|launch|code)", text, re.I):
        evaluation["classification"] = "abstention"
    else:
        evaluation["classification"] = "ambiguous"
    if question["id"] == "returns":
        evaluation["control_correct"] = bool(re.search(r"\b37\s*(?:-|–)?\s*days?\b", text, re.I))
    elif question["id"] == "support":
        low = text.lower()
        evaluation["control_correct"] = all((
            bool(re.search(r"monday|\bmon\b", low)), bool(re.search(r"friday|\bfri\b", low)),
            bool(re.search(r"09:00|\b9(?::00)?\s*(?:a\.?m\.?)", low)),
            bool(re.search(r"17:00|\b5(?::00)?\s*(?:p\.?m\.?)", low)), "utc" in low,
        ))
    return evaluation


def require(operation, label):
    if operation["exit_code"] != 0 or operation["result"].get("status") != "ok":
        raise LabError(f"{label} failed: {operation['result'].get('error', operation['result'])}")
    return operation["result"]


def run_trial(trial, directory, settings):
    source, index = trial["source"], trial["index"]
    truth = read_json(directory / "evaluation" / "ground_truth.json")
    flags = settings_flags(settings)

    def save():
        atomic_json(directory / "trial.json", trial)

    def operation(label, args):
        item = invoke(args)
        trial["operations"][label] = item
        save()
        return require(item, label)

    def stage(name, no_context=False):
        print(f"Trial {trial['trial']}: {name}", file=sys.stderr, flush=True)
        data = {"status": "running", "source_presence": source_presence(source), "questions": []}
        trial["stages"][name] = data
        save()
        if not no_context:
            data["inspection"] = invoke(["inspect", "--index", index])
            save()
            require(data["inspection"], f"{name} inspection")
        else:
            data["inspection"] = {"result": {"status": "not_ingested", "records": [], "record_count": 0}}
        for q in QUESTIONS[:3] if no_context else QUESTIONS:
            args = ["ask", q["text"], "--index", index, *flags]
            if no_context:
                args.append("--no-context")
            call = invoke(args)
            item = {"question": q, "call": call, "evaluation": evaluate(q, call["result"], truth)}
            data["questions"].append(item)
            if call["exit_code"] != 0:
                trial["failures"].append({"stage": name, "question": q["id"], "error": call["result"].get("error")})
            save()
        data["status"] = "ok" if all(q["call"]["exit_code"] == 0 for q in data["questions"]) else "partial"
        atomic_json(directory / f"{name}.json", data)
        save()
        return data

    try:
        stage("A_no_context", True)
        operation("ingest", ["ingest", "--source", source, "--index", index, *flags])
        baseline = stage("B_ingested")
        trial["operations"]["source_deletion"] = delete_owned_target(trial)
        save()
        stale = stage("C_source_deleted")
        operation("D_sync", ["sync", "--source", source, "--index", index, *flags])
        synced = stage("E_after_sync")
        restarted = stage("E_restart")
        second = operation("E_second_sync", ["sync", "--source", source, "--index", index, *flags])
        final = operation("E_final_inspection", ["inspect", "--index", index])
        b = baseline["inspection"]["result"]
        c = stale["inspection"]["result"]
        e = synced["inspection"]["result"]
        r = restarted["inspection"]["result"]
        target_ids = {row["metadata"]["doc_id"] for row in b["records"] if row["metadata"]["source_path"] == "project.txt"}
        controls = [row for row in b["records"] if row["metadata"]["source_path"] != "project.txt"]
        trial["invariants"] = {
            "source_absent_before_sync": not stale["source_presence"]["project.txt"],
            "snapshot_records_survive_source_deletion_and_restart": b["records"] == c["records"],
            "zero_target_records_after_sync": bool(target_ids) and all(row["metadata"]["doc_id"] not in target_ids for row in e["records"]),
            "controls_preserved_exactly": controls == e["records"],
            "restart_records_and_manifest_unchanged": e["records"] == r["records"] and e["manifest"] == r["manifest"],
            "second_sync_no_record_operations": not second["upserted_ids"] and not second["deleted_ids"] and not second["manifest_changed"],
            "second_sync_records_and_manifest_unchanged": r["records"] == final["records"] and r["manifest"] == final["manifest"],
            "final_manifest_consistent": final["manifest_matches_record_ids"] and final["pending"] is None,
            "controls_still_on_disk": all(source_presence(source)[p] for p in ("returns.txt", "support.txt")),
        }
        trial["status"] = "ok" if all(trial["invariants"].values()) and not trial["failures"] else "failed"
    except Exception as exc:
        trial["status"] = "failed"
        trial["failures"].append({"error_type": type(exc).__name__, "error": str(exc)})
    finally:
        for name in ANSWER_STAGES:
            if name not in trial["stages"]:
                trial["stages"][name] = {"status": "skipped", "reason": "Earlier lifecycle operation failed", "questions": []}
            elif trial["stages"][name]["status"] == "running":
                trial["stages"][name]["status"] = "failed"
        save()


def summarize(trials, planned_trials):
    summary = {}
    for name in ANSWER_STAGES:
        questions = [q for trial in trials for q in trial.get("stages", {}).get(name, {}).get("questions", [])]
        target = [q for q in questions if q["question"]["kind"] == "target"]
        controls = [q for q in questions if q["question"]["kind"] == "control"]
        retrievals = [q for q in target if q["evaluation"]["retrieval_observed"]]
        classifications = {}
        for q in target:
            label = q["evaluation"]["classification"]
            classifications[label] = classifications.get(label, 0) + 1
        summary[name] = {
            "target_planned": 3 * planned_trials, "target_attempted": len(target),
            "target_answered": sum(q["call"]["result"].get("status") == "ok" for q in target),
            "exact_code_answers": sum(q["evaluation"]["exact_code"] for q in target),
            "target_retrieval_numerator": sum(q["evaluation"]["retrieved_target"] for q in retrievals),
            "target_retrieval_denominator": len(retrievals) if name != "A_no_context" else 0,
            "target_classifications": classifications,
            "controls_planned": 0 if name == "A_no_context" else 2 * planned_trials,
            "controls_answered": sum(q["call"]["result"].get("status") == "ok" for q in controls),
            "controls_correct": sum(q["evaluation"].get("control_correct", False) for q in controls),
            "controls_retrieved": sum(q["evaluation"]["retrieved_expected_source"] for q in controls),
            "queries_attempted": len(questions),
            "queries_failed": sum(q["call"]["exit_code"] != 0 for q in questions),
            "queries_truncated": sum(q["call"]["result"].get("truncated", False) for q in questions),
        }
    return summary


def render_report(run):
    lines = ["# Local RAG Reliability Lab — observed results", "",
             f"Run: `{run['run_id']}`. Status: **{run['status']}**. Planned independent trials: {run['planned_trials']}.", "",
             "This is a snapshot-import baseline followed by explicit deletion synchronization. "
             "Retained indexed text is an imported copy, not recovery of a deleted disk file or evidence of model training.", "",
             "## Real local-model observations", "",
             "| Stage | Exact code / planned targets | Target answers completed | Target evidence retrieved / retrievals observed | Controls correct / planned | Control evidence retrieved | Failed requests |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for name, row in run["summary"].items():
        retrieved = "N/A (no retrieval)" if name == "A_no_context" else f"{row['target_retrieval_numerator']}/{row['target_retrieval_denominator']}"
        lines.append(f"| {name} | {row['exact_code_answers']}/{row['target_planned']} | {row['target_answered']} | {retrieved} | {row['controls_correct']}/{row['controls_planned']} | {row['controls_retrieved']} | {row['queries_failed']} |")
    lines.extend(["", "Exact-code counts use complete, case-sensitive tokens. Denominators include planned target questions; "
                  "retrieval denominators include only observed retrieval results. Generation failures can still have inspectable retrieval evidence. "
                  "A no-context request does not count as a retrieval. Missing attempts are not successful deletions.", "",
                  "## Direct index and synchronization checks", "",
                  "| Trial | Status | Target records B / C / E / restart | Final control records | Lifecycle invariants |",
                  "|---|---|---|---:|---|"])
    for trial in run["trials"]:
        counts = []
        for name in ANSWER_STAGES[1:]:
            inspection = trial.get("stages", {}).get(name, {}).get("inspection", {}).get("result", {})
            counts.append(str(sum(r["metadata"]["source_path"] == "project.txt" for r in inspection["records"])) if "records" in inspection else "unobserved")
        final = trial.get("operations", {}).get("E_final_inspection", {}).get("result", {})
        controls = sum(r["metadata"]["source_path"] != "project.txt" for r in final.get("records", [])) if "records" in final else "unobserved"
        inv = trial.get("invariants", {})
        lines.append(f"| {trial['trial']} | {trial['status']} | {' / '.join(counts)} | {controls} | {sum(inv.values())}/{len(inv)} |")
    lines.extend(["", "## Environment and settings", "", "```json", json.dumps(run["environment"], indent=2), "```", "",
                  "Model digests, model metadata/templates, and full settings are in `environment.json`. Exact requests and raw responses "
                  "are in each trial's stage JSON and `trial.json`. Evaluation ground truth is outside every source root.", "",
                  "## Failures and limitations", ""])
    failures = list(run.get("failures", []))
    for trial in run["trials"]:
        failures.extend({"trial": trial["trial"], **f} for f in trial.get("failures", []))
        failures.extend({"trial": trial["trial"], "failed_invariant": k} for k, v in trial.get("invariants", {}).items() if not v)
    if failures:
        lines.extend(["```json", json.dumps(failures, indent=2), "```"])
    else:
        lines.append("No execution failures or lifecycle invariant failures were observed in this run.")
    lines.extend(["", "Target answer classifications (heuristic labels; review raw text):", ""])
    for name, row in run["summary"].items():
        lines.append(f"- {name}: `{json.dumps(row['target_classifications'], sort_keys=True)}`; truncated responses: {row['queries_truncated']}.")
    lines.extend(["", "- Three tiny fictional documents and three trials do not establish statistical certainty or broad RAG quality.",
                  "- Top-k is 2 with no relevance threshold. Irrelevant control chunks may be supplied after target removal; inspect the exact context.",
                  "- An unsupported generated answer is separate from stale retrieval. Missing or invalid citations remain visible; valid citation labels alone do not prove entailment.",
                  "- Automatic abstention/control-answer labels are conservative text heuristics, not a semantic judge. Raw answers are the primary evidence.",
                  "- Temperature zero and a fixed seed do not guarantee identical output on other runtimes or hardware.",
                  "- Claims cover active indexed records and the application retrieval path, not backups, training-data removal, or forensic disk erasure.",
                  "- Ground truth and trace artifacts intentionally retain evidence outside the searchable corpus.",
                  "- Source scans are checked twice; this CLI assumes files are not edited concurrently during index writes.", "",
                  "## Deterministic tests", "",
                  "Lifecycle tests use real persistent Chroma and deterministic fake embeddings, with injected failures where needed. "
                  "They are separate from these Ollama observations. See the separately saved pytest results; this report does not claim tests were run merely because a model trial completed.", "",
                  "## Reproduce", "", "```bash", "uv sync --frozen", "uv run raglab run-experiment --trials 3 --output artifacts", "```", "",
                  "Start the local-only Ollama server and install the configured models first, as described in README.md.", ""])
    return "\n".join(lines)


def run_experiment(output: Path, trials: int, settings: Settings):
    output = output.absolute()
    output.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(4)
    directory = output / run_id
    directory.mkdir()
    environment = {"python": sys.version, "platform": platform.platform(), "machine": platform.machine(),
                   "dependencies": {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()},
                   "settings": settings.to_dict(), "application_answer_cache": False,
                   "generation_history": False, "inference_endpoint": settings.url}
    run = {"schema_version": 1, "run_id": run_id, "status": "running", "planned_trials": trials,
           "planned_generation_requests": 23 * trials, "environment": environment,
           "questions": QUESTIONS, "trials": [], "failures": []}
    def checkpoint():
        run["summary"] = summarize(run["trials"], trials)
        atomic_json(directory / "run.json", run)
        (directory / "REPORT.md").write_text(render_report(run), encoding="utf-8")
    checkpoint()
    try:
        inventory = Ollama(settings).inventory()
        atomic_json(directory / "environment.json", {**environment, "ollama": inventory})
        codes = set()
        for number in range(1, trials + 1):
            code = secrets.token_hex(16).upper()
            while code in codes:
                code = secrets.token_hex(16).upper()
            codes.add(code)
            trial_dir = directory / f"trial-{number}"
            trial = create_trial(trial_dir, number, code)
            run["trials"].append(trial)
            checkpoint()
            run_trial(trial, trial_dir, settings)
            checkpoint()
        run["status"] = "ok" if all(t["status"] == "ok" for t in run["trials"]) else "failed"
    except Exception as exc:
        run["status"] = "blocked" if not run["trials"] else "failed"
        run["failures"].append({"error_type": type(exc).__name__, "error": str(exc)})
        if not (directory / "environment.json").exists():
            atomic_json(directory / "environment.json", {**environment, "preflight_error": str(exc)})
    finally:
        checkpoint()
    return {"status": run["status"], "run_id": run_id, "report": str(directory / "REPORT.md"),
            "evidence": str(directory / "run.json"), "summary": run["summary"]}
