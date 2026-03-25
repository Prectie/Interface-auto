from dataclasses import dataclass
from typing import Dict, Any, Optional, List, Set, Union

from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
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
    auth_profiles: Dict[str, List[Dict[str, Any]]]


@dataclass
class ApiItem:
    """
      存储 single.yaml 中每个接口的结构化结果
    """
    api_id: str
    auth_profile: Optional[str]
    is_run: Optional[bool]
    depends_on: List[Dict[str, Any]]
    request: Dict[str, Any]
    extract: List[Dict[str, Any]]
    assertions: List[Dict[str, Any]]
    cleanup: Optional[Dict[str, Any]]


@dataclass
class FlowBundle:
    """
      存储 multiple.yaml 的数据
    """
    common: Dict[str, Any]
    flow_id: str
    is_run: bool
    auth_profile: Optional[str]
    steps: List[Dict[str, Any]]
    cleanup: Optional[Dict[str, Any]]
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

    def _raise_validation_exception(
        self,
        *,
        reason: str,
        yaml_location: Optional[str] = None,
        hint: str = "请检查 YAML 字段与类型是否符合规范",
        extra: Optional[Dict[str, Any]] = None
    ):
        """
          统一抛出 校验失败 的异常
        :param reason: 失败原因
        :param yaml_location: YAML 定位路径
        :param hint: 修复建议
        :param extra: 扩展上下文
        """
        # 构建明确异常上下文
        error_context = build_api_exception_context(
            error_code=ExceptionCode.VALIDATION_ERROR,
            message="YAML 结构校验失败",
            reason=reason,
            yaml_location=yaml_location,
            hint=hint,
            extra=extra
        )
        raise ValidationException(error_context)

    def _check_no_edge_blank(self, s: str, yaml_location: str):
        """
          校验字符串是否存在首尾空格, 存在则报错
        :param s: 需要校验的字符串
        :param yaml_location: 定位路径
        """
        # 去掉首尾空格
        stripped = s.strip()
        # 判断去掉前后是否一致
        if s != stripped:
            # 不一致则报错
            self._raise_validation_exception(
                reason=f"{yaml_location} 含首尾空格: {s!r}",
                yaml_location=yaml_location,
                hint=f"请将 {s}, 改为: {stripped!r}"
            )

    def _check_enum(self, value, allowed: set[str], yaml_location: str):
        """
          校验 value 是 非空str 且无首尾空格, 并且必须属于 allowed 枚举集合

          使用场景:
            1.校验 extract.source 的 response_json/response_text等
            2.校验 assertions.op 的 !=/==/<=等
            3.校验 request.request_type 的 params/json等
        :param value: 待校验值
        :param allowed: 允许的枚举集合
        :param yaml_location: 定位路径
        """
        # 校验 value 是否为 非空str, 且无首尾空格
        if not isinstance(value, str) or not value.strip():
            self._raise_validation_exception(
                reason=f"{yaml_location} 必须是非空str",
                yaml_location=yaml_location,
                hint=f"请将该值改为非空 str"
            )
        self._check_no_edge_blank(value, yaml_location)

        # 校验 value 是否存在于 allowed 集合中
        if value not in allowed:
            self._raise_validation_exception(
                reason=f"{yaml_location} 必须是 {sorted(list(allowed))} 之一, 但实际是: {value!r}",
                yaml_location=yaml_location,
                hint=f"请检查填入的值是否符合规范"
            )

    def _assert_allowed_keys(self, obj: Dict[str, Any], allowed: Set[str], yaml_location: str):
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
        :param yaml_location: 错误处的精确定位路径
        """
        extra = set(obj.keys()) - set(allowed)
        if extra:
            self._raise_validation_exception(
                reason=f"{yaml_location} 出现未定义字段: {set(extra)}",
                yaml_location=yaml_location,
                hint=f"请检查填入的值是否符合规范, 符合规范的值如下: {set(allowed)}"
            )

    # ---------------------------- config.yaml 严格解析 ----------------------------
    def _validate_config(self, raw):
        """
          校验 config.yaml 里的数据
        :param raw: config.yaml 原始数据
        """
        if not raw:
            self._raise_validation_exception(
                reason="config.yaml 为空",
                hint="请检查 config.yaml 里是否存在数据"
            )

        # 校验config.yaml 顶层是否是 dict 类型
        if not isinstance(raw, dict):
            self._raise_validation_exception(
                reason="config.yaml 顶层必须是 dict 类型",
                hint="请把 YAML 顶层结构改为 dict (键值对映射结构)"
            )

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
            self._raise_validation_exception(reason="config.yaml 必须包含 非空str 的 active_env 字段")

        # 读取 env 对应值, 不存在默认为 None
        env_map = raw.get("env", None)
        if not isinstance(env_map, dict) or not env_map:
            self._raise_validation_exception(
                reason="env 字段必须是 非空dict",
                yaml_location="config.yaml.env"
            )
        # 校验 active_env 是否存在于配置好的 env 中
        if active_env not in env_map:
            self._raise_validation_exception(
                reason=f"{active_env} 不在 env 列表中",
                yaml_location=f"config.yaml.active_env={active_env}",
                extra={"可用的 env": f"{env_map}"}
            )
        # 取当前环境体
        current_env = env_map[active_env]

        # 读取 hosts
        hosts = current_env.get("hosts", None)
        # 允许 hosts 为 None
        if hosts is None:
            hosts = {}
        if not isinstance(hosts, dict):
            self._raise_validation_exception(
                reason="当前环境下的 hosts 字段必须是 dict",
                yaml_location=f"config.yaml.env.{active_env}.hosts"
            )

        # 读取 static, 允许对应值为 None, 并校验是否为 dict
        static = raw.get("static", {})
        if static is None:
            static = {}
        if not isinstance(static, dict):
            self._raise_validation_exception(
                reason="static 字段必须是 dict",
                yaml_location="config.yaml.static"
            )

        # 读取 request_defaults, 允许对应值为 None, 并校验是否为 dict
        request_defaults = raw.get("request_defaults", {})
        if request_defaults is None:
            request_defaults = {}
        if not isinstance(request_defaults, dict):
            self._raise_validation_exception(
                reason="request_defaults 字段必须是 dict",
                yaml_location="config.yaml.request_defaults"
            )

        # 读取 run_control, 允许对应值为 None, 并校验是否为 dict
        run_control = raw.get("run_control", {})
        if run_control is None:
            run_control = {}
        if not isinstance(run_control, dict):
            self._raise_validation_exception(
                reason="run_control 字段必须是 dict",
                yaml_location="config.yaml.run_control"
            )
        # 校验 is_run 字段下的 key
        self._assert_allowed_keys(
            run_control,
            {"is_run", "skip_apis", "only_apis"},
            "config.yaml.run_control"
        )
        # is_run 若写必须 bool
        if "is_run" in run_control and not isinstance(run_control.get("is_run"), bool):
            self._raise_validation_exception(
                reason="is_run 字段必须是 bool",
                yaml_location="config.yaml.run_control.is_run"
            )
        # skip_apis 若写必须 list
        if "skip_apis" in run_control and not isinstance(run_control.get("skip_apis"), list):
            self._raise_validation_exception(
                reason="skip_apis 字段必须是 list",
                yaml_location="config.yaml.run_control.skip_apis"
            )
        # only_apis 若写必须 list
        if "only_apis" in run_control and not isinstance(run_control.get("only_apis"), list):
            self._raise_validation_exception(
                reason="only_apis 字段必须是 list",
                yaml_location="config.yaml.run_control.only_apis"
            )

        # 读取 auth_profiles, 允许对应值为 None, 并校验是否为 dict
        auth_profiles = raw.get("auth_profiles", {})
        if auth_profiles is None:
            auth_profiles = {}
        if not isinstance(auth_profiles, dict):
            self._raise_validation_exception(
                reason="auth_profiles 字段必须是 dict",
                yaml_location="config.yaml.auth_profiles"
            )

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
        yaml_location = f"config.yaml.auth_profiles.{p_name}"
        # profile 体必须是非空 list
        if not isinstance(body, list) or not body:
            self._raise_validation_exception(
                reason=f"{p_name} 字段必须是非空 list",
                yaml_location=yaml_location
            )

        self._validate_ref_steps(body, yaml_location)

    # --------------------------- single.yaml 校验 ---------------------------
    def _validate_apis(self, raw):
        """
          校验 single.yaml 里的数据
        :param raw: single.yaml 原始数据
        """
        # 顶层结构必须是 dict
        if not isinstance(raw, dict):
            self._raise_validation_exception(reason="single.yaml 顶层必须是 dict")
        # 限制顶层可以存在的 key
        self._assert_allowed_keys(raw, {"apis"}, "single.yaml")
        # 读取 apis, 必须为 非空dict
        apis = raw.get("apis", None)
        if not isinstance(apis, dict) or not apis:
            self._raise_validation_exception(
                reason="apis 字段必须是非空 dict",
                yaml_location="single.yaml.apis"
            )

        # 初始化 API 输出映射
        out: Dict[str, ApiItem] = {}
        # 遍历每个 api, 并校验
        for api_name, body in apis.items():
            # 定位 api 根路径
            yaml_location = f"single.yaml.apis.{api_name}"
            # api 名称不允许存在首尾空格
            self._check_no_edge_blank(api_name, yaml_location)

            # api 对应的 value 必须为 dict
            if not isinstance(body, dict):
                self._raise_validation_exception(
                    reason=f"{api_name} 必须是 dict",
                    yaml_location=f"{yaml_location}"
                )

            # 限制可填的字段
            self._assert_allowed_keys(
                body,
                {"auth_profile", "is_run", "depends_on", "request", "extract", "assertions", "cleanup"},
                yaml_location
            )

            # 读取 auth_profile, 允许为 None, 若写必须为 str, 且首尾无空格
            auth_profile = body.get("auth_profile", None)
            if auth_profile is not None and not isinstance(auth_profile, str):
                self._raise_validation_exception(
                    reason="auth_profile 必须是 str 或不写",
                    yaml_location=f"{yaml_location}.auth_profile"
                )
            if auth_profile is not None:
                self._check_no_edge_blank(auth_profile, f"{yaml_location}.auth_profile")

            # 读取 is_run, 允许为 None, 若写必须为 bool
            is_run = body.get("is_run", None)
            if is_run is not None and not isinstance(is_run, bool):
                self._raise_validation_exception(
                    reason="is_run 必须是 bool 或不写",
                    yaml_location=f"{yaml_location}.is_run"
                )

            # 读取 depends_on 字段, 不填按空列表处理
            depends_on = body.get("depends_on", [])
            # yaml 显式写 null, 按空列表处理
            if depends_on is None:
                depends_on = []
            if not isinstance(depends_on, list):
                self._raise_validation_exception(
                    reason="depends_on 字段必须是 list",
                    yaml_location=f"{yaml_location}.depends_on"
                )
            # 仅当非空时才校验
            if depends_on:
                self._validate_ref_steps(depends_on, f"{yaml_location}.depends_on")

            # 读取 request, 并校验对应值必须为 dict
            request = body.get("request", None)
            self._validate_request(request, f"{yaml_location}.request", is_patch=False)

            # 读取 extract, 对应 value 允许为 None, 若存在必须为 list
            extract_rules = body.get("extract", [])
            if extract_rules is None:
                # 若为 None, 则转为 空list
                extract_rules = []
            if not isinstance(extract_rules, list):
                self._raise_validation_exception(
                    reason="extract 必须是 list",
                    yaml_location=f"{yaml_location}.extract"
                )
            # 遍历 extract, 并校验
            self._validate_extract_rules(extract_rules, yaml_location=f"{yaml_location}.extract")

            # 读取 assertions, 允许对应 value 为 None, 若存在必须为 list
            assertions = body.get("assertions", [])
            if assertions is None:
                # 若为None, 则转为 空list
                assertions = []
            if not isinstance(assertions, list):
                self._raise_validation_exception(
                    reason="assertions 必须是 list",
                    yaml_location=f"{yaml_location}.assertions"
                )
            # 遍历 assertions, 并校验断言规则
            self._validate_assert_rules(assertions, where=f"{yaml_location}.assertions")

            # 统一校验 cleanup
            cleanup = body.get("cleanup", None)
            if cleanup is not None:
                self._validate_cleanup(cleanup, f"{yaml_location}.cleanup")

            out[api_name] = ApiItem(
                api_id=api_name,
                auth_profile=auth_profile,
                is_run=is_run,
                depends_on=depends_on,
                request=request,
                extract=extract_rules,
                assertions=assertions,
                cleanup=cleanup
            )

        return out

    def _validate_flows(self, raw: Union[Dict[str, Any], List[Dict[str, Any]]]) -> Dict[str, FlowBundle]:
        """
          校验业务流里的数据
        :param raw: dict 或 list[dict] 类型; dict 表示只有一个业务流时, list 表示有多个业务流(如多个yaml文件, 或单yaml文件多个 '---')
        """
        # raw 为 dict, 表示是单个 flow
        if isinstance(raw, dict):
            one = self._validate_one_flow(raw)
            return {one.flow_id: one}

        # raw 为 list, 表示多个 flow 文档
        if isinstance(raw, list):
            # 初始化输出映射
            out = {}
            # 遍历该文档, 从 1 开始编号
            for i, doc in enumerate(raw, start=1):
                # 校验文档里的单个 flow
                flow = self._validate_one_flow(doc)
                # 若 flow_id 重复则报错
                if flow.flow_id in out:
                    self._raise_validation_exception(
                        reason=f"flow_id 重复: {flow.flow_id}",
                        yaml_location=f"{flow.source}.flow_id"
                    )
                out[flow.flow_id] = flow

            # 若 flows 目录为空 / 全空文档
            if not out:
                self._raise_validation_exception(reason="未加载到任何 flow 文档, 请检查 flows 文件")
            return out

        # 不支持其它类型
        self._raise_validation_exception(reason="flows 数据类型非法: 必须是 dict 或 list[dict]")

    def _validate_one_flow(self, raw: Dict[str, Any]) -> FlowBundle:
        """
          校验单个 flow 结构内容
        """
        # 顶层必须 dict
        if not isinstance(raw, dict):
            self._raise_validation_exception(reason=f"flow 顶层结构必须是 dict")

        # 提取内部来源 source 字段(文件#序号), 没有该字段时则为空串
        source = str(raw.get("_source", ""))

        # 允许出现的顶层字段
        self._assert_allowed_keys(
            raw,
            {"common", "flow_id", "is_run", "auth_profile", "steps", "cleanup", "_source"},
            source
        )

        # 读取 common, 允许对应值为 None, 若存在必须为 dict
        common = raw.get("common", {})
        if common is None:
            # 若为 None, 则转为 空dict
            common = {}
        if not isinstance(common, dict):
            self._raise_validation_exception(
                reason=f"common 字段必须是 dict",
                yaml_location=f"{source}.common"
            )

        # 读取 flow_id, 对应值必须为 非空str, 且首尾无空格
        flow_id = raw.get("flow_id", None)
        if not isinstance(flow_id, str) or not flow_id.strip():
            self._raise_validation_exception(
                reason=f"flow_id 字段必须是非空 str",
                yaml_location=f"{source}.flow_id"
            )
        self._check_no_edge_blank(flow_id, f"{source}.flow_id")

        # 读取 is_run, 对应值必须为 bool, 不填默认为 True
        is_run = raw.get("is_run", True)
        if not isinstance(is_run, bool):
            self._raise_validation_exception(
                reason=f"is_run 字段若填必须是 bool",
                yaml_location=f"{source}.is_run"
            )

        # 读取 auth_profile, 对应值允许为 None, 若存在必须为 str
        auth_profile = raw.get("auth_profile", None)
        if auth_profile is not None and not isinstance(auth_profile, str):
            self._raise_validation_exception(
                reason=f"auth_profile 字段必须是 str 或不写",
                yaml_location=f"{source}.auth_profile"
            )
        if auth_profile is not None:
            self._check_no_edge_blank(auth_profile, f"{source}.auth_profile")

        # 统一校验 steps
        steps = raw.get("steps", None)
        self._validate_ref_steps(steps, f"{source}.steps", allow_delay_run=True)

        # 统一校验 cleanup
        cleanup = raw.get("cleanup", None)
        if cleanup is not None:
            self._validate_cleanup(cleanup, f"{source}.cleanup")

        return FlowBundle(
            common=common,
            flow_id=flow_id,
            is_run=is_run,
            auth_profile=auth_profile,
            steps=steps,
            cleanup=cleanup,
            source=source
        )

    # --------------------------- 通用规则校验 ---------------------------
    def _validate_ref_steps(
        self,
        steps,
        yaml_location: str,
        allow_delay_run: bool = False
    ):
        """
          统一校验引用型步骤列表
        :param steps: 步骤列表
        :param yaml_location: 当前步骤列表定位路径
        :param allow_delay_run: 是否允许当前步骤包含额外的 delay_run 字段
        """
        # 步骤列表必须是非空 list
        if not isinstance(steps, list) or not steps:
            self._raise_validation_exception(
                reason="步骤列表必须是非空 list",
                yaml_location=yaml_location
            )
        # 逐个校验步骤项
        for index, step in enumerate(steps, start=1):
            self._validate_ref_step(step, f"{yaml_location}[{index}]", allow_delay_run=allow_delay_run)

    def _validate_ref_step(
        self,
        step,
        yaml_location: str,
        allow_delay_run: bool = False
    ):
        """
          统一校验单个引用型步骤结构

          通用字段:
            - id
            - ref
            - is_run
            - override

          flow.steps 在此基础上额外允许:
            - delay_run
        """
        # 单个步骤必须是 dict
        if not isinstance(step, dict):
            self._raise_validation_exception(
                reason="步骤必须是 dict",
                yaml_location=yaml_location
            )

        # 限制允许填入的字段
        allowed_keys = {"id", "ref", "is_run", "override"}
        if allow_delay_run:
            allowed_keys.add("delay_run")

        self._assert_allowed_keys(
            step,
            allowed_keys,
            yaml_location
        )

        # id 若写必须是非空 str
        if "id" in step and step.get("id") is not None:
            step_id = step.get("id")
            # 校验 id 类型与是否非空
            if not isinstance(step_id, str) or not step_id.strip():
                self._raise_validation_exception(
                    reason="id 字段必须为非空 str",
                    yaml_location=f"{yaml_location}.id"
                )
            self._check_no_edge_blank(step_id, f"{yaml_location}.id")

        # 读取 ref
        ref = step.get("ref", None)
        if not isinstance(ref, str) or not ref.strip():
            self._raise_validation_exception(
                reason="ref 字段必须为非空 str",
                yaml_location=f"{yaml_location}.ref"
            )
        self._check_no_edge_blank(ref, f"{yaml_location}.ref")

        # is_run 若写必须是 bool
        if "is_run" in step and step.get("is_run") is not None and not isinstance(step.get("is_run"), bool):
            self._raise_validation_exception(
                reason="is_run 字段必须为bool, 或者不填",
                yaml_location=f"{yaml_location}.is_run"
            )

        # flow step 允许 delay_run
        if allow_delay_run and "delay_run" in step:
            delay_run = step.get("delay_run")
            # 若 delay_run 有值(允许 None 值 等价于不延迟)
            if delay_run is not None:
                # bool 单独排除, 因为 bool 在python里属于 int 子类
                if isinstance(delay_run, bool) or not isinstance(delay_run, (int, float)):
                    self._raise_validation_exception(
                        reason="delay_run 字段必须是非负值(int/float)",
                        yaml_location=f"{yaml_location}.delay_run"
                    )
                # 不能为负数
                if delay_run < 0:
                    self._raise_validation_exception(
                        reason="delay_run 不能小于 0",
                        yaml_location=f"{yaml_location}.delay_run"
                    )

        # 统一校验 override 结构
        self._validate_override(step.get("override"), f"{yaml_location}.override")

    def _validate_cleanup(self, cleanup, yaml_location: str):
        """
          统一校验 cleanup 结构
        """
        if not isinstance(cleanup, dict):
            self._raise_validation_exception(
                reason="cleanup 字段必须是 dict",
                yaml_location=yaml_location
            )

        # 限制可填的字段
        self._assert_allowed_keys(
            cleanup,
            {"when", "continue_on_error", "steps"},
            yaml_location
        )

        if "when" in cleanup and cleanup.get("when") is not None:
            self._check_enum(
                cleanup.get("when"),
                {"always", "on_success", "on_fail"},
                f"{yaml_location}.when"
            )

        # continue_on_error 若写必须是 bool
        if "continue_on_error" in cleanup and cleanup.get("continue_on_error") is not None and \
                not isinstance(cleanup.get("continue_on_error"), bool):
            self._raise_validation_exception(
                reason="continue_on_error 字段必须是 bool 或不填",
                yaml_location=f"{yaml_location}.continue_on_error"
            )

        # 统一校验 steps 字段
        steps = cleanup.get("steps", None)
        self._validate_ref_steps(steps, f"{yaml_location}.steps")

    def _validate_request(self, request, yaml_location: str, is_patch: bool):
        """
          校验 request 下的字段
          注: 除了必要的 method/url/body_type/body 进行校验, 其它参数不再校验
        :param request: request 对应的 值
        :param yaml_location: 定位路径
        :param is_patch: 是否为补丁, 是则不需要填 url/method, 否则必填. 比如 multiple.yaml 里的覆盖数据在校验时就不需要完整请求
        """
        # request 必须为 dict
        if not isinstance(request, dict):
            self._raise_validation_exception(reason=f"{yaml_location} 必须是 dict")

        # 限制 request 下的字段
        self._assert_allowed_keys(
            request,
            {
                "method", "url", "host",
                "body_type", "body",
                "params", "files",
                "headers", "cookies",
                "auth", "timeout",
                "allow_redirects", "proxies",
                "verify", "stream",
                "cert"
             },
            yaml_location
        )

        # 允许的 method 值
        allowed_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        # 允许的 body_type 值
        allowed_body_types = {"data", "json"}

        # 若 host 存在且不为 None
        if "host" in request and request.get("host", None) is not None:
            host = request.get("host", None)
            # 那么必须为非空 str
            if not isinstance(host, str) or not host.strip():
                self._raise_validation_exception(
                    reason="request.host 字段必须是非空 str",
                    yaml_location=f"{yaml_location}.host"
                )
            # 并且不允许首尾有空格
            self._check_no_edge_blank(host, f"{yaml_location}.host")

        # 若不是补丁, 则需要完整 request 请求
        if not is_patch:
            # 读取 method, 并校验是否错写/漏写
            method = request.get("method", None)
            # 若 method 不为 None, 并且属于 str, 则转换为小写
            if method is not None and isinstance(method, str):
                method = method.lower()
            self._check_enum(method, allowed_methods, yaml_location=f"{yaml_location}.method")

            # 读取 url, 并校验 url 是否为 非空str, 且首尾无空格
            url = request.get("url", None)
            if not isinstance(url, str) or not url.strip():
                self._raise_validation_exception(
                    reason=f"url 字段必须是非空 str",
                    yaml_location=f"{yaml_location}.url"
                )
            self._check_no_edge_blank(url, yaml_location=f"{yaml_location}.url")

        # 若为 override.request, 则校验写了 method/url 的情况
        else:
            if "method" in request and request.get("method") is not None:
                self._check_enum(request.get("method"), allowed_methods, yaml_location=f"{yaml_location}.method")
            if "url" in request and request.get("url") is not None:
                url = request.get("url")
                if not isinstance(url, str) or not url.strip():
                    self._raise_validation_exception(
                        reason=f"url 字段必须是非空 str",
                        yaml_location=f"{yaml_location}.url"
                    )
                self._check_no_edge_blank(url, yaml_location=f"{yaml_location}.url")

        # body_type 若写必须符合两种类型
        if "body_type" in request and request.get("body_type") is not None:
            self._check_enum(request.get("body_type"), allowed_body_types, yaml_location=f"{yaml_location}.body_type")
        # body 若写, 校验是否正确填写数据
        if "body" in request:
            body_node = request.get("body")
            # 若 body 为 空list, 则报错
            if isinstance(body_node, list) and len(body_node) == 0:
                self._raise_validation_exception(
                    reason=f"body 字段为 list 时不能为空",
                    yaml_location=f"{yaml_location}.body"
                )

            # 不是补丁request时, body 非空, 则需校验 request_type 是否也存在
            if not is_patch and body_node is not None:
                if "body_type" not in request or request.get("body_type") is None:
                    self._raise_validation_exception(reason=f"{yaml_location}.body 已提供, 但 {yaml_location}.body_type 未写")

        # 若存在 params
        if "params" in request:
            # 读取 params 节点
            params_node = request.get("params")
            # 若 params 是空 list, 直接报错
            if isinstance(params_node, list) and len(params_node) == 0:
                self._raise_validation_exception(
                    reason="params 字段为 list 时不能为空",
                    yaml_location=f"{yaml_location}.params"
                )

        # 若存在 files
        if "files" in request:
            # 读取 files 节点
            files_node = request.get("files")
            # 若 files 是空 list, 则直接报错
            if isinstance(files_node, list) and len(files_node) == 0:
                self._raise_validation_exception(
                    reason="params 字段为 list 时不能为空",
                    yaml_location=f"{yaml_location}.files"
                )

    def _validate_override(self, override, yaml_location: str):
        """
          统一校验 override 结构
        """
        # 避免为空报错
        if override is None:
            override = {}

        # override 结构必须是 dict 类型
        if not isinstance(override, dict):
            self._raise_validation_exception(
                reason=f"override 字段必须是 dict",
                yaml_location=yaml_location
            )

        # 限制 override 下的字段
        self._assert_allowed_keys(override, {"request", "assertions", "extract"}, yaml_location)

        # request 若存在则进行校验
        if "request" in override and override.get("request") is not None:
            self._validate_request(
                override.get("request"),
                yaml_location=f"{yaml_location}.request",
                is_patch=True
            )

        # extract 若存在则进行校验
        if "extract" in override and override.get("extract") is not None:
            # extract 必须为 list
            if not isinstance(override.get("extract"), list):
                self._raise_validation_exception(
                    reason=f"extract 字段必须是 list",
                    yaml_location=f"{yaml_location}.extract"
                )
            self._validate_extract_rules(override.get("extract"), yaml_location=f"{yaml_location}.extract")

        # assertions 若存在则进行校验
        if "assertions" in override and override.get("assertions") is not None:
            # assertions 必须为 list
            if not isinstance(override.get("assertions"), list):
                self._raise_validation_exception(
                    reason=f"assertions 字段必须是 list",
                    yaml_location=f"{yaml_location}.assertions"
                )
            self._validate_assert_rules(override.get("assertions"), where=f"{yaml_location}.assertions")

    def _validate_extract_rules(self, rules: List[Any], yaml_location: str):
        """
          对每条 extract rule 调用 _validate_extract_rule
        """
        exist_as = set()
        for i, rule in enumerate(rules, start=1):
            # 构造定位路径
            rule_where = f"{yaml_location}[{i}]"
            self._validate_extract_rule(rule, yaml_location=rule_where)
            # 存在同名 as 日志报警
            as_name = rule.get("as")
            if as_name in exist_as:
                logger.warning(msg="存在同名 as, 后者已覆盖前者")
            # 将 as 添加进 set 中
            exist_as.add(as_name)

    def _validate_extract_rule(self, rule, yaml_location: str):
        """
          校验 extract 的具体规则
        :param rule: extract.[value]
        :param yaml_location: 定位路径
        """
        # rule 必须是 dict
        if not isinstance(rule, dict):
            self._raise_validation_exception(reason=f"{yaml_location} 必须是 dict")

        # 限制 extract 字段
        self._assert_allowed_keys(rule, {"source", "jsonpath", "as"}, yaml_location)

        # 允许提取的数据源
        allowed_sources = {"response_json", "response_text", "response_headers", "response_status"}
        # 校验是否正确填写数据源, 以及格式是否正确
        self._check_enum(rule.get("source"), allowed_sources, yaml_location)

        # 提取路径jsonpath 必须为 非空str, 且无首尾空格
        jsonpath = rule.get("jsonpath")
        if not isinstance(jsonpath, str) or not jsonpath.strip():
            self._raise_validation_exception(
                reason=f"jsonpath 字段必须是非空 str",
                yaml_location=f"{yaml_location}.jsonpath"
            )
        self._check_no_edge_blank(jsonpath, yaml_location)

        # 提取的数据 存储名称key: as 必须为 非空str, 且无首尾空格
        as_name = rule.get("as")
        if not isinstance(as_name, str) or not as_name.strip():
            self._raise_validation_exception(
                reason=f"as 字段必须是非空 str",
                yaml_location=f"{yaml_location}.as"
            )
        self._check_no_edge_blank(as_name, yaml_location)

    def _validate_assert_rules(self, rules: List[Any], where: str):
        """
          对每条 assert rule 调用 _validate_assert_rule
        """
        for i, rule in enumerate(rules, start=1):
            self._validate_assert_rule(rule, f"{where}[{i}]")

    def _validate_assert_rule(self, rule, yaml_location: str):
        """
          校验 assertions 的具体规则
        :param rule: assertions.[value]
        :param yaml_location: 定位路径
        """
        # rule 必须为 dict
        if not isinstance(rule, dict):
            self._raise_validation_exception(reason=f"{yaml_location} 必须是 dict")

        # 限制断言字段
        self._assert_allowed_keys(rule, {"source", "jsonpath", "op", "expected"}, yaml_location)
        # 允许提取的数据源
        allowed_sources = {"response_json", "response_text", "response_headers", "response_status"}
        # 校验是否正确填写数据源, 以及格式是否正确
        self._check_enum(rule.get("source"), allowed_sources, f"{yaml_location}.source")

        # 提取路径jsonpath 必须为 非空str, 且无首尾空格
        jsonpath = rule.get("jsonpath")
        if not isinstance(jsonpath, str) or not jsonpath.strip():
            self._raise_validation_exception(
                reason=f"jsonpath 字段必须是非空 str",
                yaml_location=f"{yaml_location}.jsonpath"
            )
        self._check_no_edge_blank(jsonpath, f"{yaml_location}.jsonpath")

        # 限制断言条件
        allowed_op = {"exists", "==", "!=", ">", ">=", "<", "<=", "contains", "regex"}
        # 校验断言规则, 必须为 非空str, 且首尾无空格
        op = rule.get("op")
        self._check_enum(op, allowed_op, f"{yaml_location}.op")
        if not isinstance(op, str) or not op.strip():
            self._raise_validation_exception(
                reason=f"op 字段必须是非空 str",
                yaml_location=f"{yaml_location}.op"
            )
        self._check_no_edge_blank(op, f"{yaml_location}.op")

        # expected 必须存在键(允许 expected: null)
        if "expected" not in rule:
            self._raise_validation_exception(
                reason=f"expected 必须存在, 在场景不需要 expected 值时, 须填 expected: null",
                yaml_location=f"{yaml_location}.expected"
            )


