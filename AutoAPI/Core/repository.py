from pathlib import Path
from typing import Dict, Optional, Union, List, Any

from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
from Schema.data_models import (
    ApiCase,
    ApiTemplate,
    EnvProfile,
    EnvironmentConfig,
    HostRule,
    ProjectAssets,
    Scenario,
    ScenarioStep,
    TestPlan,
)
from Schema.data_validation import ConfigBundle, ApiItem, FlowBundle, YamlSchemaValidator
from Utils.yaml_io import load_yaml_file, load_yaml_documents

PathLike = Union[str, Path]


class YamlRepository:
    """
      作用：
        1.读取 Data 下的 yaml 文件并存储
        2.对读取的数据进行结构校验
        3.提供 get_api/get_flow/get_auth_profile 等读取能力给执行层
    """
    def __init__(self, root_dir: PathLike):
        """
          保存存储 YAML 的根目录, 后续统一从该目录读取 yaml 文件
        :param root_dir: YAML 文件所在目录
        """
        self.root_dir = Path(root_dir)
        # 初始化校验器
        self._validator = YamlSchemaValidator()
        self.config: Optional[ConfigBundle] = None
        self.apis: Optional[Dict[str, ApiItem]] = None
        self.flows: Optional[Dict[str, FlowBundle]] = None

    def load(self):
        """
          读取并严格校验 yaml数据, 并加载到 repository 内存对象中
        """
        # 读取三个 yaml 文件
        config_raw = load_yaml_file(self.root_dir / "config.yaml")
        single_raw = load_yaml_file(self.root_dir / "single.yaml")
        multiple_raw = self.load_flow_docs(self.root_dir / "Flows")

        # 校验并处理原始数据
        validated = self._validator.validate_all(config_raw, single_raw, multiple_raw)

        # 缓存校验后的结果
        self.config = validated.config
        self.apis = validated.apis
        self.flows = validated.flows

    def load_flow_docs(self, flows_dir):
        # 初始化输出列表
        out: List[Dict[str, Any]] = []

        # 判断 Flows 目录是否存在且是目录
        if flows_dir.exists() and flows_dir.is_dir():
            # 扫描 yaml 文件
            files = list(flows_dir.glob("*.yaml"))
            # 按文件名排序, 确保收集顺序稳定
            files.sort(key=lambda p: p.name)
            # 遍历每个文档
            for file in files:
                # 加载文档
                docs = load_yaml_documents(file)
                # 遍历文档(文档可能存在 '---'), 并编号
                for i, doc in enumerate(docs, start=1):
                    # 注入 文档来源字段
                    doc["_source"] = f"{file.name}#{i}"
                    out.append(doc)
            return out

        # 找不到文件抛错
        raise FileNotFoundError("未找到相关文件, 请创建 Data/Flows/*.yaml")

    def get_api(self, api_id: str) -> ApiItem:
        """
          获取具体接口需要的数据
        :param api_id: 接口库里的 api_id, 不能有首尾空格
        :return:
        """
        # 若不存在该 api
        if api_id is None or api_id not in self.apis:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="接口库不存在",
                yaml_location="single.yaml",
                reason=f"single.yaml.apis 不存在接口：{api_id}",
            )
            raise ValidationException(error_context)
        # 返回 api
        return self.apis[api_id]

    def should_run_single_api(self, api_id: str) -> bool:
        """
          根据 config.yaml.run_control 与 api.is_run 决定是否 跳过/仅执行 single 接口

        :param api_id: 接口 id
        :return: 返回 bool, 决定是否执行
        """
        # 获取接口定义
        api = self.get_api(api_id)

        # 读取 run_control, 为 None 时设为 空dict
        rc = self.config.run_control or {}

        # 全局开关, 不填默认为 True, 如果全局开关为 False, 则全部不执行
        global_is_run = rc.get("is_run", True)
        if not global_is_run:
            return False

        # 仅执行的接口列表
        only_apis = set(rc.get("only_apis", []) or [])
        # 若白名单非空, 但该 api 不在白名单中, 则该 api 不执行
        if only_apis and api_id not in only_apis:
            return False

        # 跳过执行的接口列表
        skip_apis = set(rc.get("skip_apis", []) or [])
        # 若当前 api 在黑名单中, 跳过执行
        if api_id in skip_apis:
            return False

        # 若 single.yaml 里的 api 显式写了 is_run, 在全局开关为 True, 且在白名单, 不在黑名单(或两个名单为空) 情况下生效
        # 优先级最低
        if api.is_run is False:
            return False

        # 其它情况下允许执行
        return True

    def get_flow(self, flow_id: str) -> FlowBundle:
        """
          获取 multiple.yaml 的校验后结构化对象（包含 common）
        """
        if flow_id is None or flow_id not in self.flows:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="接口不存在",
                reason=f"业务流 flows 不存在接口：{flow_id}",
            )
            raise ValidationException(error_context)
        return self.flows[flow_id]

    def list_flow_ids(self) -> List[str]:
        """
          返回当前已加载的所有已排序后的 flow_id, 用于 pytest 收集参数化
        """
        # 若 flows 为空, 返回空列表
        if not self.flows:
            return []
        # 取出所有 flow_id
        ids = list(self.flows.keys())
        # 排序确保稳定
        ids.sort()
        return ids

    def list_runnable_api_id(self) -> List[str]:
        """
          返回最终允许执行的 single api_id 列表
        :return: 已排序的 api_id 列表
        """
        # 若 apis 为空, 则返回空列表
        if not self.apis:
            return []

        # 取出全部 api_id, 并排序保持执行顺序稳定
        api_ids = sorted(self.apis.keys())

        return [api_id for api_id in api_ids if self.should_run_single_api(api_id)]

class YamlRepository:
    """
      P0 YAML 资产仓库。

      新主路径只加载 config.yaml、apis.yaml、cases.yaml、Scenarios/*.yaml、plans.yaml。
      文件上方旧实现暂时不再作为主路径使用，后续执行器重构时统一清理。
    """
    def __init__(self, root_dir: PathLike):
        self.root_dir = Path(root_dir)
        self._validator = YamlSchemaValidator()
        self.assets: Optional[ProjectAssets] = None

        self.config: Optional[EnvironmentConfig] = None
        self.apis: Dict[str, ApiTemplate] = {}
        self.cases: Dict[str, ApiCase] = {}
        self.scenarios: Dict[str, Scenario] = {}
        self.plans: Dict[str, TestPlan] = {}

    def load(self) -> ProjectAssets:
        config = self._load_config(load_yaml_file(self.root_dir / "config.yaml"))
        apis = self._load_apis(load_yaml_file(self.root_dir / "apis.yaml"))
        cases = self._load_cases(load_yaml_file(self.root_dir / "cases.yaml"))
        scenarios = self._load_scenarios(self.root_dir / "Scenarios")
        plans = self._load_plans(load_yaml_file(self.root_dir / "plans.yaml"))

        assets = ProjectAssets(
            config=config,
            apis=apis,
            cases=cases,
            scenarios=scenarios,
            plans=plans,
        )
        self._validator.validate_project(assets)

        self.assets = assets
        self.config = assets.config
        self.apis = assets.apis
        self.cases = assets.cases
        self.scenarios = assets.scenarios
        self.plans = assets.plans
        return assets

    def _load_config(self, raw: Dict[str, Any]) -> EnvironmentConfig:
        envs_raw = raw.get("envs", {}) or {}
        envs: Dict[str, EnvProfile] = {}

        for env_name, env_body in envs_raw.items():
            env_body = env_body or {}
            host_rules = []
            for rule in env_body.get("host_rules", []) or []:
                if not isinstance(rule, dict):
                    continue
                host_rules.append(
                    HostRule(
                        host=rule.get("host", ""),
                        priority=rule.get("priority", 0) or 0,
                        apis=list(rule.get("apis", []) or []),
                        modules=list(rule.get("modules", []) or []),
                        path_prefixes=list(rule.get("path_prefixes", []) or []),
                        default=bool(rule.get("default", False)),
                    )
                )
            envs[env_name] = EnvProfile(
                variables=env_body.get("variables", {}) or {},
                hosts=env_body.get("hosts", {}) or {},
                host_rules=host_rules,
            )

        return EnvironmentConfig(
            active_env=raw.get("active_env", ""),
            envs=envs,
            request_defaults=raw.get("request_defaults", {}) or {},
            sensitive_keys=list(raw.get("sensitive_keys", []) or []),
        )

    def _load_apis(self, raw: Dict[str, Any]) -> Dict[str, ApiTemplate]:
        apis_raw = raw.get("apis", {}) or {}
        return {
            api_id: ApiTemplate(
                id=api_id,
                meta=body.get("meta", {}) or {},
                request=body.get("request", {}) or {},
                parameters=body.get("parameters", {}) or {},
                before_steps=body.get("before_steps", []) or [],
                after_steps=body.get("after_steps", []) or [],
                extract=body.get("extract", []) or [],
                assertions=body.get("assertions", []) or [],
            )
            for api_id, body in apis_raw.items()
            if isinstance(body, dict)
        }

    def _load_cases(self, raw: Dict[str, Any]) -> Dict[str, ApiCase]:
        cases_raw = raw.get("cases", {}) or {}
        return {
            case_id: ApiCase(
                id=case_id,
                api=body.get("api", ""),
                meta=body.get("meta", {}) or {},
                request=body.get("request", {}) or {},
                before_steps=body.get("before_steps", []) or [],
                after_steps=body.get("after_steps", []) or [],
                extract=body.get("extract", []) or [],
                assertions=body.get("assertions", []) or [],
            )
            for case_id, body in cases_raw.items()
            if isinstance(body, dict)
        }

    def _load_scenarios(self, scenarios_dir: Path) -> Dict[str, Scenario]:
        if not scenarios_dir.exists() or not scenarios_dir.is_dir():
            self._raise_validation(
                reason="未找到场景目录",
                yaml_location=str(scenarios_dir),
                hint="请检查 P0 新结构目录是否存在",
            )

        scenarios: Dict[str, Scenario] = {}
        for file_path in sorted(scenarios_dir.glob("*.yaml"), key=lambda p: p.name):
            raw = load_yaml_file(file_path)
            scenario = self._load_one_scenario(raw, source=file_path.name)
            if scenario.id in scenarios:
                self._raise_validation(
                    reason=f"scenario_id 重复: {scenario.id}",
                    yaml_location=f"{file_path.name}.scenario_id",
                )
            scenarios[scenario.id] = scenario

        if not scenarios:
            self._raise_validation(
                reason="未加载到任何 scenario",
                yaml_location="Scenarios",
            )
        return scenarios

    def _load_one_scenario(self, raw: Dict[str, Any], *, source: str) -> Scenario:
        steps = []
        for step in raw.get("steps", []) or []:
            if not isinstance(step, dict):
                continue
            steps.append(
                ScenarioStep(
                    id=step.get("id", ""),
                    use=step.get("use", ""),
                    override=step.get("override", {}) or {},
                    delay=step.get("delay"),
                )
            )

        return Scenario(
            id=raw.get("scenario_id", ""),
            env=raw.get("env"),
            meta=raw.get("meta", {}) or {},
            steps=steps,
            source=source,
        )

    def _load_plans(self, raw: Dict[str, Any]) -> Dict[str, TestPlan]:
        plans_raw = raw.get("plans", {}) or {}
        return {
            plan_id: TestPlan(
                id=plan_id,
                meta=body.get("meta", {}) or {},
                scenarios=list(body.get("scenarios", []) or []),
                cases=list(body.get("cases", []) or []),
            )
            for plan_id, body in plans_raw.items()
            if isinstance(body, dict)
        }

    def get_api(self, api_id: str) -> ApiTemplate:
        if api_id not in self.apis:
            self._raise_missing("api", api_id, sorted(self.apis.keys()))
        return self.apis[api_id]

    def get_case(self, case_id: str) -> ApiCase:
        if case_id not in self.cases:
            self._raise_missing("case", case_id, sorted(self.cases.keys()))
        return self.cases[case_id]

    def get_scenario(self, scenario_id: str) -> Scenario:
        if scenario_id not in self.scenarios:
            self._raise_missing("scenario", scenario_id, sorted(self.scenarios.keys()))
        return self.scenarios[scenario_id]

    def get_plan(self, plan_id: str) -> TestPlan:
        if plan_id not in self.plans:
            self._raise_missing("plan", plan_id, sorted(self.plans.keys()))
        return self.plans[plan_id]

    def get_env(self, env_name: Optional[str] = None) -> EnvProfile:
        if self.config is None:
            self._raise_validation(reason="Repository 尚未 load", yaml_location="config")

        resolved_env = env_name or self.config.active_env
        if resolved_env not in self.config.envs:
            self._raise_missing("env", resolved_env, sorted(self.config.envs.keys()))
        return self.config.envs[resolved_env]

    def list_ids(self) -> Dict[str, List[str]]:
        return {
            "apis": sorted(self.apis.keys()),
            "cases": sorted(self.cases.keys()),
            "scenarios": sorted(self.scenarios.keys()),
            "plans": sorted(self.plans.keys()),
        }

    def _raise_missing(self, asset_type: str, asset_id: str, available: List[str]):
        self._raise_validation(
            reason=f"{asset_type} 不存在: {asset_id}",
            yaml_location=asset_type,
            extra={"available": available},
        )

    def _raise_validation(
        self,
        *,
        reason: str,
        yaml_location: str,
        hint: str = "请检查 P0 新结构 YAML 资产",
        extra: Optional[Dict[str, Any]] = None,
    ):
        error_context = build_api_exception_context(
            error_code=ExceptionCode.VALIDATION_ERROR,
            message="Repository 加载失败",
            reason=reason,
            yaml_location=yaml_location,
            hint=hint,
            extra=extra,
        )
        raise ValidationException(error_context)


if __name__ == "__main__":
    data = YamlRepository("./Data")

