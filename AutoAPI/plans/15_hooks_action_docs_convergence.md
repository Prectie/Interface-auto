# AutoAPI Hooks/Action 文档收敛计划

## 1. Purpose / Big Picture

完成后，AutoAPI 的产品文档、决策记录和当前状态文档会统一表达同一条规则：hooks 全部 action-only，业务接口调用只允许出现在 `Scenario.steps`。

这一轮只做模型和文档收敛，不删除执行代码，避免把“废弃设计”和“代码清理”混在同一轮。

## 2. Scope

In scope:

- 更新 `docs/product_requirements.md`。
- 更新 `docs/decision_log.md`。
- 更新 `docs/current_state.md`。
- 更新 `docs/technical_design_v1.md`，如存在旧 hooks 语义。
- 检查示例 YAML，确认 hooks 示例不再推荐 `use: case_xxx`。
- 明确环境级 `auth_profile` 废弃原因。

Out of scope:

- 不改执行器代码。
- 不删除环境级 `auth_profile` 代码。
- 不实现 `wait/sql/script`。
- 不扩展断言/提取 source。

## 3. Progress

- [x] T01 阅读 PRD、decision log、current_state、technical design。
- [x] T02 更新 hooks 总原则：所有 hooks 只允许 `action`。
- [x] T03 更新 action 第一版 kind：`wait` 实现，`sql/script` 预留。
- [x] T04 更新 action 内部 `extract` 预留说明。
- [x] T05 更新环境级 `auth_profile` 废弃说明。
- [x] T06 检查示例 YAML 中 hooks 是否仍出现 `use: case_xxx`。
- [x] T07 运行文档静态检查并补充 retrospective。

## 4. Surprises & Discoveries

- `examples/p0_minimal/Data/Scenarios/hanoi_hooks.yaml` 仍在 hooks 中使用 `use: case_*`，已改成 action-only 示例。
- 改示例后，当前执行器尚未支持 action-only hooks，因此本轮不运行 `validate`；运行时验证放到 `16_action_only_hooks_minimal_impl.md`。

## 5. Decision Log

- hooks 总原则：所有层级都只允许 `action.kind`。
- 适用层级：
  - `ApiTemplate.before_steps / after_steps`
  - `ApiCase.before_steps / after_steps`
  - `Scenario.before_steps / after_steps / finally_steps`
  - TestPlan 后续若补 hooks，也只允许 action
  - 全局环境 setup / teardown 若未来保留，也只允许 action
- 业务接口执行唯一入口：`Scenario.steps`。
- 环境级 `auth_profile` 废弃原因：
  - 会隐藏业务流程。
  - 会重新引入隐式依赖。
  - 和 action-only hooks 冲突。

## 6. Context and Orientation

相关文件：

- `docs/product_requirements.md`
- `docs/decision_log.md`
- `docs/current_state.md`
- `docs/technical_design_v1.md`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- `examples/reading_house/Data/*.yaml`

## 7. Plan of Work

1. T01 先读文档，定位所有 hooks、auth_profile、setup、teardown 相关表述。
2. T02 把 PRD 中 hooks 结构统一改成：

   ```yaml
   before_steps:
     - id: 等待服务稳定
       action:
         kind: wait
         seconds: 2
   ```

3. T03 写明第一版只正式实现 `wait`，`sql/script` 是结构预留。
4. T04 写明 action 内部 `extract` 只为未来 sql/script 写回 `RuntimeContext` 预留，不定义完整表达式语义。
5. T05 写明环境级鉴权模板废弃，但代码清理放到 `17_remove_env_auth_profile.md`。
6. T06 检查示例 YAML，确认文档示例不再引导用户在 hooks 中写 `use`。
7. T07 更新本计划 retrospective。

## 8. Concrete Steps

工作目录：

```bash
/mnt/d/githubrepository/interface-auto/autoapi
```

预计命令：

```bash
rg -n "before_steps|after_steps|finally_steps|auth_profile|setup_cases|teardown_cases|use: case" docs examples plans
git diff --check -- docs plans examples
```

## 9. Validation and Acceptance

验收标准：

- PRD、decision log、current_state 中明确：
  - hooks 全部 action-only。
  - 业务接口只允许在 `Scenario.steps`。
  - 环境级 `auth_profile` 废弃。
- 文档示例中的 hooks 不再出现 `use: case_xxx`。
- `sql/script/extract` 只作为预留，不被描述成已实现能力。

## 10. Idempotence and Recovery

- 本轮只改文档和示例，可重复检查。
- 如果发现代码中仍有旧能力，只记录到 current_state，不在本轮删除。

## 11. Outcomes & Retrospective

- 已完成文档和示例语义收敛：
  - PRD 增加 action 内部 `extract` 统一命名说明。
  - decision log 记录 action 内部提取统一使用 `extract`。
  - technical design 同步 `extract` 命名。
  - current_state 标记目标语义已收敛，但执行器尚待 `16_action_only_hooks_minimal_impl.md` 实现。
  - `hanoi_hooks.yaml` 中 hooks 不再引用 case。
- 未运行 `python run.py validate` 和 `pytest`，原因是当前代码还未实现 action-only hooks，示例已先切到目标语义。
