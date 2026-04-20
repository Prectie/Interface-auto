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
- [ ] 实现字段级 composition / Resolver。
- [ ] 实现 `host_rules` 解析。
- [ ] 实现 case 执行。
- [ ] 实现 scenario 执行。
- [ ] 实现 plan 执行。
- [ ] 实现 CLI 路由。
- [ ] 实现 JSONL history。
- [ ] 适配 Allure 元数据。
- [ ] 增加最小测试。
- [ ] 更新 retrospective。

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
- `apply_patch` 对部分已有文件执行 delete+add 失败，因此 `Core/repository.py` 和 `Schema/data_validation.py` 暂时保留旧代码块，新 P0 主路径通过后定义/新增方法接管；后续 Executor 重构时需要清理旧代码。

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

- `Core/repository.py`：旧 `YamlRepository`，固定加载旧结构。
- `Schema/data_validation.py`：旧严格 Validator，包含旧 dataclass。
- `Core/data_processing.py`：包含 `deep_merge` 和变量渲染。
- `Engine/request_resolver.py`：旧请求构建逻辑，依赖 `host/url/deep_merge`。
- `Engine/executor.py`：旧执行器，包含 `run_single`、`run_flow`、`depends_on`、`cleanup`。
- `Engine/transport.py`：requests/session 传输层，预计可复用。
- `Engine/extractor.py`、`Engine/assertion_engine.py`、`Engine/jsonpath_tool.py`：提取和断言能力，预计可复用。
- `Utils/allure_reporter.py`：Allure 附件能力可复用，但 metadata 需要适配新模型。
- `run.py`：需要改为 CLI router。
- `Tests/conftest.py`、`Tests/test.py`：旧 pytest 收集和执行入口，需要重新评估是否保留。

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

- 这些命令尚未可用。
- 后续每个 milestone 应写自己的局部验证命令。

## 10. Idempotence and Recovery

- 文档和 examples 可以重复编辑。
- `Reports/history/*.jsonl` 是运行产物，测试期间可删除重建，但删除前需要确认是否有用户需要保留。
- 新 Repository / Resolver / Executor 改造期间，不应回滚用户未说明的其他改动。
- 如果实现中发现必须跨入 P1/P2，先停下来说明，不直接实现。
- 如果发现需要兼容旧结构，先停下来说明，与 PRD 和 decision_log 对齐后再决定。

## 11. Outcomes & Retrospective

尚未开始实现。

待 P0 阶段完成后补充：

- 实际完成内容。
- 未完成内容。
- 与计划偏差。
- 运行过的验证。
- 剩余风险。
- 下一阶段建议。
