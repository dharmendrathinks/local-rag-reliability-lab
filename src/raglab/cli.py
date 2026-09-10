"""JSON-first CLI; the experiment uses the same public commands as a user."""

import argparse
import json
import os
import sys
from pathlib import Path

from .common import LabError
from .ollama import Ollama, Settings


def add_settings(parser):
    defaults = Settings()
    parser.add_argument("--ollama-url", default=defaults.url)
    parser.add_argument("--embed-model", default=defaults.embed_model)
    parser.add_argument("--model", default=defaults.model)
    parser.add_argument("--temperature", type=float, default=defaults.temperature)
    parser.add_argument("--seed", type=int, default=defaults.seed)
    parser.add_argument("--num-ctx", type=int, default=defaults.num_ctx)
    parser.add_argument("--num-predict", type=int, default=defaults.num_predict)
    parser.add_argument("--top-k", type=int, default=defaults.top_k)
    parser.add_argument("--query-prefix", default=defaults.query_prefix)
    parser.add_argument("--document-prefix", default=defaults.document_prefix)


def parser():
    cli = argparse.ArgumentParser(description="Inspect source deletion, index deletion, retrieval, and local answers separately.")
    sub = cli.add_subparsers(dest="command", required=True)
    for name in ("ingest", "sync"):
        p = sub.add_parser(name)
        p.add_argument("--source", required=True, type=Path)
        p.add_argument("--index", required=True, type=Path)
        add_settings(p)
    p = sub.add_parser("ask")
    p.add_argument("question")
    p.add_argument("--index", required=True, type=Path)
    p.add_argument("--no-context", action="store_true")
    add_settings(p)
    p = sub.add_parser("inspect")
    p.add_argument("--index", required=True, type=Path)
    p = sub.add_parser("doctor", help="Inspect local server/model inventory without inference")
    add_settings(p)
    p = sub.add_parser("run-experiment")
    p.add_argument("--trials", type=int, default=3)
    p.add_argument("--output", type=Path, default=Path("artifacts"))
    add_settings(p)
    return cli


def settings_from_args(args):
    return Settings(url=args.ollama_url, embed_model=args.embed_model, model=args.model,
                    temperature=args.temperature, seed=args.seed, num_ctx=args.num_ctx,
                    num_predict=args.num_predict, top_k=args.top_k,
                    query_prefix=args.query_prefix, document_prefix=args.document_prefix)


def main():
    args = parser().parse_args()
    try:
        if args.command == "run-experiment":
            from .experiment import run_experiment
            if args.trials < 1:
                raise LabError("--trials must be positive")
            result = run_experiment(args.output, args.trials, settings_from_args(args))
        elif args.command == "doctor":
            result = {"status": "ok", "inventory": Ollama(settings_from_args(args)).inventory()}
        else:
            from .store import Store
            store = Store(args.index)
            if args.command == "inspect":
                result = store.inspect()
            else:
                backend = Ollama(settings_from_args(args))
                if args.command == "ask":
                    result = store.ask(args.question, backend, no_context=args.no_context)
                else:
                    result = store.reconcile(args.source, backend, delete_missing=args.command == "sync")
        result["pid"] = os.getpid()
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0 if result.get("status") in ("ok", "pending") else 1
    except Exception as exc:
        # CLI boundary preserves failures as machine-readable evidence and returns nonzero.
        print(json.dumps({"status": "error", "error_type": type(exc).__name__,
                          "error": str(exc), "pid": os.getpid()}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
