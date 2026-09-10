import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from raglab.common import LabError, read_json
from raglab.store import Store, chunks
from tests.helpers import FakeBackend


@pytest.fixture
def lab(tmp_path):
    source = tmp_path / "sources"
    source.mkdir()
    (source / "target.txt").write_text("Target document. " * 180)
    (source / "other.txt").write_text("An unrelated preserved document.")
    backend = FakeBackend()
    store = Store(tmp_path / "index")
    store.reconcile(source, backend, delete_missing=False)
    return source, store, backend


def test_delete_all_chunks_preserve_other_records_and_repeat(lab):
    source, store, backend = lab
    baseline = store.inspect()
    target = [r for r in baseline["records"] if r["metadata"]["source_path"] == "target.txt"]
    other = [r for r in baseline["records"] if r["metadata"]["source_path"] == "other.txt"]
    assert len(target) > 2
    (source / "target.txt").unlink()
    assert not (source / "target.txt").exists()
    assert store.inspect()["records"] == baseline["records"]  # snapshot import semantics
    result = store.reconcile(source, backend, delete_missing=True)
    assert set(result["deleted_ids"]) == {r["id"] for r in target}
    assert store.inspect()["records"] == other
    manifest_bytes = (store.path / "manifest.json").read_bytes()
    second = store.reconcile(source, backend, delete_missing=True)
    assert second["deleted_ids"] == second["upserted_ids"] == []
    assert not second["manifest_changed"]
    assert (store.path / "manifest.json").read_bytes() == manifest_bytes
    assert store.inspect()["records"] == other


def test_ingest_does_not_synchronize_deletions(lab):
    source, store, backend = lab
    baseline = store.inspect()["records"]
    (source / "target.txt").unlink()
    store.reconcile(source, backend, delete_missing=False)
    assert store.inspect()["records"] == baseline


def test_edit_keeps_identity_and_removes_old_version_chunks(lab):
    source, store, backend = lab
    before = store.inspect()
    target = next(d for d in before["manifest"]["documents"].values() if d["source_path"] == "target.txt")
    (source / "target.txt").write_text("Short replacement.")
    store.reconcile(source, backend, delete_missing=True)
    after = store.inspect()
    new = after["manifest"]["documents"][target["doc_id"]]
    assert new["doc_id"] == target["doc_id"]
    assert new["content_hash"] != target["content_hash"]
    assert len(new["chunk_ids"]) == 1
    assert not set(target["chunk_ids"]) & {r["id"] for r in after["records"]}


def test_restart_persists_before_and_after_deletion(lab):
    source, store, backend = lab
    def inspect_new_process():
        process = subprocess.run([sys.executable, "-m", "raglab", "inspect", "--index", str(store.path)],
                                 capture_output=True, text=True, check=True)
        payload = json.loads(process.stdout)
        assert payload["pid"] != os.getpid()
        return payload
    before = inspect_new_process()
    (source / "target.txt").unlink()
    assert inspect_new_process()["records"] == before["records"]
    store.reconcile(source, backend, delete_missing=True)
    assert inspect_new_process()["records"] == store.inspect()["records"]
    assert all(r["metadata"]["source_path"] != "target.txt" for r in inspect_new_process()["records"])


@pytest.mark.parametrize("problem", ["missing", "root_unreadable", "nested_unreadable", "file_unreadable", "invalid_utf8", "symlink", "wrong_root", "replaced_root"])
def test_failed_scan_never_purges(lab, problem, tmp_path):
    source, store, backend = lab
    before = store.inspect()["records"]
    manifest = (store.path / "manifest.json").read_bytes()
    requested_source = source
    if problem == "missing":
        source.rename(tmp_path / "moved")
    elif problem == "root_unreadable":
        source.chmod(0)
    elif problem == "nested_unreadable":
        (source / "nested").mkdir()
        (source / "nested").chmod(0)
    elif problem == "file_unreadable":
        (source / "other.txt").chmod(0)
    elif problem == "invalid_utf8":
        (source / "other.txt").write_bytes(b"\xff")
    elif problem == "symlink":
        (source / "link.txt").symlink_to(source / "other.txt")
    elif problem == "wrong_root":
        requested_source = tmp_path / "different"
        requested_source.mkdir()
    elif problem == "replaced_root":
        source.rename(tmp_path / "moved")
        source.mkdir()
    try:
        with pytest.raises(LabError):
            store.reconcile(requested_source, backend, delete_missing=True)
        assert store.records(store.collection()) == before
        assert (store.path / "manifest.json").read_bytes() == manifest
        assert not (store.path / "pending.json").exists()
    finally:
        if source.exists():
            source.chmod(0o755)
        if (source / "nested").exists():
            (source / "nested").chmod(0o755)


def test_failed_enumeration_is_not_an_empty_scan(lab, monkeypatch):
    source, store, backend = lab
    before = store.inspect()["records"]
    original = os.scandir
    def fail(path):
        if Path(path) == source:
            raise OSError("injected enumeration failure")
        return original(path)
    monkeypatch.setattr(os, "scandir", fail)
    with pytest.raises(LabError, match="scan failed"):
        store.reconcile(source, backend, delete_missing=True)
    assert store.records(store.collection()) == before


def test_valid_empty_bound_root_can_remove_all_document_records(lab):
    source, store, backend = lab
    for path in source.iterdir():
        path.unlink()
    result = store.reconcile(source, backend, delete_missing=True)
    assert result["after_count"] == 0
    assert store.inspect()["manifest"]["documents"] == {}
    # Empty collections still invoke generation with empty context.
    answer = store.ask("Is there evidence?", backend)
    assert answer["context"] == ""
    assert len(backend.requests) == 1


@pytest.mark.parametrize("failure_point", ["delete", "manifest"])
def test_interrupted_deletion_is_recoverable(lab, monkeypatch, failure_point):
    source, store, backend = lab
    baseline = store.inspect()
    old_manifest = (store.path / "manifest.json").read_bytes()
    (source / "target.txt").unlink()
    method = "_delete" if failure_point == "delete" else "_commit_manifest"
    original = getattr(store, method)
    def fail(*args, **kwargs):
        if failure_point == "delete":
            original(*args, **kwargs)  # Simulate interruption AFTER the database accepts deletion.
        raise OSError("injected failure")
    monkeypatch.setattr(store, method, fail)
    with pytest.raises(OSError, match="injected"):
        store.reconcile(source, backend, delete_missing=True)
    assert (store.path / "manifest.json").read_bytes() == old_manifest
    assert store.inspect()["pending"] is not None
    with pytest.raises(LabError, match="interrupted"):
        store.ask("Anything?", backend)
    fresh = Store(store.path)
    result = fresh.reconcile(source, backend, delete_missing=True)
    assert result["recovered_pending"]
    expected = [r for r in baseline["records"] if r["metadata"]["source_path"] == "other.txt"]
    assert fresh.inspect()["records"] == expected
    assert fresh.inspect()["pending"] is None


def test_real_process_crash_after_upsert_recovers_orphan_chunks(lab):
    source, store, backend = lab
    old = store.inspect()["manifest"]
    (source / "target.txt").write_text("New version " * 220)
    script = """
import os, sys
from raglab.store import Store
from tests.helpers import FakeBackend
store = Store(sys.argv[1])
original = store._upsert
def crash(*args, **kwargs):
    original(*args, **kwargs)
    os._exit(17)
store._upsert = crash
store.reconcile(sys.argv[2], FakeBackend(), delete_missing=True)
"""
    process = subprocess.run([sys.executable, "-c", script, str(store.path), str(source)], capture_output=True)
    assert process.returncode == 17, process.stderr.decode()
    assert read_json(store.path / "manifest.json") == old
    assert (store.path / "pending.json").exists()
    # Source disappears after the interrupted write: remove new AND old version chunks.
    (source / "target.txt").unlink()
    fresh = Store(store.path)
    assert fresh.reconcile(source, backend, delete_missing=True)["recovered_pending"]
    assert all(r["metadata"]["source_path"] == "other.txt" for r in fresh.inspect()["records"])


def test_embedding_failure_precedes_index_mutation(lab, monkeypatch):
    source, store, backend = lab
    before = store.inspect()
    (source / "target.txt").write_text("Replacement")
    def fail(*args, **kwargs):
        raise LabError("injected embedding failure")
    monkeypatch.setattr(backend, "embed", fail)
    with pytest.raises(LabError, match="embedding failure"):
        store.reconcile(source, backend, delete_missing=True)
    assert store.inspect()["records"] == before["records"]
    assert store.inspect()["manifest"] == before["manifest"]
    assert store.inspect()["pending"] is None


def test_embedding_mismatch_fails_query_and_changed_ingestion(lab, monkeypatch):
    source, store, backend = lab
    monkeypatch.setattr(backend, "embedding_config", lambda: {"digest": "different"})
    with pytest.raises(LabError, match="differs"):
        store.ask("Question", backend)
    (source / "target.txt").write_text("Changed.")
    with pytest.raises(LabError, match="differs"):
        store.reconcile(source, backend, delete_missing=True)


def test_chunk_boundaries():
    assert chunks("") == []
    assert len(chunks("x" * 800)) == 1
    assert [len(c) for c in chunks("x" * 801)] == [800, 101]


def test_no_context_bypasses_index_and_never_caches(tmp_path):
    backend = FakeBackend()
    store = Store(tmp_path / "absent")
    first = store.ask("Unknown code?", backend, no_context=True)
    second = store.ask("Unknown code?", backend, no_context=True)
    assert len(backend.requests) == 2
    assert first["request"] == second["request"]
    assert first["context"] == ""
    assert not store.path.exists()


def test_generation_failure_keeps_context_and_request(lab, monkeypatch):
    _, store, backend = lab
    def fail(request):
        raise LabError("injected inference failure")
    monkeypatch.setattr(backend, "generate", fail)
    result = store.ask("Target document?", backend)
    assert result["status"] == "error"
    assert result["retrieved"] and result["context"]
    assert result["context"] in result["request"]["prompt"]


def test_invalid_citations_are_not_repaired(lab, monkeypatch):
    _, store, backend = lab
    monkeypatch.setattr(backend, "generate", lambda request: {"done": True, "response": "An assertion [C99] [C1]."})
    result = store.ask("Question", backend)
    assert result["answer"] == "An assertion [C99] [C1]."
    assert result["citations"] == [{"label": "C99", "valid_reference": False}, {"label": "C1", "valid_reference": True}]
