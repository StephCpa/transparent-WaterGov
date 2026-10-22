"""gunicorn settings:  gunicorn -c deploy/gunicorn.conf.py levee_eval.wsgi:application"""

import multiprocessing
import os

bind = f"{os.environ.get('LEVEE_EVAL_HOST', '127.0.0.1')}:{os.environ.get('LEVEE_EVAL_PORT', '8080')}"
# the evaluation is CPU-bound (~0.5 ms per unit): processes, not threads, add throughput
workers = int(os.environ.get("LEVEE_EVAL_WORKERS", min(2 * multiprocessing.cpu_count() + 1, 9)))
worker_class = "sync"
timeout = int(os.environ.get("LEVEE_EVAL_TIMEOUT", "60"))   # a 1000-unit batch takes about 1 s
graceful_timeout = 30
keepalive = 5
max_requests = 5000
max_requests_jitter = 500
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LEVEE_EVAL_LOG_LEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(M)sms rid=%({x-request-id}o)s'
