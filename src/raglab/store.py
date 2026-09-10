"""Persistent snapshot ingestion and explicitly recoverable reconciliation."""

import fcntl
import hashlib
import os
import re
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from .common import LabError, atomic_json, fsync_directory, read_json
from .ollama import generation_request

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
COLLECTION = "raglab_documents"


def fingerprint(s):
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def scan(root: Path):
    """Fail closed on any incomplete scan; never silently turn errors into absence."""
    try:
        if root.is_symlink():
            raise LabError(f"Source root cannot be a symlink: {root}")
        root_stat = root.stat()
        if not stat.S_ISDIR(root_stat.st_mode):
            raise LabError(f"Source root is not a directory: {root}")
        documents, directories = {}, {}

        def walk(directory):
            before = directory.stat()
            # Explicit mode check also makes tests meaningful under privileged users.
            if not before.st_mode & 0o444 or not before.st_mode & 0o111:
                raise LabError(f"Unreadable source directory: {directory}")
            directories[str(directory.relative_to(root))] = fingerprint(before)
            with os.scandir(directory) as entries:
                children = sorted(entries, key=lambda e: e.name)
            for entry in children:
                path = Path(entry.path)
                if entry.is_symlink():
                    raise LabError(f"Symlinks are not supported in source roots: {path}")
                if entry.is_dir(follow_symlinks=False):
                    walk(path)
                elif path.suffix == ".txt":
                    before_file = path.stat(follow_symlinks=False)
                    if not stat.S_ISREG(before_file.st_mode) or not before_file.st_mode & 0o444:
                        raise LabError(f"Unreadable or non-regular source: {path}")
                    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
                    with os.fdopen(fd, "rb") as stream:
                        opened = os.fstat(stream.fileno())
                        raw = stream.read()
                        after_file = os.fstat(stream.fileno())
                    if fingerprint(before_file) != fingerprint(opened) or fingerprint(opened) != fingerprint(after_file) or fingerprint(path.stat()) != fingerprint(after_file):
                        raise LabError(f"Source changed during scan: {path}")
                    documents[path.relative_to(root).as_posix()] = {
                        "text": raw.decode("utf-8"),
                        "content_hash": hashlib.sha256(raw).hexdigest(),
                        "stat": fingerprint(after_file),
                    }
            if fingerprint(directory.stat()) != fingerprint(before):
                raise LabError(f"Directory changed during scan: {directory}")

        walk(root)
        return {"identity": [root_stat.st_dev, root_stat.st_ino],
                "documents": documents, "directories": directories}
    except (OSError, UnicodeError) as exc:
        raise LabError(f"Source scan failed; index was not reconciled: {exc}") from exc


def chunks(text):
    if not text:
        return []
    result = []
    start = 0
    while start < len(text):
        result.append(text[start:start + CHUNK_SIZE])
        if start + CHUNK_SIZE >= len(text):
            break
        start += CHUNK_SIZE - CHUNK_OVERLAP
    return result


def make_document(binding, relative_path, source):
    doc_id = str(uuid.uuid5(uuid.UUID(binding["root_id"]), relative_path))
    texts = chunks(source["text"])
    ids = [f"{doc_id}:{source['content_hash']}:{i}" for i in range(len(texts))]
    return {"doc_id": doc_id, "source_path": relative_path,
            "content_hash": source["content_hash"], "chunk_ids": ids}, texts


class Store:
    def __init__(self, path):
        self.path = Path(path).absolute()
        self._collection = None

    @contextmanager
    def locked(self):
        self.path.mkdir(parents=True, exist_ok=True)
        with (self.path / "access.lock").open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def collection(self, *, create=False):
        if self._collection is None:
            client = chromadb.PersistentClient(
                path=str(self.path / "chroma"),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            if create:
                self._collection = client.get_or_create_collection(
                    COLLECTION, embedding_function=None,
                    configuration={"hnsw": {"space": "cosine"}},
                )
            else:
                self._collection = client.get_collection(COLLECTION, embedding_function=None)
        return self._collection

    def records(self, collection):
        rows = []
        offset = 0
        while True:
            result = collection.get(limit=1000, offset=offset, include=["documents", "metadatas"])
            rows.extend({"id": i, "text": t, "metadata": m} for i, t, m in
                        zip(result["ids"], result["documents"], result["metadatas"], strict=True))
            if len(result["ids"]) < 1000:
                return sorted(rows, key=lambda r: r["id"])
            offset += len(result["ids"])

    def _upsert(self, collection, **kwargs):
        collection.upsert(**kwargs)

    def _delete(self, collection, **kwargs):
        collection.delete(**kwargs)

    def _commit_manifest(self, manifest):
        atomic_json(self.path / "manifest.json", manifest)

    def reconcile(self, source_root, embedder, *, delete_missing):
        root_input = Path(source_root).absolute()
        if root_input.is_symlink():
            raise LabError("Source root cannot be a symlink")
        root = root_input.resolve()
        index = self.path.resolve()
        if root == index or root in index.parents or index in root.parents:
            raise LabError("Source and index directories must not contain each other")
        with self.locked():
            snapshot = scan(root)
            binding = read_json(self.path / "binding.json")
            pending = read_json(self.path / "pending.json")
            if pending and not delete_missing:
                raise LabError("Interrupted operation found; run sync to recover before ingest")
            if binding:
                if binding["source_root"] != str(root) or binding["root_identity"] != snapshot["identity"]:
                    raise LabError("Source root differs from the bound root (path or filesystem identity)")
            else:
                binding = {"schema_version": 1, "source_root": str(root), "root_id": str(uuid.uuid4()),
                           "root_identity": snapshot["identity"], "embedding": embedder.embedding_config(),
                           "chunk_size": CHUNK_SIZE, "chunk_overlap": CHUNK_OVERLAP, "distance": "cosine"}
            if binding["chunk_size"] != CHUNK_SIZE or binding["chunk_overlap"] != CHUNK_OVERLAP:
                raise LabError("Chunk configuration changed; use a separate index")
            old_manifest = read_json(self.path / "manifest.json", {"schema_version": 1, "documents": {}})
            desired = {}
            text_by_doc = {}
            for relative, source in snapshot["documents"].items():
                doc, text = make_document(binding, relative, source)
                desired[doc["doc_id"]] = doc
                text_by_doc[doc["doc_id"]] = text
            # No binding/collection is created until the complete scan and config checks succeed.
            if not (self.path / "binding.json").exists():
                atomic_json(self.path / "binding.json", binding)
            collection = self.collection(create=True)
            before = self.records(collection)
            by_doc = {}
            for row in before:
                metadata = row["metadata"] or {}
                if metadata.get("root_id") != binding["root_id"] or not metadata.get("doc_id"):
                    raise LabError("Unexpected foreign record in this index; refusing reconciliation")
                by_doc.setdefault(metadata["doc_id"], []).append(row)
            expected = {} if delete_missing else dict(old_manifest["documents"])
            expected.update(desired)
            changed = []
            for doc_id, doc in desired.items():
                existing = {r["id"]: r for r in by_doc.get(doc_id, [])}
                matches = set(existing) == set(doc["chunk_ids"])
                for i, chunk_id in enumerate(doc["chunk_ids"]):
                    row = existing.get(chunk_id)
                    meta = self._metadata(binding, doc, i)
                    matches = matches and row is not None and row["text"] == text_by_doc[doc_id][i] and row["metadata"] == meta
                if not matches:
                    changed.append(doc_id)
            removed_docs = sorted((set(old_manifest["documents"]) | set(by_doc) |
                                   set((pending or {}).get("document_ids", []))) - set(desired)) if delete_missing else []
            embeddings = {}
            if changed:
                if embedder.embedding_config() != binding["embedding"]:
                    raise LabError("Embedding model/digest/prefix configuration differs from this index")
                # Compute everything before writes; failure here cannot partially replace an index.
                for doc_id in changed:
                    text = text_by_doc[doc_id]
                    embeddings[doc_id] = embedder.embed(text) if text else []
            if scan(root) != snapshot:
                raise LabError("Source changed before index operations; retry with a stable source tree")
            journal = {"schema_version": 1, "operation": "sync" if delete_missing else "ingest",
                       "document_ids": sorted(set(changed) | set(removed_docs)),
                       "root_id": binding["root_id"]}
            atomic_json(self.path / "pending.json", journal)
            upserted, deleted = [], []
            for doc_id in changed:
                doc = desired[doc_id]
                if doc["chunk_ids"]:
                    self._upsert(collection, ids=doc["chunk_ids"], documents=text_by_doc[doc_id],
                                 embeddings=embeddings[doc_id],
                                 metadatas=[self._metadata(binding, doc, i) for i in range(len(doc["chunk_ids"]))])
                    upserted.extend(doc["chunk_ids"])
                obsolete = sorted({r["id"] for r in by_doc.get(doc_id, [])} - set(doc["chunk_ids"]))
                if obsolete:
                    self._delete(collection, ids=obsolete)
                    deleted.extend(obsolete)
            for doc_id in removed_docs:
                self._delete(collection, where={"doc_id": doc_id})
                deleted.extend(r["id"] for r in by_doc.get(doc_id, []))
            after = self.records(collection)
            expected_ids = {i for d in expected.values() for i in d["chunk_ids"]}
            if {r["id"] for r in after} != expected_ids:
                raise LabError("Post-operation record verification failed; manifest not committed, run sync")
            # Full record equality for unrelated documents, not just record counts.
            unaffected = set(by_doc) - set(changed) - set(removed_docs)
            if [r for r in before if r["metadata"]["doc_id"] in unaffected] != [r for r in after if r["metadata"]["doc_id"] in unaffected]:
                raise LabError("Unrelated record preservation failed; manifest not committed")
            manifest = {"schema_version": 1, "documents": expected}
            self._commit_manifest(manifest)
            (self.path / "pending.json").unlink()
            fsync_directory(self.path)
            return {"status": "ok", "operation": journal["operation"], "recovered_pending": bool(pending),
                    "source_root": str(root), "scanned_documents": len(desired),
                    "upserted_ids": upserted, "deleted_ids": sorted(deleted),
                    "deleted_document_ids": removed_docs,
                    "before_count": len(before), "after_count": len(after),
                    "manifest_changed": manifest != old_manifest}

    @staticmethod
    def _metadata(binding, doc, position):
        return {"root_id": binding["root_id"], "doc_id": doc["doc_id"],
                "source_root": binding["source_root"], "source_path": doc["source_path"],
                "content_hash": doc["content_hash"], "chunk_index": position}

    def inspect(self):
        if not (self.path / "binding.json").exists():
            raise LabError(f"No initialized index at {self.path}")
        with self.locked():
            binding = read_json(self.path / "binding.json")
            manifest = read_json(self.path / "manifest.json", {"schema_version": 1, "documents": {}})
            pending = read_json(self.path / "pending.json")
            records = self.records(self.collection())
            paths = sorted({d["source_path"] for d in manifest["documents"].values()} |
                           {r["metadata"]["source_path"] for r in records})
            source_status = {}
            for path in paths:
                try:
                    source_status[path] = {"present": (Path(binding["source_root"]) / path).is_file()}
                except OSError as exc:
                    source_status[path] = {"present": None, "error": str(exc)}
            expected = {i for d in manifest["documents"].values() for i in d["chunk_ids"]}
            return {"status": "pending" if pending else "ok", "binding": binding,
                    "manifest": manifest, "pending": pending, "records": records,
                    "record_count": len(records), "manifest_matches_record_ids": expected == {r["id"] for r in records},
                    "source_presence": source_status}

    def ask(self, question, backend, *, no_context=False):
        if no_context:
            return answer(question, [], backend)
        if not (self.path / "manifest.json").exists():
            raise LabError("Index is not ingested; use ingest or ask --no-context")
        with self.locked():
            if (self.path / "pending.json").exists():
                raise LabError("Index has an interrupted operation; inspect it and run sync before ask")
            binding = read_json(self.path / "binding.json")
            if backend.embedding_config() != binding["embedding"]:
                raise LabError("Embedding model/digest/prefix configuration differs from this index")
            collection = self.collection()
            count = collection.count()
            retrieved = []
            if count:
                result = collection.query(query_embeddings=backend.embed([question], query=True),
                                          n_results=min(backend.settings.top_k, count),
                                          include=["documents", "metadatas", "distances"])
                retrieved = [{"id": i, "text": t, "metadata": m, "distance": d}
                             for i, t, m, d in zip(result["ids"][0], result["documents"][0],
                                                   result["metadatas"][0], result["distances"][0], strict=True)]
            return answer(question, retrieved, backend)


def answer(question, retrieved, backend):
    retrieved = [dict(row, citation=f"C{i}") for i, row in enumerate(retrieved, 1)]
    context = "\n\n".join(f"[{r['citation']}] source={r['metadata']['source_path']} chunk_id={r['id']}\n{r['text']}" for r in retrieved)
    request = generation_request(backend.settings, question, context)
    result = {"status": "ok", "question": question, "retrieved": retrieved,
              "context": context, "request": request, "application_answer_cache": False}
    try:
        response = backend.generate(request)
        text = response["response"]
        citations = re.findall(r"\[(C\d+)\]", text)
        available = {r["citation"] for r in retrieved}
        result.update(answer=text, raw_response=response,
                      citations=[{"label": c, "valid_reference": c in available} for c in citations],
                      truncated=response.get("done_reason") == "length")
    except (LabError, OSError) as exc:
        # Retain retrieval and exact request even when generation fails.
        result.update(status="error", error=str(exc), answer=None, citations=[])
    return result
