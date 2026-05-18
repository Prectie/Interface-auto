# AutoAPI v0.2 执行内核切换到 pytest

## 1. Purpose / Big Picture

完成后，用户可以观察到：

- `python run.py --case ... / --scenario ... / --plan ...` 与 v0.1 的 CLI 行为完全一致，但内部由 pytest 执行；执行结束自动产出标准 `allure-pytest` 结果，再由 CLI 调用 `allure generate` 输出 HTML。
- `Reports/history/runs.jsonl` 与 `Reports/history/results.jsonl` 字段保持 PRD §14 不变，写入入口由 pytest hook 提供。
- 用户在 `Scenario.steps[]` 上加 `always_run: true` 即可让该 step 在前序失败时仍执行；加 `continue_on_error: true` 即可让 step 失败后 scenario 继续走完。所有清理动作（接口 / SQL / 脚本）通过这种方式统一表达。
- `Scenario.steps[]` 中每个 step 可以在 `use: case_xxx` 与 `action: {kind: wait/sql/script, ...}` 之间二选一；hooks (`before_steps / after_steps`) 与 step 内联 action 共享同一个 action 执行入口。
- `action.kind=sql` 能执行真实 SQL，`action.kind=script` 能执行本地命令；`wait` 行为不变。
- 现存 case-style step YAML 零改动；`finally_steps` 字段在 `ApiTemplate / ApiCase / Scenario` 三个层级被移除，validate 拒绝带 `finally_steps` 的 YAML 并给出明确报错。
- `ApiCase` 不再持有 `before_steps / after_steps` 字段；validate 在 YAML 中遇到 `cases.<id>.before_steps` 或 `cases.<id>.after_steps` 时报明确错误。
- `cases.<id>.api` 字段重命名为 `cases.<id>.use`，与 `scenarios.steps[].use` 风格统一；validate 在 YAML 中遇到旧 `cases.<id>.api: ...` 时报明确错误并提示改用 `use:`。
- `Scenario` 每轮场景执行的 `RuntimeContext` 初始化按"env.variables → dataset.variables → 运行时 extract"三层叠加：env.variables 作为只读基底，dataset 在每轮开始叠加，运行时 extract 写在最上层；多轮 dataset 互不污染。

## 2. Scope

In scope：

- 新增 plugin 包 `pytest_autoapi/`：
  - `pytest_autoapi/plugin.py`：实现 `pytest_collect_file / pytest_collection_modifyitems / pytest_sessionstart / pytest_sessionfinish / pytest_runtest_logreport`。
  - `pytest_autoapi/items.py`：实现 `AutoApiCaseItem / AutoApiScenarioItem / AutoApiPlanItem` 等 pytest item 类。
  - `pytest_autoapi/actions.py`：`wait / sql / script` 三种 action 的执行入口。
  - `pytest_autoapi/__init__.py`：注册 entry point。
- 改造 `Engine/executor.py`：抽出纯函数 `execute_one(executable, ctx, env, transport) -> StepResult`，移除原 `run_case / run_scenario / run_plan / _run_*` 调度方法（以等价行为保留为内部工具函数即可，不再对外暴露）。
- 改造 `Utils/allure_runtime.py` 与 `Utils/allure_reporter.py`：移除对 `allure_commons` 内部 API 的直接依赖，统一使用 `allure-pytest` + `allure.step / allure.attach`。`environment.properties` 与 `categories.json` 改由 plugin 的 `pytest_sessionstart` hook 写入。
- 改造 `Engine/history_writer.py`：把 `runs.jsonl / results.jsonl` 的写入入口改为 plugin hook。字段保持 PRD §14 不变。
- 改造 `run.py`：`--case / --scenario / --plan / --env / --data` 改为构造 `pytest.main(...)` 参数；`validate` 子命令逻辑不变。
- `Schema/data_models.py`、`Schema/data_validation.py`：
  - `ScenarioStep` 增加 `always_run / continue_on_error` 字段。
  - `ScenarioStep` 增加 `action: ActionSpec | None` 字段，并加 "use xor action" 互斥校验。
  - 移除 `ApiTemplate / ApiCase / Scenario` 三个层级的 `finally_steps` 字段；validate 在 YAML 中遇到 `finally_steps` 时报明确错误，提示迁移到 `steps[]` + `always_run: true`。
  - 移除 `ApiCase` 的 `before_steps / after_steps` 字段；validate 在 YAML 中遇到 `cases.<id>.before_steps` 或 `cases.<id>.after_steps` 时报明确错误，提示迁移到 `ApiTemplate` 或 `Scenario` 层。
  - `ApiCase` 字段 `api` 重命名为 `use`；validate 在 YAML 中遇到 `cases.<id>.api: ...` 时报明确错误，提示改用 `use:`。
  - `Composer` 合成 hooks 时只在 `ApiTemplate → Scenario` 两层之间组装，不再读取 case 层 hooks。
- `Engine/executor.py` / `pytest_autoapi/`：每轮 dataset 起 `RuntimeContext` 时按"env.variables 拷贝 → dataset.variables 叠加"路径初始化（v0.1 实现已有，此处只是 PRD 锁定后的内核稳定化）。
- `config.yaml` 顶层新增 `datasources`，由 sql action 引用。
- 更新 `examples/p0_minimal/Data` 与 `examples/reading_house/Data` 中至少一个示例，演示：
  - 在 `Scenario.steps[]` 末尾用 `use: case_xxx` + `always_run: true` 表达接口级清理；
  - 在 `Scenario.steps[]` 末尾用 `action: {kind: sql, ...}` + `always_run: true` 表达 SQL 清理。
- 更新 `Tests/`：覆盖 plugin 收集、execute_one 行为、`always_run / continue_on_error` 行为、sql/script action 行为、step `use xor action` 互斥校验、validate 拒绝 `finally_steps`。

Out of scope：

- 不实现 step retry（保留在 P2，由 `pytest-rerunfailures` 接入）。
- 不实现并行执行（保留在 P2，由 `pytest-xdist` 接入）。
- 不实现 OpenAPI 导入、SQLite 历史、严格字段校验、敏感变量脱敏、资产索引、稳定 ID 生成、tag/priority 执行、Web UI（仍属 P2）。
- 不在 plugin 中处理跨机执行、容器化执行、安全沙箱。
- 不修改 PRD §13.1 断言/提取 source。
- 本计划修改 PRD §6 资产模型的字段命名与 hooks 作用域（`ApiCase.before_steps / after_steps` 删除、`cases.<id>.api → use`），与"废弃 finally_steps + 扩展 step inline action"是同一批 schema 收敛动作；不引入其他对 §6 的破坏性变更。

## 3. Progress

- [x] T01 阅读 PRD §6 / §11 / §12，复核 2026-04-26 四条决策（pytest 内核 / sql 升 P1 / always_run / 废弃 finally_steps）；列出本计划的"等价行为锁"（v0.1 的 CLI 输入/输出在 v0.2 必须保持一致的清单），写入 §4 Surprises。
- [x] T02 引入运行时依赖：经核实 `allure-pytest==2.13.5` 与 `pytest==8.4.1` 已在 `requirements.txt` 中；本仓库存在 `pyproject.toml`（仅 `[tool.pytest.ini_options]` 段），Phase B 不再追加。`sqlalchemy` 等 sql / script action 依赖留到 Phase C 再决策。
- [x] T03 抽出纯函数 `execute_one(...)`：在 `Engine/executor.py` 顶部新增模块级 `execute_one(executable, ctx, env, transport, *, resolver, extractor, assert_engine, request_defaults) -> StepResult`；`Executor._execute_executable` 退化为薄壳调用 `execute_one`，`_error_status / _duration_ms` 退化为转发模块级 `_classify_error_status / _perf_to_ms`。`run_case / run_scenario / run_plan` 三个调度方法签名与行为不变（仍负责 hooks / 多 step / dataset 编排，留给 Phase B 切到 pytest 后才会被实际复用）。
- [x] T04 创建 `pytest_autoapi/` 包骨架：`__init__.py` 显式 re-export 6 个 hook，`plugin.py` 实现 `pytest_addoption / pytest_configure / pytest_sessionstart / pytest_collect_file / pytest_collection_modifyitems / pytest_sessionfinish`，`items.py` 实现 `CasesCollector / ScenariosCollector / PlansCollector / AutoApiCaseItem / AutoApiScenarioItem / AutoApiPlanItem` 6 个类。item 内 `runtest()` 调 `Executor.run_case / run_scenario / run_plan`（Phase B 选项 1 粗粒度策略：item 是 case/scenario/plan，dataset 多轮仍由 Executor 内核处理，dataset 信息在 Allure 嵌套 step 名前缀展示）。
- [x] T05 把 Allure 写入切到 `allure-pytest`：`Utils/allure_runtime.py` 删除 `export_run / write_results / _attach_json / _attach_text / _build_test_name / _build_step_name / _map_status / _build_status_details / _build_traceback_text / _to_epoch_ms` 共 10 个方法 + `allure_commons._core / lifecycle / logger / model2` 4 个内部 API import；新增 `generate_html_for_run(run_id, *, results_dir=None, report_dir=None)` 高层入口。`environment.properties / categories.json` 由 `pytest_sessionstart` 直接调 `AllureReporter.write_environment_file / write_categories_file` 写入；testcase 内 `*-result.json` 完全交给 `allure-pytest` 自动生成。`Utils/allure_reporter.py` 因仅依赖 `allure_commons.types.AttachmentType`（公开类型），保持原状。
- [x] T06（合入 plugin sessionfinish 而非新写 hook）：`HistoryWriter().write_run(aggregate_result)` 由 `pytest_sessionfinish` 在聚合 RunResult 后调用一次；字段对照 PRD §14 完全不变（直接复用 v0.1 `HistoryWriter`，未改造类内部）。Phase D 引入 `continue_on_error` 后再决定是否拆为 `pytest_runtest_logreport` 流式写入。
- [x] T07 改造 `run.py`：`run_target` 翻译为进程内 `pytest.main([...])` 调用，预生成 `run_id` 让 `--alluredir` 路径可预测；`_emit_allure_artifacts` 改签名为接受 `Optional[AllureArtifacts]`，从 `pytest_autoapi.plugin.LAST_RUN_ARTIFACTS` 取产物；`_print_run_summary` 不变，敏感字段脱敏行为不变。`validate` 子命令完全不走 pytest，路径不变。
- [x] T08 给 `ScenarioStep` 加 `always_run / continue_on_error` 字段，并加 `action: ActionSpec | None`（与 `use` xor 互斥）；移除 `ApiTemplate / ApiCase / Scenario` 三个层级的 `finally_steps` 字段；validate 遇到 `finally_steps` 时报明确错误。**实际实现走选项 A：调度 always_run / continue_on_error 仍保留在 `Executor._run_scenario_step_list` 内（不下沉到 pytest mark / fixture finalizer），plugin 不需要感知这两个字段；选项 B（plugin mark / fixture）在选项 1 粗粒度策略下不必要——一个 scenario 仍是 1 个 pytest item，调度细节属于 item.runtest() 内部。**
- [x] T08b schema 收敛配套：`ApiCase` 移除 `before_steps / after_steps` 字段；`ApiCase.api` 字段重命名为 `ApiCase.use`；`Composer` 合成 hooks 时不再读取 case 层 hooks。validate 在 YAML 中遇到 `cases.<id>.before_steps / after_steps / api:` 时分别报明确错误并提示迁移路径。`examples/minimal/Data/cases.yaml` 与 `examples/reading_house/Data/cases.yaml` 全部 `api:` 字段改为 `use:`。
- [x] T09 实现 `Engine/action_runner.py` 的 `wait / script` 真实执行入口（`sql` 仍抛 `NotImplementedError` 占位）；`Engine/executor.py` 的 `_execute_action_hook` 退化为薄壳转发；`config.yaml` 顶层 `datasources` 字段不在第一版引入。详见 `docs/decision_log.md` 2026-04-26（修订）"sql action 真实执行延后到 P2"。hooks (`before_steps / after_steps`) 与 `Scenario.steps[]` 的内联 action 共享该入口。
- [x] T10 更新示例资产：`examples/minimal/Data/Scenarios/hanoi_hooks.yaml` 在 before_steps 加一条 hook script 演示，并在 steps 末尾加一条 inline script + always_run + continue_on_error 演示（与原 wait 兜底并存，作为新 schema 的两种清理写法参考）。SQL 清理示例延后到 P2 一并补。
- [x] T11 改造 `Tests/`：单测覆盖 collection、execute_one、always_run / continue_on_error、actions（wait / sql / script）、`step use xor action` 互斥校验、validate 拒绝 `finally_steps`、validate 拒绝 `cases.<id>.before_steps / after_steps`、validate 拒绝 `cases.<id>.api`、上下文叠加初始化（多轮 dataset 不互相污染、env.variables 在每轮可见）。把过期的针对自研 Executor 调度逻辑、finally_steps、case-level hooks、旧 `cases.<id>.api` 字段的测试改写或删除。**Phase D 范围内的项已完成；T09 之后再补 sql/script action 的单测。**
- [x] T12 在 v0.1 验证矩阵上运行所有 Must 命令，逐项复核行为等价；用户在 Windows `.venv` 中确认。`pytest -q` 80 全绿；两个 `validate` 命令资产计数与 v0.1 一致；CLI smoke 主战场切到 `examples/reading_house/Data`（minimal 因无本地 backend 仅做 schema + 调度回归）；`docs/validation_matrix.md §4` 已补 Phase A / E 两节并修订 Phase C / D 过期命令。
- [x] T13 更新 `docs/current_state.md`：把"P0 / P1 状态 / v0.2 切换方向 / v0.2 阶段进展"4 段并存的版本压缩为单段"当前 v0.2 状态：2026-04-26"，新线程读 1 段即掌握全局；过期内容指向 `release_v0.1.md` / `plans/20` / `decision_log.md` / git 历史。`docs/decision_log.md` 已在 Phase B / C 期间同步更新（不在此 task 内重复修改）。
- [x] T14 retrospective：填写第 11 章 Outcomes & Retrospective。

## 4. Surprises & Discoveries

### 2026-04-26 Phase A "等价行为锁"

T01 复核 PRD 后，固化 v0.1 → v0.2 必须保持一致的契约清单（任何 phase 违反都需要在本节记录并升级为决策）：

- **CLI 形态**: `python run.py validate --data <dir>` / `python run.py --case <id>` / `python run.py --scenario <id>` / `python run.py --plan <id>`，可选 `--env`、`--data` 路径；不允许新增/重命名子命令。
- **stdout 字面**: `AutoAPI validate passed.` / 资产计数行 / `allure_results: <path>` / `allure_report: <path>` / `allure_warning: <text>` / 失败时的 `step=...` 摘要，逐字保留（用作 BI / 平台日志解析锚点）。
- **退出码**: 成功 `0`、validate 失败 `1`、运行失败（status != passed）`1`。
- **JSONL 字段**: `Reports/history/runs.jsonl` 与 `results.jsonl` 的字段名 / 顺序完全保持 PRD §14，不允许新增 / 重命名 / 改类型。
- **Allure 目录布局**: `Reports/allure-results/<run_id>/` 存放每次运行的 `*-result.json` + `environment.properties` + `categories.json`；`Reports/allure-report/<run_id>/` 存放 HTML。`run_id` 走 32 位 uuid hex。
- **失败诊断**: 每个失败 step 的 Allure 详情必须含请求快照、响应快照、提取结果、断言逐条结果、上下文快照、异常 traceback 6 类附件，缺一报警。
- **敏感字段**: `config.sensitive_keys` 在 stdout / Allure 附件中需被替换成 `***`，行为与 v0.1 一致。

### 2026-04-26 Phase A 完成事实

- `Engine/executor.py`：新增 `execute_one(executable, ctx, env, transport, *, resolver, extractor, assert_engine, request_defaults) -> StepResult` 与辅助 `_classify_error_status / _perf_to_ms` 三个模块级函数。`Executor._execute_executable` 仅剩 `return execute_one(executable, ...)` 一行薄壳；`_error_status / _duration_ms` 改为转发模块级函数。
- 行为等价验证：用户在 Windows `.venv` 跑 `python -m pytest -q` 全绿（44 个测试），未需要修改任何 `Tests/`，确认重构不破坏 v0.1 行为。
- 限制：`run_case / run_scenario / run_plan` 这三个调度方法**未**退化为薄壳——hooks / dataset / 多 step 编排目前仍在 Executor 类内，等 Phase B 把调度切到 pytest item.runtest() 后才会逐步上移。本计划之前一度写成"三者退化为薄壳"，已更正为只对 `_execute_executable` 适用。

### 2026-04-26 Phase B 设计基线（动手前固化）

经与产品对齐确认，Phase B 锁定 4 条核心决策：

1. **Item 粒度（选项 1：粗粒度）**: 1 个 case / 1 个 scenario / 1 个 plan = 1 个 pytest item。dataset 多轮仍由 Executor 内核处理，dataset 信息进入 Allure 嵌套 step 名前缀（形如 `01. [level_3] 启动任务`）。这样 case / scenario / plan 三个层级的报告条目数量与 v0.1 一致，方便平台对接。
2. **内核复用**: 保留 `Executor.run_case / run_scenario / run_plan` 作为执行内核；pytest 只负责 collection / 调度 / 报告聚合，不重写 step 编排。Phase B 不动 Executor 调度代码。
3. **Allure 切换深度**: 删除 `Utils/allure_runtime.py` 对 `allure_commons` 的全部内部 API 调用（`Lifecycle / model2 / logger / _core`），保留 `AllureReporter.attach_*` 公开 API；`*-result.json` 由 `allure-pytest` 自动产出；`environment.properties / categories.json` 由 plugin sessionstart hook 直接写文件；`Utils/allure_runtime.py` 仅保留 HTML 生成 + 高层入口 `generate_html_for_run`。
4. **CLI 翻译**: `run.py` 用进程内 `pytest.main([...])` 调用，不 spawn 子进程；plugin 通过模块级 holder（`LAST_RUN_RESULT / LAST_RUN_ARTIFACTS / LAST_SENSITIVE_KEYS`）回传结果，`run.py` 用 `from pytest_autoapi import plugin as autoapi_plugin; autoapi_plugin.LAST_RUN_RESULT` 读，避免 from-import 绑死旧值。

数据通道分工（避免功能重叠）：

- **Allure 报告**: 给人看的可视化产物，每次跑都有完整 testcase 详情。
- **JSONL history（HistoryWriter）**: 给机器看的结构化数据，未来平台 / BI 直接读 `runs.jsonl + results.jsonl`，字段稳定不漂移。两者并行写、互不替代。

plugin 内部生命周期：

- `pytest_addoption`: 注册 `--autoapi-data / --autoapi-env / --autoapi-target / --autoapi-run-id`（4 个）。
- `pytest_configure`: 仅当 `--autoapi-data` 给出时启用 AutoAPI 链路（避免污染框架自身单测）。
- `pytest_sessionstart`: 一次性 `YamlRepository.load()` + 构造 `Executor` + 写 `alluredir/environment.properties / categories.json` + 缓存 `sensitive_keys`。
- `pytest_collect_file`: 识别 `cases.yaml / Scenarios/*.yaml / plans.yaml`，分别 yield 三类 collector。
- `pytest_collection_modifyitems`: 按 `--autoapi-target` 过滤 items（kind:id 形式）。
- `pytest_sessionfinish`: 聚合 `RunResult` → 写 history → 生成 HTML → 暴露模块级 holder。

### 2026-04-26 Phase B 完成事实

代码结构落地：

- 新增包 `pytest_autoapi/`（`__init__.py + plugin.py + items.py`）。`__init__.py` 必须显式 re-export 6 个 hook 给 pytest pluginmanager，否则 `-p pytest_autoapi` 无法识别 `pytest_addoption` 等 hook（这是 pytest 插件加载约定，踩坑后才发现）。
- `Utils/allure_runtime.py`：删除 10 个方法 + 4 个 `allure_commons` 内部 import，新增 `generate_html_for_run` 高层入口；只保留 `AllureArtifacts` dataclass 与 HTML 生成路径。
- `Utils/allure_reporter.py`：保持原状（仅依赖 `allure_commons.types.AttachmentType` 公开类型）。
- `Engine/history_writer.py`：保持原状，调用入口由 `Executor.run_*` 改为 plugin `pytest_sessionfinish`。
- `run.py`：`run_target` 改造为 `pytest.main([...])` 翻译层，预生成 `run_id` 后 `--alluredir Reports/allure-results/<run_id>/` 显式传入；从 `pytest_autoapi.plugin` 读 `LAST_RUN_RESULT / LAST_RUN_ARTIFACTS / LAST_SENSITIVE_KEYS`。`_emit_allure_artifacts` 改签名为接收 `Optional[AllureArtifacts]`，输出格式逐字与 v0.1 一致。`validate` 子命令完全不走 pytest。

测试调整：

- `Tests/test_repository.py`：删除 `test_allure_runtime_writes_results_and_support_files`（`AllureRuntimeReporter.export_run` 已删除）；重写 `test_emit_allure_artifacts_prints_paths_and_warning` 直接构造 `AllureArtifacts` 并断言 stdout；新增 `test_allure_runtime_generate_html_for_run_returns_warning_when_results_missing` 覆盖 `results_dir` 缺失分支。
- 新增 `Tests/test_pytest_autoapi.py`（4 个用例）：用 `pytester.runpytest_inprocess` + `--collect-only` 验证 collection 与 `--autoapi-target` 过滤。

验证结果：

- `python -m pytest -q` 全绿，44 → 48 个测试（新增 3 + 1，删除 1，净增 4 个 plugin 用例 - 先前的 1 个 export_run 测试 = 4 个 plugin 测试 + 0 个净增旧测）。
- `python run.py validate --data examples/reading_house/Data` stdout 与 v0.1 完全一致（4 行：`AutoAPI validate passed.` + 3 行资产计数）。
- `python -m pytest -p pytest_autoapi --autoapi-data examples/reading_house/Data --collect-only -q` 收集到 12 个 item（8 cases + 2 scenarios + 2 plans），`--autoapi-target` 过滤后剩 1 个，行为符合预期。资产计数与 `python run.py validate --data examples/reading_house/Data` 输出一致（8 / 2 / 2）。
- `python run.py --case case_book_click_rank_success --data examples/reading_house/Data` 主链路打通：`collected 12 items / 11 deselected / 1 selected` → RunResult 通过 plugin holder 回传 → v0.1 字面 stdout 全部正确（`allure_results: / allure_report: / AutoAPI run finished: error / run_id / target / env / passed / failed / error / first_problem.{case_id,api_id,status,request,response,context,error_code,error_message,error_reason,error_hint}`），敏感字段 `cookies / login_password / auth_token` 全部被替换为 `***`，exit code = 1（status=error 时正确）。本次失败的根因是**用户本机代理 `127.0.0.1:7897` 把 `http://novel.hctestedu.com/book/listClickRank` 上游 502，body 为空导致 JSON 提取失败**，与 v0.2 框架行为无关，属网络层。

发现的事实 / 踩坑：

- 仓库已存在 `pyproject.toml`（仅 `[tool.pytest.ini_options]`），不需要新建；`requirements.txt` 已有 `allure-pytest==2.13.5 / pytest==8.4.1`，无需追加。
- **`pyproject.toml` 的 `testpaths = Tests` 与 v0.2 主链路冲突**：`run.py` 调 `pytest.main([...])` 时若不显式追加 `data_dir` 作为位置参数，pytest 只会扫描 `Tests/` 目录，YAML 资产被全部忽略，导致 `--autoapi-target` 把 48 个内置单测全部 deselect（输出 `48 deselected / 0 selected`）。修复办法：在 `run.py` 的 `pytest_args` 末尾追加 `str(data_dir)`，让命令行 path 覆盖 `testpaths`。`pytester` 测试不会撞这个坑，因为它在 tmpdir 启动 pytest，tmpdir 没有 `pyproject.toml`，所以本地单测全绿不能保证 CLI 主链路工作——这是单测覆盖盲点，需在交付清单里手动跑 `python run.py --case ...` 验证。
- `pytester.runpytest_inprocess` 默认 cwd 是 tmpdir，必须显式 `pytester.syspathinsert(PROJECT_ROOT)` + 把 `examples/reading_house/Data` 作为最后一个位置参数传入，否则 pytest 不会扫描到 YAML 资产文件。
- pytest item 的 `nodeid` 形如 `examples/reading_house/Data/cases.yaml::case_xxx`，与 `reportinfo()` 显示的 `case::xxx` 是两套字符串；测试断言要直接断 `case_id` 子串而不是 `case::case_id`。
- plugin 模块级 holder（`LAST_RUN_RESULT` 等）只能用 `from pytest_autoapi import plugin; plugin.LAST_RUN_RESULT` 访问；`from pytest_autoapi.plugin import LAST_RUN_RESULT` 会绑死到导入瞬间的 None。已在 `pytest_autoapi/plugin.py` 顶部 docstring 显式标注。

Phase B 取舍记录：

- **未做**: `pytest_runtest_logreport` 流式写 history（暂时仅 `pytest_sessionfinish` 一次性写 run 行）。Phase D 引入 `continue_on_error` 后再决定是否拆。
- **未做**: 把 Executor 调度方法（`run_case / run_scenario / run_plan`）退化为薄壳。Phase B 选项 1 粗粒度策略下 plugin 复用 Executor，调度逻辑保留在 Executor 类内。
- **保留**: `HistoryWriter` 不变，给 BI / 平台留稳定数据通道；`AllureReporter` 公开 attach API 不变，给 Allure 报告留可视化通道。两条数据通道并行。

### 2026-04-26 Phase D 完成事实

schema 收敛 + `always_run / continue_on_error` + use↔action XOR 全部落地。`Scenario.finally_steps` / `ApiCase.before_steps / after_steps` / `cases.<id>.api` 四类字段在 v0.2 一刀切删除，YAML 命中即报错并附迁移提示。

代码层落地：

- `Schema/data_models.py`：`ApiCase` 删 `api / before_steps / after_steps`、加必填 `use`；`Scenario` 删 `finally_steps`；`ScenarioStep.use` 改为 `Optional[str] = None`，新增 `action: Optional[Dict] = None`、`always_run: bool = False`、`continue_on_error: bool = False`。
- `Core/repository.py`：`_load_cases` 新增 `_reject_deprecated_case_fields(case_id, body)`，命中 `api / before_steps / after_steps` 直接抛 `ValidationException` 并附迁移提示；`_load_one_scenario` 新增 `finally_steps` 字段拦截；`_load_scenario_step_list` 新增 `_validate_step_use_action_xor`，在加载阶段就拦截"两个都填 / 一个都没填"两种非法情况，避免 Composer / Executor 拿到歧义 step。
- `Schema/data_validation.py`：`_validate_references` 改用 `case.use`；`_validate_scenario_step_list` 兼容 use 路径与 action 路径分支，新增 `_validate_inline_action` 校验内联 action 的 `kind / seconds`；删除 case 层 hooks / scenario.finally_steps 校验；`_validate_shared_rule_refs` 跳过 action 类 step。
- `Core/composer.py`：`compose_case` 不再读 case 层 hooks，hooks 仅来自 `ApiTemplate.before_steps / after_steps`（PRD §6 决策 1）；删除 `_compose_case_hooks` 私有方法。
- `Engine/executor.py`：`_run_scenario_iteration` 删除 `finally_steps` 调度，新增 `preceded_by_failure` 透传；`_run_scenario_step_list` 引入 `halted_by_failure` 状态，按"普通 step 截停 + always_run 永跑 + continue_on_error 不截停"三条规则调度；新增 `_execute_scenario_step` 把 `step.use` / `step.action` 两条路径分发到 `_execute_executable_with_hooks` 与 `_execute_action_hook` 同一份内核（清理 case 与清理 SQL 等价）。
- `pytest_autoapi/items.py`：`AutoApiCaseItem.runtest` 把 `case.api` 改成 `case.use`，与 schema 收敛同步。
- `examples/minimal/Data/cases.yaml` + `examples/reading_house/Data/cases.yaml`：19 + 8 = 27 行 `api:` 全部改成 `use:`。
- `examples/minimal/Data/Scenarios/hanoi_hooks.yaml`：原 `finally_steps[兜底等待]` 迁移为 `Scenario.steps[]` 末尾的 `action: {kind: wait, seconds: 0}` + `always_run: true`，作为新 schema 的"无论成败都跑的清理"参考写法。

测试调整：

- `Tests/test_repository.py`：5 个旧测改写——`test_executor_run_case_executes_template_and_case_wait_hooks` 改名为 `_template_wait_hooks_only`（删 case 层 hooks 注入）；`test_executor_run_scenario_with_hooks_and_finally` 改名为 `_with_hooks_and_inline_action_cleanup`（兜底等待迁到 always_run inline action）；`_finally_steps_even_when_main_failed` 改为 `_always_run_step_runs_even_when_main_failed`；`_assertions_fail_still_runs_finally` 改为 `_assertions_fail_after_always_run_cleanup`（执行顺序变成 main → always_run → after → assertions，与 v0.2 一致）；`_hooks_with_datasets_keep_dataset_dimensions` 用 `scenario.steps.append(ScenarioStep(action=..., always_run=True))` 替换原本的 `scenario.finally_steps = [...]` 注入。
- `Tests/test_step_policy.py`（新文件，11 个用例）：覆盖旧字段拒绝（4 项：`cases.<id>.api / before_steps`、`scenarios.<id>.finally_steps`）、use↔action XOR 互斥（同填 / 缺一）、always_run 行为、continue_on_error 行为、inline action(wait) 走 hook 同一内核、inline action(sql) 走"暂未实现"分支、context overlay（多轮 dataset 不互相污染、env.variables 每轮可见）、validate 通过 examples/minimal 自洽自检。新建 `_write_minimal_repo(tmp_path, cases_yaml=..., hooks_yaml=...)` helper 复制 `examples/minimal/Data` 到 tmpdir 并局部改 YAML。

验证结果：

- `python -m pytest -q` 全绿，48 → 59（新增 11 个 step policy 用例）。无 lint 报错。
- `python run.py validate --data examples/minimal/Data` → `apis: 10 / cases: 19 / scenarios: 3 / plans: 1`，stdout 与 v0.1 完全一致。
- `python run.py validate --data examples/reading_house/Data` → `apis: 8 / cases: 8 / scenarios: 2 / plans: 2`，与 Phase B 一致。
- `python run.py --scenario scn_hanoi_hooks_flow --data examples/minimal/Data` 端到端走通：collected 23 items / 1 selected / before_steps 等待服务稳定 passed → 启动任务 error（本地 `127.0.0.1:1806` 无服务） → 上传任务数据 / 停止任务被截停（halted_by_failure） → 兜底等待 always_run inline action passed → stdout `passed: 2, failed: 0, error: 1` 与新调度规则相符，敏感字段 `auth_token / basic_password` 全部脱敏为 `***`。**这是 always_run 在 CLI 端的端到端证据：主流程失败但兜底动作仍执行。**

发现的事实 / 踩坑：

- ScenarioStep `use` 改为 `Optional[str]` 时必须同时把 dataclass 默认值改成 `None`，否则会破坏现有 `ScenarioStep(id=..., use=...)` 调用方。已在 `Tests/test_repository.py` 旧测里看到一处 `ScenarioStep(id="raw-js-override", use="case_raw_javascript_payload", override={...})` 形式，仍然兼容（因为 use 是第二个位置参数 + Optional）。
- `compose_step` 内部 `EMPTY_BY_FIELD` 字段表保留 `before_steps / after_steps` 不变——ScenarioStep.override 仍然可以覆写 ExecutableCase 上从 ApiTemplate 继承下来的 hooks，行为与 v0.1 一致。这一点不被 schema 收敛影响。
- inline action step 走 `_execute_action_hook` 时 `executable=None` → `case_id / api_id` 自动 fallback 为 `"action"`（与 hook 风格一致），plugin 端的 history / Allure 不需要额外分支。
- `pytest_autoapi/plugin.py` / `pytest_autoapi/items.py` 不感知 `always_run / continue_on_error / action`：选项 1 粗粒度策略下，调度细节完全在 `Executor.run_scenario` 内部。这是 PD 设计层取舍——选项 B（pytest mark / fixture finalizer）会让 scenario 拆成 N 个 pytest item，与 v0.1 报告条目数对不齐，与"等价行为锁"冲突。

Phase D 取舍记录：

- **未做**: `pytest_runtest_logreport` 流式写 history（暂时仍 `pytest_sessionfinish` 一次性写 run 行）。`continue_on_error` 在选项 1 粗粒度策略下不需要 per-step 流式写——所有 step 都在 1 个 pytest item 内执行，aggregate 后写 history 即可。
- **未做**: pytest mark `always_run / continue_on_error`。同上，选项 1 下不必要。
- **保留**: `_execute_action_hook` 仍负责 sql / script 的 NotImplementedError 分支——Phase C 实现真实 SQL/脚本时只改这一个函数，inline action step 与 hooks 自动同步获得新能力。

### 2026-04-26 Phase C 完成事实

Phase C 落地 wait + script 真实执行；sql 按"修订"决策延后到 P2；actions 模块归内核包，Engine 单向 import。

代码层落地：

- `Engine/action_runner.py`（**新文件**）：模块级 `run_action(action, ctx) -> ActionOutcome` 主入口 + `_run_wait / _run_script / _resolve_script_args` 三个内部函数。`ActionOutcome` dataclass 只编码 `passed/failed` 业务语义，`error/extract_out` 字段透传给 Executor 组装 StepResult。失败语义两层：业务期望不符（script returncode 不匹配 expect_returncode）→ ActionOutcome(status="failed", error=AssertionError(...)) 落到 StepResult.status="failed"；环境/资源/未实现错误（FileNotFoundError / TimeoutExpired / NotImplementedError 等）→ 直接抛异常给 Executor，由 `_classify_error_status` 归类为 "error"。
- `Engine/executor.py`：`_execute_action_hook` 退化为薄壳，调用 `run_action(...)` 后按 ActionOutcome.status / error / extract_out 三个字段组装 StepResult；wait/sql/script 三类分支整体下沉到 action_runner。删除原 `if kind == "wait": time.sleep` / `elif kind in {"sql", "script"}: raise NotImplementedError` 分支共 6 行业务代码。新增 `from Engine.action_runner import ActionOutcome, run_action` 一行 import。
- `Schema/data_validation.py`：`_validate_inline_action` 重构为转发到新公开函数 `_validate_action_schema(action, *, yaml_location, owner)`（hooks 与 inline action 共用同一份校验，错误前缀按 `owner` 区分）。新增 `_validate_script_action(action, *, yaml_location, owner)` 校验 `command / expect_returncode / timeout / cwd / env / extract` 六个字段，命中错误时给出明确 reason + yaml_location。`_validate_hook_step_list` 改为统一调用 `_validate_action_schema`，删除 hook 与 inline action 各一份重复校验代码。
- `examples/minimal/Data/Scenarios/hanoi_hooks.yaml`：`before_steps` 末尾新增"打印 hook 启动标记"hook script（list-form `[python, -c, "print('hook before_steps ok')"]`）；`steps` 末尾在原 wait 兜底之后追加"兜底脚本清理"inline script，演示 `extract: [{source: stdout, as: cleanup_stdout}, {source: returncode, as: cleanup_rc}]` + `always_run: true` + `continue_on_error: true` 完整组合。两个示例都用 list-form command 跨平台兼容。

测试调整：

- `Tests/test_actions.py`（**新文件，21 个用例**）：分四组覆盖：
  - **action_runner.run_action - wait**（2 个）：0 秒成功 / 负数 ValueError。
  - **action_runner.run_action - script 行为**（5 个）：returncode 0 默认成功 / returncode 非 0 默认 failed + AssertionError + "returncode=2" 错误文案 / 显式 `expect_returncode=2` 匹配 / `expect_returncode=any` 跳过校验 / `command: str` 形态 shlex.split 走通。
  - **action_runner.run_action - script extract**（2 个）：source=stdout 写回 ctx / source=stderr+returncode 多 source 同时写回 ctx。
  - **action_runner.run_action - 输入校验**（4 个）：command 空 / extract.source 不合法 / expect_returncode 类型错误 / unknown kind。
  - **action_runner.run_action - sql 仍未实现**（1 个）：保留 Phase D 决策"sql 走 NotImplementedError"的回归锁。
  - **Schema validation**（4 个）：command 缺失 / expect_returncode 错误类型 `"maybe"` / extract.source 非法 `"result"` / examples/minimal 自身 hooks YAML 仍能 load 通过。
  - **Executor 端到端调度**（2 个）：hook script 退出码非 0 截停主流程但 inline always_run 仍执行 / 主 step 失败后 inline script always_run 仍执行并把 stdout 写回 ctx 供后续读取。

- 其它测试不动：`Tests/test_step_policy.py` 的 `test_executor_inline_action_sql_returns_not_implemented_error` 仍然有效——sql 走 NotImplementedError → status="error"，与 Phase C 锁齐。

验证结果：

- **action_runner sanity**: 在 Cursor 终端用 `python` 直接 import action_runner 跑 9 条主路径（wait 0s / script returncode 0 / script returncode 2 default / script returncode 2 expect 2 / script returncode 5 expect any / script extract 三 source / sql NotImplementedError / command 空 / unknown kind），全部 assertion 通过。这条 sanity 是无 pytest 环境下的"代码可运行"证明。
- **shlex 跨平台 sanity**（第一次回归后补做）: 在 Cursor 终端用 `python` 直接调 `run_action({command: list, ...})` 与 `run_action({command: 'forward-slash quoted str', ...})` 两条路径，Windows 下双双 passed。验证 `posix=True` 在正斜杠路径上跨平台一致。
- **pytest 全量回归（2026-04-26 用户反馈）**: 第一次跑 `python -m pytest -q` 报 4 failed / 75 passed：
  - `test_run_action_script_command_str_form_uses_shlex_split` — 上面 shlex 反斜杠引号坑，已通过统一 `posix=True` + 测试改用正斜杠路径修复。
  - `test_executor_run_scenario_with_hooks_and_inline_action_cleanup / always_run_step_runs_even_when_main_failed / assertions_fail_after_always_run_cleanup` — 三条断言写死了旧 step ID 列表，与 Phase C 新加进 `examples/minimal/Data/Scenarios/hanoi_hooks.yaml` 的 hook script "打印 hook 启动标记" + inline script "兜底脚本清理" 不一致。已在 `Tests/test_repository.py` 把 step ID 列表 + 状态列表 + assertions step 索引整体对齐到 9 个 step 的新顺序，并补了 `result.steps[1].extract_out["action"]["kind"] == "script"` 与 cleanup_stdout 写回 ctx 的回归断言。
- **修复后预期**: 80 个用例全绿（v0.1 44 + Phase B plugin 4 + Phase D step policy 11 + Phase C 21）。
- **CLI smoke 路径调整**（用户产品偏好，2026-04-26）: `examples/minimal` 没有真实可联通的 backend，CLI 端到端 smoke 走该 example 时主流程 step 必然 error，只能用于断言"调度链路顺序正确"。今后 `python run.py --scenario / --case / --plan` 的 smoke 演示统一切到 `examples/reading_house/Data`（本地有真实读书屋 API），minimal 仅留作"YAML schema 与调度顺序"的最小回归。

发现的事实 / 踩坑：

- `_classify_error_status` 区分 "failed" 与 "error" 完全靠 `getattr(exc, 'error_context', None).error_code == ASSERT_ERROR`。普通 `AssertionError` 没有 `error_context` 属性，会被归类为 "error"——这与"业务期望不符 → failed"的直觉不符。**Phase C 解决办法**：让 action_runner 不抛 `AssertionError`，改为返回 `ActionOutcome(status="failed", error=AssertionError(...))`，由 Executor 直接采用 ActionOutcome.status 而不走 `_classify_error_status`。这条决策保证 script returncode 不匹配时正确归类为 "failed"，FileNotFoundError / TimeoutExpired 仍走 `_classify_error_status` 归类为 "error"。
- subprocess 在 Windows 上对 `command: str` 形态的 shlex 模式选择踩过坑：第一版用 `shlex.split(command, posix=os.name != 'nt')`（Windows posix=False）。`posix=False` 会把外层引号当字面量保留，subprocess 拿到 `['"C:\\Python\\python.exe"', '-c', '"print(1)"']` 后报 `FileNotFoundError [WinError 2]`。**修订**：统一用 `posix=True`，`command: str` 形态在 Windows 下要求路径用正斜杠（如 `"C:/Python/python.exe"`），或直接改用 list-form。docstring 已明确"Windows 强烈建议 list 形态"。
- `RuntimeContext.set` / `get` 不区分 None 与缺失，extract 写回时如果 stdout 为空字符串，`ctx.get('s_out')` 返回 `''` 而不是 `None`，单测里要用 `.strip()` 过滤换行符再断言文本。

Phase C 取舍记录：

- **未做（按修订决策）**: `action.kind=sql` 真实执行（延后到 P2，目标方言 PostgreSQL）；`config.yaml` 顶层 `datasources` schema（与 sql 真实执行一并放 P2 引入）。
- **未做**: script 沙箱 / 跨机执行 / 容器化执行（PRD §12 已锁定 P1 不做沙箱）。
- **未做**: script 命令变量渲染（如 `command: ["python", "-c", "${cleanup_script}"]` 替换 ctx 变量）。第一版 command 直接传给 subprocess 不走 render_any，避免 shell 注入风险。如果业务侧需要变量化清理脚本，下一版再决策（可能需要白名单）。
- **保留**: subprocess.run 默认 `check=False`，不让命令失败抛 `CalledProcessError` 干扰 ActionOutcome 的状态归类；让 expect_returncode 校验流程独占判定权。

## 5. Decision Log

本计划执行期间产生的新决策都写在这里，重要决策同步到 `docs/decision_log.md`。

初始决策（沿用 2026-04-26 主决策）：

- 切换为 pytest 内核 + `allure-pytest`。
- sql / script action 升 P1 必做。
- `always_run / continue_on_error` 提前到 P1。
- 废弃 `finally_steps`（三层 hooks 全删），扩展 `Scenario.steps[]` 形态为 `use` xor `action`，所有清理统一通过 `steps[]` 末尾 + `always_run: true` 表达。
- 删除 `ApiCase.before_steps / after_steps`：hooks 只保留 `ApiTemplate`（接口默认）和 `Scenario`（场景前置后置）两层。详见 `docs/decision_log.md` 2026-04-26 "删除 ApiCase 的 before_steps / after_steps" 决策。
- YAML 引用字段统一为 `use:`：`cases.<id>.api` 重命名为 `cases.<id>.use`，与 `scenarios.steps[].use` 风格统一。详见 `docs/decision_log.md` 2026-04-26 "YAML 引用字段统一为 use" 决策。
- 场景执行的上下文初始化采用"叠加"语义：每轮 dataset 起 `RuntimeContext` 时按 env.variables → dataset.variables → 运行时 extract 三层叠加。详见 `docs/decision_log.md` 2026-04-26 "场景执行的上下文初始化采用叠加语义" 决策。

待本计划开工前再决策的事项：

- sql action 第一版具体使用 `sqlalchemy` 还是 `sqlite3 + pymysql`，按当前主要使用场景决定。
- script action 是否限定只调用 Python 入口，还是允许任意 shell 命令；第一版倾向"只允许显式声明的入口"，避免 hooks 被滥用。
- pytest item 的 nodeid 具体格式（建议 `<scenario_id>::[dataset]::<step_id>` / `<plan_id>::<scenario_id>` / `<case_id>`）。

## 6. Context and Orientation

需要改造的代码：

- `Engine/executor.py`：抽出 `execute_one(...)`，移除自研调度方法。
- `Utils/allure_runtime.py`、`Utils/allure_reporter.py`：替换 `allure_commons` 内部 API 调用为 `allure-pytest`。
- `Engine/history_writer.py`：写入入口由"runtime 层主动调用"改为"pytest hook 被动监听"。
- `run.py`：CLI 参数翻译为 `pytest.main(...)`。
- `Schema/data_models.py` / `Schema/data_validation.py`：`ScenarioStep` 加字段。

新增代码：

- `pytest_autoapi/__init__.py`
- `pytest_autoapi/plugin.py`
- `pytest_autoapi/items.py`
- `pytest_autoapi/actions.py`

需要保留的领域内核（不动）：

- `Schema/data_models.py`（仅追加字段）
- `Core/repository.py` / `Core/composer.py` / `Core/context.py`
- `Engine/host_resolver.py` / `Engine/request_resolver.py` / `Engine/transport.py` / `Engine/extractor.py` / `Engine/assertion_engine.py` / `Engine/jsonpath_tool.py`
- `Utils/yaml_io.py`

需要观察的下游：

- `Tests/conftest.py` 当前还会做一些 P0 级别的 fixture 注册；要确认与 plugin 不冲突，必要时把项目内部测试与 `pytest_autoapi` 的注册路径区分清楚。

## 7. Plan of Work

切换分四个 phase，每个 phase 单独可验证、单独可回滚。每个 phase 开始前，确认上一个 phase 的 Must 验证已经通过。

### Phase A：等价行为锁（T01–T03）

- 不改业务行为，先把 `Engine/executor.py` 的调度逻辑解耦：抽出 `execute_one(...)` 纯函数，使现有 `run_case / run_scenario / run_plan` 退化为调用 `execute_one` 的薄壳。
- 现有 v0.1 验证矩阵（`docs/validation_matrix.md` §3）保持全绿；CLI 行为完全不变。
- 这一步本质是为 Phase B 做准备：让 pytest item 直接复用 `execute_one(...)`。

### Phase B：插件骨架 + Allure 标准化（T04–T07）

- 创建 `pytest_autoapi/` 插件包；实现 collection 与 item 调度。
- Allure 切到 `allure-pytest`；移除 `AllureRuntimeReporter` 中对 `allure_commons` 内部 API 的直接调用。
- `Engine/history_writer.py` 改成 hook 驱动。
- `run.py` 内部翻译为 `pytest.main(...)`。
- 完成后用户 CLI 行为不变，但内核已经是 pytest。

### Phase C：script action 落地 + sql 占位（T09 + 部分 T10/T11）

- 实现 `Engine/action_runner.py` 中的 `wait / script`（默认 `expect_returncode=0`）。
- `Engine/executor.py` 的 `_execute_action_hook` 退化为薄壳转发；hooks 与 inline action 行为同源。
- `config.yaml` 不引入 `datasources` 字段（与 PostgreSQL 真实落地一并放 P2）。
- 给 `examples/minimal/Data` 加一条 script 清理演示（hook 与 inline action 各一例）。
- `Tests/test_actions.py` 覆盖 `expect_returncode` 默认 / 显式 / `any` 三条路径与 extract 行为。
- 完成后用户可以在 hooks 与 `Scenario.steps[]` 中真实跑脚本清理；SQL 清理仍由 `NotImplementedError` 显式占位，不会被静默通过。

### Phase D：always_run / continue_on_error + schema 收敛（T08 + T08b + 剩余 T10/T11）

- `ScenarioStep` 加 `always_run / continue_on_error / action` 字段；plugin 在 collection 阶段读取 `always_run / continue_on_error` 并映射 marker；validator 加 `use xor action` 互斥校验。
- 移除 `ApiTemplate / ApiCase / Scenario` 三个层级的 `finally_steps` 字段；validate 遇到 `finally_steps` 时报明确错误。
- 移除 `ApiCase.before_steps / after_steps` 字段；validate 遇到 `cases.<id>.before_steps / after_steps` 时报明确错误。
- `ApiCase.api` 字段重命名为 `ApiCase.use`；validate 遇到 `cases.<id>.api: ...` 时报明确错误。
- `examples/p0_minimal/Data/cases.yaml` 与 `examples/reading_house/Data/cases.yaml` 中的 `api:` 字段全部改为 `use:`。
- 给示例补：`Scenario.steps[]` 末尾的 `use + always_run`（接口清理）与 `action + always_run`（SQL 清理）两种写法。
- 完成后所有清理动作通过 `steps[]` + `always_run: true` 统一表达，hooks 只剩 `before_steps / after_steps` 两件套，且只在 ApiTemplate 与 Scenario 两层；YAML 引用字段统一为 `use:`。

### Phase E：收口（T12–T14）

- 跑全部 Must 命令；用户人工确认。——**已确认**（`pytest` 80 全绿 + `validate` 两目录 + reading_house 补 script 后无 schema 回退）。
- 同步 `docs/current_state.md` 与 `docs/decision_log.md`。
- 填 retrospective。

## 8. Concrete Steps

工作目录：

```bash
D:\GitHubRepository\Interface-auto\AutoAPI
```

预计修改文件：

- `Engine/executor.py`
- `Engine/history_writer.py`
- `Schema/data_models.py`
- `Schema/data_validation.py`
- `Utils/allure_runtime.py`
- `Utils/allure_reporter.py`
- `run.py`
- `requirements.txt`
- `pyproject.toml`
- `Tests/conftest.py`
- `Tests/test_repository.py`（按需调整）
- `examples/p0_minimal/Data/` 与/或 `examples/reading_house/Data/` 至少一个示例
- `docs/current_state.md`
- `docs/decision_log.md`（按需追加）

预计新增文件：

- `pytest_autoapi/__init__.py`
- `pytest_autoapi/plugin.py`
- `pytest_autoapi/items.py`
- `pytest_autoapi/actions.py`
- `Tests/test_actions.py`
- `Tests/test_step_policy.py`
- `Tests/test_pytest_autoapi_collection.py`

预计命令：

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m pytest -q --alluredir Reports/allure-results/<run_id>
allure generate Reports/allure-results/<run_id> -o Reports/allure-report/<run_id> --clean
python run.py validate --data examples/p0_minimal/Data
python run.py validate --data examples/reading_house/Data
python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --plan plan_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_auth_flow --env test --data examples/reading_house/Data
```

如果 WSL 中 `python` 不可用，由用户在 Windows `.venv` 中运行并回传结果。

## 9. Validation and Acceptance

按 phase 验收，避免一次性大爆炸。

### Phase A

- v0.1 验证矩阵 §3 的 Must 命令全绿。
- `Engine/executor.py` 中 `run_case / run_scenario / run_plan` 退化为薄壳，业务逻辑都在 `execute_one(...)`。
- 现有 `Tests/test_repository.py` 不需要修改即可通过。

### Phase B

- `python -m pytest -q` 全绿。
- `python -m pytest -q --alluredir <dir>` + `allure generate` 能产出标准 HTML，testcase 的 historyId / fullName / start / stop 都由 `allure-pytest` 标准产出。
- `python run.py --case ... / --scenario ... / --plan ...` CLI 输出与 v0.1 等价（路径、退出码、JSONL 字段）。
- `Utils/allure_runtime.py` 不再 import `allure_commons` 的内部模块。

### Phase C

- `Tests/test_actions.py` 全绿。
- `python run.py --scenario <带 sql 清理的场景> --env test --data <fixture_data>` 能在 `Scenario.steps[]` 末尾的 `action: {kind: sql, ...}` + `always_run: true` 中执行 SQL 并写回 ctx（场景失败路径下仍执行）。
- `config.yaml` 中 `datasources` 配置错误时报错明确。

### Phase D

- `Tests/test_step_policy.py` 全绿。
- 无标记的 step 仍然"失败即停止"。
- 标 `always_run: true` 的 step 在前序失败时仍执行；标 `continue_on_error: true` 的 step 失败后 scenario 继续。
- step 字段 `use` 与 `action` 互斥；同时填或都不填都被 validate 拒绝。
- YAML 中如果还出现 `finally_steps`（任何层级），validate 报明确错误并提示迁移路径。
- YAML 中如果出现 `cases.<id>.before_steps` 或 `cases.<id>.after_steps`，validate 报明确错误并提示迁移路径（迁到 ApiTemplate 或 Scenario 层）。
- YAML 中如果出现 `cases.<id>.api: ...`，validate 报明确错误并提示改用 `use:`；改名后能正常加载并跑通现有用例链。
- `Tests/` 中"上下文叠加初始化"的负向 / 正向用例全绿：env.variables 在每轮 dataset 内仍然可见；dataset.variables 同名 key 覆盖 env.variables；多轮 dataset 互不污染（第二轮看不到第一轮 extract 的变量）。
- 示例 YAML 演示两种清理写法：`use + always_run`（接口清理）与 `action + always_run`（SQL 清理）。

### Phase E

- v0.2 验证矩阵（`docs/validation_matrix.md` §4）的 Must 全绿。
- `docs/current_state.md` "当前 v0.2 状态" 章节存在，且与实际行为一致。
- 本计划 Outcomes & Retrospective 已填写。

## 10. Idempotence and Recovery

- Phase A 与 Phase B 是最高风险的两步。Phase A 只动 `Engine/executor.py` 内部结构，可以通过 git revert 回滚。Phase B 引入新依赖与 plugin，回滚需要：撤销 plugin 注册、恢复 `Utils/allure_runtime.py`、恢复 `Engine/history_writer.py` 的主动调用入口；建议 Phase B 在独立分支上完成并人工对比 CLI 输出。
- Phase C 与 Phase D 都是"加字段、加分支"的扩展型改动，回滚成本低。
- 任何 phase 完成后产生的 `Reports/allure-results/<run_id>/` 与 `Reports/history/*.jsonl` 都可以删除重建，不影响主代码。
- 任何 phase 中如发现 PRD §6 / §13.1 受影响（理论上不应该），必须先把 PRD 与本计划同步更新，再继续实现。

## 11. Outcomes & Retrospective

### 交付事实（2026-04-26）

| Phase | 完成日期 | 用户验收 | 关键产出 |
|---|---|---|---|
| A | 2026-04-26 | "ok，人工验证通过" | `Engine/executor.execute_one(...)` 模块级纯函数；`Executor._execute_executable` 退薄壳；44 v0.1 单测零修改全绿（行为等价硬证据） |
| B | 2026-04-26 | "可以，B2 保留。粒度选 1" + "ok，人工验证通过" | `pytest_autoapi/` 插件包（plugin/items/__init__）；`Utils/allure_runtime.py` 删除 10 个方法 + 4 个 `allure_commons` 内部 import；`run.py` 翻译为进程内 `pytest.main([...])`；CLI 字面输出与 v0.1 一致 |
| D | 2026-04-26 | "可以，开干吧" | schema 一刀切：删 `ApiCase.api / before_steps / after_steps`、`Scenario.finally_steps`；新增 `ScenarioStep.use ⊕ action / always_run / continue_on_error`；hooks 二层化；上下文叠加初始化锁定 |
| C | 2026-04-26 | "人工验证通过" | `Engine/action_runner.py`（wait + script 真实执行；sql 占位 NotImplementedError）；`_execute_action_hook` 退薄壳；script schema 校验；hanoi_hooks.yaml 加 hook script + inline script 完整演示 |
| E | 2026-04-26 | 用户已确认"验证通过" | `docs/validation_matrix.md §4` 补 Phase A / E 节并修订 C / D 过期命令；`docs/current_state.md` 压缩为单段 v0.2 状态；§11 retrospective；reading_house 示例补 script 演示；终局复核 `pytest` 80 + `validate` 两目录 |

`pytest -q` 终态：80 passed（44 v0.1 + 4 plugin + 11 step policy + 21 action_runner / schema / executor 端到端）。`validate --data examples/{minimal,reading_house}/Data` 资产计数与 v0.1 完全一致。

### 决策修订记录（与初版计划差异）

执行过程中相对计划 §2 / §5 初版产生的修订，每一条都已同步到 `docs/decision_log.md` 或本计划其它章节：

1. **Phase A "三薄壳"过度设计修订**：初版把"`run_case / run_scenario / run_plan` 退化为薄壳"写进 §1 与 §3 T03。实际只对 `_execute_executable` 适用——hooks / dataset / 多 step 编排留在 Executor 内（选项 1 粗粒度策略下，这是 pytest item.runtest() 的内部实现）。已在 §4 "2026-04-26 Phase A 完成事实" 段更正。
2. **Phase B Item 粒度（动手前固化）**：选项 1 粗粒度（1 case = 1 item / 1 scenario = 1 item / 1 plan = 1 item），dataset 多轮仍由 Executor 内核处理，dataset 信息进入 Allure 嵌套 step 名前缀。本来还在评估选项 2 细粒度（1 step = 1 item），用户明确"粒度选 1"后立即锁定。
3. **Phase B HistoryWriter 保留**：`HistoryWriter.write_run(result)` 自定义 JSONL 输出原计划可能拆为 `pytest_runtest_logreport` 流式写入，实际改为复用 v0.1 类，由 `pytest_sessionfinish` 在聚合 RunResult 后调用一次。Phase D 引入 `continue_on_error` 后亦未拆分，保持简单。
4. **Phase C sql 范围降级（用户产品决策）**：初版 §1 / §2 把 `action.kind=sql` 真实执行写入 P1 Must；实际用户偏好 PostgreSQL，与第一版 sqlite3 / sqlalchemy 候选不匹配。修订为：sql 真实执行延后到 P2，目标方言锁定 PostgreSQL；第一版仅落 wait + script；`config.yaml` 顶层 `datasources` 字段一并延后。详见 `docs/decision_log.md` 2026-04-26（修订）"sql action 真实执行延后到 P2"。
5. **Phase C actions 模块归属**：初版 §2 / §3 T09 写在 `pytest_autoapi/actions.py`。实际改为 `Engine/action_runner.py`，归内核包，与 `pytest_autoapi/` 解耦。Engine 单向 import，未来如果脱离 pytest 用别的 runner，actions 仍可复用。
6. **Phase C script 失败语义锁定**：初版未明确 `expect_returncode` 缺省值；用户决策为"默认 `expect_returncode=0`，非 0 自动 failed（推荐）"。`expect_returncode: any` 跳过校验。详见 `docs/decision_log.md` 2026-04-26 "script action 默认 expect_returncode=0"。
7. **Phase C `_classify_error_status` 不能直接区分 failed / error**：实现时发现普通 `AssertionError` 没有 `error_context` 属性，会被归类为 "error"，这与"业务期望不符 → failed"的直觉不符。解决方案：让 `action_runner.run_action` 不抛 `AssertionError`，而是返回 `ActionOutcome(status="failed", error=AssertionError(...))`，由 Executor 直接采用 `ActionOutcome.status` 而不走 `_classify_error_status`。这条决策保证 script returncode 不匹配时正确归类为 "failed"，FileNotFoundError / TimeoutExpired / NotImplementedError 仍走 `_classify_error_status` 归类为 "error"。
8. **CLI smoke 主战场迁移（用户产品偏好）**：用户在 Phase C 验收期间明确"以后你用接口使用读书屋的接口"。原因：`examples/minimal` 没有真实可联通的 backend，CLI 端到端 smoke 走该 example 时主流程 step 必然 error。**修订**：今后 `python run.py --scenario / --case / --plan` 的真实联通 smoke 统一切到 `examples/reading_house/Data`；minimal 仅留作"YAML schema + 调度顺序"最小回归。已在 `docs/validation_matrix.md §4 Phase E Should` + `docs/current_state.md` "CLI smoke 主战场说明" + `examples/reading_house/Data/Scenarios/` 补 script 演示三处同步。

### 踩坑事实（按 phase 时间线）

Phase B：

- **`pyproject.toml` 的 `testpaths = Tests` 与 v0.2 主链路冲突**：`run.py` 调 `pytest.main([...])` 时若不显式追加 `data_dir` 作为位置参数，pytest 只扫 `Tests/`，YAML 资产被忽略，`--autoapi-target` 把 48 个内置单测全部 deselect。修复：在 `pytest_args` 末尾追加 `str(data_dir)`，让命令行 path 覆盖 `testpaths`。本地单测全绿不能保证 CLI 主链路可用——这是单测覆盖盲点，需要在交付清单里手动跑 `python run.py --case ...` 验证。
- **plugin 模块级 holder 必须用 module 引用而不是 from-import**：`from pytest_autoapi import plugin; plugin.LAST_RUN_RESULT` 才能拿到 sessionfinish 写入的值；`from pytest_autoapi.plugin import LAST_RUN_RESULT` 会绑死到导入瞬间的 None。已在 `pytest_autoapi/plugin.py` 顶部 docstring 显式标注。
- **`pytest_autoapi/__init__.py` 必须显式 re-export 6 个 hook**，否则 pytest pluginmanager 无法识别 `pytest_addoption` 等 hook，`-p pytest_autoapi` 静默失败、报 "unrecognized arguments: --autoapi-data"。
- **`pytester` 测试不踩 `testpaths` 坑**：因为它在 tmpdir 启动 pytest，tmpdir 没有 `pyproject.toml`。所以 plugin 的 pytester 单测全绿不等于 CLI 主链路 OK。
- **`pytester.runpytest_inprocess` 默认 cwd 是 tmpdir**：必须显式 `pytester.syspathinsert(PROJECT_ROOT)` + 把 `examples/reading_house/Data` 作为最后一个位置参数传入，否则 pytest 不会扫描到 YAML 资产文件。
- **`nodeid` vs `reportinfo()` 显示**：pytest item 的 `nodeid` 形如 `examples/reading_house/Data/cases.yaml::case_xxx`，与 `reportinfo()` 显示的 `case::xxx` 是两套字符串；测试断言要直接断 `case_id` 子串而不是 `case::case_id`。

Phase C：

- **subprocess `command: str` 形态在 Windows 上的 shlex 模式选择**：第一版用 `shlex.split(command, posix=os.name != 'nt')`（Windows posix=False）。`posix=False` 把外层引号当字面量保留，subprocess 拿到 `['"C:\\Python\\python.exe"', '-c', '"print(1)"']` 后报 `FileNotFoundError [WinError 2]`。修订：统一用 `posix=True`，`command: str` 形态在 Windows 下要求路径用正斜杠（`"C:/Python/python.exe"`），或直接改用 list-form。docstring 已标注"Windows 强烈建议 list 形态"。
- **`RuntimeContext.set / get` 不区分 None 与缺失**：extract 写回时如果 stdout 为空字符串，`ctx.get('s_out')` 返回 `''` 而不是 `None`，单测里要用 `.strip()` 过滤换行符再断言文本。
- **YAML 修改不会自动同步老断言**：Phase C 给 `examples/minimal/Data/Scenarios/hanoi_hooks.yaml` 加了 hook script + inline script 两个 step 后，`Tests/test_repository.py` 三条 step ID 列表断言（v0.1 写的）立即变红。修复：把三条断言整体对齐到新 9 step 顺序，并补 `result.steps[1].extract_out["action"]["kind"] == "script"` 与 `cleanup_stdout` 写回 ctx 的回归断言。这条踩坑也说明：基线示例的 step 列表就是隐式契约，加 step 时必须扫一遍依赖该 scenario 的所有测试。

### 留给 v0.3 / P2 的事项

代码层（不是文档层）：

- `action.kind=sql` 真实执行（PostgreSQL 方言；`config.yaml` 顶层 `datasources` schema；`psycopg2` 依赖）。
- step retry（`pytest-rerunfailures`）、并行执行（`pytest-xdist`）。
- script 命令变量渲染（`command: ["python", "-c", "${cleanup_script}"]` 替换 ctx 变量）；需要先做白名单 / shell 注入防护设计。
- pytest mark `always_run / continue_on_error` 对外暴露（仅当未来要把 inline action 拆成独立 pytest item 时才需要）。
- OpenAPI 导入、SQLite 历史、敏感变量完整脱敏体系、资产索引、稳定 ID 生成、严格字段校验、tag/priority 执行、Web UI / 平台化"启用 / 禁用"toggle 实施。

文档层（已就位）：

- `docs/current_state.md` 已压缩为单段稳定状态；新线程读 1 段即掌握全局。
- `docs/validation_matrix.md` v0.2 §4 已覆盖 5 个 phase 的最小验证集合。
- `docs/decision_log.md` 9 条 2026-04-26 决策（含 1 条修订）已记录，下一次反复讨论时直接引用条目即可。
- `plans/20_pytest_kernel_migration.md` 全章节已就位，作为下次 v0.3 计划起草时的"如何打 phase / 如何与产品对齐 / 如何收尾"模版。
