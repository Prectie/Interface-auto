# -*- coding: utf-8 -*-

"""
  pytest_autoapi: 把 AutoAPI YAML 资产桥接到 pytest 内核的插件包。

  重要约定：
  - LAST_RUN_RESULT / LAST_RUN_ARTIFACTS / LAST_SENSITIVE_KEYS 是 plugin 模块级
    "run 结束后的产物句柄"，外部读取必须用模块路径访问（``from pytest_autoapi
    import plugin as autoapi_plugin; autoapi_plugin.LAST_RUN_RESULT``），
    不能 ``from pytest_autoapi import LAST_RUN_RESULT``，否则会绑死到 None。
  - plugin 仅在用户传入 ``--autoapi-data`` 时启用 collection，避免污染框架内
    其它单测。

  ``-p pytest_autoapi`` 加载约定：
  - pytest 用 ``-p pytest_autoapi`` 注册插件时, 读取本模块里的 hook 函数。
    必须把 plugin.py 里的 hook 函数全部 re-export 到顶层, 否则 pytest 无法识别
    ``pytest_addoption / pytest_collect_file / pytest_sessionfinish`` 等 hook。
"""

from pytest_autoapi import plugin as plugin  # noqa: F401  让 ``-p pytest_autoapi`` 能正确加载
from pytest_autoapi.plugin import (  # noqa: F401  re-export hook 给 pytest pluginmanager 识别
    pytest_addoption,
    pytest_collect_file,
    pytest_collection_modifyitems,
    pytest_configure,
    pytest_sessionfinish,
    pytest_sessionstart,
)

__all__ = [
    "plugin",
    "pytest_addoption",
    "pytest_collect_file",
    "pytest_collection_modifyitems",
    "pytest_configure",
    "pytest_sessionfinish",
    "pytest_sessionstart",
]
