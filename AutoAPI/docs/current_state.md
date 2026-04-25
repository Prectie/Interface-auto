# AutoAPI 当前状态

本文档记录仓库真实状态。早期章节保留 P0 重构前的基线描述；本节记录当前 P0 实现推进后的实际状态。

## 当前 P0 状态：2026-04-25

当前已完成 P0 的基础资产加载、基础校验、字段级合成、`host_rules` 解析、`case/scenario/plan` 执行链、CLI 路由、JSONL history 初版、Allure 新模型元数据适配，以及请求模型前三个阶段的可运行子集实现。

已实现文件：

```text
Schema/data_models.py
Core/repository.py
Schema/data_validation.py
Core/composer.py
Engine/host_resolver.py
Engine/request_resolver.py
Engine/executor.py
Engine/history_writer.py
Engine/results.py
Utils/allure_reporter.py
Utils/yaml_io.py
Tests/test_repository.py
Tests/conftest.py
run.py
```

当前可用能力：

- `run.py validate --data <DataDir>` 可以加载并基础校验 P0 新结构。
- `YamlRepository` 可以加载 `config.yaml`、`apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。
- `YamlSchemaValidator.validate_project(...)` 已支持基础检查：
  - 全局 ID 唯一。
  - case 引用 api 存在。
  - scenario step 引用 case 存在。
  - plan 引用 scenario/case 存在。
  - `method + path` 重复检查。
  - `active_env` 和 `host_rules` 基础检查。
- `Composer` 已支持：
  - `ApiTemplate + ApiCase -> ExecutableCase`。
  - `ExecutableCase + ScenarioStep override -> ExecutableStep`。
  - 字段级整体覆盖。
  - `null` 显式清空。
  - 禁止覆盖 `method/path`。
- `HostResolver` 已支持：
  - `apis` 匹配。
  - `path_prefixes` 匹配。
  - `default` 匹配。
  - `priority` 冲突判断。
- `RequestResolver.resolve_executable(...)` 已支持 P0 新请求构建入口：
  - 使用 `request.path`。
  - 使用环境 `host_rules` 拼接 base URL。
  - 使用 `render_any` 渲染变量。
  - 支持 `query` -> `requests params`。
  - 支持 `path_params` 路径模板替换。
  - 支持 `body_mode=raw`：
    - `raw_type=json` -> `requests json`
    - `raw_type=text/xml/html/javascript` -> `requests data`
    - 对 `text/xml/html/javascript` 自动补默认 `Content-Type`，但不覆盖用户显式 headers。
  - 支持 `body_mode=form_urlencoded`。
  - 支持 `body_mode=form_data`，其中 `kind=file` 使用极简模型 `name + path`。
  - 支持 `cookies`。
  - 支持 `auth.type=none/bearer/basic/api_key`。
  - 支持 `body_mode=binary`，当前仅支持 `source=path`。
- `Executor` 已新增 P0 新执行入口：
  - `run_case(...)`。
  - `run_scenario(...)`。
  - `run_plan(...)`。
  - scenario step 共享同一个 `RuntimeContext`。
  - P0 默认失败即停止。
- `run.py` 已支持：
  - `validate`。
  - `--case`。
  - `--scenario`。
  - `--plan`。
  - `--env`。
- `HistoryWriter` 已支持写入：
  - `Reports/history/runs.jsonl`。
  - `Reports/history/results.jsonl`。
- `AllureRuntimeReporter` 已接入 CLI 主链路：
  - 每次执行写入 `Reports/allure-results/<run_id>/`
  - 尝试生成 `Reports/allure-report/<run_id>/`
  - 终端输出 `allure_results` 和 `allure_report` 路径
  - 若 `allure` CLI 缺失或 HTML 生成失败，只输出 warning，不改变真实测试退出状态
- `EnvProfile` 当前代码仍保留一版环境级执行配置：
  - `setup_cases`
  - `teardown_cases`
  - `auth_profiles`
  - `auth_profile`
- `Executor` 顶层 `run_case / run_scenario / run_plan` 已支持：
  - 先执行环境 `setup_cases`
  - 再执行环境 `auth_profile.setup_cases`
  - 再执行目标资产
  - 最后执行环境 `auth_profile.teardown_cases` 和 `teardown_cases`
  - 环境 hooks 与目标资产共享同一个 `RuntimeContext`
- 以上环境级执行配置已经和最新产品方向冲突：
  - hooks 不应引用 case。
  - 环境不应承载业务接口编排。
  - 登录、准备数据、清理数据等接口动作应放在 `Scenario.steps` 中显式编排。
  - 后续需要从模型、仓库加载、校验、执行器、示例和测试中清理。
- `EnvironmentConfig` 已支持第一版公共规则注册表：
  - `shared_extracts`
  - `shared_assertions`
- `ApiTemplate`、`ApiCase`、`ScenarioStep override` 已支持：
  - `extract_ref`
  - `assertions_ref`
- `Composer` 已支持在合成阶段展开公共断言/提取：
  - 先展开共享规则
  - 再追加本地 `extract` / `assertions`
  - 不新增新的执行层级
- `Scenario` 已支持第一版 `datasets`：
  - 每个 dataset 对应一轮完整场景执行
  - dataset variables 优先覆盖 env variables
  - 每轮使用独立 `RuntimeContext`
- `Scenario` 已支持第一版场景级 hooks，但当前实现仍复用 `ScenarioStep(use=case_id)`，需要按最新产品方向迁移为 action-only：
  - `before_steps`
  - `after_steps`
  - `assertions`
  - `finally_steps`
  - 执行顺序 = `before -> steps -> after(success only) -> scenario assertions -> finally(always)`
- `HistoryWriter` 已支持 step 级 `dataset_name / dataset_index`
- `AllureReporter` 已切换到 P0 新模型命名：
  - `set_case_metadata(...)`。
  - `set_scenario_metadata(...)`。
  - `set_plan_metadata(...)`。
  - `attach_p0_step_result(...)`。
  - `attach_p0_run_result(...)`。
- `PreparedRequest.to_dict()` 已支持更易读的请求快照：
  - multipart `files` 摘要化输出。
  - binary `data` 摘要化输出。
  - `headers / requests params / cookies` 中明显敏感 key 的最小隐藏。
- 旧 `single/flow/depends_on/cleanup` 执行入口已从主代码路径移除：
  - `Core/repository.py` 不再加载 `single.yaml` 和 `Flows/*.yaml`。
  - `Schema/data_validation.py` 不再保留旧 `ConfigBundle/ApiItem/FlowBundle`。
  - `Engine/executor.py` 不再保留 `run_single/run_flow/depends_on/cleanup`。
  - `Tests/conftest.py` 不再动态收集旧 single/flow pytest 用例。
  - `Engine/results.py` 不再保留旧 `CaseResult/FlowResult`。
  - `Engine/request_resolver.py` 不再保留旧 `host/url/deep_merge` 请求入口。

当前验证结果：

```text
python run.py validate --data examples/p0_minimal/Data
```

在用户 Windows `.venv` 环境中已通过：

```text
AutoAPI validate passed
apis: 3
cases: 3
scenarios: 1
plans: 1
```

```text
python -m pytest -q
```

在用户 Windows `.venv` 环境中已通过：

```text
8 passed
```

以下请求模型阶段也已在用户 Windows `.venv` 环境中完成验证：

```text
request_01_query_path_raw
```

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

```text
request_02_form_modes
```

- `python run.py validate --data examples/reading_house/Data`
- `python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data`
- `python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data`
- `python run.py --plan plan_reading_house_public_smoke --env test --data examples/reading_house/Data`
- `python run.py --case case_user_login_success --env test --data examples/reading_house/Data`
- `python -m pytest -q`

```text
request_03_cookies_auth_binary
```

- `python run.py validate --data examples/reading_house/Data`
- `python run.py --scenario scn_reading_house_auth_flow --env test --data examples/reading_house/Data`
- `python run.py --case case_user_info_success --env test --data examples/reading_house/Data`
- `python -m pytest -q`

用户已人工确认以上结果通过。

以下 CLI 执行命令已在用户 Windows `.venv` 环境中验证可以进入真实请求发送阶段：

```text
python run.py --case case_start_task_success --env test --data examples/p0_minimal/Data
python run.py --scenario scn_hanoi_main_flow --env test --data examples/p0_minimal/Data
python run.py --plan plan_hanoi_regression --env test --data examples/p0_minimal/Data
```

三条命令当前结果均为 `error`，失败原因是请求 `http://127.0.0.1:1806/je/orp/scenario/startDs` 时目标连接被拒绝。该结果说明 CLI、Repository、Composer、HostResolver、RequestResolver、Executor 和 HistoryWriter 已串到真实 HTTP 发送阶段，但本地目标服务未连通。

当前限制：

- `run_case/run_scenario/run_plan` 已实现，并已验证可以进入真实 HTTP 请求；仍需要在目标服务可用时验证成功路径。
- `--case/--scenario/--plan/--env` 已实现，并已根据失败执行结果补充 CLI 失败诊断输出。
- JSONL history 已实现，真实失败执行已写入 `Reports/history/*.jsonl`；成功路径仍待目标服务可用时验证。
- Allure 自动 HTML 已接入 CLI 主链路，但当前仓库 shell 无 `python`，仍需用户在 Windows `.venv` 中验证真实产物目录和 `allure` CLI 的行为。
- `RequestResolver` 当前只覆盖请求模型前三个阶段：
  - 已支持 `query / path_params / raw(json/text/xml/html/javascript) / form_urlencoded / form_data / cookies / auth / binary`
  - `form_data.kind=file` 当前只要求 `name + path`
  - `binary` 当前仍仅支持 `source=path`
- 当前的敏感信息处理只是请求快照最小隐藏，还不是 PRD 中 P2 的完整脱敏体系。
- `Data/single.yaml`、`Data/Flows/*.yaml` 等旧资产文件如仍存在，只作为历史文件存在；当前代码主路径不再读取它们。
- 当前环境级 hooks 第一版只支持“引用 case 作为执行载体”，该方向已废弃，待清理。
- 当前公共断言 / 公共提取第一版只支持：
  - 顶层 `config.yaml` 注册
  - `extract_ref / assertions_ref` 一层引用
  - 不支持共享规则继续引用共享规则
- 当前场景级数据驱动第一版只支持：
  - `Scenario.datasets`
  - 失败即停止后续 dataset
  - 不支持数据集筛选、tag
- 当前场景级 hooks 第一版只支持：
  - `before_steps / after_steps / assertions / finally_steps`
  - 仅支持引用 case 作为执行载体，该方向已废弃，待迁移为 `action.kind`
  - 场景级 assertions 第一版只支持 `source=context`
  - 不支持复杂 `when` 条件
  - 不支持场景级 `extract`

本轮 Allure 自动 HTML 的新增静态验证：

```text
git diff --check -- plans/07_execution_enhancements_backlog.md plans/08_allure_auto_html.md Utils/allure_runtime.py run.py Tests/test_repository.py
```

已通过。

本轮待用户在 Windows `.venv` 中补充的运行时验证：

```text
python run.py validate --data examples/reading_house/Data
python -m pytest -q
python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data
```

其中最后一条主要观察：

- CLI 是否输出 `allure_results` / `allure_report`
- `Reports/allure-results/<run_id>/` 是否生成
- 若本机未安装 `allure` CLI，是否只输出 warning 而不改变真实退出状态

以下执行增强能力也已在用户 Windows `.venv` 环境中完成验证：

```text
env_hooks_and_auth_profile
```

- `python run.py validate --data examples/reading_house/Data`
- `python -m pytest -q`
- `python run.py --case case_user_info_success --env test_auth --data examples/reading_house/Data`

```text
shared_assertions_and_extracts
```

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

```text
scenario_datasets
```

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

```text
scenario_hooks_and_finally
```

- `python run.py validate --data examples/p0_minimal/Data`
- `python -m pytest -q`

用户已人工确认以上结果通过。

---

## P0 重构前基线

以下内容记录 P0 重构前的仓库真实状态。它只描述当时代码“是什么样”，不描述目标设计。

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
