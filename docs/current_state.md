# AutoAPI 当前状态

本文档只记录仓库当前真实状态，作为新线程接入工程时的快速入口。已经被当前实现覆盖的历史迁移细节、阶段性验证记录和旧命令写法不再保留在本文中；如需回溯，查看 git 历史、`docs/decision_log.md` 或对应 `plans/*.md`。

## 当前状态：2026-05-08

AutoAPI 当前是轻量级 `CLI + YAML + pytest execution engine + Allure + JSONL history` 框架。测试资产采用 YAML-first 管理，接口模板、接口用例、业务场景、测试计划分层存放；执行历史和报告产物写入 `Reports/`。

当前默认示例资产目录：

```text
Data/reading_house
```

当前默认可用环境：

```text
test
```

## 核心结构

```text
Schema/
  data_models.py          # ApiTemplate / ApiCase / Scenario / TestPlan 等数据模型
  data_validation.py      # 基础校验入口，保留 Validator 壳子

Core/
  repository.py           # YAML 资产加载和基础关系校验
  composer.py             # ApiTemplate / ApiCase / ScenarioStep 合成
  context.py              # env variables / dataset / extract 运行上下文

Engine/
  executor.py             # run_case / run_scenario / run_plan 执行编排
  action_runner.py        # wait / script action 执行；sql 当前仍是占位
  request_resolver.py     # 请求解析和变量渲染
  host_resolver.py        # 根据环境 host_rules 解析 host
  transport.py            # HTTP 请求发送
  extractor.py            # 响应提取
  assertion_engine.py     # 断言执行
  history_writer.py       # JSONL history 写入
  results.py              # RunResult / StepResult

pytest_autoapi/
  plugin.py               # pytest 参数、session、收集和结果聚合
  items.py                # YAML 文件收集为 pytest item

Utils/
  allure_runtime.py       # Allure results/report 路径和 HTML 生成
  allure_reporter.py      # Allure 附件和步骤报告辅助

Data/reading_house/
  apis.yaml
  cases.yaml
  config.yaml
  plans.yaml
  Scenarios/
    reading_house_public_smoke.yaml
    reading_house_auth_flow.yaml

run.py                    # CLI parser 和 pytest_autoapi 调用入口
```

## 当前 CLI 能力

正常用户入口是终端里的 `run` 命令：

```bash
run <selector> [--data DATA_ROOT] [--env ENV_NAME]
```

如果直接从源码执行，对应形式是：

```bash
python run.py run <selector> [--data DATA_ROOT] [--env ENV_NAME]
python run.py validate [--data DATA_ROOT]
```

`run.py` 底部的本地调试模板不作为用户入口描述。

### selector 支持

```text
cases
scenarios
plans
all
case_xxx
scn_xxx
plan_xxx
```

### 常用命令

```bash
run validate --data Data/reading_house

run cases --data Data/reading_house --env test
run scenarios --data Data/reading_house --env test
run plans --data Data/reading_house --env test
run all --data Data/reading_house --env test

run case_book_click_rank_success --data Data/reading_house --env test
run scn_reading_house_public_smoke --data Data/reading_house --env test
run plan_reading_house_public_smoke --data Data/reading_house --env test
```

当前默认资产中的主要 ID：

```text
case_book_click_rank_success
case_book_new_rank_success
case_book_update_rank_success
case_book_rank_top30_success
case_book_category_success
case_book_detail_success
case_user_login_success
case_user_info_success

scn_reading_house_public_smoke
scn_reading_house_auth_flow

plan_reading_house_public_smoke
plan_reading_house_auth_manual
```

## pytest 集成

框架内置 `pytest_autoapi` 插件，可让 pytest 直接收集 YAML 资产：

```bash
python -m pytest -q -p pytest_autoapi --autoapi-data Data/reading_house --autoapi-env test Data/reading_house
```

目标过滤格式：

```bash
--autoapi-target case:<case_id>
--autoapi-target scenario:<scenario_id>
--autoapi-target plan:<plan_id>
```

## 执行产物

一次执行会生成或尝试生成以下产物：

```text
Reports/allure-results/<run_id>
Reports/allure-report/<run_id>
Reports/history/runs.jsonl
Reports/history/results.jsonl
```

说明：

- `allure-results` 是 Allure 原始结果目录。
- `allure-report` 是 HTML 报告目录，依赖本机安装 `allure` CLI。
- `runs.jsonl` 记录每次运行摘要。
- `results.jsonl` 记录 step 级执行结果。

## YAML 资产规则

当前资产分层：

```text
ApiTemplate -> ApiCase -> Scenario -> TestPlan
```

关键约束：

- `ApiTemplate`、`ApiCase`、`ScenarioStep` 中不写 `host` 或 `host_key`。
- host 只能通过环境 `config.yaml` 中的 `host_rules` 解析。
- 场景步骤显式排列，引用直接使用全局唯一 ID。
- P0 阶段，场景步骤只引用 `case_` 开头的 ID。
- 接口级 `depends_on` 已移除。
- 旧 `cleanup` 字段已移除，业务清理应作为显式场景步骤。
- `override` 使用字段级整体覆盖，不做 deep merge。
- 不兼容旧 `Data/single.yaml` 和 `Data/Flows/*.yaml`。

## action 能力

`ScenarioStep` 当前支持 `use` 和 `action` 两种形态，二者互斥。

```yaml
steps:
  - id: 引用接口用例
    use: case_book_click_rank_success

  - id: 兜底脚本清理
    action:
      kind: script
      command: ["python", "-c", "print('cleanup ok')"]
    always_run: true
    continue_on_error: true
```

当前 action 状态：

| kind | 状态 | 说明 |
| --- | --- | --- |
| wait | 已实现 | `seconds < 0` 会报错 |
| script | 已实现 | 支持 `stdout` / `stderr` / `returncode` 提取 |
| sql | 占位 | 当前抛 `NotImplementedError`，真实执行留给后续阶段 |

执行策略：

- `always_run: true`：前序 step 失败时仍执行。
- `continue_on_error: true`：当前 step 失败后场景继续往后走。
- 默认行为是失败即停止。

## 当前边界

- 严格字段 schema 校验暂未完全开启。
- pytest item 级数据驱动展开尚未实现。
- `action.kind=sql` 真实执行尚未实现。
- step retry、并行执行、OpenAPI 导入、SQLite 历史、资产索引、稳定 ID 生成、Web UI 暂未实现。
- 登录鉴权场景依赖真实账号、验证码或 token，默认不保证可直接通过。

## 参考资料

- `docs/product_requirements.md`：产品需求和长期规则。
- `docs/technical_design_v1.md`：技术设计。
- `docs/decision_log.md`：仍在指导未来工作的决策。
- `plans/20_pytest_kernel_migration.md`：v0.2 pytest 内核切换历史。
