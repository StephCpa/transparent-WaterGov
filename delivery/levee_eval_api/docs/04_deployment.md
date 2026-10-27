# 部署说明

## 1 环境要求

| 项目 | 要求 |
|---|---|
| 操作系统 | Linux（推荐）、Windows、macOS均可 |
| Python | 3.10及以上；已在3.10、3.11、3.12、3.13上通过全部测试 |
| 第三方依赖 | **服务本身无第三方依赖**（只用标准库）；生产环境另装一个WSGI服务器：Linux用gunicorn，Windows用waitress（见 `requirements-deploy.txt`） |
| CPU / 内存 | 单个评价约0.5 ms计算；每个工作进程常驻内存约20～30 MB。2核2 GB的虚拟机足够一般平台使用 |
| 磁盘 | 对接包解压后约2.5 MB；服务不写数据文件，只输出日志 |
| 网络 | 只需开放一个HTTP端口（默认8080），建议仅对内网或反向代理开放 |

实测吞吐（4核虚拟机，单个评价请求、16路并发）：gunicorn 4进程约1100次/s，waitress 8线程约800次/s；875个单元的批量请求约0.8 s。

## 2 部署前自检

在部署机器上解压对接包，进入目录后运行：

```bash
python3 -m unittest discover -s tests -t .        # Windows: py -3 -m unittest discover -s tests -t .
```

全部通过（OK）说明该机器的Python环境能得到与交付模型完全一致的结果。

## 3 方式A：开发联调（标准库服务器）

```bash
python3 -m levee_eval.server --host 127.0.0.1 --port 8080
# 或 sh deploy/run_dev.sh
```

多线程，适合联调、演示和小规模内网使用。对外长期服务请用方式B/C/D。

## 4 方式B：Linux生产部署（gunicorn + systemd + nginx）

```bash
# 1. 放置代码并创建运行账号
sudo mkdir -p /opt/levee_eval_api && sudo cp -r ./* /opt/levee_eval_api/
sudo useradd --system --no-create-home levee
cd /opt/levee_eval_api
sudo python3 -m venv .venv
sudo .venv/bin/pip install -r requirements-deploy.txt
sudo chown -R levee:levee /opt/levee_eval_api

# 2. 密钥等配置写入环境文件（不要写进unit文件）
echo 'LEVEE_EVAL_API_KEY=请替换为随机长字符串' | sudo tee /etc/levee-eval.env
sudo chmod 600 /etc/levee-eval.env

# 3. 注册为系统服务
sudo cp deploy/levee-eval.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now levee-eval
systemctl status levee-eval
curl http://127.0.0.1:8080/api/v1/health

# 4. 反向代理与HTTPS：参考 deploy/nginx_levee_eval.conf
```

`deploy/gunicorn.conf.py` 的要点：默认只监听127.0.0.1（由nginx对外）；工作进程数默认 `min(2×CPU+1, 9)`，可用 `LEVEE_EVAL_WORKERS` 覆盖；计算是CPU密集型，增加进程数比增加线程有效；访问日志输出到标准输出，由journald收集（`journalctl -u levee-eval`）。

## 5 方式C：Docker

```bash
# 在对接包根目录执行
docker build -f deploy/Dockerfile -t levee-eval:1.3.2 .
docker run -d --name levee-eval --restart unless-stopped \
  -p 127.0.0.1:8080:8080 --read-only --tmpfs /tmp \
  -e LEVEE_EVAL_WORKERS=4 -e LEVEE_EVAL_API_KEY=请替换 \
  levee-eval:1.3.2
docker ps            # STATUS 显示 (healthy) 即正常
```

或使用 `docker compose -f deploy/docker-compose.yml up -d --build`。镜像基于 `python:3.12-slim`（约180 MB），以非root用户运行，内置健康检查，容器文件系统可设为只读。无法访问外网的服务器可在有网的机器上构建后 `docker save` / `docker load` 导入。

## 6 方式D：Windows

```bat
REM 在对接包根目录执行（一次性准备）
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements-deploy.txt

REM 启动（默认 127.0.0.1:8080，可先 set LEVEE_EVAL_HOST / LEVEE_EVAL_PORT / LEVEE_EVAL_API_KEY）
deploy\run_windows_waitress.bat
```

需要开机自启时，可用NSSM把上述bat注册为Windows服务，或用“任务计划程序”在系统启动时以专用账号运行。若通过IIS对外，配置为反向代理到该端口即可。

## 7 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `LEVEE_EVAL_HOST` | 127.0.0.1（Docker中为0.0.0.0） | 监听地址 |
| `LEVEE_EVAL_PORT` | 8080 | 监听端口 |
| `LEVEE_EVAL_API_KEY` | 空（不鉴权） | 设置后除 `/health` 外须带请求头 `X-API-Key` |
| `LEVEE_EVAL_CORS_ORIGINS` | 空（不返回CORS头） | 允许浏览器跨域调用的来源，逗号分隔，或 `*` |
| `LEVEE_EVAL_MAX_BODY_MB` | 5 | 请求体上限（MB），需与nginx的 `client_max_body_size` 一致 |
| `LEVEE_EVAL_WORKERS` | min(2×CPU+1, 9) | gunicorn工作进程数 |
| `LEVEE_EVAL_TIMEOUT` | 60 | gunicorn请求超时（s） |
| `LEVEE_EVAL_LOG_LEVEL` | info | gunicorn日志级别 |
| `LEVEE_EVAL_THREADS` | 8 | waitress线程数（Windows脚本） |

## 8 安全建议

- 服务只应部署在内网，或放在反向代理之后；对外必须走HTTPS（在nginx/IIS终止TLS）。
- 生产环境设置 `LEVEE_EVAL_API_KEY`（随机长字符串），密钥放在权限为600的环境文件或容器密钥中，不要写入代码仓库。
- 仅在确实需要浏览器直接调用时设置CORS，并列出具体来源，不要用 `*`。
- 服务不保存请求数据；日志只记录方法、路径、状态码、耗时和追踪号，不记录请求体。调用方如需留存评价记录，应在本方系统中保存请求和响应。
- 请求体大小有上限（默认5 MB），校验拒绝未声明字段和非有限数值。

## 9 运维

- **健康检查**：`GET /api/v1/health`，返回200和 `{"status":"ok", ...}`；可用于负载均衡、容器编排和监控。
- **版本核对**：`/health` 返回的 `api_version` 与模型文件sha256应与本包一致（`01_code_description.md` 第3节）。
- **日志**：gunicorn访问日志格式为 `来源 "方法 路径 协议" 状态 字节 耗时ms rid=追踪号`；500错误的完整堆栈写入错误日志，按响应中的 `trace_id` 检索。
- **扩容**：服务无状态，可直接增加进程或实例，前面用nginx负载均衡。
- **升级与回滚**：新版本解压到新目录（或使用新镜像标签），先运行第2节自检，再切换systemd的 `WorkingDirectory`/`ExecStart` 或容器镜像；回滚时切回旧目录或旧标签。

## 10 部署后验证

```bash
BASE=http://127.0.0.1:8080
curl -s $BASE/api/v1/health
curl -s -X POST $BASE/api/v1/evaluate -H "Content-Type: application/json" \
     -H "X-API-Key: <密钥>" --data-binary @examples/request_full.json
# 应得到 "score": 67.5529, "grade": "B"，与 examples/response_full.json 一致
BASE=$BASE API_KEY=<密钥> sh examples/curl_examples.sh
```

## 11 常见问题

| 现象 | 原因与处理 |
|---|---|
| 415 Unsupported Media Type | 请求头缺少 `Content-Type: application/json` |
| 422且details为required | 必填字段未给出；“没有”也要显式填写（`不涉及`、`[]`、`null`） |
| 中文乱码或400 invalid_json | 请求体不是UTF-8；Windows PowerShell的 `curl` 是别名，请用 `curl.exe --data-binary @文件` |
| 413 Payload Too Large | 批量请求过大：拆分，或同时调大 `LEVEE_EVAL_MAX_BODY_MB` 和nginx的 `client_max_body_size` |
| 504（经nginx） | 超时：批量过大或进程不足；拆分批量、增加 `LEVEE_EVAL_WORKERS` |
| Docker构建时pip下载失败 | 服务器无外网：配置pip镜像源，或在有网机器上构建后 `docker save`/`docker load` |
| 结果与本地测试不一致 | 核对 `/health` 的模型sha256和 `api_version`；比较两次请求的 `provenance.input_sha256` 是否相同 |
