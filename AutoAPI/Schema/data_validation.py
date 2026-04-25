from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
from Schema.data_models import ProjectAssets


class YamlSchemaValidator:
    def validate_project(self, assets: ProjectAssets) -> None:
        """
          P0 新模型基础校验入口。

          当前阶段不做严格字段 schema 校验，只检查执行链必须依赖的基础关系。
        """
        # 先检查所有资产 ID 是否非空且全局唯一，这是后续引用校验的前提。
        self._validate_p0_global_ids(assets)
        # 再检查 case/scenario/plan 的引用关系是否都能落到已加载资产。
        self._validate_p0_references(assets)
        # 然后检查 ApiTemplate 层的 method + path 是否唯一。
        self._validate_p0_duplicate_api_path(assets)
        # 最后检查环境和 host_rules 是否能支撑请求构建。
        self._validate_p0_envs(assets)
        # 最后检查公共断言/提取引用是否都能落到共享注册表。
        self._validate_p0_shared_rule_refs(assets)

    def _validate_p0_global_ids(self, assets: ProjectAssets) -> None:
        # seen 记录 ID 第一次出现的资产组，用于发现跨层重复。
        seen = {}
        # P0 要求 api/case/scenario/plan 的 ID 全局唯一。
        groups = [
            ("apis", assets.apis.keys()),
            ("cases", assets.cases.keys()),
            ("scenarios", assets.scenarios.keys()),
            ("plans", assets.plans.keys()),
        ]

        # 逐组遍历所有 ID，既检查空值，也检查跨组重复。
        for group_name, ids in groups:
            for asset_id in ids:
                # ID 必须是非空字符串，防止后续引用定位不到具体资产。
                if not isinstance(asset_id, str) or not asset_id.strip():
                    self._raise_validation_exception(
                        reason=f"{group_name} 存在空 ID",
                        yaml_location=group_name,
                    )
                # 任意两类资产复用同一个 ID 都会让直接引用变得歧义。
                if asset_id in seen:
                    self._raise_validation_exception(
                        reason=f"全局 ID 重复: {asset_id}",
                        yaml_location=group_name,
                        extra={"first_seen_in": seen[asset_id], "duplicated_in": group_name},
                    )
                # 记录当前 ID 首次出现的位置。
                seen[asset_id] = group_name

    def _validate_p0_references(self, assets: ProjectAssets) -> None:
        # ApiCase 必须引用一个已存在的 ApiTemplate。
        for case_id, case in assets.cases.items():
            if case.api not in assets.apis:
                self._raise_validation_exception(
                    reason=f"case 引用的 api 不存在: {case.api}",
                    yaml_location=f"cases.{case_id}.api",
                    extra={"case_id": case_id, "available_apis": sorted(assets.apis.keys())},
                )

        # Scenario 需要校验可选 env 和每个步骤的 use 引用。
        for scenario_id, scenario in assets.scenarios.items():
            # 场景显式指定 env 时，该 env 必须存在于 config.envs。
            if scenario.env is not None and scenario.env not in assets.config.envs:
                self._raise_validation_exception(
                    reason=f"scenario 指定的 env 不存在: {scenario.env}",
                    yaml_location=f"scenarios.{scenario_id}.env",
                    extra={"available_envs": sorted(assets.config.envs.keys())},
                )

            # dataset 名称在同一场景内必须唯一，且不能为空。
            seen_dataset_names = set()
            for dataset_index, dataset in enumerate(scenario.datasets, start=1):
                if not isinstance(dataset.name, str) or not dataset.name.strip():
                    self._raise_validation_exception(
                        reason="scenario dataset.name 不能为空",
                        yaml_location=f"scenarios.{scenario_id}.datasets[{dataset_index}].name",
                    )
                if dataset.name in seen_dataset_names:
                    self._raise_validation_exception(
                        reason=f"scenario dataset.name 重复: {dataset.name}",
                        yaml_location=f"scenarios.{scenario_id}.datasets[{dataset_index}].name",
                    )
                seen_dataset_names.add(dataset.name)

            self._validate_scenario_step_list(assets, scenario_id=scenario_id, steps=scenario.before_steps, field_name="before_steps")
            self._validate_scenario_step_list(assets, scenario_id=scenario_id, steps=scenario.steps, field_name="steps")
            self._validate_scenario_step_list(assets, scenario_id=scenario_id, steps=scenario.after_steps, field_name="after_steps")
            self._validate_scenario_step_list(assets, scenario_id=scenario_id, steps=scenario.finally_steps, field_name="finally_steps")

        # TestPlan 只负责引用已存在的 scenario 和 case，不负责选择环境。
        for plan_id, plan in assets.plans.items():
            # 校验 plan.scenarios 中每个 ID 都存在。
            for scenario_id in plan.scenarios:
                if scenario_id not in assets.scenarios:
                    self._raise_validation_exception(
                        reason=f"plan 引用的 scenario 不存在: {scenario_id}",
                        yaml_location=f"plans.{plan_id}.scenarios",
                        extra={"available_scenarios": sorted(assets.scenarios.keys())},
                    )

            # 校验 plan.cases 中每个 ID 都存在。
            for case_id in plan.cases:
                if case_id not in assets.cases:
                    self._raise_validation_exception(
                        reason=f"plan 引用的 case 不存在: {case_id}",
                        yaml_location=f"plans.{plan_id}.cases",
                        extra={"available_cases": sorted(assets.cases.keys())},
                    )

    def _validate_p0_duplicate_api_path(self, assets: ProjectAssets) -> None:
        # seen 保存已经出现过的 (method, path)，用于检查接口模板是否重复。
        seen = {}
        # 遍历所有 ApiTemplate 的请求定义。
        for api_id, api in assets.apis.items():
            # method 统一转小写，避免 GET/get 被当成两个不同接口。
            method = str(api.request.get("method", "")).lower()
            # path 原样转字符串，后续由请求构建阶段负责拼接 host。
            path = str(api.request.get("path", ""))
            # method + path 是接口模板唯一性约束。
            key = (method, path)

            # 缺 method 或 path 的接口无法构建请求，必须提前报错。
            if not method or not path:
                self._raise_validation_exception(
                    reason=f"api 缺少 method 或 path: {api_id}",
                    yaml_location=f"apis.{api_id}.request",
                )

            # 同一个 method + path 出现两次会让接口模板语义重复。
            if key in seen:
                self._raise_validation_exception(
                    reason=f"method + path 重复: {method.upper()} {path}",
                    yaml_location=f"apis.{api_id}.request",
                    extra={"first_api": seen[key], "duplicated_api": api_id},
                )
            # 记录当前接口的 method + path，供后续接口比较。
            seen[key] = api_id

    def _validate_p0_envs(self, assets: ProjectAssets) -> None:
        # config 是环境校验的入口，包含 active_env、envs、hosts 和 host_rules。
        config = assets.config
        # active_env 必须存在，否则 CLI 和执行器无法选择默认环境。
        if not config.active_env or config.active_env not in config.envs:
            self._raise_validation_exception(
                reason=f"active_env 不存在: {config.active_env}",
                yaml_location="config.active_env",
                extra={"available_envs": sorted(config.envs.keys())},
            )

        # 逐个环境检查 host_rules 是否能解析到已声明的 hosts。
        for env_name, env in config.envs.items():
            # P0 每个环境最多允许一个 default 规则，避免兜底 host 歧义。
            default_count = 0
            # 遍历当前环境下的所有 host_rule，并记录从 1 开始的 YAML 位置。
            for index, rule in enumerate(env.host_rules, start=1):
                location = f"config.envs.{env_name}.host_rules[{index}]"
                # host_rule.host 必须是 env.hosts 中存在的 key。
                if rule.host not in env.hosts:
                    self._raise_validation_exception(
                        reason=f"host_rules 引用的 host 不存在: {rule.host}",
                        yaml_location=f"{location}.host",
                        extra={"available_hosts": sorted(env.hosts.keys())},
                    )
                # 统计 default 规则数量，循环结束后统一判断是否超过 1 个。
                if rule.default:
                    default_count += 1

            # 多个 default 规则会导致没有明确匹配条件时无法唯一选 host。
            if default_count > 1:
                self._raise_validation_exception(
                    reason=f"env 只能存在一个 default host_rule: {env_name}",
                    yaml_location=f"config.envs.{env_name}.host_rules",
                )

            # 环境级 setup / teardown 只能引用已存在的 case。
            for index, case_id in enumerate(env.setup_cases, start=1):
                if case_id not in assets.cases:
                    self._raise_validation_exception(
                        reason=f"env.setup_cases 引用的 case 不存在: {case_id}",
                        yaml_location=f"config.envs.{env_name}.setup_cases[{index}]",
                        extra={"available_cases": sorted(assets.cases.keys())},
                    )
            for index, case_id in enumerate(env.teardown_cases, start=1):
                if case_id not in assets.cases:
                    self._raise_validation_exception(
                        reason=f"env.teardown_cases 引用的 case 不存在: {case_id}",
                        yaml_location=f"config.envs.{env_name}.teardown_cases[{index}]",
                        extra={"available_cases": sorted(assets.cases.keys())},
                    )

            # 当前环境若指定默认鉴权模板，则该模板必须存在。
            if env.auth_profile is not None and env.auth_profile not in env.auth_profiles:
                self._raise_validation_exception(
                    reason=f"env.auth_profile 不存在: {env.auth_profile}",
                    yaml_location=f"config.envs.{env_name}.auth_profile",
                    extra={"available_auth_profiles": sorted(env.auth_profiles.keys())},
                )

            # 鉴权模板中引用的 case 同样必须存在。
            for profile_name, profile in env.auth_profiles.items():
                for index, case_id in enumerate(profile.setup_cases, start=1):
                    if case_id not in assets.cases:
                        self._raise_validation_exception(
                            reason=f"auth_profile.setup_cases 引用的 case 不存在: {case_id}",
                            yaml_location=f"config.envs.{env_name}.auth_profiles.{profile_name}.setup_cases[{index}]",
                            extra={"available_cases": sorted(assets.cases.keys())},
                        )
                for index, case_id in enumerate(profile.teardown_cases, start=1):
                    if case_id not in assets.cases:
                        self._raise_validation_exception(
                            reason=f"auth_profile.teardown_cases 引用的 case 不存在: {case_id}",
                            yaml_location=f"config.envs.{env_name}.auth_profiles.{profile_name}.teardown_cases[{index}]",
                            extra={"available_cases": sorted(assets.cases.keys())},
                        )

    def _validate_p0_shared_rule_refs(self, assets: ProjectAssets) -> None:
        for api_id, api in assets.apis.items():
            self._validate_shared_ref_list(
                refs=api.extract_ref,
                registry=assets.config.shared_extracts,
                yaml_location=f"apis.{api_id}.extract_ref",
                reason_prefix="api.extract_ref",
            )
            self._validate_shared_ref_list(
                refs=api.assertions_ref,
                registry=assets.config.shared_assertions,
                yaml_location=f"apis.{api_id}.assertions_ref",
                reason_prefix="api.assertions_ref",
            )

        for case_id, case in assets.cases.items():
            self._validate_shared_ref_list(
                refs=case.extract_ref,
                registry=assets.config.shared_extracts,
                yaml_location=f"cases.{case_id}.extract_ref",
                reason_prefix="case.extract_ref",
            )
            self._validate_shared_ref_list(
                refs=case.assertions_ref,
                registry=assets.config.shared_assertions,
                yaml_location=f"cases.{case_id}.assertions_ref",
                reason_prefix="case.assertions_ref",
            )

        for scenario_id, scenario in assets.scenarios.items():
            self._validate_shared_ref_list(
                refs=scenario.assertions_ref,
                registry=assets.config.shared_assertions,
                yaml_location=f"scenarios.{scenario_id}.assertions_ref",
                reason_prefix="scenario.assertions_ref",
            )
            self._validate_scenario_override_shared_refs(
                assets,
                scenario_id=scenario_id,
                steps=scenario.before_steps,
                field_name="before_steps",
            )
            self._validate_scenario_override_shared_refs(
                assets,
                scenario_id=scenario_id,
                steps=scenario.steps,
                field_name="steps",
            )
            self._validate_scenario_override_shared_refs(
                assets,
                scenario_id=scenario_id,
                steps=scenario.after_steps,
                field_name="after_steps",
            )
            self._validate_scenario_override_shared_refs(
                assets,
                scenario_id=scenario_id,
                steps=scenario.finally_steps,
                field_name="finally_steps",
            )

    def _validate_scenario_step_list(self, assets: ProjectAssets, *, scenario_id: str, steps: list, field_name: str) -> None:
        for index, step in enumerate(steps, start=1):
            location = f"scenarios.{scenario_id}.{field_name}[{index}].use"
            if not step.use.startswith("case_"):
                self._raise_validation_exception(
                    reason=f"P0/P1 阶段 scenario step 只能引用 case_ ID: {step.use}",
                    yaml_location=location,
                )
            if step.use not in assets.cases:
                self._raise_validation_exception(
                    reason=f"scenario step 引用的 case 不存在: {step.use}",
                    yaml_location=location,
                    extra={"available_cases": sorted(assets.cases.keys())},
                )

    def _validate_scenario_override_shared_refs(
        self,
        assets: ProjectAssets,
        *,
        scenario_id: str,
        steps: list,
        field_name: str,
    ) -> None:
        for index, step in enumerate(steps, start=1):
            override = step.override or {}
            if "extract_ref" in override:
                self._validate_shared_ref_list(
                    refs=override.get("extract_ref") or [],
                    registry=assets.config.shared_extracts,
                    yaml_location=f"scenarios.{scenario_id}.{field_name}[{index}].override.extract_ref",
                    reason_prefix="scenario.override.extract_ref",
                )
            if "assertions_ref" in override:
                self._validate_shared_ref_list(
                    refs=override.get("assertions_ref") or [],
                    registry=assets.config.shared_assertions,
                    yaml_location=f"scenarios.{scenario_id}.{field_name}[{index}].override.assertions_ref",
                    reason_prefix="scenario.override.assertions_ref",
                )

    def _validate_shared_ref_list(
        self,
        *,
        refs,
        registry: dict,
        yaml_location: str,
        reason_prefix: str,
    ) -> None:
        for ref in refs or []:
            if ref not in registry:
                self._raise_validation_exception(
                    reason=f"{reason_prefix} 引用不存在: {ref}",
                    yaml_location=yaml_location,
                    extra={"available_refs": sorted(registry.keys())},
                )
    def _raise_validation_exception(
        self,
        *,
        reason: str,
        yaml_location: str | None = None,
        hint: str = "请检查 YAML 基础结构和引用关系",
        extra: dict | None = None,
    ) -> None:
        error_context = build_api_exception_context(
            error_code=ExceptionCode.VALIDATION_ERROR,
            message="YAML 基础校验失败",
            reason=reason,
            yaml_location=yaml_location,
            hint=hint,
            extra=extra,
        )
        raise ValidationException(error_context)
