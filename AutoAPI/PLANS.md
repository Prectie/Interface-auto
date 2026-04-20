# AutoAPI ExecPlan 规范

本文档定义 AutoAPI 项目中复杂任务的 ExecPlan 写法。ExecPlan 是复杂任务的执行计划，不是简单 TODO 列表。

## 什么时候必须写 ExecPlan

以下任务开始实现前，必须先创建或更新 `plans/*.md`：

- 数据模型变化，例如新增 `ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan`。
- Repository 重构。
- Resolver 重构。
- Executor 重构。
- CLI 入口改造。
- 报告或 JSONL history 改造。
- 迁移方案。
- 涉及多个核心模块的重构。

简单文档修改、小范围 bugfix、单个函数的小改动，可以不写 ExecPlan。

## 核心要求

- ExecPlan 必须自包含。新的 Codex 会话或人类维护者只看计划，也能理解目标、范围、步骤和验证方式。
- ExecPlan 必须是活文档。任务推进时要更新进度、发现、决策和验证结果。
- ExecPlan 必须可验证。不能只写“完成重构”，必须写明用什么命令或观察结果证明完成。
- ExecPlan 必须对齐：
  - `AGENTS.md`
  - `docs/product_requirements.md`
  - `docs/current_state.md`
  - `docs/decision_log.md`
  - `docs/technical_design_v1.md`，如果存在

## 文件位置

复杂任务计划放在：

```text
plans/
```

命名建议：

```text
plans/autoapi_p0_refactor.md
plans/p0_01_repository_loading.md
plans/p0_02_reference_resolution.md
plans/p0_03_executor_cli.md
```

`plans/autoapi_p0_refactor.md` 可以作为 P0 总纲；如果任务过大，再拆成 milestone 计划。

## 必备章节

每个 ExecPlan 必须包含以下章节。

### 1. Purpose / Big Picture

说明完成后用户能获得什么能力。

要求：

- 用业务可观察结果描述。
- 不只描述内部实现。

示例：

```text
完成后，用户可以执行 `python run.py validate`，并能基于新结构加载 `apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。
```

### 2. Scope

明确 In scope 和 Out of scope。

要求：

- 不要把 P1/P2 混进 P0。
- 如果用户临时扩范围，需要更新本节。

### 3. Progress

用 checklist 记录进度。

要求：

- 每完成一个重要步骤就更新。
- 如果中途暂停，下一次可以从这里继续。

格式：

```markdown
- [x] 阅读 PRD 和 current_state
- [ ] 创建示例 YAML
- [ ] 实现 Repository 加载
```

### 4. Surprises & Discoveries

记录执行中发现的意外情况。

示例：

```text
- `requirements.txt` 在 shell 中显示为带 NUL 的异常文本，后续需要单独清理。
- `run.py` 当前固定执行 flow，不存在 CLI router。
```

### 5. Decision Log

记录本计划执行期间新增的决策。

要求：

- 写清背景、决策和原因。
- 重要决策后续同步到 `docs/decision_log.md`。

### 6. Context and Orientation

说明当前相关代码在哪里。

要求：

- 指明文件路径。
- 指明当前行为。
- 指明哪些模块可复用，哪些模块需要重构。

### 7. Plan of Work

用自然语言描述实现顺序。

要求：

- 从低风险基础工作开始。
- 先让代码读懂新模型，再接执行器。
- 每一步都有明确产出。

### 8. Concrete Steps

列出具体操作。

要求：

- 包含预计修改文件。
- 包含预计新增文件。
- 包含工作目录。
- 包含必要命令。

### 9. Validation and Acceptance

列出验收方式。

要求：

- 说明要运行什么命令。
- 说明预期观察结果。
- 如果某些验证暂时不能跑，要写明原因。

### 10. Idempotence and Recovery

说明失败后如何安全重试。

要求：

- 哪些操作可重复执行。
- 哪些生成文件可以删除重建。
- 哪些操作需要人工确认。

### 11. Outcomes & Retrospective

阶段完成或计划完成后填写。

内容包括：

- 实际完成了什么。
- 和计划相比有什么偏差。
- 还剩什么风险。
- 下一步建议。

## 更新规则

执行计划期间，Codex 需要在这些时机更新 ExecPlan：

- 完成一个 checklist 项。
- 发现计划外风险。
- 做出新决策。
- 验证命令运行完成。
- 任务暂停，需要保留上下文。
- 任务完成，需要写 retrospective。

## AutoAPI P0 特别约束

P0 ExecPlan 必须遵守：

- 不兼容旧 `Data/single.yaml` 和 `Data/Flows/*.yaml`。
- 不把 YAML 资产放进数据库。
- 不引入 Web UI。
- 不做 OpenAPI import。
- 不做 SQLite。
- 不做严格字段 schema 校验。
- 不做 tag/priority 执行。
- 不做 scenario-level data driving。
- 不做 `finally_steps`。
- 不做 deep merge。
- 不重新引入 `host` 或 `host_key`。

