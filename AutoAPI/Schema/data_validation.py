from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Set, Union

from Exceptions.schema_exception import YamlSchemaException
from Utils.log_utils import LoggerManager

# 日志打印
logger = LoggerManager.get_logger()


@dataclass
class ConfigBundle:
    """
      存储 config.yaml 里面的数据
    """
    active_env: str
    env: Dict[str, Any]
    static: Dict[str, Any]
    request_defaults: Dict[str, Any]
    run_control: Dict[str, Any]
    auth_profiles: Dict[str, Any]


@dataclass
class ApiItem:
    """
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
      存储 multiple.yaml 的数据
    """
    common: Dict[str, Any]
    flow_id: str
    is_run: bool
    auth_profile: str
    steps: List[Dict[str, Any]]
    source: str = ""  # flow 来源定位(文件名#文档序号), 便于多文件/多文档定位


@dataclass
class ValidatedBundle:
    """
      存储校验后的所有 yaml 文件数据
    """
    config: ConfigBundle
    apis: Dict[str, ApiItem]
    flows: Dict[str, FlowBundle]


class YamlSchemaValidator:
    def validate_all(self, config_raw, apis_raw, flows_raw):
        cfg = self._validate_config(config_raw)
        apis = self._validate_apis(apis_raw)
        flows = self._validate_flows(flows_raw)
        return ValidatedBundle(config=cfg, apis=apis, flows=flows)

    def _check_no_edge_blank(self, s: str, where: str):
        """
          校验字符串是否存在首尾空格, 存在则报错
        :param s: 需要校验的字符串
        :param where: 定位路径
        """
        # 去掉首尾空格
        stripped = s.strip()
        # 判断去掉前后是否一致
        if s != stripped:
            # 不一致则报错
            raise YamlSchemaException(f"{where} 含首尾空格: {s!r}, 请改为: {stripped!r}")

    def _check_enum(self, value, allowed: set[str], where: str):
        """
          校验 value 是 非空str 且无首尾空格, 并且必须属于 allowed 枚举集合

          使用场景:
            1.校验 extract.source 的 response_json/response_text等
            2.校验 assertions.op 的 !=/==/<=等
            3.校验 request.request_type 的 params/json等
        :param value: 待校验值
        :param allowed: 允许的枚举集合
        :param where: 定位路径
        """
        # 校验 value 是否为 非空str, 且无首尾空格
        if not isinstance(value, str) or not value.strip():
            raise YamlSchemaException(f"{where} 必须是 非空str")
        self._check_no_edge_blank(value, where)

        # 校验 value 是否存在于 allowed 集合中
        if value not in allowed:
            raise YamlSchemaException(f"{where} 必须是 {sorted(list(allowed))} 之一, 但实际是: {value!r}")

    def _assert_allowed_keys(self, obj: Dict[str, Any], allowed: Set[str], where: str):
        """
          校验 obj 中是否存在 "不被允许(未在 allowed 名单中)" 的字段

          例如：
            obj = {
                "url": "xxx"
                "method": "get"
            }
            allowed = ["url", "get"]

            extra = set(obj.keys()) - set(allowed) = method
            就会抛出异常

        :param obj: 待校验的字典对象
        :param allowed: 允许出现的字段集合
        :param where: 错误定位信息
        """
        extra = set(obj.keys()) - set(allowed)
        if extra:
            raise YamlSchemaException(f"{where} 出现未定义字段")

    # ---------------------------- config.yaml 严格解析 ----------------------------
    def _validate_config(self, raw):
        """
          校验 config.yaml 里的数据
        :param raw: config.yaml 原始数据
        """
        # 校验config.yaml 顶层是否是 dict 类型
        if not isinstance(raw, dict):
            raise YamlSchemaException("config.yaml 顶层必须是 dict 类型")

        # 校验 config.yaml 的顶层 key 是否多写
        self._assert_allowed_keys(
            raw,
            {"env", "active_env", "static", "request_defaults", "run_control", "auth_profiles"},
            "config.yaml"
        )

        # 读取 active_env 对应值, 不存在默认为 None
        active_env = raw.get("active_env", None)
        # 校验 active_env 的值是否为 非空str
        if not isinstance(active_env, str) or not active_env.strip():
            raise YamlSchemaException("config.yaml 必须包含 非空str 的 active_env 字段")

        # 读取 env 对应值, 不存在默认为 None
        env_map = raw.get("env", None)
        if not isinstance(env_map, dict) or not env_map:
            raise YamlSchemaException("config.yaml.env 必须是 非空dict")
        # 校验 active_env 是否存在于配置好的 env 中
        if active_env not in env_map:  # active_env 必须出现在 env_map 里
            raise YamlSchemaException(f"config.yaml.active_env={active_env} 不在 env 列表中")
        # 取当前环境体
        current_env = env_map[active_env]

        # 读取 static, 允许对应值为 None, 并校验是否为 dict
        static = raw.get("static", {})
        if static is None:
            static = {}
        if not isinstance(static, dict):
            raise YamlSchemaException("config.yaml.static 必须是 dict")

        # 读取 request_defaults, 允许对应值为 None, 并校验是否为 dict
        request_defaults = raw.get("request_defaults", {})
        if request_defaults is None:
            request_defaults = {}
        if not isinstance(request_defaults, dict):
            raise YamlSchemaException("config.yaml.request_defaults 必须是 dict")

        # 读取 run_control, 允许对应值为 None, 并校验是否为 dict
        run_control = raw.get("run_control", {})
        if run_control is None:
            run_control = {}
        if not isinstance(run_control, dict):
            raise YamlSchemaException("config.yaml.run_control 必须是 dict")
        # 校验 is_run 字段下的 key
        self._assert_allowed_keys(
            run_control,
            {"is_run", "skip_apis", "only_apis"},
            "config.yaml.run_control"
        )
        # is_run 若写必须 bool
        if "is_run" in run_control and not isinstance(run_control.get("is_run"), bool):
            raise YamlSchemaException("config.yaml.run_control.is_run 必须是 bool")
        # skip_apis 若写必须 list
        if "skip_apis" in run_control and not isinstance(run_control.get("skip_apis"), list):
            raise YamlSchemaException("config.yaml.run_control.skip_apis 必须是 list")
        # only_apis 若写必须 list
        if "only_apis" in run_control and not isinstance(run_control.get("only_apis"), list):
            raise YamlSchemaException("config.yaml.run_control.only_apis 必须是 list")

        # 读取 auth_profiles, 允许对应值为 None, 并校验是否为 dict
        auth_profiles = raw.get("auth_profiles", {})
        if auth_profiles is None:
            auth_profiles = {}
        if not isinstance(auth_profiles, dict):
            raise YamlSchemaException("config.yaml.auth_profiles 必须是 dict")

        # 校验 auth_profiles 下的数据, 遍历每个 profile 并校验
        for p_name, p_body in auth_profiles.items():
            self._validate_auth_profile(p_name, p_body)

        # 构造 config_bundle 返回
        return ConfigBundle(
            active_env=active_env,
            env=current_env,
            static=static,
            request_defaults=request_defaults,
            run_control=run_control,
            auth_profiles=auth_profiles,
        )

    def _validate_auth_profile(self, p_name: str, body):
        """
          校验 auth_profiles.<name>
        :param p_name: key -> auth_profiles.<name>
        :param body: p_name 对应的 value
        """
        # profile 体必须 dict
        if not isinstance(body, dict):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name} 必须是 dict")

        # 每个前置接口底下的首个 key 名必须为 pre_apis
        self._assert_allowed_keys(body, {"pre_apis"}, f"config.yaml.auth_profiles.{p_name}")
        # 读取 pre_apis, value不存在默认为 None, 并校验 pre_apis 必须为 dict 并且非空
        pre_apis = body.get("pre_apis", None)
        if not isinstance(pre_apis, dict) or not pre_apis:
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis 必须是非空 dict")
        # 遍历每个 pre_api 下的 step, 并校验
        for step_name, step_body in pre_apis.items():
            self._validate_auth_step(p_name, step_name, step_body)

    def _validate_auth_step(self, p_name: str, step_name: str, body: Any):
        """
          校验 auth_profiles.<name>.pre_apis.<step>
        :param p_name: auth_profiles.<name>
        :param step_name: pre_apis.<step>
        :param body: step 对应的 value
        """
        # 校验 step 必须为 dict,
        if not isinstance(body, dict):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name} 必须是 dict")
        # 限制 step 下的字段
        self._assert_allowed_keys(
            body,
            {"order", "is_run", "ref", "override", "extract"},
            f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}"
        )
        # is_run 若填则必须为 bool
        is_run = body.get("is_run", None)
        if "is_run" is not None and not isinstance(is_run, bool):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.is_run 若写必须为 bool")
        # order 若写必须 int
        if "order" in body and body.get("order") is not None and not isinstance(body.get("order"), int):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.order 必须是 int 或不写")

        # 读取 ref, 并校验 ref 必须非空字符串, 且无首尾空格
        ref = body.get("ref", None)
        where = f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.ref"
        if not isinstance(ref, str) or not ref.strip():
            raise YamlSchemaException(f"{where} 必须是非空字符串")
        self._check_no_edge_blank(ref, where)

        # 读取 override, 允许对应值为 None, 但若存在必须为 dict
        override = body.get("override", {})
        if override is None:
            # 若为 None 则转为 空dict
            override = {}
        if not isinstance(override, dict):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.override 必须是 dict")

        # 读取 extract, 允许对应值为 None, 但若存在必须为 list
        extract_rules = body.get("extract", [])
        if extract_rules is None:
            # 若为 None 则转为 空list
            extract_rules = []
        if not isinstance(extract_rules, list):
            raise YamlSchemaException(f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.extract 必须是 list")
        # 遍历 extract 规则, 并校验
        for i, rule in enumerate(extract_rules, start=1):
            self._validate_extract_rule(rule, f"config.yaml.auth_profiles.{p_name}.pre_apis.{step_name}.extract[{i}]")

    # --------------------------- single.yaml 校验 ---------------------------
    def _validate_apis(self, raw):
        """
          校验 single.yaml 里的数据
        :param raw: single.yaml 原始数据
        """
        # 顶层结构必须是 dict
        if not isinstance(raw, dict):
            raise YamlSchemaException("single.yaml 顶层必须是 dict")
        # 限制顶层可以存在的 key
        self._assert_allowed_keys(raw, {"apis"}, "single.yaml")
        # 读取 apis, 必须为 非空dict
        apis = raw.get("apis", None)
        if not isinstance(apis, dict) or not apis:
            raise YamlSchemaException("single.yaml.apis 必须是非空 dict")

        # 初始化 API 输出映射
        out: Dict[str, ApiItem] = {}
        # 遍历每个 api, 并校验
        for api_name, body in apis.items():
            # 定位 api 根路径
            where = f"single.yaml.apis.{api_name}"
            # api 名称不允许存在首尾空格
            self._check_no_edge_blank(api_name, where)

            # api 对应的 value 必须为 dict
            if not isinstance(body, dict):
                raise YamlSchemaException(f"{where} 必须是 dict")

            # 读取 case_id, 并校验对应值必须为 非空str, 且不允许首尾空格
            case_id = body.get("case_id", None)
            if not isinstance(case_id, str) or not case_id.strip():
                raise YamlSchemaException(f"{where}.case_id 必须是非空字符串")
            self._check_no_edge_blank(case_id, f"{where}.case_id")

            # 读取 auth_profile, 允许为 None, 若写必须为 str, 且首尾无空格
            auth_profile = body.get("auth_profile", None)
            if auth_profile is not None and not isinstance(auth_profile, str):
                raise YamlSchemaException(f"{where}.auth_profile 必须是字符串或不写")
            if auth_profile is not None:
                self._check_no_edge_blank(auth_profile, f"{where}.auth_profile")

            # 读取 is_run, 允许为 None, 若写必须为 bool
            is_run = body.get("is_run", None)
            if is_run is not None and not isinstance(is_run, bool):
                raise YamlSchemaException(f"{where}.is_run 必须是 bool 或不写")

            # 读取 request, 并校验对应值必须为 dict
            request = body.get("request", None)
            self._validate_request(request, f"{where}.request", is_patch=False)

            # 读取 extract, 对应 value 允许为 None, 若存在必须为 list
            extract_rules = body.get("extract", [])
            if extract_rules is None:
                # 若为 None, 则转为 空list
                extract_rules = []
            if not isinstance(extract_rules, list):
                raise YamlSchemaException(f"{where}.extract 必须是 list")
            # 遍历 extract, 并校验
            self._validate_extract_rules(extract_rules, where=f"{where}.extract")

            # 读取 assertions, 允许对应 value 为 None, 若存在必须为 list
            assertions = body.get("assertions", [])
            if assertions is None:
                # 若为None, 则转为 空list
                assertions = []
            if not isinstance(assertions, list):
                raise YamlSchemaException(f"{where}.assertions 必须是 list")
            # 遍历 assertions, 并校验断言规则
            self._validate_assert_rules(assertions, where=f"{where}.assertions")

            out[api_name] = ApiItem(
                api_id=api_name,
                case_id=case_id,
                auth_profile=auth_profile,
                is_run=is_run,
                request=request,
                extract=extract_rules,
                assertions=assertions
            )

        return out

    # TODO
    def _validate_flows(self, raw: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, FlowBundle]:
        """
          校验业务流里的数据
        :param raw: dict 或 list[dict] 类型; dict 表示只有一个业务流时, list 表示有多个业务流(如多个yaml文件, 或单yaml文件多个 '---')
        """
        # raw 为 dict, 表示是单个 flow
        if isinstance(raw, dict):
            one = self._validate_one_flow(raw, where="flow[1]")
            return {one.flow_id: one}

        # raw 为 list, 表示多个 flow 文档
        if isinstance(raw, list):
            # 初始化输出映射
            out = {}
            # 遍历该文档, 从 1 开始编号
            for i, doc in enumerate(raw, start=1):
                # 校验文档里的单个 flow
                flow = self._validate_one_flow(doc, where=f"flow[{i}]")
                # 若 flow_id 重复则报错
                if flow.flow_id in out:
                    raise YamlSchemaException(f"flow_id 重复: {flow.flow_id}")
                out[flow.flow_id] = flow

            # 若 flows 目录为空 / 全空文档
            if not out:
                raise YamlSchemaException("未加载到任何 flow 文档, 请检查 flows 文件")
            return out

        # 不支持其它类型
        raise YamlSchemaException("flows 数据类型非法: 必须是 dict 或 list[dict]")

    def _validate_one_flow(self, raw: Dict[str, Any], where: str) -> FlowBundle:
        # 顶层必须 dict
        if not isinstance(raw, dict):
            raise YamlSchemaException(f"{where} 顶层必须是 dict")

        # 允许出现的顶层字段
        self._assert_allowed_keys(
            raw,
            {"common", "flow_id", "is_run", "auth_profile", "steps", "_source"},
            "multiple.yaml"
        )

        # 提取内部来源 source 字段(文件#序号), 没有该字段时则为空串
        source = str(raw.get("_source", ""))

        # 读取 common, 允许对应值为 None, 若存在必须为 dict
        common = raw.get("common", {})
        if common is None:
            # 若为 None, 则转为 空dict
            common = {}
        if not isinstance(common, dict):
            raise YamlSchemaException(f"{where}.common 必须是 dict")

        # 读取 flow_id, 对应值必须为 非空str, 且首尾无空格
        flow_id = raw.get("flow_id", None)
        if not isinstance(flow_id, str) or not flow_id.strip():
            raise YamlSchemaException(f"{where}.flow_id 必须是非空字符串")
        self._check_no_edge_blank(flow_id, where)

        # 读取 is_run, 对应值必须为 bool, 不填默认为 True
        is_run = raw.get("is_run", True)
        if not isinstance(is_run, bool):
            raise YamlSchemaException(f"{where}.is_run 若填必须是 bool")

        # 读取 auth_profile, 对应值允许为 None, 若存在必须为 str
        auth_profile = raw.get("auth_profile", None)
        if auth_profile is not None and not isinstance(auth_profile, str):
            raise YamlSchemaException(f"{where}.auth_profile 必须是字符串或不写")
        if auth_profile is not None:
            self._check_no_edge_blank(auth_profile, f"{where}.auth_profile")

        # 读取 steps, 对应值必须为 非空list
        steps = raw.get("steps", None)
        if not isinstance(steps, list) or not steps:
            raise YamlSchemaException(f"{where}.steps 必须是非空 list")
        # 遍历每个 step, 并校验
        for i, step in enumerate(steps, start=1):
            self._validate_step(step, f"{where}.steps[{i}]")

        return FlowBundle(
            common=common,
            flow_id=flow_id,
            is_run=is_run,
            auth_profile=auth_profile,
            steps=steps,
            source=source
        )

    def _validate_step(self, step, where: str):
        """
          校验 multiple.yaml 里的单个 step
        :param step: 待校验的单个 step
        :param where: 定位路径
        """
        # # step 必须 dict
        if not isinstance(step, dict):
            raise YamlSchemaException(f"{where} 必须是 dict")

        # 限制 step 下的字段
        self._assert_allowed_keys(step, {"name", "is_run", "ref", "override"}, where)
        # 读取 ref, 对应值必须为 非空str
        ref = step.get("ref", None)
        if not isinstance(ref, str) or not ref.strip():
            raise YamlSchemaException(f"{where}.ref 必须是非空字符串")

        # name 若写必须为 str
        if "name" in step and step.get("name") is not None and not isinstance(step.get("name"), str):
            raise YamlSchemaException(f"{where}.name 必须是字符串或不写")
        # is_run 若写必须为 bool
        if "is_run" in step and step.get("is_run") is not None and not isinstance(step.get("is_run"), bool):
            raise YamlSchemaException(f"{where}.is_run 必须是 bool 或不写")

        # 读取 override, 对应值允许为 None, 若存在必须为 dict
        override = step.get("override", {})
        if override is None:
            # 为 None 时, 转为 空dict
            override = {}
        if not isinstance(override, dict):
            raise YamlSchemaException(f"{where}.override 必须是 dict")

        # 限制 override 下的字段
        self._assert_allowed_keys(override, {"request", "assertions", "extract"}, f"{where}.override")

        # request 若存在则进行校验
        if "request" in override and override.get("request") is not None:
            self._validate_request(override.get("request"), where=f"{where}.override.request", is_patch=True)

        # extract 若存在则进行校验
        if "extract" in override and override.get("extract") is not None:
            # extract 必须为 list
            if not isinstance(override.get("extract"), list):
                raise YamlSchemaException(f"{where}.override.extract 必须是 list")
            self._validate_extract_rules(override.get("extract"), where=f"{where}.override.extract")

        # assertions 若存在则进行校验
        if "assertions" in override and override.get("assertions") is not None:
            # assertions 必须为 list
            if not isinstance(override.get("assertions"), list):
                raise YamlSchemaException(f"{where}.override.assertions 必须是 list")
            self._validate_assert_rules(override.get("assertions"), where=f"{where}.override.assertions")

    # --------------------------- 通用规则校验 ---------------------------
    def _validate_request(self, request, where: str, is_patch: bool):
        """
          校验 request 下的字段
          注: 除了必要的 method/url/request_type/data 进行校验, 其它参数不再校验
        :param request: request 对应的 值
        :param where: 定位路径
        :param is_patch: 是否为补丁, 是则不需要填 url/method, 否则必填. 比如 multiple.yaml 里的覆盖数据在校验时就不需要完整请求
        """
        # request 必须为 dict
        if not isinstance(request, dict):
            raise YamlSchemaException(f"{where} 必须是 dict")

        # 限制 request 下的字段
        self._assert_allowed_keys(
            request,
            {"method", "url",
             "request_type", "data",
             "headers", "cookies",
             "auth", "timeout",
             "allow_redirects", "proxies",
             "verify", "stream",
             "cert"
             },
            where
        )

        # 允许的 method 值
        allowed_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        # 允许的 request_type 值
        allowed_request_types = {"params", "data", "json", "file"}

        # 若不是补丁, 则需要完整 request 请求
        if not is_patch:
            # 读取 method, 并校验是否错写/漏写
            method = request.get("method", None)
            # 若 method 不为 None, 并且属于 str, 则转换为小写
            if method is not None and isinstance(method, str):
                method = method.lower()
            self._check_enum(method, allowed_methods, where=f"{where}.method")

            # 读取 url, 并校验 url 是否为 非空str, 且首尾无空格
            url = request.get("url", None)
            if not isinstance(url, str) or not url.strip():
                raise YamlSchemaException(f"{where}.url 必须是非空字符串")
            self._check_no_edge_blank(url, where=f"{where}.url")

        # 若为 override.request, 则校验写了 method/url 的情况
        else:
            if "method" in request and request.get("method") is not None:
                self._check_enum(request.get("method"), allowed_methods, where=f"{where}.method")
            if "url" in request and request.get("url") is not None:
                url = request.get("url")
                if not isinstance(url, str) or not url.strip():
                    raise YamlSchemaException(f"{where}.url 必须是非空字符串")
                self._check_no_edge_blank(url, where=f"{where}.url")

        # request_type 若写必须符合四种类型
        if "request_type" in request and request.get("request_type") is not None:
            self._check_enum(request.get("request_type"), allowed_request_types, where=f"{where}.request_type")
        # data 若写, 校验是否正确填写数据
        if "data" in request:
            data_node = request.get("data")
            # 若 data 为 空list, 则报错
            if isinstance(data_node, list) and len(data_node) == 0:
                raise YamlSchemaException(f"{where}.data 为 list 时不能为空")

            # 不是补丁request时, data 非空, 则需校验 request_type 是否也存在
            if not is_patch and data_node is not None:
                if "request_type" not in request or request.get("request_type") is None:
                    raise YamlSchemaException(f"{where}.data 已提供, 但 {where}.request_type 未写")

    def _validate_extract_rules(self, rules: List[Any], where: str):
        """
          对每条 extract rule 调用 _validate_extract_rule
        """
        exist_as = set()
        for i, rule in enumerate(rules, start=1):
            # 构造定位路径
            rule_where = f"{where}[{i}]"
            self._validate_extract_rule(rule, where=rule_where)
            # 存在同名 as 日志报警
            as_name = rule.get("as")
            if as_name in exist_as:
                logger.warning(msg="存在同名 as, 后者已覆盖前者")
            # 将 as 添加进 set 中
            exist_as.add(as_name)

    def _validate_extract_rule(self, rule, where: str):
        """
          校验 extract 的具体规则
        :param rule: extract.[value]
        :param where: 定位路径
        """
        # rule 必须是 dict
        if not isinstance(rule, dict):
            raise YamlSchemaException(f"{where} 必须是 dict")

        # 限制 extract 字段
        self._assert_allowed_keys(rule, {"source", "jsonpath", "as"}, where)

        # 允许提取的数据源
        allowed_sources = {"response_json", "response_text", "response_headers", "response_status"}
        # 校验是否正确填写数据源, 以及格式是否正确
        self._check_enum(rule.get("source"), allowed_sources, where)

        # 提取路径jsonpath 必须为 非空str, 且无首尾空格
        jsonpath = rule.get("jsonpath")
        if not isinstance(jsonpath, str) or not jsonpath.strip():
            raise YamlSchemaException(f"{where}.jsonpath 必须是非空字符串")
        self._check_no_edge_blank(jsonpath, where)

        # 提取的数据 存储名称key: as 必须为 非空str, 且无首尾空格
        as_name = rule.get("as")
        if not isinstance(as_name, str) or not as_name.strip():
            raise YamlSchemaException(f"{where}.as 必须是非空字符串")
        self._check_no_edge_blank(as_name, where)

    def _validate_assert_rules(self, rules: List[Any], where: str):
        """
          对每条 assert rule 调用 _validate_assert_rule
        """
        for i, rule in enumerate(rules, start=1):
            self._validate_assert_rule(rule, f"{where}[{i}]")

    def _validate_assert_rule(self, rule, where: str):
        """
          校验 assertions 的具体规则
        :param rule: assertions.[value]
        :param where: 定位路径
        """
        # rule 必须为 dict
        if not isinstance(rule, dict):
            raise YamlSchemaException(f"{where} 必须是 dict")

        # 限制断言字段
        self._assert_allowed_keys(rule, {"source", "jsonpath", "op", "expected"}, where)
        # 允许提取的数据源
        allowed_sources = {"response_json", "response_text", "response_headers", "response_status"}
        # 校验是否正确填写数据源, 以及格式是否正确
        self._check_enum(rule.get("source"), allowed_sources, f"{where}.source")

        # 提取路径jsonpath 必须为 非空str, 且无首尾空格
        jsonpath = rule.get("jsonpath")
        if not isinstance(jsonpath, str) or not jsonpath.strip():
            raise YamlSchemaException(f"{where}.jsonpath 必须是非空字符串")
        self._check_no_edge_blank(jsonpath, f"{where}.jsonpath")

        # 限制断言条件
        allowed_op = {"exists", "==", "!=", ">", ">=", "<", "<=", "contains", "regex"}
        # 校验断言规则, 必须为 非空str, 且首尾无空格
        op = rule.get("op")
        self._check_enum(op, allowed_op, f"{where}.op")
        if not isinstance(op, str) or not op.strip():
            raise YamlSchemaException(f"{where}.op 必须是非空字符串")
        self._check_no_edge_blank(op, f"{where}.op")

        # expected 必须存在键(允许 expected: null)
        if "expected" not in rule:
            raise YamlSchemaException(f"{where}.expected 必须存在, 在场景不需要 expected 值时, 须填 expected: null")


