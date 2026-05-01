# -*- coding: utf-8 -*-

"""
  Phase C 新行为单测:action_runner（wait / script）+ schema 校验 + Executor 端到端调度.

  覆盖面:
    - run_action wait: 0 秒 / 负数 / extract_out 形态
    - run_action script: 退出码 0 / 退出码非 0 默认 failed / expect_returncode 显式 / "any" 跳过
    - run_action script: extract 写回 ctx 的 stdout / stderr / returncode 三个 source
    - run_action script: command 缺失 / extract.source 不合法 / expect_returncode 类型错误
    - run_action sql: 仍然 NotImplementedError（与 Phase D 锁定一致）
    - schema validation: hook + inline action 的 script 字段错误能在 YAML 加载阶段被拦截
    - Executor 端到端: hook script 失败截停主流程; inline script + always_run 仍执行

  本文件不依赖 pytester / 网络 / 真实服务, 用 sys.executable 启动 python 子进程跑命令,
  保证 Windows / Linux / macOS 都可执行（测试在 GitHub CI 与本地 .venv 中行为一致）.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from requests import Response

from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.action_runner import ActionOutcome, run_action
from Engine.executor import Executor
from Engine.transport import TransportBase
from Exceptions.AutoApiException import ValidationException
from Schema.data_models import ScenarioStep


# ---------------------------------------------------------------------------
# 共享工具
# ---------------------------------------------------------------------------


PYTHON = sys.executable  # 用当前解释器跑子进程, 跨平台一致.


class FakeTransport(TransportBase):
    """单测用 transport: 始终返回 200 + 固定 JSON, 让 case 不依赖真实服务。"""

    def send(self, req, **kwargs):
        response = Response()
        response.status_code = 200
        response._content = b'{"success": true, "obj": "task-1"}'
        response.headers["Content-Type"] = "application/json"
        response.url = req.url
        return response


def _write_minimal_repo(
    tmp_path: Path,
    *,
    hooks_yaml: str | None = None,
) -> Path:
    """复制 examples/minimal/Data 到 tmpdir, 让单测可以局部改写 hooks scenario YAML。"""
    src = Path("examples/minimal/Data")
    dst = tmp_path / "Data"
    shutil.copytree(src, dst)
    if hooks_yaml is not None:
        (dst / "Scenarios" / "hanoi_hooks.yaml").write_text(hooks_yaml, encoding="utf-8")
    return dst


# ---------------------------------------------------------------------------
# action_runner.run_action: wait
# ---------------------------------------------------------------------------


def test_run_action_wait_zero_seconds_passes():
    ctx = RuntimeContext()
    outcome = run_action({"kind": "wait", "seconds": 0}, ctx)
    assert isinstance(outcome, ActionOutcome)
    assert outcome.status == "passed"
    assert outcome.error is None
    assert outcome.extract_out["action"] == {"kind": "wait", "seconds": 0}


def test_run_action_wait_negative_seconds_raises_value_error():
    ctx = RuntimeContext()
    with pytest.raises(ValueError) as exc_info:
        run_action({"kind": "wait", "seconds": -1}, ctx)
    assert "seconds 不能为负数" in str(exc_info.value)


# ---------------------------------------------------------------------------
# action_runner.run_action: script - 基础路径
# ---------------------------------------------------------------------------


def test_run_action_script_returncode_zero_passes():
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [PYTHON, "-c", "print('ok')"],
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert outcome.error is None
    assert outcome.extract_out["returncode"] == 0
    assert "ok" in outcome.extract_out["stdout"]


def test_run_action_script_returncode_nonzero_default_fails():
    """默认 expect_returncode=0; 退出码非 0 → status=failed, error 为 AssertionError."""
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [PYTHON, "-c", "import sys; sys.exit(2)"],
        },
        ctx,
    )
    assert outcome.status == "failed"
    assert isinstance(outcome.error, AssertionError)
    assert "returncode=2" in str(outcome.error)
    assert "expect_returncode=0" in str(outcome.error)
    assert outcome.extract_out["returncode"] == 2


def test_run_action_script_explicit_expect_returncode_matches():
    """显式 expect_returncode=2; 退出码同样为 2 → status=passed."""
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [PYTHON, "-c", "import sys; sys.exit(2)"],
            "expect_returncode": 2,
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert outcome.error is None


def test_run_action_script_expect_returncode_any_skips_check():
    """expect_returncode='any' 跳过校验; 任何退出码都视为 passed（覆盖路径 B 能力）."""
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [PYTHON, "-c", "import sys; sys.exit(99)"],
            "expect_returncode": "any",
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert outcome.extract_out["returncode"] == 99


# ---------------------------------------------------------------------------
# action_runner.run_action: script - extract 写回 ctx
# ---------------------------------------------------------------------------


def test_run_action_script_extract_writes_stdout_to_ctx():
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [PYTHON, "-c", "print('hello-from-script')"],
            "extract": [
                {"source": "stdout", "as": "script_out"},
            ],
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert "hello-from-script" in ctx.get("script_out", "")
    assert outcome.extract_out["script_out"] == ctx.get("script_out")


def test_run_action_script_extract_writes_stderr_and_returncode_to_ctx():
    ctx = RuntimeContext()
    outcome = run_action(
        {
            "kind": "script",
            "command": [
                PYTHON,
                "-c",
                "import sys; print('warn-msg', file=sys.stderr); sys.exit(7)",
            ],
            "expect_returncode": 7,
            "extract": [
                {"source": "stderr", "as": "warn"},
                {"source": "returncode", "as": "rc"},
            ],
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert "warn-msg" in ctx.get("warn", "")
    assert ctx.get("rc") == 7


# ---------------------------------------------------------------------------
# action_runner.run_action: script - 输入校验
# ---------------------------------------------------------------------------


def test_run_action_script_command_empty_raises_value_error():
    ctx = RuntimeContext()
    with pytest.raises(ValueError) as exc_info:
        run_action({"kind": "script", "command": ""}, ctx)
    assert "command 不能为空" in str(exc_info.value)


def test_run_action_script_extract_source_invalid_raises_value_error():
    ctx = RuntimeContext()
    with pytest.raises(ValueError) as exc_info:
        run_action(
            {
                "kind": "script",
                "command": [PYTHON, "-c", "print('x')"],
                "extract": [{"source": "result", "as": "x"}],
            },
            ctx,
        )
    assert "stdout" in str(exc_info.value)


def test_run_action_script_expect_returncode_invalid_type_raises_value_error():
    ctx = RuntimeContext()
    with pytest.raises(ValueError) as exc_info:
        run_action(
            {
                "kind": "script",
                "command": [PYTHON, "-c", "print('x')"],
                "expect_returncode": "later",
            },
            ctx,
        )
    assert "expect_returncode" in str(exc_info.value)


def test_run_action_script_command_str_form_uses_shlex_split():
    """
      command: str 形态走 shlex.split(posix=True).

      Windows 上 sys.executable 含反斜杠（C:\\Python\\python.exe）, 在 posix=True 模式下
      会被 shlex 误吃成转义符. 因此 str 形态本身在 Windows 路径含反斜杠的场景下不可靠,
      _resolve_script_args 的 docstring 也明确要求 Windows 用 list 形态. 这里改用正斜杠路径
      绕开 shlex 的反斜杠转义, 同时验证 quoted 路径 + quoted 参数能被正确拆成 3 段 token.
    """
    ctx = RuntimeContext()
    python_forward_slash = PYTHON.replace("\\", "/")
    outcome = run_action(
        {
            "kind": "script",
            "command": f'"{python_forward_slash}" -c "print(123)"',
        },
        ctx,
    )
    assert outcome.status == "passed"
    assert "123" in outcome.extract_out["stdout"]


# ---------------------------------------------------------------------------
# action_runner.run_action: sql 仍未实现
# ---------------------------------------------------------------------------


def test_run_action_sql_still_raises_not_implemented():
    """Phase C 决策: sql 真实执行延后到 P2, 第一版仍 NotImplementedError."""
    ctx = RuntimeContext()
    with pytest.raises(NotImplementedError) as exc_info:
        run_action({"kind": "sql", "datasource": "main_db", "sql": "select 1"}, ctx)
    assert "sql" in str(exc_info.value).lower()


def test_run_action_unknown_kind_raises_value_error():
    ctx = RuntimeContext()
    with pytest.raises(ValueError) as exc_info:
        run_action({"kind": "unknown"}, ctx)
    assert "kind 不支持" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Schema validation: hook + inline action 共用同一份 script schema
# ---------------------------------------------------------------------------


def test_repository_rejects_script_action_without_command(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "before_steps:\n"
        "  - id: 缺少 command\n"
        "    action:\n"
        "      kind: script\n"
        "steps:\n"
        "  - id: 启动\n"
        "    use: case_start_task_success\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)
    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()
    assert "command" in exc_info.value.error_context.reason


def test_repository_rejects_script_action_with_invalid_expect_returncode(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "steps:\n"
        "  - id: 启动\n"
        "    use: case_start_task_success\n"
        "  - id: 非法 expect_returncode\n"
        "    action:\n"
        "      kind: script\n"
        "      command: ['echo', 'x']\n"
        "      expect_returncode: maybe\n"
        "    always_run: true\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)
    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()
    assert "expect_returncode" in exc_info.value.error_context.reason


def test_repository_rejects_script_action_with_invalid_extract_source(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "steps:\n"
        "  - id: 启动\n"
        "    use: case_start_task_success\n"
        "  - id: 非法 extract source\n"
        "    action:\n"
        "      kind: script\n"
        "      command: ['echo', 'x']\n"
        "      extract:\n"
        "        - source: result\n"
        "          as: x\n"
        "    always_run: true\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)
    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()
    assert "stdout" in exc_info.value.error_context.reason


def test_repository_accepts_minimal_hanoi_hooks_with_script_actions(minimal_data_dir):
    """examples/minimal 自身演示了 hook + inline script, 必须能 load 通过 schema 校验。"""
    repo = YamlRepository(minimal_data_dir)
    repo.load()  # 不抛异常即通过


# ---------------------------------------------------------------------------
# Executor 端到端: hook script + inline script 调度链路
# ---------------------------------------------------------------------------


def test_executor_hook_script_failure_halts_main_steps_but_always_run_runs(minimal_data_dir):
    """before_steps 中 script 退出码非 0 → 主 step 全部跳过, always_run step 仍执行."""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")

    from Schema.data_models import HookStep

    scenario.before_steps = [
        HookStep(
            id="失败的 hook script",
            action={
                "kind": "script",
                "command": [PYTHON, "-c", "import sys; sys.exit(3)"],
            },
            raw={"id": "失败的 hook script"},
        ),
    ]
    scenario.steps = [
        ScenarioStep(
            id="不应执行的普通 step",
            use="case_start_task_success",
        ),
        ScenarioStep(
            id="兜底脚本（always_run）",
            action={
                "kind": "script",
                "command": [PYTHON, "-c", "print('cleanup ok')"],
            },
            always_run=True,
        ),
    ]
    scenario.assertions_ref = []
    scenario.assertions = []
    scenario.after_steps = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    step_ids = [step.step_id for step in result.steps]
    # hook script 失败截停, 普通 step 全部跳过, always_run step 仍执行.
    assert "失败的 hook script" in step_ids
    assert "兜底脚本（always_run）" in step_ids
    assert "不应执行的普通 step" not in step_ids
    # 最终状态为 failed（hook 退出码不匹配触发 AssertionError → status=failed）.
    assert result.status == "failed"


def test_executor_inline_script_always_run_after_main_failure(minimal_data_dir):
    """主 step 失败后, inline script always_run step 仍然执行并把 stdout 写回 ctx."""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")

    failing_step = ScenarioStep(
        id="故意失败-启动任务",
        use="case_start_task_success",
        override={
            "assertions": [
                {
                    "source": "response_json",
                    "jsonpath": "$.success",
                    "op": "==",
                    "expected": False,
                }
            ]
        },
    )
    scenario.before_steps = []
    scenario.steps = [
        failing_step,
        ScenarioStep(
            id="清理脚本（always_run）",
            action={
                "kind": "script",
                "command": [PYTHON, "-c", "print('CLEANUP')"],
                "extract": [{"source": "stdout", "as": "cleanup_marker"}],
            },
            always_run=True,
        ),
    ]
    scenario.after_steps = []
    scenario.assertions_ref = []
    scenario.assertions = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    step_ids = [step.step_id for step in result.steps]
    assert step_ids == ["故意失败-启动任务", "清理脚本（always_run）"]
    cleanup_step = result.steps[1]
    assert cleanup_step.status == "passed"
    assert "CLEANUP" in cleanup_step.context_snapshot.get("cleanup_marker", "")
    assert result.status == "failed"
