# AutoAPI P1 收口与状态同步

## Purpose / Big Picture

完成后，AutoAPI 当前 P1 核心能力会在文档中形成明确边界：哪些已经完成，哪些已经移动到 P2，下一步不能再无意识继续扩大范围。

本计划只做状态收口和文档同步，不改执行代码。

## Scope

In scope:

- 同步 `docs/current_state.md` 中 P1 已完成能力。
- 清理文档中已经过期的环境级鉴权和 case 引用 hooks 描述。
- 在 `docs/decision_log.md` 记录 P1 收口决策。
- 更新 `plans/07_execution_enhancements_backlog.md` 的最终结果。
- 如有必要，微调 `docs/product_requirements.md` 的 P1 清单，使其包含已完成的企业常用断言/提取 source 扩展。

Out of scope:

- 不实现 P2 功能。
- 不改 Repository / Resolver / Executor。
- 不恢复旧 `single.yaml / Flows` 兼容。
- 不调整当前 YAML 模型规则。

## Progress

- [x] T01 阅读当前状态、决策记录、执行增强总表和 PRD P1/P2 清单。
- [x] T02 创建 P1 收口计划。
- [x] T03 更新 `docs/current_state.md`。
- [x] T04 更新 `docs/decision_log.md`。
- [x] T05 更新 `plans/07_execution_enhancements_backlog.md` 和必要 PRD 文本。
- [x] T06 执行文档静态验证。
- [x] T07 填写 Outcomes & Retrospective。

## Surprises & Discoveries

- `docs/current_state.md` 前半部分已经记录 action-only hooks 和环境级鉴权清理完成，但限制列表中仍保留“hooks 引用 case”的旧描述，需要清理。
- `plans/07_execution_enhancements_backlog.md` 仍把“环境级鉴权与前后置”写在原始优先顺序中，需要补充说明该方向已经被废弃并由 action-only hooks 替代。

## Decision Log

- P1 当前按已讨论范围收口，不继续顺手推进 P2。
- 企业常用断言/提取 source 扩展视为 P1 收尾增强，因为它直接补齐当前断言/提取能力缺口，不属于平台化能力。

## Context and Orientation

相关文档：

- `docs/product_requirements.md`
- `docs/current_state.md`
- `docs/decision_log.md`
- `plans/07_execution_enhancements_backlog.md`
- `plans/18_enterprise_assert_extract_sources.md`

当前 P1 已完成能力包括：

- Allure 自动 HTML。
- 公共断言 / 公共提取。
- 场景级数据驱动。
- 场景级 before / after / assertions / finally。
- action-only hooks。
- 环境级 auth_profile 清理。
- 企业常用断言/提取 source 和 op 扩展。

## Plan of Work

先同步真实状态，再记录决策，最后更新总表和 PRD 边界。这样后续新会话可以直接从文档判断：P1 已收口，下一步如果继续开发，应明确选择 P2 起点。

## Concrete Steps

1. 在 `docs/current_state.md` 增加 P1 收口状态，并删除过期限制描述。
2. 在 `docs/decision_log.md` 增加 P1 收口决策。
3. 更新 `plans/07_execution_enhancements_backlog.md` 的 Decision Log 和 Outcomes。
4. 必要时更新 `docs/product_requirements.md` P1 清单。
5. 运行：

```bash
git diff --check -- docs/current_state.md docs/decision_log.md docs/product_requirements.md plans/07_execution_enhancements_backlog.md plans/19_p1_closure_current_state.md
```

## Validation and Acceptance

- 文档中不再把环境级 `auth_profile` 描述为当前主线能力。
- 文档中不再把 hooks 引用 case 描述为当前限制。
- P1 已完成能力和 P2 延后能力边界清楚。
- `git diff --check` 通过。

## Idempotence and Recovery

本计划只改 Markdown。若内容有误，可以通过普通 diff 查看并用补丁修正，不涉及生成物或执行状态。

## Outcomes & Retrospective

已完成：

- 新增 P1 收口计划。
- `docs/current_state.md` 增加 P1 收口状态，并清理过期的“hooks 引用 case”描述。
- `docs/decision_log.md` 增加 P1 收口决策。
- `plans/07_execution_enhancements_backlog.md` 更新为 P1 已收口、P2 需显式选择。
- `docs/product_requirements.md` P1 清单补充企业常用断言 / 提取 source 和常用断言 op。

已执行静态验证：

```bash
rg -n "仅支持引用 case|环境级 hooks 第一版|仍需用户|待清理|extract_to" docs/current_state.md docs/decision_log.md docs/product_requirements.md plans/07_execution_enhancements_backlog.md plans/19_p1_closure_current_state.md
git diff --check -- docs/current_state.md docs/decision_log.md docs/product_requirements.md plans/07_execution_enhancements_backlog.md plans/19_p1_closure_current_state.md
```

结果：

- 过期文本搜索只命中本计划中记录的验证命令，业务文档无残留。
- `git diff --check` 通过。

结论：

- P1 文档状态已经收口。
- 下一步如果继续实现，应明确选择 P2 起点，而不是继续在 P1 名义下扩范围。
