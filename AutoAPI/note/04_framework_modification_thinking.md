# AutoAPI 功能修改的代码思维

本文重点讲“以后你自己改功能时，应该怎么思考代码落点”。它不是功能清单，也不是语法教程，而是把 AutoAPI 当前框架的工程判断方式写下来。

## 1. 总原则：先判断需求属于哪一层

AutoAPI 当前不是一个单文件脚本，而是分层框架。

所以任何新需求进来，第一步不是直接写代码，而是先问：

```text
这个需求影响的是资产模型、合成规则、请求构造、执行流程、断言提取、结果输出，还是 CLI 入口？
```

对应关系：

```text
资产字段怎么定义             -> Schema/data_models.py
YAML 怎么读成对象            -> Core/repository.py
资产关系怎么校验             -> Schema/data_validation.py
继承和覆盖怎么生效           -> Core/composer.py
请求怎么变成 HTTP            -> Engine/request_resolver.py
场景/计划怎么跑              -> Engine/executor.py
变量怎么提取                 -> Engine/extractor.py / Engine/jsonpath_tool.py
断言怎么判断                 -> Engine/assertion_engine.py / Engine/jsonpath_tool.py
结果怎么保存                 -> Engine/history_writer.py / Engine/results.py
Allure 怎么展示              -> Utils/allure_runtime.py / Utils/allure_reporter.py
命令怎么暴露给用户           -> run.py
```

这张映射表是以后改代码时最重要的起点。

## 2. 代码思维一：先保护核心边界

当前框架最重要的边界是：

```text
Repository 只读资产
Composer 只合成执行对象
RequestResolver 只构造请求
Executor 只编排流程
Extractor 只提取变量
AssertionEngine 只判断断言
History / Allure 只输出结果
CLI 只触发入口
```

如果一个改动让某个模块开始做别人的事情，就要警惕。

例如：

- 不要在 `Executor` 里拼 multipart 文件。
- 不要在 `RequestResolver` 里判断 scenario 是否继续执行。
- 不要在 `Repository` 里展开公共断言。
- 不要在 `run.py` 里写场景执行顺序。

这些短期可能省事，长期会让框架重新变成“大函数脚本”。

## 3. 代码思维二：数据先结构化，再执行

AutoAPI 的核心链路是：

```text
YAML dict
-> data model
-> executable model
-> prepared request
-> step result
-> run result
```

所以新功能最好也遵守这个方向。

例如要新增一个请求字段：

```yaml
request:
  allow_redirects: false
```

不要直接在 `Executor` 里读 YAML。

正确思路是：

1. `Repository` 把 YAML 保存在 `ApiTemplate.request` 或 `ApiCase.request` 中。
2. `Composer` 决定它是否可以被 case / step 覆盖。
3. `RequestResolver` 把它翻译成 `requests` 参数。
4. `Executor` 不关心这个字段。

这样执行流程不需要因为一个请求字段而改变。

## 4. 代码思维三：产品规则放在 Composer

凡是涉及“模板、用例、场景步骤之间如何继承和覆盖”的规则，优先考虑 `Composer`。

例如这些问题都属于 Composer：

- case 写了字段后是否覆盖 template？
- step override 是否覆盖 case？
- `null` 是保留 None 还是清空？
- 公共断言引用后和本地断言谁先执行？
- 是否允许覆盖 `method/path`？

为什么不放在 Executor？

因为 Executor 是执行流程。如果把继承规则放进去，那么：

- case 单独执行可能是一套规则。
- scenario 中执行可能又是一套规则。
- 以后 plan 执行可能又出现第三套规则。

Composer 的价值就是让所有入口在执行前都得到统一的 `ExecutableCase / ExecutableStep`。

## 5. 代码思维四：执行流程放在 Executor，但细节不要放进去

`Executor` 只应该回答：

```text
先执行什么，失败后是否继续，最后返回什么结果？
```

例如：

```text
scenario.before_steps
-> scenario.steps
-> scenario.after_steps
-> scenario.assertions
-> scenario.finally_steps
```

这是 Executor 的职责。

但这些不是 Executor 的职责：

- raw json 怎么传给 requests。
- response header 怎么取。
- contains 怎么判断。
- Allure 附件怎么写。

判断标准：

```text
如果这个逻辑和“执行顺序”无关，就尽量不要写进 Executor。
```

## 6. 代码思维五：请求语义放在 RequestResolver

任何 HTTP 请求构造细节，都优先看 `RequestResolver`。

比如：

- `query` 映射到 `params`
- `path_params` 替换 path
- `auth` 映射到 headers / params / cookies
- `body_mode=raw` 映射到 `json` 或 `data`
- `form_data` 映射到 `files`
- `binary` 映射到 `data`

为什么要集中在这里？

因为用户看到的是 AutoAPI 请求模型，不应该被迫理解 `requests` 的参数细节。

例如 `requests` 中：

```text
json 和 data/files 同时传时，json 会被忽略
```

这种底层规则不应该散落在 YAML 或 Executor 中，而应该由 RequestResolver 负责消化。

## 7. 代码思维六：断言和提取不要互相混

提取和断言看起来都在读响应，但目标不同。

提取：

```text
从响应或上下文中取值，写入 RuntimeContext，供后续步骤使用。
```

断言：

```text
从响应或上下文中取值，和 expected 比较，决定通过或失败。
```

所以：

- 新增提取来源，优先看 `Extractor` 和 `JsonPathTool`。
- 新增断言来源，优先看 `AssertionEngine` 和 `JsonPathTool`。
- 新增断言比较方式，优先看 `AssertionEngine._eval_op`。

不要在 Extractor 里判断通过失败，也不要在 AssertionEngine 里写变量。

## 8. 代码思维七：结果对象是系统边界

当前执行结果有两层：

```text
P0StepResult：一个步骤的结果
P0RunResult：一次执行的总结果
```

这两个对象非常重要。

它们是这些模块的共同边界：

- CLI 输出
- JSONL history
- Allure 报告
- 后续趋势分析
- 后续 Web UI

所以如果要新增结果字段，例如：

```text
retry_count
dataset_name
request_size
response_size
```

不要只在 CLI 里拼字符串。

正确顺序是：

1. 先看 `Engine/results.py` 是否需要新增字段。
2. 再看 `Executor` 是否能填充字段。
3. 再看 `HistoryWriter` 是否需要写入。
4. 再看 `AllureRuntimeReporter` 是否需要展示。
5. 最后再看 CLI 是否输出。

这叫“结果模型先行”。

## 9. 示例：如果要新增一个断言 op

需求：

```text
响应体字段必须是数字
```

可能新增：

```yaml
op: is_number
```

思考路径：

1. 这是断言比较方式，不是请求构造，也不是执行流程。
2. 所以主要改 `Engine/assertion_engine.py`。
3. 找到 `_eval_op`。
4. 新增 `is_number` 分支。
5. 在 `Tests/test_repository.py` 或后续更合适的测试文件中加一个小单测。

不应该改：

- `Executor`
- `RequestResolver`
- `Repository`

因为它们和“如何判断数字”无关。

## 10. 示例：如果要新增一个 body_mode

需求：

```text
支持 GraphQL 请求。
```

可能新增：

```yaml
body_mode: graphql
graphql:
  query: |
    query Book($id: ID!) {
      book(id: $id) { name }
    }
  variables:
    id: "${bookId}"
```

思考路径：

1. 这是请求模型能力。
2. 需要判断 YAML 字段是否需要进入 `REQUEST_FIELDS`。
3. `Composer` 要允许 case/step 覆盖 `graphql`。
4. `RequestResolver` 要把 `body_mode=graphql` 翻译成 `requests json`。
5. `Executor` 不需要改，因为它只拿 `PreparedRequest` 发送。

可能修改：

- `Core/composer.py`
- `Engine/request_resolver.py`
- `docs/product_requirements.md`
- `examples/...`
- `Tests/test_repository.py`

这就是一个典型“请求模型扩展”。

## 11. 示例：如果要新增 step retry

需求：

```text
某个场景步骤失败后重试 2 次。
```

可能 YAML：

```yaml
steps:
  - id: 查询状态
    use: case_get_status
    retry:
      count: 2
      interval_seconds: 1
```

思考路径：

1. 这是执行策略，不是请求模型。
2. 需要修改 `ScenarioStep` 数据模型。
3. Repository 需要读取 retry。
4. Validator 后续需要校验 retry。
5. Executor 在 `_run_scenario_step_list` 中处理重试。
6. P0StepResult 可能需要记录 retry 信息。
7. History / Allure 可能要展示 retry 过程或最终结果。

主要修改：

- `Schema/data_models.py`
- `Core/repository.py`
- `Engine/executor.py`
- `Engine/results.py`
- `Engine/history_writer.py`
- `Utils/allure_runtime.py`
- `Tests/test_repository.py`

这就是一个典型“执行流程扩展”。

## 12. 示例：如果要新增严格字段校验

需求：

```text
YAML 中写错字段时 validate 直接报错。
```

思考路径：

1. 这是资产校验能力。
2. 不应该改 Executor。
3. 不应该让 RequestResolver 在执行时报错才发现字段拼错。
4. 应该在 `Schema/data_validation.py` 中做 schema 检查。

例如用户写错：

```yaml
body_mod: raw
```

应该在：

```bash
python run.py validate
```

阶段报错，而不是等执行时发现没有 body。

主要修改：

- `Schema/data_validation.py`
- `Exceptions/AutoApiException.py`
- `Tests/test_repository.py`
- `docs/product_requirements.md`

这就是一个典型“资产质量扩展”。

## 13. 示例：如果要新增资产索引

需求：

```text
输出接口、用例、场景之间的引用关系。
```

思考路径：

1. 这是资产分析，不是执行。
2. Repository 已经能加载完整 `ProjectAssets`。
3. 可以新增一个 asset analyzer。
4. CLI 新增命令调用 analyzer。
5. 不应该改 Executor。

可能新增：

```text
Core/asset_indexer.py
```

输入：

```text
ProjectAssets
```

输出：

```text
接口总数
用例总数
场景总数
接口被哪些用例引用
用例被哪些场景引用
未被引用的接口
```

主要修改：

- 新增 `Core/asset_indexer.py`
- 修改 `run.py`
- 添加测试

这就是一个典型“资产分析扩展”。

## 14. 判断是否 over-design

不是所有功能都需要新类。

简单判断：

```text
如果只是给已有模块补一个分支，且不会扩大职责，可以直接改已有模块。
如果新逻辑有独立输入、输出、测试价值，并且未来会继续增长，可以拆新模块。
```

例如：

- 新增一个断言 op：直接改 `AssertionEngine`。
- 新增一整套资产引用分析：可以新增 `AssetIndexer`。
- 新增一个 raw_type：直接改 `RequestResolver`。
- 新增完整 OpenAPI 导入：应该新增工具或模块，不要塞进 Repository。

## 15. 写测试的代码思维

测试不是只为了通过 CI，而是为了让你理解代码。

一个好测试应该像一个小调试案例：

```text
准备输入
-> 调用一个明确行为
-> 断言输出
```

例如测试 Composer：

```text
准备 ApiTemplate 和 ApiCase
调用 compose_case
断言 request 合成结果
```

例如测试 RequestResolver：

```text
准备 ExecutableCase、RuntimeContext、EnvProfile
调用 resolve_executable
断言 PreparedRequest.url 和 kwargs
```

例如测试 Executor：

```text
使用 fake transport
执行 scenario
断言步骤顺序、上下文变量、最终状态
```

测试时尽量不要依赖真实网络。

真实网络更适合人工验收或少量集成测试。

## 16. 以后自己改代码的固定步骤

建议以后每次改功能都按这个顺序：

```text
1. 先写清需求属于哪一层
2. 找到对应模块
3. 判断是否需要改数据模型
4. 判断是否需要改 Repository 加载
5. 判断是否需要改 Composer 合成
6. 判断是否需要改执行器
7. 判断是否需要改结果对象
8. 判断是否需要改 history / Allure / CLI
9. 补最小测试
10. 跑 validate 和 pytest
```

不要从“我想在哪个文件写代码”开始。

要从：

```text
这个能力在系统里属于哪一层？
```

开始。

## 17. 最重要的一句话

AutoAPI 当前代码思维可以浓缩成一句话：

```text
让每一层只处理自己能稳定负责的事情，把变化点固定在最合适的位置。
```

这也是你以后没有我时，能继续维护这个框架的关键。
