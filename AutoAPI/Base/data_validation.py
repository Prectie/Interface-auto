from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Set

from Exceptions.schema_exception import YamlSchemaException
from Utils.print_pretty import print_rich
from Utils.yaml_io import load_yaml_file


@dataclass
class ConfigBundle:
    """
      作用：
        存储 config.yaml 里面的数据
    """
    active_env: str
    env: Dict[str, Any]
    static: Dict[str, Any]
    run_control: Dict[str, Any]
    auth_profiles: Dict[str, Any]


@dataclass
class ApiItem:
    """
      作用：
        存储 single.yaml 中每个接口的结构化结果
    """
    api_id: str
    case_id: str
    auth_profile: Optional[str]
    is_run: Optional[bool]
    request: Dict[str, Any]
    extract: List[Dict[str, Any]]
    assertions: List[Dict[str, Any]]


@dataclass
class FlowBundle:
    """
      作用：
        存储 multiple.yaml 的数据
    """
    common: Dict[str, Any]
    flow_id: str
    is_run: bool
    auth_profile: str
    steps: List[Dict[str, Any]]


@dataclass
class ValidatedBundle:
    config: ConfigBundle
    apis: Dict[str, ApiItem]
    flows: FlowBundle


class YamlSchemaValidator:
    def validate_all(self, config_raw, apis_raw, flows_raw):
        cfg = self._validate_config(config_raw)
        apis = self._validate_apis(apis_raw)
        flows = self._validate_flows(flows_raw)
        return ValidatedBundle(config=cfg, apis=apis, flows=flows)

    # ---------------------------- config.yaml 严格解析 ----------------------------
    def _validate_config(self, raw):
        if not isinstance(raw, dict):
            raise YamlSchemaException("config.yaml 顶层必须是 dict 类型")

        self._assert_allowed_keys(raw, {"env", "active_env", "static", "run_control", "auth_profiles"}, "config.yaml")

        active_env = raw.get("active_env", None)
        if not isinstance(active_env, str) or not  active_env.strip():
            raise YamlSchemaException("config.yaml 必须包含非空 str 的 active_env 字段")
        active_env = active_env.strip()

        env_list = raw.get("env", None)
        if not isinstance(env_list, list) or not env_list:
            raise YamlSchemaException("config.yaml 必须包含非空 list 的 env_list 字段")

        env_map: Dict[str, Dict[str, Any]] = {}
        for i, item in enumerate(env_list, start=1):
            if not isinstance(item, dict):
                raise YamlSchemaException(f"config.yaml env[{i}] 必须是 dict")
            env_name = list(item.keys())[0]
            env_body = item[env_name]
            if not isinstance(env_body, dict):
                raise YamlSchemaException(f"config.yaml env[{i}].{env_name} 必须是 dict")
            env_map[env_name] = env_body

        if active_env not in env_map:  # active_env 必须出现在 env_map 里
            raise YamlSchemaException(f"config.yaml.active_env={active_env} 不在 env 列表中")  # 抛出中文异常  #
        current_env = env_map[active_env]  # 取当前环境体

        static = raw.get("static", {})  # 读取 static  #
        if static is None:  # 允许显式 null  #
            static = {}  # 转为空 dict  #
        if not isinstance(static, dict):  # static 必须 dict  #
            raise YamlSchemaException("config.yaml.static 必须是 dict")  # 抛出中文异常  #

        run_control = raw.get("run_control", {})  # 读取 run_control  #
        if run_control is None:  # 允许显式 null  #
            run_control = {}  # 转为空 dict  #
        if not isinstance(run_control, dict):  # run_control 必须 dict  #
            raise YamlSchemaException("config.yaml.run_control 必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(run_control, {"is_run", "skip_apis", "only_apis"}, "config.yaml.run_control")  # 严格限制 run_control 字段  #
        if "is_run" in run_control and not isinstance(run_control.get("is_run"), bool):  # is_run 若写必须 bool  #
            raise YamlSchemaException("config.yaml.run_control.is_run 必须是 bool")  # 抛出中文异常  #
        if "skip_apis" in run_control and not isinstance(run_control.get("skip_apis"), list):  # skip_apis 若写必须 list  #
            raise YamlSchemaException("config.yaml.run_control.skip_apis 必须是 list")  # 抛出中文异常  #
        if "only_apis" in run_control and not isinstance(run_control.get("only_apis"), list):  # only_apis 若写必须 list  #
            raise YamlSchemaException("config.yaml.run_control.only_apis 必须是 list")  # 抛出中文异常  #

        auth_profiles = raw.get("auth_profiles", {})  # 读取 auth_profiles  #
        if auth_profiles is None:  # 允许显式 null  #
            auth_profiles = {}  # 转为空 dict  #
        if not isinstance(auth_profiles, dict):  # auth_profiles 必须 dict  #
            raise YamlSchemaException("config.yaml.auth_profiles 必须是 dict")  # 抛出中文异常  #

        for pname, pbody in auth_profiles.items():  # 遍历每个 profile  #
            self._validate_auth_profile(pname, pbody)  # 严格校验每个 profile  #

        return ConfigBundle(  # 构造 config_bundle 返回  # 返回构造说明
            active_env=active_env,  # 写入 active_env  # 字段说明
            env=current_env,  # 写入当前 env 对象  # 字段说明
            static=static,  # 写入 static  # 字段说明
            run_control=run_control,  # 写入 run_control  # 字段说明
            auth_profiles=auth_profiles,  # 写入 auth_profiles  # 字段说明
        )

    def _validate_auth_profile(self, pname: str, body: Any) -> None:  # 校验 auth_profiles.<name>  #
        if not isinstance(body, dict):  # profile 体必须 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname} 必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(body, {"pre_apis"}, f"config.yaml.auth_profiles.{pname}")  # profile 顶层只允许 pre_apis  #
        pre_apis = body.get("pre_apis", None)  # 读取 pre_apis  #
        if not isinstance(pre_apis, dict) or not pre_apis:  # pre_apis 必须非空 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis 必须是非空 dict")  # 抛出中文异常  #
        for step_name, step_body in pre_apis.items():  # 遍历每个 pre_api step  #
            self._validate_auth_step(pname, step_name, step_body)  # 校验 step  #

    def _validate_auth_step(self, pname: str, step_name: str, body: Any) -> None:  # 校验 pre_apis.<step>  #
        if not isinstance(body, dict):  # step 必须 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name} 必须是 dict")  # 抛出中文异常  #

        self._assert_allowed_keys(body, {"order", "enabled", "ref", "override", "extract"}, f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}")  # 严格限制 step 字段  #
        if "enabled" not in body or not isinstance(body.get("enabled"), bool):  # enabled 必须存在且为 bool  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.enabled 必须显式填写且为 bool")  # 抛出中文异常  #
        if "order" in body and body.get("order") is not None and not isinstance(body.get("order"), int):  # order 若写必须 int  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.order 必须是 int 或不写")  # 抛出中文异常  #

        ref = body.get("ref", None)  # 读取 ref  #
        if not isinstance(ref, str) or not ref.strip():  # ref 必须非空字符串  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.ref 必须是非空字符串")  # 抛出中文异常  #

        override = body.get("override", {})  # 读取 override  #
        if override is None:  # 允许 null  #
            override = {}  # 转空 dict  #
        if not isinstance(override, dict):  # override 必须 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.override 必须是 dict")  # 抛出中文异常  #

        extract_rules = body.get("extract", [])  # 读取 extract  #
        if extract_rules is None:  # 允许 null  #
            extract_rules = []  # 转空 list  #
        if not isinstance(extract_rules, list):  # extract 必须 list  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.extract 必须是 list")  # 抛出中文异常  #
        for i, rule in enumerate(extract_rules, start=1):  # 遍历 extract 规则  #
            self._validate_extract_rule(rule, f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.extract[{i}]")  # 校验规则  #

    # --------------------------- single.yaml 校验 ---------------------------
    def _validate_apis(self, raw):
        if not isinstance(raw, dict):  # 顶层必须 dict  #
            raise YamlSchemaException("single.yaml 顶层必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(raw, {"apis"}, "single.yaml")  # 顶层只允许 apis  #
        apis = raw.get("apis", None)  # 读取 apis  #
        if not isinstance(apis, dict) or not apis:  # apis 必须非空 dict  #
            raise YamlSchemaException("single.yaml.apis 必须是非空 dict")  # 抛出中文异常  #

        out: Dict[str, ApiItem] = {}  # 初始化输出映射  #
        for api_name, body in apis.items():  # 遍历每个 api  #
            api_key = str(api_name).strip()  # 规范化 api key  #
            if not isinstance(body, dict):  # api 体必须 dict  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key} 必须是 dict")  # 抛出中文异常  #

            case_id = body.get("case_id", None)  # 读取 case_id  #
            if not isinstance(case_id, str) or not case_id.strip():  # case_id 必须非空字符串  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.case_id 必须是非空字符串")  # 抛出中文异常  #
            case_id = case_id.strip()  # 去空格  #

            auth_profile = body.get("auth_profile", None)  # 读取 auth_profile  #
            if auth_profile is None:
                auth_profile = ""
            if auth_profile is not None and not isinstance(auth_profile, str):  # 若写必须 str  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.auth_profile 必须是字符串或不写")  # 抛出中文异常  #
            auth_profile = auth_profile.strip()  # 规范化  #

            is_run = body.get("is_run", None)  # 读取 is_run  #
            if is_run is not None and not isinstance(is_run, bool):  # 若写必须 bool  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.is_run 必须是 bool 或不写")  # 抛出中文异常  #

            request = body.get("request", None)  # 读取 request  #
            if not isinstance(request, dict):  # request 必须 dict  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.request 必须是 dict")  # 抛出中文异常  #

            extract_rules = body.get("extract", [])  # 读取 extract  #
            if extract_rules is None:  # 允许 null  #
                extract_rules = []  # 转空 list  #
            if not isinstance(extract_rules, list):  # extract 必须 list  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.extract 必须是 list")  # 抛出中文异常  #
            for i, rule in enumerate(extract_rules, start=1):  # 遍历 extract  #
                self._validate_extract_rule(rule, f"single.yaml.apis.{api_key}.extract[{i}]")  # 校验规则  #

            assertions = body.get("assertions", [])  # 读取 assertions  #
            if assertions is None:  # 允许 null  #
                assertions = []  # 转空 list  #
            if not isinstance(assertions, list):  # assertions 必须 list  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.assertions 必须是 list")  # 抛出中文异常  #
            for i, rule in enumerate(assertions, start=1):  # 遍历断言  #
                self._validate_assert_rule(rule, f"single.yaml.apis.{api_key}.assertions[{i}]")  # 校验断言规则  #

            out[api_key] = ApiItem(
                api_id=api_key,
                case_id=case_id,
                auth_profile=auth_profile,
                is_run=is_run,
                request=request,
                extract=extract_rules,
                assertions=assertions
            )

        return out  # 返回接口库映射  #

    def _validate_flows(self, raw):
        if not isinstance(raw, dict):  # 顶层必须 dict  #
            raise YamlSchemaException("multiple.yaml 顶层必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(raw, {"common", "flow_id", "is_run", "auth_profile", "steps"},
                                  "multiple.yaml")  # 严格限制顶层字段  #

        common = raw.get("common", {})  # 读取 common  #
        if common is None:  # 允许 null  #
            common = {}  # 转空 dict  #
        if not isinstance(common, dict):  # common 必须 dict  #
            raise YamlSchemaException("multiple.yaml.common 必须是 dict")  # 抛出中文异常  #

        flow_id = raw.get("flow_id", None)  # 读取 flow_id  #
        if not isinstance(flow_id, str) or not flow_id.strip():  # flow_id 必须非空  #
            raise YamlSchemaException("multiple.yaml.flow_id 必须是非空字符串")  # 抛出中文异常  #
        flow_id = flow_id.strip()  # 去空格  #

        is_run = raw.get("is_run", True)  # 读取 is_run  #
        if not isinstance(is_run, bool):  # is_run 必须 bool  #
            raise YamlSchemaException("multiple.yaml.is_run 必须是 bool")  # 抛出中文异常  #

        auth_profile = raw.get("auth_profile", None)  # 读取 auth_profile  #
        if auth_profile is not None and not isinstance(auth_profile, str):  # 若写必须 str  #
            raise YamlSchemaException("multiple.yaml.auth_profile 必须是字符串或不写")  # 抛出中文异常  #
        auth_profile = auth_profile.strip() if isinstance(auth_profile, str) else None  # 规范化  #

        steps = raw.get("steps", None)  # 读取 steps  #
        if not isinstance(steps, list) or not steps:  # steps 必须非空 list  #
            raise YamlSchemaException("multiple.yaml.steps 必须是非空 list")  # 抛出中文异常  #
        for i, step in enumerate(steps, start=1):  # 遍历每个 step  #
            self._validate_step(step, f"multiple.yaml.steps[{i}]")  # 严格校验 step  #

        return FlowBundle(
            common=common,
            flow_id=flow_id,
            is_run=is_run,
            auth_profile=auth_profile,
            steps=steps
        )  # 返回结构化结果  #

    def _validate_step(self, step: Any, where: str) -> None:  # 校验单个 step  #
        if not isinstance(step, dict):  # step 必须 dict  #
            raise YamlSchemaException(f"{where} 必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(step, {"name", "is_run", "ref", "override"}, where)  # 严格限制 step 字段  #
        ref = step.get("ref", None)  # 读取 ref  #
        if not isinstance(ref, str) or not ref.strip():  # ref 必须非空  #
            raise YamlSchemaException(f"{where}.ref 必须是非空字符串")  # 抛出中文异常  #
        if "name" in step and step.get("name") is not None and not isinstance(step.get("name"), str):  # name 若写必须 str  #
            raise YamlSchemaException(f"{where}.name 必须是字符串或不写")  # 抛出中文异常  #
        if "is_run" in step and step.get("is_run") is not None and not isinstance(step.get("is_run"), bool):  # is_run 若写必须 bool  #
            raise YamlSchemaException(f"{where}.is_run 必须是 bool 或不写")  # 抛出中文异常  #

        override = step.get("override", {})  # 读取 override  #
        if override is None:  # 允许 null  #
            override = {}  # 转空 dict  #
        if not isinstance(override, dict):  # override 必须 dict  #
            raise YamlSchemaException(f"{where}.override 必须是 dict")  # 抛出中文异常  #

    # --------------------------- 通用规则校验 ---------------------------
    def _validate_extract_rule(self, rule, where: str) -> None:  # 校验 extract 规则  #
        if not isinstance(rule, dict):  # rule 必须 dict  #
            raise YamlSchemaException(f"{where} 必须是 dict")  # 抛出中文异常  #

        self._assert_allowed_keys(rule, {"source", "jsonpath", "as"}, where)  # 严格限制 extract 字段  #
        if not isinstance(rule.get("source"), str) or not str(rule.get("source")).strip():  # source 必须非空 str  #
            raise YamlSchemaException(f"{where}.source 必须是非空字符串")  # 抛出中文异常  #
        if not isinstance(rule.get("jsonpath"), str) or not str(rule.get("jsonpath")).strip():  # jsonpath 必须非空 str  #
            raise YamlSchemaException(f"{where}.jsonpath 必须是非空字符串")  # 抛出中文异常  #
        if not isinstance(rule.get("as"), str) or not str(rule.get("as")).strip():  # as 必须非空 str  #
            raise YamlSchemaException(f"{where}.as 必须是非空字符串")  # 抛出中文异常  #

    def _validate_assert_rule(self, rule: Any, where: str) -> None:  # 校验 assertions 规则  #
        if not isinstance(rule, dict):  # rule 必须 dict  #
            raise YamlSchemaException(f"{where} 必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(rule, {"source", "jsonpath", "op", "expected"}, where)  # 严格限制断言字段（禁止 type/excepted）  #
        if not isinstance(rule.get("source"), str) or not str(rule.get("source")).strip():  # source 必须非空 str  #
            raise YamlSchemaException(f"{where}.source 必须是非空字符串")  # 抛出中文异常  #
        if not isinstance(rule.get("jsonpath"), str) or not str(rule.get("jsonpath")).strip():  # jsonpath 必须非空 str  #
            raise YamlSchemaException(f"{where}.jsonpath 必须是非空字符串")  # 抛出中文异常  #
        if not isinstance(rule.get("op"), str) or not str(rule.get("op")).strip():  # op 必须非空 str  #
            raise YamlSchemaException(f"{where}.op 必须是非空字符串")  # 抛出中文异常  #
        if "expected" not in rule:  # expected 必须存在键（允许 expected: null，但必须写出键）  #
            raise YamlSchemaException(f"{where}.expected 必须存在")  # 抛出中文异常  #

    def _assert_allowed_keys(self, obj: Dict[str, Any], allowed: Set[str], where: str):
        extra = set(obj.keys()) - set(allowed)
        if extra:
            raise YamlSchemaException(f"{where} 出现未定义字段")

