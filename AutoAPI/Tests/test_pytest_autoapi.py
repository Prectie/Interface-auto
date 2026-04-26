# -*- coding: utf-8 -*-

"""
  pytest_autoapi 插件的最小验收测试:
    - collection 能从 examples/reading_house/Data 产出 case / scenario / plan items;
    - --autoapi-target 能正确过滤 items;
    - --autoapi-data 缺省时插件不启用, 不会污染框架内单测。

  本套测试只做 collection 阶段验证 (--collect-only), 不真正驱动 runtest,
  避免在 CI / 本地环境上发起真实 HTTP 请求。
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

EXAMPLES_DATA = (Path(__file__).resolve().parent.parent / "examples" / "reading_house" / "Data").resolve()
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_pytester(pytester: pytest.Pytester, *extra_args: str) -> pytest.RunResult:
    # pytester 默认 cwd 在临时目录, 必须:
    #   1. 把 PROJECT_ROOT 注入 sys.path 才能 import pytest_autoapi;
    #   2. 显式把 EXAMPLES_DATA 传成 collect path (最后一个位置参数), 否则 pytest
    #      会从 pytester 的 tmpdir 开始扫描, 找不到 cases.yaml / Scenarios / plans.yaml。
    pytester.syspathinsert(PROJECT_ROOT)
    args = (
        "-p",
        "pytest_autoapi",
        "--autoapi-data",
        str(EXAMPLES_DATA),
        "--collect-only",
        "-q",
    )
    return pytester.runpytest_inprocess(*args, *extra_args, str(EXAMPLES_DATA))


def test_collection_without_target_yields_all_items(pytester: pytest.Pytester):
    # 不传 --autoapi-target 时, plugin 应当 yield 所有 case + scenario + plan items。
    # nodeid 形如 ``examples/.../cases.yaml::case_xxx``, 直接断言 ID 字符串。
    result = _run_pytester(pytester)

    output = "\n".join(result.outlines)
    assert "case_book_click_rank_success" in output
    assert "scn_reading_house_public_smoke" in output
    assert "plan_reading_house_public_smoke" in output
    assert "12 tests collected" in output


def test_collection_modifyitems_filters_by_case_target(pytester: pytest.Pytester):
    # --autoapi-target=case:xxx 应只剩对应 1 个 case item, 其余 items 被 deselect。
    result = _run_pytester(
        pytester,
        "--autoapi-target",
        "case:case_user_info_success",
    )

    output = "\n".join(result.outlines)
    assert "case_user_info_success" in output
    assert "case_book_click_rank_success" not in output
    assert "scn_reading_house_public_smoke" not in output
    assert "plan_reading_house_public_smoke" not in output
    assert "1 test collected" in output or "1/12 tests collected" in output


def test_collection_modifyitems_filters_by_scenario_target(pytester: pytest.Pytester):
    # --autoapi-target=scenario:xxx 应只剩 1 个 scenario item。
    result = _run_pytester(
        pytester,
        "--autoapi-target",
        "scenario:scn_reading_house_public_smoke",
    )

    output = "\n".join(result.outlines)
    assert "scn_reading_house_public_smoke" in output
    assert "scn_reading_house_auth_flow" not in output
    assert "case_book_click_rank_success" not in output
    assert "plan_reading_house_public_smoke" not in output


def test_plugin_is_inactive_without_autoapi_data(pytester: pytest.Pytester):
    # 未传 --autoapi-data 时, plugin 不应启用 collection, 不会触发 YamlRepository.load,
    # 也不会污染框架内的其它单测。这里只跑一个空目录, 期望 0 collected。
    pytester.syspathinsert(PROJECT_ROOT)
    result = pytester.runpytest_inprocess(
        "-p",
        "pytest_autoapi",
        "--collect-only",
        "-q",
    )
    output = "\n".join(result.outlines)
    assert "case_book_click_rank_success" not in output
    assert "scn_reading_house_public_smoke" not in output
    assert "plan_reading_house_public_smoke" not in output
