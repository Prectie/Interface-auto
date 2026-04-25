# AutoAPI P0 技术设计

版本：v0.2

本文档只覆盖 P0 新模型重构。它回答“代码准备怎么做”，不重复 PRD 的产品描述，也不设计 P1/P2 的 OpenAPI、SQLite、Web UI、通知和平台化能力。

说明：

- `docs/product_requirements.md` 已经把请求模型标准升级为更完整的 Postman / MeterSphere 风格。
- 当前 P0 代码实现仍可能只覆盖其中的一个可运行子集。
- 技术设计需要同时说明“当前怎么做”和“后续往哪个标准演进”，避免后续继续在旧 `params/body_type/files` 抽象上打补丁。

## 1. 目标架构

P0 执行链路：

```text
YAML Assets
  -> Repository
  -> Validator
  -> Composer
  -> HostResolver
  -> RequestResolver
  -> Executor
  -> Allure + JSONL History
```

核心资产模型：

```text
ApiTemplate -> ApiCase -> Scenario -> TestPlan
```

P0 需要支持的命令：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_hanoi_main_flow --env test
python run.py --plan plan_hanoi_regression --env test
```

## 2. 目录与文件

目标数据目录：

```text
Data/
  config.yaml
  apis.yaml
  cases.yaml
  Scenarios/
    *.yaml
  plans.yaml
```

P0 示例资产已经放在：

```text
examples/p0_minimal/Data/
```

建议代码落点：

```text
Schema/data_models.py          # 新 dataclass
Schema/data_validation.py      # P0 Validator 壳子和基础检查
Core/repository.py             # 加载新 YAML 资产
Core/composer.py               # ApiTemplate + ApiCase + step override 合成
Engine/host_resolver.py        # env.host_rules -> base_url
Engine/request_resolver.py     # 新请求构建逻辑
Engine/executor.py             # run_case / run_scenario / run_plan
Engine/history_writer.py       # JSONL history 输出
run.py                         # CLI router
```

现有可复用模块：

- `Core/context.py`：继续作为 `RuntimeContext`。
- `Core/data_processing.py`：保留 `render_any` / `render_str`，新模型不使用 `deep_merge` 作为合成规则。
- `Engine/transport.py`：继续发送 HTTP 请求。
- `Engine/extractor.py`：继续负责响应提取。
- `Engine/assertion_engine.py`：继续负责断言。
- `Utils/allure_reporter.py`：继续负责 Allure step、attachment、异常附件。
- `Utils/yaml_io.py`：继续负责 YAML 读取。

## 3. 数据对象

P0 新增 dataclass 建议放在 `Schema/data_models.py`。

注意：

- 数据对象中的 `request` 当前仍可先保留为 `dict`，避免在 P0 一次性把所有请求子结构完全 dataclass 化。
- 但文档层的长期标准字段已经是：`path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`timeout`、`verify`、`allow_redirects`。
- `form_data.kind=file` 当前产品模型收敛为 `name + path`；上传文件名和 content type 由框架内部按 multipart 基本规则推导，不作为用户字段。
- 后续实现不要再围绕旧 `params/body_type/files` 扩展新能力。

最小对象：

```text
ProjectAssets
  config: EnvironmentConfig
  apis: dict[str, ApiTemplate]
  cases: dict[str, ApiCase]
  scenarios: dict[str, Scenario]
  plans: dict[str, TestPlan]

EnvironmentConfig
  active_env: str
  envs: dict[str, EnvProfile]
  request_defaults: dict
  sensitive_keys: list[str]

EnvProfile
  variables: dict
  hosts: dict[str, str]
  host_rules: list[HostRule]

HostRule
  host: str
  priority: int
  apis: list[str]
  modules: list[str]
  path_prefixes: list[str]
  default: bool

ApiTemplate
  id: str
  meta: dict
  request: dict
  parameters: dict
  before_steps: list
  after_steps: list
  extract: list
  assertions: list

ApiCase
  id: str
  api: str
  meta: dict
  request: dict
  before_steps: list
  after_steps: list
  extract: list
  assertions: list

Scenario
  id: str
  env: str | None
  meta: dict
  steps: list[ScenarioStep]

ScenarioStep
  id: str
  use: str
  override: dict
  delay: float | int | None

TestPlan
  id: str
  meta: dict
  scenarios: list[str]
  cases: list[str]
```

运行时对象：

```text
ExecutableCase
  case_id
  api_id
  meta
  request
  before_steps
  after_steps
  extract
  assertions

ExecutableStep
  scenario_id
  step_id
  case_id
  api_id
  request
  before_steps
  after_steps
  extract
  assertions

ExecutionResult
  run_id
  target_type
  target_id
  status
  counters
  details
```

## 4. Repository

`YamlRepository.load()` 改为加载新结构：

```text
config.yaml
apis.yaml
cases.yaml
Scenarios/*.yaml
plans.yaml
```

加载规则：

- `apis.yaml` 顶层读取 `apis`。
- `cases.yaml` 顶层读取 `cases`。
- `Scenarios/*.yaml` 每个文件读取一个 scenario。
- `plans.yaml` 顶层读取 `plans`。
- 所有资产 ID 放入全局索引，用于唯一性检查和直接引用解析。

Repository 对执行层提供：

```text
get_api(api_id)
get_case(case_id)
get_scenario(scenario_id)
get_plan(plan_id)
get_env(env_name | None)
list_ids()
```

P0 不保留旧方法作为主路径：

- `list_runnable_api_id`
- `get_flow`
- `should_run_single_api`

这些旧方法可以在重构时删除或隔离，但新执行链不再依赖它们。

## 5. Validator

P0 暂不做严格字段 schema 校验。`YamlSchemaValidator` 只保留基础检查壳子：

```text
validate_project(assets)
```

P0 必须检查：

- YAML 文件能读取。
- 全局 ID 唯一。
- `case.api` 引用存在。
- `scenario.steps[].use` 引用存在，且 P0 只能引用 `case_` ID。
- `plan.scenarios[]` 引用存在。
- `plan.cases[]` 引用存在。
- `ApiTemplate.request.method + ApiTemplate.request.path` 不重复。
- `config.active_env` 存在于 `envs`。
- 每个 `host_rules[].host` 存在于当前 env 的 `hosts`。
- 每个 env 最多只能有一个 `default: true` rule。

P0 不检查：

- 未知字段。
- 字段完整类型。
- 参数 schema 是否完整。
- assertion/extract 的全部字段是否合法。

这样做是为了先稳定模型和执行链，避免早期开发阶段被字段校验拖慢。后续严格校验仍放在 `YamlSchemaValidator` 内扩展，但优先级已经调整到 P2。

## 6. 组合规则

组合由 `Core/composer.py` 负责。

### 6.1 ApiTemplate + ApiCase

输入：

```text
ApiTemplate
ApiCase
```

输出：

```text
ExecutableCase
```

继承规则：

- `method`、`path` 永远来自 `ApiTemplate.request`。
- `path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`timeout`、`verify`、`allow_redirects`、`before_steps`、`after_steps`、`extract`、`assertions` 可由 case 覆盖。
- 未填写字段继承上层。
- 已填写字段整体替换上层。
- 字段值为 `null` 表示显式清空。
- 不做 dict deep merge。

case 中如果出现 `method` 或 `path`，P0 可以先在组合阶段抛错；严格字段校验稳定后再提前到 Validator。

### 6.2 ExecutableCase + ScenarioStep override

输入：

```text
ExecutableCase
ScenarioStep.override
```

输出：

```text
ExecutableStep
```

规则与 case 覆盖一致：

- step override 不能覆盖 `method/path`。
- step override 只影响当前步骤。
- step override 不回写 case。
- 字段级整体替换，不做 deep merge。

### 6.3 字段覆盖函数

建议提供一个小函数：

```text
replace_field(base, override, field_name)
```

语义：

- override 不包含该 field：返回 base field。
- override 包含该 field 且值不是 null：返回 override field。
- override 包含该 field 且值为 null：返回空值。

空值按字段类型约定：

- `path_params/query/headers/cookies/auth/form_urlencoded/raw/binary/request`：`{}`
- `form_data/extract/assertions/before_steps/after_steps`：`[]`
- `body_mode/timeout/verify/allow_redirects`：`None`

## 7. 环境与 host_rules

P0 不在 ApiTemplate、ApiCase、ScenarioStep 中写 `host` 或 `host_key`。

执行环境来源：

```text
CLI --env > scenario.env > config.active_env
```

TestPlan 不选择环境。

`HostResolver` 输入：

```text
env_profile
api_id
api_meta.module
request.path
```

匹配来源：

- `apis`
- `modules`
- `path_prefixes`
- `default`

匹配规则：

1. 收集所有匹配 rule。
2. 按 `priority` 从高到低排序。
3. 取最高优先级 rule 的 `host`。
4. 如果最高优先级并列且 host 不同，抛出配置冲突。
5. 如果没有匹配 rule，抛出无法解析 host。

最终 URL：

```text
base_url.rstrip("/") + path
```

## 8. 请求构建

`RequestResolver` 新职责：

```text
ExecutableStep/ExecutableCase + env + ctx -> PreparedRequest
```

步骤：

1. 注入 `request_defaults`。
2. 通过 `HostResolver` 得到 `base_url`。
3. 使用 `path_params` 渲染 `path`，再拼接完整 URL。
4. 使用 `render_any` 渲染 `${var}`。
5. 处理 `query`、`headers`、`cookies`、`auth`、`timeout`、`verify`、`allow_redirects`。
6. 根据 `body_mode` 分发到请求体构建逻辑：
   - `none` -> 不构建请求体
   - `form_data` -> `requests` 的 multipart 结构
   - `form_urlencoded` -> `kwargs["data"]`
   - `raw` -> 根据 `raw.raw_type` 决定 `json` 或 `data`
   - `binary` -> 请求体直接使用二进制内容
7. 输出 `PreparedRequest`。

注意：

- 新模型字段名使用 `path`，不再使用旧 `url`。
- 新模型不再读取 request-level `host`。
- `request_defaults` 与 request 的合成也使用字段级整体覆盖，不使用 `deep_merge`。
- 当前 P0 可先实现一个最小可运行子集，例如 `query`、`headers`、`raw(json)`、`form_urlencoded`、基础 `form_data`。
- `raw(text/xml/html/javascript)` 进入 `kwargs["data"]`，并按类型补默认 `Content-Type`；若用户已显式声明 `headers.Content-Type`，执行层不覆盖用户值。
- 后续不应继续在旧 `params/body_type/files` 概念上叠加能力，而应直接往文档标准的 `body_mode` 模型收敛。

## 9. Executor

`Executor` P0 对外提供：

```text
run_case(case_id, env_name=None, run_id=None)
run_scenario(scenario_id, env_name=None, run_id=None)
run_plan(plan_id, env_name=None, run_id=None)
```

### 9.1 run_case

流程：

1. 创建 `RuntimeContext`。
2. 注入 env variables。
3. 读取 case 和 api。
4. composer 合成 `ExecutableCase`。
5. 执行 before_steps。
6. 构建并发送请求。
7. 执行 extract，写入 ctx。
8. 执行 assertions。
9. 执行 after_steps。
10. 写 Allure 和 JSONL result。

P1 的 before_steps / after_steps 使用 action-only 模型，不引用 case 或 api。第一批只实现 `action.kind=wait`；`sql` 和 `script` 只保留结构扩展点，具体执行器后续单独设计。action 内部如果需要提取执行结果，统一使用 `extract` 字段，保持提取语义命名一致。

### 9.2 run_scenario

流程：

1. 创建一个 scenario 级 `RuntimeContext`。
2. 注入 env variables。
3. 按 `steps` 顺序执行。
4. 每个 step 复用同一个 ctx。
5. step 失败时 P0 默认终止 scenario。
6. P1 再支持 `continue_on_error` 和 `finally_steps`。

### 9.3 run_plan

流程：

1. 读取 plan。
2. 生成一个 `run_id`。
3. 按 plan 中顺序执行 scenarios。
4. 再执行 plan 中独立 cases。
5. plan 自身不选择环境，环境由 CLI 或 scenario/config 决定。
6. 汇总 run 级结果。

## 10. 报告与 History

Allure：

- 保留现有 `AllureReporter`。
- case、scenario、step 需要写入可读的 Allure step。
- 失败时附加请求、响应、上下文、异常原因。
- 每次执行完成后自动生成：
  - `Reports/allure-results/<run_id>/`
  - `Reports/allure-report/<run_id>/`
- CLI 默认输出 HTML 报告路径，不自动打开浏览器。
- 如果 Allure CLI 缺失或 HTML 生成失败，只输出 warning，不改变真实测试执行结果。

JSONL：

```text
Reports/history/runs.jsonl
Reports/history/results.jsonl
```

`runs.jsonl` 最小字段：

```text
run_id
target_type
target_id
env
status
started_at
ended_at
duration_ms
passed_count
failed_count
error_count
```

`results.jsonl` 最小字段：

```text
run_id
plan_id
scenario_id
case_id
api_id
step_id
status
method
url
status_code
duration_ms
error_code
error_message
```

敏感字段脱敏：

- 该能力已从 P1 下调到 P2。
- P0 技术设计里只保留接口和扩展位置，不要求当前阶段落地。
- 后续可在 history / Allure 附件写入层统一处理。

## 11. CLI

`run.py` 改为 `argparse` CLI router。

目标：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_hanoi_main_flow --env test
python run.py --plan plan_hanoi_regression --env test
```

规则：

- `validate` 只加载和基础校验，不执行请求。
- `--case`、`--scenario`、`--plan` 三者一次只能指定一个。
- `--env` 可选。
- 没有指定执行目标时，输出帮助信息并退出非 0。
- 执行失败时退出非 0。

P0 不需要保留当前固定 pytest 入口作为主入口。

## 12. 测试策略

优先补最小可验证测试。

建议测试项：

- Repository 能加载 `examples/p0_minimal/Data`。
- Validator 能发现重复 ID。
- Validator 能发现 case 引用不存在。
- Validator 能发现重复 `method + path`。
- Composer 能完成模板到 case 的字段级覆盖。
- Composer 不做 deep merge。
- Composer 能识别 `null` 清空。
- HostResolver 能按 `apis` 命中。
- HostResolver 能按 `path_prefixes` 命中。
- HostResolver 能按 default 命中。
- CLI `validate` 能对示例资产返回成功。

涉及真实 HTTP 的测试先做薄测试或 mock，避免 P0 被外部服务稳定性影响。

## 13. 实施边界

P0 实现时不做：

- 旧 `single.yaml` / `Flows` 兼容。
- OpenAPI import。
- SQLite。
- Web UI。
- tag / priority 执行。
- scenario 级数据驱动。
- `finally_steps`。
- 自动生成 ID。
- 字段级继承策略。
- 严格 schema 校验。

如果实现过程中发现必须突破这些边界，需要先更新 ExecPlan 和 decision_log，再继续实现。

## 14. 迁移策略

当前框架仍处于不成熟阶段，因此 P0 采用破坏式新结构。

处理原则：

- 新代码路径只服务新 YAML 资产。
- 旧 `Data/single.yaml`、`Data/Flows/*.yaml` 不再参与新执行。
- 如果需要迁移旧资产，后续单独做一次性迁移脚本。
- 不在 P0 主执行链里保留旧结构判断分支。

## 15. 验收标准

P0 第一阶段验收：

- `examples/p0_minimal/Data` 可以被 Repository 加载。
- `python run.py validate` 可以完成基础校验。
- `python run.py --case case_start_task_success --env test` 可以进入新 case 执行链。
- `python run.py --scenario scn_hanoi_main_flow --env test` 可以按步骤显式执行。
- `python run.py --plan plan_hanoi_regression --env test` 可以统一执行 plan。
- 执行后生成 Allure 原始结果和 HTML 报告目录。
- 执行后写入 `Reports/history/runs.jsonl` 和 `Reports/history/results.jsonl`。
- 失败时能输出请求、响应、上下文和异常原因。
