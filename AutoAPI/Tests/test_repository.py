from Core.composer import Composer
from Core.context import RuntimeContext
from Core.repository import YamlRepository
from Engine.history_writer import HistoryWriter
from Engine.results import P0RunResult, P0StepResult, PreparedRequest
from Engine.executor import Executor
from Engine.host_resolver import HostResolver
from Engine.request_resolver import RequestResolver
from Engine.transport import TransportBase
from Schema.data_models import ScenarioStep
from Utils.allure_runtime import AllureArtifacts, AllureRuntimeReporter
from run import _emit_allure_artifacts, _print_run_summary
from requests import Response
import base64
from pathlib import Path


class FakeTransport(TransportBase):
    def send(self, req, **kwargs):
        # 返回固定 JSON 响应，避免单测依赖真实接口服务。
        response = Response()
        response.status_code = 200
        response._content = b'{"success": true, "obj": "task-1"}'
        response.headers["Content-Type"] = "application/json"
        response.url = req.url
        return response


class ReadingHouseAuthTransport(TransportBase):
    def __init__(self):
        self.calls = []

    def send(self, req, **kwargs):
        api_id = kwargs.get("api_id")
        self.calls.append({"api_id": api_id, "request": req})
        response = Response()
        response.status_code = 200
        response.headers["Content-Type"] = "application/json"
        response.url = req.url

        if api_id == "api_user_login":
            response._content = b'{"code": 0, "data": {"token": "env-login-token"}}'
            return response

        response._content = b'{"code": 0, "data": {"id": 1, "username": "demo"}}'
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
        "api_login_form",
        "api_submit_multipart_form",
        "api_upload_dataset",
        "api_import_members",
        "api_request_probe",
        "api_raw_payload_probe",
        "api_binary_upload",
    }
    # 校验 cases.yaml 中的接口用例 ID 都被加载到 repo.cases。
    assert set(repo.cases) == {
        "case_start_task_success",
        "case_update_task_member_level_4",
        "case_stop_task_success",
        "case_login_admin",
        "case_submit_multipart_level_4",
        "case_upload_dataset_demo",
        "case_import_members_append",
        "case_probe_with_cookie",
        "case_probe_with_auth_none",
        "case_probe_with_bearer_auth",
        "case_probe_with_basic_auth",
        "case_probe_with_api_key_header",
        "case_probe_with_api_key_query",
        "case_probe_with_api_key_cookie",
        "case_raw_text_payload",
        "case_raw_xml_payload",
        "case_raw_html_payload",
        "case_raw_javascript_payload",
        "case_binary_upload_demo",
    }
    # 校验 Scenarios 目录和 plans.yaml 都被纳入 P0 仓库索引。
    assert set(repo.scenarios) == {"scn_hanoi_main_flow", "scn_hanoi_dataset_flow", "scn_hanoi_hooks_flow"}
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


def test_repository_loads_shared_extracts_and_assertions(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    assert "extract_task_id" in repo.config.shared_extracts
    assert "assert_success" in repo.config.shared_assertions
    assert "assert_context_task_id_exists" in repo.config.shared_assertions


def test_repository_loads_env_auth_profile(reading_house_data_dir):
    repo = YamlRepository(reading_house_data_dir)
    repo.load()

    env = repo.get_env("test_auth")
    assert env.auth_profile == "reading_house_login"
    assert "reading_house_login" in env.auth_profiles
    assert env.auth_profiles["reading_house_login"].setup_cases == ["case_user_login_success"]


def test_composer_case_inherits_template_extract_and_assertions(p0_minimal_data_dir):
    # 加载 P0 最小资产，准备测试模板和用例的合成逻辑。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # Composer 负责把 ApiTemplate + ApiCase 合成为 ExecutableCase。
    composer = Composer(repo.config)

    # 合成启动任务的可执行用例。
    executable = composer.compose_case(
        repo.get_api("api_start_task"),
        repo.get_case("case_start_task_success"),
    )

    # method/path 应从 ApiTemplate 继承，ApiCase 不允许覆盖。
    assert executable.request["method"] == "post"
    assert executable.request["path"] == "/je/orp/scenario/startDs"
    # 新请求模型下，请求体通过 body_mode/raw 表达。
    assert executable.request["body_mode"] == "raw"
    assert executable.request["raw"]["raw_type"] == "json"
    # ApiCase 未覆盖 extract/assertions 时，应展开模板层公共规则引用。
    assert executable.extract_ref == ["extract_task_id"]
    assert executable.assertions_ref == ["assert_success"]
    assert executable.extract[0]["as"] == "taskId"
    assert executable.assertions[0]["jsonpath"] == "$.success"


def test_composer_case_appends_local_rules_after_shared_refs(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    api = repo.get_api("api_start_task")
    case = repo.get_case("case_start_task_success")
    case.extract = [
        {
            "source": "response_json",
            "jsonpath": "$.success",
            "as": "successFlag",
        }
    ]
    case.extract_ref = ["extract_task_id"]
    case.provided_fields.add("extract")
    case.provided_fields.add("extract_ref")

    executable = composer.compose_case(api, case)

    assert [item["as"] for item in executable.extract] == ["taskId", "successFlag"]


def test_composer_step_override_replaces_field_without_deep_merge(p0_minimal_data_dir):
    # 加载 P0 最小资产，准备验证场景步骤 override 的字段级覆盖语义。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    # Composer 同时负责 case 合成和 step override 合成。
    composer = Composer(repo.config)
    # 取主流程场景，用第二个步骤验证 request.raw 覆盖。
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
    assert executable_case.request["raw"] == {
        "raw_type": "json",
        "content": {
            "attrs": {
                "级数设置": {
                    "state": "${level_state}",
                }
            }
        },
    }
    # step 层 raw 被整体替换为 override.raw，不做 deep merge。
    assert executable_step.request["raw"] == {
        "raw_type": "json",
        "content": {
            "attrs": {
                "级数设置": {
                    "state": "4",
                }
            }
        },
    }


def test_composer_step_override_replaces_shared_rule_refs(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable_case = composer.compose_case(
        repo.get_api("api_start_task"),
        repo.get_case("case_start_task_success"),
    )
    step = ScenarioStep(
        id="共享断言覆盖",
        use="case_start_task_success",
        override={
            "assertions_ref": [],
            "assertions": [
                {
                    "source": "response_json",
                    "jsonpath": "$.obj",
                    "op": "exists",
                }
            ],
        },
    )

    executable_step = composer.compose_step(
        executable_case,
        step,
        scenario_id="scn_shared_rules",
    )

    assert executable_step.assertions_ref == []
    assert len(executable_step.assertions) == 1
    assert executable_step.assertions[0]["jsonpath"] == "$.obj"


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
    composer = Composer(repo.config)
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
    # raw(json) 中的变量应被 RuntimeContext 渲染为当前环境变量值。
    assert prepared.kwargs["json"]["scenarioMakeId"] == "demo_scenario_make_id"


def test_request_resolver_renders_query_and_path_params(p0_minimal_data_dir):
    # 加载 P0 资产，准备验证 query 和 path_params 的正式请求构建。
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    ctx = RuntimeContext({
        **repo.get_env("test").variables,
        "taskId": "task-1",
    })

    executable = composer.compose_case(
        repo.get_api("api_stop_task"),
        repo.get_case("case_stop_task_success"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )

    # path_params 应先渲染路径模板，再与 host 拼接成最终 URL。
    assert prepared.url == "http://127.0.0.1:1808/ds/task/op/task-1/stop"
    # stop_task 当前没有 query，请求参数里不应平白出现 params。
    assert "params" not in prepared.kwargs
    # raw(json) 仍应进入 requests 的 json 参数。
    assert prepared.kwargs["json"]["force"] is True


def test_request_resolver_builds_form_urlencoded(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_login_form"),
        repo.get_case("case_login_admin"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.method == "post"
    assert prepared.kwargs["data"] == {
        "username": "admin",
        "password": "admin123",
    }
    assert "files" not in prepared.kwargs


def test_request_resolver_builds_raw_text_with_default_content_type(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_raw_payload_probe"),
        repo.get_case("case_raw_text_payload"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.method == "post"
    assert prepared.kwargs["data"] == "hello raw text"
    assert prepared.kwargs["headers"]["Content-Type"] == "text/plain"
    assert "json" not in prepared.kwargs


def test_request_resolver_builds_raw_xml_and_html_with_default_content_type(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    ctx = RuntimeContext(repo.get_env("test").variables)

    xml_prepared = RequestResolver().resolve_executable(
        composer.compose_case(repo.get_api("api_raw_payload_probe"), repo.get_case("case_raw_xml_payload")),
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )
    html_prepared = RequestResolver().resolve_executable(
        composer.compose_case(repo.get_api("api_raw_payload_probe"), repo.get_case("case_raw_html_payload")),
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )

    assert xml_prepared.kwargs["data"].strip() == "<config>\n  <name>demo</name>\n</config>"
    assert xml_prepared.kwargs["headers"]["Content-Type"] == "application/xml"
    assert html_prepared.kwargs["data"] == "<div>demo</div>"
    assert html_prepared.kwargs["headers"]["Content-Type"] == "text/html"


def test_request_resolver_builds_raw_javascript_and_preserves_explicit_content_type(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable_case = composer.compose_case(
        repo.get_api("api_raw_payload_probe"),
        repo.get_case("case_raw_javascript_payload"),
    )
    default_prepared = RequestResolver().resolve_executable(
        executable_case,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )
    step = ScenarioStep(
        id="raw-js-override",
        use="case_raw_javascript_payload",
        override={
            "request": {
                "headers": {
                    "Content-Type": "application/x-custom-js",
                },
                "raw": {
                    "raw_type": "javascript",
                    "content": 123,
                },
            }
        },
    )

    executable_step = composer.compose_step(
        executable_case,
        step,
        scenario_id="scn_raw_subtypes",
    )

    prepared = RequestResolver().resolve_executable(
        executable_step,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert default_prepared.kwargs["data"] == "console.log('demo');"
    assert default_prepared.kwargs["headers"]["Content-Type"] == "application/javascript"
    assert prepared.kwargs["data"] == "123"
    assert prepared.kwargs["headers"]["Content-Type"] == "application/x-custom-js"


def test_request_resolver_builds_form_data_fields(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_submit_multipart_form"),
        repo.get_case("case_submit_multipart_level_4"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.method == "post"
    assert prepared.kwargs["files"] == [
        ("bizType", (None, "task")),
        ("level", (None, "4")),
    ]
    # 请求快照应该把 multipart 字段摘要化，而不是直接暴露底层 tuple 细节。
    assert prepared.to_dict()["kwargs"]["files"] == [
        {"field": "bizType", "kind": "field", "value": "task"},
        {"field": "level", "kind": "field", "value": "4"},
    ]


def test_request_resolver_builds_form_data_file(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_upload_dataset"),
        repo.get_case("case_upload_dataset_demo"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    field_name, file_part = prepared.kwargs["files"][0]
    assert field_name == "file"
    assert file_part[0] == "upload_demo.txt"
    assert file_part[1] == b"upload demo content\n"
    assert file_part[2] == "text/plain"
    assert prepared.to_dict()["kwargs"]["files"][0]["kind"] == "file"
    assert prepared.to_dict()["kwargs"]["files"][0]["size"] == len(b"upload demo content\n")


def test_composer_step_override_replaces_form_data_field(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable_case = composer.compose_case(
        repo.get_api("api_import_members"),
        repo.get_case("case_import_members_append"),
    )
    step = ScenarioStep(
        id="导入成员-覆盖为覆盖模式",
        use="case_import_members_append",
        override={
            "request": {
                "form_data": [
                    {
                        "kind": "field",
                        "name": "importMode",
                        "value": "overwrite",
                    },
                    {
                        "kind": "file",
                        "name": "file",
                        "path": "examples/p0_minimal/files/upload_demo.txt",
                    },
                ]
            }
        },
    )

    executable_step = composer.compose_step(
        executable_case,
        step,
        scenario_id="scn_form_modes",
    )

    assert executable_case.request["form_data"][0]["value"] == "append"
    assert executable_step.request["form_data"][0]["value"] == "overwrite"


def test_request_resolver_builds_form_data_mixed(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_import_members"),
        repo.get_case("case_import_members_append"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.kwargs["files"][0] == ("importMode", (None, "append"))
    assert prepared.kwargs["files"][1][0] == "file"
    assert prepared.kwargs["files"][1][1][0] == "upload_demo.txt"


def test_request_resolver_passes_explicit_cookies(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_request_probe"),
        repo.get_case("case_probe_with_cookie"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.kwargs["cookies"]["session_id"] == "demo-session"


def test_request_resolver_builds_bearer_auth_header(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_request_probe"),
        repo.get_case("case_probe_with_bearer_auth"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.kwargs["headers"]["Authorization"] == "Bearer demo-token"
    assert prepared.to_dict()["kwargs"]["headers"]["Authorization"] == "***"


def test_request_resolver_keeps_request_clean_when_auth_none(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_request_probe"),
        repo.get_case("case_probe_with_auth_none"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert "Authorization" not in prepared.kwargs.get("headers", {})
    assert "params" not in prepared.kwargs
    assert "cookies" not in prepared.kwargs


def test_request_resolver_builds_basic_auth_header(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_request_probe"),
        repo.get_case("case_probe_with_basic_auth"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    expected = "Basic " + base64.b64encode(b"demo-user:demo-pass").decode("ascii")
    assert prepared.kwargs["headers"]["Authorization"] == expected
    assert prepared.to_dict()["kwargs"]["headers"]["Authorization"] == "***"


def test_request_resolver_builds_api_key_header_query_cookie(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    ctx = RuntimeContext(repo.get_env("test").variables)

    header_req = RequestResolver().resolve_executable(
        composer.compose_case(repo.get_api("api_request_probe"), repo.get_case("case_probe_with_api_key_header")),
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )
    query_req = RequestResolver().resolve_executable(
        composer.compose_case(repo.get_api("api_request_probe"), repo.get_case("case_probe_with_api_key_query")),
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )
    cookie_req = RequestResolver().resolve_executable(
        composer.compose_case(repo.get_api("api_request_probe"), repo.get_case("case_probe_with_api_key_cookie")),
        repo.config.request_defaults,
        ctx,
        repo.get_env("test"),
    )

    assert header_req.kwargs["headers"]["X-Token"] == "demo-token"
    assert query_req.kwargs["params"]["token"] == "demo-token"
    assert cookie_req.kwargs["cookies"]["auth_token"] == "demo-token"
    assert header_req.to_dict()["kwargs"]["headers"]["X-Token"] == "***"
    assert query_req.to_dict()["kwargs"]["params"]["token"] == "***"
    assert cookie_req.to_dict()["kwargs"]["cookies"]["auth_token"] == "***"
    # 当前规则是 auth 注入发生在显式 cookies 之后，因此冲突时 auth 覆盖 cookies。
    assert cookie_req.kwargs["cookies"]["auth_token"] == "demo-token"


def test_request_resolver_builds_binary_body(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    composer = Composer(repo.config)
    executable = composer.compose_case(
        repo.get_api("api_binary_upload"),
        repo.get_case("case_binary_upload_demo"),
    )

    prepared = RequestResolver().resolve_executable(
        executable,
        repo.config.request_defaults,
        RuntimeContext(repo.get_env("test").variables),
        repo.get_env("test"),
    )

    assert prepared.method == "put"
    assert prepared.url == "http://127.0.0.1:1806/files/binary/binary-demo"
    assert prepared.kwargs["data"] == b"binary-demo-123\n"
    assert prepared.kwargs["headers"]["Content-Type"] == "application/octet-stream"
    assert prepared.to_dict()["kwargs"]["data"]["kind"] == "binary"


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
    # 第二步使用 query 接收第一步提取出的 taskId。
    assert result.steps[1].request.kwargs["params"]["taskId"] == "task-1"
    # 第三步使用 path_params，把同一个 taskId 渲染进 URL。
    assert result.steps[2].request.url == "http://127.0.0.1:1808/ds/task/op/task-1/stop"


def test_executor_run_scenario_with_datasets(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    result = Executor(repo).run_scenario(
        "scn_hanoi_dataset_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert len(result.steps) == 6
    assert [step.dataset_name for step in result.steps[:3]] == ["level_3", "level_3", "level_3"]
    assert [step.dataset_name for step in result.steps[3:]] == ["level_5", "level_5", "level_5"]
    assert [step.dataset_index for step in result.steps[:3]] == [1, 1, 1]
    assert [step.dataset_index for step in result.steps[3:]] == [2, 2, 2]
    # 第二轮的上传步骤应使用第二组 dataset 注入的 level_state。
    assert result.steps[1].request.kwargs["json"]["attrs"]["级数设置"]["state"] == "3"
    assert result.steps[4].request.kwargs["json"]["attrs"]["级数设置"]["state"] == "5"


def test_executor_run_scenario_with_hooks_and_finally(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()

    result = Executor(repo).run_scenario(
        "scn_hanoi_hooks_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert [step.step_id for step in result.steps] == [
        "场景前置启动任务",
        "上传任务数据",
        "场景后置停止任务",
        "scenario.assertions",
        "场景兜底停止任务",
    ]
    assert result.steps[3].assertions[0].rule["source"] == "context"


def test_executor_run_scenario_finally_steps_even_when_main_failed(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_hooks_flow")
    scenario.steps[0].override = {
        "assertions": [
            {
                "source": "response_json",
                "jsonpath": "$.success",
                "op": "==",
                "expected": False,
            }
        ]
    }

    result = Executor(repo).run_scenario(
        "scn_hanoi_hooks_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "failed"
    assert [step.step_id for step in result.steps] == [
        "场景前置启动任务",
        "上传任务数据",
        "场景兜底停止任务",
    ]
    assert [step.status for step in result.steps] == ["passed", "failed", "passed"]


def test_executor_run_scenario_assertions_fail_still_runs_finally(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_hooks_flow")
    scenario.assertions_ref = []
    scenario.assertions = [
        {
            "source": "context",
            "jsonpath": "$.missingTaskId",
            "op": "exists",
        }
    ]

    result = Executor(repo).run_scenario(
        "scn_hanoi_hooks_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "failed"
    assert [step.step_id for step in result.steps] == [
        "场景前置启动任务",
        "上传任务数据",
        "场景后置停止任务",
        "scenario.assertions",
        "场景兜底停止任务",
    ]
    assert result.steps[3].status == "failed"
    assert result.steps[4].status == "passed"


def test_executor_run_scenario_hooks_with_datasets_keep_dataset_dimensions(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    scenario = repo.get_scenario("scn_hanoi_dataset_flow")
    scenario.before_steps = [ScenarioStep(id="dataset前置", use="case_start_task_success")]
    scenario.after_steps = [ScenarioStep(id="dataset后置", use="case_stop_task_success")]
    scenario.assertions = [
        {
            "source": "context",
            "jsonpath": "$.taskId",
            "op": "exists",
        }
    ]
    scenario.finally_steps = [ScenarioStep(id="dataset兜底", use="case_stop_task_success")]

    result = Executor(repo).run_scenario(
        "scn_hanoi_dataset_flow",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert len(result.steps) == 14
    assert [step.dataset_index for step in result.steps[:7]] == [1, 1, 1, 1, 1, 1, 1]
    assert [step.dataset_index for step in result.steps[7:]] == [2, 2, 2, 2, 2, 2, 2]
    assert [step.dataset_name for step in result.steps[:7]] == ["level_3"] * 7
    assert [step.dataset_name for step in result.steps[7:]] == ["level_5"] * 7
    assert result.steps[5].step_id == "scenario.assertions"
    assert result.steps[12].step_id == "scenario.assertions"


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


def test_history_writer_persists_dataset_dimensions(tmp_path):
    result = P0RunResult(
        run_id="run-dataset-1",
        target_type="scenario",
        target_id="scn_hanoi_dataset_flow",
        env="test",
        status="passed",
        started_at="2026-04-25T12:00:00",
        ended_at="2026-04-25T12:00:01",
        duration_ms=1000,
        steps=[
            P0StepResult(
                case_id="case_start_task_success",
                api_id="api_start_task",
                status="passed",
                scenario_id="scn_hanoi_dataset_flow",
                dataset_name="level_3",
                dataset_index=1,
                duration_ms=100,
            )
        ],
    )

    HistoryWriter(tmp_path).write_run(result)

    content = (tmp_path / "results.jsonl").read_text(encoding="utf-8")
    assert '"dataset_name": "level_3"' in content
    assert '"dataset_index": 1' in content


def test_executor_runs_env_setup_and_teardown_cases(p0_minimal_data_dir):
    repo = YamlRepository(p0_minimal_data_dir)
    repo.load()
    repo.config.envs["test"].setup_cases = ["case_start_task_success"]
    repo.config.envs["test"].teardown_cases = ["case_stop_task_success"]
    repo.get_env("test").variables["taskId"] = "task-1"

    result = Executor(repo).run_case(
        "case_update_task_member_level_4",
        env_name="test",
        transport=FakeTransport(),
    )

    assert result.status == "passed"
    assert [step.step_id for step in result.steps] == [
        "env.setup.case_start_task_success",
        None,
        "env.teardown.case_stop_task_success",
    ]


def test_executor_runs_env_auth_profile_before_target(reading_house_data_dir):
    repo = YamlRepository(reading_house_data_dir)
    repo.load()
    transport = ReadingHouseAuthTransport()

    result = Executor(repo).run_case(
        "case_user_info_success",
        env_name="test_auth",
        transport=transport,
    )

    assert result.status == "passed"
    assert [item["api_id"] for item in transport.calls] == ["api_user_login", "api_user_info"]
    assert result.steps[0].step_id == "env.auth.setup.case_user_login_success"
    assert result.steps[1].request.kwargs["headers"]["Authorization"] == "env-login-token"


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


def test_allure_runtime_writes_results_and_support_files(tmp_path):
    result = P0RunResult(
        run_id="run-allure-1",
        target_type="case",
        target_id="case_start_task_success",
        env="test",
        status="passed",
        started_at="2026-04-25T10:00:00",
        ended_at="2026-04-25T10:00:01",
        duration_ms=1000,
        steps=[
            P0StepResult(
                case_id="case_start_task_success",
                api_id="api_start_task",
                status="passed",
                request=PreparedRequest(
                    method="post",
                    url="http://127.0.0.1:1806/demo",
                    kwargs={"json": {"hello": "world"}},
                ),
                context_snapshot={"taskId": "task-1"},
                duration_ms=120,
            )
        ],
    )

    runtime = AllureRuntimeReporter(tmp_path)
    artifacts = runtime.export_run(result)

    assert artifacts.results_dir.exists()
    assert (artifacts.results_dir / "environment.properties").exists()
    assert (artifacts.results_dir / "categories.json").exists()
    assert any(path.name.endswith("-result.json") for path in artifacts.results_dir.iterdir())
    # 单测环境不要求存在 allure CLI，因此只验证 warning 路径不会阻止原始结果落盘。
    assert artifacts.report_dir == tmp_path / "allure-report" / "run-allure-1"


def test_emit_allure_artifacts_prints_paths_and_warning(monkeypatch, capsys):
    result = P0RunResult(
        run_id="run-allure-2",
        target_type="scenario",
        target_id="scn_hanoi_main_flow",
        env="test",
        status="passed",
        started_at="2026-04-25T10:00:00",
        ended_at="2026-04-25T10:00:02",
        duration_ms=2000,
    )

    def fake_export_run(self, run_result):
        return AllureArtifacts(
            results_dir=Path("Reports/allure-results/run-allure-2"),
            report_dir=Path("Reports/allure-report/run-allure-2"),
            html_generated=False,
            warning="allure CLI 未安装，已跳过 HTML 报告生成",
        )

    monkeypatch.setattr(AllureRuntimeReporter, "export_run", fake_export_run)

    _emit_allure_artifacts(result)

    output = capsys.readouterr().out
    assert "allure_results: Reports/allure-results/run-allure-2" in output
    assert "allure_report: Reports/allure-report/run-allure-2" in output
    assert "allure_warning: allure CLI 未安装，已跳过 HTML 报告生成" in output
