# 输入输出参数字典

> 本文件由 `tools/gen_docs.py` 根据 `levee_eval/schema.py` 自动生成，请勿手工修改。
> 字段路径中 `[]` 表示数组元素；“必填”指其所在对象出现时必须给出。

## 1 输入字段

### 顶层

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `request_id` | string |  |  |  |  |  |  | 调用方请求编号，原样返回，便于日志关联 |

### section：评价单元基本信息

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `section` | object | 是 |  |  |  |  |  | 评价单元（代表断面）基本信息 |
| `section.section_id` | string | 是 |  |  |  |  | 桩号 | 断面或评价单元编号，如K0+500，原样返回 |
| `section.is_lake_levee` | boolean | 是 |  |  |  | B1 | 是否为湖堤 | 是否为湖堤；决定规范超高（湖堤2.5 m，河堤2.0 m） |
| `section.crest_elevation_m` | number | 是 | m |  |  | B1 | 堤顶高程_m | 堤顶高程 |
| `section.design_flood_level_m` | number | 是 | m |  |  | B1 | 设计洪水位_m | 设计洪水位 |
| `section.crest_width_m` | number | 是 | m | >0 |  | A1 | 堤顶宽度_m | 堤顶宽度（设计标准7.5 m） |
| `section.outer_slope_ratio` | number | 是 |  | >0 |  | A1 | 外坡坡比 | 临水坡（外坡）坡比1:m中的m（标准2.5） |
| `section.inner_slope_ratio` | number | 是 |  | >0 |  | A1 | 内坡坡比 | 背水坡（内坡）坡比1:m中的m（标准3.0） |
| `section.foundation_class` | string |  |  | A / B / C / D |  | A7 | 堤基类型 | 堤基类型（地勘分类）；未给出qualitative.A7时用于A7：C类70分、D类60分、其余100分 |
| `section.control_layer` | object |  |  |  |  | C1,C4,C5 |  | 渗流控制土层；与soil_layers至少给出其一 |
| `section.control_layer.name` | string |  |  |  |  |  | 控制土层名称 | 控制土层名称 |
| `section.control_layer.Gs` | number | 是 |  | ≥2，≤3.2 |  |  | 控制层Gs | 控制土层土粒比重 |
| `section.control_layer.e` | number | 是 |  | ≥0.1，≤3 |  |  | 控制层e | 控制土层孔隙比 |
| `section.control_layer.J_allow` | number |  |  | ≥0 |  |  | 控制渗透比降J_allow | 控制土层允许渗透比降（仅记录） |
| `section.soil_layers` | array |  |  |  |  |  |  | 土层参数表；未给control_layer时取临界比降最小的土层为控制层 |
| `section.soil_layers[].name` | string | 是 |  |  |  |  | 土层名称 | 土层名称 |
| `section.soil_layers[].Gs` | number | 是 |  | ≥2，≤3.2 |  |  | Gs | 土粒比重 |
| `section.soil_layers[].e` | number | 是 |  | ≥0.1，≤3 |  |  | e | 孔隙比 |
| `section.soil_layers[].thickness_m` | number |  | m | ≥0 |  |  | 厚度_m | 厚度 |
| `section.soil_layers[].k_cm_s` | number |  | cm/s | ≥0 |  |  | 渗透系数_cm_s | 渗透系数 |
| `section.soil_layers[].J_allow` | number |  |  | ≥0 |  |  | 允许渗透比降J_allow | 允许渗透比降 |

### computation：渗流与稳定计算结果

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `computation` | object | 是 |  |  |  |  |  | 渗流计算与边坡稳定复核结果（同一水位工况） |
| `computation.foundation_gradient` | number | 是 |  | ≥0 |  | C1 | 渗透比降i | 堤基渗透比降i（出口法向出逸梯度） |
| `computation.body_gradient` | number | 是 |  | ≥0 |  | C4 | 堤身渗透比降i | 堤身渗透比降 |
| `computation.contact_gradient` | number | 是 |  | ≥0 |  | C5 | 接触面渗透比降i | 堤基接触面渗透比降 |
| `computation.body_Gs` | number |  |  | ≥2，≤3.2 |  | C4 | 堤身Gs | 堤身土粒比重（缺省取控制层） |
| `computation.body_e` | number |  |  | ≥0.1，≤3 |  | C4 | 堤身e | 堤身孔隙比（缺省取控制层） |
| `computation.back_slope_fos` | number，可null |  |  | >0 |  | D1 | 背水坡FoS_正常 | 背水坡抗滑稳定安全系数（正常运用）；未做稳定计算时不填或null：D1按缺失处理，不做背水坡稳定门控 |
| `computation.front_slope_fos` | number，可null |  |  | >0 |  | D2 | 临水坡FoS | 临水坡抗滑稳定安全系数（稳态）；未做稳定计算时不填或null：D2按缺失处理，不做临水坡稳定门控 |

### survey：测量与检查

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `survey` | object | 是 |  |  |  |  |  | 测量与检查资料 |
| `survey.scour_depth_m` | number，可null |  | m | ≥0 |  | D3 | 冲刷深度_m | 堤脚冲刷深度；无测量资料时不填或null：D3按缺失处理（有未加固的重大险情记录时仍计0分），不做冲刷门控 |
| `survey.soft_foundation_settlement_cm` | number，可null |  | cm | ≥0 |  | A5 | 软基段_沉降量_cm | 软基段沉降量；缺省或null时按soft_foundation_status处理 |
| `survey.soft_foundation_settlement_diff_cm` | number，可null |  | cm | ≥0 |  | A5 | 软基段_沉降差_cm | 软基段沉降差；给出沉降量时必填 |
| `survey.soft_foundation_status` | string |  |  | non_soft / unknown | "non_soft" | A5 |  | 未给沉降量时说明原因：non_soft＝非软基段（默认，A5按100分并提示）；unknown＝软基情况或沉降资料未知（A5按缺失处理，不做沉降门控）。给出沉降量时不得填写 |

### records：台账与检查结论

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `records` | object | 是 |  |  |  |  |  | 台账与检查结论 |
| `records.fill_quality` | string | 是 |  | 质量较好 / 质量一般 / 质量较差 |  | A2 | 填土质量 | 堤身填土质量（地勘结论） |
| `records.crossing_structure_class` | string | 是 |  | 一类 / 二类 / 三类 / 四类 / 1类 / 2类 / 3类 / 4类 / 加固 / 改建 / 重建 / 不涉及 |  | A3 | 检测结论 | 穿堤建筑物安全检测结论；无穿堤建筑物填“不涉及”（按交付模型编码为100分，并给出提示） |
| `records.historical_dangers` | array | 是 |  |  |  | A6,D3 |  | 本评价单元的历史险情与隐患记录；已核查无记录时传空数组 |
| `records.historical_dangers[].type` | string | 是 |  |  |  |  | 险情类型 | 险情类型，如管涌、散浸、渗漏、崩岸、蚁穴、隐患 |
| `records.historical_dangers[].reinforced` | boolean | 是 |  |  |  |  | 是否已加固 | 是否已加固处置 |
| `records.historical_dangers[].severity` | string |  |  | 无 / 轻微 / 中度 / 严重 |  |  | 严重程度 | 严重程度 |

### qualitative：定性指标结论

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `qualitative` | object |  |  |  |  |  | 待输入指标 | 定性指标结论：键为指标代码，值为分档名称或0～100分；未给出的指标按缺失处理（不默认100分） |

### calculated：可替代定性结论的计算量

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `calculated` | object |  |  |  |  |  |  | 可替代定性结论的计算量（qualitative中给出同一指标时以qualitative为准） |
| `calculated.flood_standard` | object |  |  |  |  | B2 |  | 防洪标准 |
| `calculated.flood_standard.current_return_period_a` | number | 是 | a | ≥0 |  |  | 现状防洪标准_年 | 现状防洪标准（重现期） |
| `calculated.flood_standard.approved_return_period_a` | number | 是 | a | ≥0 |  |  | 批复防洪标准_年 | 批复防洪标准（重现期） |
| `calculated.overtopping` | object |  |  |  |  | B3 |  | 越浪量复核 |
| `calculated.overtopping.discharge` | number | 是 | L/(s·m) | ≥0 |  |  | 越浪量 | 越浪量 |
| `calculated.overtopping.allowable_discharge` | number | 是 | L/(s·m) | ≥0 |  |  | 允许越浪量 | 允许越浪量 |
| `calculated.crossing_structure` | object |  |  |  |  | B4,D4 |  | 穿堤建筑物复核计算 |
| `calculated.crossing_structure.flood_defence_elevation_m` | number |  | m |  |  |  | 穿堤建筑物挡洪高程_m | 挡洪高程（与required_elevation_m同时给出用于B4） |
| `calculated.crossing_structure.required_elevation_m` | number |  | m |  |  |  | 穿堤建筑物防洪要求高程_m | 防洪要求高程 |
| `calculated.crossing_structure.sliding_fos` | number |  |  | ≥0 |  |  | 穿堤抗滑安全系数 | 抗滑安全系数（D4需六项齐全） |
| `calculated.crossing_structure.overturning_fos` | number |  |  | ≥0 |  |  | 穿堤抗倾安全系数 | 抗倾安全系数 |
| `calculated.crossing_structure.bearing_fos` | number |  |  | ≥0 |  |  | 穿堤承载力安全系数 | 承载力安全系数 |
| `calculated.crossing_structure.sliding_fos_allow` | number |  |  | ≥0 |  |  | 穿堤抗滑允许安全系数 | 抗滑允许安全系数 |
| `calculated.crossing_structure.overturning_fos_allow` | number |  |  | ≥0 |  |  | 穿堤抗倾允许安全系数 | 抗倾允许安全系数 |
| `calculated.crossing_structure.bearing_fos_allow` | number |  |  | ≥0 |  |  | 穿堤承载力允许安全系数 | 承载力允许安全系数 |

### inspection：巡检证据

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `inspection` | object |  |  |  |  | C3 |  | 巡检证据（C3与观测门控）；缺省时C3按缺失处理 |
| `inspection.coverage` | string | 是 |  | complete / none |  |  |  | 巡检覆盖状态：complete为覆盖完整且在有效期内；none为未覆盖或过期（C3按缺失处理） |
| `inspection.mode` | string |  |  | events / aggregated | "events" |  |  | events：传入已确认事件，由服务按交付规则汇总；aggregated：传入已汇总的密度与门控 |
| `inspection.segment_length_m` | number |  | m | >0 | 100.0 |  |  | 评价段长度（events模式） |
| `inspection.confirmed_events` | array |  |  |  |  |  |  | 经人工复核确认的渗漏/管涌事件；events模式必填，无事件时传空数组；算法候选与误报不得传入 |
| `inspection.confirmed_events[].position` | string |  |  | 普通堤身 / 堤身 / 堤坡 / 堤脚 / 坡脚 / 穿堤建筑物 / 建筑物附近 / 结合部 / 历史险情附近 | "普通堤身" |  | 位置类型 | 位置类型（决定位置权重：普通1.0，堤脚1.2，建筑物附近1.3，结合部或历史险情附近1.5） |
| `inspection.confirmed_events[].repeat_count` | integer |  |  | ≥1 | 1 |  | 重复次数 | 同一位置出现次数 |
| `inspection.confirmed_events[].sand` | boolean |  |  |  | false |  | 带砂 | 带砂 |
| `inspection.confirmed_events[].muddy` | boolean |  |  |  | false |  | 浑水 | 浑水 |
| `inspection.confirmed_events[].spouting` | boolean |  |  |  | false |  | 冒水 | 冒水 |
| `inspection.confirmed_events[].clustered` | boolean |  |  |  | false |  | 集中成簇 | 集中成簇 |
| `inspection.aggregated` | object |  |  |  |  |  |  | 已汇总的巡检证据（aggregated模式） |
| `inspection.aggregated.weighted_density_per_100m` | number | 是 | 点/100 m | ≥0 |  |  | 加权渗漏点密度_点每100m | 加权渗漏点密度 |
| `inspection.aggregated.evidence_level` | integer | 是 |  | ≥0，≤3 |  |  | UAV证据等级 | 巡检证据等级0～3 |
| `inspection.aggregated.gate_cap` | string，可null |  |  | B / C |  |  | UAV门控等级上限 | 观测门控等级上限（B或C；不设门控时为null） |
| `inspection.aggregated.note` | string |  |  |  |  |  | UAV门控说明 | 门控说明 |

### options：模型参数

| 字段路径 | 类型 | 必填 | 单位 | 取值/范围 | 默认 | 对应指标 | 模型内部字段 | 说明 |
|---|---|---|---|---|---|---|---|---|
| `options` | object |  |  |  |  |  |  | 模型参数（一般不需改动；改动时响应中给出提示） |
| `options.alpha` | number |  |  | ≥0，≤1 | 0.45 |  |  | 短板系数α |
| `options.barrier_lambda` | number |  |  | ≥0，≤1 | 0.5 |  |  | 运行管理屏障强度λ |

### 交叉校验规则

- `section.control_layer` 与 `section.soil_layers` 至少给出其一；都给出时以 control_layer 为准。
- `section.foundation_class` 与 `qualitative.A7` 至少给出其一；都给出时A7以qualitative为准。
- 给出 `survey.soft_foundation_settlement_cm` 时必须同时给出 `soft_foundation_settlement_diff_cm`，且不得填写 `soft_foundation_status`。
- `inspection.coverage=complete` 且 `mode=events`（默认）时必须给出 `confirmed_events`（无事件传 `[]`），不得给出 `aggregated`；`mode=aggregated` 时必须给出 `aggregated`，不得给出 `confirmed_events`。
- aggregated模式下证据等级与门控上限须符合交付规则：0级、1级无门控（gate_cap为null或不给），2级为B，3级为C；加权密度为0当且仅当证据等级为0。
- 未声明的字段一律报 `unknown_field`，防止拼写错误被静默忽略。

## 2 定性指标分档与赋分

`qualitative` 的值可以是下表中的分档名称，也可以是0～100的数值得分。
B2、B3、B4、D4 未在 `qualitative` 中给出时，可由 `calculated` 中的计算量换算；两者都没有则按缺失处理。

| 指标 | 名称 | 分档：得分 |
|---|---|---|
| A4 | 护坡完好率 | 优：100；良：80；中：60；一般：60；差：40；极差：0 |
| A6 | 内部隐患 | 无：100；轻微：80；中度：60；严重：0 |
| A7 | 堤基不良地质处理 | 良好：100；一般：70；未处理：0；险情：0 |
| A8 | 结合部填筑止水质量 | 不涉及：100；密实：100；良好：100；轻微渗漏：70；集中渗漏：0；严重渗漏：0 |
| A9 | 跨堤交叉工程质量 | 不涉及：100；无影响：100；轻微影响：70；存在危险：0；危险：0 |
| B2 | 防洪标准符合性 | 符合：100；待复核：60；不符合：0 |
| B3 | 风浪爬高与越浪量复核 | 满足：100；待复核：60；略超标：70；严重超标：0；超标：0 |
| B4 | 穿堤建筑物防洪标准 | 不涉及：100；完全符合：100；符合：100；待复核：60；高程不足：60；不达标：0 |
| C2 | 排水设施有效性 | 通畅：100；一般：60；局部淤积：70；局部堵塞：70；失效：0 |
| C6 | 穿堤建筑物渗流稳定 | 不涉及：100；无渗漏：100；明显渗漏：60；失稳：0；带砂：0 |
| D4 | 穿堤结构安全系数 | 不涉及：100；全部满足：100；满足：100；临界状态：60；临界：60；不满足：0 |
| D5 | 堤身不均匀沉降与裂缝 | 无：100；轻微：70；明显：40；严重：0 |
| E1 | 监测设施完备性 | 完善：100；一般：80；差：40 |
| E2 | 管理制度健全性 | 健全：100；基本健全：70；不健全：40 |
| E3 | 维护记录完整性 | 完备：100；基本满足：70；缺失：0 |
| E4 | 应急预案与物资储备 | 完备：100；基本满足：70；严重缺失：0；缺失：0 |
| E5 | 隐患巡查与处置率 | 全部处置：100；部分处置：60；未执行：0 |

其他由台账字段换算的指标：

| 指标 | 来源字段 | 换算 |
|---|---|---|
| A2 填土质量 | records.fill_quality | 质量较好：100；质量一般：80；质量较差：60 |
| A3 穿堤建筑物完好性 | records.crossing_structure_class | 一类：100；二类：100；三类：70；四类：0；1类：100；2类：100；3类：70；4类：0；加固：100；改建：70；重建：0；不涉及：100 |
| A6 内部隐患 | qualitative.A6，否则records.historical_dangers | 多条记录取最低；有severity按A6分档；否则类型含“蚁”或“隐患”：未加固0、已加固80；其他类型：未加固60、已加固不扣分；无记录100 |
| A7 堤基不良地质处理 | qualitative.A7，否则section.foundation_class | C类70分，D类60分，A/B类100分 |
| D3 堤岸冲刷稳定性 | survey.scour_depth_m＋records.historical_dangers | 冲刷≥1.0 m或有未加固的重大险情记录（类型含“崩”、管涌、散浸、渗漏）：0；冲刷≥0.5 m或有已加固的重大险情记录：70；否则100。未给冲刷深度：有未加固的重大险情记录仍为0，否则缺失 |
| A5 软基段沉降 | survey.soft_foundation_settlement_cm、soft_foundation_settlement_diff_cm、soft_foundation_status | 沉降量≤15 cm且沉降差≤5 cm：100，否则0。未给沉降量：soft_foundation_status=non_soft（默认）按100分，unknown按缺失 |
| D1、D2 抗滑稳定 | computation.back_slope_fos、front_slope_fos | 按安全系数分段评分（见第5章）；未给安全系数：缺失，不做该侧稳定门控 |
| C3 管涌隐患（巡检） | inspection | 加权密度0：100；≤1：80；≤2：60；≤4：40；>4：0（点/100 m）；无有效巡检：缺失 |

巡检事件位置权重：普通堤身 1.0，堤身 1.0，堤坡 1.0，堤脚 1.2，坡脚 1.2，穿堤建筑物 1.3，建筑物附近 1.3，结合部 1.5，历史险情附近 1.5；重复2次×1.2，≥3次×1.5。

## 3 输出字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `request_id` | string/null | 调用方请求编号（原样返回） |
| `section_id` | string | 评价单元编号（原样返回） |
| `api_version` | string | 接口版本 |
| `model.files` | object | 模型文件名→sha256，用于确认服务端模型未被改动 |
| `result.score` | number | 安全得分S=100(1−ρ)，0～100 |
| `result.grade` | string | 最终评价等级A/B/C（得分分级→观测门控→硬约束门控，只降不升） |
| `result.grade_label` | string | 等级名称：安全/基本安全/不安全 |
| `result.model_grade` | string | 仅按得分分级的等级（A≥80，40≤B<80，C<40） |
| `result.grade_after_observation_gate` | string | 经巡检观测门控后的等级 |
| `result.gate_reasons` | string[] | 硬约束门控触发原因（交付模型原文；D3由险情记录触发时改写为说明记录的文字），为空表示未触发 |
| `result.gates_not_checked[]` | object[] | 因缺资料未做的门控检查：indicator、reason（如未给安全系数时的D1/D2、无有效巡检时的C3） |
| `result.rho` | number | 综合风险度量ρ=α·max(Rk)+(1−α)·Σwk·Rk |
| `result.dominant_mode.code / name` | string | 主控失效模式（屏障修正后响应最大者） |
| `result.barrier.ability / coverage / lambda` | number | 运行管理屏障能力Bm、信息覆盖度、屏障强度λ |
| `result.observation_gate.cap / note` | string/null | 巡检观测门控上限（B/C/null）及说明 |
| `result.inspection_evidence` | object/null | 巡检证据汇总：模式、加权密度、证据等级、事件明细；无有效巡检时为null |
| `result.mode_responses.<mode>` | object | 五类失效模式的权重、原始响应raw、屏障修正响应adjusted（0～1，越大越危险） |
| `result.indicator_scores.<code>` | number/null | 29项二级指标得分（0～100）；null为缺失 |
| `result.missing_indicators` | string[] | 缺失指标代码；缺失指标不作满分处理，在模式内按现有权重归一化 |
| `result.indicator_sources.<code>` | string | 各指标得分的资料来源：design_survey、computed、records、survey、survey_records、inspection、qualitative、calculated、not_applicable、missing；中文名见 /api/v1/meta 的 indicator_source_labels |
| `result.dominant_mode_contributions[]` | object[] | 主控模式内各指标的风险响应、模式内权重、贡献值和贡献率（降序） |
| `result.contributions_by_mode.<mode>[]` | object[] | 全部失效模式的指标贡献（detail=summary时省略） |
| `result.seepage_checks` | object | 控制土层及C1/C4/C5的比降、Terzaghi临界比降、i/i_cr与门控状态 |
| `warnings[]` | object[] | 提示：code、message、indicator（见02_http_api.md第6节） |
| `notice` | string | 等级含义与使用限制的固定说明 |
| `provenance.evaluated_at` | string | 评价时间（UTC，ISO 8601） |
| `provenance.input_sha256` | string | 请求体规范化JSON的sha256，用于追溯同一输入 |

失效模式代码：`overtopping` 漫顶失效，`seepage` 渗流破坏，`slope_instability` 边坡失稳，`scour` 冲刷破坏，`crossing_structure` 穿堤建筑物失效。

## 4 错误码

| HTTP状态 | error.code | 含义 |
|---|---|---|
| 400 | invalid_json / invalid_query | 请求体不是合法UTF-8 JSON；detail参数非法 |
| 401 | unauthorized | 启用API Key时缺少或错误的 X-API-Key |
| 404 | not_found | 路径不存在 |
| 405 | method_not_allowed | 方法不对（GET/POST） |
| 413 | payload_too_large | 请求体超过上限（默认5 MB） |
| 415 | unsupported_media_type | Content-Type 不是 application/json |
| 422 | validation_failed | 字段校验未通过，`error.details[]` 逐项给出 field 与 reason |
| 500 | internal_error | 服务内部错误，凭 trace_id 查日志 |

`error.details[].reason` 取值：required、unknown_field、type_<类型>_required、not_in_enum、below_minimum、above_maximum、unknown_indicator、score_out_of_range_0_100、category_or_score_required、control_layer_or_soil_layers_required、foundation_class_or_qualitative_A7_required、required_when_settlement_given、not_allowed_when_settlement_given、required_in_events_mode_empty_list_if_none、required_in_aggregated_mode、not_allowed_in_events_mode、not_allowed_in_aggregated_mode、inconsistent_with_evidence_level、inconsistent_with_density、too_many_items、empty。
