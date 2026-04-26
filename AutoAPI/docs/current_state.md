# AutoAPI 当前状态

本文档记录仓库真实状态，作为新线程接入工程时**只读 1 段就能掌握全局**的入口。每次推进只新增"当前 …… 状态：YYYY-MM-DD"章节，不滚动覆盖历史结论。当一段被后续段完全覆盖、或仅描述"既成事实"且不再指导未来工作时，从本文件移除以控制上下文体积；可在 git 历史中通过 `git log -- docs/current_state.md` 查阅。

## 当前 v0.2 状态：2026-04-26

v0.2 内核切换四阶段（A / B / C / D）已全部落地并人工验收通过，仓库当前处于"等价行为锁定 + 内核已切到 pytest + actions wait/script 已可执行"的稳定形态。Phase E（`docs/validation_matrix.md` / `docs/current_state.md` 收口 + `plans/20` §11 retrospective + 读书屋 public smoke 补 script 演示）亦已完成，**用户在 `python -m pytest -q` 与 `python run.py validate --data examples/reading_house/Data` 上再次人工确认通过**；`plans/20_pytest_kernel_migration.md` 可视为 v0.2 内核切换 ExecPlan 终局。

### 架构组件

```text
Schema/
  data_models.py          # 数据模型（v0.2 收敛后：ApiCase 仅 use; Scenario 无 finally_steps; ScenarioStep 含 use ⊕ action / always_run / continue_on_error）
  data_validation.py      # 校验入口 + 旧字段拒绝（finally_steps / cases.<id>.api / cases.<id>.before_steps / after_steps）+ action schema 校验

Core/
  repository.py / composer.py / context.py
  # YAML 加载、ExecutableCase / ExecutableStep 合成、RuntimeContext 三层叠加（env.variables → dataset.variables → 运行时 extract）

Engine/
  executor.py             # run_case / run_scenario / run_plan 仍负责 hooks / dataset / 多 step 编排; 原子 step 走模块级 execute_one(...) 纯函数; _execute_action_hook 退化为薄壳, 转发到 action_runner
  action_runner.py        # NEW: wait / script 真实执行入口; sql 仍 NotImplementedError 占位（P2 落地, 目标 PostgreSQL）
  request_resolver.py / host_resolver.py / transport.py / extractor.py / assertion_engine.py / jsonpath_tool.py / history_writer.py / results.py

pytest_autoapi/           # NEW: pytest 插件包
  __init__.py             # 显式 re-export 6 个 hook
  plugin.py               # pytest_addoption / configure / sessionstart / collect_file / collection_modifyitems / sessionfinish
  items.py                # CasesCollector / ScenariosCollector / PlansCollector + AutoApiCaseItem / ScenarioItem / PlanItem; runtest 调 Executor.run_*

Utils/
  allure_runtime.py       # 仅保留 AllureArtifacts dataclass + generate_html_for_run; 全部 allure_commons 内部 API 已删除
  allure_reporter.py      # 仅依赖 allure_commons.types.AttachmentType 公开类型; *-result.json 由 allure-pytest 自动产出

run.py                    # validate 子命令直读 YamlRepository; --case / --scenario / --plan 翻译为进程内 pytest.main([...]) + 显式追加 data_dir 作为 collect path（绕开 pyproject.toml testpaths）
```

### 用户视角能力

CLI（v0.1 → v0.2 等价行为锁，stdout / 退出码 / JSONL 字段 / Allure 目录布局逐字保持）：

```bash
python run.py validate --data <DataDir>
python run.py --case   <case_id>     --env <env> --data <DataDir>
python run.py --scenario <scn_id>    --env <env> --data <DataDir>
python run.py --plan   <plan_id>     --env <env> --data <DataDir>
```

直接进 pytest 模式（CI / IDE 集成 / xdist 并行预演）：

```bash
python -m pytest -q                                                    # 仅跑仓库自身单测
python -m pytest -q --autoapi-data <DataDir> --autoapi-env <env>       # 把 YAML 资产收集为 pytest items
python -m pytest -q --autoapi-data <DataDir> --autoapi-target case:<case_id>   # 单条过滤
```

### 三个新能力的 schema 表达

`ScenarioStep` 同时支持引用 case 和内联 action（XOR 互斥）：

```yaml
steps:
  - id: 启动任务                      # use 形态
    use: case_start_task_success

  - id: 兜底等待                      # action 形态: wait
    action:
      kind: wait
      seconds: 0
    always_run: true

  - id: 兜底脚本清理                  # action 形态: script
    action:
      kind: script
      command: ["python", "-c", "print('cleanup ok')"]   # list-form 推荐, str-form 在 Windows 下要求正斜杠路径
      extract:
        - source: stdout
          as: cleanup_stdout
    always_run: true
    continue_on_error: true
```

执行策略（标记仅在 `Scenario.steps[]` 上有效；hooks `before_steps / after_steps` 不接受这两个字段）：

- `always_run: true`：前序 step 失败时仍执行；其自身失败不阻塞其它 `always_run` step。
- `continue_on_error: true`：本 step 失败后场景继续往后走，不立即停止。
- 默认行为保持"失败即停止"。

### action 真实执行边界（Phase C 当前版本）

| kind   | 状态        | 失败语义                              | extract source                      |
|--------|-------------|---------------------------------------|-------------------------------------|
| wait   | 已实现      | `seconds < 0` → `ValueError`（→ error）| 无                                  |
| script | 已实现      | `expect_returncode` 不匹配 → `failed`；环境/资源/超时 → `error` | `stdout / stderr / returncode`      |
| sql    | 占位      | 抛 `NotImplementedError` → `error`（避免 YAML 已声明 sql 占位时被静默通过） | 待 P2 引入                          |

详见 `docs/decision_log.md`：

- 2026-04-26 "sql / script action 从结构预留升级为 P1 必做"
- 2026-04-26（修订）"sql action 真实执行延后到 P2，第一版仅落 wait + script"
- 2026-04-26 "script action 默认 expect_returncode=0"

### 验证基线（2026-04-26 用户已在 Windows `.venv` 确认）

v0.2 全历程（含 Phase E 对 `reading_house_public_smoke.yaml` 增补 script）最终复核：`python -m pytest -q` 仍为 80 全绿；`validate` 对 minimal / reading_house 两目录资产计数未漂移。

```text
python -m pytest -q
→ 80 passed（44 v0.1 + 4 plugin + 11 step policy + 21 action_runner/schema/executor）

python run.py validate --data examples/minimal/Data
→ apis: 10 / cases: 19 / scenarios: 3 / plans: 1

python run.py validate --data examples/reading_house/Data
→ apis: 8 / cases: 8 / scenarios: 2 / plans: 2
（Phase E 在 public smoke 中增加 before_steps 与 inline script，不改变 scenarios 总数=2。）
```

CLI smoke 主战场说明：

- `examples/minimal`（汉诺塔示例）**无本地 backend**，仅做"YAML schema + 调度顺序"最小回归。CLI 执行端到端时主流程 step 必然 error，不影响 `validate` 与 pytest。
- `examples/reading_house`（读书屋示例）**有真实公网 backend**，作为 v0.2 起的 CLI smoke 主战场。public smoke 一次性跑过；auth_flow 需要真实账号 + 验证码，由用户人工判定。详见 `docs/validation_matrix.md §4 Phase E Should`。

### 边界 / 留给 P2 的事项

- `action.kind=sql` 真实执行（目标方言 PostgreSQL，与 `config.yaml` 顶层 `datasources` schema、`psycopg2` 依赖一并引入）。
- step retry（`pytest-rerunfailures` 接入）、并行执行（`pytest-xdist` 接入）。
- OpenAPI 导入、SQLite 历史、敏感变量完整脱敏体系、资产索引、稳定 ID 生成、严格字段校验、tag/priority 执行、Web UI / 平台化"启用 / 禁用"toggle 实施。
- script 命令变量渲染（如 `command: ["python", "-c", "${cleanup_script}"]` 替换 ctx 变量）；第一版 command 直接传给 subprocess 不走 `render_any`，避免 shell 注入。需求出现时单独决策。

完整 v0.2 切换执行细节（每个 phase 的代码改动 / 踩坑 / 决策修订）以 `plans/20_pytest_kernel_migration.md` 为准；v0.1 已交付能力的逐项清单与 v0.1 期间的人工验证记录见 `docs/release_v0.1.md`。

## 历史基线

主线已经远离最初的 `single.yaml + Flows + depends_on + cleanup` 旧模型；P0 重构前的逐文件基线快照、以及 P0/P1 阶段每个 milestone 的 ExecPlan，结论都已固化进当前 PRD / release_v0.1 / decision_log，不再保留为活文档。如需回溯：

- `docs/release_v0.1.md`：v0.1 已交付能力的完整清单与验证命令。
- `docs/decision_log.md`：仍在指导未来工作的决策；已被覆盖或仅描述既成事实的旧决策可在 git 历史中查看。
- `plans/20_pytest_kernel_migration.md`：v0.2 内核切换的 ExecPlan，含 Progress / Surprises / Outcomes & Retrospective 三段一手记录。
- 仓库 git 历史：所有被删除的 ExecPlan 与历史决策都可通过 `git log --all -- plans/ docs/decision_log.md docs/current_state.md` 检索。
