from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
from Schema.data_models import (
    ApiCase,
    ApiTemplate,
    EnvProfile,
    EnvironmentConfig,
    HookStep,
    HostRule,
    ProjectAssets,
    Scenario,
    ScenarioDataset,
    ScenarioStep,
    TestPlan,
)
from Schema.data_validation import YamlSchemaValidator
from Utils.yaml_io import load_yaml_file

PathLike = Union[str, Path]

class YamlRepository:
    """
      YAML 资产仓库。

      新主路径只加载 config.yaml、apis.yaml、cases.yaml、Scenarios/*.yaml、plans.yaml。
    """
    def __init__(self, root_dir: PathLike):
        # root_dir 指向 YAML 资产目录，默认通常是 Data。
        self.root_dir = Path(root_dir)
        # 复用现有 Validator 壳子，当前只执行必要的关系校验。
        self._validator = YamlSchemaValidator()
        # assets 保存一次 load 后的完整资产快照，便于执行层统一传递。
        self.assets: Optional[ProjectAssets] = None

        # config 保存环境配置，load 前为 None，用于判断仓库是否已初始化。
        self.config: Optional[EnvironmentConfig] = None
        # apis/cases/scenarios/plans 分层缓存，key 均为全局唯一 ID。
        self.apis: Dict[str, ApiTemplate] = {}
        self.cases: Dict[str, ApiCase] = {}
        self.scenarios: Dict[str, Scenario] = {}
        self.plans: Dict[str, TestPlan] = {}

    def load(self) -> ProjectAssets:
        # 加载 config.yaml，并转换为 EnvironmentConfig。
        config = self._load_config(load_yaml_file(self.root_dir / "config.yaml"))
        # 加载 apis.yaml，得到所有 ApiTemplate。
        apis = self._load_apis(load_yaml_file(self.root_dir / "apis.yaml"))
        # 加载 cases.yaml，得到所有 ApiCase。
        cases = self._load_cases(load_yaml_file(self.root_dir / "cases.yaml"))
        # 加载 Scenarios/*.yaml，得到所有 Scenario。
        scenarios = self._load_scenarios(self.root_dir / "Scenarios")
        # 加载 plans.yaml，得到所有 TestPlan。
        plans = self._load_plans(load_yaml_file(self.root_dir / "plans.yaml"))

        # 组装完整项目资产，后续 Validator 和执行层都围绕 ProjectAssets 工作。
        assets = ProjectAssets(
            config=config,
            apis=apis,
            cases=cases,
            scenarios=scenarios,
            plans=plans,
        )
        # 当前阶段只做基础关系校验，不启用严格字段 schema 校验。
        self._validator.validate_project(assets)

        # 将完整资产和分层索引都缓存到仓库对象上，便于 get_* 方法读取。
        self.assets = assets
        self.config = assets.config
        self.apis = assets.apis
        self.cases = assets.cases
        self.scenarios = assets.scenarios
        self.plans = assets.plans
        return assets

    def _load_config(self, raw: Dict[str, Any]) -> EnvironmentConfig:
        # envs 顶层为空时按空 dict 处理，后续校验会检查 active_env 是否存在。
        envs_raw = raw.get("envs", {}) or {}
        # envs 保存转换后的环境对象，key 是环境名。
        envs: Dict[str, EnvProfile] = {}

        # 逐个环境转换 hosts、variables 和 host_rules。
        for env_name, env_body in envs_raw.items():
            # 单个 env 为空时按空 dict 处理，避免 None 影响读取。
            env_body = env_body or {}
            # host_rules 要转换成 HostRule 对象，方便执行时按属性访问。
            host_rules = []
            # 遍历当前环境下的 host_rules 列表。
            for rule in env_body.get("host_rules", []) or []:
                # 非 dict 规则暂时跳过，严格类型校验后续再补。
                if not isinstance(rule, dict):
                    continue
                # 将 YAML 中的单条规则转换成 HostRule，并为缺失字段提供空默认值。
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
            # 将当前环境转换为 EnvProfile，供执行和 host 解析使用。
            envs[env_name] = EnvProfile(
                variables=env_body.get("variables", {}) or {},
                hosts=env_body.get("hosts", {}) or {},
                host_rules=host_rules,
            )

        # 返回完整环境配置对象，request_defaults 和 sensitive_keys 属于全局配置。
        return EnvironmentConfig(
            active_env=raw.get("active_env", ""),
            envs=envs,
            request_defaults=raw.get("request_defaults", {}) or {},
            sensitive_keys=list(raw.get("sensitive_keys", []) or []),
            shared_extracts={
                name: body if isinstance(body, list) else []
                for name, body in (raw.get("shared_extracts", {}) or {}).items()
            },
            shared_assertions={
                name: body if isinstance(body, list) else []
                for name, body in (raw.get("shared_assertions", {}) or {}).items()
            },
        )

    def _load_apis(self, raw: Dict[str, Any]) -> Dict[str, ApiTemplate]:
        # apis.yaml 的有效内容位于顶层 apis 节点。
        apis_raw = raw.get("apis", {}) or {}
        # 将每个 api_id 下的 YAML dict 转成 ApiTemplate 对象。
        return {
            api_id: ApiTemplate(
                id=api_id,
                meta=body.get("meta", {}) or {},
                request=body.get("request", {}) or {},
                parameters=body.get("parameters", {}) or {},
                before_steps=self._load_hook_step_list(body.get("before_steps", [])),
                after_steps=self._load_hook_step_list(body.get("after_steps", [])),
                extract_ref=body.get("extract_ref", []) or [],
                extract=body.get("extract", []) or [],
                assertions_ref=body.get("assertions_ref", []) or [],
                assertions=body.get("assertions", []) or [],
            )
            for api_id, body in apis_raw.items()
            if isinstance(body, dict)
        }

    def _load_cases(self, raw: Dict[str, Any]) -> Dict[str, ApiCase]:
        # cases.yaml 的有效内容位于顶层 cases 节点。
        cases_raw = raw.get("cases", {}) or {}
        cases: Dict[str, ApiCase] = {}
        for case_id, body in cases_raw.items():
            if not isinstance(body, dict):
                continue
            # v0.2 schema 收敛: 拒绝旧的 cases.<id>.api / before_steps / after_steps,
            # 给出明确迁移路径, 避免 YAML 改名失败时被静默忽略。
            self._reject_deprecated_case_fields(case_id, body)
            cases[case_id] = ApiCase(
                id=case_id,
                use=body.get("use", ""),
                meta=body.get("meta", {}) or {},
                request=body.get("request", {}) or {},
                extract_ref=body.get("extract_ref", []) or [],
                extract=body.get("extract", []) or [],
                assertions_ref=body.get("assertions_ref", []) or [],
                assertions=body.get("assertions", []) or [],
                # 记录 YAML 实际出现的字段，后续 Composer 用它区分继承和显式覆盖。
                provided_fields=set(body.keys()),
            )
        return cases

    def _reject_deprecated_case_fields(self, case_id: str, body: Dict[str, Any]) -> None:
        if "api" in body:
            self._raise_validation(
                reason=f"cases.{case_id}.api 已废弃, 请改用 cases.{case_id}.use",
                yaml_location=f"cases.{case_id}.api",
                hint="把 cases.<id>.api 整体改名为 cases.<id>.use, 语义不变",
            )
        for deprecated in ("before_steps", "after_steps"):
            if deprecated in body:
                self._raise_validation(
                    reason=f"cases.{case_id}.{deprecated} 已废弃, ApiCase 不再承载 hooks",
                    yaml_location=f"cases.{case_id}.{deprecated}",
                    hint="hooks 请上移到 ApiTemplate.before_steps/after_steps, 或改写到 Scenario.steps[] 末尾的 inline action",
                )

    def _load_scenarios(self, scenarios_dir: Path) -> Dict[str, Scenario]:
        # 新结构要求场景必须放在 Scenarios 目录下。
        if not scenarios_dir.exists() or not scenarios_dir.is_dir():
            self._raise_validation(
                reason="未找到场景目录",
                yaml_location=str(scenarios_dir),
                hint="请检查新结构目录是否存在",
            )

        # scenarios 用于按 scenario_id 去重和建立快速索引。
        scenarios: Dict[str, Scenario] = {}
        # 按文件名排序读取，保证不同机器上的加载顺序稳定。
        for file_path in sorted(scenarios_dir.glob("*.yaml"), key=lambda p: p.name):
            # 每个 YAML 文件对应一个 Scenario。
            raw = load_yaml_file(file_path)
            # 将原始 YAML 转成 Scenario 对象，并记录来源文件名。
            scenario = self._load_one_scenario(raw, source=file_path.name)
            # scenario_id 必须全局唯一，同目录重复时直接报错。
            if scenario.id in scenarios:
                self._raise_validation(
                    reason=f"scenario_id 重复: {scenario.id}",
                    yaml_location=f"{file_path.name}.scenario_id",
                )
            # 缓存转换后的场景对象。
            scenarios[scenario.id] = scenario

        # 最小资产至少需要有一个场景，否则计划和执行链没有业务流入口。
        if not scenarios:
            self._raise_validation(
                reason="未加载到任何 scenario",
                yaml_location="Scenarios",
            )
        # 返回以 scenario_id 为 key 的场景索引。
        return scenarios

    def _load_one_scenario(self, raw: Dict[str, Any], *, source: str) -> Scenario:
        scenario_id = raw.get("scenario_id", "")
        # v0.2 schema 收敛: 拒绝旧的 scenarios.<id>.finally_steps,
        # 同语义在 v0.2 改用 Scenario.steps[] 末尾 + always_run: true 表达。
        if "finally_steps" in raw:
            self._raise_validation(
                reason=f"scenarios.{scenario_id or source}.finally_steps 已废弃",
                yaml_location=f"scenarios.{scenario_id or source}.finally_steps",
                hint=(
                    "请把原 finally_steps 中的动作迁移到 Scenario.steps[] 末尾, "
                    "并加上 always_run: true（接口清理用 use, SQL/脚本清理用 action）"
                ),
            )
        # hooks 使用 HookStep，业务流程 steps 才使用 ScenarioStep。
        before_steps = self._load_hook_step_list(raw.get("before_steps", []))
        steps = self._load_scenario_step_list(raw.get("steps", []), scenario_id=scenario_id)
        after_steps = self._load_hook_step_list(raw.get("after_steps", []))

        datasets = []
        for dataset in raw.get("datasets", []) or []:
            if not isinstance(dataset, dict):
                continue
            datasets.append(
                ScenarioDataset(
                    name=dataset.get("name", ""),
                    variables=dataset.get("variables", {}) or {},
                )
            )

        # 返回场景对象，source 用于后续错误定位和报告辅助信息。
        return Scenario(
            id=scenario_id,
            env=raw.get("env"),
            meta=raw.get("meta", {}) or {},
            datasets=datasets,
            before_steps=before_steps,
            steps=steps,
            after_steps=after_steps,
            assertions_ref=list(raw.get("assertions_ref", []) or []),
            assertions=list(raw.get("assertions", []) or []),
            source=source,
        )

    def _load_hook_step_list(self, raw_steps: Any) -> list[HookStep]:
        steps: list[HookStep] = []
        for step in raw_steps or []:
            if not isinstance(step, dict):
                continue
            steps.append(
                HookStep(
                    id=step.get("id", ""),
                    action=step.get("action", {}) or {},
                    delay=step.get("delay"),
                    raw=step,
                )
            )
        return steps

    def _load_scenario_step_list(self, raw_steps: Any, *, scenario_id: str = "") -> list[ScenarioStep]:
        steps: list[ScenarioStep] = []
        for index, step in enumerate(raw_steps or [], start=1):
            if not isinstance(step, dict):
                continue
            step_id = step.get("id", "")
            use_value = step.get("use")
            action_value = step.get("action")
            # use 与 action 必须 XOR：必须填一个、且只能填一个。
            # 在 load 阶段就拦截, 避免后续 Composer 拿到歧义 step 后不可用。
            self._validate_step_use_action_xor(
                scenario_id=scenario_id,
                index=index,
                step_id=step_id,
                use_value=use_value,
                action_value=action_value,
            )
            steps.append(
                ScenarioStep(
                    id=step_id,
                    use=use_value if use_value not in (None, "") else None,
                    action=action_value if action_value else None,
                    override=step.get("override", {}) or {},
                    delay=step.get("delay"),
                    always_run=bool(step.get("always_run", False)),
                    continue_on_error=bool(step.get("continue_on_error", False)),
                )
            )
        return steps

    def _validate_step_use_action_xor(
        self,
        *,
        scenario_id: str,
        index: int,
        step_id: str,
        use_value: Any,
        action_value: Any,
    ) -> None:
        # use 视空字符串/None 为"未填"; action 视空 dict/None 为"未填"。
        has_use = isinstance(use_value, str) and use_value.strip() != ""
        has_action = isinstance(action_value, dict) and len(action_value) > 0
        location_root = f"scenarios.{scenario_id or '?'}.steps[{index}]"
        if has_use and has_action:
            self._raise_validation(
                reason=(
                    f"scenario step '{step_id}' 同时配置了 use 和 action, "
                    "v0.2 schema 要求 use 与 action 互斥"
                ),
                yaml_location=location_root,
                hint="一个 step 只能引用 case (use:) 或承载 inline action (action:), 二选一",
            )
        if not has_use and not has_action:
            self._raise_validation(
                reason=(
                    f"scenario step '{step_id}' 既没有 use 也没有 action, "
                    "v0.2 schema 要求 use 与 action 必须 XOR 填写一项"
                ),
                yaml_location=location_root,
                hint="引用 case 请填 use: case_xxx, 内联动作请填 action: {kind: wait/sql/script}",
            )

    def _load_plans(self, raw: Dict[str, Any]) -> Dict[str, TestPlan]:
        # plans.yaml 的有效内容位于顶层 plans 节点。
        plans_raw = raw.get("plans", {}) or {}
        # 将每个 plan_id 下的 YAML dict 转成 TestPlan 对象。
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
        # 读取 api 前先检查 ID 是否存在，缺失时给出可用 ID 列表。
        if api_id not in self.apis:
            self._raise_missing("api", api_id, sorted(self.apis.keys()))
        return self.apis[api_id]

    def get_case(self, case_id: str) -> ApiCase:
        # 读取 case 前先检查 ID 是否存在，缺失时给出可用 ID 列表。
        if case_id not in self.cases:
            self._raise_missing("case", case_id, sorted(self.cases.keys()))
        return self.cases[case_id]

    def get_scenario(self, scenario_id: str) -> Scenario:
        # 读取 scenario 前先检查 ID 是否存在，缺失时给出可用 ID 列表。
        if scenario_id not in self.scenarios:
            self._raise_missing("scenario", scenario_id, sorted(self.scenarios.keys()))
        return self.scenarios[scenario_id]

    def get_plan(self, plan_id: str) -> TestPlan:
        # 读取 plan 前先检查 ID 是否存在，缺失时给出可用 ID 列表。
        if plan_id not in self.plans:
            self._raise_missing("plan", plan_id, sorted(self.plans.keys()))
        return self.plans[plan_id]

    def get_env(self, env_name: Optional[str] = None) -> EnvProfile:
        # config 为空说明仓库尚未 load，不能解析环境。
        if self.config is None:
            self._raise_validation(reason="Repository 尚未 load", yaml_location="config")

        # 未显式传 env_name 时使用 config.active_env。
        resolved_env = env_name or self.config.active_env
        # 解析后的环境名必须存在于 config.envs。
        if resolved_env not in self.config.envs:
            self._raise_missing("env", resolved_env, sorted(self.config.envs.keys()))
        # 返回当前环境配置，供执行器和 RequestResolver 使用。
        return self.config.envs[resolved_env]

    def list_ids(self) -> Dict[str, List[str]]:
        # 返回排序后的各类 ID，CLI validate 用它输出资产数量。
        return {
            "apis": sorted(self.apis.keys()),
            "cases": sorted(self.cases.keys()),
            "scenarios": sorted(self.scenarios.keys()),
            "plans": sorted(self.plans.keys()),
        }

    def _raise_missing(self, asset_type: str, asset_id: str, available: List[str]):
        # 缺失资产统一转成 Repository 加载/读取失败，并附带可用 ID。
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
        hint: str = "请检查新结构 YAML 资产",
        extra: Optional[Dict[str, Any]] = None,
    ):
        # 构造统一的校验异常上下文，保持 Repository 对外错误格式一致。
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
