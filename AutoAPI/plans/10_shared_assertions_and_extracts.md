# AutoAPI 公共断言 / 公共提取

## Purpose / Big Picture

完成后，用户可以把重复出现的断言规则和提取规则定义成共享片段，在 `ApiTemplate`、`ApiCase` 和 `ScenarioStep override` 中通过引用复用，而不需要在多个 YAML 资产里复制粘贴同样的规则。

用户可观察结果：

- 类似“接口成功返回”“提取 taskId/token”这类公共规则可以集中维护。
- 修改公共规则后，所有引用它的资产自动生效。
- 不新增新的执行层级，只是把公共片段在合成阶段展开。

## Scope

In scope:

- `config.yaml` 顶层新增：
  - `shared_extracts`
  - `shared_assertions`
- `ApiTemplate` / `ApiCase` 支持：
  - `extract_ref`
  - `assertions_ref`
- `ScenarioStep.override` 支持：
  - `extract_ref`
  - `assertions_ref`
- Composer 在合成阶段展开共享规则
- Validator 做引用存在性检查
- 示例和测试覆盖

Out of scope:

- 共享 hooks
- 共享 request 片段
- 嵌套引用（公共片段再引用公共片段）
- 循环引用检测

## Progress

- [x] 明确第一版模型和合成顺序
- [x] 扩展数据模型与仓库加载
- [x] 扩展基础校验
- [x] 接入 Composer 展开逻辑
- [x] 增加测试
- [x] 更新示例
- [x] 更新 current_state
- [x] 写 retrospective

## Surprises & Discoveries

- 当前 `extract` / `assertions` 已是纯列表结构，非常适合在 Composer 里做“引用展开”。
- 把共享规则放到 `config.yaml` 顶层，可以避免新增 `shared.yaml`，减少 Repository 读取面。

## Decision Log

- 第一版公共规则统一放在 `config.yaml` 顶层。
- 引用字段命名固定为：
  - `extract_ref`
  - `assertions_ref`
- 合成顺序固定为：
  - 先展开共享规则
  - 再追加本地 `extract` / `assertions`
- `ScenarioStep override` 若显式写 `extract_ref` / `assertions_ref`，按字段级整体覆盖处理。

## Context and Orientation

- 数据模型：`Schema/data_models.py`
- 仓库加载：`Core/repository.py`
- 合成逻辑：`Core/composer.py`
- 基础校验：`Schema/data_validation.py`
- 示例资产：`examples/p0_minimal/Data/config.yaml`

## Plan of Work

1. 先给 `config.yaml` 和数据模型增加共享片段注册表。
2. 再扩 `ApiTemplate / ApiCase / ScenarioStep` 的引用字段。
3. 然后在 Composer 中按统一顺序展开。
4. 最后补测试、示例和 `current_state`。

## Concrete Steps

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Core/composer.py`
- `Tests/test_repository.py`
- `examples/p0_minimal/Data/config.yaml`
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `examples/p0_minimal/Data/Scenarios/hanoi.yaml`
- `docs/current_state.md`
- `plans/10_shared_assertions_and_extracts.md`

第一版 YAML 结构：

```yaml
shared_extracts:
  extract_task_id:
    - source: response_json
      jsonpath: $.obj
      as: taskId

shared_assertions:
  assert_success:
    - source: response_json
      jsonpath: $.success
      op: ==
      expected: true
```

引用示例：

```yaml
extract_ref:
  - extract_task_id

assertions_ref:
  - assert_success
```

## Validation and Acceptance

需要验证：

1. `python run.py validate --data examples/p0_minimal/Data`
2. `python -m pytest -q`

重点观察：

- 公共引用存在时，合成结果中能展开为真实规则列表
- 公共引用不存在时，validate 失败并给出明确定位
- step override 能覆盖 `extract_ref / assertions_ref`

## Idempotence and Recovery

- 本次改动只扩模型和合成逻辑，可重复执行。
- 若示例写坏，可直接回退 `examples/p0_minimal/Data/*`。

## Outcomes & Retrospective

- 已完成第一版实现，共享断言 / 共享提取已在合成阶段展开，不新增执行层级。
- 用户已在 Windows `.venv` 中完成：
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python -m pytest -q`
- 已确认：
  - `extract_ref / assertions_ref` 能正确展开为真实规则列表
  - 缺失共享引用会在 `validate` 阶段报错
  - `ScenarioStep.override` 可覆盖共享引用列表
- 当前边界保持不变：
  - 只支持一层共享引用
  - 不支持共享规则引用共享规则
