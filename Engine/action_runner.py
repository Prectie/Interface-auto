# -*- coding: utf-8 -*-

"""
  action_runner: hooks 与 Scenario.steps[] 内联 action 共享的执行入口.

  设计要点（Phase C）:
    - kind=wait:   time.sleep(seconds), 不支持 extract.
    - kind=script: subprocess.run 执行命令, 默认 expect_returncode=0,
                   非期望退出码 → ActionOutcome(status="failed").
                   stdout / stderr / returncode 通过 extract 写回 RuntimeContext.
                   extract 第一版只支持 source ∈ {stdout, stderr, returncode}, 整体写入,
                   不做 jsonpath / path 二次提取（保持最小可用面, P2 再扩展）.
    - kind=sql:    P2 才落地真实执行（目标方言 PostgreSQL）,第一版抛 NotImplementedError,
                   让 Executor._classify_error_status 把 step 标记为 "error",
                   避免 YAML 已声明 sql 占位时被静默通过.

  失败语义分层:
    - "failed": 业务期望不符（script returncode != expect_returncode）,
                通过 ActionOutcome(status="failed", error=AssertionError(...)) 表达,
                给上层 Executor 直接落到 StepResult.status="failed".
    - "error":  环境 / 资源 / 未实现 错误（FileNotFoundError, TimeoutExpired, NotImplementedError 等）,
                直接抛异常到 Executor, 由 _classify_error_status 归类为 "error".
                不在本模块吞掉, 让上层 _execute_action_hook 统一处理 traceback 与状态.

  本模块不感知 pytest, 也不依赖 pytest_autoapi, 任何 runner 都可以复用.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

from Core.context import RuntimeContext


# script.extract.source 的合法白名单, 第一版只暴露 subprocess 三大输出.
_SCRIPT_EXTRACT_SOURCES = {"stdout", "stderr", "returncode"}


@dataclass
class ActionOutcome:
    """
      action_runner 的统一返回形态.

      只编码 "业务语义层面的 passed / failed", 不直接构造 StepResult,
      让 Executor 保留对 case_id / api_id / context_snapshot / duration_ms 的组装权.
    """

    status: str  # "passed" | "failed"
    extract_out: Dict[str, Any] = field(default_factory=dict)
    error: Optional[BaseException] = None


def run_action(action: Dict[str, Any], ctx: RuntimeContext) -> ActionOutcome:
    """
      action 主入口: 按 kind 分发到具体执行器.

      :param action: hook.action 或 ScenarioStep.action 原始 dict
      :param ctx:    当前轮 RuntimeContext, script 的 extract 会写回这里
      :return:       ActionOutcome (业务期望不符) 或抛异常 (环境/资源/未实现)
    """
    kind = (action or {}).get("kind")
    if kind == "wait":
        return _run_wait(action)
    if kind == "script":
        return _run_script(action, ctx)
    if kind == "sql":
        # P2 才落地真实执行（目标 PostgreSQL）, 第一版显式 NotImplementedError,
        # 让上层归类为 "error" 而不是被静默通过.
        raise NotImplementedError("hook action 暂未实现: sql")
    raise ValueError(f"hook action.kind 不支持: {kind}")


def _run_wait(action: Dict[str, Any]) -> ActionOutcome:
    seconds = float(action.get("seconds", 0))
    if seconds < 0:
        raise ValueError(f"action.kind=wait 的 seconds 不能为负数: {seconds}")
    time.sleep(seconds)
    return ActionOutcome(status="passed", extract_out={"action": action})


def _run_script(action: Dict[str, Any], ctx: RuntimeContext) -> ActionOutcome:
    args = _resolve_script_args(action)
    cwd = action.get("cwd")
    timeout = action.get("timeout")
    env_overrides = action.get("env") or {}
    expect_rc: Union[int, str] = action.get("expect_returncode", 0)

    proc_env: Optional[Dict[str, str]] = None
    if env_overrides:
        if not isinstance(env_overrides, dict):
            raise ValueError("script.env 必须是 dict")
        # 在当前进程 env 之上叠加, 避免清空 PATH 等关键变量.
        proc_env = {**os.environ, **{str(k): str(v) for k, v in env_overrides.items()}}

    completed = subprocess.run(
        args,
        cwd=cwd,
        env=proc_env,
        timeout=timeout,
        capture_output=True,
        text=True,
        check=False,
    )

    extract_out: Dict[str, Any] = {
        "action": action,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
    }

    # 按 extract 规则把 stdout / stderr / returncode 写回 ctx, 供后续 step / 断言使用.
    extract_rules = action.get("extract") or []
    if extract_rules and not isinstance(extract_rules, list):
        raise ValueError("script.extract 必须是 list")
    for rule in extract_rules:
        if not isinstance(rule, dict):
            raise ValueError(f"script.extract 项必须是 dict: {rule!r}")
        source = rule.get("source")
        as_name = rule.get("as")
        if source not in _SCRIPT_EXTRACT_SOURCES:
            raise ValueError(
                f"script.extract.source 第一版只支持 {sorted(_SCRIPT_EXTRACT_SOURCES)}: {source}"
            )
        if not as_name:
            raise ValueError("script.extract.as 不能为空")
        value = {
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        }[source]
        ctx.set(str(as_name), value)
        extract_out[str(as_name)] = value

    # expect_returncode 校验: "any" 跳过, 数字必须等于退出码.
    if expect_rc == "any":
        return ActionOutcome(status="passed", extract_out=extract_out)
    try:
        expect_int = int(expect_rc)
    except (TypeError, ValueError):
        raise ValueError(
            f"script.expect_returncode 必须是整数或 'any': {expect_rc!r}"
        )
    if completed.returncode != expect_int:
        return ActionOutcome(
            status="failed",
            extract_out=extract_out,
            error=AssertionError(
                f"script returncode={completed.returncode} 不等于 expect_returncode={expect_int}"
            ),
        )
    return ActionOutcome(status="passed", extract_out=extract_out)


def _resolve_script_args(action: Dict[str, Any]) -> List[str]:
    """
      把 script.command 标准化为 subprocess 可接受的参数列表.

      约束（避免 shell 注入）:
        - command: list[str | int] -> 转 str 后直接使用（推荐,跨平台无歧义）
        - command: str             -> 用 shlex.split(posix=True) 拆分.
                                       Windows 路径若含反斜杠,请改用 list 形态或使用正斜杠路径,
                                       以避免被 POSIX 解析当作转义.
        - 其它类型                 -> 抛 ValueError, 防止误用 shell=True 形式.

      为什么强制 posix=True:shlex 的 posix=False 模式（Windows 默认）会把 ", ' 当字面量保留,
      导致 subprocess 拿到 ['"python.exe"', '-c', '"print(1)"'] 这种带引号 token 后报
      FileNotFoundError. 实测下来 posix=True 在 Linux / macOS / Windows（forward-slash 路径）都正确,
      Windows 反斜杠路径强烈建议 list 形态.
    """
    command = action.get("command")
    if command is None or command == "":
        raise ValueError("script.command 不能为空")
    if isinstance(command, list):
        if not command:
            raise ValueError("script.command list 不能为空")
        return [str(item) for item in command]
    if isinstance(command, str):
        parts = shlex.split(command, posix=True)
        if not parts:
            raise ValueError(f"script.command 无法解析为命令参数: {command!r}")
        return parts
    raise ValueError(f"script.command 必须是字符串或字符串列表: {command!r}")
