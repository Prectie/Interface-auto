from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def p0_minimal_data_dir() -> Path:
    # 提供 P0 最小示例数据目录，供 repository/composer/resolver 测试复用。
    return Path("examples/p0_minimal/Data")
