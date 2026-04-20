# AutoAPI 产品需求文档

版本：v0.1

## 1. 产品定位

产品名称暂定：AutoAPI。

近期定位：面向测试个人或小团队的轻量级接口自动化框架，优先解决接口模板、接口用例、场景编排、环境变量、测试计划、执行报告和执行历史这些核心问题。

远期定位：演进为多端自动化测试平台，覆盖接口自动化、Web UI 自动化、APP 自动化，并逐步结合 AI 完成用例生成、资产维护、失败诊断和辅助执行。

## 2. 产品原则

1. 资产先结构化，再谈平台化。
2. 接口模板、接口用例、场景、测试计划必须分层。
3. 场景编排必须显式，废弃隐藏的接口级 `depends_on` 链路。
4. 支持引用上层资产并局部覆盖，但覆盖规则必须简单一致。
5. 优先完成 CLI + YAML + 执行引擎 + 报告历史，暂不做 Web UI。
6. 当前框架仍不成熟，新版本以结构清晰为目标，不保留旧结构兼容。
7. 接口自动化内核必须独立于平台 UI，后续 Web 平台只是资产管理和执行入口。

## 3. 核心用户

### P0 用户

- 接口自动化测试工程师。
- 后端研发自测人员。
- 小团队测试负责人。

### P1 用户

- 需要把接口自动化接入 CI 的团队。
- 需要维护多环境、多场景回归用例的团队。

### P2 用户

- 需要 Web 协作、权限管理、资产审批、多端自动化统一管理的团队。

## 4. 核心使用流程

1. 创建接口模板。
   - 编辑基本信息，例如名称、模块、标签、负责人、优先级、状态、描述。
   - 定义接口请求模板，例如 `method`、`path`、`headers`、参数结构。
   - 定义默认前置、后置、提取和断言操作，用于后续用例复用。
   - 检查 `method + path` 不重复。
2. 基于接口模板创建接口用例。
   - 用例引用接口模板。
   - 用例继承接口模板的请求模板、默认前置、后置、提取和断言。
   - 用例可覆盖 headers、params、body、files、extract、assertions、hooks。
   - 用例禁止覆盖 `method` 和 `path`。
3. 创建业务场景。
   - 场景显式编排步骤。
   - 场景步骤引用接口用例。
   - 场景步骤可临时 override 请求参数、提取、断言和执行策略。
   - override 仅在当前场景步骤生效，不回写接口用例。
4. 创建测试计划。
   - 测试计划统筹多个场景和单接口用例。
   - 测试计划不负责选择环境。
5. 执行并查看结果。
   - 支持执行单个 case、单个 scenario、整个 plan。
   - 支持 Allure 报告。
   - 支持结构化执行历史。
   - 后续支持趋势分析。

## 5. 产品对象模型

### 5.1 接口模板 ApiTemplate

接口模板回答：这个接口是什么，以及它默认应该如何执行。

接口模板不是纯 OpenAPI 定义，而是 AutoAPI 内部的可执行接口模板，包含接口基础信息、请求模板、默认 hooks、默认 extract 和默认 assertions。

建议文件：

```text
Data/apis.yaml
```

示例：

```yaml
apis:
  api_01HX9K2A7F:
    meta:
      name: 启动任务
      module: 汉诺塔
      tags: ["任务", "启动"]
      owner: qa
      priority: P0
      status: active
      description: 启动一个汉诺塔任务

    request:
      method: post
      path: /je/orp/scenario/startDs
      headers:
        Content-Type: application/x-www-form-urlencoded

    parameters:
      body:
        scenarioMakeId:
          type: string
          required: true

    before_steps: []
    after_steps: []

    extract:
      - source: response_json
        jsonpath: $.obj
        as: taskId

    assertions:
      - source: response_json
        jsonpath: $.success
        op: ==
        expected: true
```

需求：

- `api_id` 全局唯一。
- `api_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `api_id` 推荐格式为 `api_start_task`。
- `meta.name` 是展示名，不要求全局唯一。
- `method + path` 不允许重复。
- 接口模板不包含具体业务编排依赖。
- 接口模板不包含 host 或 host_key，host 由环境规则解析。
- 接口模板允许默认前置、后置、提取和断言，用于用例复用。
- 接口定义调试属于后续平台能力，调试时可临时选择环境，但调试结果不等于正式用例。

### 5.2 接口用例 ApiCase

接口用例回答：这个接口在某个测试变体下怎么测。

建议文件：

```text
Data/cases.yaml
```

示例：

```yaml
cases:
  case_01HX9K9ZZZ:
    api: api_01HX9K2A7F

    meta:
      name: 启动任务成功
      tags: ["冒烟"]
      priority: P0

    request:
      body_type: data
      body:
        scenarioMakeId: "a9YsWRcL3MWx3FrHj95"
```

需求：

- `case_id` 全局唯一。
- `case_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `case_id` 推荐格式为 `case_start_task_success`。
- 一个接口模板可以创建多个接口用例。
- 用例默认继承接口模板的请求模板、前置、后置、提取和断言。
- 用例可以覆盖 `headers`、`params`、`body`、`files`、`extract`、`assertions`、`before_steps`、`after_steps`。
- 用例禁止覆盖 `method` 和 `path`。
- 用例可以单独执行。
- 用例支持数据驱动，具体数据驱动能力放 P1。

### 5.3 场景 Scenario

场景回答：业务流程怎么串。

建议目录：

```text
Data/Scenarios/*.yaml
```

示例：

```yaml
scenario_id: scn_01HX9M1111
env: test

meta:
  name: 汉诺塔完整流程
  module: 汉诺塔
  tags: ["回归", "主流程"]
  priority: P0

steps:
  - id: 启动业务
    use: case_01HX9K9ZZZ

  - id: 上传数据
    use: case_01HX9KB222
    override:
      request:
        params:
          taskId: "${taskId}"

  - id: 停止任务
    use: case_01HX9KC333
```

需求：

- `scenario_id` 全局唯一。
- `scenario_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `scenario_id` 推荐格式为 `scn_hanoi_main_flow`。
- 场景步骤必须显式排列。
- P0 优先支持场景步骤引用 case。
- 场景后续可以直接引用 api，但不作为 P0 必做。
- 场景步骤允许临时 override，但不回写被引用 case。
- 场景选择默认执行环境。
- 场景级前置、后置、断言、finally_steps 放 P1。
- 废弃接口级 `depends_on` 作为业务编排方式。

### 5.4 测试计划 TestPlan

测试计划回答：这次统一执行哪些资产。

建议文件：

```text
Data/plans.yaml
```

示例：

```yaml
plans:
  plan_01HX9P0001:
    meta:
      name: 汉诺塔回归计划
      owner: qa

    scenarios:
      - scn_01HX9M1111

    cases: []
```

需求：

- `plan_id` 全局唯一。
- `plan_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `plan_id` 推荐格式为 `plan_hanoi_regression`。
- 测试计划可以包含多个场景。
- 测试计划可以包含单接口用例。
- 测试计划不指定运行环境。
- 测试计划只负责任务统筹。
- 后续历史报告按 plan 聚合。

### 5.5 环境 Environment

环境回答：当前运行环境下变量是什么，host 如何解析。

建议文件：

```text
Data/config.yaml
```

示例：

```yaml
active_env: test

envs:
  test:
    variables:
      cookie:
        authorization: xxx

    hosts:
      task_service: http://127.0.0.1:1806
      ds_service: http://127.0.0.1:1808

    host_rules:
      - host: ds_service
        priority: 300
        apis:
          - api_update_member
          - api_get_value

      - host: ds_service
        priority: 200
        modules:
          - 数据服务

      - host: ds_service
        priority: 100
        path_prefixes:
          - /ds/

      - host: task_service
        priority: 0
        default: true

request_defaults:
  timeout: [3.05, 30]

sensitive_keys:
  - token
  - cookie
  - authorization
  - password
```

需求：

- 支持多环境。
- 支持环境变量。
- 支持默认请求参数。
- host 只在 Environment 中配置。
- ApiTemplate、ApiCase、ScenarioStep 不出现 host 或 host_key。
- 支持敏感字段脱敏，至少处理 `token`、`cookie`、`authorization`、`password`。
- 环境级前置、后置、鉴权模板放 P1。

## 6. ID 与引用规则

P0 阶段暂不提供自动生成 ID 能力，所有资产 ID 由用户手写。

规则：

1. 所有资产 ID 全局唯一，包括 `api_id`、`case_id`、`scenario_id`、`plan_id`。
2. ID 使用稳定、可读、语义化命名。
3. ID 推荐使用小写英文、数字、下划线。
4. ID 推荐带对象类型前缀：`api_`、`case_`、`scn_`、`plan_`。
5. 资产引用时直接写 ID，不使用 `case:`、`api:`、`scn:` 这类命名空间前缀。
6. ID 一旦被其他资产引用，不建议修改。

示例：

```yaml
cases:
  case_start_task_success:
    api: api_start_task

scenario_id: scn_hanoi_main_flow
steps:
  - id: 启动业务
    use: case_start_task_success
```

不同字段根据语义限制引用目标：

- `cases.<case_id>.api` 只能引用 `api_` 开头的接口模板 ID。
- `scenario.steps[].use` 在 P0 阶段只能引用 `case_` 开头的接口用例 ID。
- `plans.<plan_id>.scenarios[]` 只能引用 `scn_` 开头的场景 ID。
- `plans.<plan_id>.cases[]` 只能引用 `case_` 开头的接口用例 ID。

P1 阶段可提供 CLI 自动生成稳定 ID、检查 ID 命名规范、重命名 ID 并自动更新引用。

## 7. 继承与覆盖规则

AutoAPI 采用字段级整体覆盖，不做深度合并。

规则：

1. 当前层未声明某字段时，继承上层字段。
2. 当前层声明某字段且值非 null 时，该字段整体覆盖上层字段。
3. 当前层声明某字段为 null 时，表示显式清空该字段。
4. 字段内部不递归合并。
5. override 仅作用于当前执行上下文，不回写被引用资产。

示例：

```yaml
# ApiTemplate
request:
  body:
    a: 1
    b: 2

# ApiCase
request:
  body:
    a: 100
```

最终结果：

```yaml
request:
  body:
    a: 100
```

说明：`request.body` 被整体覆盖，不保留上层的 `b: 2`。

覆盖粒度以直接字段为准。例如 `request` 下的 `method`、`path`、`headers`、`params`、`body` 是独立字段。用例只写 `request.body` 时，仍继承上层的 `request.method`、`request.path` 和 `request.headers`。

## 8. host 解析规则

host 完全由当前执行环境的 `host_rules` 解析。

规则：

1. 只在当前 env 内解析 host。
2. `host_rules` 可以按 `apis`、`modules`、`path_prefixes`、`default` 命中。
3. 命中多个规则时，`priority` 高的生效。
4. `priority` 相同时，如果命中多个不同 host，则报错。
5. 没有任何规则命中且没有 default，则报错。
6. default 规则最多只能有一个。
7. `host_rules.host` 必须存在于当前 env 的 `hosts` 中。

环境优先级：

```text
CLI --env > scenario.env > config.active_env
```

说明：

- 测试计划不选择环境。
- 场景拥有默认执行环境。
- CLI 可以临时覆盖执行环境。
- 接口模板调试能力后续平台化时支持临时选择环境。

## 9. 字段校验策略

开发期间暂时屏蔽严格字段校验，默认用户输入字段均正确。

P0 阶段只保留校验器壳子和少量关键校验，避免开发期被完整 schema 约束拖慢。

P0 保留：

- YAML 文件可读取。
- 资产 ID 全局唯一检查。
- 引用关系存在性检查。
- `method + path` 重复检查。
- host_rules 基础冲突检查。

P0 暂不做：

- 所有字段完整白名单校验。
- 所有字段类型严格校验。
- 所有枚举值严格校验。
- request、extract、assertions、hooks 的完整 schema 校验。

P1 在核心执行链稳定后，再补齐严格字段校验，并将校验逻辑集中在独立 Validator 中，方便后续扩展。

## 10. 执行能力需求

### P0

- 支持基础 validate，不发请求。
- 支持执行单个 case。
- 支持执行单个 scenario。
- 支持执行 test plan。
- 支持 CLI 选择环境。
- 支持 Allure 报告。
- 支持结构化执行结果输出。
- 支持失败时输出请求、响应、上下文、异常原因。
- 支持关键配置错误时给出明确定位。

CLI 目标：

```bash
python run.py validate
python run.py --case case_01HX9K9ZZZ --env test
python run.py --scenario scn_01HX9M1111 --env test
python run.py --plan plan_01HX9P0001
python run.py --plan plan_01HX9P0001 --env prod
```

### P1

- 支持失败重试。
- 支持 step 失败继续。
- 支持场景级数据驱动。
- 支持场景级前置、后置、断言。
- 支持 `finally_steps`。
- 支持环境级前置、后置、鉴权模板。
- 支持执行历史 SQLite 落库。
- 支持公共断言和公共提取。
- 支持敏感变量脱敏。
- 支持资产索引与影响分析。

### P2

- 支持按 tag 执行。
- 支持按 priority 执行。
- 支持定时任务。
- 支持通知。
- 支持 Web UI。

## 11. 编排策略需求

### P0

- 废弃接口级 `depends_on`。
- 不保留旧 `depends_on` 兼容。
- 场景步骤必须显式。
- 废弃旧 `cleanup` 字段。
- 业务清理通过普通场景 step 显式编排。
- P0 暂不实现 `finally_steps`。

### P1

使用更统一的 hooks 模型替代旧 cleanup：

```yaml
before_steps:
  - id: 准备数据
    use: case_prepare_data

after_steps:
  - id: 正常清理
    use: case_clean_data

finally_steps:
  - id: 兜底停止任务
    use: case_stop_task
    when: always
```

语义：

- `before_steps`：主流程前执行。
- `after_steps`：主流程成功后执行。
- `finally_steps`：无论成功失败都执行。

## 12. 复制与引用策略

P0 只支持部分引用，也就是继承 + override。

规则：

- case 引用 api template。
- scenario step 引用 case。
- scenario step 可以通过 override 临时覆盖部分字段。
- override 不回写 case。
- P0 不支持全部复制。
- P0 不支持多种复制/引用模式切换。

后续平台化时再支持：

- 从接口模板复制生成接口用例。
- 从接口用例复制生成新接口用例。
- 字段级继承配置策略。
- 全量复制作为资产编辑能力，而不是执行引擎能力。

## 13. 报告与历史需求

### P0

- 保留 Allure。
- 每次执行生成 `run_id`。
- 输出结构化结果文件。

运行级历史：

```text
Reports/history/runs.jsonl
```

字段：

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

case/step 级结果：

```text
Reports/history/results.jsonl
```

字段：

```text
run_id
plan_id
scenario_id
case_id
api_id
step_id
status
method
path
url
status_code
duration_ms
error_code
error_message
```

### P1

- SQLite 存储。
- 简单趋势统计命令。

```bash
python run.py history --plan plan_01HX9P0001
```

### P2

- Web 趋势看板。

## 14. OpenAPI 导入需求

### P1

- 支持 OpenAPI 3.x 导入到 `apis.yaml`。
- 第一版只导入：
  - path
  - method
  - operationId
  - summary
  - tags
  - parameters
  - requestBody schema
- 不自动生成完整测试用例。
- 可以生成基础 case 草稿。

命令：

```bash
python tools/openapi_import.py openapi.yaml --out Data/apis.yaml
```

重复接口处理：

```text
method + path 相同：
  - 默认跳过
  - 可选择覆盖
  - 可选择生成 diff
```

## 15. 团队协作与资产管理需求

### P0

- 暂不做 Web 协作。
- 通过 Git 管理 YAML 资产。
- 通过 `meta` 字段补齐 `owner`、`tags`、`module`、`priority`、`status`。

### P1

生成资产索引：

```bash
python run.py assets
```

输出：

```text
接口模板总数
接口用例总数
场景总数
测试计划总数
接口模板被哪些用例引用
用例被哪些场景引用
场景被哪些计划引用
未被引用的接口模板
未被引用的接口用例
重复接口定义
host_rules 冲突
```

### P2

- Web UI。
- 用户权限。
- 在线编辑。
- 审批流。

## 16. 目录结构

新结构：

```text
Data/
  config.yaml
  apis.yaml
  cases.yaml
  Scenarios/
    hanoi.yaml
  plans.yaml
Reports/
  history/
    runs.jsonl
    results.jsonl
```

旧结构：

```text
Data/single.yaml
Data/Flows/*.yaml
```

旧结构处理：

- 不保留旧结构兼容。
- 新版本执行器只支持新结构。
- 可提供一次性迁移脚本，但迁移后以新结构为准。
- 旧 `depends_on` 废弃。
- 旧 `cleanup` 废弃。

## 17. 优先级总表

### P0：第一批必须做

1. 新数据模型：`apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。
2. 接口模板与接口用例分离。
3. 接口模板允许默认前置、后置、提取和断言。
4. 用例引用接口模板。
5. 场景显式编排。
6. 场景 step 引用 case。
7. 场景 step 支持临时 override。
8. 字段级整体覆盖规则。
9. 废弃旧 `depends_on`。
10. 废弃旧 `cleanup`。
11. 环境 `host_rules` 解析。
12. 全局唯一 ID 与直接引用规则。
13. 基础 validate：ID、引用关系、重复接口定义、host_rules 冲突。
14. 保留 Validator 壳子，暂不做严格字段校验。
15. CLI 支持 `validate/case/scenario/plan/env`。
16. 保留 Allure。
17. 结构化结果 JSONL。
18. 旧结构不兼容。

### P1：第二批增强

1. 场景级数据驱动。
2. step 重试。
3. step 失败继续。
4. 场景级 before_steps、after_steps、assertions。
5. finally_steps。
6. 环境级前置、后置、鉴权模板。
7. OpenAPI 导入。
8. 历史结果 SQLite。
9. 公共断言和公共提取。
10. 敏感变量脱敏。
11. 资产索引与影响分析。
12. CLI 自动生成稳定 ID。

### P2：第三批平台化

1. Web UI。
2. 团队协作。
3. 权限管理。
4. 在线调试页面。
5. 测试趋势看板。
6. 通知集成。
7. 公共脚本市场。
8. Mock。
9. 数据工厂。
10. 审批流。
11. Web UI 自动化。
12. APP 自动化。
13. AI 辅助用例生成、维护和失败诊断。
