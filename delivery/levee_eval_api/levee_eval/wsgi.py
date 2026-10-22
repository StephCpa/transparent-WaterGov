"""WSGI application (standard library only).

Endpoints (all JSON, UTF-8):
  GET  /api/v1/health          liveness and model file hashes
  GET  /api/v1/meta            weights, categories, grade thresholds, constants
  GET  /api/v1/openapi.json    OpenAPI 3.0 description
  POST /api/v1/evaluate        one evaluation unit
  POST /api/v1/evaluate/batch  {"items": [...]}, at most schema.MAX_BATCH units
  Both POST endpoints accept ?detail=summary to omit result.contributions_by_mode.

Environment:
  LEVEE_EVAL_API_KEY       if set, every request except /health must send header X-API-Key
  LEVEE_EVAL_CORS_ORIGINS  comma-separated allowed origins, or * (default: no CORS headers)
  LEVEE_EVAL_MAX_BODY_MB   request body limit in MB (default 5)

Run behind any WSGI server, e.g.  gunicorn -c deploy/gunicorn.conf.py levee_eval.wsgi:application
"""

from __future__ import annotations

import hmac
import json
import logging
import os
import traceback
import uuid
from urllib.parse import parse_qs

from . import engine
from .openapi import build_openapi

log = logging.getLogger("levee_eval")
PREFIX = "/api/v1"
_STATUS = {200: "200 OK", 204: "204 No Content", 400: "400 Bad Request", 401: "401 Unauthorized",
           404: "404 Not Found", 405: "405 Method Not Allowed", 413: "413 Payload Too Large",
           415: "415 Unsupported Media Type", 422: "422 Unprocessable Entity", 500: "500 Internal Server Error"}


class HttpError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status, self.code, self.message, self.details = status, code, message, details


def _settings():
    return {"api_key": os.environ.get("LEVEE_EVAL_API_KEY") or None,
            "cors": [o.strip() for o in os.environ.get("LEVEE_EVAL_CORS_ORIGINS", "").split(",") if o.strip()],
            "max_body": int(float(os.environ.get("LEVEE_EVAL_MAX_BODY_MB", "5")) * 1024 * 1024)}


def _read_json(environ, max_body):
    ctype = environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower()
    if ctype != "application/json":
        raise HttpError(415, "unsupported_media_type", "Content-Type必须为application/json")
    too_large = HttpError(413, "payload_too_large", f"请求体超过{max_body / (1024 * 1024):g} MB上限")
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        length = 0
    if length > max_body:
        raise too_large
    if length:
        raw = environ["wsgi.input"].read(length)
    elif environ.get("wsgi.input_terminated"):   # chunked upload (gunicorn)
        raw = environ["wsgi.input"].read(max_body + 1)
        if len(raw) > max_body:
            raise too_large
    else:
        raw = b""
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HttpError(400, "invalid_json", f"请求体不是合法的UTF-8 JSON：{exc}") from None


def _detail(environ):
    values = parse_qs(environ.get("QUERY_STRING", "")).get("detail", ["full"])
    if len(values) != 1 or values[0] not in engine.DETAIL_LEVELS:
        raise HttpError(400, "invalid_query", "detail只能为full或summary")
    return values[0]


def _route(method, path, environ, cfg):
    if path == f"{PREFIX}/health":
        _allow(method, "GET")
        return 200, {"status": "ok", "api_version": engine.API_VERSION, "model": engine.MODEL_INFO}
    if path == f"{PREFIX}/meta":
        _allow(method, "GET")
        return 200, engine.meta()
    if path == f"{PREFIX}/openapi.json":
        _allow(method, "GET")
        return 200, build_openapi()
    if path == f"{PREFIX}/evaluate":
        _allow(method, "POST")
        detail = _detail(environ)
        body = _read_json(environ, cfg["max_body"])
        try:
            return 200, engine.evaluate(body, detail=detail)
        except engine.RequestInvalid as exc:
            raise HttpError(422, "validation_failed", "请求字段校验未通过", exc.details) from None
    if path == f"{PREFIX}/evaluate/batch":
        _allow(method, "POST")
        detail = _detail(environ)
        body = _read_json(environ, cfg["max_body"])
        if not isinstance(body, dict) or set(body) != {"items"}:
            raise HttpError(422, "validation_failed", "批量请求体必须为{\"items\": [...]}",
                            [{"field": "items", "reason": "required"}])
        try:
            return 200, engine.evaluate_batch(body["items"], detail=detail)
        except engine.RequestInvalid as exc:
            raise HttpError(422, "validation_failed", "批量请求校验未通过", exc.details) from None
    raise HttpError(404, "not_found", f"未找到接口：{path}")


def _allow(method, expected):
    if method != expected:
        raise HttpError(405, "method_not_allowed", f"该接口只接受{expected}")


def _cors_headers(environ, cfg):
    origin = environ.get("HTTP_ORIGIN")
    if not origin or not cfg["cors"]:
        return []
    if "*" in cfg["cors"]:
        allow = "*"
    elif origin in cfg["cors"]:
        allow = origin
    else:
        return []
    return [("Access-Control-Allow-Origin", allow), ("Vary", "Origin"),
            ("Access-Control-Allow-Headers", "Content-Type, X-API-Key, X-Request-ID"),
            ("Access-Control-Allow-Methods", "GET, POST, OPTIONS")]


def application(environ, start_response):
    cfg = _settings()
    method = environ.get("REQUEST_METHOD", "GET").upper()
    path = environ.get("PATH_INFO", "") or "/"
    if len(path) > 1:
        path = path.rstrip("/")
    trace_id = environ.get("HTTP_X_REQUEST_ID") or uuid.uuid4().hex
    headers = [("Content-Type", "application/json; charset=utf-8"), ("X-Request-ID", trace_id),
               *_cors_headers(environ, cfg)]
    if method == "OPTIONS":
        start_response(_STATUS[204], headers)
        return [b""]
    try:
        if cfg["api_key"] and path != f"{PREFIX}/health":
            sent = environ.get("HTTP_X_API_KEY", "")
            if not hmac.compare_digest(sent.encode(), cfg["api_key"].encode()):
                raise HttpError(401, "unauthorized", "缺少或错误的X-API-Key")
        status, payload = _route(method, path, environ, cfg)
    except HttpError as exc:
        status = exc.status
        payload = {"error": {"code": exc.code, "message": exc.message, **({"details": exc.details} if exc.details else {})},
                   "trace_id": trace_id}
    except Exception:  # noqa: BLE001
        log.error("unhandled error trace_id=%s\n%s", trace_id, traceback.format_exc())
        status = 500
        payload = {"error": {"code": "internal_error", "message": "服务内部错误，请凭trace_id联系维护方"},
                   "trace_id": trace_id}
    log.info("%s %s -> %s trace_id=%s", method, path, status, trace_id)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers.append(("Content-Length", str(len(body))))
    start_response(_STATUS[status], headers)
    return [body]
