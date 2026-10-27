# HTTP接口说明

## 1 对接方式建议

推荐**HTTP + JSON**对接：评价服务单独部署，调用方系统（数字孪生平台、业务系统、脚本）按评价单元发起请求。

| 方式 | 适用 | 说明 |
|---|---|---|
| HTTP单个评价 `POST /api/v1/evaluate` | 平台在线调用（推荐） | 与调用方语言无关；模型版本集中在服务端，可通过 `/health` 核对 |
| HTTP批量评价 `POST /api/v1/evaluate/batch` | 全线定期评价、历史回算 | 一次≤1000个单元，单项失败不影响其他项 |
| Python库 `from levee_eval import evaluate` | 调用方本身是Python程序 | 输入输出与HTTP完全相同，见第9节 |

服务是**纯函数、无状态**的：同一请求体得到相同结果（只有 `provenance.evaluated_at` 不同），不保存任何请求数据，可以安全重试，也可以水平扩展多个实例。

## 2 基本约定

- 基础地址：`http(s)://<服务地址>/api/v1`，开发服务器默认 `http://127.0.0.1:8080`。
- 编码：请求和响应都是UTF-8 JSON；POST请求必须带 `Content-Type: application/json`。
- 字段名：英文snake_case；枚举值（分档名称、险情类型等）使用中文，须与参数字典完全一致。
- 数值：使用JSON数字，不要用字符串（`36.84` 而不是 `"36.84"`）；单位以参数字典为准（m、cm、cm/s、a）。
- 鉴权（可选）：服务端设置环境变量 `LEVEE_EVAL_API_KEY` 后，除 `/health` 外的请求都必须带请求头 `X-API-Key`。
- 追踪：请求头 `X-Request-ID`（可选）会原样出现在响应头和服务日志中；不传时服务端生成一个。业务层的编号请放在请求体 `request_id`，它会原样返回。
- 超时：单个评价约1 ms，1000个单元的批量约1 s（4核机器实测）。客户端超时建议单个10 s、批量60 s。
- 兼容性：1.x版本只做新增，调用方应忽略不认识的响应字段。

## 3 接口列表

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 健康检查，返回版本和模型文件sha256；不需要API Key |
| GET | `/api/v1/meta` | 指标名称与权重、分档赋分、失效模式权重、等级阈值、常数 |
| GET | `/api/v1/openapi.json` | OpenAPI 3.0文档（可导入Swagger UI、Apifox、Postman） |
| POST | `/api/v1/evaluate` | 评价一个单元 |
| POST | `/api/v1/evaluate/batch` | 批量评价，请求体 `{"items": [请求, ...]}` |

两个POST接口都支持查询参数 `detail`：`full`（默认）返回全部失效模式的指标贡献；`summary` 省略 `result.contributions_by_mode`，响应体积约减半，批量回算时建议使用。

## 4 请求体

请求体按资料来源分组，完整字段（类型、单位、范围、对应指标、模型内部字段名）见 `03_parameter_dictionary.md`。

| 分组 | 必填 | 内容 | 通常来自 |
|---|---|---|---|
| `section` | 是 | 编号、河堤/湖堤、堤顶高程、设计洪水位、顶宽、内外坡比、堤基类型、控制土层/土层表 | 设计资料、地勘报告 |
| `computation` | 是 | 堤基/堤身/接触面渗透比降，背水坡与临水坡抗滑安全系数（同一水位工况） | 第4章渗流与稳定计算、复核计算 |
| `survey` | 是 | 堤脚冲刷深度，软基沉降与沉降差（非软基段可不填） | 测量与检查 |
| `records` | 是 | 填土质量、穿堤建筑物检测结论、历史险情列表 | 工程台账、安全检测报告 |
| `qualitative` | 否 | 定性指标结论：分档名称或0～100分 | 现场检查、管理考核 |
| `calculated` | 否 | 防洪标准重现期、越浪量、穿堤建筑物复核计算量 | 复核计算 |
| `inspection` | 否 | 巡检覆盖状态和已确认事件（或汇总证据） | 无人机/人工巡检系统 |
| `options` | 否 | α、λ，一般不改 | — |

最小可用请求（不含定性指标和巡检，缺失项会在响应中列出）：

```json
{
  "request_id": "demo-0003",
  "section": {
    "section_id": "DEMO-K0+500", "is_lake_levee": false,
    "crest_elevation_m": 36.84, "design_flood_level_m": 34.04,
    "crest_width_m": 8.5, "outer_slope_ratio": 3.0, "inner_slope_ratio": 3.2,
    "foundation_class": "B",
    "control_layer": {"name": "粉细砂（合成示例）", "Gs": 2.65, "e": 0.70}
  },
  "computation": {"foundation_gradient": 0.82, "body_gradient": 0.30, "contact_gradient": 0.45,
                  "back_slope_fos": 1.42, "front_slope_fos": 1.38},
  "survey": {"scour_depth_m": 0.2, "soft_foundation_settlement_cm": null},
  "records": {"fill_quality": "质量一般", "crossing_structure_class": "不涉及",
              "historical_dangers": [{"type": "蚁穴", "reinforced": true, "severity": "轻微"}]}
}
```

完整请求见 `examples/request_full.json`。

几个容易出错的地方：

- **坡比**填1:m中的m（1:3.0填 `3.0`）。
- **没有的东西要明说**：无穿堤建筑物填 `"不涉及"`；已核查无历史险情传 `[]`；非软基段沉降填 `null` 或不填。服务不会把“没填”当成“没问题”。
- **定性指标**可以填分档名称（如 `"E4": "基本满足"`），也可以直接填0～100分；不清楚的指标**不要填**，按缺失处理比随意填“良好”更真实。
- 未声明的字段会报 `unknown_field`，可以借此发现拼写错误。

### 只用有资料支撑的输入（推荐）

没有资料的指标**不要用假设值填满**：模型对未填的指标按缺失处理，在所属失效模式内按其余指标重新分配权重；用“良好”之类的假设值填进去会使得分偏乐观。v1.1 起下列输入也可以不填：

| 输入 | 不填时 | 结果中的体现 |
|---|---|---|
| `computation.back_slope_fos`、`front_slope_fos` | D1、D2缺失，不做该侧边坡稳定门控 | `missing_indicators`、`gates_not_checked`、`warnings`（`input_missing_no_gate`） |
| `survey.scour_depth_m` | D3缺失，不做冲刷门控；有未加固的重大险情记录时D3仍为0分 | 同上 |
| 沉降资料（填 `survey.soft_foundation_status: "unknown"`） | A5缺失，不做沉降门控 | 同上 |

注意：沉降量不填且不写 `soft_foundation_status` 时，仍按“非软基段”处理，A5计100分。沉降情况不明时务必填 `"unknown"`。

渗流指标 C1、C4、C5 的三个比降仍为必填，这是评价的核心。示例见 `examples/request_data_supported.json`：只含断面、控制土层、三个比降、地勘台账结论、防洪标准和“不涉及”项，不含安全系数、冲刷深度、沉降和巡检。

## 5 巡检证据

巡检证据决定C3（管涌隐患）得分和观测门控，按以下规则填写：

1. **覆盖状态** `inspection.coverage`：评价单元被有效期内的巡检完整覆盖时填 `complete`；未覆盖或巡检已过期填 `none`（或不传 `inspection`）。`none` 时C3按缺失处理、不触发门控，响应中给出 `inspection_missing` 提示——这**不等于**“未发现渗漏”。
2. **只传已确认事件**：算法候选、误报、未复核目标都不能传入。覆盖完整但没有确认事件时传 `"confirmed_events": []`，C3得100分。
3. **两种模式**：
   - `events`（默认，推荐）：逐条传入已确认事件的位置类型、重复次数和征兆（带砂、浑水、冒水、集中成簇），由服务按交付规则汇总；
   - `aggregated`：调用方已按同一规则算好加权密度、证据等级和门控上限时使用，服务只做C3赋分和门控。
     三者须符合下面的规则（0级、1级无门控，2级为B，3级为C；密度为0当且仅当0级），否则返回422。

events模式的汇总规则（交付代码原样）：

- 每个事件的加权值 = 位置权重 × 重复权重。位置权重：普通堤身/堤身/堤坡1.0，堤脚/坡脚1.2，穿堤建筑物/建筑物附近1.3，结合部/历史险情附近1.5；重复权重：1次1.0，2次1.2，≥3次1.5。
- 加权密度 = 100 × Σ加权值 / 评价段长度（点/100 m），`segment_length_m` 默认100 m。
- C3得分：密度0→100，≤1→80，≤2→60，≤4→40，>4→0。
- 证据等级与门控：有严重征兆、任一事件重复≥3次或密度>3 → 3级，上限C；位于敏感位置（堤脚、坡脚、穿堤建筑物附近、结合部、历史险情附近）、≥2个事件、重复2次或密度>1 → 2级，上限B；其余单点 → 1级，只进C3评分。

```json
"inspection": {
  "coverage": "complete", "mode": "events", "segment_length_m": 100,
  "confirmed_events": [
    {"position": "堤脚", "repeat_count": 1, "sand": false, "muddy": false, "spouting": false, "clustered": false}
  ]
}
```

## 6 响应体

```json
{
  "request_id": "demo-0001",
  "section_id": "DEMO-K0+500",
  "api_version": "1.3.2",
  "model": {"name": "...", "files": {"safety_evaluation.py": "89808c...", "...": "..."}},
  "result": {
    "score": 67.5529, "grade": "B", "grade_label": "基本安全",
    "model_grade": "B", "grade_after_observation_gate": "B",
    "gate_reasons": ["C1堤基渗透比降: i/i_cr=0.84接近临界"],
    "gates_not_checked": [],
    "rho": 0.324471,
    "dominant_mode": {"code": "seepage", "name": "渗流破坏"},
    "barrier": {"ability": 0.71032, "coverage": 1.0, "lambda": 0.5},
    "observation_gate": {"cap": "B", "note": "无人机渗漏点位于敏感部位或多点出现，最高等级限制为B级"},
    "inspection_evidence": {"mode": "events", "weighted_density_per_100m": 1.2, "evidence_level": 2, "...": "..."},
    "mode_responses": {"seepage": {"name": "渗流破坏", "weight": 0.408463, "raw": 0.417832, "adjusted": 0.453064,
                                   "basis": {"direct_indicators": ["C1", "C4", "C5"], "direct_missing": [], "...": "..."}}, "...": {}},
    "indicator_scores": {"A1": 100, "A2": 80, "...": "...", "C3": 60.0},
    "missing_indicators": [],
    "indicator_sources": {"A1": "design_survey", "C1": "computed", "A2": "records", "B2": "qualitative", "A8": "not_applicable", "...": "..."},
    "dominant_mode_contributions": [
      {"indicator": "C1", "score": 28.6231, "risk_response": 0.844848, "weight_in_mode": 0.235054,
       "contribution": 0.198585, "contribution_rate": 0.475275, "source": "physical_response"}
    ],
    "contributions_by_mode": {"overtopping": ["..."], "seepage": ["..."]},
    "seepage_checks": {"control_layer": {"name": "粉细砂（合成示例）", "Gs": 2.65, "e": 0.7},
                       "C1": {"gradient": 0.82, "critical_gradient": 0.970588, "ratio": 0.844848, "state": "near_critical"}}
  },
  "warnings": [{"code": "not_applicable_scored_100", "message": "无穿堤建筑物（不涉及），A3按交付模型编码为100分", "indicator": "A3"}],
  "notice": "A/B/C为本研究评价等级……",
  "provenance": {"evaluated_at": "2026-10-22T00:00:00+00:00", "input_sha256": "..."}
}
```

（上面为节选，数值以 `examples/response_full.json` 为准。）

界面展示建议：

- 面向非专业用户的简化界面：结论直接显示 `conclusion_text`，等级显示 `grade` + `grade_label`，原因列表显示 `gate_details[].plain`；其余字段放进“查看详情”；
- 术语：接口里的“门控”（gate）是一条判定规则，不是参数值——某项关键指标超过限值时，等级最高只能为B或C，与综合得分无关。界面上建议称为“限级”，例如“限级条件：堤基渗透比降达到临界，最高C级”；
- 主结论显示 `grade`、`grade_label`、`score` 和 `dominant_mode.name`；
- `gate_reasons` 非空时一并显示——它说明等级为什么被压低，比得分更重要；
- `grade` 与 `model_grade` 不同时，提示“等级经门控下调”；
- `dominant_mode_contributions` 前3项可作为“主要原因”；
- `warnings` 应展示给评价人员，尤其是 `inspection_missing`、`input_missing_no_gate` 和 `indicators_missing`；
- `gates_not_checked` 非空时，在门控检查中把这些项标为“未检查（缺资料）”，不要显示成“通过”；
- 失效模式的 `basis.direct_missing` 非空时（例如边坡失稳缺D1、D2），在该模式旁标“依据不足”，提醒其响应值只来自间接指标；
- 每项指标按 `indicator_sources` 标注资料来源（中文名取 `/api/v1/meta` 的 `indicator_source_labels`）；为 `missing` 的指标不在明细中逐行显示，用一行列出“无资料、未参与评价”的指标即可；
- `notice` 中的等级说明应随结果一起展示或在报告中注明。

`warnings[].code` 取值：

| code | 含义 |
|---|---|
| `inspection_missing` | 无有效巡检，C3按缺失处理，不触发观测门控 |
| `inspection_ignored` | coverage=none时传入的事件或汇总证据未参与计算 |
| `not_applicable_scored_100` | “不涉及”的A3、非软基段的A5按交付模型编码为100分 |
| `derived_from_records` | A6由空的历史险情列表推定、A7由堤基类型推定 |
| `indicators_missing` | 列出缺失指标（未作满分处理） |
| `non_default_option` | 修改了α或λ，结果与标准配置不可直接比较 |
| `input_missing_no_gate` | 未提供安全系数、冲刷深度或沉降资料，对应指标缺失、未做该项门控（v1.1） |

## 7 错误处理

错误响应统一为：

```json
{
  "error": {
    "code": "validation_failed",
    "message": "请求字段校验未通过",
    "details": [
      {"field": "section.crest_elevation_m", "reason": "type_number_required"},
      {"field": "computation.foundation_gradient", "reason": "required"},
      {"field": "records.fill_quality", "reason": "not_in_enum", "allowed": ["质量较好", "质量一般", "质量较差"]}
    ]
  },
  "trace_id": "5b0c6c2e..."
}
```

| HTTP状态 | 处理建议 |
|---|---|
| 200 | 成功 |
| 400 | 请求体不是合法JSON或detail参数错误，修正后重发 |
| 401 | 检查 `X-API-Key` |
| 404 / 405 | 检查路径和方法 |
| 413 | 请求体超过上限（默认5 MB），拆分批量请求 |
| 415 | 补上 `Content-Type: application/json` |
| 422 | 按 `details` 逐项修正字段；**不要重试原请求** |
| 500 | 服务内部错误，可退避重试一次；仍失败时凭 `trace_id` 联系维护方 |

校验会一次性返回所有字段错误（交叉规则在基本字段全部合法后再检查）。`reason` 的全部取值见参数字典第4节。

## 8 批量接口

用户用 Excel 一次填多个断面时，可用 `excel_import/levee_excel.py` 把模板转成本接口的请求体，并把结果和错误对回 Excel 行号，见 `docs/05_excel_import.md`。

```
POST /api/v1/evaluate/batch?detail=summary
{"items": [请求1, 请求2, ...]}        最多1000项
```

响应：

```json
{
  "api_version": "1.3.2", "count": 3, "succeeded": 2, "failed": 1,
  "results": [
    {"index": 0, "ok": true, "response": {"request_id": "demo-0001", "result": {"...": "..."}}},
    {"index": 1, "ok": true, "response": {"...": "..."}},
    {"index": 2, "ok": false, "request_id": "demo-0004",
     "error": {"code": "validation_failed", "message": "请求字段校验未通过", "details": ["..."]}}
  ]
}
```

- 单项失败不影响其他项，整体仍返回200；请按 `index` 或 `request_id` 对应结果。
- 只有请求体本身不合规（不是 `{"items": [...]}`、为空或超过1000项）时整体返回422。
- 1000项、detail=full的响应约11 MB，建议批量时使用 `detail=summary`（约4.7 MB）。

## 9 调用示例

curl：

```bash
curl -X POST http://127.0.0.1:8080/api/v1/evaluate \
     -H "Content-Type: application/json" -H "X-API-Key: <密钥>" \
     --data-binary @examples/request_full.json
```

更多见 `examples/curl_examples.sh`。

Python（标准库，含重试处理的完整版见 `examples/client_example.py`）：

```python
import json, urllib.request

req = json.load(open("examples/request_full.json", encoding="utf-8"))
r = urllib.request.Request("http://127.0.0.1:8080/api/v1/evaluate",
                           data=json.dumps(req, ensure_ascii=False).encode("utf-8"),
                           headers={"Content-Type": "application/json"})
with urllib.request.urlopen(r, timeout=10) as resp:
    result = json.loads(resp.read())["result"]
print(result["score"], result["grade"], result["dominant_mode"]["name"], result["gate_reasons"])
```

JavaScript（浏览器或Node 18+；浏览器跨域调用需在服务端设置 `LEVEE_EVAL_CORS_ORIGINS`）：

```javascript
const resp = await fetch("http://127.0.0.1:8080/api/v1/evaluate?detail=summary", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": "<密钥>" },
  body: JSON.stringify(request),
});
const body = await resp.json();
if (resp.status === 422) console.table(body.error.details);
else console.log(body.result.grade, body.result.gate_reasons);
```

Python程序也可以不经HTTP直接调用，输入输出相同：

```python
import sys; sys.path.insert(0, "<对接包目录>")
from levee_eval import evaluate, validate, RequestInvalid

errors = validate(req)            # [] 表示合法
resp = evaluate(req)              # 不合法时抛出 RequestInvalid，.details 同HTTP 422
```

## 10 对接检查清单

- [ ] 用 `examples/request_full.json` 调通 `/evaluate`，结果与 `examples/response_full.json` 一致（`provenance.evaluated_at` 除外）；
- [ ] 没有资料的指标不填假设值；沉降情况不明时填 `soft_foundation_status: "unknown"`；
- [ ] `GET /health` 返回的模型sha256与 `01_code_description.md` 第3节一致；
- [ ] 本方数据的字段映射逐项对照参数字典核对单位（m/cm）、坡比写法、湖堤/河堤；
- [ ] 比降与安全系数取自同一水位工况；
- [ ] 无穿堤建筑物、无历史险情、非软基段都按约定显式填写；
- [ ] 巡检：只传已确认事件，过期按 `coverage="none"` 处理；
- [ ] 422的 `details` 能在本方系统中展示给数据维护人员；
- [ ] 界面或报告展示 `gate_reasons`、`warnings` 和 `notice`；
- [ ] 本方日志记录 `request_id`、`X-Request-ID` 和 `provenance.input_sha256`，便于追溯。
