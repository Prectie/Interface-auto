from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from Core.repository import YamlRepository
from Engine.results import P0RunResult, P0StepResult
from Engine.executor import Executor
from Engine.history_writer import HistoryWriter
from Exceptions.AutoApiException import AutoApiException
from Utils.allure_runtime import AllureRuntimeReporter


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
    # P0 执行目标互斥：一次命令只允许跑 case/scenario/plan 之一。
    target_group = parser.add_mutually_exclusive_group()
    target_group.add_argument("--case", dest="case_id", help="执行单个 ApiCase")
    target_group.add_argument("--scenario", dest="scenario_id", help="执行单个 Scenario")
    target_group.add_argument("--plan", dest="plan_id", help="执行单个 TestPlan")
    # --env 只影响执行命令，不影响 validate。
    parser.add_argument("--env", dest="env_name", default=None, help="指定运行环境")

    # 子命令入口，P0 先提供 validate。
    subparsers = parser.add_subparsers(dest="command")
    # validate 负责加载并执行 P0 基础资产校验。
    validate_parser = subparsers.add_parser("validate", help="加载并基础校验 P0 YAML 资产")
    # validate 自己也支持 --data，便于写成 AutoAPI validate --data xxx。
    validate_parser.add_argument(
        "--data",
        default=None,
        help="YAML 资产目录，默认使用全局 --data 或 Data",
    )
    return parser


def validate(data_dir: str) -> int:
    # 根据传入目录创建 P0 YAML 仓库。
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


def run_target(data_dir: str, *, case_id: str = None, scenario_id: str = None, plan_id: str = None, env_name: str = None) -> int:
    # 加载并校验 YAML 资产，确保执行前资产关系是可用的。
    repo = YamlRepository(Path(data_dir))
    repo.load()
    executor = Executor(repo)

    # 按用户指定的唯一目标进入不同执行链。
    if case_id:
        result = executor.run_case(case_id, env_name=env_name)
    elif scenario_id:
        result = executor.run_scenario(scenario_id, env_name=env_name)
    elif plan_id:
        result = executor.run_plan(plan_id, env_name=env_name)
    else:
        raise ValueError("必须指定 --case、--scenario 或 --plan")

    # 每次执行都追加结构化历史，方便后续趋势统计。
    HistoryWriter().write_run(result)
    _emit_allure_artifacts(result)
    _print_run_summary(result, sensitive_keys=repo.config.sensitive_keys)
    return 0 if result.status == "passed" else 1


def _emit_allure_artifacts(result: P0RunResult) -> None:
    """
      尝试为当前 run 写入 Allure 原始结果并生成 HTML；失败时只输出 warning。
    """
    try:
        artifacts = AllureRuntimeReporter().export_run(result)
    except Exception as exc:
        print(f"allure_warning: AutoAPI Allure 导出失败: {exc}")
        return

    # 终端输出统一使用 POSIX 风格路径，避免测试和跨平台文档出现分隔符差异。
    print(f"allure_results: {artifacts.results_dir.as_posix()}")
    print(f"allure_report: {artifacts.report_dir.as_posix()}")
    if artifacts.warning:
        print(f"allure_warning: {artifacts.warning}")


def _print_run_summary(result: P0RunResult, *, sensitive_keys: list[str] | None = None) -> None:
    """
      输出一次 P0 执行摘要；失败时补充首个异常步骤的诊断信息。
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


def _first_problem_step(result: P0RunResult) -> P0StepResult | None:
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

    # 当前 P0 CLI 只实现 validate 子命令。
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
    # 将 main 的返回码交给系统退出码，便于 shell/CI 判断执行结果。
    raise SystemExit(main())
