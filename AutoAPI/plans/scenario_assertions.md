# AutoAPI 场景级 assertions

## Purpose / Big Picture

完成后，用户可以在 `Scenario` 上定义场景级断言，用于校验整轮业务流程执行后的上下文变量，而不是把这些校验硬塞进最后一个接口用例。

用户可观察结果：

- `Scenario.assertions` 会在每轮主流程成功后执行。
- 场景级断言基于当前轮 `RuntimeContext`，而不是某一个 step 的响应。
- 断言结果会写入同一条 run 的 step 列表和 history。
- dataset 场景下，每轮断言都带上 `dataset_name / dataset_index`。

## Scope

In scope:

- `Scenario.assertions`
- `Scenario.assertions_ref`
- Repository 加载和基础校验
- Composer 展开共享断言引用
- AssertionEngine 支持 `source=context`
- Executor 在场景生命周期中执行场景级断言
- dataset 轮次内的场景级断言
- 示例和测试覆盖
- `current_state` 同步

Out of scope:

- 场景级 `extract`
- 场景级 `before_steps / after_steps / finally_steps` 语义重构
- 场景级断言直接读取某个 step 的原始响应对象
- 更复杂的上下文表达式 DSL

## Progress

- [x] 阅读 PRD、technical_design、decision_log
- [x] 明确第一版执行语义
- [x] 扩展数据模型和仓库加载
- [x] 扩展基础校验
- [x] 接入共享断言展开
- [x] 扩展 AssertionEngine `source=context`
- [x] 接入 Executor 场景级断言
- [x] 增加测试
- [x] 更新示例
- [x] 更新 current_state
- [ ] 写 retrospective

## Surprises & Discoveries

- 现有 `AssertionEngine` 只支持响应类 source，所以场景级断言若继续依赖 response，会把语义绑死到“最后一个接口响应”，这不合适。
- 当前 `RuntimeContext` 已经覆盖 env variables、dataset variables 和前序 step 提取变量，正好适合作为场景级断言输入。

## Decision Log

- 场景级断言第一版只支持 `source=context`。
- 场景级断言执行时机固定为：
  - `before_steps`
  - 主流程 `steps`
  - `after_steps`
  - `scenario assertions`
  - `finally_steps`
- 若主流程或 `after_steps` 失败，不执行场景级断言，但仍执行 `finally_steps`。
- 场景级断言支持 `assertions_ref`，复用项目级共享断言。
- 场景级断言会产出一条独立 `P0StepResult`，其 `step_id` 固定为 `scenario.assertions`。

## Context and Orientation

- 数据模型：`Schema/data_models.py`
- 仓库加载：`Core/repository.py`
- 基础校验：`Schema/data_validation.py`
- 共享断言展开：`Core/composer.py`
- 断言引擎：`Engine/assertion_engine.py`、`Engine/jsonpath_tool.py`
- 执行器：`Engine/executor.py`
- 测试：`Tests/test_repository.py`

## Plan of Work

1. 给 `Scenario` 增加 `assertions_ref / assertions` 字段。
2. 让 Repository 加载这些字段，并让 Validator 检查共享引用。
3. 扩展 `AssertionEngine`，支持 `source=context`。
4. 在 `Executor` 中增加场景级断言执行步骤。
5. 补 dataset 维度下的测试和示例。
6. 更新 `current_state` 和 retrospective。

## Concrete Steps

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Core/composer.py`
- `Engine/assertion_engine.py`
- `Engine/jsonpath_tool.py`
- `Engine/executor.py`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/scenario_assertions.md`

## Validation and Acceptance

需要验证：

1. `python run.py validate --data examples/p0_minimal/Data`
2. `python -m pytest -q`

重点观察：

- `Scenario.assertions` 能被正确加载和展开
- `source=context` 能从当前轮上下文读取数据
- 主流程成功后会执行场景级断言
- 主流程失败时不执行场景级断言，但 `finally_steps` 仍执行
- dataset 场景下断言结果带正确的 `dataset_name / dataset_index`

## Idempotence and Recovery

- 本次改动集中在场景层断言语义和执行顺序，可重复执行。
- 示例 YAML 若写坏，可直接回退 `examples/p0_minimal/Data/Scenarios/*.yaml`。

## Outcomes & Retrospective

待实现和验证完成后补充。
