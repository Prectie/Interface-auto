# AutoAPI v0.1 里程碑说明

## 版本定位

`AutoAPI v0.1` 是当前框架的第一个可用产品内核里程碑。

它的定位是：

```text
YAML-first 接口自动化执行内核
```

当前版本已经完成从旧脚本式结构到分层执行框架的核心转型：

- 资产分层已经建立。
- 显式场景编排已经建立。
- 请求模型已经覆盖常见接口形态。
- CLI 执行链路已经打通。
- Allure 和 JSONL history 已经接入。
- P1 的核心复用和编排增强已经完成第一版。

它还不是企业级接口自动化平台，也不是 Web UI 产品。

## 当前已具备能力

### 1. YAML-first 测试资产模型

当前主结构：

```text
config.yaml
apis.yaml
cases.yaml
Scenarios/*.yaml
plans.yaml
```

核心对象：

- `ApiTemplate`：接口模板。
- `ApiCase`：接口用例。
- `Scenario`：业务场景。
- `TestPlan`：测试计划。
- `EnvironmentConfig`：环境、变量、host 规则和共享规则。

旧结构已经退出主路径：

- `single.yaml`
- `Flows/*.yaml`
- `depends_on`
- `cleanup`

### 2. 分层执行模型

当前代码主链路：

```text
Repository
-> Validator
-> Composer
-> RequestResolver
-> Executor
-> Extractor
-> AssertionEngine
-> HistoryWriter / AllureRuntimeReporter
```

关键规则：

- `ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan` 分层。
- `Scenario.steps` 是业务接口编排的唯一入口。
- hooks 不允许引用 case 或 api，只允许 action。
- `method/path` 只能来自 `ApiTemplate`。
- override 使用字段级整体覆盖，不做 deep merge。
- 未填写表示继承。
- `null` 表示清空。

### 3. CLI 能力

当前支持：

```bash
python run.py validate --data examples/minimal/Data
python run.py --case case_start_task_success --env test --data examples/minimal/Data
python run.py --scenario scn_hanoi_main_flow --env test --data examples/minimal/Data
python run.py --plan plan_hanoi_regression --env test --data examples/minimal/Data
```

CLI 已支持：

- `validate`
- `--case`
- `--scenario`
- `--plan`
- `--env`
- `--data`

执行失败时，CLI 会输出：

- 请求快照。
- 响应快照。
- 上下文快照。
- 异常原因。
- 错误提示。

### 4. 请求模型能力

当前 `RequestResolver` 已支持：

- `path`
- `path_params`
- `query`
- `headers`
- `cookies`
- `auth`
- `body_mode`
- `raw`
- `form_urlencoded`
- `form_data`
- `binary`

当前 body mode：

- `none`
- `raw`
- `form_urlencoded`
- `form_data`
- `binary`

当前 raw subtype：

- `json`
- `text`
- `xml`
- `html`
- `javascript`

当前 auth type：

- `none`
- `bearer`
- `basic`
- `api_key`

当前文件上传模型：

```yaml
form_data:
  - kind: file
    name: file
    path: ./files/demo.txt
```

### 5. 环境与 host 解析

当前 host 只通过环境配置中的 `host_rules` 解析。

接口模板、用例、场景步骤中不再写：

- `host`
- `host_key`

当前 `HostResolver` 支持：

- `apis`
- `path_prefixes`
- `default`
- `priority`

### 6. 场景编排能力

当前 `Scenario` 支持：

- 显式 `steps`
- 引用 case ID
- step 级 `override`
- 场景级 `datasets`
- 场景级 `before_steps`
- 场景级 `after_steps`
- 场景级 `assertions`
- 场景级 `finally_steps`

执行顺序：

```text
scenario.before_steps
-> scenario.steps
-> scenario.after_steps
-> scenario.assertions
-> scenario.finally_steps
```

其中：

- `finally_steps` 总是执行。
- `after_steps` 只在主流程通过后执行。
- 当前默认失败即停止。

### 7. action-only hooks

当前 hooks 只允许：

```yaml
action:
  kind: wait
```

已实现：

- `wait`

预留但未实现：

- `sql`
- `script`

接口调用类动作不再放入 hooks。登录、准备数据、清理数据都应放在 `Scenario.steps` 中显式编排。

### 8. 公共断言与公共提取

当前 `config.yaml` 支持：

- `shared_extracts`
- `shared_assertions`

当前资产支持：

- `extract_ref`
- `assertions_ref`

展开规则：

```text
先展开共享规则
再追加本地规则
```

### 9. 断言与提取能力

当前断言 source：

- `response_status`
- `response_headers`
- `response_json`
- `response_text`
- `context`
- `response_time_ms`

当前提取 source：

- `response_json`
- `response_headers`
- `response_text`
- `context`

当前断言 op：

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

### 10. 报告与历史

当前支持：

- 写入 `Reports/history/runs.jsonl`
- 写入 `Reports/history/results.jsonl`
- 写入 `Reports/allure-results/<run_id>/`
- 尝试生成 `Reports/allure-report/<run_id>/`

Allure HTML 生成失败时：

- 输出 warning。
- 不改变真实执行状态。

### 11. 代码学习笔记

当前已沉淀代码理解笔记：

- `note/autoapi_code_thinking.md`
- `note/01_composer_code_thinking.md`
- `note/02_executor_code_thinking.md`
- `note/03_request_resolver_code_thinking.md`

这些笔记用于解释框架代码思维、模块职责和后续扩展边界。

## 推荐验证命令

当前推荐最小验证：

```bash
python run.py validate --data examples/minimal/Data
python run.py validate --data examples/reading_house/Data
python -m pytest -q
```

读书屋示例执行验证：

```bash
python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --plan plan_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_auth_flow --env test --data examples/reading_house/Data
```

如果目标服务不可访问，请优先使用：

```bash
python run.py validate --data examples/reading_house/Data
python -m pytest -q
```

## 当前已知限制

### 1. 严格字段校验尚未实现

当前 Validator 只做基础关系校验。

尚未严格校验：

- 字段白名单。
- 字段类型。
- 枚举值。
- request schema。
- hooks schema。
- assertions / extract schema。

该能力已放入 P2。

### 2. step retry / continue_on_error 尚未实现

当前执行策略是：

```text
失败即停止
```

尚未支持：

- step 重试。
- step 失败后继续。
- 按场景或计划配置失败策略。

### 3. 敏感信息脱敏仍是最小版本

当前只在请求快照和 CLI 输出中做最小隐藏。

尚未形成完整脱敏体系：

- history 脱敏策略。
- Allure 附件脱敏策略。
- 用户可配置敏感字段策略。
- 响应内容脱敏。

### 4. 资产管理能力尚未产品化

当前还没有：

- 资产索引。
- 引用关系分析。
- 未引用接口扫描。
- 变更影响分析。
- 重复资产报告。

### 5. OpenAPI 导入尚未实现

当前不能直接从 OpenAPI 3.x 生成 `apis.yaml`。

该能力已放入 P2。

### 6. 历史趋势能力尚未实现

当前已有 JSONL history。

尚未实现：

- SQLite 落库。
- 趋势统计命令。
- Web 趋势看板。

### 7. 暂无 Web UI

当前版本仍是：

```text
CLI + YAML + Git 管理
```

Web UI、团队协作、权限、在线编辑都属于后续平台化阶段。

## v0.1 不包含的能力

以下能力不属于 v0.1：

- OpenAPI 导入。
- SQLite 历史。
- Web UI。
- 资产索引与影响分析。
- 严格字段校验。
- CLI 自动生成稳定 ID。
- step retry（基于 `pytest-rerunfailures`）。
- 并行执行（基于 `pytest-xdist`）。
- tag / priority 执行。
- 定时任务。
- 通知。
- Mock。
- 数据工厂。
- 审批流。

## 下一阶段：v0.2 内核切换

v0.1 已经验证了 YAML-first 资产模型与显式场景编排的可行性。但当前 v0.1 的执行内核与 Allure 报告全部由 `Engine/executor.py` 与 `Utils/allure_runtime.py` 自研，绕过了 pytest 与 `allure-pytest` 的标准生态。继续以这种方式扩展将让后续 retry / parallel / tag / priority / 严格字段校验 / WebUI / APP 等多端能力都需要自研一遍。

因此 v0.2 的目标是**执行内核切换**，而不是继续在 v0.1 自研内核上叠加新能力。

v0.2 预定推进的能力（详见 `docs/decision_log.md` 2026-04-26 决策与 `plans/20_pytest_kernel_migration.md`）：

1. `执行内核切换到 pytest`
   - 自研 `Executor` 调度逻辑改造为纯函数 `execute_one(...)`，调度责任交给 pytest items。
   - 新增 `pytest_autoapi/` 插件包负责把 YAML 资产收集成 pytest items。
   - CLI 用户体验保持不变。

2. `Allure 报告改用 allure-pytest`
   - 移除对 `allure_commons` 内部 API 的直接耦合。
   - 仅使用 `allure.step / allure.attach` 等公开 API。
   - 时间戳、historyId、retries 聚合等由 `allure-pytest` 标准产出。

3. `sql / script action 升级为真实执行`
   - 让 hooks 与 `Scenario.steps[]` 内联 action 都能落地"测后清理"。
   - 第一版只支持执行单条 SQL 或本地命令。

4. `step 级 always_run / continue_on_error`
   - 配合 `Scenario.steps[]` 内联 action（见下条），统一承载所有清理动作的"无条件执行"语义。
   - 不破坏 hooks action-only 原则。

5. `Scenario.steps[]` 扩展 + `finally_steps` 废弃
   - `Scenario.steps[]` 中每个 step 在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一。
   - 移除 `ApiTemplate / ApiCase / Scenario` 三个层级的 `finally_steps` 字段；原"无条件执行"语义统一改由 `steps[]` 末尾 + `always_run: true` 承载。
   - 现存 case-style step YAML 零改动（`use` 字段不变）；新写法只在需要 `sql / script / wait` 清理时启用 `action` 字段。
   - 详见 `docs/decision_log.md` 2026-04-26 "废弃 finally_steps" 决策。

6. `ApiCase` schema 收敛：hooks 二层化 + 引用字段重命名 + 上下文叠加初始化
   - 删除 `ApiCase.before_steps / after_steps`：hooks 只保留 `ApiTemplate`（接口默认伴随）和 `Scenario`（场景前置后置）两层。
   - `cases.<id>.api` 字段重命名为 `cases.<id>.use`，与 `scenarios.steps[].use` 风格统一；validate 拒绝旧 `api:` 写法。
   - 每轮场景执行的 `RuntimeContext` 初始化按"env.variables → dataset.variables → 运行时 extract"三层叠加，作为 PRD 锁定规则（v0.1 实现已是这个形态）。
   - 详见 `docs/decision_log.md` 2026-04-26 三条配套决策（删除 ApiCase hooks / 引用字段统一为 use / 上下文叠加初始化）。

7. 在新内核稳定后，再分别打开下列开箱即用能力（仍按 P2 优先级）：
   - 严格字段校验。
   - 资产索引与影响分析。
   - 敏感变量脱敏。
   - CLI 自动生成稳定 ID。
   - step retry（基于 `pytest-rerunfailures`）。
   - 并行执行（基于 `pytest-xdist`）。
   - tag / priority 执行。

## 里程碑结论

`AutoAPI v0.1` 可以作为当前仓库的第一个正式阶段点。

它证明了：

- 新资产模型可行。
- 显式场景编排可行。
- 请求模型可以覆盖常见接口形态。
- CLI 执行、报告、历史、断言、提取已经串成闭环。
- 旧结构可以退出主路径，不再拖累新模型。

下一阶段的重点不再是证明"能不能跑"，而是：

```text
让它和业内主流测试栈一致，避免长期自研。
让它更稳定、更安全、更容易维护、更接近产品化。
```
