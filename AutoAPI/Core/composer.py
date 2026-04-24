from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from Exceptions.AutoApiException import (
    ExceptionCode,
    ValidationException,
    build_api_exception_context,
)
from Schema.data_models import ApiCase, ApiTemplate, ExecutableCase, ExecutableStep, ScenarioStep


EMPTY_BY_FIELD = {
    # 字段被显式写成 null 时，不保留父级值，而是按字段类型清空。
    "headers": {},
    "params": {},
    "body": {},
    "files": {},
    "request": {},
    "extract": [],
    "assertions": [],
    "before_steps": [],
    "after_steps": [],
    "body_type": None,
}


class Composer:
    """
    Compose P0 assets into executable runtime objects.

    Override semantics are intentionally simple: a present field replaces the
    inherited field entirely; missing fields inherit; null clears the field.
    """

    # request 内只允许这些字段被 ApiCase 或 ScenarioStep 做字段级整体覆盖。
    REQUEST_FIELDS = ("headers", "params", "body", "files", "body_type")
    # request 外的运行规则同样只做整体替换，不做 deep merge。
    TOP_LEVEL_FIELDS = ("before_steps", "after_steps", "extract", "assertions")

    def compose_case(self, api: ApiTemplate, case: ApiCase) -> ExecutableCase:
        # 用例层只能覆盖请求参数，method/path 必须固定继承自 ApiTemplate。
        self._ensure_no_method_path(case.request, f"cases.{case.id}.request")

        # 将模板层和用例层合成为可直接执行的单接口对象。
        return ExecutableCase(
            # 记录来源 case，后续报告和错误上下文都依赖这个 ID。
            case_id=case.id,
            # 记录来源 api，host_rules 和报告需要知道模板身份。
            api_id=api.id,
            # 用例 meta 只复制快照，避免执行期改动污染仓库缓存。
            meta=deepcopy(case.meta),
            # 模板 meta 单独保存，主要用于读取 module 等模板级信息。
            api_meta=deepcopy(api.meta),
            # request 使用 P0 字段级覆盖规则合成。
            request=self._compose_request(api.request, case.request),
            # hooks/extract/assertions 通过 provided_fields 区分继承和覆盖。
            before_steps=self._case_field(api.before_steps, case, "before_steps"),
            after_steps=self._case_field(api.after_steps, case, "after_steps"),
            extract=self._case_field(api.extract, case, "extract"),
            assertions=self._case_field(api.assertions, case, "assertions"),
        )

    def compose_step(
        self,
        executable_case: ExecutableCase,
        step: ScenarioStep,
        *,
        scenario_id: str,
    ) -> ExecutableStep:
        # 场景步骤未写 override 时按空 dict 处理，保持继承已有 ExecutableCase。
        override = step.override or {}
        # request 子节点单独取出，便于校验 method/path 和执行字段级覆盖。
        override_request = override.get("request", {}) or {}
        # 步骤级 override 也不能改 method/path，避免场景绕过接口模板定义。
        self._ensure_no_method_path(override_request, f"scenarios.{scenario_id}.steps.{step.id}.override.request")

        # 将已合成的 ExecutableCase 叠加当前步骤 override，得到场景步骤执行对象。
        return ExecutableStep(
            # 保留场景和步骤 ID，便于报告展示和失败定位。
            scenario_id=scenario_id,
            step_id=step.id,
            # case_id/api_id 不允许在步骤层改变，只透传来源关系。
            case_id=executable_case.case_id,
            api_id=executable_case.api_id,
            # meta/api_meta 复制快照，避免步骤级执行污染 case 级对象。
            meta=deepcopy(executable_case.meta),
            api_meta=deepcopy(executable_case.api_meta),
            # request 继续使用字段级覆盖，override.request 只影响当前步骤。
            request=self._compose_request(executable_case.request, override_request),
            # 未写 override 字段时传入哨兵值，确保可以区分“未写”和“写 null”。
            before_steps=self._replace_field(
                executable_case.before_steps,
                override.get("before_steps", self._missing()),
                "before_steps",
            ),
            after_steps=self._replace_field(
                executable_case.after_steps,
                override.get("after_steps", self._missing()),
                "after_steps",
            ),
            extract=self._replace_field(
                executable_case.extract,
                override.get("extract", self._missing()),
                "extract",
            ),
            assertions=self._replace_field(
                executable_case.assertions,
                override.get("assertions", self._missing()),
                "assertions",
            ),
        )

    def _compose_request(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        # 先复制父级 request，防止合成结果反向修改模板或用例缓存。
        out = deepcopy(base or {})
        # override 为空时仍按空 dict 遍历，减少调用方分支。
        override = override or {}

        # P0 只对允许覆盖的 request 字段做字段级整体替换。
        for field in self.REQUEST_FIELDS:
            # 字段只要在 override 中出现，就替换父级值；未出现则继承。
            if field in override:
                # 显式 null 通过 _value_or_empty 转为该字段的空值。
                out[field] = self._value_or_empty(override[field], field)

        # 返回新的 request dict，调用方可继续安全修改。
        return out

    def _replace_field(self, base_value: Any, override_value: Any, field: str) -> Any:
        # 哨兵值表示 YAML 中没有写该字段，应完整继承父级值。
        if override_value is self._missing():
            return deepcopy(base_value)
        # 字段存在时整体替换；若写 null，则按字段类型清空。
        return self._value_or_empty(override_value, field)

    def _case_field(self, base_value: Any, case: ApiCase, field: str) -> Any:
        # 用 provided_fields 判断 YAML 是否真的写过该字段，避免默认空列表误判为覆盖。
        if field not in case.provided_fields:
            return deepcopy(base_value)
        # 用例显式写了该字段时，按字段级整体覆盖模板值。
        return self._value_or_empty(getattr(case, field), field)

    def _value_or_empty(self, value: Any, field: str) -> Any:
        # null 的语义是“清空继承值”，不是保留 None 直接进入执行链。
        if value is None:
            return deepcopy(EMPTY_BY_FIELD.get(field))
        # 非 null 值复制后返回，避免复用 YAML 原始对象。
        return deepcopy(value)

    def _ensure_no_method_path(self, request: Dict[str, Any], yaml_location: str) -> None:
        # method/path 只能来自 ApiTemplate，所有下层覆盖都要拦截。
        forbidden = {"method", "path"} & set((request or {}).keys())
        if forbidden:
            # 构造带 YAML 定位的业务异常，方便用户直接改对应字段。
            error_context = build_api_exception_context(
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="非法覆盖 method/path",
                reason=f"case 或 scenario step 不允许覆盖字段: {sorted(forbidden)}",
                yaml_location=yaml_location,
                hint="method/path 只能来自 ApiTemplate",
            )
            raise ValidationException(error_context)

    @staticmethod
    def _missing():
        # 返回模块级唯一哨兵，用于区分字段缺失和值为 None。
        return _MISSING


# 模块级哨兵对象必须唯一，才能用 is 做缺失判断。
_MISSING = object()
