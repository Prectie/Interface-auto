# AutoAPI P0 新模型重构 ExecPlan

本计划遵守 `PLANS.md`。它是 P0 重构总纲，用于指导后续 milestone 拆分和实现。

## 1. Purpose / Big Picture

完成 P0 后，AutoAPI 将从旧的 `single.yaml + Flows` 原型，重构为清晰的新资产模型：

```text
ApiTemplate -> ApiCase -> Scenario -> TestPlan
```

用户可以使用新 YAML 资产执行：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_hanoi_main_flow --env test
python run.py --plan plan_hanoi_regression --env test
```

执行链路需要支持：

- 新结构 YAML 加载。
- 基础 validate。
- 直接 ID 引用解析。
- `ApiTemplate + ApiCase + ScenarioStep override` 合成。
- 环境 `host_rules` 解析。
- case / scenario / plan 执行。
- Allure 报告复用。
- JSONL history 输出。

## 2. Scope

### In scope

- 新数据文件：
  - `Data/apis.yaml`
  - `Data/cases.yaml`
  - `Data/Scenarios/*.yaml`
  - `Data/plans.yaml`
- 新样例资产：`examples/p0_minimal/`
- 新数据对象：
  - `ApiTemplate`
  - `ApiCase`
  - `Scenario`
  - `ScenarioStep`
  - `TestPlan`
  - `EnvironmentConfig`
  - `HostRule`
- Repository 加载新结构。
- Validator 壳子和基础检查：
  - YAML 可读取
  - 全局 ID 唯一
  - 引用关系存在
  - `method + path` 重复
  - `host_rules` 基础冲突
- 字段级整体覆盖，不做 deep merge。
- `host_rules` 解析。
- case 执行。
- scenario 执行。
- plan 执行。
- CLI 路由：
  - `validate`
  - `--case`
  - `--scenario`
  - `--plan`
  - `--env`
- Allure 元数据适配新模型。
- JSONL history 输出。
- 最小测试覆盖。

### Out of scope

- 旧 `Data/single.yaml` 和 `Data/Flows/*.yaml` 兼容。
- Web UI。
- OpenAPI import。
- SQLite。
- 严格字段 schema 校验。
- tag / priority 执行。
- scenario-level data driving。
- `finally_steps`。
- 环境级鉴权模板。
- 公共脚本。
- 自动生成 ID。
- 把 YAML 资产放进数据库。

## 3. Progress

- [x] 创建 `docs/product_requirements.md`。
- [x] 创建项目级 `AGENTS.md`。
- [x] 创建 `docs/current_state.md`。
- [x] 创建 `PLANS.md`。
- [x] 创建 `docs/decision_log.md`。
- [x] 创建 `examples/p0_minimal/`。
- [x] 创建本 P0 总 ExecPlan。
- [x] 编写 `docs/technical_design_v1.md`。
- [x] 编写 `docs/validation_matrix.md`。
- [x] 设计新 dataclass。
- [x] 实现新 Repository 加载。
- [x] 实现基础 Validator。
- [x] 实现字段级 composition / Resolver。
- [x] 实现 `host_rules` 解析。
- [x] 实现 case 执行。
- [x] 实现 scenario 执行。
- [x] 实现 plan 执行。
- [x] 实现 CLI 路由。
- [x] 实现 JSONL history。
- [x] 适配 Allure 元数据。
- [x] 增加最小测试。
- [x] 清理旧结构代码。
- [x] 更新 retrospective。

## 4. Surprises & Discoveries

- 当前 `run.py` 固定执行 `Tests/test.py::test_flows_api`，没有 CLI router。
- 当前 `YamlRepository` 固定加载 `Data/config.yaml`、`Data/single.yaml`、`Data/Flows/*.yaml`。
- 当前 `YamlSchemaValidator` 严格耦合旧结构，而 P0 暂不做严格字段 schema 校验。
- 当前 `RequestResolver` 依赖 request 中的 `host` 和 `url`，且使用 `deep_merge`。
- 当前 `Executor` 耦合 `ApiItem`、`FlowBundle`、`depends_on`、`cleanup`。
- `requirements.txt` 在 shell 中显示为带 NUL 的异常文本或类似 UTF-16 的内容，后续需要单独评估。
- 当前 shell 的系统 Python 缺少 `pytest`，执行 `python3 -m pytest -q` 失败。
- 当前 `.venv` 是 Windows 虚拟环境，WSL 下执行 `.venv/Scripts/python.exe -m pytest -q` 失败。
- Windows `.venv` 中 `python run.py validate --data examples/p0_minimal/Data` 可以通过。
- Windows `.venv` 中 `python -m pytest -q` 曾显示 `no tests ran`，原因是 `pyproject.toml` 只匹配 `test_*.py`，而测试文件原名是 `Tests/test.py`；已改名为 `Tests/test_repository.py`。
- Windows `.venv` 中 `python -m pytest -q` 已通过，结果为 `8 passed`。
- 当前 WSL shell 调用 `powershell.exe -NoProfile -Command "python --version"` 失败，不能直接代跑 Windows `.venv` 验证。
- `apply_patch` 对部分已有文件执行 delete+add 失败，后续通过更小范围 patch 和定向替换完成旧结构代码清理。
- 已实现 `Executor.run_case/run_scenario/run_plan`、CLI `--case/--scenario/--plan/--env` 和 JSONL history，等待 Windows `.venv` 下执行验证。
- 用户 Windows `.venv` 已执行 `--case`、`--scenario`、`--plan`，三条命令均进入真实 HTTP 请求发送阶段；当前失败原因为 `127.0.0.1:1806` 连接被拒绝。
- 初版 CLI 失败摘要过于简略，已补充首个失败 step 的 request、response、context 和 error 输出。
- 全局 `git diff --check` 当前会被无关文件 `.idea/.gitignore` 和 `1.py` 的行尾空白阻塞；本次相关文件定向 `git diff --check -- <files>` 已通过。

## 5. Decision Log

已确认决策见 `docs/decision_log.md`。

本计划执行期间如出现新增决策，需要先记录在本节，并在阶段完成时同步到 `docs/decision_log.md`。

当前关键决策：

- P0/P1 测试资产 YAML-first，不进数据库。
- 新结构不兼容旧 `single.yaml / Flows`。
- 接口定义升级为 `ApiTemplate`。
- case 和 scenario step 不允许覆盖 `method/path`。
- `override` 使用字段级整体覆盖，不做 deep merge。
- host 只通过 Environment `host_rules` 解析。
- 场景步骤直接引用全局唯一 ID。
- P0 阶段 ID 手写。
- 废弃接口级 `depends_on`。
- 废弃旧 `cleanup`。
- P0 暂时关闭严格字段 schema 校验。

## 6. Context and Orientation

当前代码状态见 `docs/current_state.md`。

关键现状：

- `Core/repository.py`：已只加载 P0 新结构。
- `Schema/data_validation.py`：已只保留 P0 基础 Validator 壳子。
- `Core/data_processing.py`：保留变量渲染；新模型合成不使用 deep merge。
- `Engine/request_resolver.py`：已只保留 P0 `resolve_executable(...)` 请求构建入口。
- `Engine/executor.py`：已只保留 `run_case/run_scenario/run_plan` 新执行入口。
- `Engine/transport.py`：requests/session 传输层继续复用。
- `Engine/extractor.py`、`Engine/assertion_engine.py`、`Engine/jsonpath_tool.py`：提取和断言能力继续复用。
- `Utils/allure_reporter.py`：已适配 P0 case/scenario/plan 元数据方法。
- `run.py`：已改为 CLI router。
- `Tests/conftest.py`：已移除旧 pytest 收集逻辑，只保留 P0 最小样例 fixture。

P0 示例资产：

```text
examples/p0_minimal/Data/config.yaml
examples/p0_minimal/Data/apis.yaml
examples/p0_minimal/Data/cases.yaml
examples/p0_minimal/Data/Scenarios/hanoi.yaml
examples/p0_minimal/Data/plans.yaml
```

P0 验证约定：

```text
docs/validation_matrix.md
```

## 7. Plan of Work

### Milestone 1：技术设计

基于 PRD、current_state、decision_log、examples 和本计划，编写 `docs/technical_design_v1.md`。

只覆盖 P0，不写 P1/P2 的 OpenAPI、SQLite、Web UI、通知、平台化等内容。

### Milestone 2：数据模型与 Repository

新增或重构数据模型，支持加载：

- config
- apis
- cases
- scenarios
- plans

实现基础 Validator：

- YAML 可读取
- ID 唯一
- 引用存在
- `method + path` 重复
- `host_rules` 基础冲突

### Milestone 3：解析与合成

实现新模型的 composition 逻辑：

- `ApiTemplate + ApiCase -> ExecutableCase`
- `ExecutableCase + ScenarioStep override -> ExecutableStep`
- 字段级整体覆盖
- null 显式清空
- 不做 deep merge
- 禁止覆盖 `method/path`

实现 `host_rules` 解析：

- `apis`
- `modules`
- `path_prefixes`
- `default`
- priority 冲突处理

### Milestone 4：执行链

实现：

- `run_case`
- `run_scenario`
- `run_plan`

复用：

- `SessionTransport`
- `Extractor`
- `AssertionEngine`
- `ResponseSnapshot`
- Allure attach 能力

移除新链路中的：

- `depends_on`
- `cleanup`

### Milestone 5：CLI 与 history

改造 `run.py` 为 CLI router：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_hanoi_main_flow --env test
python run.py --plan plan_hanoi_regression --env test
```

新增 JSONL history：

```text
Reports/history/runs.jsonl
Reports/history/results.jsonl
```

### Milestone 6：测试与收口

增加最小测试：

- Repository 加载。
- Validator 基础检查。
- 字段级覆盖。
- host_rules 解析。
- case/scenario/plan 路由或执行薄测试。

更新：

- `docs/current_state.md`
- 本 ExecPlan progress。
- `docs/decision_log.md`，如有新增决策。

## 8. Concrete Steps

预计新增或重点修改文件：

```text
Schema/data_models.py
Schema/data_validation.py
Core/repository.py
Core/data_processing.py
Engine/request_resolver.py
Engine/executor.py
Engine/results.py
Utils/allure_reporter.py
run.py
Tests/
Reports/history/
```

预计新增文档或样例：

```text
docs/technical_design_v1.md
examples/p0_minimal/
```

实际执行时，如果某个 milestone 过大，应拆出更小计划，例如：

```text
plans/p0_01_repository_loading.md
plans/p0_02_reference_resolution.md
plans/p0_03_executor_cli.md
plans/p0_04_history_output.md
```

## 9. Validation and Acceptance

P0 完成后的目标验证命令：

```bash
python run.py validate
python run.py --case case_start_task_success --env test
python run.py --scenario scn_hanoi_main_flow --env test
python run.py --plan plan_hanoi_regression --env test
pytest
```

目标观察结果：

- `validate` 能加载新结构并完成基础检查。
- `--case` 能解析 case、api template、host_rules 并执行。
- `--scenario` 能按 steps 顺序执行并共享 context。
- `--plan` 能执行计划中的 scenarios 和 cases。
- Allure 能记录新模型元数据。
- `Reports/history/runs.jsonl` 和 `Reports/history/results.jsonl` 能追加记录。

当前阶段说明：

- `python run.py validate --data examples/p0_minimal/Data` 已在用户 Windows `.venv` 环境通过。
- `python -m pytest -q` 已在用户 Windows `.venv` 环境通过，结果为 `8 passed`。
- `--case`、`--scenario`、`--plan` 已在用户 Windows `.venv` 中验证可进入真实请求发送阶段；成功路径仍需目标服务可用后验证。

## 10. Idempotence and Recovery

- 文档和 examples 可以重复编辑。
- `Reports/history/*.jsonl` 是运行产物，测试期间可删除重建，但删除前需要确认是否有用户需要保留。
- 新 Repository / Resolver / Executor 改造期间，不应回滚用户未说明的其他改动。
- 如果实现中发现必须跨入 P1/P2，先停下来说明，不直接实现。
- 如果发现需要兼容旧结构，先停下来说明，与 PRD 和 decision_log 对齐后再决定。

## 11. Outcomes & Retrospective

当前 P0 主链路已完成到可进入真实服务验证的阶段；旧结构代码已从主代码路径清理。

### 实际完成内容

- 已建立项目级协作规则：`AGENTS.md`。
- 已建立 ExecPlan 规则：`PLANS.md`。
- 已建立 P0 产品需求、当前状态、决策记录、技术设计和验证矩阵。
- 已建立 P0 最小样例资产：`examples/p0_minimal/Data`。
- 已实现 P0 新数据模型：`ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan`、`ExecutableCase`、`ExecutableStep`。
- 已实现 P0 Repository 加载新结构：`config.yaml`、`apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。
- 已实现基础 Validator：ID 唯一、引用存在、`method + path` 重复、`host_rules` 基础检查。
- 已实现字段级 composition：未填写继承、填写则整体覆盖、`null` 清空、不做 deep merge、禁止覆盖 `method/path`。
- 已实现 `host_rules` 解析：`apis`、`path_prefixes`、`default`、`priority`。
- 已实现 P0 RequestResolver 新入口：`resolve_executable(...)`。
- 已实现 P0 Executor 新入口：`run_case(...)`、`run_scenario(...)`、`run_plan(...)`。
- 已实现 CLI：`validate`、`--case`、`--scenario`、`--plan`、`--env`。
- 已实现 JSONL history 初版：`Reports/history/runs.jsonl`、`Reports/history/results.jsonl`。
- 已增强 CLI 失败摘要：失败时输出首个问题 step 的 request、response、context、error_code、error_message、error_reason 和 hint。
- 已适配 Allure P0 元数据方法：case、scenario、plan、P0 step、P0 run。
- 已清理旧结构代码：Repository、Validator、Executor、RequestResolver、Results、AllureReporter、pytest conftest 不再保留旧 single/flow 主路径。
- 已增加最小测试，覆盖 Repository、Composer、HostResolver、RequestResolver、Executor 和 HistoryWriter。
- 已更新 `docs/current_state.md` 记录当前状态。

### 未完成内容

- CLI 的 `--case`、`--scenario`、`--plan` 已验证失败路径；成功路径尚未在真实本地接口服务下验证。
- `Reports/history/*.jsonl` 已验证会记录失败路径；成功路径记录尚未验证。
- Allure P0 元数据方法已存在，但尚未接入 CLI 执行链自动生成 Allure 报告。

### 与计划偏差

- 原计划中 Repository 和 Validator 更偏向一次性重构；实际先追加 P0 主路径并验证，再在当前阶段清理旧结构代码。
- 原计划希望 Codex 直接本地执行 pytest；实际 WSL 中缺少 `python/pytest`，Windows `.venv` 由用户代跑。
- 原计划中 Allure 保留为 P0 项；实际先完成 CLI + JSONL 主链路，再补 P0 元数据方法，尚未接入 CLI 自动生成报告。

### 已运行验证

- 用户 Windows `.venv` 中执行 `python run.py validate --data examples/p0_minimal/Data`，结果通过。
- 用户 Windows `.venv` 中执行 `python -m pytest -q`，结果为 `8 passed`。
- 用户 Windows `.venv` 中执行 `--case`、`--scenario`、`--plan`，均进入真实 HTTP 请求发送阶段并记录 JSONL；结果为 `REQUEST_SEND_ERROR`，原因为 `127.0.0.1:1806` 连接被拒绝。
- Codex 在 WSL 中对本次相关文件执行定向 `git diff --check -- <files>`，结果通过。

### 未运行验证

- 未在 Codex 当前 WSL 中运行 `python -m pytest -q`，原因是系统 Python 缺少 pytest，且 Windows `.venv` 无法从 WSL 调用。
- 未验证 `--case`、`--scenario`、`--plan` 成功路径，原因是当前本地目标服务未连通。

### 剩余风险

- 真实接口服务未启动时，CLI 执行会进入新链路但请求失败；当前已补充 CLI 失败详情，后续还需验证成功路径输出。
- Allure 路线尚未决策：继续走 pytest 生成 Allure，还是 CLI 写 JSONL、后续再生成报告。
- 旧数据文件如果仍留在 `Data/` 目录，不再被主代码路径读取，但后续可以单独清理资产文件。
- 全局 `git diff --check` 会被无关文件 `.idea/.gitignore` 和 `1.py` 的行尾空白阻塞；当前未处理这些无关文件。

### 下一阶段建议

- 在目标接口服务可用后，重新运行 `--case`、`--scenario`、`--plan` 三条 CLI 命令，确认成功路径和 JSONL history。
- 再决策 Allure 报告生成路线，并把 P0 元数据方法接入实际执行链。
- 视需要清理旧 `Data/single.yaml`、`Data/Flows/*.yaml` 资产文件。
