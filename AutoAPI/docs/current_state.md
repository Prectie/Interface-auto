# AutoAPI 当前状态

本文档记录 P0 重构前的仓库真实状态。它只描述当前代码“现在是什么样”，不描述目标设计。

## 目录概览

当前主要目录和文件：

```text
Core/
Data/
  config.yaml
  single.yaml
  Flows/
    multiple.yaml
Engine/
Exceptions/
Profile/
Schema/
Tests/
Utils/
docs/
  product_requirements.md
run.py
pyproject.toml
requirements.txt
```

当前还存在一些生成物或本地环境目录：

```text
.pytest_cache/
.venv/
__pycache__/
allure_json_report/
allure_report/
Log/
```

这些目录不应该影响产品设计，后续可以再评估 `.gitignore` 和清理策略。

## 当前数据结构

当前可执行的数据模型仍是旧结构：

- `Data/config.yaml`
- `Data/single.yaml`
- `Data/Flows/*.yaml`

`Data/config.yaml` 当前包含：

- `env`
- `active_env`
- `static`
- `request_defaults`
- `run_control`
- `auth_profiles`

`Data/single.yaml` 当前在 `apis` 下定义接口。每个接口可以包含：

- `auth_profile`
- `is_run`
- `depends_on`
- `request`
- `extract`
- `assertions`
- `cleanup`

`Data/Flows/multiple.yaml` 当前定义 flow。主要字段包括：

- `flow_id`
- `steps`
- step `id`
- step `ref`
- step `delay_run`
- step `override`

PRD 中定义的 P0 目标文件当前还不存在：

```text
Data/apis.yaml
Data/cases.yaml
Data/Scenarios/*.yaml
Data/plans.yaml
```

## 当前入口

`run.py` 是当前唯一脚本入口。

当前行为：

- 生成带时间戳的 Allure 中间结果目录。
- 生成带时间戳的 Allure HTML 报告目录。
- 固定执行 pytest 目标：`Tests/test.py::test_flows_api`。
- 调用 `pytest.main(...)`。
- 通过 `os.system` 调用 `allure generate ...`。
- 通过 `os.system` 调用 `allure serve ...`。

当前限制：

- 没有 CLI 参数解析。
- 没有 `validate` 命令。
- 没有 `--case`、`--scenario`、`--plan`、`--env`。
- 不能执行 P0 新资产模型。
- 当前默认只跑旧 flow 测试。

## 当前 pytest 收集逻辑

`Tests/conftest.py` 负责 pytest 收集和 fixture。

当前行为：

- 使用 `PathTool.project_root(...)` 定位项目根目录和 `Data` 目录。
- 创建并缓存一个 `YamlRepository`。
- 在收集阶段调用 `YamlRepository.load()`。
- 基于旧 `single.yaml` 生成 single API 用例。
- 基于旧 `repo.flows` 生成 flow 用例。
- 在 pytest session 开始时写入 Allure environment 和 categories。
- 提供 `repo` 和 `executor_fx` fixture。

single API 收集规则：

- 通过 `repo.list_runnable_api_id()` 获取可执行 API。
- 根据旧 request 数据决定用例条数，优先级为：
  1. `body`
  2. `params`
  3. `files`
- 生成 pytest 参数 `(api_id, data_index)`。

flow 收集规则：

- 读取 `repo.flows`。
- 收集 `flow_bundle.is_run` 为 true 的 flow。

## 当前测试入口

`Tests/test.py` 定义两个 pytest 测试函数：

- `test_single_api(executor_fx, api_id, data_index)`
- `test_flows_api(executor_fx, flow_id)`

当前行为：

- `test_single_api` 调用 `executor_fx.run_single(...)`。
- `test_flows_api` 调用 `executor_fx.run_flow(...)`。
- 两者都通过 `AllureReporter` 写入 Allure 元数据。

当前还没有针对 P0 新模型的单元测试。

## 当前 Repository

`Core/repository.py` 定义 `YamlRepository`。

当前加载链路：

```text
Data/config.yaml
Data/single.yaml
Data/Flows/*.yaml
  -> YamlSchemaValidator.validate_all(...)
  -> ConfigBundle / ApiItem / FlowBundle
```

当前主要查询方法：

- `get_api(api_id)`
- `get_flow(flow_id)`
- `list_flow_ids()`
- `list_runnable_api_id()`
- `should_run_single_api(api_id)`

相对 P0 目标的限制：

- 固定加载旧 `single.yaml` 和 `Flows`。
- 没有 `ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan`。
- 不加载 `apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。
- 没有全局资产 ID 索引。
- 没有 P0 直接 ID 引用解析。
- 没有 P0 新模型的基础 Validator 壳子。

## 当前 Schema / Validator

`Schema/data_validation.py` 当前定义：

- `ConfigBundle`
- `ApiItem`
- `FlowBundle`
- `ValidatedBundle`
- `YamlSchemaValidator`

当前 Validator 面向旧结构，且校验比较严格。它会校验：

- `config.yaml`
- `single.yaml`
- flow 文档
- request 字段
- override 字段
- extract 规则
- assertions 规则
- cleanup 字段
- ref steps

相对 P0 目标的限制：

- Validator 和旧资产模型耦合。
- P0 开发期间计划暂时关闭严格字段 schema 校验。
- P0 只需要保留 Validator 壳子和基础检查：
  - YAML 可读取
  - 全局 ID 唯一
  - 引用关系存在
  - `method + path` 重复检查
  - `host_rules` 基础冲突检查

## 当前 RuntimeContext 和数据处理

`Core/context.py` 定义 `RuntimeContext`。

已有能力：

- `set`
- `update`
- `get`
- `pop`
- `snapshot`
- `fork`

`Core/data_processing.py` 当前定义：

- `deep_merge`
- `render_any`
- `render_str`

当前行为：

- `deep_merge` 会递归合并 dict。
- 非 dict 值直接覆盖。
- `${var}` 渲染支持普通 key 和点号路径。
- 变量缺失时抛 `VarResolveException`。

相对 P0 目标的限制：

- P0 要求 `override` 使用字段级整体覆盖，不做 deep merge。
- `deep_merge` 可以在旧代码过渡期间保留，但不能作为新模型的主合成规则。

## 当前 RequestResolver

`Engine/request_resolver.py` 定义 `RequestResolver`。

当前行为：

- 使用 `deep_merge` 合并 `request_defaults`、API request、override request。
- 使用 `render_any` 渲染变量。
- 根据 request 中的 `host` 和 `url` 构建完整 URL。
- 支持完整 URL，或 host key + 相对 URL。
- 根据 `body_type` 把 body 转成 `json` 或 `data`。
- 其他 requests 参数按原样传递。

相对 P0 目标的限制：

- 依赖 request 里的 `host`。
- 使用旧字段 `url`，而 P0 目标使用 `path`。
- 使用 deep merge。
- 不支持从环境 `host_rules` 解析 host。
- 不支持合成 `ApiTemplate + ApiCase + ScenarioStep override`。

## 当前 Executor

`Engine/executor.py` 当前定义：

- `ExecutionState`
- `Executor`

当前主要方法：

- `_run_auth_profile`
- `_run_depends_on`
- `_run_cleanup`
- `run_single`
- `run_flow`
- `_execute_api`

当前行为：

- 基于旧 `ApiItem` 执行 single API。
- 基于旧 `FlowBundle` 执行 flow。
- 支持 `auth_profile`。
- 支持递归 `depends_on`。
- 支持带 `when` 和 `continue_on_error` 的 cleanup。
- 使用 `SessionTransport`。
- 使用 `RequestResolver`、`Extractor`、`AssertionEngine`。
- 写入较丰富的 Allure steps 和附件。

相对 P0 目标的限制：

- 与旧 `ApiItem` 和 `FlowBundle` 耦合。
- 没有 `run_case`、`run_scenario`、`run_plan`。
- 业务流可以隐藏在 `depends_on` 中，而 P0 要移除这种模式。
- cleanup 是特殊字段，而 P0 要移除旧 `cleanup`。
- 没有 JSONL 执行历史。

## 当前 Transport

`Engine/transport.py` 定义：

- `TransportBase`
- `RequestsTransport`
- `SessionTransport`

当前行为：

- 通过 `requests.request` 或 `requests.Session` 发送请求。
- 请求发送失败时包装为 `RequestSendException`。

该模块大概率可以在 P0 复用。

## 当前 Extractor / AssertionEngine / JsonPathTool

`Engine/extractor.py` 定义 `Extractor`。

当前行为：

- 通过 `JsonPathTool` 读取 response source。
- 提取 JSONPath 第一个命中值。
- 将提取结果写入 runtime context。

`Engine/assertion_engine.py` 定义 `AssertionEngine`。

当前支持断言操作符：

- `exists`
- `==`
- `!=`
- `>`
- `>=`
- `<`
- `<=`
- `contains`
- `regex`

`Engine/jsonpath_tool.py` 当前支持 response source：

- `response_json`
- `response_text`
- `response_headers`
- `response_status`

这些模块大概率可以在 P0 复用，但外围 schema 校验和执行模型会变化。

## 当前结果与报告

`Engine/results.py` 当前定义：

- `PreparedRequest`
- `ResponseSnapshot`
- `AssertionResult`
- `ApiInvokeResult`
- `CaseResult`
- `StepResult`
- `FlowResult`

当前行为：

- 记录旧 single 和 flow 执行中的 request、response、extract、assertion、cleanup 和执行状态。

`Utils/allure_reporter.py` 定义 `AllureReporter`。

当前行为：

- 设置 single 和 flow 元数据。
- 附加 request、response、context、extract trace、assertion、exception、case result、flow result、execution state。
- 写入 Allure `environment.properties` 和 `categories.json`。

相对 P0 目标的限制：

- Result 对象和 Allure 元数据仍面向旧模型命名。
- 没有 plan 级报告。
- 没有 JSONL history writer。

## 当前 YAML 工具

`Utils/yaml_io.py` 提供：

- `load_yaml_file`
- `load_yaml_documents`

当前行为：

- 从项目根目录解析相对路径。
- 支持单文档 YAML 和多文档 YAML。
- YAML 读取异常会包装为结构化异常。

该模块大概率可以在 P0 复用。

## 当前路径工具

`Utils/path_utils.py` 支持通过 marker 文件查找项目根目录。

该模块大概率可以在 P0 复用。

## 当前配置和依赖说明

`pyproject.toml` 包含 pytest 配置：

- `testpaths = ["Tests"]`
- `python_files = ["test_*.py"]`
- `pythonpath = ["."]`

其中许多 pytest 和环境相关配置仍是注释状态。

`requirements.txt` 在 shell 中显示为带 NUL 的异常文本或类似 UTF-16 的内容。后续可能需要清理，但这不是第一步 P0 规划任务的一部分。

## 当前生成物

仓库中当前存在生成物：

- `allure_json_report/`
- `allure_report/`
- `__pycache__/`
- `.pytest_cache/`

这些不应该驱动产品设计。后续可以单独评估清理或 `.gitignore`。

## 关键重构风险

1. `YamlRepository` 固定加载旧数据文件。
2. `YamlSchemaValidator` 严格且耦合旧模型，而 P0 只需要基础校验。
3. `RequestResolver` 当前使用 `deep_merge` 和 request `host`，而 P0 要字段级整体覆盖和环境 `host_rules`。
4. `Executor` 耦合 `ApiItem`、`FlowBundle`、`depends_on`、`cleanup`。
5. `Tests/conftest.py` 通过 pytest hook 收集旧 single 和 flow。
6. `run.py` 没有 CLI router，且固定执行旧 flow。
7. Allure reporting 可以复用，但旧模型命名和 metadata 需要调整。
8. JSONL 执行历史不存在。

## 当前基线结论

当前仓库是一个可运行的旧模型 `YAML + pytest + Allure` 接口自动化原型。P0 产品方向是破坏式重构，而不是旧结构兼容层。第一批实现任务应该避免兼容旧结构，围绕新模型建立加载、解析、执行和报告链路。

