- 合并规则(如 override 与 接口库里的模板进行合并):
  - 非 dict 直接覆盖, 如 list 的情况:
    ```yaml
        # single.yaml
        extract:
          - source: "response_json"
            jsonpath: "$.obj"
            as: "taskId"
    ```
    
    ```yaml
        # multiple.yaml
        extract:
          - source: "response_text"
            jsonpath: "$.obj"
            as: "taskId_user_id"
            like: "test"
    ```
  
    合并后, 就替换为 multiple.yaml 的数据:
    ```yaml
        # multiple.yaml
        extract:
          - source: "response_text"
            jsonpath: "$.obj"
            as: "taskId_user_id"
            like: "test"
    ```
  - dict 情况, 则为合并, 如
    ```yaml
        # single.yaml
        extract:
          source: "response_json"
          jsonpath: "$.obj"
          as: "taskId"
    ```
    
    ```yaml
        # multiple.yaml
        extract:
          source: "response_text"
          jsonpath: "$.obj"
          As: "taskId_user_id"
          like: "test"
    ```
  
    合并后, 相同 key 进行替换, 不同 key 进行合并(大小写敏感):
    ```yaml
        # multiple.yaml
        extract:
          source: "response_text"
          jsonpath: "$.obj"
          as: "taskId"
          As: "taskId_user_id"
          like: "test"
    ```

收集测试条数的优先级, 且是根据 list 条数进行收集:
1. 先看 data
2. 再看 params
3. 最后看 files

例如: 

第一种情况:

params 是两条 list 数据, data 是一个 dict
那么收集逻辑会这样判断:
- `data` 不是 list, 不用它决定 case 数
- `params` 是 list, 长度为 2, 收集 2 条 case

最终表现:
- 生成 2 条用例, params 分别取第 1 条 和 第 2 条
- `data` 因为是 dict, 因此两条用例都复用同一份 body

第二种情况:

params 是两条 list 数据, data 也是一个 list, 但只有一条

那么收集逻辑就会这样:
- 按 `data` 条数收集(见上述的优先级)

最终表现:
- 只生成 1 条 case, 并且只会用到 `params[0]`
- `params[1]` 会被忽略

注意: 业务流执行不遵循以上规则, 现认为业务流一般仅会使用一条数据, 因此
业务流永远默认取第 `[0]` 条数据, 多条数据也会取第 `[0]` 条