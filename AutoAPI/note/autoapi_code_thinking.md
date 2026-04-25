# AutoAPI 重构后的代码思维笔记

本文用于记录 AutoAPI 当前版本的代码理解方式。目标不是逐行解释语法，而是帮助理解框架为什么这样拆、数据如何流动、后续看代码应该从哪里入手。

## 1. 总体结论

当前 AutoAPI 已经不是“读取 YAML 后直接发请求”的脚本，而是一个小型接口自动化执行框架。

核心思路：

```text
先把资产变成结构化对象，再合成为可执行对象，最后由执行器统一调度。
```

主链路：

```text
YAML
-> Repository 加载成 ProjectAssets
-> Validator 做基础关系校验
-> Composer 合成 ExecutableCase / ExecutableStep
-> RequestResolver 构造 PreparedRequest
-> Transport 发送请求
-> Extractor 写入 RuntimeContext
-> AssertionEngine 执行断言
-> Executor 汇总 P0StepResult / P0RunResult
-> HistoryWriter / Allure 输出结果
```

理解这条链路后，再看每个模块，就不会觉得代码是散的。

## 2. 职责边界

### Repository：资产怎么读

对应文件：

- `Core/repository.py`

`YamlRepository` 只负责读取和转换 YAML 资产：

- `config.yaml`
- `apis.yaml`
- `cases.yaml`
- `Scenarios/*.yaml`
- `plans.yaml`

它把 YAML 转成：

- `EnvironmentConfig`
- `ApiTemplate`
- `ApiCase`
- `Scenario`
- `TestPlan`
- `ProjectAssets`

它不负责：

- 不发送 HTTP 请求。
- 不做变量渲染。
- 不执行断言。
- 不决定场景怎么跑。

这样做的原因是：资产加载和执行逻辑必须分离。否则后续做 OpenAPI 导入、资产索引、影响分析时，会很难复用 Repository。

### Validator：资产关系是否成立

对应文件：

- `Schema/data_validation.py`

当前 Validator 只做基础检查：

- 全局 ID 是否唯一。
- case 引用的 api 是否存在。
- scenario step 引用的 case 是否存在。
- plan 引用的 scenario / case 是否存在。
- `method + path` 是否重复。
- `active_env` 和 `host_rules` 是否基本可用。

当前不做严格字段 schema 校验，这是有意保留的。因为模型还在演进，过早严格校验会拖慢开发。

后续严格字段校验属于 P2。

### Composer：继承和覆盖怎么合成

对应文件：

- `Core/composer.py`

这是当前框架里最关键的模块之一。

它负责把资产合成为可执行对象：

```text
ApiTemplate + ApiCase -> ExecutableCase
ExecutableCase + ScenarioStep override -> ExecutableStep
```

它承载这些产品规则：

- `method/path` 只能来自 `ApiTemplate`。
- `ApiCase` 不能覆盖 `method/path`。
- `ScenarioStep override` 也不能覆盖 `method/path`。
- override 使用字段级整体覆盖。
- 未填写表示继承。
- 写 `null` 表示清空。
- 公共断言 / 公共提取在合成阶段展开。

为什么要有 Composer：

如果没有它，继承和覆盖逻辑会散落在 Executor、RequestResolver、CLI 里。后续一旦发现某个字段继承错了，就很难定位。

现在如果你想判断“为什么这个字段最后是这个值”，优先看 `Composer`。

### RequestResolver：请求模型怎么翻译成 requests

对应文件：

- `Engine/request_resolver.py`

它负责把 AutoAPI 的请求模型翻译成 `requests` 能理解的参数。

典型映射：

```text
path_params -> 替换 /model/{id}
query -> requests params
cookies -> requests cookies
auth -> headers / params / cookies
body_mode=raw + raw_type=json -> requests json
body_mode=raw + raw_type=text/xml/html/javascript -> requests data
body_mode=form_urlencoded -> requests data
body_mode=form_data -> requests files
body_mode=binary -> requests data
host_rules -> base_url
```

这层存在的意义是：YAML 面向用户表达产品语义，`RequestResolver` 面向代码处理 HTTP 细节。

用户不需要知道 `requests` 的 `json/data/files` 互斥规则；这些由 Resolver 处理。

### Executor：执行顺序怎么编排

对应文件：

- `Engine/executor.py`

`Executor` 是总调度器。它串起：

- Repository
- Composer
- RequestResolver
- Transport
- Extractor
- AssertionEngine

它自己不应该处理太多底层细节。

执行单个 case：

```text
读取 case
-> 读取 api
-> compose_case
-> 执行 before hooks
-> 执行主请求
-> 执行 after hooks
-> 汇总 P0RunResult
```

执行场景：

```text
scenario before_steps
-> scenario steps
-> scenario after_steps
-> scenario assertions
-> scenario finally_steps
```

其中业务接口只允许放在 `Scenario.steps` 中。

hooks 只允许执行 `action.kind`，例如：

```yaml
before_steps:
  - id: 等待服务稳定
    action:
      kind: wait
      seconds: 2
```

这个规则是为了避免回到旧的隐藏链式依赖。

### RuntimeContext：变量如何流动

对应文件：

- `Core/context.py`

`RuntimeContext` 可以理解为一次执行过程中的变量背包。

变量流向：

```text
env.variables 初始化上下文
-> dataset.variables 覆盖本轮输入
-> 请求中 ${xxx} 变量渲染
-> extract 提取响应写回 ctx
-> 后续步骤继续使用 ${xxx}
-> assertions 可以读取 context
```

场景级数据驱动的本质不是“单个接口换几组参数”，而是“一整条业务流用不同初始变量跑多轮”。

例如：

```text
启动模型 -> 查看启动状态 -> 更新模型数据 -> 查看结果
```

每个 dataset 都是一轮完整业务，不是一条接口数据。

### Extractor：变量怎么提取

对应文件：

- `Engine/extractor.py`

`Extractor` 的职责很单纯：

```text
source + jsonpath + as
-> 取值
-> 写入 RuntimeContext
```

示例：

```yaml
extract:
  - source: response_json
    jsonpath: $.data.taskId
    as: taskId
```

这表示：

```text
从响应 JSON 里取 $.data.taskId
写入 ctx["taskId"]
后续可以用 ${taskId}
```

Extractor 不关心请求怎么发，也不关心断言怎么判断。

### AssertionEngine：结果怎么判断

对应文件：

- `Engine/assertion_engine.py`

断言模型：

```text
source + jsonpath + op + expected
-> actual
-> 比较
-> AssertionResult
```

支持的 source 包括：

- `response_status`
- `response_headers`
- `response_json`
- `response_text`
- `context`
- `response_time_ms`

支持的 op 包括：

- `==`
- `!=`
- `>`
- `>=`
- `<`
- `<=`
- `contains`
- `not_contains`
- `starts_with`
- `ends_with`
- `empty`
- `not_empty`
- `regex`
- `length_gt`
- `length_gte`
- `length_lt`
- `length_lte`
- `length_eq`
- `exists`

以后如果要增强断言能力，优先看 `AssertionEngine`，不要改 Executor。

### CLI：用户怎么触发

对应文件：

- `run.py`

CLI 只负责入口，不承载业务规则。

它做这些事：

- 解析命令。
- 加载 YAML 资产。
- 创建 Executor。
- 调用 `run_case / run_scenario / run_plan`。
- 写 history。
- 导出 Allure。
- 打印执行摘要。

它不应该知道：

- 场景步骤怎么执行。
- 请求体怎么拼。
- 断言怎么判断。
- 变量怎么提取。

如果这些逻辑进入 CLI，CLI 会变成新的复杂中心。

## 3. 核心数据流

以执行一个场景为例：

```text
python run.py --scenario scn_demo --env test
```

代码链路：

```text
run.py
-> YamlRepository.load()
-> Executor.run_scenario()
-> repo.get_scenario()
-> env = repo.get_env()
-> dataset 初始化 RuntimeContext
-> scenario.before_steps
-> scenario.steps
   -> repo.get_case()
   -> repo.get_api()
   -> composer.compose_case()
   -> composer.compose_step()
   -> request_resolver.resolve_executable()
   -> transport.send()
   -> extractor.apply()
   -> assertion_engine.assert_all()
-> scenario.after_steps
-> scenario.assertions
-> scenario.finally_steps
-> P0RunResult
-> HistoryWriter
-> AllureRuntimeReporter
```

每一步都产出下一步需要的对象，而不是直接共享一堆散乱 dict。

## 4. Before vs After

### 重构前

旧方向的问题：

- `single.yaml` 同时包含接口定义、请求数据、断言、提取、依赖、cleanup。
- `depends_on` 会隐藏业务链路。
- `cleanup` 会让清理逻辑不透明。
- 执行入口依赖 pytest 收集，CLI 能力弱。
- host 分散在接口请求里，不利于多环境管理。
- 请求模型偏简化，不容易支持 Postman / MeterSphere 常见 body 类型。

### 重构后

当前结构：

- `ApiTemplate` 描述接口模板。
- `ApiCase` 描述接口怎么测。
- `Scenario` 显式编排业务流。
- `TestPlan` 组织场景和用例。
- `EnvironmentConfig` 管理环境、变量、host_rules、共享规则。
- `Composer` 统一处理继承和覆盖。
- `Executor` 统一处理执行流程。
- `RequestResolver` 统一处理 HTTP 请求构造。

重构后带来的收益：

- 业务流更直观。
- 模块职责更清楚。
- 新请求类型可以集中加在 RequestResolver。
- 新断言能力可以集中加在 AssertionEngine。
- 新资产分析能力可以复用 Repository。
- 执行结果有统一结构，便于 history 和 Allure 输出。

## 5. 当前设计的 trade-offs

当前设计不是没有成本。

成本包括：

- 文件比以前多。
- 对象层次比以前多。
- 新人需要理解 Repository / Composer / Executor / Resolver 的分工。
- Composer 的继承和覆盖逻辑需要认真看，不能随意改。

但这个成本是值得的，因为它换来了：

- 清晰职责边界。
- 可测试的模块。
- 后续扩展不需要到处改。
- 产品规则能落到固定位置。

## 6. 如何判断代码该放在哪里

以后新增功能时，可以用下面的问题判断应该改哪个模块。

### 资产字段怎么加载？

改：

- `Schema/data_models.py`
- `Core/repository.py`

### 字段是否合法、引用是否存在？

改：

- `Schema/data_validation.py`

### 模板、用例、场景步骤之间如何继承和覆盖？

改：

- `Core/composer.py`

### YAML 请求字段如何变成 HTTP 请求？

改：

- `Engine/request_resolver.py`

### 场景、计划、hooks、finally 的执行顺序怎么调整？

改：

- `Engine/executor.py`

### 响应变量怎么提取？

改：

- `Engine/extractor.py`
- `Engine/jsonpath_tool.py`

### 断言 source 或 op 怎么扩展？

改：

- `Engine/assertion_engine.py`
- `Engine/jsonpath_tool.py`

### 执行结果怎么记录？

改：

- `Engine/results.py`
- `Engine/history_writer.py`
- `Utils/allure_runtime.py`
- `Utils/allure_reporter.py`

### CLI 怎么暴露新命令？

改：

- `run.py`

## 7. 阅读代码的建议顺序

建议按这个顺序看：

1. `Schema/data_models.py`
2. `Core/repository.py`
3. `Core/composer.py`
4. `Engine/request_resolver.py`
5. `Engine/executor.py`
6. `Engine/extractor.py`
7. `Engine/assertion_engine.py`
8. `Engine/results.py`
9. `run.py`
10. `Tests/test_repository.py`

原因：

- 先看模型，知道系统里有哪些对象。
- 再看 Repository，知道对象从哪里来。
- 再看 Composer，知道对象如何被合成。
- 再看 Resolver 和 Executor，知道请求如何执行。
- 最后看结果和 CLI，知道输出如何形成。

## 8. 后续学习重点

如果要继续深入，优先学习三块：

1. `Composer`

它最能体现 AutoAPI 的产品规则，例如继承、覆盖、`null` 清空、公共规则展开。

2. `Executor`

它是完整执行链的中枢，理解它之后，你就能知道场景、计划、hooks、finally 是怎么串起来的。

3. `RequestResolver`

它决定 YAML 请求模型如何真正落到 HTTP，也是后续支持更多请求形式的主要扩展点。

## 9. 最重要的判断标准

以后看 AutoAPI 代码时，不要先问“这一行语法是什么意思”，而是先问：

```text
这个模块属于哪一层？
它的输入是什么？
它的输出是什么？
它有没有越权做别的层的事？
```

如果一个模块开始做不属于自己的事情，后续维护成本就会升高。

当前重构的核心价值，就是把这些边界先立住。
