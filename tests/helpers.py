"""Test doubles only; production CLI cannot select this embedding backend."""

import hashlib

from raglab.ollama import Settings


class FakeBackend:
    def __init__(self):
        self.settings = Settings()
        self.requests = []

    def embedding_config(self):
        return {"model": "deterministic-test-double", "digest": "test-only",
                "query_prefix": "", "document_prefix": "", "truncate": False}

    def embed(self, texts, *, query=False):
        return [[(b - 127.5) / 128 for b in hashlib.sha256(t.encode()).digest()] for t in texts]

    def generate(self, request):
        self.requests.append(request)
        return {"done": True, "response": "I do not know.", "done_reason": "stop"}
