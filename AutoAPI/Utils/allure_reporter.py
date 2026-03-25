import json
import traceback
from pathlib import Path
from typing import Optional, Any

import allure
from allure_commons.types import AttachmentType

from Engine.results import PreparedRequest, ResponseSnapshot, AssertionResult, CaseResult, FlowResult
from Exceptions.AutoApiException import AutoApiException, ExceptionCode
from Schema.data_validation import FlowBundle


class AllureReporter:
    """
      Allure 适配器
        - 统一挂请求/响应/提取等信息
        - 统一写 environment。properties 和 categories。json
    """
    @classmethod
    def step(cls, title: str):
        """
          获取 allure.step 上下文管理器
        :param title: 当前步骤标题, 用于报告页面展示步骤名称
        """
        return allure.step(title)

    @classmethod
    def set_single_metadata(cls, api_id: str, data_index: int, active_env: str):
        """
          为 single 用例写入 allure 元数据
        :param api_id: 当前执行的接口 id
        :param data_index: 当前接口数据驱动下标
        :param active_env: 当前激活的环境名称
        """
        # 设置 parent_suite 用于顶层目录分类
        allure.dynamic.parent_suite("接口自动化")
        # 设置 suite, 表示当前是单接口测试集合
        allure.dynamic.suite("single")
        # 设置 sub suite, 表示当前属于接口库级测试
        allure.dynamic.sub_suite("接口库")
        # 动态设置当前测试标题, 显示接口 id 和数据下标
        allure.dynamic.title(f"单接口 | {api_id}[data_{data_index}]")
        # 显式挂 api_id, 便于在报告中检索与筛选
        allure.dynamic.parameter("api_id", api_id)
        # 显式挂 data_index, 便于区分同接口的不同数据集
        allure.dynamic.parameter("data_index", data_index)
        # 显式挂 active_env, 便于区分不同环境执行记录
        allure.dynamic.parameter("active_env", active_env)

    @classmethod
    def set_flow_metadata(cls, flow: FlowBundle, active_env):
        """
          为 业务流 用例写入 allure 元数据

        :param flow: 业务流对象
        :param active_env: 当前激活的环境名称
        """
        # 设置 parent_suite 用于顶层目录分类
        allure.dynamic.parent_suite("接口自动化")
        # 设置 suite, 表示当前是业务流测试集合
        allure.dynamic.suite("flow")
        # 设置 sub suite, 表示当前属于业务流测试
        allure.dynamic.sub_suite("业务流")
        # 动态设置当前测试标题, 显示业务流 id 和数据下标
        allure.dynamic.title(f"业务流 | {flow.flow_id}")
        # 显式挂 flow id, 便于在报告中检索与筛选
        allure.dynamic.parameter("flow_id", flow.flow_id)
        # 显式挂 active_env, 便于区分不同环境执行记录
        allure.dynamic.parameter("active_env", active_env)
        # 显式挂 flow 来源, 便于定位具体 YAML 来源
        allure.dynamic.parameter("flow_source", flow.source)

        # 读取 flow.common 配置, 不存在时回退为空 dict
        common = flow.common or {}
        if common.get("allure_epic"):
            allure.dynamic.epic(common.get("allure_epic"))
        if common.get("allure_feature"):
            allure.dynamic.feature(common.get("allure_feature"))
        if common.get("allure_story"):
            allure.dynamic.story(common.get("allure_story"))

    @classmethod
    def attach_json(cls, name: str, data):
        """
          把任意 data 对象作为 JSON 附件挂入报告
        :param name: 附件名称
        :param data: 任意可序列化对象
        """
        body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
        allure.attach(body, name=name, attachment_type=AttachmentType.JSON)

    @classmethod
    def attach_text(cls, name: str, text):
        """
          把文本内容作为纯文本附件挂入报告
        :param name: 附件名称
        :param text: 文本内容, 可传任意对象, 内部会强制转为字符串
        """
        allure.attach(str(text), name=name, attachment_type=AttachmentType.TEXT)

    @classmethod
    def attach_bytes(cls, name: str, data: bytes, *, attachment_type=None, extension: Optional[str] = None):
        """
          把二进制数据挂入报告

        :param name: 附件名称
        :param data: 二进制内容
        :param attachment_type: 附件类型, 可用于指定媒体类型
        :param extension: 附件后缀, 用于报告导出时标识文件扩展名
        """
        allure.attach(data, name=name, attachment_type=attachment_type, extension=extension)

    @classmethod
    def attach_context(cls, name: str, ctx):
        """
          把运行时的上下文变量挂入报告

        :param name: 附件名称
        :param ctx: 运行时上下文对象
        """
        # 为空直接返回
        if ctx is None:
            return

        try:
            payload = ctx.snapshot()
        except Exception as e:
            payload = {"_error": f"ctx.snapshot() 失败: {e}"}
        cls.attach_json(name, payload)

    @classmethod
    def attach_prepared_request(cls, request: PreparedRequest):
        """
          把已构建的请求对象挂入报告
        :param request: PreparedRequest 对象
        """
        if request is None:
            return
        cls.attach_json("构建的请求参数", request.to_dict())

    @classmethod
    def attach_response_snapshot(cls, response: ResponseSnapshot):
        """
          把响应摘要对象挂入报告
        :param response: ResponseSnapshot 对象
        """
        if response is None:
            return
        cls.attach_json("响应摘要", response.to_dict())

    @classmethod
    def attach_extract_trace(cls, extract_trace: list[dict[str, Any]]):
        """
          把提取规则执行轨迹挂入报告
        :param extract_trace: 提取规则轨迹列表, 一般每条对应一条 extract 规则的执行结构
        """
        if not extract_trace:
            return
        cls.attach_json("提取规则轨迹", extract_trace)

    @classmethod
    def attach_extract_out(cls, extract_out: dict[str, Any]):
        """
          把最终提取响应数据的结果挂入报告
        :param extract_out: 提取的响应数据
        """
        if not extract_out:
            return
        cls.attach_json("提取的响应数据", extract_out)

    @classmethod
    def attach_assertion_result(cls, index: int, item: AssertionResult):
        """
          把单条断言结果挂入报告
        :param index: 断言序号
        :param item: AssertionResult 对象
        """
        if item is None:
            return
        cls.attach_json(f"第 {index} 条断言结果", item.to_dict())

    @classmethod
    def attach_case_result(cls, result: CaseResult):
        """
          把 single 里单个接口执行中生命周期产生的最终结果挂入报告
        :param result: CaseResult 对象
        """
        if result is None:
            return
        cls.attach_json("单个接口执行总结果", result.to_dict())

    @classmethod
    def attach_flow_result(cls, result: FlowResult):
        """
          把一条业务流执行过程中产生的总结果挂入报告
        :param result: FlowResult 对象
        """
        if result is None:
            return
        cls.attach_json("单个业务流执行总结果", result.to_dict())

    @classmethod
    def attach_execution_state(cls, state):
        """
          把接口生命周期的执行状态挂入报告
        :param state: ExecutionState 对象
        """
        if state is None:
            return
        payload = {
            "当前生命周期已执行的 auth_profile": sorted(state.executed_profiles),
            "当前生命周期已执行的 depends_on": sorted(state.executed_depends),
            "当前生命周期 depends_on 的访问链": list(state.visiting_api_chain),
            "cleanup 错误": [str(item) for item in state.cleanup_errors],
        }
        cls.attach_json("本次接口执行状态", payload)

    @classmethod
    def attach_exception(cls, exc: Exception, *, traceback_text: Optional[str] = None):
        """
          把异常文本、异常栈和自定义的结构化异常上下文挂入报告
        :param exc: 异常对象
        :param traceback_text: 程序生成的 traceback 文本, 若不传则内部自动生成
        """
        # 若当前异常对象已经挂入报告, 则直接返回, 避免重复挂载
        if getattr(exc, "_allure_attached", False):
            return

        # 给异常对象打标记, 表示已经挂过 allure 附件了
        setattr(exc, "_allure_attached", True)

        # 挂异常文本, 快速阅读错误摘要
        cls.attach_text("异常摘要", str(exc))
        # 优先使用外部传入的 traceback 文本, 否则自动获取当前异常栈
        final_tb = traceback_text or traceback.format_exc()
        # 若存在则挂入
        if final_tb and final_tb.strip():
            cls.attach_text("异常栈", final_tb)

        # 若异常属于框架自定义异常体系, 则继续挂结构化上下文
        if isinstance(exc, AutoApiException):
            cls.attach_json("结构化异常上下文", exc.error_context.to_dict())

    @classmethod
    def write_environment_file(cls, results_dir: Path, env_map: dict[str, Any]):
        """
          写入 environment.properties 文件
        :param results_dir: allure-results 目录
        :param env_map: 环境信息字典
        """
        if not results_dir:
            return

        # 确保结果目录存在, 不存在则递归创建
        results_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for key, value in env_map.items():
            lines.append(f"{key}={value}")
        (results_dir / "environment.properties").write_text("\n".join(lines), encoding="utf-8")

    @classmethod
    def build_default_categories(cls) -> list[dict[str, Any]]:
        """
          生成默认的归类规则, 让 allure 报告可以按照异常类别归类失败用例
        """
        return [
            # 定义 "变量渲染异常" 分类
            {
                "name": "变量渲染异常",  # 分类名称
                "matchedStatuses": ["failed", "broken"],  # 该分类匹配的测试状态
                "messageRegex": f".*{ExceptionCode.VAR_RENDER_ERROR.value}.*",  # 根据异常码匹配变量渲染异常
            },
            # 定义 "请求构建异常" 分类
            {
                "name": "请求构建异常",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": f".*{ExceptionCode.REQUEST_BUILD_ERROR.value}.*",
            },
            # 定义 "请求发送异常" 分类
            {
                "name": "请求发送异常",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": f".*{ExceptionCode.REQUEST_SEND_ERROR.value}.*",
            },
            # 定义 "响应提取异常" 分类
            {
                "name": "响应提取异常",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": f".*{ExceptionCode.RESPONSE_EXTRACT_ERROR.value}.*",
            },
            # 定义 "断言失败" 分类
            {
                "name": "断言失败",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": f".*{ExceptionCode.ASSERT_ERROR.value}.*",
            },
            # 定义 "业务编排异常" 分类
            {
                "name": "业务编排异常",
                "matchedStatuses": ["failed", "broken"],
                "messageRegex": f".*{ExceptionCode.PIPELINE_ERROR.value}.*",
            },
        ]

    @classmethod
    def write_categories_file(cls, results_dir: Path, categories: Optional[list[dict[str, Any]]] = None):
        """
          写 categories.json 文件, 让报告首页和 defects 视图按异常类别展示问题分布
        :param results_dir: allure-results 目录
        :param categories: 自定义 categories 列表, 不传则使用默认的
        """
        if not results_dir:
            return
        # 确保结果目录存在, 不存在则递归创建
        results_dir.mkdir(parents=True, exist_ok=True)
        payload = categories if categories is not None else cls.build_default_categories()

        # 把分类列表序列化为格式化 JSON
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        (results_dir / "categories.json").write_text(body, encoding="utf-8")
