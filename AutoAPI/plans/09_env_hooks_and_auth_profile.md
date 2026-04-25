# AutoAPI 环境级前置 / 后置 / 鉴权模板

> 状态：已废弃。
>
> 最新决策见 `plans/14_action_only_hooks_refactor.md` 和 `docs/decision_log.md` 的 2026-04-25 记录。环境级 `setup_cases / teardown_cases / auth_profile / auth_profiles` 不再作为产品方向继续扩展，后续实现需要清理。

## Purpose / Big Picture

完成后，用户可以把环境相关的自动准备动作和自动鉴权动作放进 `config.yaml` 的 `envs.<env>` 下统一管理。执行 `case / scenario / plan` 时，AutoAPI 可以先执行环境前置和鉴权 setup，再执行目标资产，最后执行环境 teardown。

用户可观察结果：

- 同一环境下，不再需要把“先登录拿 token”重复写进每个 scenario。
- 不同环境可以有不同的登录和清理逻辑。
- `RuntimeContext` 会复用环境 hooks 提取出来的变量，例如 `auth_token`。

## Scope

In scope:

- `EnvProfile` 新增：
  - `setup_cases`
  - `teardown_cases`
  - `auth_profiles`
  - `auth_profile`
- `YamlRepository` 加载以上字段
- `YamlSchemaValidator` 做基础关系校验
- `Executor` 在顶层 `run_case / run_scenario / run_plan` 中执行：
  - env `setup_cases`
  - env `auth_profile.setup_cases`
  - 目标资产
  - env `auth_profile.teardown_cases`
  - env `teardown_cases`
- hook case 与目标资产共享同一个 `RuntimeContext`
- 用例和例子覆盖第一版真实链路

Out of scope:

- 环境级脚本 / SQL / wait DSL
- 场景级 `before_steps / after_steps / assertions / finally_steps`
- 公共断言 / 公共提取
- 自动根据接口是否需要鉴权去智能选择 auth_profile

## Progress

- [x] 阅读 PRD、current_state、decision_log、technical_design
- [x] 明确第一版 YAML 结构和执行顺序
- [x] 扩展环境数据模型与仓库加载
- [x] 增加基础校验
- [x] 接入 Executor 顶层环境 hooks
- [x] 增加测试
- [x] 更新示例配置
- [x] 更新 current_state
- [x] 写 retrospective

## Surprises & Discoveries

- 当前 `Executor` 还没有执行 case / api 级 `before_steps / after_steps`，所以环境 hooks 不能依赖那套未落地能力。
- 现有 `reading_house` 资产正适合拿来验证“环境自动登录 -> 查询用户信息”。
- 如果把 `auth_profile` 直接加到现有 `test` 环境，会污染公开冒烟用例；更合理的是增加单独的鉴权环境。

## Decision Log

- 第一版环境 hooks 只复用 `case` 作为执行载体，不新增环境级 DSL。
- `auth_profiles` 放在 `env` 下作为环境内的鉴权模板注册表。
- `auth_profile` 是环境级默认鉴权模板名；为空则不自动鉴权。
- 顶层执行顺序固定为：
  - `env.setup_cases`
  - `env.auth_profile.setup_cases`
  - target
  - `env.auth_profile.teardown_cases`
  - `env.teardown_cases`
- `teardown_cases` 无论 target 成功失败都执行。
- `run_plan` 内部调用 `run_scenario / run_case` 的 core 版本，避免环境 hooks 重复套娃。

## Context and Orientation

- 数据模型：`Schema/data_models.py`
- 仓库加载：`Core/repository.py`
- 基础校验：`Schema/data_validation.py`
- 执行入口：`Engine/executor.py`
- 真实示例：`examples/reading_house/Data/config.yaml`

## Plan of Work

1. 先扩环境数据模型和加载逻辑，让 `config.yaml` 能表达环境 hooks 和鉴权模板。
2. 再补基础校验，保证 env 引用的 case 和 auth_profile 都存在。
3. 然后重构 `Executor` 顶层入口，把环境 hooks 只包裹一次。
4. 最后补测试和示例配置，并同步当前状态文档。

## Concrete Steps

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Engine/executor.py`
- `Tests/test_repository.py`
- `examples/reading_house/Data/config.yaml`
- `docs/current_state.md`
- `plans/09_env_hooks_and_auth_profile.md`

第一版 YAML 结构：

```yaml
envs:
  test_auth:
    variables: {}
    hosts: {}
    host_rules: []
    setup_cases: []
    teardown_cases: []
    auth_profile: login_default
    auth_profiles:
      login_default:
        setup_cases:
          - case_user_login_success
        teardown_cases: []
```

## Validation and Acceptance

需要验证：

1. `python run.py validate --data examples/reading_house/Data`
2. `python -m pytest -q`
3. `python run.py --case case_user_info_success --env test_auth --data examples/reading_house/Data`

第 3 条的预期观察：

- 无需把登录步骤显式写进 scenario
- CLI 自动先执行登录 case，再执行用户信息 case
- `case_user_info_success` 的请求头里能使用前一步提取出来的 `auth_token`

## Idempotence and Recovery

- 环境 hooks 只改 YAML 加载和执行编排，不涉及破坏性迁移。
- 若示例环境配置出错，可直接回退 `examples/reading_house/Data/config.yaml`。
- `Executor` 重构要保留 core 入口，避免 plan/scenario/case 相互递归时重复执行环境 hooks。

## Outcomes & Retrospective

- 已完成第一版实现，环境级前置 / 后置 / 鉴权模板已进入正式执行链。
- 用户已在 Windows `.venv` 中完成：
  - `python run.py validate --data examples/reading_house/Data`
  - `python -m pytest -q`
  - `python run.py --case case_user_info_success --env test_auth --data examples/reading_house/Data`
- 已确认环境 `auth_profile` 会在目标资产前自动执行登录 case，并与目标资产共享 `RuntimeContext`。
- 当前边界保持不变：
  - 只支持引用 case 作为环境 hooks 载体
  - 不支持环境级脚本 / SQL / wait DSL
