# AutoAPI

AutoAPI 是一个轻量级接口自动化测试框架，当前阶段以 `CLI + YAML + pytest execution engine + Allure + JSONL history` 为核心。

框架当前采用 YAML-first 的测试资产管理方式：接口模板、接口用例、业务场景、测试计划都写在 YAML 文件中，执行历史和报告产物写入 `Reports/`。

## 当前状态

当前仓库的默认示例资产是读书屋接口：

```text
Data/reading_house
```

当前可用环境：

```text
test
```

当前正常使用入口是终端里的 `run` 命令，支持执行 selector 和基础校验。

框架内部由 `run.py` 提供 CLI 能力，正常用户不需要关注文件底部的本地调试模板。

`run.py` 当前支持两个子命令：

```text
run
validate
```

日常使用直接执行：

```bash
run cases --env test
```

如果没有安装或封装 `run` 命令，也可以从源码目录执行：

```bash
python run.py run cases --env test
```

Windows 虚拟环境下也可以显式指定解释器：

```bash
.venv\Scripts\python.exe run.py run cases --env test
```

## 目录结构

```text
Core/                 YAML 加载、资产合成、运行上下文
Engine/               执行引擎、请求解析、断言、提取、历史写入
Schema/               数据模型和基础校验
Utils/                Allure 报告相关工具
pytest_autoapi/       pytest 插件和 YAML item 收集器
Data/reading_house/   当前默认示例资产
Reports/              执行后生成的 Allure 和 JSONL 历史产物
run.py                当前 CLI 入口
```

默认资产目录结构：

```text
Data/reading_house/
  apis.yaml
  cases.yaml
  config.yaml
  plans.yaml
  Scenarios/
    reading_house_public_smoke.yaml
    reading_house_auth_flow.yaml
```

## 安装依赖

建议使用项目自带虚拟环境或自己创建虚拟环境后安装依赖：

```bash
pip install -r requirements.txt
```

当前 `requirements.txt` 是 UTF-16 编码；如果你的 `pip` 读取异常，可以先确认本机工具链是否能正确识别该文件编码。

## 命令格式

日常执行格式：

```bash
run <selector> [--data DATA_ROOT] [--env ENV_NAME]
```

源码执行格式：

```bash
python run.py run <selector> [--data DATA_ROOT] [--env ENV_NAME]
```

### 查看帮助

日常方式：

```bash
run --help
```

源码方式：

```bash
python run.py --help
python run.py run --help
python run.py validate --help
```

## 校验 YAML 资产

校验默认资产目录：

```bash
run validate
```

指定资产目录：

```bash
run validate --data Data/reading_house
```

源码方式：

```bash
python run.py validate --data Data/reading_house
```

校验成功后会输出类似：

```text
AutoAPI validate passed
apis: 8
cases: 8
scenarios: 2
plans: 2
```

## 执行测试

`run` 子命令的 selector 支持以下几类：

```text
cases
scenarios
plans
all
case_xxx
scn_xxx
plan_xxx
```

### 批量执行

执行所有 case：

```bash
run cases --env test
```

执行所有 scenario：

```bash
run scenarios --env test
```

执行所有 plan：

```bash
run plans --env test
```

执行整个资产目录：

```bash
run all --env test
```

### 执行单个 case

当前默认资产中的 case ID：

```text
case_book_click_rank_success
case_book_new_rank_success
case_book_update_rank_success
case_book_rank_top30_success
case_book_category_success
case_book_detail_success
case_user_login_success
case_user_info_success
```

执行示例：

```bash
run case_book_click_rank_success --env test
```

### 执行单个 scenario

当前默认资产中的 scenario ID：

```text
scn_reading_house_public_smoke
scn_reading_house_auth_flow
```

执行公开接口冒烟场景：

```bash
run scn_reading_house_public_smoke --env test
```

执行登录鉴权场景：

```bash
run scn_reading_house_auth_flow --env test
```

注意：`scn_reading_house_auth_flow` 需要在 `Data/reading_house/config.yaml` 中配置真实可用的登录账号、密码、验证码或 token。

### 执行单个 plan

当前默认资产中的 plan ID：

```text
plan_reading_house_public_smoke
plan_reading_house_auth_manual
```

执行公开接口冒烟计划：

```bash
run plan_reading_house_public_smoke --env test
```

执行鉴权接口手工数据计划：

```bash
run plan_reading_house_auth_manual --env test
```

### 指定资产目录

所有执行命令都可以加 `--data`：

```bash
run cases --data Data/reading_house --env test
run scn_reading_house_public_smoke --data Data/reading_house --env test
run plan_reading_house_public_smoke --data Data/reading_house --env test
```

对应源码方式是在 `run.py` 后补上 `run` 子命令：

```bash
python run.py run cases --data Data/reading_house --env test
```

## 执行输出

一次执行结束后，终端会输出执行状态、run id、目标、环境、通过数、失败数和错误数，例如：

```text
allure_results: Reports/allure-results/<run_id>
allure_report: Reports/allure-report/<run_id>
AutoAPI run finished: passed
run_id: <run_id>
target: scenario:scn_reading_house_public_smoke
env: test
passed: 6, failed: 0, error: 0
```

如果有失败或异常，CLI 会额外输出第一个问题步骤的请求、响应、上下文和错误信息。

## 报告和历史

执行产物默认写入：

```text
Reports/allure-results/<run_id>
Reports/allure-report/<run_id>
Reports/history/runs.jsonl
Reports/history/results.jsonl
```

`allure-results` 是 Allure 原始结果目录。

`allure-report` 是 HTML 报告目录；生成 HTML 报告依赖本机已安装 `allure` 命令。如果本机没有 Allure CLI，测试仍可执行，但 HTML 报告可能不会生成，并会在终端输出 `allure_warning`。

`Reports/history/runs.jsonl` 记录每次运行摘要。

`Reports/history/results.jsonl` 记录每个 step 的执行结果。

## YAML 资产分层

当前框架按四层组织测试资产：

```text
ApiTemplate -> ApiCase -> Scenario -> TestPlan
```

### ApiTemplate

定义接口模板，位于：

```text
Data/reading_house/apis.yaml
```

示例：

```yaml
apis:
  api_book_click_rank:
    meta:
      name: 点击榜单
      module: 书籍
      tags: ["榜单", "公开接口"]
      owner: qa
      priority: P0
    request:
      method: get
      path: /book/listClickRank
    extract:
      - source: response_json
        jsonpath: $.data[0].id
        as: bookId
```

### ApiCase

定义接口用例，位于：

```text
Data/reading_house/cases.yaml
```

示例：

```yaml
cases:
  case_book_click_rank_success:
    use: api_book_click_rank
    meta:
      name: 点击榜单查询成功
      tags: ["smoke", "public"]
      priority: P0
```

### Scenario

定义业务场景，位于：

```text
Data/reading_house/Scenarios/
```

示例：

```yaml
scenario_id: scn_reading_house_public_smoke

env: test

steps:
  - id: 获取点击榜单并提取书籍ID
    use: case_book_click_rank_success

  - id: 查询书籍详情
    use: case_book_detail_success
```

场景 step 当前支持两种形态：

```yaml
steps:
  - id: 引用接口用例
    use: case_book_click_rank_success

  - id: 执行脚本动作
    action:
      kind: script
      command: ["python", "-c", "print('cleanup ok')"]
    always_run: true
    continue_on_error: true
```

### TestPlan

定义测试计划，位于：

```text
Data/reading_house/plans.yaml
```

示例：

```yaml
plans:
  plan_reading_house_public_smoke:
    meta:
      name: 读书屋公开接口冒烟计划
      owner: qa
      priority: P0
    scenarios:
      - scn_reading_house_public_smoke
    cases: []
    run:
      continue_on_error: false
      report: allure
```

## 环境配置

环境配置位于：

```text
Data/reading_house/config.yaml
```

当前示例：

```yaml
active_env: test

envs:
  test:
    variables:
      bookId: 1
      rank_type: 0
      rank_limit: 30
    hosts:
      reading_house: http://novel.hctestedu.com
    host_rules:
      - host: reading_house
        priority: 0
        default: true
```

当前规则：`ApiTemplate`、`ApiCase`、`ScenarioStep` 中不写 `host` 或 `host_key`。host 只能通过环境里的 `host_rules` 解析。

## pytest 集成

框架内置 `pytest_autoapi` 插件。可以直接让 pytest 收集 YAML 资产：

```bash
python -m pytest -q -p pytest_autoapi --autoapi-data Data/reading_house --autoapi-env test Data/reading_house
```

过滤单个目标：

```bash
python -m pytest -q -p pytest_autoapi --autoapi-data Data/reading_house --autoapi-env test --autoapi-target case:case_book_click_rank_success Data/reading_house
python -m pytest -q -p pytest_autoapi --autoapi-data Data/reading_house --autoapi-env test --autoapi-target scenario:scn_reading_house_public_smoke Data/reading_house
python -m pytest -q -p pytest_autoapi --autoapi-data Data/reading_house --autoapi-env test --autoapi-target plan:plan_reading_house_public_smoke Data/reading_house
```

一般用户优先使用 `run.py`，CI 或 IDE 深度集成时再直接使用 pytest。

## 当前边界

- 不兼容旧的 `Data/single.yaml` 和 `Data/Flows/*.yaml`。
- 不支持接口级 `depends_on`。
- 不支持旧 `cleanup` 字段；业务清理应作为显式场景步骤。
- `override` 使用字段级整体覆盖，不做 deep merge。
- 严格字段 schema 校验在早期阶段暂未完全开启。
- `action.kind=wait` 和 `action.kind=script` 已实现；`action.kind=sql` 当前仍是占位能力。
- 登录鉴权相关示例依赖真实账号、验证码或 token，默认不保证可直接通过。

## 推荐快速验证

先校验资产：

```bash
run validate --data Data/reading_house
```

再执行公开接口冒烟：

```bash
run scn_reading_house_public_smoke --data Data/reading_house --env test
```

只想快速确认 case 收集和执行链路：

```bash
run cases --data Data/reading_house --env test
```
