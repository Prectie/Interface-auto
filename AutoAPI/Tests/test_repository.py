from Core.composer import Composer
from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.executor import Executor
from Engine.history_writer import HistoryWriter
from Engine.host_resolver import HostResolver
from Engine.request_resolver import RequestResolver
from Engine.results import P0RunResult, P0StepResult, PreparedRequest
from Engine.transport import TransportBase
from run import _print_run_summary
from requests import Response


class FakeTransport(TransportBase):
    def send(self, req, **kwargs):
        # 返回固定 JSON 响应，避免单测依赖真实接口服务。
        response = Response()
        response.status_code = 200
        response._content = b'{"success": true, "obj": "task-1"}'
        response.headers["Content-Type"] = "application/json"
        response.url = req.url
        return response


def test_repository_loads_p0_minimal_assets(p0_minimal_data_dir):
    # 使用 P0 最小示例数据创建仓库，验证新 YAML 分层结构可以完整加载。
    repo = YamlRepository(p0_minimal_data_dir)
    # load 会读取 config/apis/cases/scenarios/plans 并触发基础校验。
    assets = repo.load()

    # 校验 active_env 被正确读取到 ProjectAssets。
    assert assets.config.active_env == "test"
    # 校验 apis.yaml 中的接口模板 ID 都被加载到 repo.apis。
    assert set(repo.apis) == {
        "api_start_task",
        "api_update_task_member",
        "api_stop_task",
    }
    # 校验 cases.yaml 中的接口用例 ID 都被加载到 repo.cases。
    assert set(repo.cases) == {
        "case_start_task_success",
        "case_update_task_member_level_4",
        "case_stop_task_success",
    }
    # 校验 Scenarios 目录和 plans.yaml 都被纳入 P0 仓库索引。
    assert set(repo.scenarios) == {"scn_hanoi_main_flow"}
    assert set(repo.plans) == {"plan_hanoi_regression"}


def test_repository_get_env_uses_active_env(p0_minimal_data_dir):
    # 创建并加载 P0 仓库，准备读取默认环境。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    # 不传 env_name 时应使用 config.active_env。
    env = repo.get_env()

    # 校验默认环境中的变量池可用于后续请求渲染。
    assert env.variables["scenario_make_id"] == "demo_scenario_make_id"
    # 校验默认环境中的 host key 到 base_url 映射被正确加载。
    assert env.hosts["task_service"] == "http://127.0.0.1:1806"


def test_composer_case_inherits_template_extract_and_assertions(p0_minimal_data_dir):
    # 加载 P0 最小资产，准备测试模板和用例的合成逻辑。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # Composer 负责把 ApiTemplate + ApiCase 合成为 ExecutableCase。
    composer = Composer()

    # 合成启动任务的可执行用例。
    executable = composer.compose_case(
        repo.get_api("api_start_task"),
        repo.get_case("case_start_task_success"),
    )

    # method/path 应从 ApiTemplate 继承，ApiCase 不允许覆盖。
    assert executable.request["method"] == "post"
    assert executable.request["path"] == "/je/orp/scenario/startDs"
    # ApiCase 未覆盖 extract/assertions 时，应继承 ApiTemplate 默认值。
    assert executable.extract[0]["as"] == "taskId"
    assert executable.assertions[0]["jsonpath"] == "$.success"


def test_composer_step_override_replaces_field_without_deep_merge(p0_minimal_data_dir):
    # 加载 P0 最小资产，准备验证场景步骤 override 的字段级覆盖语义。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # Composer 同时负责 case 合成和 step override 合成。
    composer = Composer()
    # 取主流程场景，用第二个步骤验证 request.body 覆盖。
    scenario = repo.get_scenario("scn_hanoi_main_flow")
    step = scenario.steps[1]

    # 先合成 case 层可执行对象，作为 step override 的父级输入。
    executable_case = composer.compose_case(
        repo.get_api("api_update_task_member"),
        repo.get_case("case_update_task_member_level_4"),
    )
    # 再把场景步骤 override 叠加到 ExecutableCase 上。
    executable_step = composer.compose_step(executable_case, step, scenario_id=scenario.id)

    # case 层仍保留变量表达式，说明 step override 没有反向污染 case。
    assert executable_case.request["body"] == {
        "attrs": {
            "级数设置": {
                "state": "${level_state}",
            }
        }
    }
    # step 层 body 被整体替换为 override.body，不做 deep merge。
    assert executable_step.request["body"] == {
        "attrs": {
            "级数设置": {
                "state": "4",
            }
        }
    }


def test_host_resolver_prefers_highest_priority_api_rule(p0_minimal_data_dir):
    # 加载环境配置，准备验证 host_rules 的 priority 裁决。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # 显式读取 test 环境，避免依赖默认环境隐含行为。
    env = repo.get_env("test")

    # api_stop_task 同时可能命中多类规则，应优先选择最高 priority 的 api 规则。
    base_url = HostResolver().resolve_base_url(
        env,
        api_id="api_stop_task",
        module="汉诺塔",
        path="/ds/task/op/stop",
    )

    # stop_task_service 是该示例中最高优先级规则对应的 base_url。
    assert base_url == "http://127.0.0.1:1808"


def test_host_resolver_matches_path_prefix_rule(p0_minimal_data_dir):
    # 加载环境配置，准备验证 path_prefixes 规则。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    env = repo.get_env("test")

    # 未知 api 和空 module 不应命中精确规则，只能依赖 path_prefixes。
    base_url = HostResolver().resolve_base_url(
        env,
        api_id="api_unknown",
        module="",
        path="/ds/other",
    )

    # /ds 前缀应路由到 stop_task_service。
    assert base_url == "http://127.0.0.1:1808"


def test_host_resolver_uses_default_rule(p0_minimal_data_dir):
    # 加载环境配置，准备验证 default 兜底规则。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    env = repo.get_env("test")

    # 当前请求不命中 api/module/path_prefixes，应使用 default host_rule。
    base_url = HostResolver().resolve_base_url(
        env,
        api_id="api_unknown",
        module="",
        path="/other",
    )

    # default 规则应回落到 task_service。
    assert base_url == "http://127.0.0.1:1806"


def test_request_resolver_builds_url_from_host_rules(p0_minimal_data_dir):
    # 加载 P0 资产，准备验证 resolve_executable 的请求构建路径。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # 先通过 Composer 得到 ExecutableCase，再交给 RequestResolver。
    composer = Composer()
    executable = composer.compose_case(
        repo.get_api("api_start_task"),
        repo.get_case("case_start_task_success"),
    )
    # RuntimeContext 使用当前环境变量，负责渲染请求中的 ${scenario_make_id}。
    ctx = RuntimeContext(repo.get_env("test").variables)

    # resolve_executable 应通过 host_rules 解析 base_url，并渲染请求数据。
    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )

    # method 来自 ApiTemplate，不能被 case 或 step 改写。
    assert prepared.method == "post"
    # url 应由 host_rules 的 base_url 和 request.path 拼接得到。
    assert prepared.url == "http://127.0.0.1:1806/je/orp/scenario/startDs"
    # body 中的变量应被 RuntimeContext 渲染为当前环境变量值。
    assert prepared.kwargs["data"]["scenarioMakeId"] == "demo_scenario_make_id"


def test_executor_run_case_with_fake_transport(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    # 使用 FakeTransport 只验证执行链，不依赖真实 HTTP 服务。
    result = Executor(repo).run_case(
        "case_start_task_success",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert result.passed_count == 1
    assert result.steps[0].extract_out["taskId"] == "task-1"


def test_executor_run_scenario_shares_context(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    result = Executor(repo).run_scenario(
        "scn_hanoi_main_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert len(result.steps) == 3
    assert result.steps[1].request.kwargs["params"]["taskId"] == "task-1"


def test_executor_run_plan_and_history_writer(p0_minimal_data_dir, tmp_path):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    result = Executor(repo).run_plan(
        "plan_hanoi_regression",
        env_name="test",
        transport=FakeTransport(),
    )
    HistoryWriter(tmp_path).write_run(result)

    assert result.status == "passed"
    assert len(result.steps) == 4
    assert (tmp_path / "runs.jsonl").exists()
    assert (tmp_path / "results.jsonl").exists()


def test_cli_run_summary_prints_failure_diagnostics(capsys):
    result = P0RunResult(
        run_id="run-1",
        target_type="case",
        target_id="case_start_task_success",
        env="test",
        status="error",
        started_at="2026-04-22T00:00:00",
        ended_at="2026-04-22T00:00:01",
        duration_ms=1000,
        steps=[
            P0StepResult(
                case_id="case_start_task_success",
                api_id="api_start_task",
                status="error",
                request=PreparedRequest(
                    method="post",
                    url="http://127.0.0.1:1806/demo",
                    kwargs={"headers": {"Authorization": "secret-token"}},
                ),
                context_snapshot={"token": "secret-token", "taskId": "task-1"},
                error=RuntimeError("connection refused"),
            )
        ],
    )

    _print_run_summary(result)

    output = capsys.readouterr().out
    assert "first_problem:" in output
    assert "http://127.0.0.1:1806/demo" in output
    assert "connection refused" in output
    assert "secret-token" not in output
