from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def minimal_data_dir() -> Path:
    # 提供最小示例数据目录，供 repository/composer/resolver 测试复用。
    return Path("examples/minimal/Data")


@pytest.fixture(scope="session")
def reading_house_data_dir() -> Path:
    # 提供 reading_house 示例数据目录，供真实接口配置和环境级鉴权测试复用。
    return Path("examples/reading_house/Data")
