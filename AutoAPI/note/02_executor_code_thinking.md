# Executor 代码思维笔记

对应文件：

- `Engine/executor.py`

## 1. Executor 的核心角色

`Executor` 是执行调度器。

它的职责是：

```text
决定执行顺序，并把各个执行组件串起来。
```

它不应该亲自处理太多细节。

它依赖这些组件：

- `YamlRepository`：读取资产。
- `Composer`：合成可执行对象。
- `RequestResolver`：构造请求。
- `Transport`：发送请求。
- `Extractor`：提取变量。
- `AssertionEngine`：执行断言。

所以 Executor 是 orchestration 层，不是业务细节层。

## 2. 对外入口

Executor 当前有三个主要入口：

```text
run_case(case_id)
run_scenario(scenario_id)
run_plan(plan_id)
```

这三个方法都返回：

```text
RunResult
```

`RunResult` 是一次执行的总结果，包括：

- run_id
- target_type
- target_id
- env
- status
- started_at
- ended_at
- duration_ms
- steps
- error

这样 CLI、history、Allure 都可以统一消费这个结果。

## 3. run_case 执行链

核心链路：

```text
run_case
-> _run_case_core
-> repo.get_env
-> RuntimeContext(env.variables)
-> repo.get_case
-> repo.get_api
-> composer.compose_case
-> _execute_executable_with_hooks
-> RunResult
```

case 单独执行时，仍然会走 template/case hooks：

```text
before hooks
-> main request
-> after hooks
```

这保证 case 单独执行和 scenario 中执行的行为一致。

## 4. run_scenario 执行链

核心链路：

```text
run_scenario
-> _run_scenario_core
-> datasets 循环
-> _run_scenario_iteration
```

每个 dataset 是一轮完整场景。

如果没有 datasets：

```text
datasets = [None]
```

也就是普通执行一轮。

如果有 datasets：

```text
for dataset in scenario.datasets:
    创建独立 RuntimeContext
    注入 dataset.variables
    执行完整场景
```

这么设计是为了避免不同数据轮次之间变量互相污染。

## 5. 单轮 scenario 的执行顺序

对应 `_run_scenario_iteration`。

顺序是：

```text
scenario.before_steps
-> scenario.steps
-> scenario.after_steps
-> scenario.assertions
-> scenario.finally_steps
```

其中：

- `before_steps` 失败后，不执行主业务步骤。
- `steps` 失败后，不执行 `after_steps` 和 `scenario.assertions`。
- `finally_steps` 总是执行。

这和常见自动化框架里的 finally 语义一致：无论主流程是否失败，都尝试执行兜底动作。

## 6. scenario.steps 为什么是唯一业务接口入口

在当前产品规则里：

```text
业务接口调用只允许出现在 Scenario.steps。
```

原因：

旧的 `depends_on` 和环境级 `auth_profile` 会隐藏业务链路。

例如旧思路可能变成：

```text
执行最后一个接口
-> 自动执行 depends_on
-> 自动登录
-> 自动清理
```

这会让场景不透明。

现在统一要求：

```yaml
steps:
  - id: 登录
    use: case_login_success

  - id: 启动模型
    use: case_start_model_success

  - id: 更新数据
    use: case_update_model_success
```

这样业务流程一眼可见。

## 7. action-only hooks

hooks 不再引用 case。

当前支持：

```yaml
before_steps:
  - id: 等待服务稳定
    action:
      kind: wait
      seconds: 2
```

Executor 中执行 hooks 的方法：

```text
_run_hook_step_list
-> _execute_action_hook
```

当前 `action.kind`：

- `wait`：已实现。
- `sql`：预留，未实现。
- `script`：预留，未实现。

`sql/script` 暂时抛出 `NotImplementedError`，这是有意设计。它让 YAML 结构提前稳定，但不假装功能已经可用。

## 8. 执行一个请求的核心

对应 `_execute_executable`。

完整顺序：

```text
RequestResolver.resolve_executable
-> Transport.send
-> ResponseSnapshot.format_response
-> Extractor.apply
-> AssertionEngine.assert_all
-> StepResult
```

这段是整个框架最核心的请求执行链。

注意：

`Executor` 不自己组 URL，不自己判断 body_mode，不自己提取 JSONPath，也不自己比较断言。

它只调用对应组件。

## 9. 错误如何变成状态

Executor 不让异常直接冲出执行链，而是转换成 `StepResult`。

规则：

```text
断言失败 -> failed
其它异常 -> error
```

对应方法：

```text
_error_status
```

这样做的意义是：

- 请求失败、变量渲染失败、文件不存在等属于 error。
- 响应正常但断言不通过属于 failed。
- history 和 Allure 能区分两类问题。

## 10. plan 执行逻辑

`run_plan` 是计划执行入口。

当前逻辑：

```text
先执行 plan.scenarios
如果全部通过，再执行 plan.cases
遇到失败即停止
```

当前还没有：

- step retry
- step continue_on_error
- plan 级 hooks

这些都属于后续 P2 或更后面的能力。

## 11. 设计收益

Executor 当前设计的收益：

- 执行顺序集中可读。
- 请求构造、提取、断言都不混在一起。
- case/scenario/plan 结果统一成 `RunResult`。
- 每个步骤都有 `StepResult`，方便 history 和 Allure 输出。
- `Transport` 可注入，便于单元测试使用 fake transport。

## 12. 当前 trade-offs

当前 Executor 的成本：

- 方法数量较多。
- 执行链拆得比较细，初看不如一个大函数直观。
- hooks、scenario assertions、datasets 让控制流更复杂。

但拆开后有一个明显好处：

```text
每个方法都对应一个执行层级。
```

例如：

- `_run_case_core`：case 层。
- `_run_scenario_core`：scenario 总层。
- `_run_scenario_iteration`：单轮 dataset 层。
- `_run_scenario_step_list`：业务 steps 层。
- `_execute_executable`：单请求层。
- `_execute_action_hook`：action hook 层。

这比一个超大函数更适合长期维护。

## 13. 调试建议

如果你要看一次完整执行，断点建议：

1. `run_case / run_scenario / run_plan`
2. `_run_case_core` 或 `_run_scenario_core`
3. `_run_scenario_iteration`
4. `_run_scenario_step_list`
5. `_execute_executable_with_hooks`
6. `_execute_executable`

重点观察：

- `ctx.snapshot()`
- `env`
- `executable.request`
- `prepared.to_dict()`
- `response_snapshot`
- `extract_out`
- `assertions`
- `StepResult.status`

## 14. 后续扩展时怎么判断是否该改 Executor

应该改 Executor 的需求：

- step retry。
- step continue_on_error。
- plan 级 hooks。
- 更复杂的 finally 策略。
- 并发执行。
- 失败后跳过 / 继续策略。

不应该改 Executor 的需求：

- 新增 body_mode。
- 新增 auth 类型。
- 新增断言 op。
- 新增 JSONPath source。
- 新增 Allure 附件格式。

这些分别属于 `RequestResolver`、`AssertionEngine`、`JsonPathTool`、`AllureRuntimeReporter`。
