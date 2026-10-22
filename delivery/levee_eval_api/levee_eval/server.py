"""Development / small-deployment server (standard library, multi-threaded).

    python -m levee_eval.server --host 0.0.0.0 --port 8080

For production prefer gunicorn (Linux) or waitress (Windows) behind a reverse proxy;
see docs/04_deployment.md.
"""

from __future__ import annotations

import argparse
import logging
import os
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

from .wsgi import application


class _ThreadingServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, fmt, *args):   # access lines come from the app logger instead
        pass


def main(argv=None):
    p = argparse.ArgumentParser(description="堤防渗流安全评价服务（开发/轻量部署用）")
    p.add_argument("--host", default=os.environ.get("LEVEE_EVAL_HOST", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(os.environ.get("LEVEE_EVAL_PORT", "8080")))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    with make_server(args.host, args.port, application, _ThreadingServer, _QuietHandler) as httpd:
        logging.info("listening on http://%s:%d/api/v1/health", args.host, args.port)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
