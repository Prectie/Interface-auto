# AutoAPI 场景级数据驱动

## Purpose / Big Picture

完成后，用户可以在 `Scenario.datasets` 中定义多组业务输入变量，并让同一个场景按数据集逐轮执行完整流程。每轮执行拥有独立上下文，前一轮提取出的变量不会污染后一轮。

用户可观察结果：

- 一个 `Scenario` 可以用多组业务数据重复执行。
- `Reports/history/results.jsonl` 能区分每个 step 属于哪一组 dataset。
- CLI / Allure / history 能定位某一轮失败的是哪组数据。

## Scope

In scope:

- `Scenario.datasets`
- `ScenarioDataset` 数据模型
- Repository 加载和基础校验
- `Executor.run_scenario` / `run_plan` 支持按 dataset 多轮执行
- `P0StepResult` 和 history 增加 `dataset_name / dataset_index`
- 示例和测试覆盖

Out of scope:

- 场景级 hooks / `finally_steps`
- dataset 级选择、过滤、tag
- 测试计划持有 datasets
- Web UI 数据集管理

## Progress

- [x] 阅读 PRD、technical_design、decision_log
- [x] 明确第一版执行语义
- [x] 扩展数据模型和仓库加载
- [x] 扩展基础校验
- [x] 接入 Executor 多轮执行
- [x] 扩展 history 维度
- [x] 增加测试
- [x] 更新示例
- [x] 更新 current_state
- [x] 写 retrospective

## Surprises & Discoveries

- 环境 hooks 已经包裹在顶层执行入口，所以 dataset 执行必须放在 `_run_scenario_core` 内部，不能在顶层再套一层。
- history 当前只记录 step 级结果，直接加 `dataset_name / dataset_index` 就足够支持第一版定位。

## Decision Log

- `datasets` 只挂在 `Scenario` 上，`TestPlan` 不持有 datasets。
- dataset variables 优先级高于 env variables。
- 每个 dataset 对应一轮完整场景执行。
- 每轮场景使用独立 `RuntimeContext`，其初始值 = 顶层上下文快照 + dataset.variables。
- 若某一轮失败，第一版仍按失败即停止，不继续后续 dataset。
- history 先补 `dataset_name / dataset_index` 到 step 级记录。

## Context and Orientation

- 数据模型：`Schema/data_models.py`
- 仓库加载：`Core/repository.py`
- 基础校验：`Schema/data_validation.py`
- 执行器：`Engine/executor.py`
- history：`Engine/history_writer.py`
- 结果模型：`Engine/results.py`

## Plan of Work

1. 先给 `Scenario` 增加 `datasets` 模型和加载逻辑。
2. 再补基础校验，保证 dataset 名称和结构最小可用。
3. 然后改 `_run_scenario_core`，让它按 dataset 多轮执行。
4. 最后补 history 字段、测试和示例。

## Concrete Steps

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Engine/results.py`
- `Engine/history_writer.py`
- `Engine/executor.py`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/scenario_datasets.md`

## Validation and Acceptance

需要验证：

1. `python run.py validate --data examples/p0_minimal/Data`
2. `python -m pytest -q`

重点观察：

- 含 `datasets` 的 scenario 能被正确加载
- 同一 scenario 会按 dataset 多轮执行
- 每轮 step 的 `dataset_name / dataset_index` 正确写入结果
- 某一轮失败时后续 dataset 不继续执行

## Idempotence and Recovery

- 本次改动主要是模型和执行逻辑扩展，可重复执行。
- 示例 YAML 若写坏，可直接回退 `examples/p0_minimal/Data/Scenarios/*.yaml`。

## Outcomes & Retrospective

- 已完成第一版实现，当前状态如下：
  - `Scenario.datasets` 已进入正式数据模型和仓库加载链路。
  - `Executor.run_scenario(...)` 已支持按 dataset 多轮执行。
  - 每轮 dataset 使用独立 `RuntimeContext`，避免提取变量跨轮污染。
  - `HistoryWriter` 已写入 `dataset_name / dataset_index`。
  - 示例场景和单测已补齐。
- 用户已在 Windows `.venv` 中完成：
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python -m pytest -q`
- 已确认 dataset 轮次、变量注入和 history 维度都能正常工作。
- 当前边界保持不变：
  - 第一版仍是失败即停止后续 dataset
  - 不支持数据集筛选、tag、计划级 datasets
