#!/usr/bin/env sh
# Development server (standard library only).  Run from the package root.
exec python3 -m levee_eval.server --host "${LEVEE_EVAL_HOST:-127.0.0.1}" --port "${LEVEE_EVAL_PORT:-8080}"
