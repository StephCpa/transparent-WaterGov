#!/usr/bin/env sh
# curl examples.  Run from the package root after starting the service.
#   BASE=http://127.0.0.1:8080  API_KEY=...  sh examples/curl_examples.sh
BASE="${BASE:-http://127.0.0.1:8080}"
KEY_HEADER=""
[ -n "$API_KEY" ] && KEY_HEADER="X-API-Key: $API_KEY"

echo "== health";   curl -sS "$BASE/api/v1/health"; echo
echo "== meta (first 300 bytes)"; curl -sS -H "$KEY_HEADER" "$BASE/api/v1/meta" | head -c 300; echo

echo "== evaluate (full request, full detail)"
curl -sS -X POST "$BASE/api/v1/evaluate" \
     -H "Content-Type: application/json" -H "$KEY_HEADER" -H "X-Request-ID: demo-trace-001" \
     --data-binary @examples/request_full.json -o /tmp/levee_eval_response.json -w "HTTP %{http_code}\n"
python3 -c "import json;r=json.load(open('/tmp/levee_eval_response.json',encoding='utf-8'))['result'];print(r['score'],r['grade'],r['dominant_mode'],r['gate_reasons'])"

echo "== evaluate (no inspection: C3 missing, warning returned)"
curl -sS -X POST "$BASE/api/v1/evaluate?detail=summary" \
     -H "Content-Type: application/json" -H "$KEY_HEADER" \
     --data-binary @examples/request_minimal_no_inspection.json | head -c 400; echo

echo "== invalid request -> 422 with per-field details"
curl -sS -X POST "$BASE/api/v1/evaluate" \
     -H "Content-Type: application/json" -H "$KEY_HEADER" \
     --data-binary @examples/request_invalid.json -w "\nHTTP %{http_code}\n"

echo "== batch (3 items, one invalid)"
curl -sS -X POST "$BASE/api/v1/evaluate/batch?detail=summary" \
     -H "Content-Type: application/json" -H "$KEY_HEADER" \
     --data-binary @examples/request_batch.json \
  | python3 -c "import json,sys;b=json.load(sys.stdin);print(b['count'],b['succeeded'],b['failed'],[x['ok'] for x in b['results']])"
