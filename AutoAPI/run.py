from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

import pytest

from Core.repository import YamlRepository
from Engine.results import RunResult, StepResult
from Exceptions.AutoApiException import AutoApiException
from Utils.allure_runtime import AllureArtifacts


def build_parser() -> argparse.ArgumentParser:
    # 创建 AutoAPI 顶层 CLI parser。
    parser = argparse.ArgumentParser(prog="AutoAPI")
    # 全局 --data 指定 YAML 资产目录，所有子命令都可以复用。
    parser.add_argument(
        "--data",
        dest="data_root",
        default="D:/GitHubRepository/Interface-auto/AutoAPI/examples/reading_house/Data",
        help="YAML 资产目录，默认 Data",
    )
    # 执行目标互斥：一次命令只允许跑 case/scenario/plan 之一。
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument("--case", dest="case_id", help="执行单个 ApiCase")
    target_group.add_argument("--scenario", dest="scenario_id", help="执行单个 Scenario")
    target_group.add_argument("--plan", dest="plan_id", help="执行单个 TestPlan")
    # --env 只影响执行命令，不影响 validate。
    parser.add_argument("--env", dest="env_name", default=None, help="指定运行环境")

    # 子命令入口，先提供 validate。
    subparsers = parser.add_subparsers(dest="command")
    # validate 负责加载并执行基础资产校验。
    validate_parser = subparsers.add_parser("validate", help="加载并基础校验 YAML 资产")
    # validate 自己也支持 --data，便于写成 AutoAPI validate --data xxx。
    validate_parser.add_argument(
        "--data",
        default=None,
        help="YAML 资产目录，默认使用全局 --data 或 Data",
    )
    return parser


def validate(data_dir: str) -> int:
    # 根据传入目录创建 YAML 仓库。
    repo = YamlRepository(Path(data_dir))
    # 加载所有资产并触发 validate_project 基础校验。
    repo.load()

    # 读取各类资产 ID，用于输出校验结果摘要。
    ids = repo.list_ids()
    # 校验成功时输出固定提示，便于 CLI/CI 识别。
    print("AutoAPI validate passed")
    # 分别输出各类资产数量，帮助用户确认加载范围。
    print(f"apis: {len(ids['apis'])}")
    print(f"cases: {len(ids['cases'])}")
    print(f"scenarios: {len(ids['scenarios'])}")
    print(f"plans: {len(ids['plans'])}")
    return 0


def run_target(
    data_dir: str,
    *,
    case_id: Optional[str] = None,
    scenario_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    env_name: Optional[str] = None,
) -> int:
    """
      Phase B 后的 CLI 翻译层：把 --case/--scenario/--plan 翻译为 pytest 内核调用。

      关键设计：
      - 提前生成 run_id (uuid hex), 让 alluredir 路径完全可预测,
        ``Reports/allure-results/<run_id>`` 与 v0.1 stdout 字面保持一致;
      - ``-p pytest_autoapi`` 强制加载本框架插件, 不依赖 entry_points 注册;
      - 进程内调用 ``pytest.main([...])``, 让 history / Allure HTML 由 plugin 的
        ``pytest_sessionfinish`` 完成, run.py 只负责打印 v0.1 字面 + 决定 exit code;
      - 通过 ``pytest_autoapi.plugin`` 模块路径访问 LAST_RUN_RESULT 等 holder,
        避免 import 时绑死到 None。
    """
    target = _build_target(case_id=case_id, scenario_id=scenario_id, plan_id=plan_id)
    run_id = uuid.uuid4().hex
    alluredir = Path("Reports/allure-results") / run_id

    pytest_args = [
        "-p",
        "pytest_autoapi",
        "--autoapi-data",
        str(data_dir),
        "--autoapi-target",
        target,
        "--autoapi-run-id",
        run_id,
        "--alluredir",
        str(alluredir),
    ]
    if env_name:
        pytest_args.extend(["--autoapi-env", env_name])
    # 必须把 data_dir 显式作为 collect path 传给 pytest, 覆盖 pyproject.toml 中的
    # ``testpaths = Tests`` 配置, 否则 pytest 只会扫描 Tests/ 目录, AutoAPI 的 YAML
    # 资产 (cases.yaml / Scenarios/*.yaml / plans.yaml) 不会被 collect。
    pytest_args.append(str(data_dir))

    pytest.main(pytest_args)

    # 必须用模块路径访问 plugin 内的 holder, 不能用 ``from ... import LAST_RUN_RESULT``。
    from pytest_autoapi import plugin as autoapi_plugin

    result: Optional[RunResult] = autoapi_plugin.LAST_RUN_RESULT
    artifacts: Optional[AllureArtifacts] = autoapi_plugin.LAST_RUN_ARTIFACTS
    sensitive_keys = list(autoapi_plugin.LAST_SENSITIVE_KEYS)

    if result is None:
        print(
            f"AutoAPI run failed: 未找到目标 {target} 或没有任何 item 被执行",
            file=sys.stderr,
        )
        return 1

    _emit_allure_artifacts(artifacts)
    _print_run_summary(result, sensitive_keys=sensitive_keys)
    return 0 if result.status == "passed" else 1


def _build_target(*, case_id: Optional[str], scenario_id: Optional[str], plan_id: Optional[str]) -> str:
    if case_id:
        return f"case:{case_id}"
    if scenario_id:
        return f"scenario:{scenario_id}"
    if plan_id:
        return f"plan:{plan_id}"
    raise ValueError("必须指定 --case、--scenario 或 --plan")


def _emit_allure_artifacts(artifacts: Optional[AllureArtifacts]) -> None:
    """
      输出 v0.1 风格的 Allure 路径三件套 (allure_results / allure_report / allure_warning)。

      Phase B 后此函数只是 ``stdout 翻译层``: artifacts 由 plugin 在
      ``pytest_sessionfinish`` 内生成并通过 LAST_RUN_ARTIFACTS 暴露; run.py 直接
      接收并打印, 不再持有 AllureRuntimeReporter 调度责任。
    """
    if artifacts is None:
        print("allure_warning: 未生成 Allure 产物 (sessionfinish 未触发)")
        return

    # 终端输出统一使用 POSIX 风格路径，避免测试和跨平台文档出现分隔符差异。
    print(f"allure_results: {artifacts.results_dir.as_posix()}")
    print(f"allure_report: {artifacts.report_dir.as_posix()}")
    if artifacts.warning:
        print(f"allure_warning: {artifacts.warning}")


def _print_run_summary(result: RunResult, *, sensitive_keys: list[str] | None = None) -> None:
    """
      输出一次执行摘要；失败时补充首个异常步骤的诊断信息。
    """
    print(f"AutoAPI run finished: {result.status}")
    print(f"run_id: {result.run_id}")
    print(f"target: {result.target_type}:{result.target_id}")
    print(f"env: {result.env}")
    print(f"passed: {result.passed_count}, failed: {result.failed_count}, error: {result.error_count}")

    problem_step = _first_problem_step(result)
    if problem_step is None:
        return

    print("first_problem:")
    print(f"  case_id: {problem_step.case_id}")
    print(f"  api_id: {problem_step.api_id}")
    if problem_step.scenario_id:
        print(f"  scenario_id: {problem_step.scenario_id}")
    if problem_step.step_id:
        print(f"  step_id: {problem_step.step_id}")
    print(f"  status: {problem_step.status}")

    request_payload = problem_step.request.to_dict() if problem_step.request else None
    response_payload = problem_step.response.to_dict() if problem_step.response else None
    print("  request:")
    _print_indented_json(_mask_sensitive(request_payload, sensitive_keys))
    print("  response:")
    _print_indented_json(_mask_sensitive(response_payload, sensitive_keys))
    print("  context:")
    _print_indented_json(_mask_sensitive(problem_step.context_snapshot, sensitive_keys))

    error_context = getattr(problem_step.error, "error_context", None)
    if error_context is not None:
        error_code = getattr(error_context.error_code, "value", str(error_context.error_code))
        print(f"  error_code: {error_code}")
        print(f"  error_message: {error_context.message}")
        print(f"  error_reason: {_truncate(str(error_context.reason))}")
        if error_context.hint:
            print(f"  error_hint: {error_context.hint}")
    elif problem_step.error is not None:
        print(f"  error_code: {type(problem_step.error).__name__}")
        print(f"  error_message: {_truncate(str(problem_step.error))}")


def _first_problem_step(result: RunResult) -> StepResult | None:
    # 优先返回第一个 failed/error step，保持 CLI 输出稳定。
    return next((item for item in result.steps if item.status != "passed"), None)


def _print_indented_json(payload: Any) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
    for line in body.splitlines():
        print(f"    {line}")


def _mask_sensitive(payload: Any, sensitive_keys: list[str] | None = None) -> Any:
    # CLI 输出失败详情时做最小脱敏，避免 token/cookie 等直接出现在终端。
    keys = {item.lower() for item in (sensitive_keys or [])}
    keys.update({"token", "cookie", "authorization", "password"})

    if isinstance(payload, dict):
        masked = {}
        for key, value in payload.items():
            key_text = str(key).lower()
            if any(sensitive in key_text for sensitive in keys):
                masked[key] = "***"
            else:
                masked[key] = _mask_sensitive(value, sensitive_keys)
        return masked
    if isinstance(payload, list):
        return [_mask_sensitive(item, sensitive_keys) for item in payload]
    return payload


def _truncate(text: str, max_length: int = 1200) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length] + "...<truncated>"


def main(argv: list[str] | None = None) -> int:
    # 构建 CLI parser，argv 为空时 argparse 会读取 sys.argv。
    parser = build_parser()
    # 解析命令行参数。
    args = parser.parse_args(argv)

    # 当前 CLI 只实现 validate 子命令。
    if args.command == "validate":
        try:
            # 子命令 --data 优先；未传时回退到全局 --data。
            return validate(args.data or args.data_root)
        except AutoApiException as exc:
            # AutoAPI 自定义异常已经包含结构化上下文，直接输出到 stderr。
            print(exc, file=sys.stderr)
            return 1
        except Exception as exc:
            # 兜底捕获非预期异常，避免 CLI 直接打印 Python traceback。
            print(f"AutoAPI validate failed: {exc}", file=sys.stderr)
            return 1

    if args.case_id or args.scenario_id or args.plan_id:
        try:
            return run_target(
                args.data_root,
                case_id=args.case_id,
                scenario_id=args.scenario_id,
                plan_id=args.plan_id,
                env_name=args.env_name,
            )
        except AutoApiException as exc:
            print(exc, file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"AutoAPI run failed: {exc}", file=sys.stderr)
            return 1

    # 未指定子命令时展示帮助信息，并用非 0 退出码表示未执行成功命令。
    parser.print_help()
    return 1


if __name__ == "__main__":
    # PyCharm 本地调试模板（默认关闭）:
    # 1) 把 DEBUG_CLI_EXAMPLE 改成下面任意 key；
    # 2) 在 main/run_target/executor 等位置打断点；
    # 3) 直接点 Debug 运行当前文件即可复现对应命令行。
    #
    # 注意:
    # - validate 用法: ["validate", "--data", "..."]
    # - 运行目标用法: ["--scenario", "...", "--env", "...", "--data", "..."]
    # - 默认 None 时保持真实命令行行为（读取 sys.argv）。
    DEBUG_CLI_EXAMPLE = "run_reading_house_public_smoke"
    DEBUG_CLI_ARGS: dict[str, list[str]] = {
        "validate_minimal": [
            "validate",
            "--data",
            "examples/minimal/Data",
        ],
        "validate_reading_house": [
            "validate",
            "--data",
            "examples/reading_house/Data",
        ],
        "run_hanoi_hooks": [
            "--scenario",
            "scn_hanoi_hooks_flow",
            "--env",
            "test",
            "--data",
            "examples/minimal/Data",
        ],
        "run_reading_house_public_smoke": [
            "--scenario",
            "scn_reading_house_public_smoke",
            "--env",
            "test",
            "--data",
            "examples/reading_house/Data",
        ],
        "run_reading_house_auth_flow": [
            "--scenario",
            "scn_reading_house_auth_flow",
            "--env",
            "test",
            "--data",
            "examples/reading_house/Data",
        ],
    }

    argv = DEBUG_CLI_ARGS.get(DEBUG_CLI_EXAMPLE)
    # 将 main 的返回码交给系统退出码，便于 shell/CI 判断执行结果。
    raise SystemExit(main(argv))
