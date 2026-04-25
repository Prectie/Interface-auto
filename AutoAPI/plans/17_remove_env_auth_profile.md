# AutoAPI 环境级 Auth Profile 清理计划

## 1. Purpose / Big Picture

完成后，AutoAPI 不再保留环境级 `setup_cases / teardown_cases / auth_profiles / auth_profile` 执行路线。鉴权接口、准备接口、清理接口都通过 `Scenario.steps` 显式编排。

这一轮只在 action-only hooks 最小实现稳定后执行。

## 2. Scope

In scope:

- 删除 `EnvProfile.setup_cases`。
- 删除 `EnvProfile.teardown_cases`。
- 删除 `EnvProfile.auth_profiles`。
- 删除 `EnvProfile.auth_profile`。
- 删除 `EnvAuthProfile` 模型。
- 删除 Repository 对这些字段的加载。
- 删除 Validator 对这些字段的校验。
- 删除 Executor 顶层环境 hooks 执行链。
- 删除或改写相关测试。
- 用显式场景鉴权样例替代旧 auth flow 样例。
- 更新 `docs/current_state.md` 和相关计划 retrospective。

Out of scope:

- 不实现新的环境级 hooks。
- 不实现平台化 auth panel。
- 不实现复杂鉴权模板。
- 不改变 request.auth 字段本身；接口请求仍可使用 `auth`。
- 不扩展断言/提取 source。

## 3. Progress

- [x] T01 确认 `16_action_only_hooks_minimal_impl.md` 已完成并通过验证。
- [x] T02 删除环境级 auth profile 数据模型。
- [x] T03 删除 Repository 加载逻辑。
- [x] T04 删除 Validator 校验逻辑。
- [x] T05 删除 Executor 环境 hooks 包裹逻辑。
- [x] T06 改写 reading_house 鉴权示例为显式场景步骤。
- [x] T07 删除或改写测试。
- [x] T08 运行验证并补充 retrospective。

## 4. Surprises & Discoveries

- `reading_house` 已经有 `scn_reading_house_auth_flow`，其中登录步骤显式排在用户信息查询前面，因此不需要新增场景，只需删除 `config.yaml` 中的 `test_auth` 环境和 auth profile。
- 清理 Executor 后，`run_plan` 内部不再需要 env hooks 去重逻辑，顶层入口可以直接调用 core 执行方法。

## 5. Decision Log

- 环境级鉴权模板是错误方向，不保留长期兼容。
- 鉴权接口统一放在 `Scenario.steps` 第一位。
- 环境只负责变量、host 解析、默认请求参数和后续脱敏配置。
- request-level `auth` 字段仍保留，它表达单个请求如何携带认证信息，不等同于环境级鉴权模板。

## 6. Context and Orientation

相关文件：

- `Schema/data_models.py`
  - `EnvAuthProfile`
  - `EnvProfile.setup_cases`
  - `EnvProfile.teardown_cases`
  - `EnvProfile.auth_profiles`
  - `EnvProfile.auth_profile`
- `Core/repository.py`
  - 环境 auth profile 加载逻辑。
- `Schema/data_validation.py`
  - 环境 setup/teardown/auth profile 引用校验。
- `Engine/executor.py`
  - `_run_with_env_hooks`
  - `_run_env_case_list`
- `examples/reading_house/Data/config.yaml`
  - 当前存在 auth profile 示例。
- `examples/reading_house/Data/Scenarios/*.yaml`
  - 需要加入显式登录步骤的场景样例。
- `Tests/test_repository.py`
  - 环境 setup/teardown/auth profile 相关测试。

## 7. Plan of Work

1. T01 先确认 action-only hooks 已稳定，避免同时改两条执行链。
2. T02 从模型层移除环境级 auth profile 字段。
3. T03 清理 Repository 加载逻辑。
4. T04 清理 Validator 对 env setup/teardown/auth profile 的引用校验。
5. T05 清理 Executor 顶层环境 hooks 包裹逻辑：
   - 执行 `case/scenario/plan` 时不再自动跑环境 case。
   - plan 内部调用不再需要避免 env hooks 重复套娃。
6. T06 改写 reading_house 示例：
   - 鉴权接口作为 `Scenario.steps` 第一位。
   - 后续步骤通过提取变量继续使用 token/cookie。
7. T07 改写测试，删除旧能力断言。
8. T08 更新 current_state 和本计划 retrospective。

## 8. Concrete Steps

工作目录：

```bash
/mnt/d/githubrepository/interface-auto/autoapi
```

预计修改文件：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- `Engine/executor.py`
- `examples/reading_house/Data/config.yaml`
- `examples/reading_house/Data/Scenarios/*.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/17_remove_env_auth_profile.md`

预计命令：

```bash
python run.py validate --data examples/reading_house/Data
python run.py validate --data examples/p0_minimal/Data
python -m pytest -q
```

如果 WSL 中 `python` 不可用，由用户在 Windows `.venv` 中运行并回传结果。

## 9. Validation and Acceptance

必须验证：

- `config.yaml` 中不再需要 `setup_cases / teardown_cases / auth_profiles / auth_profile`。
- Repository 不再加载这些字段。
- Validator 不再校验这些字段。
- Executor 不再自动执行环境 case。
- reading_house 鉴权流程通过显式 `Scenario.steps` 表达。
- 原有 request-level `auth` 能力不受影响。

## 10. Idempotence and Recovery

- 删除代码前先确认测试覆盖点，避免误删 request-level `auth`。
- 如果 reading_house 示例需要真实服务验证，由用户在 Windows `.venv` 中运行。
- 不保留旧字段兼容；如果旧 YAML 仍写这些字段，早期宽松校验下可能被忽略，后续严格校验再统一报错。

## 11. Outcomes & Retrospective

- 已完成代码清理：
  - 删除 `EnvAuthProfile`。
  - 删除 `EnvProfile.setup_cases / teardown_cases / auth_profiles / auth_profile`。
  - 删除 Repository 加载逻辑。
  - 删除 Validator 引用校验逻辑。
  - 删除 Executor 顶层环境 hooks 包裹逻辑。
  - 删除环境 setup/teardown/auth profile 相关测试，改为显式场景鉴权测试。
  - 删除 reading_house 示例中的 `test_auth` 环境。
- 已运行：
  - `git diff --check -- Schema/data_models.py Core/repository.py Schema/data_validation.py Engine/executor.py Tests/test_repository.py examples/reading_house/Data/config.yaml Core/data_processing.py docs/current_state.md`
  - `rg -n "EnvAuthProfile|setup_cases|teardown_cases|auth_profiles|auth_profile|_run_with_env_hooks|_run_env_case_list|test_auth|env.auth|env.setup|env.teardown" Schema Core Engine Tests examples`
- 用户已在 Windows `.venv` 中完成验证并确认通过：
  - `python run.py validate --data examples/reading_house/Data`
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python -m pytest -q`
