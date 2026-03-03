# 示例：obj 是你实际拿到的配置（比如解析后的 yaml 节点）
obj = {  # 定义一个字典，模拟用户写的配置内容
    "url": "https://api.xxx.com",  # 允许字段：url
    "method": "get",              # 允许字段：method
    "timeout": 10,                # 允许字段：timeout
    "debug": True,                # 多余字段：debug（假设 schema 不允许）
}

# 示例：allowed 是 schema 允许出现的字段集合（白名单）
allowed = ["url", "method", "timeout", "debug", "ccc"]  # 允许字段列表（也可以是 set）

# 把 obj 的 key 转成集合（便于做集合运算）
obj_keys_set = set(obj.keys())  # obj.keys() -> dict_keys，再转成 set

# 把 allowed 转成集合（保证也能做集合运算）
allowed_set = set(allowed)  # list -> set

# 差集：找出“在 obj 里但不在 allowed 里”的字段
extra = obj_keys_set - allowed_set  # 得到多余字段集合

# 打印结果，看看多出来的字段有哪些
print(extra)  # 输出多余字段