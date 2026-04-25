# RequestResolver 代码思维笔记

对应文件：

- `Engine/request_resolver.py`

## 1. RequestResolver 的核心角色

`RequestResolver` 负责把 AutoAPI 的请求模型翻译成 `requests` 可以发送的请求对象。

它的输出是：

```text
PreparedRequest
```

包含：

- method
- url
- kwargs

它不发送请求。发送请求是 `Transport` 的职责。

## 2. 为什么需要 RequestResolver

AutoAPI 的 YAML 是产品模型，不是 `requests` 参数模型。

例如用户写：

```yaml
request:
  method: post
  path: /model/{id}
  path_params:
    id: "${modelId}"
  query:
    debug: true
  body_mode: raw
  raw:
    raw_type: json
    content:
      name: demo
```

但是 `requests` 需要的是：

```python
method = "post"
url = "http://host/model/123"
kwargs = {
    "params": {"debug": True},
    "json": {"name": "demo"},
}
```

这个翻译过程就属于 RequestResolver。

## 3. resolve_executable 主流程

核心顺序：

```text
合并 request_defaults 和 executable.request
-> render_any 变量渲染
-> path_params 替换 path
-> host_rules 解析 base_url
-> 拼出 full_url
-> 处理 headers / timeout / verify 等普通 requests 参数
-> query -> params
-> cookies -> cookies
-> auth -> headers / params / cookies
-> body_mode -> json / data / files
-> PreparedRequest
```

这个顺序很关键。

尤其是：

```text
变量渲染必须早于 host_rules 和 body 构造。
```

否则 path 或 auth token 中的 `${xxx}` 还没替换，就会进入后续逻辑。

## 4. host 解析思路

AutoAPI 当前不允许在 `ApiTemplate / ApiCase / ScenarioStep` 中写 `host` 或 `host_key`。

host 只能来自环境：

```yaml
envs:
  test:
    hosts:
      reading_house: https://...
    host_rules:
      - host: reading_house
        priority: 10
        path_prefixes:
          - /api
```

RequestResolver 会把这些信息交给 `HostResolver`：

```text
api_id
module
path
```

由 `HostResolver` 返回 base_url。

这样 host 管理集中在环境层，接口模板不绑定具体环境。

## 5. request_defaults 的定位

`request_defaults` 是全局默认请求参数。

例如：

```yaml
request_defaults:
  timeout: [3.05, 30]
  verify: false
  headers:
    User-Agent: AutoAPI
```

RequestResolver 先复制默认值：

```text
merged = dict(request_defaults)
```

再用 executable.request 覆盖：

```text
merged.update(executable.request)
```

注意这里是浅层覆盖，符合当前 AutoAPI “字段级整体覆盖”的产品规则。

## 6. query / cookies / auth 的处理

### query

YAML 中：

```yaml
query:
  page: 1
  size: 20
```

转换为：

```python
kwargs["params"] = {"page": 1, "size": 20}
```

### cookies

YAML 中：

```yaml
cookies:
  sessionid: "${sessionid}"
```

转换为：

```python
kwargs["cookies"] = {"sessionid": "..."}
```

### auth

`auth` 是语义化字段，不直接透传给 `requests`。

支持：

```text
none
bearer
basic
api_key
```

示例：

```yaml
auth:
  type: bearer
  token: "${token}"
```

转换为：

```python
headers["Authorization"] = "Bearer xxx"
```

`api_key` 可以放在：

- header
- query
- cookie

所以 `_apply_auth` 会按 `auth.in` 写入不同位置。

## 7. body_mode 的设计

AutoAPI 用 `body_mode` 明确请求体类型：

```text
none
raw
form_urlencoded
form_data
binary
```

这样比旧的 `body_type` 更接近 Postman / MeterSphere。

### none

不设置请求体。

### form_urlencoded

YAML：

```yaml
body_mode: form_urlencoded
form_urlencoded:
  username: test
  password: 123456
```

转换为：

```python
kwargs["data"] = {...}
```

### form_data

YAML：

```yaml
body_mode: form_data
form_data:
  - kind: field
    name: bizType
    value: task
  - kind: file
    name: file
    path: ./demo.txt
```

转换为：

```python
kwargs["files"] = [...]
```

这里有一个重要点：

`form_data` 本身就是 multipart item 列表，不能再按数据驱动 list 去取第 0 项。

所以代码里没有对 `form_data` 调用 `_pick_data_item`，而是直接传给 `_build_multipart_files`。

这是之前出现过 bug 的地方。

### raw

YAML：

```yaml
body_mode: raw
raw:
  raw_type: json
  content:
    name: demo
```

如果 `raw_type=json`：

```python
kwargs["json"] = content
```

如果是：

```text
text
xml
html
javascript
```

则：

```python
kwargs["data"] = content
headers.setdefault("Content-Type", 默认类型)
```

这是因为 `requests` 的 `json` 参数只适合 JSON body。如果同时传 `data/files`，`json` 会被忽略。

所以不同 body_mode 必须互斥。

### binary

YAML：

```yaml
body_mode: binary
binary:
  source: path
  path: ./data/demo.bin
```

当前只支持：

```text
source=path
```

执行时读取文件 bytes：

```python
kwargs["data"] = file_bytes
```

## 8. _pick_data_item 的作用

有些字段未来或当前可能支持数据列表：

```yaml
query:
  - page: 1
  - page: 2
```

`_pick_data_item` 的作用是：

```text
dict -> 直接返回
list -> 根据 data_index 取一项
None -> 返回 None
其它 -> 原样返回
```

但不是所有 list 都代表数据驱动。

`form_data` 是一个 multipart item 列表，不是多组数据，所以不能用 `_pick_data_item`。

这就是 RequestResolver 里需要理解业务语义的地方。

## 9. 错误处理

`resolve_executable` 会捕获请求构建中的普通异常，并包装成：

```text
RequestBuildException
```

异常上下文里包含：

- api_id
- step_id
- executable.request
- request_defaults
- env_hosts
- hint

这样 CLI 输出错误时，用户能知道是请求构建失败，而不是看到一个普通 Python traceback。

变量解析异常 `VarResolveException` 会原样抛出，因为它已经有明确上下文。

## 10. 设计收益

RequestResolver 让请求模型和 requests 细节解耦。

收益：

- YAML 更接近用户心智。
- `requests` 的 json/data/files 互斥规则集中处理。
- host 解析集中处理。
- auth 翻译集中处理。
- 新增 body_mode 时不用改 Executor。

## 11. 当前 trade-offs

当前成本：

- RequestResolver 需要知道较多 HTTP 细节。
- `body_mode` 分支会随着请求类型增加而变长。
- 文件读取目前直接发生在 Resolver 中，后续如果需要更复杂文件管理，可能要再拆。

但目前这个抽象仍然是必要的。因为相比让 Executor 或 CLI 直接处理 HTTP 细节，集中在 Resolver 更可控。

## 12. 调试建议

调试请求构造时，断点建议：

1. `resolve_executable`
2. `render_any`
3. `_render_path_with_params`
4. `host_resolver.resolve_base_url`
5. `_apply_auth`
6. `_apply_body_by_mode`
7. `_build_multipart_files`

重点观察：

- `merged`
- `rendered`
- `path`
- `base_url`
- `full_url`
- `kwargs`
- 最终 `PreparedRequest.to_dict()`

如果请求发出去不对，通常先看：

```text
PreparedRequest.to_dict()
```

它能告诉你最终 method、url、headers、params、body 到底是什么。

## 13. 后续扩展时怎么判断是否该改 RequestResolver

应该改 RequestResolver 的需求：

- 新增 body_mode。
- 新增 raw_type。
- 新增 auth.type。
- 修改 cookies / query / path_params 行为。
- 修改 host_rules 到 URL 的映射。
- 支持更多 binary source。

不应该改 RequestResolver 的需求：

- 新增断言 op。
- 新增场景执行顺序。
- 新增 history 字段。
- 新增 Allure 展示方式。

这些分别属于 `AssertionEngine`、`Executor`、`HistoryWriter`、`AllureRuntimeReporter`。
