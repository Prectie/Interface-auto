from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

from Base.data_validation import ConfigBundle, ApiItem, FlowBundle, YamlSchemaValidator
from Exceptions.schema_exception import YamlSchemaException
from Utils.print_pretty import print_rich
from Utils.yaml_io import load_yaml_file

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
        self.root_dir = root_dir
        # 初始化校验器
        self._validator = YamlSchemaValidator()
        self.config: Optional[ConfigBundle] = None
        self.apis: Optional[Dict[str, ApiItem]] = None
        self.flows: Optional[FlowBundle] = None

    def load(self):
        """
          读取并严格校验 yaml数据, 并加载到 repository 内存对象中
        """
        # 读取三个 yaml 文件
        config_raw = load_yaml_file(self.root_dir / "config.yaml")
        single_raw = load_yaml_file(self.root_dir / "single.yaml")
        multiple_raw = load_yaml_file(self.root_dir / "multiple.yaml")

        # 校验并处理原始数据
        validated = self._validator.validate_all(config_raw, single_raw, multiple_raw)

        # 缓存校验后的结果
        self.config = validated.config
        self.apis = validated.apis
        self.flows = validated.flows

    def get_api(self, api_id: str) -> ApiItem:
        """
          获取具体接口需要的数据
        :param api_id: 接口库里的 api_id, 不能有首尾空格
        :return:
        """
        # 若不存在该 api
        if api_id not in self.apis:
            # 直接抛错提示修正引用
            raise YamlSchemaException(f"single.yaml.apis 不存在接口：{api_id}")
        # 返回 api
        return self.apis[api_id]

    def get_flow(self) -> FlowBundle:
        """
          获取 multiple.yaml 的校验后结构化对象（包含 common）
        """
        return self.flows

    def get_common(self) -> dict:
        """
          直接拿到 multiple.yaml.common，供执行层写入 Allure epic/feature/story 等
        """
        return self.flows.common


if __name__ == "__main__":
    data = YamlRepository("./Data/config.yaml")



