# AutoAPI P0 验证矩阵

版本：v0.1

本文档规定 P0 重构期间每个 milestone 至少怎么验证。它不替代测试代码，只用于约束每次实现后的验收口径，避免每次临时判断“该跑什么”。

## 1. 通用汇报格式

每个 milestone 完成后，汇报必须包含：

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

当前 milestone 必须执行。未执行时不能视为完成，除非明确是功能尚未进入该阶段。

### Should

当前 milestone 建议执行。若因环境或依赖缺失无法执行，需要说明原因。

### Optional

辅助验证。执行后可增加信心，但不作为完成条件。

## 3. Milestone 验证矩阵

### Milestone 1：文档与设计

范围：

- `docs/product_requirements.md`
- `docs/current_state.md`
- `docs/decision_log.md`
- `docs/technical_design_v1.md`
- `docs/validation_matrix.md`
- `PLANS.md`
- `plans/*.md`
- `examples/p0_minimal/`

Must：

```bash
git status --short AGENTS.md PLANS.md docs examples plans
```

观察点：

- 新增文档位于预期目录。
- ExecPlan 进度与实际文件一致。
- 文档没有把 P1/P2 能力写进 P0 实现范围。

Should：

```bash
find examples/p0_minimal/Data -maxdepth 3 -type f | sort
```

观察点：

- 示例资产包含 `config.yaml`、`apis.yaml`、`cases.yaml`、`Scenarios/*.yaml`、`plans.yaml`。

### Milestone 2：数据模型与 Repository

范围：

- `Schema/data_models.py`
- `Core/repository.py`
- `Schema/data_validation.py`
- Repository 相关测试。

Must：

```bash
python run.py validate --data examples/p0_minimal/Data
```

观察点：

- 能加载 P0 新结构。
- 能读取 config/apis/cases/scenarios/plans。
- 能输出 validate 成功。

Must：

```bash
pytest -q
```

观察点：

- Repository 和基础 Validator 测试通过。
- 不要求旧 `single.yaml / Flows` 测试继续通过，除非仍被保留为非主路径。

Should：

```bash
python run.py validate
```

观察点：

- 默认 `Data/` 目录如果尚未迁移，允许失败，但错误需要明确说明缺少新结构文件。

### Milestone 3：解析与合成

范围：

- `Core/composer.py`
- `Engine/host_resolver.py`
- `Engine/request_resolver.py`
- composition / host_rules 测试。

Must：

```bash
pytest -q
```

观察点：

- `ApiTemplate + ApiCase` 合成正确。
- `ScenarioStep.override` 只影响当前 step。
- override 是字段级整体覆盖，不做 deep merge。
- `null` 能显式清空。
- case / step 覆盖 `method/path` 会失败。
- `host_rules` 能按 `apis`、`modules`、`path_prefixes`、`default` 匹配。
- 同优先级冲突能报明确错误。

Should：

```bash
python run.py validate --data examples/p0_minimal/Data
```

观察点：

- 示例资产仍可通过基础校验。

### Milestone 4：执行链

范围：

- `Engine/executor.py`
- `Engine/request_resolver.py`
- `Engine/results.py`
- Allure 附件适配。

Must：

```bash
pytest -q
```

观察点：

- case 执行链薄测试通过。
- scenario 顺序执行薄测试通过。
- plan 聚合执行薄测试通过。
- 失败时能形成结构化错误。

Should：

```bash
python run.py --case case_start_task_success --env test --data examples/p0_minimal/Data
```

观察点：

- 能进入新 case 执行链。
- 如果没有真实服务，允许请求失败，但失败信息必须包含请求、环境、上下文、异常原因。

Should：

```bash
python run.py --scenario scn_hanoi_main_flow --env test --data examples/p0_minimal/Data
```

观察点：

- 能按 scenario steps 顺序执行。
- step 间共享 `RuntimeContext`。

### Milestone 5：CLI 与 History

范围：

- `run.py`
- `Engine/history_writer.py`
- `Reports/history/*.jsonl`
- CLI 测试。

Must：

```bash
python run.py validate --data examples/p0_minimal/Data
```

Must：

```bash
python run.py --case case_start_task_success --env test --data examples/p0_minimal/Data
```

Must：

```bash
python run.py --scenario scn_hanoi_main_flow --env test --data examples/p0_minimal/Data
```

Must：

```bash
python run.py --plan plan_hanoi_regression --env test --data examples/p0_minimal/Data
```

观察点：

- CLI 参数路由正确。
- `--case`、`--scenario`、`--plan` 互斥。
- `--env` 覆盖 scenario/config 环境。
- 执行失败时退出码非 0。
- 执行结束后生成 `Reports/history/runs.jsonl`。
- 执行结束后生成 `Reports/history/results.jsonl`。

Should：

```bash
pytest -q
```

观察点：

- CLI 和 history 单测通过。

### Milestone 6：测试与收口

范围：

- `Tests/`
- `docs/`
- `plans/00_autoapi_p0_refactor.md`
- README 或使用说明如后续需要。

Must：

```bash
pytest -q
```

Must：

```bash
python run.py validate --data examples/p0_minimal/Data
```

Must：

```bash
python run.py --plan plan_hanoi_regression --env test --data examples/p0_minimal/Data
```

观察点：

- P0 主链路可跑。
- 示例资产可作为最小验证资产长期保留。
- ExecPlan `Outcomes & Retrospective` 已更新。

Should：

```bash
git status --short
```

观察点：

- 能清楚区分本次改动与已有无关脏文件。

## 4. 可合并状态定义

P0 某个 milestone 达到可合并状态，需要满足：

- 该 milestone 的 Must 验证已执行并通过，或明确说明功能尚未到达可执行阶段。
- 失败项有明确原因和后续补跑时机。
- ExecPlan 进度已更新。
- 未引入 P0 范围外能力。
- 未保留旧 `single.yaml / Flows` 兼容作为新主链路。
- 没有静默扩大设计范围。

## 5. 当前阶段说明

截至本文档创建时，P0 仍处于文档与设计阶段。

当前能执行的验证主要是文件存在性和文档一致性检查。以下命令暂未要求通过：

```bash
python run.py validate --data examples/p0_minimal/Data
python run.py --case case_start_task_success --env test --data examples/p0_minimal/Data
python run.py --scenario scn_hanoi_main_flow --env test --data examples/p0_minimal/Data
python run.py --plan plan_hanoi_regression --env test --data examples/p0_minimal/Data
```

原因：

- `run.py` 当前仍是旧 pytest 固定入口。
- 新 Repository、Validator、Composer、Executor、CLI 尚未实现。

