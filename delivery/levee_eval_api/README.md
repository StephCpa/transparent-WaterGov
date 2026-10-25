# 堤防渗流安全评价服务 v1.2.0（对接包）

本包把第5章“失效响应—安全屏障”规则链评价模型封装为一个JSON/HTTP计算服务，供合作方系统对接。

- 模型计算全部由交付的模型代码完成（`levee_eval/model/`，原样复制，附sha256校验）；
- 服务层负责字段校验、格式转换和HTTP接口，**只用Python标准库**，不需要安装任何第三方包；
- 在875个合成样本上，服务输出与直接运行交付代码的结果逐项完全一致（`tests/test_regression_875.py`）。

**推荐对接方式：HTTP + JSON。** 调用方每次提交一个评价单元（代表断面）的资料，服务返回安全得分、A/B/C等级、主控失效模式、门控原因、指标得分与贡献。

## 快速开始

```bash
# 1. 自检（约2 s，应显示 OK）
python3 -m unittest discover -s tests -t .

# 2. 启动服务（开发/联调）
python3 -m levee_eval.server --port 8080

# 3. 另开终端调用
curl http://127.0.0.1:8080/api/v1/health
curl -X POST http://127.0.0.1:8080/api/v1/evaluate \
     -H "Content-Type: application/json" --data-binary @examples/request_full.json
```

Windows下把 `python3` 换成 `py -3`，`curl` 换成 `curl.exe`。生产部署（gunicorn / Docker / Windows waitress）见 `docs/04_deployment.md`。

## 文档

| 文件 | 内容 |
|---|---|
| `docs/01_code_description.md` | 代码说明：定位、评价原理、代码结构、与交付代码的关系、验证、限制 |
| `docs/02_http_api.md` | HTTP接口说明：接口列表、请求与响应、巡检证据、错误处理、批量、示例、对接检查清单 |
| `docs/03_parameter_dictionary.md` | 输入输出参数字典（由代码自动生成）：字段、类型、单位、范围、对应指标、分档赋分、错误码 |
| `docs/04_deployment.md` | 部署说明：环境要求、四种部署方式、环境变量、安全、运维、常见问题 |
| `docs/openapi.json` | OpenAPI 3.0接口描述，可导入Swagger UI / Apifox / Postman |

## 目录

```
levee_eval/            服务代码
  model/               交付的模型代码（原样，勿改）
  schema.py            请求字段定义与校验（字段的唯一来源）
  engine.py            评价引擎：JSON ↔ 交付模型
  wsgi.py / server.py  HTTP接口 / 开发服务器
  openapi.py           OpenAPI文档生成
examples/              请求与响应示例、curl脚本、Python客户端
deploy/                Dockerfile、docker-compose、gunicorn、systemd、nginx、Windows启动脚本
tests/                 单元测试、HTTP测试、875样本回归测试
tools/                 回归基准与文档的生成脚本
requirements-deploy.txt  生产WSGI服务器（可选）
```

## 接口一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查与模型版本 |
| GET | `/api/v1/meta` | 指标、权重、分档赋分、等级阈值 |
| GET | `/api/v1/openapi.json` | OpenAPI文档 |
| POST | `/api/v1/evaluate` | 单个评价单元 |
| POST | `/api/v1/evaluate/batch` | 批量评价（≤1000个） |

## 使用前请注意

1. A/B/C是本研究的评价等级（A≥80，40≤B<80，C<40），**不等同于**SL/Z 679-2015的一类/二类/三类堤，不能替代安全鉴定结论。
2. 模型目前只在合成样本上验证了计算一致性和区分能力，尚未用实际堤段鉴定结论标定。
3. 服务不做渗流和稳定计算：比降、安全系数由调用方提供，且应对应同一水位工况。
4. 巡检证据只能传入**人工复核确认**的事件；巡检未覆盖或过期时C3按缺失处理，这不等于“未发现渗漏”。
5. 资料缺失不会被当成安全：缺失的定性指标按缺失处理并在响应中列出；“不涉及”“无险情记录”等必须显式填写。
6. 没有资料的指标不要用假设值填满（会使得分偏乐观）。v1.1 起安全系数、冲刷深度可不填，沉降情况不明时填 `soft_foundation_status: "unknown"`；对应门控在响应的 `gates_not_checked` 中列出。示例见 `examples/request_data_supported.json`。

## 版本

| 项目 | 值 |
|---|---|
| 接口版本 | 1.2.0（变更见 `docs/01_code_description.md` 第7节） |
| 发布日期 | 2026-10-25 |
| safety_evaluation.py | sha256 89808cfe9c4393b42074ca39a209820d5be3ee5ac06aa74a9442ed34b0b9f7bb |
| failure_response_barrier_model.py | sha256 c031bd3a71d38dd88abe04bec4b481b618b019214047a5b0ddbb3d921f8f62aa |
| failure_mode_indicator_matrix.json | sha256 6b4e5ebf8100c4addc0c2b690badd9db73e5546c80699bac31324cb771b6c088 |
