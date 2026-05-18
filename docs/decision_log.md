# AutoAPI 决策记录

本文档记录 AutoAPI 的重要产品和架构决策。它回答"为什么这样定"，避免后续反复讨论或实现跑偏。

> 文档治理：当一条决策已经被后续决策完全覆盖、或仅描述"某个事实已发生"且不再指导未来工作时，从本文移除以控制上下文体积。被移除的旧决策可在 git 历史中通过 `git log -- docs/decision_log.md` 查阅。本文只保留"仍在指导未来工作 / 仍在解释当前规则边界"的决策。

## 2026-04-17：P0/P1 阶段测试资产采用 YAML-first

背景：

AutoAPI 当前目标是轻量级接口自动化框架，优先完成 CLI、YAML、执行引擎、Allure 和结构化历史。

决策：

- P0/P1 阶段，`ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan` 都以 YAML 作为资产源。
- 这些测试资产通过 Git 管理。
- 不把接口资产放进数据库。
- JSONL 或数据库只用于执行历史和报告趋势数据。

原因：

- YAML 便于阅读、diff、review 和回滚。
- 当前没有 Web UI 和团队协作后端，资产入库收益不高。
- 数据库存资产会提前引入服务端、迁移、备份、权限等复杂度。

影响：

- P0 实现应围绕 `Data/apis.yaml`、`Data/cases.yaml`、`Data/Scenarios/*.yaml`、`Data/plans.yaml`。
- 历史结果可以进入 `Reports/history/*.jsonl`。

## 2026-04-17：case 不允许覆盖 method/path

背景：

case 是同一接口的不同测试变体，不应该改变接口本身。

决策：

- `ApiCase` 可以覆盖 `path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`extract`、`assertions`、`hooks`。
- `ApiCase` 禁止覆盖 `method` 和 `path`。
- `ScenarioStep override` 同样禁止覆盖 `method` 和 `path`。

原因：

- 保证接口路径和方法只来自 `ApiTemplate`。
- `ApiTemplate` 变更后，case 和 scenario 可以自然跟随。
- 避免 case 变成另一个接口。

影响：

- Resolver 需要在合成阶段保护 `method/path`。
- Validator 后续严格化时需要检查该规则。

## 2026-04-24：`form_data.kind=file` 收敛为极简模型

背景：

早期请求模型为了扩展性，把 `form_data.kind=file` 设计成 `source + path + filename + content_type`。但 AutoAPI 当前目标不是通用 API client，而是低认知负担的测试资产模型。对当前产品来说，这些字段大多属于传输层细节，而不是用户真正需要维护的配置。

决策：

- `form_data.kind=file` 正式用户字段只保留 `name + path`。
- `kind` 继续保留，取值固定为 `field / file`。
- 不再把 `source / filename / content_type` 作为 `form_data.kind=file` 的正式用户字段。

原因：

- 当前真实上传路径就是本地文件路径。
- 上传文件名默认取本地文件名，更符合平台实际使用方式。
- content type 属于 multipart 组装细节，不应增加 YAML 心智负担。

影响：

- PRD、示例资产、测试和讲解文档都要统一收敛。
- `RequestResolver` 内部仍可根据本地文件名推导 content type，但这属于实现细节。
- `binary` 仍保留自己的 `source/path/content_type` 结构，不受本决策影响。

## 2026-04-17：override 使用字段级整体覆盖

背景：

旧框架使用 `deep_merge`，dict 会递归合并。该规则对用户有认知成本。

决策：

- P0 新模型采用字段级整体覆盖。
- 未填写字段：继承上层。
- 字段已填写：整体覆盖上层。
- 字段为 null：显式清空。
- 字段内部不做 deep merge。

原因：

- 规则简单，用户容易理解。
- 避免 list、dict、scalar 使用不同合并规则。
- 即使覆盖时需要多写一点配置，也比隐式合并更可控。

影响：

- `Core/data_processing.py` 中的 `deep_merge` 不能作为新模型主合成逻辑。
- 需要新增字段级 resolver 或 composition 逻辑。

## 2026-04-17：host 只通过 Environment host_rules 解析

背景：

旧结构在 request 中写 `host`，用户希望 host 由全局环境统一管理，并按范围自动匹配。

决策：

- `ApiTemplate`、`ApiCase`、`ScenarioStep` 不出现 `host` 或 `host_key`。
- host 只在 Environment 中配置。
- 执行时根据 `host_rules` 解析 base_url。

匹配来源：

- `apis`
- `modules`
- `path_prefixes`
- `default`

原因：

- 避免 host 分散在多个资产层。
- 更接近平台化环境管理方式。
- 可以通过 priority 解决匹配优先级问题。

影响：

- `RequestResolver` 需要从 `host_rules` 解析 host。
- `method + path` 重复检查不依赖 request-level host。

## 2026-04-17：场景步骤直接引用全局唯一 ID

背景：

曾考虑使用 `case:case_xxx` 这种命名空间引用方式，但如果 ID 全局唯一，则前缀语法会增加噪音。

决策：

- 所有资产 ID 全局唯一。
- 引用时直接写 ID。
- P0 阶段，`scenario.steps[].use` 只允许引用 `case_` 开头的 ID。

示例：

```yaml
steps:
  - id: 启动业务
    use: case_start_task_success
```

原因：

- YAML 更简洁。
- ID 前缀已经能表达类型。
- 校验器可以根据字段语义和 ID 前缀检查引用合法性。

影响：

- 不使用 `case:`、`api:`、`scn:` 作为引用语法。
- 所有资产 ID 需要全局唯一。

## 2026-04-17：P0 阶段 ID 手写，后续再自动生成

背景：

当前没有平台或 CLI 生成 ID 的能力。

决策：

- P0 阶段 ID 由用户手写。
- 使用可读、稳定、语义化 ID。
- 推荐格式：
  - `api_start_task`
  - `case_start_task_success`
  - `scn_hanoi_main_flow`
  - `plan_hanoi_regression`

原因：

- 随机短 ID 或纯数字 ID 不适合当前 YAML 手写阶段。
- 语义化 ID 更容易阅读、引用和 CLI 调试。

影响：

- P2 可以提供 CLI 自动生成 stable ID。
- 未来平台内部可以有数据库主键，但 YAML 引用仍使用 stable ID。

## 2026-04-17：P0 暂时关闭严格字段 schema 校验

背景：

当前旧 Validator 很严格，但新模型还在演进。如果一开始就做完整字段校验，会拖慢核心链路开发。

决策：

- P0 只保留 Validator 壳子和基础检查。
- 暂不做完整字段白名单、类型、枚举、request/extract/assertions/hooks schema 校验。

P0 保留检查：

- YAML 可读取。
- 全局 ID 唯一。
- 引用关系存在。
- `method + path` 重复。
- `host_rules` 基础冲突。

原因：

- 先跑通 Repository、Resolver、Executor、CLI 主链路。
- 等模型稳定后再补严格校验，避免反复改 schema。

影响：

- P2 再补严格字段校验。
- 新 Validator 需要保留扩展点。

## 2026-04-24：请求模型升级为 Postman / MeterSphere 风格标准

背景：

原始 P0 请求结构偏简化，主要围绕 `params/body_type/body/files`。继续沿这个方向加能力，会导致后续 `path_params`、`raw subtype`、`auth`、`cookies`、文件上传和纯二进制上传都只能用补丁方式接入。

决策：

- PRD 中的长期标准请求模型升级为：
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
  - `timeout`
  - `verify`
  - `allow_redirects`
- `params` 在文档层统一改名为 `query`。
- `body_type` 在文档层统一改名为 `body_mode`。
- `path_params` 独立建模，不再混在 `path` 字符串拼接里。
- `raw` 使用 `raw + raw_type` 作为长期标准。
- `auth` 和 `cookies` 纳入请求模型标准结构。
- 文件上传长期主路径走 `form_data`。
- `form_data` 使用统一 item 结构，`kind=field|file`。
- 纯文件流请求长期走 `binary`。

原因：

- 更接近 Postman / MeterSphere 的使用心智。
- 请求结构分层更清晰，便于 CLI、YAML 和后续 Web UI 统一。
- 避免继续在旧抽象上堆补丁，降低后续扩展成本。
- 平台化后更容易做表单编辑、调试和导入映射。

影响：

- PRD 先定义完整标准，代码实现可以分阶段落地。
- 当前执行器如果仍只支持子集，也必须按这个长期标准演进，而不是继续扩旧字段。
- 相关示例、技术设计和后续导入能力都要围绕该模型收敛。

## 2026-04-25：hooks 改为 action-only，废弃环境鉴权模板方向

背景：

之前的环境级 `setup_cases / teardown_cases / auth_profile` 和场景级 hooks 都支持通过 `use` 引用 case。这个方向会把业务接口调用藏进 hooks 或环境配置中，容易重新形成隐式链式编排，和“场景显式编排”的产品原则冲突。

决策：

- `Scenario.steps` 是唯一承载业务接口编排的位置。
- `ApiTemplate`、`ApiCase`、`Scenario` 的前置、后置和兜底 hooks 统一使用 action-only 模型。
- hooks 中不允许出现 `use`，不允许引用 `case` 或 `api`。
- 当前 action 第一批只实现 `wait`。
- `sql` 和 `script` 作为结构扩展点预留，暂不实现执行能力。
- action 内部如果需要把执行结果写回上下文，统一使用 `extract` 字段，保持和接口/用例/场景提取命名一致。
- 环境级 `setup_cases / teardown_cases / auth_profile / auth_profiles` 不再作为产品方向继续扩展，后续代码清理时移除。
- 登录、准备数据、清理数据等接口动作必须作为普通场景 step 显式排列。

影响：

- 已经实现的环境级鉴权模板属于临时方向偏差，需要通过新的清理计划移除。
- 已经实现的场景级 hooks 需要从 `ScenarioStep(use=case_id)` 改为 `HookStep(action=...)`。
- 文档中的 `setup` / `teardown` 只作为未来平台化生命周期术语保留，不进入当前 YAML 字段。

## 2026-04-25：P1 核心能力收口，后续显式进入 P2

背景：

Allure 自动 HTML、公共断言/提取、场景级数据驱动、场景级 hooks、`finally_steps`、action-only hooks、环境级 auth_profile 清理，以及企业常用断言/提取 source 扩展已经完成第一版，并由用户在 Windows `.venv` 环境中完成验证。

决策：

- 当前 P1 按已讨论范围收口。
- 后续不再以“补 P1 缺口”为名继续扩大执行器能力。
- 如果继续开发，应从 P2 清单中显式选择一个起点。
- P2 起点包括但不限于：
  - `step retry`
  - `step continue_on_error`
  - OpenAPI 导入
  - SQLite 历史
  - 敏感变量脱敏
  - 资产索引与影响分析
  - CLI 稳定 ID 生成
  - 严格字段校验
  - tag / priority 执行

原因：

- 当前核心模型已经能覆盖轻量级接口自动化框架的主要使用闭环。
- 继续推进的能力大多属于产品化、平台化或执行增强，需要单独评估优先级。
- 明确 P1 收口可以避免把 P2 能力静默混入当前阶段。

影响：

- 下一轮实现必须先明确选择 P2 目标，并创建对应 numbered ExecPlan。
- 文档和计划应把 P1 已完成能力与 P2 延后能力分开描述。

## 2026-04-26：执行内核切换到 pytest，报告改用 allure-pytest

背景：

当前 AutoAPI 自研 `Engine/executor.py` 的 `run_case / run_scenario / run_plan` 调度链，并通过 `allure_commons` 内部 API（`AllureLifecycle / AllureFileLogger / plugin_manager.register/unregister`）直接驱动 Allure 写入。短期内能跑通 P0/P1 主链路，但有以下结构性问题：

- 自研三套并列入口、`_run_scenario_iteration` 手动遍历 datasets、`_run_hook_step_list` 手动跑 before/after/finally，本质是在重新实现 pytest 已经免费提供的能力。
- `Utils/allure_runtime.py` 依赖的是 `allure_commons` 非公开 API；`historyId` 自己 `md5(target_type:target_id)`，step 时间戳用 `step_cursor += duration_ms` 手动累加，与 Allure 官方语义不一致，TestOps 时间线、retries 聚合、flaky 检测都难以对齐。
- P2 路线图中的 `step retry`、`step 失败继续`（本次同步以 step 字段 `continue_on_error` 升 P1，见同日另一条决策）、`tag / priority 执行`、并行、严格字段校验等能力，在 pytest 生态中分别对应 `pytest-rerunfailures`、`pytest.mark.xfail` / `pytest-check`、`pytest.mark + -m`、`pytest-xdist`、`pydantic + pytest_collection_modifyitems`，继续自研性价比低。
- PRD §1 远期定位为多端自动化平台（接口 + WebUI + APP），业内 WebUI / APP 自动化几乎都默认架在 pytest 之上；自研调度路线会让接口、UI、APP 三端各做一套执行器。
- PRD §2 第 8 条"接口自动化内核必须独立于平台 UI"恰好支持 pytest 路线：pytest 是无 UI 的纯运行器，平台层只需启 pytest 子进程并采集 `allure-results / *.jsonl`，是业内成熟模式。

决策：

- 自 AutoAPI v0.2 起，执行内核改为 **pytest collection + 适配器调用现有领域代码**。具体由仓库内独立 plugin 包 `pytest_autoapi/` 承载，负责把 `cases.yaml`、`Scenarios/*.yaml`、`plans.yaml` 收集成 pytest items。
- Allure 报告改用 **`allure-pytest`** 标准接入；测试主体内只允许使用 `allure.step / allure.attach` 等公开 API，不再直接调用 `allure_commons` 内部模块。`environment.properties` 与 `categories.json` 仍由 `pytest_sessionstart` hook 主动写入，保留 PRD §14 行为。
- CLI 用户体验保持不变：`AutoAPI --case/--scenario/--plan/--env/--data` 子命令仍可用，内部翻译为 `pytest.main(...)`。
- `validate` 子命令与 pytest 无关，保持原状。
- JSONL 历史字段保持 PRD §14 不变，写入入口改为 pytest hook（`pytest_runtest_logreport` + `pytest_sessionfinish`）。

保留：

- PRD §6 资产模型（`ApiTemplate / ApiCase / Scenario / TestPlan / Environment`）。
- PRD §8 字段级整体覆盖语义。
- PRD §9 host_rules 解析。
- PRD §13.1 断言/提取 source 与 op。
- `Schema/data_models.py`、`Schema/data_validation.py`、`Core/repository.py`、`Core/composer.py`、`Core/context.py`、`Engine/host_resolver.py`、`Engine/request_resolver.py`、`Engine/transport.py`、`Engine/extractor.py`、`Engine/assertion_engine.py`、`Engine/jsonpath_tool.py`、`Utils/yaml_io.py` 全部保留为领域内核。

改造：

- `Engine/executor.py` 中的调度类（`run_case / run_scenario / run_plan`、`_run_scenario_iteration`、`_run_hook_step_list`、`_run_plan_core` 等）改造成纯函数 `execute_one(executable, ctx, env, transport) -> StepResult`，调度责任交给 pytest items。
- `Utils/allure_runtime.py`（`AllureRuntimeReporter`）以及 `Utils/allure_reporter.py` 中调用 `allure_commons` 内部 API 的部分被替换为 `allure-pytest` + `allure.step / allure.attach`。
- `Engine/history_writer.py` 改成 pytest hook：逐 item 写 `results.jsonl`，session 结束时写 `runs.jsonl`。

不兼容点：

- `RunResult / StepResult` 的对外形态可能调整；JSONL 字段保持 PRD §14 不变。
- Allure 中 testcase 的 nodeid、historyId、时间戳由 `allure-pytest` 标准产出，不再与旧自研 ID 一致。
- 自研 `Executor` 的对外类与方法将逐步移除，外部脚本如直接调用过这些方法需要适配。

落地方式：

- 详见 `plans/20_pytest_kernel_migration.md`。先做"插件骨架 + Allure 标准化"作为最低风险切换；再分别打开 retry / continue / tag / priority 等"开箱即用"能力。
- 现有 P1 已交付能力以等价行为迁移为准；外部行为变化由 ExecPlan 验收命令保证。

影响：

- 新增运行时依赖：`allure-pytest`。其余 `pytest-rerunfailures / pytest-xdist` 等仅在对应 P2 任务激活时引入。
- 平台化阶段不再需要从零写执行器与报告写入；平台只做"拼 pytest 命令 + 读 Reports/"。
- 远期 WebUI / APP 自动化按相同模式接入（`pytest_autoui` / `pytest_autoapp`），共享同一套 runner、reporter、CI 集成。

## 2026-04-26：sql / script action 从结构预留升级为 P1 必做

背景：

`docs/decision_log.md` 2026-04-25 决策将 hooks 收敛为 action-only，第一批仅实现 `wait`，`sql / script` 作为结构扩展点预留。结合 PRD §1 和 §11 P1 的"完成核心能力闭环"目标，仅有 `wait` 不足以覆盖企业接口测试中常见的"测后清理"诉求；切到 pytest 内核后，hooks 由 fixture teardown 承载，`finally_steps` 的执行可靠性进一步提升，sql/script 的真实执行变成自然要求。

决策：

- `action.kind=sql` 在 P1 必须有真实执行能力。
  - 第一版只支持执行单条 SQL，并把结果写回 `RuntimeContext`。
  - 数据源在 `config.yaml` 中以 `datasources` 顶层键声明，hooks 通过 `datasource` 引用。
  - `extract` 字段统一从结果集提取，写入 `RuntimeContext`。
- `action.kind=script` 在 P1 必须有真实执行能力。
  - 第一版只支持执行本地命令或 Python 入口；安全沙箱、跨机执行、容器化执行不在 P1 范围。
  - 标准输出 / 退出码 / 自定义 `extract` 字段写回 `RuntimeContext`。
- 三种 action（`wait / sql / script`）共享同一个 `extract` 语义：从 action 结果中按 source/path 提取，写入上下文。

原因：

- 接口自动化的"清理"在企业实践中至少有过半比例是 SQL 直清；只有 `wait` 的 hooks 在 P1 阶段没有工程意义。
- 切到 pytest 内核后，hooks 在 fixture teardown 中执行，`finally_steps` 即使在 KeyboardInterrupt / 异常中断 / RuntimeContext 损坏时也会跑，sql/script 落地后才能真正发挥这种可靠性。
- 落地 sql/script 让 hooks 与 `Scenario.steps`（业务接口编排）形成真正互补：业务流走 steps，环境/数据辅助走 hooks。

影响：

- 新增 `Engine/action_runner.py`（或 `pytest_autoapi/actions.py`）作为 sql/script 的执行入口；`wait` 也统一走该入口。
- `config.yaml` 新增 `datasources` 声明，由 sql action 引用。
- 新增运行时依赖：`sqlalchemy`（或 `pymysql / psycopg2 / sqlite3` 按需）。具体选型在 ExecPlan 中确认，遵循 `AGENTS.md` "除非用户明确要求，不新增第三方依赖" 的规则，引入前会先写入 ExecPlan。
- PRD §11 P1 增加 sql / script 落地条目；§12 描述同步更新；§11 P2 不再保留 sql / script 字样，避免重复。

## 2026-04-26：新增 step 字段 always_run / continue_on_error，并提前到 P1

背景：

PRD §11 P2 曾列出 "step 重试 / step 失败继续"。同日决策将执行内核切到 pytest 后，"无条件执行某个 step" 与 "失败后继续"在 pytest 生态里分别对应 fixture finalizer / `pytest.mark.xfail` / `pytest-check`，落地成本约几十行代码；同时这两个能力是表达"接口级清理"的最干净路径——按 hooks action-only 原则（2026-04-25 决策），不允许在 hooks 里 `use: case_xxx`。

决策：

- `Scenario.steps[]` 新增字段：
  - `always_run: bool`，默认 `false`。
    - `true`：无论前面 step 是否失败，本 step 都会执行。多个 always_run step 按声明顺序执行。
    - 即使整个 scenario 已被判定失败，标了 `always_run` 的 step 仍然进入执行阶段；其自身失败仍会被记录到结果中，但不影响其它 always_run step 的尝试执行。
  - `continue_on_error: bool`，默认 `false`。
    - `true`：本 step 如果失败，scenario 不立即停止，继续执行后续 step。
    - 该 step 自身的状态仍为 `failed/error`；scenario 整体状态由所有 step 聚合得出。
- 默认 P1 行为仍然是"失败即停止"。仅当用户在 step 上显式声明 `always_run` 或 `continue_on_error` 时才偏离默认行为。
- 这两个字段对 `before_steps / after_steps / finally_steps` 不生效；hooks 的执行规则由各自语义保证（`finally_steps` 永远执行，`after_steps` 仅成功后执行）。
- 这两个字段是表达"接口级清理"的标准方式：把清理 case 写在 `Scenario.steps` 末尾，并加 `always_run: true`，等价于"无论前面流程是否失败，都尝试调用清理接口"，且业务流仍然在 `Scenario.steps` 显式可见。
- "step 重试"（`retry / reruns`）仍保留在 P2，落地时通过 `pytest-rerunfailures` 接入，本决策不覆盖该能力。

原因：

- 切到 pytest 内核后，这两个字段在收集期映射为 pytest marker（`@pytest.mark.always_run` / `@pytest.mark.continue_on_error`），适配器在 fixture / collection 阶段处理执行顺序，落地成本极低。
- 用户口述的"finally 是为了让最后清理接口一定执行"指向"接口级清理"，与 hooks action-only 决策（2026-04-25）冲突。`always_run + continue_on_error` 是不破坏 action-only 原则的等价解。
- 业务流的全部接口编排仍然只在 `Scenario.steps` 中可见，符合 PRD §2 第 3 条"场景编排必须显式"。

影响：

- `Schema/data_models.py` 的 `ScenarioStep` 新增 `always_run / continue_on_error` 字段。
- `Schema/data_validation.py` 接受这两个字段。
- `pytest_autoapi` 把这两个字段映射为 pytest marker；执行器在 collection / fixture 阶段处理顺序与失败传播。
- PRD §11 P1 增加该字段；P2 删除已被本字段覆盖的 "step 失败继续"，保留 "step 重试" 在 P2。
- PRD §6.3 Scenario YAML 示例补充 `always_run` 演示。

## 2026-04-26：废弃 finally_steps，统一用 steps[].always_run + step 内联 action 表达清理

背景：

引入 `steps[].always_run / continue_on_error` 之后，"无条件清理"在 v0.2 设计中存在两条等价路径：

- 路径 A — `Scenario.finally_steps`：只能放 `wait / sql / script` action，不能 `use: case`（hooks action-only）。
- 路径 B — `Scenario.steps[]` 末尾 + `always_run: true`：只能 `use: case`，不能内联 sql / script。

两者互补地切了"非接口清理"和"接口清理"两个域，根因是 `Scenario.steps[]` 当前只支持 `use: case`，不接受内联 action。一旦 step 也允许内联 action，路径 A 与 B 完全可以合并到 B，`finally_steps` 即冗余。

决策：

- 删除 `finally_steps` 字段，作用域覆盖三个层级：`ApiTemplate` / `ApiCase` / `Scenario`。
- 保留 `before_steps / after_steps`（同样作用于三个层级），仍是 action-only。它们承担"非业务接口辅助"的视觉分块（场景叙事中的"准备 → 主体 → 收尾"），不与 `steps[]` 合并。
- 扩展 `Scenario.steps[]` 字段形态：每个 step 在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一，现存所有 case-step YAML 零改动；`always_run / continue_on_error` 对两类 step 都适用。
- 所有"无条件清理"——无论是 DELETE 接口、SQL DELETE、还是清理脚本——统一通过 `Scenario.steps[]` 末尾 + `always_run: true` 表达。
- 上一条决策（同日"新增 step 字段 always_run / continue_on_error"）中"这两个字段对 `before_steps / after_steps / finally_steps` 不生效"在 `finally_steps` 删除后自动收缩为：仅作用于 `Scenario.steps[]`。

YAML 示例：

```yaml
scenario.yaml:
before_steps:
  - id: 等待服务稳定
    action: { kind: wait, seconds: 2 }

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

after_steps:
  - id: 写日志
    action:
      kind: sql
      datasource: main_db
      sql: "INSERT INTO scenario_log (...) VALUES (...)"
```

原因：

- 两条等价机制对用户是认知冗余：用户写"无条件清理"时要先在脑子里判断"这是 case 还是 sql/script"，然后选不同字段。合并后只剩一条规则——"清理放 `steps[]` 末尾，标 `always_run: true`"。
- pytest 视角：`steps[]` 收集成 pytest items 后用 marker 控制执行顺序与失败传播即可，不需要再单独搞 fixture finalizer 跑 finally_steps。实现路径单一，`pytest_autoapi` 插件复杂度更低。
- 业务接口与 sql/script/wait 都按声明顺序在 `steps[]` 中可见，符合 PRD §2 第 3 条"场景编排必须显式"。

边界与取舍：

- 取消了 `ApiCase` / `ApiTemplate` 的 `finally_steps` 之后，`AutoAPI --case case_xxx` 单跑 case 时**不再有"无条件清理"入口**。如果一个 case 需要保证清理副作用，用户需要把它包成 scenario，并把清理动作作为 `steps[]` 末尾 + `always_run: true` 表达。这一条边界在用户产品评审中已确认接受。
- `before_steps / after_steps` 仍保留为 action-only（不允许 `use: case`），与 2026-04-25 "hooks action-only" 决策一致。
- step 字段扩展采取轻量方案（`use` 与 `action` 二选一，xor 互斥），不引入 step 层 `kind` 字段；现存 case-step YAML 完全不需要迁移。

影响：

- `Schema/data_models.py`：`ApiTemplate / ApiCase / Scenario` 移除 `finally_steps` 字段；`ScenarioStep` 增加 `action: ActionSpec | None`，并加 "use xor action" 互斥校验。
- `Schema/data_validation.py`：解析时拒绝 `finally_steps`，以及 step 同时填 use 与 action 的情况。
- `pytest_autoapi`：collection 阶段把 `action`-style step 与 `use`-style step 统一收成 pytest items；`always_run` 标记对两类 item 同样生效。
- `Engine/action_runner.py`（待建）作为 step inline action 的执行入口与 hooks 共享。
- PRD §6.1 / §6.2 / §6.3 / §11 / §12 / §18：移除 `finally_steps` 字段与示例；§6.3 step 字段说明扩展；§12 hooks 语义只剩 before / after；§11 把 sql / script 落地从"hooks 内"挪到"hooks + step inline action"。
- `docs/release_v0.1.md` 不动：v0.1 已交付包含 `finally_steps`，事实记录保留。
- `docs/current_state.md` 与 `plans/20_pytest_kernel_migration.md` 的 v0.2 切换方向同步：删除 finally_steps 相关迁移项，新增 step inline action 实现项。

## 2026-04-26：删除 ApiCase 的 before_steps / after_steps（hooks 二层化）

背景：

继"废弃 finally_steps"之后再次审视 hooks 模型，发现 `ApiCase.before_steps / after_steps` 与 `ApiTemplate` / `Scenario` 同名字段构成三层重叠。继续保留它有两个具体问题：

- 字段级整体覆盖语义反直觉。按 §8 规则，`case.before_steps: [...]` 会**整体覆盖**模板的 `before_steps`，而不是叠加。但用户写 case hook 时几乎总是期望"在模板默认之上再加一段"，这是个内置的踩坑点。
- Case 层 hook 的合理使用场景几乎不存在。ApiCase 是同一接口的"参数变体"，变体之间需要不同 hook 的需求基本不存在。真有差异时多半是流程级（应下沉到 Scenario）或接口级（应上提到 ApiTemplate）。

决策：

- 从 `ApiCase` schema 中删除 `before_steps / after_steps` 字段。Hooks 只保留两层：`ApiTemplate`（接口默认伴随）和 `Scenario`（场景前置后置）。
- `ApiTemplate.before_steps / after_steps` **保留**，承担"接口默认伴随动作"的 DRY 复用入口（同一接口在每次调用前后所需的 wait / sql / script 辅助动作）。
- validate 在 YAML 中遇到 `cases.<id>.before_steps` 或 `cases.<id>.after_steps` 时报明确错误，提示迁移路径："case 级 hook 已下线，请把流程级动作放到 Scenario 层；如果是接口默认动作，请上提到 ApiTemplate"。
- v0.1 已交付的 case-level hooks 写法不需要数据迁移工具；本变更随 v0.2 schema 收敛一起落地，与 `finally_steps` 删除是同一个 schema 改动批次。

影响：

- `Schema/data_models.py`：`ApiCase` 移除 `before_steps / after_steps` 字段。
- `Schema/data_validation.py`：解析时拒绝 case 写 hooks。
- `Core/composer.py`：合成时不再考虑 case 层 hooks，hooks 合成只在 ApiTemplate → Scenario 两层间发生。
- PRD §6.2：覆盖列表中删除 `before_steps / after_steps`；需求项明确"用例不再覆盖 hooks"。
- PRD §11 / §12：hooks 语义说明从三层改为两层。
- `docs/release_v0.1.md` 不动：v0.1 已交付包含 case-level hooks 字段，事实记录保留；v0.2 切换段落补一条"删 ApiCase hooks"。

## 2026-04-26：YAML 引用字段统一为 `use:`（命名风格收敛）

背景：

PRD 当前对"资产 ID 引用"用了两个不同的字段名：

- ApiCase 引用 ApiTemplate：`cases.<case_id>.api: api_xxx`。
- ScenarioStep 引用 ApiCase：`scenarios.steps[].use: case_xxx`。

两者都是同一个语义动作（"我引用某个上层资产 ID"），但风格不一致：一个像 OO 属性（`api`），一个像动作动词（`use`）。在 v0.2 内核切换前一并改名，未来改的成本更大；尤其是 v0.2 后 plugin、validator、平台 UI 都会绑定 YAML 字段名。

决策：

- 把 `cases.<case_id>.api` 字段重命名为 `cases.<case_id>.use`，与 `scenarios.steps[].use` 风格统一。
- 引用目标的合法性约束按 §7 不变：`cases.<id>.use` 仍然只能引用 `api_` 开头的 ApiTemplate ID；`scenarios.steps[].use` 在 P0/P1 仍然只能引用 `case_` 开头的 ApiCase ID。即"用什么字段名"统一，"能指向什么 ID 前缀"按上下文区分。
- 不保留向后兼容：v0.2 schema 切换时一次性改完。validate 在 YAML 中遇到 `cases.<id>.api: ...` 时报明确错误，提示改用 `use:`。
- 与"v0.1 → v0.2 schema 收敛"是同一批改动（与 finally_steps 删除、case hooks 删除合并到 Phase D）。

边界与取舍：

- 不动 `ApiCase` 的 `meta.api` 这种潜在子字段（PRD 当前不存在）。本决策只针对 `cases.<id>.api` 这一个具体字段。
- 不动 `plans.<id>.scenarios[]` / `plans.<id>.cases[]` 这两个数组。它们是"ID 列表"，不是"引用字段"，没有同样的命名不一致问题。
- v0.1 已写就的示例 / 用户 YAML 中 `cases.<id>.api: ...` 必须在切换 v0.2 时改为 `use`，但场景 step `use:` 完全不动，迁移成本最小。

影响：

- `Schema/data_models.py`：`ApiCase` 字段 `api` 重命名为 `use`。
- `Schema/data_validation.py`：报错路径与字段名同步。
- `Core/repository.py / composer.py`：解析与合成时按新字段名读取。
- PRD §6.2：所有 cases 示例 `api: api_xxx` 改为 `use: api_xxx`。
- PRD §7：引用规则 `cases.<case_id>.api` 改为 `cases.<case_id>.use`。
- `examples/p0_minimal/Data/cases.yaml` 与 `examples/reading_house/Data/cases.yaml`：随 v0.2 schema 切换一并改。

## 2026-04-26：场景执行的上下文初始化采用"叠加"语义

背景：

PRD §6.3 关于 `Scenario.datasets` 只说"每轮使用独立上下文"，但没说独立上下文是从空白开始还是从环境变量复制后再叠加 dataset。同一份 YAML 在两种解释下行为差距很大：

- 解释 A（"替换"）：每轮上下文从空白开始，dataset.variables 是唯一初始变量。env.variables 不会进入场景上下文。
- 解释 B（"叠加"）：每轮上下文先把 env.variables 拷贝进来作为基底，再用 dataset.variables 叠加（同名 key 覆盖），运行时 extract 再叠加在最上层。

实际项目中用户在 env.variables 里维护跨场景的公共变量（如 `token / baseUrl`），如果走"替换"，dataset 必须重写一遍这些变量，或者每个场景在第一步用 sql/script 把 token 拉一次——非常不便。

决策：

- 采用"叠加"语义。每轮场景执行的上下文初始化顺序为：
  1. 拷贝当前 env 的 `variables`（含 `request_defaults` 中暴露给变量的部分）作为基底。
  2. 叠加当前 `dataset.variables`（同名 key 覆盖 env.variables）。
  3. 运行时 `extract` 写入的变量再叠加（同名 key 覆盖前两层）。
- 当 `Scenario` 没有 `datasets` 时，相当于一轮空 dataset：基底就是 env.variables，再加运行时 extract。
- "每轮使用独立上下文"仍然成立：第二轮 dataset 不会看到第一轮的 extract 结果，env.variables 在每轮开始都重新拷贝（保证不被前一轮污染）。
- env.variables 与 dataset.variables 都是只读快照视角下的初始基底；运行时 extract 的写入只发生在当前轮上下文内，不回写到 env 或 dataset。

边界与取舍：

- 与 PRD §8 "字段级整体覆盖"对齐：变量层级合并在 key 粒度上，是 dict 合并，不是 list 合并；list 类型变量按 key 整体覆盖。
- 不引入"变量 visibility 修饰符"（如 `private / public`）：变量只有"在哪一层定义"的来源差别，没有显式作用域控制，保持当前低认知负担。
- 平台化后如需"环境只读 / dataset 只追加 / extract 只追加"等更严格的隔离规则，再单独决策，不在本决策范围。

影响：

- PRD §6.3：在 `datasets` 子节后新增"上下文初始化与变量合并规则"段落，明确三层叠加顺序。
- PRD §9（host 解析规则）/ §11：保持不变，但 §9 的"环境优先级"说明可点出"同一规则也适用于变量初始化"。
- `Engine/executor.py` / `pytest_autoapi/`：每轮 dataset 起 `RuntimeContext` 时按"env.variables 拷贝 → dataset.variables 叠加"的固定路径初始化；现有 v0.1 实现路径已经是这个形态（见 `docs/current_state.md`"dataset variables 优先覆盖 env variables"），本决策只是把它从"实现细节"上升为"PRD 锁定规则"。
- `docs/validation_matrix.md`：补一条 dataset 多轮执行时 env.variables 仍然可见的观察点。

## 2026-04-26（修订）：sql action 真实执行延后到 P2，第一版仅落 wait + script

背景：

2026-04-26 上一条"sql / script action 升 P1 必做"决策中，sql 与 script 被绑定为同一批落地。Phase C 开工前与产品再次对齐时确认两点：

- 当前 v0.2 切换 + Phase D schema 收敛刚完成，业务侧没有立即依赖真实 SQL 清理的场景（`examples/reading_house` 只跑 HTTP 接口）。
- 用户后续 SQL 选型确定使用 PostgreSQL，但希望"放在后面再实现"，避免在 v0.2 内核切换的关键期同时引入数据库依赖与连接池调优。

按 AGENTS.md "除非用户明确要求，不新增第三方依赖" 与"P1 完成后再决定是否引入 SQLAlchemy / psycopg2"对齐，决定把 sql 的真实执行从"P1 必做"降级。

决策：

- `action.kind=sql` 真实执行延后到 P2，目标方言锁定为 PostgreSQL（不再保留 sqlite/mysql 多方言路径）。
- Phase C 范围内只做 `wait` + `script` 两类 action 的真实执行；`sql` 仍由 `Engine/action_runner.py` 命中后抛 `NotImplementedError`，并在 `extract_out` 中保留 `action` 原始字段方便后续接入。
- `config.yaml` 顶层 `datasources` 字段在第一版**不引入**——避免 schema 引入了字段但没有任何驱动支撑、用户写错时报错路径不清晰。等 P2 落地 PostgreSQL 时一并引入 schema、validator、`psycopg2` 依赖。
- `Schema/data_validation.py` 中已有的"action.kind ∈ {wait, sql, script}"白名单不变（只校验 schema 合法，不要求实际能执行），让用户可以提前在 YAML 中预声明 sql 占位 step，到 P2 上线时无需修改 YAML。
- `Tests/test_step_policy.py` 中 `test_executor_inline_action_sql_returns_not_implemented_error` 用例继续保留，作为"sql 暂未实现"语义的回归锁。

边界：

- 不影响 hooks 与 inline action 的统一执行入口设计——`Engine/action_runner.py` 统一处理 wait/script/sql 三类，sql 分支只是抛 NotImplementedError，未来加 PostgreSQL 实现时只动一个分支。
- 不影响"清理动作的统一表达"——用户仍然可以用 `Scenario.steps[]` 末尾 + `always_run: true` + HTTP `use:` 表达清理（接口级清理是 v0.2 的主推荐写法）；script 清理也走同一套调度。
- 与 PRD §11 / §12 中"sql / script 在 P1 内升级为真实执行能力"的描述存在偏差，PRD 同步调整为"script 在 P1 内升级为真实执行能力；sql 真实执行延后到 P2，目标方言 PostgreSQL"。

影响：

- `requirements.txt` 不变：本次不新增 `sqlalchemy / psycopg2` 任何依赖。
- 新增 `Engine/action_runner.py`（不放 `pytest_autoapi/` 包内），保持"actions 是测试动作而非 pytest 调度"的语义；Executor 单向 import 这一模块，避免 Engine ↔ pytest_autoapi 双向耦合。
- `Engine/executor.py` 的 `_execute_action_hook` 只保留薄壳，把 wait/script/sql 三个分支转发到 action_runner，hooks 与 inline action 行为同源。
- PRD §11 P1 调整：`script` 留 P1，`sql` 移到 P2（注明"目标 PostgreSQL，第一版仅 NotImplementedError 占位"）。

## 2026-04-26：script action 默认 expect_returncode=0

背景：

`action.kind=script` 在 P1 内升级为真实执行能力（参见上一条决策）。落地时存在两种 returncode 语义路径：

- 路径 A（推荐）：默认 `expect_returncode=0`，进程退出码不等于期望值时 step 自动 `failed`；`stdout / stderr / returncode` 仍可通过 `extract` 写回 `RuntimeContext` 供后续断言。
- 路径 B：完全不解释退出码，所有判定全部交给用户写 `extract` + `assertions`。

决策：

- 采用路径 A：第一版 `script` action 默认 `expect_returncode: 0`；用户可在 action 中显式声明 `expect_returncode: 1` 等具体值，或 `expect_returncode: any` 取消校验。
- `expect_returncode` 仅校验进程退出码，不参与 `extract` / `assertions` 的判定。
- 路径 B 的能力由 A 完全覆盖（`expect_returncode: any` 即等价于 B），因此不再保留双轨。

原因：

- 测试 step 的默认观感是"我期望它成功"，路径 A 在 90% 清理脚本场景下用户一行不用写就能用。
- 路径 B 强制每个 script step 多 5 行 extract+assertions 模板代码，提高人因错误风险（用户忘写就静默通过）。
- 路径 A 完全包含路径 B 的能力，无功能损失。

影响：

- `Engine/action_runner.py` 中 `_run_script(action, ctx)` 实现按"读取 `expect_returncode`（默认 0），命中 `any` 跳过校验，否则进程退出码不等于期望值时把 step 标 `failed`"的固定逻辑。
- `Schema/data_validation.py` 在 `_validate_inline_action` 内允许 `expect_returncode: int | "any"` 字段（第一版接受这两类，其它类型报 `ValidationException`）。
- `Tests/test_actions.py` 覆盖三条主路径：默认成功、默认失败、`expect_returncode: any` 跳过校验。
