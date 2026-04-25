# Raw Subtypes / 补全 `raw` 剩余子类型

## 1. Purpose / Big Picture

完成后，AutoAPI 的 `body_mode=raw` 不再只支持 `raw_type=json`，而是补齐当前 PRD 已定义但尚未实现的剩余子类型：

- `text`
- `xml`
- `html`
- `javascript`

用户可观察到的结果：

- `ApiTemplate`、`ApiCase`、`ScenarioStep override` 可以稳定使用这些 `raw_type`
- `RequestResolver` 会把这些请求体映射到正确的 `requests` 低层参数
- history、失败输出和讲解文档会反映这些 `raw` 请求体的真实内容

## 2. Scope

### In scope

- `body_mode=raw`
- `raw.raw_type=text`
- `raw.raw_type=xml`
- `raw.raw_type=html`
- `raw.raw_type=javascript`
- 对应的 case / step override
- 对应示例资产、测试、讲解文档和当前状态文档

### Out of scope

- `raw_type=json` 之外的其它新请求模式
- `binary`
- `form_data`
- `form_urlencoded`
- `auth / cookies`
- 自动推断复杂 `Content-Type` 策略
- 严格字段 schema 校验

## 3. Progress

- [x] 阅读 PRD、技术设计、当前状态和现有 `raw(json)` 实现
- [x] 新建本次 ExecPlan
- [x] 明确 `raw` 剩余子类型的 requests 映射规则
- [x] 调整 `RequestResolver`
- [x] 更新示例资产
- [x] 更新测试
- [x] 更新当前状态与讲解文档
- [x] 记录 retrospective

## 4. Surprises & Discoveries

- PRD 已经定义了 `raw_type=text/xml/html/javascript`，但当前实现只支持 `json`。
- 技术设计文档只写到了“根据 `raw.raw_type` 决定 `json` 或 `data`”，还没有把每个子类型的映射规则写死。
- `RequestResolver` 当前对 `raw` 的入口已经集中在 `_apply_body_by_mode`，补这一批能力不会影响其它请求模式。

## 5. Decision Log

- `raw_type=json` 继续映射到 `kwargs["json"]`
- `raw_type=text/xml/html/javascript` 统一映射到 `kwargs["data"]`
- `raw_type=text/xml/html/javascript` 的 `raw.content` 以字符串为主；若传入非字符串，执行层统一转成 `str(...)`
- 自动补默认 `Content-Type`：
  - `text` -> `text/plain`
  - `xml` -> `application/xml`
  - `html` -> `text/html`
  - `javascript` -> `application/javascript`
- 若用户已显式写了 `headers.Content-Type`，执行层不覆盖用户值
- `raw` 与 `form_data / form_urlencoded / binary` 继续保持互斥，不支持“同一请求里同时发 JSON body 和 form/multipart body”

## 6. Context and Orientation

相关文件：

- `Engine/request_resolver.py`：当前只支持 `raw(json)`
- `Tests/test_repository.py`：已有 `raw(json)` 测试，可继续扩展
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `docs/product_requirements.md`
- `docs/technical_design_v1.md`
- `docs/current_state.md`

## 7. Plan of Work

先把剩余 `raw` 子类型的低层映射规则定清楚，再改 `RequestResolver`。随后补示例和测试，最后同步文档与当前状态。实现时不改其它请求模式，避免把 `raw` 补全和更大范围的请求模型改造混在一起。

## 8. Concrete Steps

预计修改文件：

- `plans/06_raw_subtypes.md`
- `Engine/request_resolver.py`
- `Tests/test_repository.py`
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `docs/current_state.md`
- `docs/01_request_query_path_raw.md` 或新增更合适的讲解文档

## 9. Validation and Acceptance

验收标准：

- `raw(text/xml/html/javascript)` 都能进入正式执行链
- `raw(json)` 现有行为不回退
- `case` 和 `scenario step override` 都能覆盖这些 `raw` 子类型
- 失败输出里可以看到 `raw` 请求体摘要
- `git diff --check` 通过

运行时验证：

- 当前 shell 中无 `python`，运行时验证仍由用户在 Windows `.venv` 完成

## 10. Idempotence and Recovery

- 代码、测试、示例和文档修改可重复执行
- 若某个 `raw_type` 的映射规则需要调整，可集中在 `RequestResolver` 一个入口修正
- 本次不涉及数据迁移和破坏性命令

## 11. Outcomes & Retrospective

- 已完成 `raw(text/xml/html/javascript)` 的执行链补全。
- `RequestResolver` 现在按 `raw_type` 分流：
  - `json` -> `kwargs["json"]`
  - `text/xml/html/javascript` -> `kwargs["data"]`
- 已实现默认 `Content-Type` 注入，且用户显式写了 `headers.Content-Type` 时不覆盖用户值。
- 已补充 `p0_minimal` 的 raw 探针接口和 4 个 raw case。
- 已补充测试，覆盖：
  - `raw(text)` 默认头
  - `raw(xml)` 默认头
  - `raw(html)` 默认头
  - `raw(javascript)` 默认头
  - 显式 `Content-Type` 不被覆盖
  - 非字符串 `raw.content` 稳定转成字符串
- 已新增实现讲解文档：`docs/request_06_raw_subtypes_explanation.md`

已完成静态验证：

- `git diff --check -- plans/06_raw_subtypes.md Engine/request_resolver.py Tests/test_repository.py examples/p0_minimal/Data/apis.yaml examples/p0_minimal/Data/cases.yaml docs/current_state.md docs/technical_design_v1.md docs/decision_log.md docs/request_06_raw_subtypes_explanation.md`

未完成验证：

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

原因：

- 当前 shell 中无 `python`，运行时验证需要由用户在 Windows `.venv` 完成。
