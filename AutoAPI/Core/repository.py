from pathlib import Path
from typing import Dict, Optional, Union, List, Any

from Exceptions.AutoApiException import build_api_exception_context, ExceptionCode, ValidationException
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


if __name__ == "__main__":
    data = YamlRepository("./Data/config.yaml")



