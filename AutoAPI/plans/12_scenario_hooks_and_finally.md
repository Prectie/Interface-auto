# AutoAPI 场景级 hooks / finally_steps

> 状态：需重构。
>
> 本计划中的 `ScenarioStep(use=case_id)` hooks 方案已被最新产品决策替换。后续按 `plans/14_action_only_hooks_refactor.md` 执行：hooks 只允许 `action`，业务接口调用只保留在 `Scenario.steps`。

## Purpose / Big Picture

完成后，用户可以在 `Scenario` 上定义：

- `before_steps`
- `after_steps`
- `finally_steps`

执行器会把它们作为场景生命周期的一部分显式执行，而不是重新引入旧 `cleanup` 或隐藏依赖链。

用户可观察结果：

- `before_steps` 在每轮场景主流程前执行。
- `after_steps` 只在主流程成功后执行。
- `finally_steps` 无论成功失败都执行。
- hooks 结果会进入同一条 run 的 step 列表和 history。

## Scope

In scope:

- `Scenario.before_steps`
- `Scenario.after_steps`
- `Scenario.finally_steps`
- Repository 加载和基础校验
- Executor 在场景执行链中接入 hooks
- dataset 轮次内的 hooks 执行
- 示例和测试覆盖
- `current_state` 同步

Out of scope:

- 场景级 `assertions`
- hooks 的脚本 / SQL / wait DSL
- `when` 的复杂条件表达式
- `continue_on_error`
- plan 级 hooks

## Progress

- [x] 阅读 PRD、technical_design、decision_log
- [x] 明确第一版执行语义
- [x] 扩展数据模型和仓库加载
- [x] 扩展基础校验
- [x] 接入 Executor 场景 hooks
- [x] 增加测试
- [x] 更新示例
- [x] 更新 current_state
- [x] 写 retrospective

## Surprises & Discoveries

- 当前 `Executor` 已有 env hooks 和 scenario datasets，所以场景 hooks 不能放在顶层，只能放进单轮 scenario iteration 内部。
- `finally_steps` 不需要新的执行器分支，只需要在 iteration 尾部无条件执行。

## Decision Log

- `before_steps / after_steps / finally_steps` 都挂在 `Scenario` 上，而不是 `TestPlan`。
- hooks 的元素结构复用 `ScenarioStep`，保持 `id/use/override/delay` 一致。
- 第一版 `finally_steps` 不实现复杂 `when` 语义，默认等价于 `always`。
- `before_steps` 失败后，不再继续主流程和 `after_steps`，但仍执行 `finally_steps`。
- `after_steps` 仅在主流程全部通过时执行。
- hooks step 也写入 run steps/history，并继承当前 dataset 维度。

## Context and Orientation

- 数据模型：`Schema/data_models.py`
- 仓库加载：`Core/repository.py`
- 基础校验：`Schema/data_validation.py`
- 执行器：`Engine/executor.py`
- 示例：`examples/p0_minimal/Data/Scenarios/*.yaml`
- 测试：`Tests/test_repository.py`

## Plan of Work

1. 给 `Scenario` 增加三类 hooks 字段。
2. 让 Repository 能从 YAML 加载 hooks。
3. 给 Validator 增加 hooks 引用检查。
4. 改 `_run_scenario_iteration(...)`，接入 hooks 生命周期。
5. 补 dataset 场景下 hooks 的测试。
6. 更新示例和 `current_state`。

## Concrete Steps

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Engine/executor.py`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/12_scenario_hooks_and_finally.md`

## Validation and Acceptance

需要验证：

1. `python run.py validate --data examples/p0_minimal/Data`
2. `python -m pytest -q`

重点观察：

- scenario hooks 能被正确加载
- `before_steps`、主流程、`after_steps`、`finally_steps` 顺序正确
- 主流程失败时 `after_steps` 不执行，但 `finally_steps` 仍执行
- dataset 场景下 hooks 也带上 `dataset_name / dataset_index`

## Idempotence and Recovery

- 本次改动集中在场景模型和执行顺序，可重复执行。
- 示例 YAML 若写坏，可直接回退 `examples/p0_minimal/Data/Scenarios/*.yaml`。

## Outcomes & Retrospective

- 已完成第一版实现，当前状态如下：
  - `Scenario.before_steps / after_steps / finally_steps` 已进入正式模型和仓库加载链路。
  - 执行顺序已固定为 `before -> steps -> after(success only) -> finally(always)`。
  - dataset 轮次中的 hooks 也会继承 `dataset_name / dataset_index`。
- 用户已在 Windows `.venv` 中完成：
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python -m pytest -q`
- 已确认：
  - hooks 加载和执行顺序正确
  - 主流程失败时 `after_steps` 不执行，但 `finally_steps` 仍执行
- 当前边界保持不变：
  - 不支持复杂 `when`
  - 不支持场景级 `assertions`
  - 不支持 hooks 的脚本 / SQL / wait DSL
