# -*- coding: utf-8 -*-

"""
  Phase D 新行为单测：覆盖 v0.2 schema 收敛带来的所有可观察变化。

  覆盖面：
    - 旧字段拒绝：cases.<id>.{api, before_steps, after_steps} / scenarios.<id>.finally_steps
    - ScenarioStep.use ↔ action XOR 互斥（缺一 / 同填）
    - always_run：前序失败仍跑
    - continue_on_error：失败不截停后续
    - inline action：kind=wait 走通；kind=sql 走 _execute_action_hook 同一份"暂未实现" 路径
    - context overlay：env → dataset → extract 三层叠加, 多轮 dataset 之间 extract 不串
"""

from __future__ import annotations

from pathlib import Path

import pytest
from requests import Response

from Core.repository import YamlRepository
from Engine.executor import Executor
from Engine.transport import TransportBase
from Exceptions.AutoApiException import ValidationException
from Schema.data_models import ScenarioStep


class FakeTransport(TransportBase):
    """单测用 transport: 始终返回 200 + 固定 JSON, 让 case 不依赖真实服务。"""

    def send(self, req, **kwargs):
        response = Response()
        response.status_code = 200
        response._content = b'{"success": true, "obj": "task-1"}'
        response.headers["Content-Type"] = "application/json"
        response.url = req.url
        return response


# ---------------------------------------------------------------------------
# 旧字段拒绝
# ---------------------------------------------------------------------------


def _write_minimal_repo(tmp_path: Path, *, cases_yaml: str | None = None, hooks_yaml: str | None = None) -> Path:
    """从 examples/minimal/Data 复制一份到 tmp_path, 让单测可以局部改 YAML。"""
    import shutil

    src = Path("examples/minimal/Data")
    dst = tmp_path / "Data"
    shutil.copytree(src, dst)
    if cases_yaml is not None:
        (dst / "cases.yaml").write_text(cases_yaml, encoding="utf-8")
    if hooks_yaml is not None:
        (dst / "Scenarios" / "hanoi_hooks.yaml").write_text(hooks_yaml, encoding="utf-8")
    return dst


def test_repository_rejects_legacy_cases_api_field(tmp_path):
    cases_yaml = (
        "cases:\n"
        "  case_legacy_api:\n"
        "    api: api_start_task\n"
    )
    data_dir = _write_minimal_repo(tmp_path, cases_yaml=cases_yaml)

    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()

    assert "cases.case_legacy_api.api 已废弃" in exc_info.value.error_context.reason
    assert "use" in exc_info.value.error_context.hint


def test_repository_rejects_legacy_case_before_steps(tmp_path):
    cases_yaml = (
        "cases:\n"
        "  case_legacy_hook:\n"
        "    use: api_start_task\n"
        "    before_steps:\n"
        "      - id: 旧 hook\n"
        "        action: {kind: wait, seconds: 0}\n"
    )
    data_dir = _write_minimal_repo(tmp_path, cases_yaml=cases_yaml)

    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()

    assert "before_steps 已废弃" in exc_info.value.error_context.reason


def test_repository_rejects_legacy_scenario_finally_steps(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "steps:\n"
        "  - id: 启动任务\n"
        "    use: case_start_task_success\n"
        "finally_steps:\n"
        "  - id: 兜底\n"
        "    action: {kind: wait, seconds: 0}\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)

    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()

    assert "finally_steps 已废弃" in exc_info.value.error_context.reason
    assert "always_run" in exc_info.value.error_context.hint


# ---------------------------------------------------------------------------
# ScenarioStep use ↔ action XOR
# ---------------------------------------------------------------------------


def test_repository_rejects_step_with_both_use_and_action(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "steps:\n"
        "  - id: 同时填了 use 和 action\n"
        "    use: case_start_task_success\n"
        "    action: {kind: wait, seconds: 0}\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)

    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()

    assert "use 和 action" in exc_info.value.error_context.reason


def test_repository_rejects_step_with_neither_use_nor_action(tmp_path):
    hooks_yaml = (
        "scenario_id: scn_hanoi_hooks_flow\n"
        "env: test\n"
        "steps:\n"
        "  - id: 啥都没填\n"
    )
    data_dir = _write_minimal_repo(tmp_path, hooks_yaml=hooks_yaml)

    with pytest.raises(ValidationException) as exc_info:
        YamlRepository(data_dir).load()

    assert "XOR" in exc_info.value.error_context.reason


# ---------------------------------------------------------------------------
# always_run / continue_on_error / inline action 调度
# ---------------------------------------------------------------------------


def _make_failing_step(use: str) -> ScenarioStep:
    """构造一个一定 failed 的普通 step（断言 success == False, 但 FakeTransport 返回 success=true）。"""
    return ScenarioStep(
        id=f"故意失败-{use}",
        use=use,
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


def test_executor_always_run_step_runs_after_normal_step_failure(minimal_data_dir):
    """普通 step 失败后，always_run step 仍执行。"""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")
    scenario.steps = [
        _make_failing_step("case_start_task_success"),
        ScenarioStep(
            id="清理（always_run）",
            action={"kind": "wait", "seconds": 0},
            always_run=True,
        ),
    ]
    scenario.assertions_ref = []
    scenario.assertions = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "failed"
    assert [step.step_id for step in result.steps] == [
        "故意失败-case_start_task_success",
        "清理（always_run）",
    ]
    assert result.steps[1].status == "passed"


def test_executor_continue_on_error_step_does_not_halt_following_steps(minimal_data_dir):
    """continue_on_error=True 的 step 失败后，下一个普通 step 仍然执行。"""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")
    failing = _make_failing_step("case_start_task_success")
    failing.continue_on_error = True
    scenario.steps = [
        failing,
        ScenarioStep(
            id="后续普通 step",
            use="case_start_task_success",
        ),
    ]
    scenario.assertions_ref = []
    scenario.assertions = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    # 第一个 step 失败但被允许继续, 第二个普通 step 仍被执行。
    assert [step.step_id for step in result.steps] == [
        "故意失败-case_start_task_success",
        "后续普通 step",
    ]
    assert result.steps[0].status == "failed"
    assert result.steps[1].status == "passed"
    # scenario 整体仍然是 failed，因为有 step 失败。
    assert result.status == "failed"


def test_executor_inline_action_wait_runs_through_hook_kernel(minimal_data_dir):
    """inline action(kind=wait) 走 _execute_action_hook 同一内核, 与 hooks 行为等价。"""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")
    scenario.steps = [
        ScenarioStep(
            id="inline 等待",
            action={"kind": "wait", "seconds": 0},
        ),
    ]
    scenario.assertions_ref = []
    scenario.assertions = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert len(result.steps) == 1
    assert result.steps[0].step_id == "inline 等待"
    assert result.steps[0].extract_out["action"]["kind"] == "wait"


def test_executor_inline_action_sql_returns_not_implemented_error(minimal_data_dir):
    """inline action(kind=sql) 在 Phase C 实现前应返回明确的 error 状态, 而不是静默通过。"""
    repo = YamlRepository(minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_main_flow")
    scenario.steps = [
        ScenarioStep(
            id="inline sql 清理",
            action={"kind": "sql", "datasource": "main_db", "sql": "delete from t"},
        ),
    ]
    scenario.assertions_ref = []
    scenario.assertions = []

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "error"
    assert result.steps[0].step_id == "inline sql 清理"
    assert "暂未实现" in str(result.steps[0].error)


# ---------------------------------------------------------------------------
# Context overlay: env → dataset → extract
# ---------------------------------------------------------------------------


def test_executor_context_overlay_isolates_extract_across_datasets(minimal_data_dir):
    """
      验证 context overlay 三层叠加：
        - env.variables 是基础层
        - dataset.variables 在每轮覆盖 env
        - 上一轮 extract 出的变量不应泄漏到下一轮（fork/snapshot 隔离）
    """
    repo = YamlRepository(minimal_data_dir)
    repo.load()

    result = Executor(repo).run_scenario(
        "scn_hanoi_dataset_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    # 每轮 dataset 的 level_state 都应被本轮 dataset.variables 覆盖, 不被上轮污染。
    # level_3 dataset 的 update step 渲染出的 state 应是本轮 level_state="3"。
    assert result.steps[1].request.kwargs["json"]["attrs"]["级数设置"]["state"] == "3"
    # level_5 dataset 的 update step 渲染出的 state 应是本轮 level_state="5", 不会回到第一轮的 "3"。
    assert result.steps[4].request.kwargs["json"]["attrs"]["级数设置"]["state"] == "5"
    # 第二轮的 ctx 仍能看到 env 层 scenario_make_id="demo_scenario_make_id"（基础层）。
    assert result.steps[3].context_snapshot["scenario_make_id"] == "demo_scenario_make_id"


def _is_minimal_data_dir():
    return Path("examples/minimal/Data").exists()


@pytest.mark.skipif(not _is_minimal_data_dir(), reason="examples/minimal/Data 不可用")
def test_validate_cli_passes_after_schema_convergence(minimal_data_dir):
    """schema 收敛后, examples/minimal 自身应可被 validator 通过, 防止资产与 schema 漂移。"""
    repo = YamlRepository(minimal_data_dir)
    assets = repo.load()
    repo._validator.validate_project(assets)
