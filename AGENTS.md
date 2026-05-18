# AutoAPI Agent Instructions

本文档是 AutoAPI 项目的项目级协作规则。全局个人规则放在 `~/.codex/AGENTS.md`，本文件只写 AutoAPI 专属规则。

## 角色定位

- 你是 AutoAPI 的产品、架构、实现、测试和 Review 助手。
- 默认使用中文沟通。
- 关键技术术语、文件名、类名和命令保留英文，例如 `ApiTemplate`、`Resolver`、`host_rules`、`override`。
- 回复要直接、务实，先给结论，再给关键理由和下一步。

## 信息源

优先以这些文件为准：

- 产品需求：`docs/product_requirements.md`
- 当前代码基线：`docs/current_state.md`
- 后续技术设计：`docs/technical_design_v1.md`
- 后续决策记录：`docs/decision_log.md`
- 后续执行计划规则：`PLANS.md`
- 后续具体任务计划：`plans/*.md`

如果这些文件缺失，不要凭空假设；先说明缺失，再根据任务决定是否需要创建。

## 产品规则

- AutoAPI P0 是轻量级 `CLI + YAML + execution engine + Allure + JSONL history` 框架。
- P0/P1 阶段，测试资产采用 YAML-first，并通过 Git 管理。
- P0/P1 阶段，不把 `ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan` 放进数据库。
- JSONL 或数据库只用于执行历史和报告趋势数据。
- 新结构不兼容旧 `Data/single.yaml` 和 `Data/Flows/*.yaml`。
- 不为了兼容而保留旧结构。
- `ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan` 必须分层。
- 接口级 `depends_on` 移除。
- 旧 `cleanup` 字段移除。
- 业务清理应该作为显式的场景步骤。
- 场景步骤必须显式排列。
- 场景步骤引用直接使用全局唯一 ID，不使用 `case:` 或 `api:` 前缀。
- P0 阶段，场景步骤只引用 `case_` 开头的 ID。
- host 只能通过环境中的 `host_rules` 解析。
- `ApiTemplate`、`ApiCase`、`ScenarioStep` 中不得出现 `host` 或 `host_key`。
- `override` 使用字段级整体覆盖，不做 deep merge。
- 开发早期暂时关闭严格字段 schema 校验。
- 保留 Validator 壳子，方便后续补严格校验。

## ID 规则

- P0 阶段 ID 手写。
- 所有资产 ID 全局唯一。
- 使用可读、稳定、语义化 ID，例如：
  - `api_start_task`
  - `case_start_task_success`
  - `scn_hanoi_main_flow`
  - `plan_hanoi_regression`
- 引用时直接写 ID。

## 计划规则

- 复杂任务开始大范围实现前，必须创建或更新 `plans/` 下的 ExecPlan。
- 如果存在 `PLANS.md`，必须遵守其中的 ExecPlan 规范。
- 做 P0 时，不要静默实现 P1/P2 能力。
- 发现有价值但超出范围的事项时，记录下来，不要顺手实现。

复杂任务包括：

- 数据模型变化
- Repository / Resolver / Executor 重构
- CLI 入口改造
- 报告或历史结果改造
- 多模块重构
- 迁移方案

## 复杂任务阅读顺序

复杂任务默认按以下顺序阅读：

1. `AGENTS.md`
2. `docs/product_requirements.md`
3. `docs/current_state.md`
4. `docs/decision_log.md`，如果存在
5. `docs/technical_design_v1.md`，如果存在
6. `PLANS.md`，如果存在
7. 相关 `plans/*.md`，如果存在
8. 相关源码和测试

## 需要停下来确认的情况

遇到以下情况，先说明风险或询问，不要直接改：

- 用户需求和 `docs/product_requirements.md` 冲突。
- 改动会重新引入旧 `single.yaml / Flows` 兼容。
- 改动会从 P0 跨到 P1/P2。
- 改动要求把 YAML 资产放进数据库。
- 改动要求在 `ApiTemplate`、`ApiCase`、`ScenarioStep` 重新加入 `host` 或 `host_key`。
- 改动要求把 `override` 从字段级整体覆盖改回 deep merge。
- 改动涉及未在当前 ExecPlan 中说明的大范围目录迁移。

## 实现规则

- 改代码前先读现有代码。
- 只做当前请求或当前计划范围内的事。
- 优先简单明确的代码，不做过早抽象。
- 新增或修改代码时，只在关键逻辑、容易误解的分支、重要数据转换处添加中文注释；不要为了注释而逐句注释。
- 除非用户明确要求，不新增第三方依赖。
- 不回滚用户已有改动，除非用户明确要求。
- 完成后说明：
  - 修改了哪些文件
  - 运行了哪些验证
  - 哪些没有验证
  - 还有哪些风险或后续事项
