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
        self._validator = YamlSchemaValidator()  # 初始化严格校验器（repository 不实现校验细节）  #
        self.config: Optional[ConfigBundle] = None
        self.apis: Optional[Dict[str, ApiItem]] = None
        self.flows: Optional[FlowBundle] = None

    def load(self):
        """
          读取并严格校验 yaml数据, 并加载到 repository 内存对象中
        """
        config_raw = load_yaml_file(self.root_dir / "config.yaml")
        single_raw = load_yaml_file(self.root_dir / "single.yaml")
        multiple_raw = load_yaml_file(self.root_dir / "multiple.yaml")

        validated = self._validator.validate_all(config_raw, single_raw, multiple_raw)  # 调用独立 validator 完成严格校验  #

        self.config = validated.config  # 缓存 config 校验结果  #
        self.apis = validated.apis  # 缓存 apis 校验结果  #
        self.flows = validated.flows  # 缓存 flow 校验结果（包含 common）  #

    def get_api(self, api_id: str) -> ApiItem:
        """
          获取具体接口需要的数据
        :param api_id:
        :return:
        """
        key = str(api_id).strip()  # 规范化 api_id，避免首尾空格导致查不到  #
        if key not in self.apis:  # 若不存在该 api  #
            raise YamlSchemaException(f"single.yaml.apis 不存在接口：{key}")  # 直接抛错提示修正引用  #
        return self.apis[key]  # 返回结构化 api 定义  #

    def get_flow(self) -> FlowBundle:  # 执行层获取业务流定义  #
        """
        目的/作用：
            获取 multiple.yaml 的校验后结构化对象（包含 common）。  #
        参数说明：
            1) 无。  #
        返回值说明：
            1) flowbundle：结构化 flow 定义。  #
        """  # 方法说明结束  #
        return self.flows  # 返回结构化 flow 定义  #

    def get_common(self) -> dict:  # 执行层获取 common（用于 Allure）  #
        """
        目的/作用：
            直接拿到 multiple.yaml.common，供执行层写入 Allure epic/feature/story 等。  #
        参数说明：
            1) 无。  #
        返回值说明：
            1) dict：common 字典。  #
        """  # 方法说明结束  #
        return self.flows.common  # 返回 common 字典  #


if __name__ == "__main__":
    data = YamlRepository("./Data/config.yaml")



