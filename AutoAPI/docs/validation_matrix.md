# AutoAPI 验证矩阵

版本：v0.2

本文档规定 AutoAPI 在每个里程碑结束时的最低验证口径。它不替代具体 ExecPlan 的验收章节，只用来约束"任意一次推进结束后，至少要跑哪些命令、观察什么"，避免每次临时判断"该跑什么"。

历史的 P0 milestone 矩阵已经随 v0.1 完成而下线；如需回溯，请查看仓库 git 历史。

## 1. 通用汇报格式

任何里程碑或 ExecPlan 收尾时，汇报至少包含：

- 改动文件。
- 改动原因。
- 已执行命令。
- 通过项。
- 未执行项及原因。
- 剩余风险。
- ExecPlan 进度更新情况。

如果某个命令因为功能尚未实现无法执行，需要明确写成：

```text
未执行：<命令>
原因：<原因>
后续补跑时机：<milestone>
```

## 2. 验证分级

### Must

当前里程碑必须执行。未执行时不能视为完成，除非明确是功能尚未进入该阶段。

### Should

当前里程碑建议执行。若因环境或依赖缺失无法执行，需要说明原因。

### Optional

辅助验证。执行后可增加信心，但不作为完成条件。

## 3. v0.1 自研内核基线（已完成）

v0.1 的执行内核 / Allure / JSONL history 全部由仓库自研代码承担。在 v0.2 切换完成前，下面这组命令仍是 AutoAPI 的最小验证集合：

Must（仅纯加载与基础校验）：

```bash
python run.py validate --data examples/p0_minimal/Data
python run.py validate --data examples/reading_house/Data
python -m pytest -q
```

Should（需要目标服务可达；已知 reading_house 公网示例由用户人工验证）：

```bash
python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --plan plan_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_auth_flow --env test --data examples/reading_house/Data
```

观察点：

- `validate` 退出码为 0；输出包含 `apis / cases / scenarios / plans` 数量。
- `pytest -q` 全部通过。
- CLI 真实执行时输出 `allure_results` 与 `allure_report` 路径。
- `Reports/history/runs.jsonl` 与 `Reports/history/results.jsonl` 均有新增条目。
- 失败时 CLI 输出请求、响应、上下文、异常原因。

## 4. v0.2 内核切换里程碑验证

v0.2 切换的具体步骤与验收命令以 `plans/20_pytest_kernel_migration.md` 为准。本节给出"每个 Phase 结束至少要看到什么"的统一约束。

> **状态**: 截至 2026-04-26，Phase A / B / C / D 已全部落地并验收；Phase E 最终交付清单见本节末尾。

### Phase A：execute_one 抽出 + 行为等价锁

Must：

```bash
python -m pytest -q
```

观察点：

- `Engine/executor.py` 顶部已存在模块级 `execute_one(executable, ctx, env, transport, *, resolver, extractor, assert_engine, request_defaults) -> StepResult` 纯函数；`Executor._execute_executable` 仅剩一行薄壳调用 `execute_one(...)`；`_error_status / _duration_ms` 转发到模块级 `_classify_error_status / _perf_to_ms`。
- 所有 v0.1 测试不需要修改即可全绿（44 个）。这是行为等价锁的硬性证据。
- `run_case / run_scenario / run_plan` 仍负责 hooks / dataset / 多 step 编排——本计划之前一度把它们也写成"退化为薄壳"，已在 `plans/20 §4` 更正：选项 1 粗粒度策略下，调度细节属于 pytest item.runtest() 内部，无需上移。

### Phase B：插件骨架 + Allure 标准化

Must：

```bash
python -m pytest -q
python -m pytest -q --alluredir Reports/allure-results/<run_id>
allure generate Reports/allure-results/<run_id> -o Reports/allure-report/<run_id> --clean
```

观察点：

- `pytest_autoapi` 已经能把 `cases.yaml / Scenarios/*.yaml / plans.yaml` 收集为 pytest items。
- 每条 item 的 nodeid 含可读的 case/scenario/plan ID。
- Allure HTML 报告由 `allure-pytest` 标准产出；`historyId / fullName / start / stop` 都不再依赖自研写入器。
- `environment.properties` 与 `categories.json` 仍由 hook 写入。

Should：

```bash
python run.py validate --data examples/p0_minimal/Data
python run.py --case case_book_rank_top30_success --env test --data examples/reading_house/Data
```

观察点：

- `run.py` 的 `validate` 子命令保持原行为。
- `run.py` 的 `--case/--scenario/--plan` 等价于 `pytest.main(...)`。
- 用户视角的命令、输出、退出码与 v0.1 一致。

### Phase C：wait / script action 真实执行（sql 延后 P2）

> **范围修订（2026-04-26）**: sql action 真实执行延后到 P2，目标方言锁定 PostgreSQL；第一版仅落 wait + script。详见 `docs/decision_log.md` 2026-04-26（修订）"sql action 真实执行延后到 P2"。

Must：

```bash
python -m pytest -q Tests/test_actions.py
```

观察点：

- `action.kind=wait` 能 `time.sleep(seconds)`，`seconds < 0` 抛 `ValueError`。
- `action.kind=script` 能执行本地命令并把 `stdout / stderr / returncode` 通过 `extract` 写回 `RuntimeContext`；默认 `expect_returncode=0`，进程退出码不等于期望值时 step 自动 `failed`；`expect_returncode: any` 跳过校验。
- `action.kind=sql` 抛 `NotImplementedError`，被 `_classify_error_status` 归类为 `error`，不被静默通过。
- `wait / script / sql` 三类共用 `Engine/action_runner.run_action(...)` 单入口。
- hooks (`before_steps / after_steps`) 与 `Scenario.steps[]` 内联 action 共享同一份 `_execute_action_hook` 薄壳，`Engine/executor.py` 不再内联 sleep / NotImplementedError。

Should：

```bash
python run.py --scenario scn_hanoi_hooks_flow --env test --data examples/minimal/Data
python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data
```

观察点：

- `examples/minimal/Data/Scenarios/hanoi_hooks.yaml` 中 `before_steps` 内的 hook script `打印 hook 启动标记` 进入 `passed`，stdout 含 `hook before_steps ok`。
- 主流程失败路径下，`steps[]` 末尾标了 `always_run: true` 的 inline script `兜底脚本清理` 仍然执行；`continue_on_error: true` 让该 step 失败也不阻塞后续 step。
- `extract: [{source: stdout, as: cleanup_stdout}]` 把 stdout 写回 ctx，可在 `scenario.assertions` 或下游 step 读取。
- `examples/reading_house/Data` 的 public smoke 脚本演示与 minimal 行为一致（CLI smoke 主战场已切到 reading_house，详见 `docs/current_state.md`）。

### Phase D：always_run / continue_on_error + schema 收敛

Must：

```bash
python -m pytest -q Tests/test_step_policy.py
```

> **说明**: schema 收敛的负向校验单测（拒绝 `finally_steps` / `cases.<id>.before_steps` / `cases.<id>.api`）已并入 `Tests/test_step_policy.py` 与 `Tests/test_repository.py`，未单独建 `test_schema_convergence.py`。

观察点（执行策略字段）：

- 标了 `always_run: true` 的 step 在前序 step 失败时仍然执行；其自身失败不阻塞其它 `always_run` step。
- 标了 `continue_on_error: true` 的 step 失败后，scenario 不立即停止；其自身状态记为 `failed/error`。
- 默认行为保持"失败即停止"。

观察点（schema 收敛负向校验）：

- YAML 中如果出现 `finally_steps`（任意层级），validate 退出码非 0，并指示迁移到 `steps[]` + `always_run: true`。
- YAML 中如果出现 `cases.<id>.before_steps` 或 `cases.<id>.after_steps`，validate 退出码非 0，并指示迁移到 `ApiTemplate` 或 `Scenario` 层。
- YAML 中如果出现 `cases.<id>.api: ...`（旧字段名），validate 退出码非 0，并指示改用 `cases.<id>.use:`。
- step 字段 `use` 与 `action` 同时出现或都不出现，validate 退出码非 0。

观察点（上下文叠加初始化）：

- `Scenario.datasets` 多轮执行时，`Environment.variables` 中的 key 在每轮内仍然可见。
- 同名 key 在 `dataset.variables` 中重新定义时，本轮内取 dataset 值；下一轮重新从 env.variables 拷贝，不被前一轮 dataset 污染。
- 上一轮 step `extract` 写入的 key 在下一轮不可见。

Should：

```bash
python run.py --scenario scn_hanoi_hooks_flow --env test --data examples/minimal/Data
python run.py --scenario scn_hanoi_dataset_flow --env test --data examples/minimal/Data
```

观察点：

- `scn_hanoi_hooks_flow`：用户在 YAML 中只增加 `always_run: true`，无需额外配置即可表达"接口级 / 脚本级清理"；含 hook script + inline script + always_run + continue_on_error 完整组合。
- `scn_hanoi_dataset_flow`：跑两轮 dataset，每轮 step 都能引用 env.variables 中的占位变量，且第二轮看不到第一轮 extract 的变量；每轮 dataset 跑 7 个 step（before(1) + main(3) + always_run兜底(1) + after(1) + assertions(1)）。

### Phase E：v0.2 最终交付

Must：

```bash
python -m pytest -q
python run.py validate --data examples/minimal/Data
python run.py validate --data examples/reading_house/Data
```

观察点：

- `pytest -q` 全绿，预期 80 个用例（44 个原 v0.1 + 4 个 Phase B plugin + 11 个 Phase D step policy + 21 个 Phase C action_runner / schema validation / executor 端到端）。
- `validate` 退出码 0；minimal 数据 `apis: 10 / cases: 19 / scenarios: 3 / plans: 1`；reading_house 数据 `apis: 8 / cases: 8 / scenarios: 2 / plans: 2`。
- `docs/current_state.md` "当前 v0.2 状态" 段存在，且与代码事实一致（不残留"v0.2 切换方向"等过期段）。
- `plans/20_pytest_kernel_migration.md §11 Outcomes & Retrospective` 已填写。

Should：

```bash
allure_run_id=$(python -c "import uuid; print(uuid.uuid4().hex)")
python -m pytest -q examples/reading_house/Data --autoapi-data examples/reading_house/Data --autoapi-env test --alluredir Reports/allure-results/$allure_run_id
allure generate Reports/allure-results/$allure_run_id -o Reports/allure-report/$allure_run_id --clean

python run.py --scenario scn_reading_house_public_smoke --env test --data examples/reading_house/Data
python run.py --scenario scn_reading_house_auth_flow --env test --data examples/reading_house/Data
```

观察点：

- Allure HTML 报告由 `allure-pytest` 标准产出；testcase 的 `historyId / fullName / start / stop` 都不依赖自研写入器；`environment.properties / categories.json` 仍由 plugin sessionstart hook 写入。
- CLI smoke 主战场已切到 reading_house（minimal 因无本地 backend 仅做"YAML schema + 调度顺序"最小回归）。public smoke 应当一次跑过；auth_flow 需要真实账号 + 验证码，结果由用户人工判定。
- reading_house 示例 scenario 中至少有一例演示 hook script + inline script always_run（详见 `examples/reading_house/Data/Scenarios/`）。

## 5. 可合并状态定义

任何里程碑达到可合并状态，需要满足：

- 该里程碑的 Must 验证已执行并通过，或明确说明功能尚未到达可执行阶段。
- 失败项有明确原因和后续补跑时机。
- 关联 ExecPlan 进度已更新。
- 未引入超出本里程碑范围的能力。
- 未保留旧 `single.yaml / Flows` 兼容作为新主链路。
- 没有静默扩大设计范围。
