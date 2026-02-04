# -*- coding: utf-8 -*-  # 声明源码编码，避免中文注释乱码  #

from dataclasses import dataclass  # 导入 dataclass，用于结构化保存校验结果  #
from typing import Any, Dict, List, Optional, Set  # 导入类型注解，提升可读性与 IDE 提示  #

from Exceptions.schema_exception import YamlSchemaException  # 导入你现有的 schema 异常类型  #


@dataclass  # 使用 dataclass 自动生成 __init__ 等样板代码  #
class configbundle:  # 定义 config.yaml 校验通过后的结构化对象  #
    active_env: str  # 当前激活环境名  #
    env: Dict[str, Any]  # 当前环境体（例如 host/request_options）  #
    static: Dict[str, Any]  # 静态变量区  #
    run_control: Dict[str, Any]  # 运行控制区  #
    auth_profiles: Dict[str, Any]  # 鉴权模板区（保留原 dict 结构，便于后续执行 pre_apis）  #


@dataclass  # 使用 dataclass 自动生成样板代码  #
class apiitem:  # 定义 single.yaml 每个 api 的结构化对象  #
    api_id: str  # 接口 id（single.yaml.apis 的 key）  #
    case_id: str  # 用例 id（必须存在）  #
    auth_profile: Optional[str]  # 接口级鉴权模板（可选）  #
    is_run: Optional[bool]  # 接口级开关（可选）  #
    request: Dict[str, Any]  # request 段  #
    extract: List[Dict[str, Any]]  # extract 规则列表  #
    assertions: List[Dict[str, Any]]  # assertions 规则列表（严格 op/expected 写法）  #


@dataclass  # 使用 dataclass 自动生成样板代码  #
class flowbundle:  # 定义 multiple.yaml 的结构化对象  #
    common: Dict[str, Any]  # common：Allure 元信息（必须保留给执行层用）  #
    flow_id: str  # 业务流 id  #
    is_run: bool  # flow 开关  #
    auth_profile: Optional[str]  # flow 级鉴权模板（可选）  #
    steps: List[Dict[str, Any]]  # steps 列表（每步已严格校验字段名）  #


@dataclass  # 使用 dataclass 自动生成样板代码  #
class validatedbundle:  # 定义整体校验结果打包对象  #
    config: configbundle  # config 校验结果  #
    apis: Dict[str, apiitem]  # apis 映射校验结果  #
    flow: flowbundle  # flow 校验结果  #


class yamlschemavalidator:  # 定义严格 schema 校验器  #
    """
    目的/作用：
        1) 对 config/single/multiple 三份 yaml 的 raw 数据做严格字段校验；  #
        2) 不做归一化、不做兼容、不做警告；字段写错立刻抛异常；  #
        3) 返回结构化对象，供 repository 缓存后给执行层使用。  #
    """  # 类说明结束  #

    def validate_all(self, config_raw: Any, single_raw: Any, multiple_raw: Any) -> validatedbundle:  # 校验三份 yaml 入口  #
        """
        目的/作用：
            对三份 yaml raw 数据进行严格校验，并返回结构化结果。  #
        参数说明：
            1) config_raw：config.yaml 读取出来的 raw 数据；  #
            2) single_raw：single.yaml 读取出来的 raw 数据；  #
            3) multiple_raw：multiple.yaml 读取出来的 raw 数据；  #
        返回值说明：
            1) validatedbundle：结构化的校验通过结果；  #
        """  # 方法说明结束  #
        cfg = self._validate_config(config_raw)  # 校验 config.yaml 并拿到结构化结果  #
        apis = self._validate_single(single_raw)  # 校验 single.yaml 并拿到接口库映射  #
        flow = self._validate_multiple(multiple_raw)  # 校验 multiple.yaml 并拿到 flow 结果  #
        return validatedbundle(config=cfg, apis=apis, flow=flow)  # 打包返回整体结果  #

    # --------------------------- config.yaml 校验 ---------------------------

    def _validate_config(self, raw: Any) -> configbundle:  # 校验 config.yaml  #
        if not isinstance(raw, dict):  # 顶层必须是 dict  #
            raise YamlSchemaException("config.yaml 顶层必须是 dict")  # 不满足直接报错  #

        self._assert_allowed_keys(raw, {"env", "active_env", "static", "run_control", "auth_profiles"}, "config.yaml")  # 严格限制顶层字段  #

        active_env = raw.get("active_env", None)  # 读取 active_env  #
        if not isinstance(active_env, str) or not active_env.strip():  # 必须非空字符串  #
            raise YamlSchemaException("config.yaml.active_env 必须是非空字符串")  # 抛出中文异常  #
        active_env = active_env.strip()  # 去掉首尾空格  #

        env_list = raw.get("env", None)  # 读取 env 列表  #
        if not isinstance(env_list, list) or not env_list:  # env 必须是非空 list  #
            raise YamlSchemaException("config.yaml.env 必须是非空 list")  # 抛出中文异常  #

        env_map: Dict[str, Dict[str, Any]] = {}  # 初始化 env 映射  #
        for i, item in enumerate(env_list, start=1):  # 遍历 env 列表  #
            if not isinstance(item, dict) or not item:  # 每项必须是非空 dict  #
                raise YamlSchemaException(f"config.yaml.env[{i}] 必须是非空 dict")  # 抛出中文异常  #
            if len(item.keys()) != 1:  # 每项只能有一个 env 名  #
                raise YamlSchemaException(f"config.yaml.env[{i}] 必须且只能包含 1 个 env name")  # 抛出中文异常  #
            env_name = str(list(item.keys())[0])  # 读取 env 名  #
            env_body = item[env_name]  # 读取 env 体  #
            if not isinstance(env_body, dict):  # env 体必须 dict  #
                raise YamlSchemaException(f"config.yaml.env[{i}].{env_name} 必须是 dict")  # 抛出中文异常  #
            self._assert_allowed_keys(env_body, {"host", "request_options"}, f"config.yaml.env[{i}].{env_name}")  # 严格限制 env 体字段  #
            if "host" not in env_body or not isinstance(env_body.get("host"), str) or not str(env_body.get("host")).strip():  # host 必须存在且非空  #
                raise YamlSchemaException(f"config.yaml.env[{i}].{env_name}.host 必须是非空字符串")  # 抛出中文异常  #
            if "request_options" in env_body and env_body.get("request_options") is not None and not isinstance(env_body.get("request_options"), dict):  # request_options 若写必须 dict  #
                raise YamlSchemaException(f"config.yaml.env[{i}].{env_name}.request_options 必须是 dict 或不写")  # 抛出中文异常  #
            env_map[env_name] = env_body  # 写入 env_map  #

        if active_env not in env_map:  # active_env 必须出现在 env_map 里  #
            raise YamlSchemaException(f"config.yaml.active_env={active_env} 不在 env 列表中")  # 抛出中文异常  #
        current_env = env_map[active_env]  # 取当前环境体  #

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
            self._validate_auth_profile(str(pname), pbody)  # 严格校验每个 profile  #

        return configbundle(active_env=active_env, env=current_env, static=static, run_control=run_control, auth_profiles=auth_profiles)  # 返回结构化结果  #

    def _validate_auth_profile(self, pname: str, body: Any) -> None:  # 校验 auth_profiles.<name>  #
        if not isinstance(body, dict):  # profile 体必须 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname} 必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(body, {"pre_apis"}, f"config.yaml.auth_profiles.{pname}")  # profile 顶层只允许 pre_apis  #
        pre_apis = body.get("pre_apis", None)  # 读取 pre_apis  #
        if not isinstance(pre_apis, dict) or not pre_apis:  # pre_apis 必须非空 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis 必须是非空 dict")  # 抛出中文异常  #
        for step_name, step_body in pre_apis.items():  # 遍历每个 pre_api step  #
            self._validate_auth_step(pname, str(step_name), step_body)  # 校验 step  #

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
        self._assert_allowed_keys(override, {"request"}, f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.override")  # override 只允许 request  #
        if "request" in override and override.get("request") is not None and not isinstance(override.get("request"), dict):  # override.request 若写必须 dict  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.override.request 必须是 dict")  # 抛出中文异常  #
        extract_rules = body.get("extract", [])  # 读取 extract  #
        if extract_rules is None:  # 允许 null  #
            extract_rules = []  # 转空 list  #
        if not isinstance(extract_rules, list):  # extract 必须 list  #
            raise YamlSchemaException(f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.extract 必须是 list")  # 抛出中文异常  #
        for i, rule in enumerate(extract_rules, start=1):  # 遍历 extract 规则  #
            self._validate_extract_rule(rule, f"config.yaml.auth_profiles.{pname}.pre_apis.{step_name}.extract[{i}]")  # 校验规则  #

    # --------------------------- single.yaml 校验 ---------------------------

    def _validate_single(self, raw: Any) -> Dict[str, apiitem]:  # 校验 single.yaml  #
        if not isinstance(raw, dict):  # 顶层必须 dict  #
            raise YamlSchemaException("single.yaml 顶层必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(raw, {"apis"}, "single.yaml")  # 顶层只允许 apis  #
        apis = raw.get("apis", None)  # 读取 apis  #
        if not isinstance(apis, dict) or not apis:  # apis 必须非空 dict  #
            raise YamlSchemaException("single.yaml.apis 必须是非空 dict")  # 抛出中文异常  #

        out: Dict[str, apiitem] = {}  # 初始化输出映射  #
        for api_id, body in apis.items():  # 遍历每个 api  #
            api_key = str(api_id).strip()  # 规范化 api key  #
            if not isinstance(body, dict):  # api 体必须 dict  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key} 必须是 dict")  # 抛出中文异常  #

            self._assert_allowed_keys(body, {"case_id", "auth_profile", "is_run", "request", "extract", "assertions"}, f"single.yaml.apis.{api_key}")  # 严格限制 api 字段  #

            case_id = body.get("case_id", None)  # 读取 case_id  #
            if not isinstance(case_id, str) or not case_id.strip():  # case_id 必须非空字符串  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.case_id 必须是非空字符串")  # 抛出中文异常  #
            case_id = case_id.strip()  # 去空格  #

            auth_profile = body.get("auth_profile", None)  # 读取 auth_profile  #
            if auth_profile is not None and not isinstance(auth_profile, str):  # 若写必须 str  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.auth_profile 必须是字符串或不写")  # 抛出中文异常  #
            auth_profile = auth_profile.strip() if isinstance(auth_profile, str) else None  # 规范化  #

            is_run = body.get("is_run", None)  # 读取 is_run  #
            if is_run is not None and not isinstance(is_run, bool):  # 若写必须 bool  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.is_run 必须是 bool 或不写")  # 抛出中文异常  #

            request = body.get("request", None)  # 读取 request  #
            if not isinstance(request, dict):  # request 必须 dict  #
                raise YamlSchemaException(f"single.yaml.apis.{api_key}.request 必须是 dict")  # 抛出中文异常  #
            self._validate_request_block(request, f"single.yaml.apis.{api_key}.request")  # 校验 request 结构  #

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

            out[api_key] = apiitem(api_id=api_key, case_id=case_id, auth_profile=auth_profile, is_run=is_run, request=request, extract=extract_rules, assertions=assertions)  # 构造结果并写入映射  #

        return out  # 返回接口库映射  #

    def _validate_request_block(self, request: Dict[str, Any], where: str) -> None:  # 校验 request 段  #
        self._assert_allowed_keys(request, {"method", "url", "request_type", "data", "headers", "options"}, where)  # 严格限制 request 字段  #
        method = request.get("method", None)  # 读取 method  #
        if not isinstance(method, str) or not method.strip():  # method 必须非空  #
            raise YamlSchemaException(f"{where}.method 必须是非空字符串")  # 抛出中文异常  #
        url = request.get("url", None)  # 读取 url  #
        if not isinstance(url, str) or not url.strip():  # url 必须非空  #
            raise YamlSchemaException(f"{where}.url 必须是非空字符串")  # 抛出中文异常  #
        request_type = request.get("request_type", None)  # 读取 request_type  #
        if not isinstance(request_type, str) or not request_type.strip():  # request_type 必须非空  #
            raise YamlSchemaException(f"{where}.request_type 必须是非空字符串")  # 抛出中文异常  #
        data = request.get("data", [])  # 读取 data  #
        if data is None:  # 允许 null  #
            data = []  # 转空 list  #
        if not isinstance(data, list):  # data 必须 list  #
            raise YamlSchemaException(f"{where}.data 必须是 list")  # 抛出中文异常  #
        headers = request.get("headers", {})  # 读取 headers  #
        if headers is None:  # 允许 null  #
            headers = {}  # 转空 dict  #
        if not isinstance(headers, dict):  # headers 必须 dict  #
            raise YamlSchemaException(f"{where}.headers 必须是 dict")  # 抛出中文异常  #
        options = request.get("options", {})  # 读取 options  #
        if options is None:  # 允许 null  #
            options = {}  # 转空 dict  #
        if not isinstance(options, dict):  # options 必须 dict  #
            raise YamlSchemaException(f"{where}.options 必须是 dict")  # 抛出中文异常  #

    # --------------------------- multiple.yaml 校验 ---------------------------

    def _validate_multiple(self, raw: Any) -> flowbundle:  # 校验 multiple.yaml  #
        if not isinstance(raw, dict):  # 顶层必须 dict  #
            raise YamlSchemaException("multiple.yaml 顶层必须是 dict")  # 抛出中文异常  #
        self._assert_allowed_keys(raw, {"common", "flow_id", "is_run", "auth_profile", "steps"}, "multiple.yaml")  # 严格限制顶层字段  #

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

        return flowbundle(common=common, flow_id=flow_id, is_run=is_run, auth_profile=auth_profile, steps=steps)  # 返回结构化结果  #

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
        self._assert_allowed_keys(override, {"request", "assertions", "extract"}, f"{where}.override")  # 严格限制 override 字段  #
        if "request" in override and override.get("request") is not None and not isinstance(override.get("request"), dict):  # override.request 若写必须 dict  #
            raise YamlSchemaException(f"{where}.override.request 必须是 dict")  # 抛出中文异常  #
        if "extract" in override and override.get("extract") is not None and not isinstance(override.get("extract"), list):  # override.extract 若写必须 list  #
            raise YamlSchemaException(f"{where}.override.extract 必须是 list")  # 抛出中文异常  #
        if "assertions" in override and override.get("assertions") is not None and not isinstance(override.get("assertions"), list):  # override.assertions 若写必须 list  #
            raise YamlSchemaException(f"{where}.override.assertions 必须是 list")  # 抛出中文异常  #

    # --------------------------- 通用规则校验 ---------------------------

    def _validate_extract_rule(self, rule: Any, where: str) -> None:  # 校验 extract 规则  #
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

    def _assert_allowed_keys(self, obj: Dict[str, Any], allowed: Set[str], where: str) -> None:  # 严格字段集合校验  #
        extra = set(obj.keys()) - set(allowed)  # 找出多余字段  #
        if extra:  # 若存在多余字段  #
            raise YamlSchemaException(f"{where} 出现未定义字段：{', '.join(sorted(extra))}；允许字段：{', '.join(sorted(allowed))}")  # 直接抛错要求修改  #
