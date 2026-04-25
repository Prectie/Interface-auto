# Request Model Cleanup / 收口

## 1. Purpose / Big Picture

完成后，AutoAPI 的代码与文档会对“产品层请求模型”和“传输层 requests kwargs”做清晰分层：

- 产品层统一使用 `path_params / query / cookies / auth / body_mode / form_data / form_urlencoded / raw / binary`
- 传输层继续允许 `requests` 使用 `params / files / data / json`
- `docs/current_state.md` 会反映 2026-04-24 的真实实现状态，不再停留在 `body_type=json/data` 阶段
- 请求模型讲解文档不再混淆旧产品字段和底层 `requests` 字段

## 2. Scope

### In scope

- 新增本次 ExecPlan
- 更新 `docs/current_state.md` 的当前状态章节
- 清理讲解文档中的旧产品层术语混淆
- 清理少量示例 / 注释中的旧 `params/body_type/files` 表达
- 保持 `requests` 低层 `params/files` 用法不变

### Out of scope

- 不新增请求能力
- 不重构 `Transport`
- 不把 `PreparedRequest.kwargs` 改成非 `requests` 风格
- 不做 P1/P2 能力
- 不做 Allure 自动 HTML 报告实现

## 3. Progress

- [x] 阅读 PRD、current_state、technical_design、现有代码
- [x] 新建本次 ExecPlan
- [x] 更新 `docs/current_state.md` 当前状态
- [x] 清理请求模型讲解文档中的旧产品层术语
- [x] 清理少量代码示例 / 注释
- [x] 记录 retrospective

## 4. Surprises & Discoveries

- `docs/current_state.md` 顶部状态仍停留在 `body_type=json/data` 阶段，和当前实现不一致。
- 代码中仍出现 `params/files`，但大多数属于 `requests` 低层 kwargs，而不是产品层旧模型回退。
- 两份请求模型讲解文档里都存在“产品层旧术语”和“传输层 kwargs 名称”混用，需要澄清。

## 5. Decision Log

- 本次收口只清“产品层请求模型”残留旧术语，不清理 `requests` 低层 `params/files`。
- `PreparedRequest.kwargs` 保持贴近 `requests`，否则会把调试与发送链分裂成两套低层结构。

## 6. Context and Orientation

相关文件：

- `docs/current_state.md`：当前状态文档，顶部状态过时
- `docs/request_02_form_modes_explanation.md`：第二阶段讲解，部分表述仍引用旧产品层术语
- `docs/request_03_auth_binary_explanation.md`：第三阶段讲解，需要明确 `params` 是 `requests params`
- `Core/data_processing.py`：`__main__` 示例仍用旧 `params/data` 演示
- `Engine/request_resolver.py`：实现已是新产品模型，内部 `kwargs["params"] / kwargs["files"]` 属于传输层

## 7. Plan of Work

先补 ExecPlan，然后更新当前状态文档，使其准确反映已经完成的三个请求模型阶段。随后清理两份讲解文档和少量代码示例，把“产品层 request 字段”和“requests kwargs”明确分层。最后更新 ExecPlan retrospective。

## 8. Concrete Steps

工作目录：项目根目录

预计修改文件：

- `plans/04_request_model_cleanup.md`
- `docs/current_state.md`
- `docs/request_02_form_modes_explanation.md`
- `docs/request_03_auth_binary_explanation.md`
- `Core/data_processing.py`

验证方式：

- `git diff --check -- <modified files>`
- 人工检查 `docs/current_state.md` 是否准确描述当前请求模型实现
- 人工检查文档中旧产品层 `params/body_type/files` 是否已收敛为“旧术语背景说明”或“requests kwargs”语境

## 9. Validation and Acceptance

验收标准：

- `docs/current_state.md` 顶部状态明确写出已支持：
  - `query`
  - `path_params`
  - `form_urlencoded`
  - `form_data(field/file)`
  - `cookies`
  - `auth`
  - `binary`
- 文档不再把当前产品层请求模型描述成 `body_type=json/data`
- 讲解文档里出现 `params/files` 时，明确是 `requests` 低层 kwargs
- `git diff --check` 通过

## 10. Idempotence and Recovery

- 文档和注释修改可重复执行
- 若表述有偏差，可直接再次编辑同一文件收口
- 本次不涉及数据迁移和破坏性命令

## 11. Outcomes & Retrospective

- 本次完成了请求模型收口的文档与示例层清理，没有改动执行链行为。
- `docs/current_state.md` 已更新到 2026-04-24 的真实状态，明确写出前三个请求模型阶段已支持的能力和验证结果。
- `docs/request_02_form_modes_explanation.md`、`docs/request_03_auth_binary_explanation.md` 已把产品层字段与 `requests` 低层 kwargs 分层说明。
- `Core/data_processing.py` 的 `__main__` 示例已从旧 `params/data` 演示切到 `query + body_mode=raw`。
- 本次刻意保留了 `RequestResolver` 和 `PreparedRequest` 里的 `params/files`，因为它们属于 `requests` 低层接口，不代表产品模型回退。
- 已完成静态验证：
  - `git diff --check -- plans/04_request_model_cleanup.md docs/current_state.md docs/request_02_form_modes_explanation.md docs/request_03_auth_binary_explanation.md Core/data_processing.py`
- 剩余风险：
  - `docs/current_state.md` 下半部分仍保留 P0 重构前旧基线，用于历史对照；后续阅读时需要区分“当前状态”和“旧基线”。
  - 运行时验证未执行，因为本次没有改动执行逻辑，只做文档与示例收口。
