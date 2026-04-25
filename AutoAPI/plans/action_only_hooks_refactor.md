# AutoAPI action-only hooks 重构计划

## 1. Purpose / Big Picture

完成后，AutoAPI 的前置、后置和兜底逻辑只表达非业务接口动作，例如等待、SQL、脚本扩展点。业务接口调用只在 `Scenario.steps` 中显式编排，避免 hooks 或环境配置重新形成隐藏的接口链路。

用户可观察结果：

- `Scenario.steps` 仍然通过 case ID 编排业务流程。
- `before_steps / after_steps / finally_steps` 只接受 `action`。
- `action.kind=wait` 可以真实执行。
- `action.kind=sql` 和 `action.kind=script` 有稳定 YAML 结构，但执行时给出清晰的未实现提示。
- 环境级 `setup_cases / teardown_cases / auth_profile / auth_profiles` 从正式模型中移除。

## 2. Scope

In scope:

- 新增 hooks 专用数据模型，例如 `HookStep`。
- 将 `ApiTemplate.before_steps / after_steps`、`ApiCase.before_steps / after_steps`、`Scenario.before_steps / after_steps / finally_steps` 迁移为 action-only hooks。
- Validator 增加 hooks 基础校验：必须有 `id` 和 `action.kind`，禁止 `use`。
- Executor 支持 `action.kind=wait`。
- Executor 对 `sql` / `script` 给出清晰未实现错误，不静默跳过。
- 清理环境级 `setup_cases / teardown_cases / auth_profile / auth_profiles` 的模型、加载、校验、执行和测试。
- 更新示例 YAML 和测试。

Out of scope:

- 不实现 SQL 数据源管理。
- 不实现脚本沙箱。
- 不实现环境级 hooks。
- 不实现 step 重试、失败继续、OpenAPI 导入、SQLite、资产索引等 P2 能力。
- 不把接口资产放入数据库。

## 3. Progress

- [x] 更新 PRD、current_state、decision_log、technical_design 中的需求口径。
- [x] 创建本 ExecPlan。
- [ ] 清理环境级鉴权模板相关实现。
- [ ] 引入 action-only hooks 数据模型和加载逻辑。
- [ ] 接入 hooks action 执行器。
- [ ] 更新示例和测试。
- [ ] 运行验证并补充 retrospective。

## 4. Surprises & Discoveries

- 当前代码已经实现了环境级 `auth_profile/setup_cases/teardown_cases`，但最新产品方向决定废弃它。
- 当前场景级 hooks 复用 `ScenarioStep(use=case_id)`，会把业务接口藏进 hooks，需要迁移成独立 `HookStep(action=...)`。

## 5. Decision Log

- hooks 不再复用 `ScenarioStep`，因为 `ScenarioStep` 的核心语义是“引用 case 执行业务接口”。
- hooks 使用 action-only 模型，第一批只实现 `wait`，SQL 和脚本作为未来扩展点。
- 登录、准备数据、清理数据等接口调用必须显式放在 `Scenario.steps`。
- 环境不承载接口执行模板，只保留变量、host 解析、默认请求参数和后续脱敏配置。

## 6. Context and Orientation

相关文件：

- `Schema/data_models.py`
  - 当前有 `EnvAuthProfile`、`EnvProfile.setup_cases`、`EnvProfile.teardown_cases`、`EnvProfile.auth_profiles`、`EnvProfile.auth_profile`。
  - 当前 `Scenario.before_steps / after_steps / finally_steps` 使用 `ScenarioStep`。
- `Core/repository.py`
  - 当前加载环境鉴权模板和场景 hooks。
- `Schema/data_validation.py`
  - 当前校验环境 hooks 引用 case。
  - 当前使用 scenario step 引用校验处理 hooks。
- `Engine/executor.py`
  - 当前 `_run_with_env_hooks` 包裹顶层执行。
  - 当前场景 hooks 执行的是 case。
- `examples/p0_minimal/Data/Scenarios/hanoi_hooks.yaml`
  - 当前 hooks 示例使用 `use: case_*`，需要改为 `action.kind=wait`。
- `examples/reading_house/Data/config.yaml`
  - 当前存在 `auth_profile` 示例，需移除。
- `Tests/test_repository.py`
  - 当前存在环境鉴权模板测试和 case 引用式 hooks 测试，需要改写。

## 7. Plan of Work

1. 先删除环境级鉴权模板方向，避免后续 hooks 重构时继续兼容旧能力。
2. 再新增 `HookStep` 模型，让 hooks 和业务 `ScenarioStep` 在类型上分开。
3. 改 Repository，让 hooks 加载为 `HookStep`，并保留 `Scenario.steps` 继续加载为 `ScenarioStep`。
4. 改 Validator，显式禁止 hooks 中出现 `use`，并校验 `action.kind`。
5. 改 Executor，增加 action 执行分支：
   - `wait`：等待指定秒数。
   - `sql`：返回未实现错误。
   - `script`：返回未实现错误。
6. 更新 examples，确保可执行示例只使用 `wait`。
7. 更新测试，覆盖加载、校验、执行顺序、失败兜底和废弃字段清理。
8. 更新 current_state 和本计划 retrospective。

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
- `Engine/results.py`，如 action step 结果需要补字段
- `examples/p0_minimal/Data/Scenarios/hanoi_hooks.yaml`
- `examples/reading_house/Data/config.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/action_only_hooks_refactor.md`

预计命令：

```bash
python run.py validate --data examples/p0_minimal/Data
python -m pytest -q
```

如果 WSL 中 `python` 不可用，由用户在 Windows `.venv` 中运行并回传结果。

## 9. Validation and Acceptance

必须通过：

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

测试观察点：

- hooks 使用 `action.kind=wait` 可以成功执行。
- hooks 中出现 `use` 会被 Validator 拒绝。
- `Scenario.steps` 仍然可以引用 `case_` ID。
- 主流程失败时 `after_steps` 不执行，`finally_steps` 仍执行。
- dataset 场景下 hooks action 结果带有 `dataset_name / dataset_index`。
- 环境级 `auth_profile/setup_cases/teardown_cases` 不再被加载或执行。
- 示例中不再出现环境级鉴权模板。

## 10. Idempotence and Recovery

- 文档和 YAML 示例修改可重复应用。
- 测试失败时优先回到 `Schema/data_models.py` 和 `Engine/executor.py` 检查数据结构和执行顺序。
- 不使用 `git reset --hard` 或回滚用户改动。
- 如果发现 `sql/script` 执行需求需要立即落地，先停下来更新 PRD 和本计划，不在本任务中顺手实现。

## 11. Outcomes & Retrospective

待实现完成后补充。
