from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
from Schema.data_models import ProjectAssets


class YamlSchemaValidator:
    def validate_project(self, assets: ProjectAssets) -> None:
        """
          新模型基础校验入口.

          当前阶段不做严格字段 schema 校验,只检查执行链必须依赖的基础关系.
        """
        # 先检查所有资产 ID 是否非空且全局唯一,这是后续引用校验的前提.
        self._validate_global_ids(assets)
        # 再检查 case/scenario/plan 的引用关系是否都能落到已加载资产.
        self._validate_references(assets)
        # 然后检查 ApiTemplate 层的 method + path 是否唯一.
        self._validate_duplicate_api_path(assets)
        # 最后检查环境和 host_rules 是否能支撑请求构建.
        self._validate_envs(assets)
        # 最后检查公共断言/提取引用是否都能落到共享注册表.
        self._validate_shared_rule_refs(assets)

    def _validate_global_ids(self, assets: ProjectAssets) -> None:
        # seen 记录 ID 第一次出现的资产组,用于发现跨层重复.
        seen = {}
        # 当前模型要求 api/case/scenario/plan 的 ID 全局唯一.
        groups = [
            ("apis", assets.apis.keys()),
            ("cases", assets.cases.keys()),
            ("scenarios", assets.scenarios.keys()),
            ("plans", assets.plans.keys()),
        ]

        # 逐组遍历所有 ID,既检查空值,也检查跨组重复.
        for group_name, ids in groups:
            for asset_id in ids:
                # ID 必须是非空字符串,防止后续引用定位不到具体资产.
                if not isinstance(asset_id, str) or not asset_id.strip():
                    self._raise_validation_exception(
                        reason=f"{group_name} 存在空 ID",
                        yaml_location=group_name,
                    )
                # 任意两类资产复用同一个 ID 都会让直接引用变得歧义.
                if asset_id in seen:
                    self._raise_validation_exception(
                        reason=f"全局 ID 重复: {asset_id}",
                        yaml_location=group_name,
                        extra={"first_seen_in": seen[asset_id], "duplicated_in": group_name},
                    )
                # 记录当前 ID 首次出现的位置.
                seen[asset_id] = group_name

    def _validate_references(self, assets: ProjectAssets) -> None:
        # ApiCase 必须引用一个已存在的 ApiTemplate.
        for api_id, api in assets.apis.items():
            self._validate_hook_step_list(api.before_steps, yaml_location=f"apis.{api_id}.before_steps")
            self._validate_hook_step_list(api.after_steps, yaml_location=f"apis.{api_id}.after_steps")

        for case_id, case in assets.cases.items():
            if case.use not in assets.apis:
                self._raise_validation_exception(
                    reason=f"case 引用的 api 不存在: {case.use}",
                    yaml_location=f"cases.{case_id}.use",
                    extra={"case_id": case_id, "available_apis": sorted(assets.apis.keys())},
                )

        # Scenario 需要校验可选 env 和每个步骤的 use 引用.
        for scenario_id, scenario in assets.scenarios.items():
            # 场景显式指定 env 时,该 env 必须存在于 config.envs.
            if scenario.env is not None and scenario.env not in assets.config.envs:
                self._raise_validation_exception(
                    reason=f"scenario 指定的 env 不存在: {scenario.env}",
                    yaml_location=f"scenarios.{scenario_id}.env",
                    extra={"available_envs": sorted(assets.config.envs.keys())},
                )

            # dataset 名称在同一场景内必须唯一,且不能为空.
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

            self._validate_hook_step_list(scenario.before_steps, yaml_location=f"scenarios.{scenario_id}.before_steps")
            self._validate_scenario_step_list(assets, scenario_id=scenario_id, steps=scenario.steps, field_name="steps")
            self._validate_hook_step_list(scenario.after_steps, yaml_location=f"scenarios.{scenario_id}.after_steps")

        # TestPlan 只负责引用已存在的 scenario 和 case,不负责选择环境.
        for plan_id, plan in assets.plans.items():
            # 校验 plan.scenarios 中每个 ID 都存在.
            for scenario_id in plan.scenarios:
                if scenario_id not in assets.scenarios:
                    self._raise_validation_exception(
                        reason=f"plan 引用的 scenario 不存在: {scenario_id}",
                        yaml_location=f"plans.{plan_id}.scenarios",
                        extra={"available_scenarios": sorted(assets.scenarios.keys())},
                    )

            # 校验 plan.cases 中每个 ID 都存在.
            for case_id in plan.cases:
                if case_id not in assets.cases:
                    self._raise_validation_exception(
                        reason=f"plan 引用的 case 不存在: {case_id}",
                        yaml_location=f"plans.{plan_id}.cases",
                        extra={"available_cases": sorted(assets.cases.keys())},
                    )

    def _validate_duplicate_api_path(self, assets: ProjectAssets) -> None:
        # seen 保存已经出现过的 (method, path),用于检查接口模板是否重复.
        seen = {}
        # 遍历所有 ApiTemplate 的请求定义.
        for api_id, api in assets.apis.items():
            # method 统一转小写,避免 GET/get 被当成两个不同接口.
            method = str(api.request.get("method", "")).lower()
            # path 原样转字符串,后续由请求构建阶段负责拼接 host.
            path = str(api.request.get("path", ""))
            # method + path 是接口模板唯一性约束.
            key = (method, path)

            # 缺 method 或 path 的接口无法构建请求,必须提前报错.
            if not method or not path:
                self._raise_validation_exception(
                    reason=f"api 缺少 method 或 path: {api_id}",
                    yaml_location=f"apis.{api_id}.request",
                )

            # 同一个 method + path 出现两次会让接口模板语义重复.
            if key in seen:
                self._raise_validation_exception(
                    reason=f"method + path 重复: {method.upper()} {path}",
                    yaml_location=f"apis.{api_id}.request",
                    extra={"first_api": seen[key], "duplicated_api": api_id},
                )
            # 记录当前接口的 method + path,供后续接口比较.
            seen[key] = api_id

    def _validate_envs(self, assets: ProjectAssets) -> None:
        # config 是环境校验的入口,包含 active_env、envs、hosts 和 host_rules.
        config = assets.config
        # active_env 必须存在,否则 CLI 和执行器无法选择默认环境.
        if not config.active_env or config.active_env not in config.envs:
            self._raise_validation_exception(
                reason=f"active_env 不存在: {config.active_env}",
                yaml_location="config.active_env",
                extra={"available_envs": sorted(config.envs.keys())},
            )

        # 逐个环境检查 host_rules 是否能解析到已声明的 hosts.
        for env_name, env in config.envs.items():
            # 每个环境最多允许一个 default 规则,避免兜底 host 歧义.
            default_count = 0
            # 遍历当前环境下的所有 host_rule,并记录从 1 开始的 YAML 位置.
            for index, rule in enumerate(env.host_rules, start=1):
                location = f"config.envs.{env_name}.host_rules[{index}]"
                # host_rule.host 必须是 env.hosts 中存在的 key.
                if rule.host not in env.hosts:
                    self._raise_validation_exception(
                        reason=f"host_rules 引用的 host 不存在: {rule.host}",
                        yaml_location=f"{location}.host",
                        extra={"available_hosts": sorted(env.hosts.keys())},
                    )
                # 统计 default 规则数量,循环结束后统一判断是否超过 1 个.
                if rule.default:
                    default_count += 1

            # 多个 default 规则会导致没有明确匹配条件时无法唯一选 host.
            if default_count > 1:
                self._raise_validation_exception(
                    reason=f"env 只能存在一个 default host_rule: {env_name}",
                    yaml_location=f"config.envs.{env_name}.host_rules",
                )

    def _validate_shared_rule_refs(self, assets: ProjectAssets) -> None:
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
            # action 类 step 没有 override.extract_ref / assertions_ref, 跳过共享引用校验.
            self._validate_scenario_override_shared_refs(
                assets,
                scenario_id=scenario_id,
                steps=[step for step in scenario.steps if step.use is not None],
                field_name="steps",
            )

    def _validate_scenario_step_list(self, assets: ProjectAssets, *, scenario_id: str, steps: list, field_name: str) -> None:
        for index, step in enumerate(steps, start=1):
            base_location = f"scenarios.{scenario_id}.{field_name}[{index}]"
            # use 与 action 的 XOR 互斥已在 Repository 加载阶段拦截, 这里只做引用 / 动作字段校验.
            if step.use is not None:
                use_location = f"{base_location}.use"
                if not step.use.startswith("case_"):
                    self._raise_validation_exception(
                        reason=f"当前阶段 scenario step 只能引用 case_ ID: {step.use}",
                        yaml_location=use_location,
                    )
                if step.use not in assets.cases:
                    self._raise_validation_exception(
                        reason=f"scenario step 引用的 case 不存在: {step.use}",
                        yaml_location=use_location,
                        extra={"available_cases": sorted(assets.cases.keys())},
                    )
                continue
            # step.action 路径: 走和 hooks 同一份 action schema, 让 SQL/脚本清理与 hook 等价.
            action = step.action or {}
            self._validate_inline_action(action, yaml_location=f"{base_location}.action", step_id=step.id)

    def _validate_inline_action(self, action: dict, *, yaml_location: str, step_id: str) -> None:
        """
          hooks 与 Scenario.steps[] 内联 action 共用同一份 action schema 校验.
          step_id 仅用于错误文案（hook 与 inline action 错误前缀略有区别）.
        """
        owner = f"scenario step '{step_id}'"
        self._validate_action_schema(action, yaml_location=yaml_location, owner=owner)

    def _validate_action_schema(self, action: dict, *, yaml_location: str, owner: str) -> None:
        if not isinstance(action, dict) or not action:
            self._raise_validation_exception(
                reason=f"{owner} 的 action 不能为空",
                yaml_location=yaml_location,
            )
        kind = action.get("kind")
        if kind not in {"wait", "sql", "script"}:
            self._raise_validation_exception(
                reason=f"{owner} 的 action.kind 暂只支持 wait/sql/script: {kind}",
                yaml_location=f"{yaml_location}.kind",
            )

        if kind == "wait":
            if "seconds" not in action:
                self._raise_validation_exception(
                    reason=f"{owner} 的 action.kind=wait 必须配置 seconds",
                    yaml_location=f"{yaml_location}.seconds",
                )
            if not isinstance(action["seconds"], (int, float)):
                self._raise_validation_exception(
                    reason=f"{owner} 的 action.seconds 必须是数字: {action['seconds']!r}",
                    yaml_location=f"{yaml_location}.seconds",
                )
            return

        if kind == "script":
            self._validate_script_action(action, yaml_location=yaml_location, owner=owner)
            return

        # kind == "sql": 真实执行延后到 P2 (PostgreSQL),
        # 第一版只接受 schema 合法（datasource / sql 字段允许存在但不强校验类型）,
        # 让用户可以提前在 YAML 中预声明 sql 占位 step,
        # 到 P2 上线时无需修改 YAML.

    def _validate_script_action(self, action: dict, *, yaml_location: str, owner: str) -> None:
        # command 必填: 字符串或非空字符串列表; 抗 shell 注入由 action_runner 的 shlex.split 与 list-form 保证.
        if "command" not in action:
            self._raise_validation_exception(
                reason=f"{owner} 的 action.kind=script 必须配置 command",
                yaml_location=f"{yaml_location}.command",
            )
        command = action["command"]
        if isinstance(command, list):
            if not command:
                self._raise_validation_exception(
                    reason=f"{owner} 的 action.command list 不能为空",
                    yaml_location=f"{yaml_location}.command",
                )
        elif not (isinstance(command, str) and command.strip()):
            self._raise_validation_exception(
                reason=f"{owner} 的 action.command 必须是非空字符串或字符串列表: {command!r}",
                yaml_location=f"{yaml_location}.command",
            )

        # expect_returncode: 默认 0; 接受 int 或字面量 "any"; 其它类型报错.
        if "expect_returncode" in action:
            expect_rc = action["expect_returncode"]
            if expect_rc != "any" and not isinstance(expect_rc, int):
                self._raise_validation_exception(
                    reason=(
                        f"{owner} 的 action.expect_returncode 第一版只接受整数或字面量 'any': "
                        f"{expect_rc!r}"
                    ),
                    yaml_location=f"{yaml_location}.expect_returncode",
                )

        # timeout: 可选, 必须是数字（subprocess.run 的 timeout 形参语义）.
        if "timeout" in action:
            timeout = action["timeout"]
            if not isinstance(timeout, (int, float)) or timeout <= 0:
                self._raise_validation_exception(
                    reason=f"{owner} 的 action.timeout 必须是正数: {timeout!r}",
                    yaml_location=f"{yaml_location}.timeout",
                )

        # cwd: 可选, 必须是字符串.
        if "cwd" in action and not isinstance(action["cwd"], str):
            self._raise_validation_exception(
                reason=f"{owner} 的 action.cwd 必须是字符串: {action['cwd']!r}",
                yaml_location=f"{yaml_location}.cwd",
            )

        # env: 可选, 必须是 dict.
        if "env" in action and not isinstance(action["env"], dict):
            self._raise_validation_exception(
                reason=f"{owner} 的 action.env 必须是 dict",
                yaml_location=f"{yaml_location}.env",
            )

        # extract: 可选, list of {source ∈ {stdout, stderr, returncode}, as: <name>}.
        if "extract" in action:
            extract_rules = action["extract"]
            if not isinstance(extract_rules, list):
                self._raise_validation_exception(
                    reason=f"{owner} 的 action.extract 必须是 list",
                    yaml_location=f"{yaml_location}.extract",
                )
            for index, rule in enumerate(extract_rules, start=1):
                rule_location = f"{yaml_location}.extract[{index}]"
                if not isinstance(rule, dict):
                    self._raise_validation_exception(
                        reason=f"{owner} 的 action.extract 每一项必须是 dict",
                        yaml_location=rule_location,
                    )
                source = rule.get("source")
                if source not in {"stdout", "stderr", "returncode"}:
                    self._raise_validation_exception(
                        reason=(
                            f"{owner} 的 action.extract.source 第一版只支持 stdout/stderr/returncode: "
                            f"{source!r}"
                        ),
                        yaml_location=f"{rule_location}.source",
                    )
                as_name = rule.get("as")
                if not isinstance(as_name, str) or not as_name.strip():
                    self._raise_validation_exception(
                        reason=f"{owner} 的 action.extract.as 不能为空",
                        yaml_location=f"{rule_location}.as",
                    )

    def _validate_hook_step_list(self, steps: list, *, yaml_location: str) -> None:
        for index, step in enumerate(steps or [], start=1):
            location = f"{yaml_location}[{index}]"
            if "use" in (step.raw or {}):
                self._raise_validation_exception(
                    reason="hooks 只能使用 action，不允许 use 引用 case 或 api",
                    yaml_location=f"{location}.use",
                )
            if not isinstance(step.id, str) or not step.id.strip():
                self._raise_validation_exception(
                    reason="hook.id 不能为空",
                    yaml_location=f"{location}.id",
                )
            self._validate_action_schema(
                step.action or {},
                yaml_location=f"{location}.action",
                owner=f"hook '{step.id}'",
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
