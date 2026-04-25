# AutoAPI Action-Only Hooks 最小实现计划

## 1. Purpose / Big Picture

完成后，AutoAPI 可以执行第一版 action-only hooks：`ApiTemplate`、`ApiCase`、`Scenario` 的 hooks 都能执行 `action.kind=wait`，并将结果写入当前 run 的 step 结果中。

业务接口调用仍然只允许出现在 `Scenario.steps`，hooks 不再执行 case。

## 2. Scope

In scope:

- 引入 hooks 专用模型，例如 `HookStep`。
- `ApiTemplate.before_steps / after_steps` 支持 action-only。
- `ApiCase.before_steps / after_steps` 支持 action-only。
- `Scenario.before_steps / after_steps / finally_steps` 支持 action-only。
- 实现 `action.kind=wait`。
- 为 `sql/script` 内部的 `extract` 保留模型字段，但不执行。
- Validator 禁止 hooks 中出现 `use`。
- hooks 执行结果写入 `P0StepResult`。

Out of scope:

- 不删除环境级 `auth_profile` 代码。
- 不实现 SQL 执行。
- 不实现 script 执行。
- 不定义 action 内部 `extract` 表达式语义。
- 不扩展企业级断言/提取 source。

## 3. Progress

- [x] T01 阅读 `15_hooks_action_docs_convergence.md` 和当前 hooks 相关代码。
- [x] T02 新增 hooks 专用模型。
- [x] T03 Repository 加载 hooks 为 action-only 模型。
- [x] T04 Validator 禁止 hooks 中使用 `use`。
- [x] T05 Executor 实现 `wait` action。
- [x] T06 接入 template/case hooks 执行顺序。
- [x] T07 接入 scenario hooks / finally_steps 执行顺序。
- [x] T08 更新示例 YAML 和测试。
- [x] T09 运行验证并补充 retrospective。

## 4. Surprises & Discoveries

- WSL 环境中 `python` 命令不存在。
- 尝试调用 Windows `.venv/Scripts/python.exe` 时触发 WSL interop socket 错误，无法在当前 shell 完成运行时验证。

## 5. Decision Log

- `ScenarioStep` 只用于 `Scenario.steps`。
- hooks 使用独立模型，避免 `use` 字段自然泄漏进 hooks。
- `wait` 是第一版唯一真实执行 action。
- `sql/script` 若被执行，应返回清晰未实现错误，不能静默跳过。

## 6. Context and Orientation

相关文件：

- `Schema/data_models.py`
  - 当前 `Scenario.before_steps / after_steps / finally_steps` 复用 `ScenarioStep`。
- `Core/repository.py`
  - 当前负责加载 template/case/scenario hooks。
- `Schema/data_validation.py`
  - 当前 hooks 校验仍可能按 scenario step 引用逻辑处理。
- `Engine/executor.py`
  - 当前场景级 hooks 执行 case。
  - template/case hooks 的 action 执行能力需要统一接入。
- `Engine/results.py`
  - 如 action step 结果需要补字段，在这里处理快照。
- `Tests/test_repository.py`
  - 需要覆盖 hooks action 执行顺序和禁止 `use`。

## 7. Plan of Work

1. T02 新增 `HookStep`：
   - `id`
   - `action`
   - 可选 `delay`
2. T03 Repository：
   - template/case/scenario hooks 加载为 `HookStep`。
   - `Scenario.steps` 继续加载为 `ScenarioStep`。
3. T04 Validator：
   - hooks 必须有 `id` 和 `action.kind`。
   - hooks 中出现 `use` 直接报错。
   - `kind=wait` 要求有 `seconds` 或等价时间字段。
   - `kind=sql/script` 允许作为预留结构，但运行时不实现。
4. T05 Executor：
   - 新增 action 执行分支。
   - `wait` 调用等待逻辑。
   - `sql/script` 返回未实现错误。
5. T06 case 执行顺序：

   ```text
   template before
   -> case before
   -> request main
   -> case after
   -> template after
   ```

6. T07 scenario 执行顺序：

   ```text
   scenario before
   -> scenario steps
   -> scenario after
   -> scenario assertions
   -> scenario finally
   ```

7. T08 更新 tests 和 examples。

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
- `Engine/results.py`
- `examples/p0_minimal/Data/Scenarios/hanoi_hooks.yaml`
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/16_action_only_hooks_minimal_impl.md`

预计命令：

```bash
python run.py validate --data examples/p0_minimal/Data
python -m pytest -q
```

如果 WSL 中 `python` 不可用，由用户在 Windows `.venv` 中运行并回传结果。

## 9. Validation and Acceptance

必须验证：

- `wait` 可在 template hooks 中执行。
- `wait` 可在 case hooks 中执行。
- `wait` 可在 scenario hooks 中执行。
- `wait` 结果写入 `P0StepResult`。
- `Scenario.finally_steps` 始终执行。
- 主请求失败时 `after_steps` 不执行。
- hooks 中出现 `use: case_xxx` 会被 Validator 拒绝。
- `sql/script` 若被执行，返回明确未实现错误。

## 10. Idempotence and Recovery

- 若 Validator 改动导致示例无法通过，先检查 hooks 示例是否仍有 `use`。
- 若执行顺序失败，优先检查 `Executor` 中 case 和 scenario 两条链路。
- 不在本计划中删除环境级 `auth_profile` 代码。

## 11. Outcomes & Retrospective

- 已完成最小实现：
  - 新增 `HookStep`，hooks 与业务 `ScenarioStep` 分离。
  - Repository 将 template/case/scenario hooks 加载为 `HookStep`。
  - Validator 禁止 hooks 中出现 `use`，并校验 `action.kind`。
  - Executor 支持 `action.kind=wait`。
  - `sql/script` 执行时返回明确未实现错误。
  - case 执行顺序已调整为 `template before -> case before -> request -> case after -> template after`。
  - scenario hooks / finally_steps 走 action 执行器。
  - `hanoi_hooks.yaml` 示例已切换到 action-only。
- 已运行：
  - `git diff --check -- Schema/data_models.py Core/repository.py Schema/data_validation.py Core/composer.py Engine/executor.py Tests/test_repository.py examples/p0_minimal/Data/Scenarios/hanoi_hooks.yaml`
- 用户已在 Windows `.venv` 中完成人工验证并确认通过：
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python run.py validate --data examples/reading_house/Data`
  - `python -m pytest -q`
