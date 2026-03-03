class ExtractError(Exception):
    """
      提取失败异常:
        当 jsonpath 无匹配、source 不支持、响应对象不符合预期等情况发生时抛出
    """
    pass
