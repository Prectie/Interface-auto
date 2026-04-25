# AutoAPI 执行增强总表

## Purpose / Big Picture

完成后，AutoAPI 会从“基础请求执行链已成型”推进到“报告自动化 + 复用能力 + 场景编排增强”的下一阶段。用户可以直接通过 CLI 获得 Allure HTML 报告，并逐步获得公共断言/提取、场景级数据驱动和 action-only hooks。

## Scope

In scope:

- 拆分以下 6 项能力的执行顺序和里程碑：
  - CLI 执行后自动生成 Allure HTML 报告
  - `docs/current_state.md` 和验证结果持续同步
  - action-only hooks 重构
  - 公共断言 / 公共提取
  - 场景级数据驱动
  - 场景级 hooks / `finally_steps`

Out of scope:

- P2 能力，如 OpenAPI import、SQLite 历史、Web UI、通知、资产索引。
- 请求模型新的字段扩展。
- 旧 `single.yaml / Flows` 兼容。

## Progress

- [x] 识别下一批优先能力
- [x] 拆成新的执行计划总表
- [x] 完成 `08_allure_auto_html.md`
- [x] 完成 `current_state` 本轮同步
- [x] 完成 `09_env_hooks_and_auth_profile.md`，但该方向已被 2026-04-25 决策废弃
- [x] 完成 `10_shared_assertions_and_extracts.md`
- [x] 完成 `11_scenario_datasets.md`
- [x] 完成 `12_scenario_hooks_and_finally.md`
- [x] 新增 `14_action_only_hooks_refactor.md` 作为后续清理和重构计划

## Surprises & Discoveries

- 当前请求模型主线已经基本收口，继续补零散请求字段的收益明显下降。
- 当前最直接的 P0 缺口是 Allure HTML 仍未接入 CLI 主链路。
- `docs/current_state.md` 已承担“真实状态基线”职责，后续每个里程碑都应同步它。

## Decision Log

- 优先顺序定为：Allure 自动 HTML -> current_state 持续同步 -> 环境级鉴权与前后置 -> 公共断言/提取 -> 场景级数据驱动 -> 场景级 hooks / `finally_steps`。
- 场景级 hooks 归类为 P1，且放在场景级数据驱动之后实现，避免同时扩大 Executor 复杂度。

## Context and Orientation

- 报告主链路入口：`run.py`
- 执行核心：`Engine/executor.py`
- 历史写入：`Engine/history_writer.py`
- Allure 适配：`Utils/allure_reporter.py`
- 当前状态基线：`docs/current_state.md`

## Plan of Work

先补 P0 缺口，再进入 P1 的复用和编排能力。

1. 先完成 Allure 自动 HTML，让 CLI 主链路闭环。
2. 建立 `current_state` 同步机制，确保每个里程碑都有真实状态记录。
3. 再做复用类能力和 action-only hooks，这些能力会降低 YAML 资产重复并保持场景显式编排。
4. 最后再做会明显改变执行模型的场景级数据驱动和场景级 hooks。

## Concrete Steps

1. 新建 Allure 子计划并实现。
2. 新建 `current_state` 同步计划，定义每次里程碑后的更新规则。
3. 为 action-only hooks 重构创建计划。
4. 为公共断言 / 公共提取创建计划。
5. 为场景级数据驱动创建计划。
6. 为场景级 hooks / `finally_steps` 创建计划。

## Validation and Acceptance

- 总表本身的验收方式：
  - 各项能力都有独立计划文件。
  - 子计划顺序与 PRD、decision log 一致。
  - 不把 P1/P2 范围混入当前实现。

## Idempotence and Recovery

- 本总表只描述里程碑，不直接改代码；可多次更新。
- 子计划可独立推进，不要求一次完成全部 6 项。

## Outcomes & Retrospective

- 这 6 项优先能力已全部完成第一版实现：
  - CLI 自动生成 Allure HTML
  - `current_state` 持续同步
  - 环境级前置 / 后置 / 鉴权模板已完成第一版，但该方向已废弃，后续按 action-only hooks 计划清理
  - 公共断言 / 公共提取
  - 场景级数据驱动
  - 场景级 hooks / `finally_steps`
- 相关能力均已由用户在 Windows `.venv` 中完成运行时验证或人工验证。
- 当前下一阶段不再是补这批基础执行增强，而是转向新的 P1 / P2 目标。
