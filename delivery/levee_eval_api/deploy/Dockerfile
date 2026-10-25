# Build from the package root:  docker build -f deploy/Dockerfile -t levee-eval:1.1.0 .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    LEVEE_EVAL_HOST=0.0.0.0 LEVEE_EVAL_PORT=8080
WORKDIR /app
COPY requirements-deploy.txt .
RUN pip install --no-cache-dir -r requirements-deploy.txt \
 && useradd --system --uid 10001 --no-create-home levee
COPY levee_eval ./levee_eval
COPY deploy/gunicorn.conf.py ./deploy/gunicorn.conf.py
USER levee
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4).status == 200 else 1)"
CMD ["gunicorn", "-c", "deploy/gunicorn.conf.py", "levee_eval.wsgi:application"]
