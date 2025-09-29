#!/usr/bin/env python3
import argparse
import json
import time
from typing import List

import requests


def measure(query: str, base_url: str, space_id: str | None, top_k: int | None) -> dict:
    params = {"q": query}
    if space_id:
        params["space_id"] = space_id
    if top_k:
        params["top_k"] = top_k
    start = time.perf_counter()
    resp = requests.get(f"{base_url}/search", params=params, timeout=30)
    latency = time.perf_counter() - start
    resp.raise_for_status()
    data = resp.json()
    chunks = data.get("results", [])
    context_tokens = sum(len(c.get("payload", {}).get("text", "").split()) for c in chunks)
    doc_types = list({c.get("payload", {}).get("doc_type") for c in chunks if c.get("payload")})
    return {
        "query": query,
        "latency_ms": round(latency * 1000, 1),
        "chunks": len(chunks),
        "context_tokens": context_tokens,
        "doc_types": doc_types,
    }


def main():
    parser = argparse.ArgumentParser(description="Measure search latency and context size.")
    parser.add_argument("queries", nargs="+", help="Queries to benchmark")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--space", help="Optional space_id")
    parser.add_argument("--top-k", type=int)
    args = parser.parse_args()

    rows: List[dict] = []
    for q in args.queries:
        rows.append(measure(q, args.base_url.rstrip("/"), args.space, args.top_k))

    print(json.dumps(rows, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
