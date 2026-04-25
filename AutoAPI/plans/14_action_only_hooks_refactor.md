# AutoAPI Hooks/Action 模型重构总计划

## 1. Purpose / Big Picture

本计划把 AutoAPI 的 hooks 体系彻底收敛为 action-only：所有层级的 hooks 都只能执行 `action.kind`，不允许引用 case。业务接口调用只允许出现在 `Scenario.steps` 中，避免隐藏业务流程、递归引用和依赖环。

同时，当前环境级 `auth_profile` 路线被判定为错误方向，不再继续增强；鉴权接口应该作为场景第一步显式编排。

本计划是总纲，具体执行拆成三个顺序计划：

- `plans/15_hooks_action_docs_convergence.md`
- `plans/16_action_only_hooks_minimal_impl.md`
- `plans/17_remove_env_auth_profile.md`

## 2. Scope

In scope:

- 明确 hooks 总原则：所有 hooks 都是 action-only。
- 明确第一版 action 只正式实现 `wait`。
- 为 `sql`、`script` 和 action 内部的 `extract` 预留模型空间。
- 文档层废弃环境级 `setup_cases / teardown_cases / auth_profiles / auth_profile`。
- 将代码清理拆到独立计划，避免一次改动过大。

Out of scope:

- 不实现 SQL 执行。
- 不实现 script 执行。
- 不定义 action 内部 `extract` 的完整表达式语义。
- 不实现环境级 hooks。
- 不实现企业级断言/提取 source 扩展；该能力排在 hooks 重构之后。

## 3. Progress

- [x] T01 明确 hooks/action 方向。
- [x] T02 将任务拆成三个顺序 ExecPlan。
- [x] T03 执行 `15_hooks_action_docs_convergence.md`。
- [x] T04 执行 `16_action_only_hooks_minimal_impl.md`。
- [x] T05 执行 `17_remove_env_auth_profile.md`。
- [x] T06 完成总计划 retrospective。

## 4. Surprises & Discoveries

- 当前环境级 auth_profile 能力已经进入代码，但它会隐藏业务流程，和显式场景编排冲突。
- 当前场景 hooks 复用了 `ScenarioStep(use=case_id)`，语义上会把业务接口执行藏进 hooks。
- `setup/teardown` 只是未来平台化生命周期术语，不应该作为当前 YAML 字段进入主线。

## 5. Decision Log

- hooks 统一采用 `action` 结构，不保留 `use` 兼容。
- 业务接口编排永远只放在 `Scenario.steps`。
- 第一版只正式实现 `action.kind=wait`。
- `sql` / `script` 只预留结构，不实现执行器。
- action 内部 `extract` 现在只做模型预留，不定义完整表达式语义。
- 环境级鉴权模板视为错误方向，后续直接废弃，不保留为长期历史能力。

## 6. Context and Orientation

相关现状：

- `ApiTemplate.before_steps / after_steps`、`ApiCase.before_steps / after_steps` 当前是 list 结构，但执行能力需要统一收敛到 action。
- `Scenario.before_steps / after_steps / finally_steps` 当前复用 `ScenarioStep`，需要改成 hooks 专用结构。
- `EnvProfile.setup_cases / teardown_cases / auth_profiles / auth_profile` 当前已存在，需要先文档废弃，再单独清理代码。
- 企业常用断言/提取 source 扩展仍然有价值，但必须排在 hooks/action 模型稳定之后。

## 7. Plan of Work

1. T03 文档收敛：
   - PRD、decision log、current_state 中明确 hooks 全部 action-only。
   - 明确业务接口只允许在 `Scenario.steps`。
   - 明确环境级 auth_profile 废弃。
   - 确认示例 YAML 中 hooks 不再出现 `use: case_xxx`。
2. T04 最小实现：
   - `wait` 可在 template/case/scenario hooks 中执行。
   - `wait` 结果写入 `P0StepResult`。
   - `Scenario.finally_steps` 始终执行。
   - 主请求失败时 `after_steps` 不执行。
3. T05 环境鉴权清理：
   - 删除 env `setup_cases / teardown_cases / auth_profiles / auth_profile`。
   - 删除对应执行链与测试。
   - 用场景显式鉴权样例替代旧 auth flow 样例。

## 8. Concrete Steps

新增或更新的计划文件：

- `plans/15_hooks_action_docs_convergence.md`
- `plans/16_action_only_hooks_minimal_impl.md`
- `plans/17_remove_env_auth_profile.md`

本总计划只定义顺序和边界，不直接改业务代码。

## 9. Validation and Acceptance

总计划验收：

- 三个子计划均存在且编号连续。
- 子计划范围分别对应文档收敛、最小实现、环境鉴权清理。
- 子计划没有把企业级断言/提取扩展混入 hooks/action 重构。

## 10. Idempotence and Recovery

- 本文件是总纲，可重复更新。
- 如果执行过程中发现范围变化，先更新对应子计划，再同步本总计划。
- 不在任一子计划中顺手实现未列入范围的能力。

## 11. Outcomes & Retrospective

- 三个子计划已完成：
  - `15_hooks_action_docs_convergence.md`：完成 hooks/action 文档收敛。
  - `16_action_only_hooks_minimal_impl.md`：完成 action-only hooks 最小实现，`wait` 已可执行。
  - `17_remove_env_auth_profile.md`：完成环境级 auth profile 清理。
- 当前产品边界已收敛为：
  - hooks 只执行 action，不引用 case。
  - 业务接口调用只允许在 `Scenario.steps` 显式编排。
  - action 第一版只真实支持 `wait`。
  - `sql/script/extract` 作为后续扩展点保留。
  - 环境只负责变量、host 解析、默认请求参数和后续脱敏配置。
- 用户已在 Windows `.venv` 中验证通过：
  - `python run.py validate --data examples/reading_house/Data`
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python -m pytest -q`
- 下一步建议进入企业常用断言/提取 source 扩展。
