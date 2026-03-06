from pathlib import Path
from typing import Dict, Optional, Union, List, Any

from Exceptions.AutoApiException import build_api_exception_context, ExceptionPhase, ExceptionCode, ValidationException
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
                phase=ExceptionPhase.VALIDATION,
                error_code=ExceptionCode.VALIDATION_ERROR,
                message="接口库不存在",
                reason=f"single.yaml.apis 不存在接口：{api_id}",
            )
            raise ValidationException(error_context)
        # 返回 api
        return self.apis[api_id]

    def get_flow(self, flow_id: str) -> FlowBundle:
        """
          获取 multiple.yaml 的校验后结构化对象（包含 common）
        """
        if flow_id is None or flow_id not in self.flows:
            # 构建明确异常上下文
            error_context = build_api_exception_context(
                phase=ExceptionPhase.VALIDATION,
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


if __name__ == "__main__":
    data = YamlRepository("./Data/config.yaml")



