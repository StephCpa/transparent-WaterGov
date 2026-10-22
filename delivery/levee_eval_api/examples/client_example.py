"""Minimal Python client (standard library only).

    python examples/client_example.py --url http://127.0.0.1:8080 [--api-key KEY] [request.json ...]

Without request files it sends examples/request_full.json.  Shows the recommended handling:
422 -> fix the listed fields; 5xx / network errors -> retry with backoff; warnings -> log/show them.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


def evaluate(base_url, payload, api_key=None, detail="full", retries=3, timeout=30):
    url = f"{base_url.rstrip('/')}/api/v1/evaluate?detail={detail}"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json", "X-Request-ID": uuid.uuid4().hex}
    if api_key:
        headers["X-API-Key"] = api_key
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = json.loads(exc.read().decode("utf-8") or "{}")
            if exc.code < 500 or attempt == retries:   # 4xx: the request itself must be fixed
                raise RuntimeError(f"HTTP {exc.code}: {json.dumps(body, ensure_ascii=False)}") from None
        except urllib.error.URLError:
            if attempt == retries:
                raise
        time.sleep(2 ** attempt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8080")
    ap.add_argument("--api-key")
    ap.add_argument("--detail", choices=["full", "summary"], default="summary")
    ap.add_argument("files", nargs="*", type=Path)
    args = ap.parse_args()
    files = args.files or [Path(__file__).with_name("request_full.json")]
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            r = evaluate(args.url, payload, args.api_key, args.detail)
        except RuntimeError as exc:
            print(f"{path.name}: {exc}", file=sys.stderr)
            continue
        res = r["result"]
        print(f"{path.name}: section={r['section_id']} score={res['score']} grade={res['grade']}({res['grade_label']}) "
              f"dominant={res['dominant_mode']['name']} gates={res['gate_reasons']}")
        for w in r["warnings"]:
            print(f"  warning[{w['code']}] {w['message']}")


if __name__ == "__main__":
    main()
