# -*- coding: utf-8 -*-
# @Author  : 柚一
# @File    : deppdiff_test.py
# https://pypi.tuna.tsinghua.edu.cn/simple/
# 项目地址可能发生变化，测试数据如果太多可能随时还原。 碰到地址打不开，报错等等情况，联系班主任老师及时反馈
from deepdiff import DeepDiff

# 对整个响应结果断言呢？是否符合预期问题；
# 准备：预期结果的返回数据   实际结果的返回数据

actual_response = {
    "code": 200,
    "message": "SUCCESS",  # 实际是大写
    "data": {
        "user": {
            "id": 1001,           # 动态生成，每次不同
            "name": "alice",      # 实际是小写
            "email": "ALICE@EXAMPLE.COM",  # 实际是大写
            "age": 25,
            "hobbies": ["reading", "swimming", "coding"],  # 顺序可能变化
            "profile": {
                "level": "VIP",
                "score": 95.5,
                "tags": ["active", "new_user"]
            },
            "create_time": "2023-10-01 10:30:00"  # 动态时间
        },
        "system_info": {
            "version": "1.2.3",
            "timestamp": 1696134600  # 动态时间戳
        }
    }
}

# 预期结果
expected_response = {
    "code": 200,
    "message": "success",  # 预期是小写  实际可以大写小写都可以
    "data": {
        "user": {
            "id": None,           # 动态字段，不比较
            "name": "Alice",      # 预期是首字母大写   实际可以大写小写都可以
            "email": "alice@example.com",  # 预期是小写
            "age": 25,
            "hobbies": ["coding", "reading", "swimming"],  # 可以顺序不同
            "profile": {
                "level": "vip",   # 预期是小写
                "score": 95.5,
                "tags": ["new_user", "active"]  # 可以顺序不同
            },
            "create_time": None   # 动态字段，不比较
        },
        "system_info": {
            "version": "1.2.3",
            "timestamp": None     # 动态字段，不比较
        }
    }
}


def test_deepdiff():
    # 过滤哪些字段  不要断言  不知道中间多了个什么内容  一定要对应字段信息
    exclude_paths = [
        "root['data']['user']['id']",  # 排除用户ID
        "root['data']['user']['create_time']",  # 排除创建时间
        "root['data']['system_info']['timestamp']"  # 排除时间戳
    ]

    diff=DeepDiff(
        actual_response,
        expected_response,
        exclude_paths=exclude_paths,#过滤字段
        ignore_order=True,#忽略顺序
        ignore_string_case=True#忽略大小写
    )

    # #diff.pretty()详细报错信息
    assert not diff, f"实际结果与预期结果不一致{diff.pretty()}"#diff没有任何内容  就是正确的
    print("测试通过")

if __name__ == '__main__':
    test_deepdiff()

# 深度断言  哪里定义了内容