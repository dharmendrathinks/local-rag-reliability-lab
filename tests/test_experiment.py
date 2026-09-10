import json

import pytest

from raglab.common import LabError
from raglab.experiment import QUESTIONS, create_trial, delete_owned_target, evaluate, run_experiment, summarize
from raglab.ollama import Ollama, Settings, generation_request
from raglab.store import Store, scan
from tests.helpers import FakeBackend


@pytest.mark.parametrize("url", ["https://ollama.com", "http://192.168.1.5:11434", "http://localhost@evil.example", "http://localhost:11434/proxy"])
def test_reject_remote_or_ambiguous_endpoints(url):
    with pytest.raises(LabError, match="loopback"):
        Settings(url=url)


@pytest.mark.parametrize("name", ["gpt-oss:120b-cloud", "remote/model", ""])
def test_reject_cloud_model_names(name):
    with pytest.raises(LabError, match="local"):
        Settings(model=name)


def test_reject_remote_alias_even_when_name_looks_local(monkeypatch):
    backend = Ollama(Settings())
    def response(method, endpoint, payload=None):
        if endpoint == "/api/tags":
            return {"models": [{"name": "gemma3:4b", "size": 1000, "digest": "fake"}]}
        return {"remote_host": "https://ollama.com", "remote_model": "other", "model_info": {"parameters": 100}}
    monkeypatch.setattr(backend, "request", response)
    with pytest.raises(LabError, match="remote host"):
        backend.model_info("gemma3:4b")


def test_fixture_ground_truth_is_outside_searchable_corpus(tmp_path):
    code = "A13B" * 8
    directory = tmp_path / "trial"
    trial = create_trial(directory, 1, code)
    files = scan(__import__('pathlib').Path(trial["source"]))["documents"]
    assert set(files) == {"project.txt", "returns.txt", "support.txt"}
    assert sum(code in doc["text"] for doc in files.values()) == 1
    assert code not in json.dumps(QUESTIONS)
    backend = FakeBackend()
    no_context = Store(trial["index"]).ask(QUESTIONS[0]["text"], backend, no_context=True)
    assert code not in json.dumps(no_context["request"])
    assert "ground_truth" not in json.dumps(no_context["request"])
    Store(trial["index"]).reconcile(trial["source"], backend, delete_missing=False)
    records = Store(trial["index"]).inspect()["records"]
    assert len(records) == 3
    assert {r["metadata"]["source_path"] for r in records} == set(files)


def test_deletion_helper_refuses_symlink_and_preserves_external_file(tmp_path):
    directory = tmp_path / "trial"
    trial = create_trial(directory, 1, "A" * 32)
    from pathlib import Path
    outside = tmp_path / "external.txt"
    outside.write_text("Keep this.")
    target = Path(trial["source"]) / "project.txt"
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(LabError, match="owned regular"):
        delete_owned_target(trial)
    assert outside.read_text() == "Keep this."


def test_same_prompt_template_for_all_comparable_stages():
    settings = Settings()
    q = QUESTIONS[0]["text"]
    a = generation_request(settings, q, "")
    b = generation_request(settings, q, "Some retrieved evidence.")
    assert a["system"] == b["system"] and a["options"] == b["options"]
    assert set(a) == {"model", "system", "prompt", "stream", "options", "keep_alive"}
    assert "context" not in a and "messages" not in a and "tools" not in a


def test_exact_match_is_not_a_substring_or_case_fold():
    truth = {"launch_code": "ABCD0123"}
    def score(answer):
        return evaluate(QUESTIONS[0], {"status": "ok", "answer": answer, "retrieved": []}, truth)
    assert score("The code is ABCD0123.")["exact_code"]
    assert not score("XABCD0123Y")["exact_code"]
    assert not score("abcd0123")["exact_code"]


def test_failed_preflight_writes_visible_report_with_planned_denominators(tmp_path, monkeypatch):
    def fail(self):
        raise LabError("injected missing model")
    monkeypatch.setattr(Ollama, "inventory", fail)
    result = run_experiment(tmp_path, 3, Settings())
    assert result["status"] == "blocked"
    from pathlib import Path
    run = json.loads(Path(result["evidence"]).read_text())
    assert run["planned_generation_requests"] == 69
    assert run["trials"] == []
    for stage in run["summary"].values():
        assert stage["target_planned"] == 9
        assert stage["target_answered"] == 0
        assert stage["target_retrieval_denominator"] == 0
    assert "injected missing model" in Path(result["report"]).read_text()


def test_generation_error_does_not_hide_successful_retrieval():
    question = QUESTIONS[0]
    result = {"status": "error", "answer": None, "retrieved": [{"metadata": {"source_path": "project.txt"}}]}
    item = {"question": question, "call": {"exit_code": 1, "result": result}, "evaluation": evaluate(question, result, {"launch_code": "ABC"})}
    summary = summarize([{"stages": {"C_source_deleted": {"questions": [item]}}}], 3)["C_source_deleted"]
    assert summary["target_retrieval_numerator"] == summary["target_retrieval_denominator"] == 1
    assert summary["target_answered"] == 0 and summary["queries_failed"] == 1
