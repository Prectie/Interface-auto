# AutoAPI 产品需求文档

版本：v0.2

## 1. 产品定位

产品名称暂定：AutoAPI。

近期定位：面向测试个人或小团队的轻量级接口自动化框架，优先解决接口模板、接口用例、场景编排、环境变量、测试计划、执行报告和执行历史这些核心问题。

远期定位：演进为多端自动化测试平台，覆盖接口自动化、Web UI 自动化、APP 自动化，并逐步结合 AI 完成用例生成、资产维护、失败诊断和辅助执行。

## 2. 产品原则

1. 资产先结构化，再谈平台化。
2. 接口模板、接口用例、场景、测试计划必须分层。
3. 场景编排必须显式，废弃隐藏的接口级 `depends_on` 链路。
4. 支持引用上层资产并局部覆盖，但覆盖规则必须简单一致。
5. 请求模型按 Postman / MeterSphere 的长期心智设计，文档层先定义完整标准，实现分阶段推进。
6. 优先完成 CLI + YAML + 执行引擎 + 报告历史，暂不做 Web UI。
7. 当前框架仍不成熟，新版本以结构清晰为目标，不保留旧结构兼容。
8. 接口自动化内核必须独立于平台 UI，后续 Web 平台只是资产管理和执行入口。

## 3. 核心用户

### P0 用户

- 接口自动化测试工程师。
- 后端研发自测人员。
- 小团队测试负责人。

### P1 用户

- 需要把接口自动化接入 CI 的团队。
- 需要维护多环境、多场景回归用例的团队。

### P2 用户

- 需要更完整请求建模、执行增强、导入能力、历史分析和平台化能力的团队。
- 需要 Web 协作、权限管理、资产审批、多端自动化统一管理的团队。

## 4. 核心使用流程

1. 创建接口模板。
   - 编辑基本信息，例如名称、模块、标签、负责人、优先级、状态、描述。
   - 定义接口请求模板，例如 `method`、`path`、`path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`。
   - 定义默认前置、后置、提取和断言操作，用于后续用例复用；前置/后置只表达动作，不引用接口用例。
   - 检查 `method + path` 不重复。
2. 基于接口模板创建接口用例。
   - 用例引用接口模板。
   - 用例继承接口模板的请求模板、默认前置、后置、提取和断言。
   - 用例可覆盖 `path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`extract`、`assertions`、`hooks`。
   - 用例禁止覆盖 `method` 和 `path`。
3. 创建业务场景。
   - 场景显式编排步骤。
   - 场景步骤引用接口用例。
   - 场景步骤可临时 override 请求参数、提取、断言和执行策略。
   - override 仅在当前场景步骤生效，不回写接口用例。
   - 场景后续支持数据集 `datasets`，实现同一流程多轮完整执行。
4. 创建测试计划。
   - 测试计划统筹多个场景和单接口用例。
   - 测试计划不负责选择环境。
5. 执行并查看结果。
   - 支持执行单个 case、单个 scenario、整个 plan。
   - 支持结构化执行历史。
   - 执行完成后自动生成 Allure HTML 报告。
   - 后续支持趋势分析。

## 5. 请求模型标准

### 5.1 目标

AutoAPI 的请求模型长期目标是接近 Postman / MeterSphere 的表达方式，而不是只围绕当前代码里简化的 `body_type + body + files + params` 继续打补丁。

文档层从本版本开始统一使用以下标准字段名：

- `path_params`
- `query`
- `headers`
- `cookies`
- `auth`
- `body_mode`
- `form_data`
- `form_urlencoded`
- `raw`
- `binary`

当前代码实现可能仍只覆盖其中一部分，但 PRD 先定义长期标准。

### 5.2 标准结构

```yaml
request:
  method: post
  path: /models/{modelId}/result

  path_params:
    modelId: "${model_id}"

  query:
    taskId: "${taskId}"
    verbose: true

  headers:
    X-Trace-Id: "${traceId}"

  cookies:
    session_id: "${session_id}"

  auth:
    type: bearer
    token: "${token}"

  body_mode: raw

  form_data: []
  form_urlencoded: {}

  raw:
    raw_type: json
    content:
      level: "${level}"
      inputFile: "${dataset_file}"

  binary:
    source: path
    path: ./data/demo.bin
    content_type: application/octet-stream

  timeout: [3.05, 30]
  verify: true
  allow_redirects: true
```

### 5.3 字段语义

- `method`
  - HTTP 方法。
- `path`
  - 路径模板，可包含 `{id}` 这类占位符。
- `path_params`
  - 用于替换 `path` 中的 `{id}`、`{code}` 等占位符。
- `query`
  - URL 查询参数。
- `headers`
  - 请求头。
- `cookies`
  - Cookie 键值对，不再推荐手写 `headers.Cookie`。
- `auth`
  - 认证信息抽象层。
- `body_mode`
  - 请求体模式。
- `form_data`
  - multipart/form-data 数据。
- `form_urlencoded`
  - application/x-www-form-urlencoded 数据。
- `raw`
  - 原始文本请求体。
- `binary`
  - 整个请求体就是一个二进制文件。
- `timeout`
  - 请求超时。
- `verify`
  - HTTPS 证书校验开关。
- `allow_redirects`
  - 是否跟随重定向。

### 5.4 body_mode 允许值

```text
none
form_data
form_urlencoded
raw
binary
```

### 5.5 各模式语义

- `none`
  - 没有请求体。
- `form_data`
  - `multipart/form-data`
  - 支持文本字段和文件字段混合。
- `form_urlencoded`
  - `application/x-www-form-urlencoded`
- `raw`
  - 使用 `raw.raw_type`
  - 支持 `json / text / html / xml / javascript`
- `binary`
  - 请求体就是一个二进制文件。

### 5.6 互斥规则

1. 一个请求只能有一个 `body_mode`。
2. `body_mode=none` 时，不应出现 `form_data/form_urlencoded/raw/binary`。
3. `body_mode=form_data` 时，不应出现 `form_urlencoded/raw/binary`。
4. `body_mode=form_urlencoded` 时，不应出现 `form_data/raw/binary`。
5. `body_mode=raw` 时，必须带 `raw.raw_type`，且不应出现 `form_data/form_urlencoded/binary`。
6. `body_mode=binary` 时，不应出现 `form_data/form_urlencoded/raw`。

### 5.7 raw 结构

```yaml
request:
  body_mode: raw
  raw:
    raw_type: json
    content:
      modelCode: "${model_code}"
      level: "${level}"
```

`raw_type` 支持：

```text
json
text
xml
html
javascript
```

### 5.8 form_data 结构

`form_data` 统一使用列表表达，每一项都带 `kind`。

```yaml
request:
  body_mode: form_data
  form_data:
    - kind: field
      name: bizType
      value: user

    - kind: file
      name: file
      path: ./data/users.xlsx
```

字段说明：

- `kind=field`
  - 必填：`name`、`value`
- `kind=file`
  - 必填：`name`、`path`
  - `path` 表示本地文件路径
  - 上传文件名默认使用本地文件名
  - content type 属于框架内部的 multipart 组装细节，不作为用户配置项

### 5.9 form_urlencoded 结构

```yaml
request:
  body_mode: form_urlencoded
  form_urlencoded:
    username: "${username}"
    password: "${password}"
```

### 5.10 binary 结构

```yaml
request:
  body_mode: binary
  binary:
    source: path
    path: ./data/demo.bin
    content_type: application/octet-stream
```

### 5.11 auth 结构

#### none

```yaml
auth:
  type: none
```

#### bearer

```yaml
auth:
  type: bearer
  token: "${token}"
```

#### basic

```yaml
auth:
  type: basic
  username: "${username}"
  password: "${password}"
```

#### api_key

```yaml
auth:
  type: api_key
  in: header
  key: X-Token
  value: "${token}"
```

`in` 支持：

```text
header
query
cookie
```

## 6. 产品对象模型

### 6.1 接口模板 ApiTemplate

接口模板回答：这个接口是什么，以及它默认应该如何执行。

接口模板不是纯 OpenAPI 定义，而是 AutoAPI 内部的可执行接口模板，包含接口基础信息、请求模板、默认 hooks、默认 extract 和默认 assertions。

建议文件：

```text
Data/apis.yaml
```

基础完整示例：

```yaml
apis:
  api_start_model:
    meta:
      name: 启动模型
      module: 模型服务
      tags: ["模型", "启动"]
      owner: qa
      priority: P0
      status: active
      description: 启动一个模型任务

    request:
      method: post
      path: /models/start
      headers:
        Content-Type: application/json
      auth:
        type: bearer
        token: "${token}"
      body_mode: raw
      raw:
        raw_type: json
        content:
          modelCode: "${model_code}"
          level: "${level}"

    parameters:
      raw:
        modelCode:
          type: string
          required: true
        level:
          type: string
          required: true

    before_steps: []
    after_steps: []

    extract:
      - source: response_json
        jsonpath: $.data.taskId
        as: modelTaskId

    assertions:
      - source: response_json
        jsonpath: $.success
        op: ==
        expected: true
```

常见请求形态示例：

#### GET + query

```yaml
apis:
  api_query_model_result:
    meta:
      name: 查询模型结果
      module: 模型服务
    request:
      method: get
      path: /models/result
      query:
        taskId: "${taskId}"
        verbose: true
      body_mode: none
```

#### REST path_params + query

```yaml
apis:
  api_get_model_status:
    meta:
      name: 查看模型状态
      module: 模型服务
    request:
      method: get
      path: /models/{modelId}/status
      path_params:
        modelId: "${model_id}"
      query:
        taskId: "${taskId}"
      body_mode: none
```

#### POST + raw(json)

```yaml
apis:
  api_update_model_json:
    meta:
      name: 更新模型数据
      module: 模型服务
    request:
      method: post
      path: /models/update
      headers:
        Content-Type: application/json
      body_mode: raw
      raw:
        raw_type: json
        content:
          level: "${level}"
          inputFile: "${dataset_file}"
```

#### POST + raw(xml)

```yaml
apis:
  api_submit_xml:
    meta:
      name: 提交 XML 配置
      module: 配置中心
    request:
      method: post
      path: /configs/import
      headers:
        Content-Type: application/xml
      body_mode: raw
      raw:
        raw_type: xml
        content: |
          <config>
            <name>${config_name}</name>
          </config>
```

#### POST + form_urlencoded

```yaml
apis:
  api_login_form:
    meta:
      name: 表单登录
      module: 认证中心
    request:
      method: post
      path: /auth/login
      headers:
        Content-Type: application/x-www-form-urlencoded
      body_mode: form_urlencoded
      form_urlencoded:
        username: "${username}"
        password: "${password}"
```

#### POST + form_data(纯字段)

```yaml
apis:
  api_submit_form_data:
    meta:
      name: 提交 multipart 表单
      module: 任务中心
    request:
      method: post
      path: /tasks/create
      body_mode: form_data
      form_data:
        - kind: field
          name: bizType
          value: task
        - kind: field
          name: level
          value: "${level}"
```

#### POST + form_data(文件上传)

```yaml
apis:
  api_upload_file:
    meta:
      name: 上传文件
      module: 文件中心
    request:
      method: post
      path: /files/upload
      body_mode: form_data
      form_data:
        - kind: file
          name: file
          path: ./data/demo.csv
```

#### POST + form_data(文件 + 文本字段)

```yaml
apis:
  api_import_dataset:
    meta:
      name: 导入数据集
      module: 数据中心
    request:
      method: post
      path: /datasets/import
      body_mode: form_data
      form_data:
        - kind: field
          name: importMode
          value: overwrite
        - kind: field
          name: bizType
          value: user
        - kind: file
          name: file
          path: ./data/users.xlsx
```

#### POST + binary

```yaml
apis:
  api_upload_binary:
    meta:
      name: 上传二进制文件
      module: 文件中心
    request:
      method: put
      path: /files/binary/{fileId}
      path_params:
        fileId: "${file_id}"
      body_mode: binary
      binary:
        source: path
        path: ./data/archive.zip
        content_type: application/zip
```

#### headers + cookies + auth

```yaml
apis:
  api_query_profile:
    meta:
      name: 查询个人信息
      module: 用户中心
    request:
      method: get
      path: /profile/me
      headers:
        X-Trace-Id: "${traceId}"
      cookies:
        session_id: "${session_id}"
      auth:
        type: api_key
        in: header
        key: X-Token
        value: "${token}"
      body_mode: none
      timeout: [3.05, 15]
      verify: true
      allow_redirects: false
```

需求：

- `api_id` 全局唯一。
- `api_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `api_id` 推荐格式为 `api_start_task`。
- `meta.name` 是展示名，不要求全局唯一。
- `method + path` 不允许重复。
- 接口模板不包含具体业务编排依赖。
- 接口模板不包含 `host` 或 `host_key`，host 由环境规则解析。
- 接口模板允许默认前置、后置、提取和断言，用于用例复用。
- 接口模板的 `before_steps / after_steps` 是 action-only 的"接口默认伴随动作"，用例继承且不允许覆盖。流程级前置/后置请放在 `Scenario.before_steps / after_steps`。
- 接口定义调试属于后续平台能力，调试时可临时选择环境，但调试结果不等于正式用例。

### 6.2 接口用例 ApiCase

接口用例回答：这个接口在某个测试变体下怎么测。

建议文件：

```text
Data/cases.yaml
```

基础完整示例：

```yaml
cases:
  case_start_model_success:
    use: api_start_model

    meta:
      name: 启动模型成功
      tags: ["冒烟"]
      priority: P0

    request:
      auth:
        type: bearer
        token: "${token}"
      body_mode: raw
      raw:
        raw_type: json
        content:
          modelCode: model_a
          level: "3"

    extract:
      - source: response_json
        jsonpath: $.data.taskId
        as: modelTaskId

    assertions:
      - source: response_json
        jsonpath: $.success
        op: ==
        expected: true
```

常见覆盖形态示例：

#### 覆盖 query

```yaml
cases:
  case_query_result_verbose:
    use: api_query_model_result
    request:
      query:
        taskId: "${taskId}"
        verbose: false
```

#### 覆盖 path_params

```yaml
cases:
  case_get_status_for_model_b:
    use: api_get_model_status
    request:
      path_params:
        modelId: model_b
```

#### 覆盖 headers / cookies / auth

```yaml
cases:
  case_query_profile_with_session:
    use: api_query_profile
    request:
      headers:
        X-Trace-Id: case-trace-id
      cookies:
        session_id: fixed-session-id
      auth:
        type: api_key
        in: header
        key: X-Token
        value: case-token
```

#### 覆盖 raw.content

```yaml
cases:
  case_update_model_level_4:
    use: api_update_model_json
    request:
      body_mode: raw
      raw:
        raw_type: json
        content:
          level: "4"
          inputFile: ./data/b.json
```

#### 覆盖 form_urlencoded

```yaml
cases:
  case_login_admin:
    use: api_login_form
    request:
      body_mode: form_urlencoded
      form_urlencoded:
        username: admin
        password: admin123
```

#### 覆盖 form_data

```yaml
cases:
  case_import_dataset_append:
    use: api_import_dataset
    request:
      body_mode: form_data
      form_data:
        - kind: field
          name: importMode
          value: append
        - kind: file
          name: file
          path: ./data/users_append.xlsx
```

#### 覆盖 binary

```yaml
cases:
  case_upload_zip:
    use: api_upload_binary
    request:
      body_mode: binary
      binary:
        source: path
        path: ./data/archive_v2.zip
        content_type: application/zip
```

#### null 清空示例

```yaml
cases:
  case_without_default_extract:
    use: api_start_model
    extract: null
```

需求：

- `case_id` 全局唯一。
- `case_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `case_id` 推荐格式为 `case_start_task_success`。
- 一个接口模板可以创建多个接口用例。
- 用例默认继承接口模板的请求模板、提取和断言；接口模板的 `before_steps / after_steps` 在合成阶段保留，由 `Composer` 直接用模板版本，用例不参与 hooks 覆盖。
- 用例可以覆盖 `path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`extract`、`assertions`。
- 用例**不允许**覆盖 `before_steps / after_steps`：接口默认伴随动作放在 `ApiTemplate`，流程级前置/后置放在 `Scenario`。validate 在 YAML 中遇到 `cases.<id>.before_steps` 或 `cases.<id>.after_steps` 时报明确错误。详见 `docs/decision_log.md` 2026-04-26 "删除 ApiCase 的 before_steps / after_steps" 决策。
- 用例禁止覆盖 `method` 和 `path`。
- 用例引用接口模板使用 `use:` 字段（例如 `cases.<id>.use: api_xxx`），与 `scenarios.steps[].use` 命名风格统一。validate 在 YAML 中遇到旧 `cases.<id>.api: ...` 时报明确错误并提示改用 `use:`。详见 `docs/decision_log.md` 2026-04-26 "YAML 引用字段统一为 use" 决策。
- 用例可以单独执行。
- 用例支持数据驱动，具体数据驱动能力放 P1。

### 6.3 场景 Scenario

场景回答：业务流程怎么串。

建议目录：

```text
Data/Scenarios/*.yaml
```

基础完整示例：

```yaml
scenario_id: scn_hanoi_main_flow
env: test

meta:
  name: 汉诺塔完整流程
  module: 汉诺塔
  tags: ["回归", "主流程"]
  priority: P0

steps:
  - id: 启动业务
    use: case_start_model_success

  - id: 上传数据
    use: case_update_model_level_4
    override:
      query:
        taskId: "${modelTaskId}"

  - id: 停止任务
    use: case_stop_task_success
```

常见 override 示例：

#### override.query

```yaml
steps:
  - id: 查询结果
    use: case_query_result_verbose
    override:
      query:
        taskId: "${modelTaskId}"
        verbose: true
```

#### override.path_params

```yaml
steps:
  - id: 查询指定模型状态
    use: case_get_status_for_model_b
    override:
      path_params:
        modelId: "${model_id}"
```

#### override.raw.content

```yaml
steps:
  - id: 更新模型数据
    use: case_update_model_level_4
    override:
      raw:
        raw_type: json
        content:
          level: "${level}"
          inputFile: "${dataset_file}"
```

#### override.form_data

```yaml
steps:
  - id: 上传数据集
    use: case_import_dataset_append
    override:
      form_data:
        - kind: field
          name: importMode
          value: overwrite
        - kind: file
          name: file
          path: "${dataset_file}"
```

#### override.assertions

```yaml
steps:
  - id: 查看结果
    use: case_query_result_verbose
    override:
      assertions:
        - source: response_json
          jsonpath: $.data.result
          op: ==
          expected: "${expected_result}"
```

#### step 内联 action（清理 SQL / 脚本 / wait）

每个 step 在 `use: case_xxx` 与 `action: {kind: ...}` 之间二选一：

```yaml
steps:
  - id: 创建任务
    use: case_create_task_success     # 业务接口：填 use

  - id: 等待业务落库
    action:                           # 辅助动作：填 action
      kind: wait
      seconds: 2

  - id: 清理脏数据
    action:                           # 辅助动作 + always_run
      kind: sql
      datasource: main_db
      sql: "DELETE FROM task WHERE name='demo'"
    always_run: true
    continue_on_error: true
```

语义：

- 每个 step 同一时间只能填 `use` 或 `action` 之一（xor 互斥）；两者同时填或都不填都视为非法 schema。
- `use`-style step 引用 `case_xxx` 资产，按 PRD §13 的继承 / override 规则合成请求。
- `action`-style step 直接内联 `wait / sql / script`，与 hooks 中的 `action` 字段同语义、同执行入口；`extract` 子字段把结果写回 `RuntimeContext`。
- `override` 仅对 `use`-style step 生效；`action`-style step 不接受 `override`。
- `always_run / continue_on_error` 两个字段对两类 step 都生效（详见下一节）。

#### always_run / continue_on_error

`Scenario.steps[]` 支持两个执行策略字段：

```yaml
steps:
  - id: 创建任务
    use: case_create_task_success
    continue_on_error: true   # 失败也继续走后面的步骤

  - id: 业务校验
    use: case_query_task_detail

  - id: 删除测试任务（接口清理）
    use: case_delete_task
    always_run: true          # 不论前面是否失败，都尝试执行

  - id: 清理脏数据（SQL 清理）
    action:
      kind: sql
      datasource: main_db
      sql: "DELETE FROM task WHERE name='demo'"
    always_run: true
    continue_on_error: true
```

语义：

- `continue_on_error: true`：本 step 失败后不立即停止 scenario，继续执行后续 step。本 step 自身的状态仍记为 `failed/error`，scenario 整体状态由所有 step 聚合得出。
- `always_run: true`：无论前面 step 是否失败，本 step 都会执行。多个 `always_run` step 按声明顺序执行；其自身失败仍计入结果，但不阻塞其它 `always_run` step。
- 两者默认值都是 `false`，默认行为仍然是"失败即停止"。
- 这两个字段是表达**所有清理动作**的标准方式——无论是接口清理（DELETE 接口）、SQL 清理、还是清理脚本，都通过"放在 `Scenario.steps` 末尾 + `always_run: true`"统一表达。业务流的全部步骤仍然在 `steps` 中显式可见。
- 这两个字段对 `before_steps / after_steps` 不生效；hooks 的执行规则由各自语义保证（before 在主体前执行，after 仅主体成功后执行）。`finally_steps` 字段在 v0.2 中已废弃，原"无条件执行"语义统一由本节字段承载。

场景级数据驱动示例：

```yaml
scenario_id: scn_model_flow
env: test

meta:
  name: 模型完整流程
  module: 模型服务
  tags: ["回归", "模型"]
  priority: P1

datasets:
  - name: model_a_level_3
    variables:
      model_id: model_a
      model_code: model_a
      dataset_file: ./data/a.json
      level: "3"
      expected_result: success

  - name: model_b_level_4
    variables:
      model_id: model_b
      model_code: model_b
      dataset_file: ./data/b.json
      level: "4"
      expected_result: success

steps:
  - id: 启动模型
    use: case_start_model_success
    override:
      raw:
        raw_type: json
        content:
          modelCode: "${model_code}"
          level: "${level}"

  - id: 查看模型启动状态
    use: case_get_status_for_model_b
    override:
      path_params:
        modelId: "${model_id}"
      query:
        taskId: "${modelTaskId}"

  - id: 更新模型数据
    use: case_update_model_level_4
    override:
      raw:
        raw_type: json
        content:
          level: "${level}"
          inputFile: "${dataset_file}"

  - id: 查看结果
    use: case_query_result_verbose
    override:
      query:
        taskId: "${modelTaskId}"
      assertions:
        - source: response_json
          jsonpath: $.data.result
          op: ==
          expected: "${expected_result}"
```

场景级数据驱动语义：

- 每个 dataset 对应一轮完整场景执行。
- dataset variables 是本轮初始输入（叠加在 env.variables 之上，详见下一节"上下文初始化与变量合并规则"）。
- 前面步骤提取的变量只在本轮内有效。
- 每轮使用独立上下文（独立 `RuntimeContext`，env / dataset 在每轮开始重新拷贝，前一轮的运行时变量不会污染下一轮）。
- 后续报告和历史需要记录 `dataset_name / dataset_index`。

#### 上下文初始化与变量合并规则

每轮场景执行的 `RuntimeContext` 初始化遵循固定的三层叠加顺序：

1. **基底**：把当前 `Environment.variables` 浅拷贝进入本轮上下文。
2. **dataset 叠加**：如果场景有 `datasets`，把当前轮 `dataset.variables` 叠加进上下文（同名 key 覆盖 env.variables）。如果没有 `datasets`，相当于一轮空 dataset，跳过本步。
3. **运行时叠加**：每个 step / hook / action 的 `extract` 写入直接写到本轮上下文，同名 key 覆盖前两层。

示例：

```yaml
# Environment（config.yaml）
envs:
  test:
    variables:
      token: env-token
      baseUrl: http://127.0.0.1:1806
      level: "1"

# Scenario
datasets:
  - name: model_a_level_3
    variables:
      level: "3"          # 覆盖 env.level
      model_code: model_a # 新增

steps:
  - id: 启动模型
    use: case_start_model_success
    # 此 step 内 ${token} = env-token, ${baseUrl} = http://...,
    # ${level} = "3"（dataset 覆盖）, ${model_code} = model_a（dataset 新增）

  - id: 查询结果
    use: case_query_result_verbose
    override:
      query:
        taskId: "${modelTaskId}"
    # 上一步 extract 的 modelTaskId 作为运行时叠加层
```

规则说明：

- 三层从下到上：env.variables（最底）→ dataset.variables（中间）→ 运行时 extract（最上）。同名 key 由上层覆盖下层。
- 与 §8 "字段级整体覆盖"一致：变量在 key 粒度上做 dict 合并；如果某个变量值本身是 list / 复杂结构，按"key 整体覆盖"处理，不做深度合并。
- env.variables 和 dataset.variables 都是只读快照视角下的初始基底；运行时 `extract` 的写入只发生在当前轮上下文内，不会回写到 env 或 dataset。
- 没有 dataset 的场景与"一轮空 dataset"等价：上下文 = env.variables 拷贝 + 运行时 extract。
- 多轮 dataset 之间互不污染：第二轮开始时上下文重新从 env.variables 拷贝并叠加第二轮 dataset，看不到第一轮 extract 的变量。

详见 `docs/decision_log.md` 2026-04-26 "场景执行的上下文初始化采用叠加语义" 决策。

平台化后的表现：

- 场景详情页建议拆为：
  - 步骤编排
  - 变量引用
  - 数据集
  - 调试执行
  - 历史结果
- 数据集是场景资产，不是临时执行参数。
- 平台结果页按 dataset 分轮展示。

需求：

- `scenario_id` 全局唯一。
- `scenario_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `scenario_id` 推荐格式为 `scn_hanoi_main_flow`。
- 场景步骤必须显式排列。
- P0 优先支持场景步骤引用 case。
- 场景后续可以直接引用 api，但不作为 P0 必做。
- 场景步骤允许临时 override，但不回写被引用 case。
- 场景选择默认执行环境。
- 场景级前置、后置、断言放 P1（仅 `before_steps / after_steps`，不再保留 `finally_steps`；"无条件执行"语义改由 `steps[].always_run` 表达）。
- 场景级数据驱动放 P1。
- `always_run / continue_on_error` 是 step 级执行策略字段，P1 必须实现。
- 废弃接口级 `depends_on` 作为业务编排方式。

### 6.4 测试计划 TestPlan

测试计划回答：这次统一执行哪些资产。

建议文件：

```text
Data/plans.yaml
```

只包含场景的示例：

```yaml
plans:
  plan_hanoi_regression:
    meta:
      name: 汉诺塔回归计划
      owner: qa
      tags: ["回归"]

    scenarios:
      - scn_hanoi_main_flow

    cases: []
```

同时包含场景和独立 case 的示例：

```yaml
plans:
  plan_model_smoke:
    meta:
      name: 模型冒烟计划
      owner: qa
      tags: ["冒烟"]

    scenarios:
      - scn_model_flow

    cases:
      - case_query_profile_with_session
```

需求：

- `plan_id` 全局唯一。
- `plan_id` 现阶段由用户手写，使用稳定、可读、语义化 ID。
- `plan_id` 推荐格式为 `plan_hanoi_regression`。
- 测试计划可以包含多个场景。
- 测试计划可以包含单接口用例。
- 测试计划不指定运行环境。
- 测试计划不持有请求数据。
- 测试计划不持有 datasets。
- 测试计划只负责任务统筹。
- 后续历史报告按 plan 聚合。

### 6.5 环境 Environment

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
      token: demo-token
      session_id: demo-session

    hosts:
      model_service: http://127.0.0.1:1806
      data_service: http://127.0.0.1:1808

    host_rules:
      - host: data_service
        priority: 300
        apis:
          - api_import_dataset
          - api_upload_binary

      - host: data_service
        priority: 200
        modules:
          - 数据中心

      - host: data_service
        priority: 100
        path_prefixes:
          - /datasets/

      - host: model_service
        priority: 0
        default: true

request_defaults:
  timeout: [3.05, 30]
  verify: true
  allow_redirects: true

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
- `ApiTemplate`、`ApiCase`、`ScenarioStep` 不出现 `host` 或 `host_key`。
- `sensitive_keys` 作为后续敏感字段脱敏能力的配置基础，正式脱敏能力放 P2。
- 环境只负责变量、默认请求参数、host 解析和后续脱敏配置，不承载接口编排。
- 当前不做环境级前置、后置、鉴权模板；登录、准备数据、清理数据这类接口调用必须放在 `Scenario.steps` 中显式编排。

## 7. ID 与引用规则

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
    use: api_start_task

scenario_id: scn_hanoi_main_flow
steps:
  - id: 启动业务
    use: case_start_task_success
```

不同字段根据语义限制引用目标：

- `cases.<case_id>.use` 只能引用 `api_` 开头的接口模板 ID。
- `scenarios.steps[].use` 在 P0 阶段只能引用 `case_` 开头的接口用例 ID。
- `plans.<plan_id>.scenarios[]` 只能引用 `scn_` 开头的场景 ID。
- `plans.<plan_id>.cases[]` 只能引用 `case_` 开头的接口用例 ID。

引用字段的命名风格统一为 `use:` 动词形式：同一个语义动作（"我引用某个上层资产 ID"）只用一种字段名，"能指向什么前缀"由上下文区分。旧字段 `cases.<id>.api` 在 v0.2 schema 切换时下线，validate 遇到时报错并提示改用 `use:`。

P2 阶段可提供 CLI 自动生成稳定 ID、检查 ID 命名规范、重命名 ID 并自动更新引用。

## 8. 继承与覆盖规则

AutoAPI 采用字段级整体覆盖，不做深度合并。

规则：

1. 当前层未声明某字段时，继承上层字段。
2. 当前层声明某字段且值非 null 时，该字段整体覆盖上层字段。
3. 当前层声明某字段为 null 时，表示显式清空该字段。
4. 字段内部不递归合并。
5. override 仅作用于当前执行上下文，不回写被引用资产。

以请求模型为例，以下字段都按字段级整体覆盖：

```text
path_params
query
headers
cookies
auth
body_mode
form_data
form_urlencoded
raw
binary
timeout
verify
allow_redirects
```

示例：

```yaml
# ApiTemplate
request:
  raw:
    raw_type: json
    content:
      a: 1
      b: 2

# ApiCase
request:
  raw:
    raw_type: json
    content:
      a: 100
```

最终结果：

```yaml
request:
  raw:
    raw_type: json
    content:
      a: 100
```

说明：`request.raw` 被整体覆盖，不保留上层的 `b: 2`。

约束：

- `method` 和 `path` 仍禁止由 `ApiCase` 或 `ScenarioStep override` 改成另一个接口语义。
- `path` 中允许使用 `path_params` 填不同值，但 `path` 模板本身仍来自 `ApiTemplate`。

## 9. host 解析规则

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

## 10. 字段校验策略

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

严格字段校验放 P2，在核心执行链和请求模型稳定后再补齐。

## 11. 执行能力需求

### P0

- 支持基础 validate，不发请求。
- 支持执行单个 case。
- 支持执行单个 scenario。
- 支持执行 test plan。
- 支持 CLI 选择环境。
- 支持结构化执行结果输出。
- 支持失败时输出请求、响应、上下文、异常原因。
- 支持关键配置错误时给出明确定位。
- 执行完成后自动生成 Allure HTML 报告。
- 生成 Allure 失败时只输出 warning，不改变真实执行结果。

CLI 目标：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_model_flow --env test
python run.py --plan plan_model_smoke --env prod
```

### P1

- 支持场景级数据驱动。
- 支持场景级 `before_steps`、`after_steps`、`assertions`（`finally_steps` 已在 v0.2 设计中废弃，对应"无条件执行"语义统一由 `steps[].always_run` 表达，详见 §6.3）。
- 支持 action-only hooks：作用于 `ApiTemplate`（接口默认伴随动作）和 `Scenario`（场景前置后置）两层，`ApiCase` 不再持有 hooks 字段；第一批 `wait` 已落地；`script` 在 P1 内升级为真实执行能力（默认 `expect_returncode=0`，详见 §12）；`sql` 真实执行延后到 P2，目标方言锁定为 PostgreSQL，第一版仅保留结构占位 + `NotImplementedError` 错误明确，详见 `docs/decision_log.md` 2026-04-26（修订）。
- 支持 `Scenario.steps[]` 内联 `action`：每个 step 在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一；与 hooks 的 action 共享执行入口。
- 支持 step 级 `always_run`：无论前面 step 是否失败都执行。
- 支持 step 级 `continue_on_error`：当前 step 失败后不阻塞后续 step。
- 支持公共断言和公共提取。
- 支持企业常用断言 / 提取 source 和常用断言 op。
- 执行内核切换到 pytest，报告改用 `allure-pytest`。CLI 用户体验保持不变；详见 `docs/decision_log.md` 2026-04-26 决策与 `plans/20_pytest_kernel_migration.md`。

### P2

- 支持 step 重试（基于 `pytest-rerunfailures`）。
- 支持 OpenAPI 导入。
- 支持执行历史 SQLite 落库。
- 支持敏感变量脱敏。
- 支持资产索引与影响分析。
- 支持 CLI 自动生成稳定 ID。
- 支持严格字段校验。
- 支持按 tag 执行（基于 `pytest.mark + -m`）。
- 支持按 priority 执行（基于 `pytest_collection_modifyitems`）。
- 支持并行执行（基于 `pytest-xdist`）。
- 支持定时任务。
- 支持通知。
- 支持 Web UI。

## 12. 编排策略需求

### P0

- 废弃接口级 `depends_on`。
- 不保留旧 `depends_on` 兼容。
- 场景步骤必须显式。
- 废弃旧 `cleanup` 字段。
- 业务清理通过普通场景 step 显式编排。

### P1

使用更统一的 action-only hooks 模型替代旧 cleanup。hooks 只表达非业务接口动作，不允许通过 `use` 引用 case 或 api。

```yaml
before_steps:
  - id: 等待服务稳定
    action:
      kind: wait
      seconds: 2

after_steps:
  - id: 查询任务状态
    action:
      kind: sql
      datasource: main_db
      sql: select id from task where name='demo'
      extract:
        - source: result
          path: $.rows[0].id
          as: taskId
```

hooks 只剩 `before_steps / after_steps` 两件套；作用域只覆盖两个层级——`ApiTemplate`（接口默认伴随动作）和 `Scenario`（场景前置后置）。`ApiCase` 不再持有 `before_steps / after_steps` 字段；用例只继承 `ApiTemplate` 的 hooks，不允许覆盖。原 `finally_steps` 字段在 v0.2 中删除（之前作用域覆盖 `ApiTemplate / ApiCase / Scenario` 三个层级），原"无条件执行"语义改由 `Scenario.steps[].always_run` 承载，详见下文"清理动作的统一表达"。

语义：

- `before_steps`：主流程前执行。
  - 作用于 `ApiTemplate` 时，每次该接口被调用前都执行。
  - 作用于 `Scenario` 时，整个场景的所有 step 开始前执行一次。
- `after_steps`：主流程成功后执行。
  - 作用于 `ApiTemplate` 时，该接口调用成功后执行。
  - 作用于 `Scenario` 时，场景所有 step 成功后执行；若场景中途失败，after_steps 不执行（"无条件清理"请走 `steps[]` + `always_run: true`）。
- `action.kind=wait`：等待指定时间，P1 第一批已实现。
- `action.kind=sql`：执行 SQL，**真实执行延后到 P2**，目标方言锁定为 PostgreSQL。第一版仅保留结构占位（YAML schema 合法、validate 通过），命中后由 `Engine/action_runner.py` 抛 `NotImplementedError`；`datasource` 引用 `config.yaml` 顶层 `datasources` 在 P2 落地时一并引入。详见 `docs/decision_log.md` 2026-04-26（修订）"sql action 真实执行延后到 P2"。
- `action.kind=script`：执行本地命令或 Python 入口，P1 升级为真实执行能力。第一版只支持非沙箱本地执行；进程 `stdout / stderr / returncode` 通过 `extract` 字段写回 `RuntimeContext`；默认 `expect_returncode=0`，进程退出码不等于期望值时 step 自动 `failed`，可显式声明 `expect_returncode: any` 跳过校验。详见 `docs/decision_log.md` 2026-04-26 "script action 默认 expect_returncode=0"。
- action 内部如需把结果写回上下文，统一使用 `extract` 字段，保持提取语义命名一致。
- 业务接口调用只允许出现在 `Scenario.steps`；不能把一组接口藏进 template/case/scenario hooks 里。
- `setup` / `teardown` 只作为未来平台化生命周期术语保留，不进入当前 YAML 字段；当前字段统一使用 `before_steps`、`after_steps`。

清理动作的统一表达：

- 所有清理动作——无论是 HTTP 接口清理（如 `DELETE /tasks/{id}`）、SQL 清理、还是清理脚本——一律通过 `Scenario.steps[]` 末尾 + `always_run: true` 表达。
- `Scenario.steps[]` 中每个 step 在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一，详见 §6.3。
- 不再存在"接口清理走 steps[]、SQL/脚本清理走 finally_steps"的双轨写法。

```yaml
steps:
  - id: 创建任务
    use: case_create_task_success

  - id: 业务校验
    use: case_query_task_detail

  - id: 删除测试任务（接口清理）
    use: case_delete_task
    always_run: true

  - id: 清理脏数据（SQL 清理）
    action:
      kind: sql
      datasource: main_db
      sql: "DELETE FROM task WHERE name='demo'"
    always_run: true
    continue_on_error: true
```

- 这样做的目的是：业务流的所有步骤——业务接口与清理动作——都按声明顺序在 `Scenario.steps` 中显式可见，不再回到隐藏式 `cleanup` 或双机制并存的老路。
- 取舍：`AutoAPI --case case_xxx` 单跑 case 时不再有"无条件清理"入口（`ApiCase.finally_steps` 同步删除）。如果一个 case 需要保证清理副作用，把它包成 scenario 并把清理动作作为 `steps[]` 末尾 + `always_run: true`。详见 `docs/decision_log.md` 2026-04-26 "废弃 finally_steps" 决策。
- 同批 schema 收敛删除 `ApiCase.before_steps / after_steps`：用例不再持有 hooks，hooks 只在 `ApiTemplate`（接口默认）和 `Scenario`（场景前置后置）两层。详见 `docs/decision_log.md` 2026-04-26 "删除 ApiCase 的 before_steps / after_steps" 决策。
- 同批 schema 收敛把 `cases.<id>.api` 字段重命名为 `cases.<id>.use`，与 `scenarios.steps[].use` 统一为同一个引用动词。validate 在 YAML 中遇到旧 `api:` 字段时报明确错误并提示改用 `use:`。详见 `docs/decision_log.md` 2026-04-26 "YAML 引用字段统一为 use" 决策。

## 13. 复制与引用策略

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

## 13.1 断言与提取 Source

第一版企业常用断言 source：

- `response_status`：响应状态码，配合 `jsonpath: "$"` 读取自身。
- `response_headers`：响应头字典。
- `response_json`：响应 JSON。
- `response_text`：响应文本，配合 `jsonpath: "$"` 读取全文。
- `context`：当前运行上下文。
- `response_time_ms`：响应耗时，单位毫秒，配合 `jsonpath: "$"` 读取自身。

第一版企业常用提取 source：

- `response_json`
- `response_headers`
- `response_text`
- `context`

断言 op：

- 比较：`==`、`!=`、`>`、`>=`、`<`、`<=`
- 包含：`contains`、`not_contains`
- 字符串：`starts_with`、`ends_with`、`regex`
- 空值：`empty`、`not_empty`
- 长度：`length_gt`、`length_gte`、`length_lt`、`length_lte`、`length_eq`
- 存在性：`exists`

示例：

```yaml
assertions:
  - source: response_status
    jsonpath: "$"
    op: ==
    expected: 200

  - source: response_headers
    jsonpath: "$['Content-Type']"
    op: contains
    expected: application/json

  - source: response_time_ms
    jsonpath: "$"
    op: <
    expected: 1000
```

## 14. 报告与历史需求

### P0

- 保留 Allure。
- 每次执行生成 `run_id`。
- 执行完成后自动生成：
  - `Reports/allure-results/<run_id>/`
  - `Reports/allure-report/<run_id>/`
- CLI 输出报告路径，不自动打开浏览器。
- Allure CLI 缺失或 HTML 生成失败时，只 warning。
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

- 暂不新增报告能力，重点补齐场景编排增强。

### P2

- SQLite 存储。
- 简单趋势统计命令。
- Web 趋势看板。
- 后续历史补充 `dataset_name / dataset_index` 维度。

## 15. OpenAPI 导入需求

### P2

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

## 16. 团队协作与资产管理需求

### P0

- 暂不做 Web 协作。
- 通过 Git 管理 YAML 资产。
- 通过 `meta` 字段补齐 `owner`、`tags`、`module`、`priority`、`status`。

### P2

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

平台化能力：

- Web UI。
- 用户权限。
- 在线编辑。
- 审批流。
- 配置项启用/禁用开关（草稿持久化）。

平台化"配置项启用/禁用开关"展开说明：

- 适用范围：场景 step 的 `override.extract` / `override.assertions`，以及 case 默认的 `extract / assertions`、`before_steps / after_steps`。后续如有诉求再决策是否扩展到单条 assertion / 单条 extract 的"条目级开关"。
- UX 目标：UI 上点击"关闭"开关后，用户已经写过的内容仍然保留为草稿；下次重新打开开关时内容仍在，不需要重写。这与 MeterSphere 等 DB-backed 平台的体验一致。
- 当前 YAML-first 阶段（P0/P1/v0.2）等价表达：在对应字段写 `null` 即可关闭这一组（PRD §8 第 3 条）；但 `null` 表示"显式清空"，关闭后不保留草稿。因此 v0.2 之前用户在 YAML 中只能选"清空 vs 保留并启用"二选一。
- P2 启动平台化时再决策落地路线：
  - 路线 A：UI 关闭等价于 YAML 写 `null`，schema 不动，UX 较弱（关闭再开启会丢内容）。
  - 路线 B：升级 schema，把上述字段允许 `{enabled: bool, items: [...]}` dict 形态，与原 list 形态长期共存；执行内核只看 `enabled` 决定是否生效，关闭时 `items` 保留。这条路线对老 YAML 零迁移；对 PRD §8"字段级整体覆盖"只补一句兼容说明（list / dict 两种形态都按整体覆盖），不破坏现有规则。
- 启用任何一条整组开关字段时，**P2 必须一次性圈定哪些字段支持开关、哪些不支持**，避免规则被零散扩张到所有字段。当前建议范围限定在上述 `extract / assertions / before_steps / after_steps` 四个字段，单条级开关不在 P2 范围。
- 详见 2026-04-26 用户讨论记录（与"override null 清空"的等价边界讨论）；本条目仅作为平台化能力登记，不进入 P0/P1/v0.2 实现范围。

## 17. 目录结构

新结构：

```text
Data/
  config.yaml
  apis.yaml
  cases.yaml
  Scenarios/
    model_flow.yaml
  plans.yaml
Reports/
  history/
    runs.jsonl
    results.jsonl
  allure-results/
  allure-report/
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

## 18. 优先级总表

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
16. 执行完成后自动生成 Allure HTML 报告。
17. 结构化结果 JSONL。
18. 旧结构不兼容。

### P1：第二批增强

1. 场景级数据驱动。
2. 场景级 `before_steps`、`after_steps`、`assertions`（`finally_steps` 已废弃，详见 §6.3 / §12 与 `docs/decision_log.md` 2026-04-26 决策）。
3. action-only hooks：作用域收敛为 `ApiTemplate` 与 `Scenario` 两层（`ApiCase` 不再持有 hooks）；`wait` 已落地；`script` 在 P1 升级为真实执行能力（默认 `expect_returncode=0`）；`sql` 真实执行延后到 P2，目标方言 PostgreSQL，第一版仅保留结构占位。
4. `Scenario.steps[]` 内联 `action`：每个 step 在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一。
5. 公共断言和公共提取。
6. 企业常用断言 / 提取 source 与常用断言 op。
7. 执行内核切换到 pytest，报告改用 `allure-pytest`。
8. step 级 `always_run` / `continue_on_error`（统一承载所有清理动作的"无条件执行"语义）。
9. v0.2 schema 收敛：删除 `ApiCase.before_steps / after_steps`；`cases.<id>.api` 字段重命名为 `cases.<id>.use`；`Scenario.datasets` 上下文采用"env.variables → dataset.variables → 运行时 extract"三层叠加初始化（详见 §6.3 与 `docs/decision_log.md` 2026-04-26 三条配套决策）。

### P2：第三批产品化与平台化

1. step 重试（基于 `pytest-rerunfailures`）。
2. 并行执行（基于 `pytest-xdist`）。
3. OpenAPI 导入。
4. 历史结果 SQLite。
5. 敏感变量脱敏。
6. 资产索引与影响分析。
7. CLI 自动生成稳定 ID。
8. 严格字段校验。
9. 按 tag 执行（基于 `pytest.mark + -m`）。
10. 按 priority 执行（基于 `pytest_collection_modifyitems`）。
11. 定时任务。
12. 通知集成。
13. Web UI。
14. 团队协作。
15. 权限管理。
16. 在线调试页面。
17. 测试趋势看板。
18. 公共脚本市场。
19. Mock。
20. 数据工厂。
21. 审批流。
22. 配置项启用/禁用开关（草稿持久化），适用于 `extract / assertions / before_steps / after_steps`，落地路线在 P2 启动平台化时决策，详见 §16 P2。
23. Web UI 自动化。
24. APP 自动化。
25. AI 辅助用例生成、维护和失败诊断。
