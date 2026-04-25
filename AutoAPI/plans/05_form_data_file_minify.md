# Form Data File Minify / 收缩 `form_data.file`

## 1. Purpose / Big Picture

完成后，AutoAPI 的 `form_data.kind=file` 会收敛成当前产品真正需要的极简模型：

- 用户只写 `name + path`
- `kind` 继续保留，取值仍为 `field / file`
- 不再把 `source / filename / content_type` 暴露成用户字段

## 2. Scope

### In scope

- 新增本次 ExecPlan
- 调整 `RequestResolver` 的 `form_data file` 解析逻辑
- 更新 `p0_minimal` 示例资产与测试
- 更新 PRD、技术设计、当前状态、决策记录和讲解文档

### Out of scope

- 不改 `binary` 模型
- 不改 `reading_house`
- 不新增上传能力

## 3. Progress

- [x] 阅读当前实现、测试和文档
- [x] 新建本次 ExecPlan
- [x] 调整 `RequestResolver` 的 `form_data file` 解析
- [x] 更新示例资产
- [x] 更新测试
- [x] 更新 PRD / 设计 / 决策 / 讲解文档
- [x] 记录 retrospective

## 4. Surprises & Discoveries

- 当前 `form_data.kind=file` 已经在代码、PRD、讲解文档和 `p0_minimal` 里多处展开，收口必须一起改。
- `binary` 和 `form_data(file)` 不是同一条请求路径，不能一起简化。

## 5. Decision Log

- `form_data.kind=file` 的正式用户字段收敛为 `name + path`
- `kind` 保留，取值固定为 `field / file`
- `source / filename / content_type` 从 `form_data.kind=file` 主模型移除

## 6. Context and Orientation

相关文件：

- `Engine/request_resolver.py`
- `Tests/test_repository.py`
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `docs/product_requirements.md`
- `docs/request_02_form_modes_explanation.md`

## 7. Plan of Work

先改 `RequestResolver`，把 file item 解析逻辑收缩成只依赖 `path`。随后同步更新 `p0_minimal` 示例和测试，再收口 PRD、技术设计、当前状态、决策记录和讲解文档，最后做静态检查并写 retrospective。

## 8. Concrete Steps

预计修改文件：

- `plans/05_form_data_file_minify.md`
- `Engine/request_resolver.py`
- `Tests/test_repository.py`
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `docs/product_requirements.md`
- `docs/technical_design_v1.md`
- `docs/current_state.md`
- `docs/decision_log.md`
- `docs/request_02_form_modes_explanation.md`

## 9. Validation and Acceptance

- `form_data.kind=file` 的示例和文档只保留 `name + path`
- `RequestResolver` 不再要求 `source`
- 测试仍能验证 file 上传和 mixed multipart
- `git diff --check` 通过

## 10. Idempotence and Recovery

- 文档、示例和测试修改可重复执行
- 本次不涉及破坏性命令

## 11. Outcomes & Retrospective

- 已完成 `form_data.kind=file` 的模型收敛，执行器、示例、测试和文档都已统一切到 `name + path`。
- `RequestResolver` 不再要求 `source`，也不再读取 `filename/content_type`；上传文件名默认取本地文件名，content type 由实现层推导。
- `p0_minimal` 的文件上传示例和测试已全部更新，不保留双模型。
- 已更新 PRD、技术设计、当前状态、决策记录和实现讲解文档。
- 已完成静态检查：
  - `git diff --check -- plans/05_form_data_file_minify.md Engine/request_resolver.py Tests/test_repository.py examples/p0_minimal/Data/apis.yaml examples/p0_minimal/Data/cases.yaml docs/product_requirements.md docs/technical_design_v1.md docs/current_state.md docs/decision_log.md docs/request_02_form_modes_explanation.md`
- 未做运行时验证：
  - 当前 shell 中无 `python`，需由用户在 Windows `.venv` 里执行 `validate` 和 `pytest`。
