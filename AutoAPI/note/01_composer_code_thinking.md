# Composer 代码思维笔记

对应文件：

- `Core/composer.py`

## 1. Composer 的核心角色

`Composer` 负责把“资产对象”合成为“可执行对象”。

它不读取 YAML，不发送请求，也不执行断言。它只回答一个问题：

```text
最终要执行的 request / hooks / extract / assertions 到底是什么？
```

当前合成链路：

```text
ApiTemplate + ApiCase -> ExecutableCase
ExecutableCase + ScenarioStep override -> ExecutableStep
```

这就是 Composer 的边界。

## 2. 为什么必须有 Composer

AutoAPI 有三层数据来源：

```text
ApiTemplate：接口模板层
ApiCase：接口用例层
ScenarioStep override：场景步骤层
```

如果没有 Composer，继承和覆盖逻辑会散落在：

- `Executor`
- `RequestResolver`
- `run.py`
- 甚至测试代码

这样后续会出现一个严重问题：同一个字段在不同入口下合成规则不一致。

Composer 把规则集中起来，保证：

- case 单独执行和 scenario step 执行使用同一套合成逻辑。
- 公共断言 / 公共提取只在一个地方展开。
- `method/path` 禁止覆盖只在一个地方拦截。
- `null` 清空语义只在一个地方处理。

## 3. 核心产品规则

Composer 当前固化了这些规则：

### method/path 只能来自 ApiTemplate

`ApiCase` 和 `ScenarioStep override` 都不能覆盖：

```text
method
path
```

原因：

case 是同一个接口的不同测试数据，不应该变成另一个接口。

场景 step 是业务编排，不应该绕过接口定义直接改接口路径。

### override 是字段级整体覆盖

规则：

```text
未填写：继承上层
已填写：整体覆盖上层
写 null：显式清空
```

不做 deep merge。

例如模板里有：

```yaml
headers:
  Content-Type: application/json
  X-App: demo
```

case 写：

```yaml
headers:
  Authorization: Bearer xxx
```

结果不是合并，而是：

```yaml
headers:
  Authorization: Bearer xxx
```

这是为了降低用户理解成本。用户只要记住“写了就替换”，不用理解 dict/list/scalar 各自的 merge 行为。

### null 表示清空

例如：

```yaml
assertions: null
```

含义不是把 `assertions` 变成 Python 的 `None`，而是清空继承值：

```yaml
assertions: []
```

这个逻辑由 `EMPTY_BY_FIELD` 控制。

## 4. 关键方法

### compose_case

作用：

```text
ApiTemplate + ApiCase -> ExecutableCase
```

主要步骤：

1. 检查 case.request 中不能出现 `method/path`。
2. 复制 case 和 api 的 meta。
3. 合成 request。
4. 合成 before / after hooks。
5. 展开公共 extract / assertions。
6. 返回 `ExecutableCase`。

它的输入仍然是“资产层对象”，输出已经是“可执行对象”。

### compose_step

作用：

```text
ExecutableCase + ScenarioStep override -> ExecutableStep
```

主要步骤：

1. 读取 step.override。
2. 检查 override.request 不能出现 `method/path`。
3. 在 `ExecutableCase` 基础上覆盖 request。
4. 根据 override 覆盖 hooks / extract / assertions。
5. 保留 scenario_id 和 step_id，便于报告定位。

注意：

`ScenarioStep` 不直接引用 api，而是引用 case。Composer 先把 case 合成出来，再叠加 step override。

### _compose_request

这是 request 合成的核心。

它只处理 `REQUEST_FIELDS` 中允许覆盖的字段：

```text
path_params
query
headers
cookies
auth
body_mode
form_urlencoded
raw
form_data
binary
```

逻辑非常直接：

```text
先复制 base
遍历允许覆盖字段
如果 override 里出现该字段，就整体替换
```

没有递归合并。

### _case_field

这个方法解决一个细节问题：

```text
如何区分“用户没写字段”和“用户写了空列表”？
```

例如：

```yaml
assertions: []
```

这表示用户明确要清空断言。

但如果 YAML 中完全没写 `assertions`，则应该继承模板。

所以 `ApiCase` 中保存了 `provided_fields`，Composer 通过它判断字段是否真实出现过。

### _replace_field

这个方法用于 step override。

它使用 `_MISSING` 哨兵区分：

```text
字段不存在
字段存在但值为 null
```

这是因为 Python 里的 `dict.get()` 如果拿不到字段，也可能返回 `None`，但 `None` 在 AutoAPI 里已经有“显式清空”的业务含义。

所以必须有 `_MISSING`。

### _compose_shared_rules

用于展开：

- `extract_ref`
- `assertions_ref`

规则：

```text
先展开共享规则
再追加本地规则
```

例如：

```yaml
assertions_ref:
  - common_success
assertions:
  - source: response_time_ms
    jsonpath: "$"
    op: <
    expected: 1000
```

最终执行的是：

```text
common_success 的所有断言
+ 当前本地断言
```

这样公共规则不需要让 Executor 感知。Executor 只看最终的 assertions 列表。

## 5. 数据流示例

假设模板：

```yaml
apis:
  api_update_model:
    request:
      method: post
      path: /model/{id}
      headers:
        Content-Type: application/json
      body_mode: raw
      raw:
        raw_type: json
        content:
          name: demo
```

用例：

```yaml
cases:
  case_update_model_success:
    api: api_update_model
    request:
      path_params:
        id: "${modelId}"
      raw:
        raw_type: json
        content:
          name: "${modelName}"
```

Composer 后的 request：

```yaml
method: post
path: /model/{id}
headers:
  Content-Type: application/json
body_mode: raw
path_params:
  id: "${modelId}"
raw:
  raw_type: json
  content:
    name: "${modelName}"
```

这里的关键是：

- `method/path` 从模板继承。
- `headers/body_mode` 从模板继承。
- `path_params/raw` 被 case 覆盖。
- raw 是整体覆盖，不是深度合并。

## 6. 设计收益

Composer 让 AutoAPI 的产品规则有了固定落点。

以后出现这些问题时，优先看 Composer：

- 为什么 case 没继承模板断言？
- 为什么 step override 后 headers 变了？
- 为什么 null 清空了字段？
- 为什么公共断言展开顺序是这样？
- 为什么不能覆盖 method/path？

## 7. 当前 trade-offs

当前 Composer 的成本是：

- 逻辑比简单 deep merge 多。
- `_MISSING`、`provided_fields` 需要理解。
- step override 的 extract/assertions 合成逻辑相对绕。

但这换来了一个重要收益：

```text
用户规则简单，代码内部承担复杂度。
```

用户只需要记住：

```text
不写 = 继承
写了 = 覆盖
写 null = 清空
```

## 8. 调试建议

如果你要调试 Composer，建议断点放在：

- `compose_case`
- `compose_step`
- `_compose_request`
- `_case_field`
- `_replace_field`
- `_compose_shared_rules`

重点观察：

- `api.request`
- `case.request`
- `step.override`
- `case.provided_fields`
- 合成后的 `ExecutableCase.request`
- 合成后的 `ExecutableStep.request`

## 9. 后续扩展时怎么判断是否该改 Composer

如果需求是这些，应该改 Composer：

- 新增可覆盖字段。
- 修改继承 / 覆盖规则。
- 修改公共规则展开方式。
- 增加新的 ref 类型。
- 改变 case 和 template 的合成顺序。

如果需求是这些，不应该改 Composer：

- 新增 HTTP body 类型。
- 新增断言 op。
- 新增 Allure 输出。
- 新增 CLI 参数。

这些分别属于 `RequestResolver`、`AssertionEngine`、`AllureRuntimeReporter`、`run.py`。
