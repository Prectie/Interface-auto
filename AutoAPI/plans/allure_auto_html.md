# AutoAPI Allure 自动 HTML 报告

## Purpose / Big Picture

完成后，用户执行：

```text
python run.py --case ...
python run.py --scenario ...
python run.py --plan ...
```

时，CLI 会在执行结束后自动产出：

- `Reports/allure-results/<run_id>/`
- `Reports/allure-report/<run_id>/`

并在终端输出报告目录；用户不需要再额外手动生成 Allure HTML。

## Scope

In scope:

- 在 CLI 主链路中自动写 `allure-results`
- 自动调用 Allure CLI 生成 HTML 报告
- 终端输出 `allure-results` 和 `allure-report` 路径
- Allure CLI 缺失或 HTML 生成失败时只输出 warning，不改变真实执行结果
- 同步 `docs/current_state.md`

Out of scope:

- P1 的场景级 hooks / `finally_steps`
- Web UI 报告查看器
- 改造 JSONL history 结构
- 新增第三方依赖

## Progress

- [x] 阅读 PRD、current_state、decision_log、technical_design
- [x] 确认 Allure 目标目录、失败策略和 CLI 口径
- [x] 新增 Allure runtime 写入器
- [x] 接入 `run.py` 主执行链
- [x] 增加单测
- [x] 更新 `docs/current_state.md`
- [x] 写 retrospective

## Surprises & Discoveries

- `Utils/allure_reporter.py` 当前主要服务于 pytest / 动态 metadata 写法，CLI 主链路没有真正使用它。
- 现成的 `allure_commons.lifecycle.AllureLifecycle + AllureFileLogger` 足够直接写 `allure-results`，不需要强行复用 pytest listener。
- `run.py` 当前 `__main__` 里还残留了硬编码 `plan_list`，需要顺手修回正常 CLI 入口。

## Decision Log

- CLI Allure 运行时采用 `allure_commons.lifecycle + AllureFileLogger` 直接写 `allure-results`。
- 每次 CLI 执行只生成一个 Allure test case，内部用 Allure step 展示 `P0StepResult` 列表。
- `P0StepResult.status=error` 映射为 Allure `broken`；`failed` 映射为 `failed`；`passed` 映射为 `passed`。
- 仍复用 `Utils/allure_reporter.py` 写 `environment.properties` 和 `categories.json`。

## Context and Orientation

- `run.py`：当前在 `run_target(...)` 写 JSONL history 和终端摘要，但没有 Allure 产物。
- `Engine/results.py`：`P0RunResult` / `P0StepResult` 已具备足够信息，可直接映射到 Allure case/step。
- `Utils/allure_reporter.py`：已有环境文件、分类文件写入能力，可继续复用。
- `.venv/Lib/site-packages/allure_commons/*`：当前仓库环境里已有可复用的 runtime API。

## Plan of Work

1. 先新增一个最小 Allure runtime 写入器，把 `P0RunResult` 映射成 `allure-results`。
2. 再在 `run.py` 里接入写入器和 `allure generate`。
3. 最后补单测、修 CLI 输出，并同步 `current_state`。

## Concrete Steps

预计修改文件：

- `run.py`
- `Utils/allure_reporter.py`
- `Utils/allure_runtime.py`（新增）
- `Tests/test_repository.py`
- `docs/current_state.md`
- `plans/allure_auto_html.md`

预计命令：

- `python run.py validate --data examples/reading_house/Data`
- `python -m pytest -q`

当前 shell 无 `python`，上述命令需用户在 Windows `.venv` 中执行。

## Validation and Acceptance

需要验证：

1. CLI 执行后产生：
   - `Reports/allure-results/<run_id>/`
   - `Reports/allure-report/<run_id>/`
2. Allure CLI 缺失时：
   - 终端有 warning
   - 命令退出码仍只由测试执行结果决定
3. `python -m pytest -q` 通过
4. `docs/current_state.md` 已同步“自动 HTML 已接入 / 验证情况”

## Idempotence and Recovery

- `allure-results/<run_id>` 和 `allure-report/<run_id>` 都是按 `run_id` 隔离，可安全重复生成。
- 同一次运行若重复生成 HTML，允许覆盖同一个 `report_dir`。
- 若 Allure CLI 不存在，只保留 `allure-results`，不影响 JSONL history。

## Outcomes & Retrospective

- 已新增 `Utils/allure_runtime.py`，使用 `AllureLifecycle + AllureFileLogger` 直接写 `allure-results`。
- `run.py` 已在写完 JSONL history 后自动导出 Allure 结果和 HTML 报告，并输出目录。
- `run.py` 入口已修回正常 `main()`，不再硬编码 `plan_list`。
- 新增单测覆盖：
  - Allure 原始结果落盘
  - `environment.properties` / `categories.json` 写入
  - CLI 路径与 warning 输出
- 当前 shell 无 `python`，运行时验证需用户在 Windows `.venv` 中执行。
- 若用户环境缺失 `allure` CLI，预期行为是：
  - 原始 `allure-results` 正常生成
  - 终端输出 `allure_warning`
  - 测试退出码不受影响
