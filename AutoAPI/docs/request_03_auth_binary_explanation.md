# AutoAPI 请求模型实现讲解 03

本文档对应第三个请求模型计划：`cookies + auth + binary`。

这批能力和前两个计划不一样，难点不在“多了几个字段”，而在于：

- `auth` 是**语义化输入**
- `binary` 是**不同于 form-data 的另一条请求体路径**
- 失败输出和 history 会天然更容易碰到敏感信息

所以这次讲解重点放在职责边界、翻译时机和最小输出控制。

## Code Role

这次主要改了三个模块：

1. `Core/composer.py`
2. `Engine/request_resolver.py`
3. `Engine/results.py`

### `Composer`

职责还是不变：

> 只负责把模板、用例、步骤 override 合成为最终 `request`

这次它新认识的字段是：

- `cookies`
- `auth`
- `binary`

也就是说，这些字段从现在开始已经进入正式覆盖规则，不再是“文档里写了，但执行器不一定认”的状态。

### `RequestResolver`

这次它承担了两个关键职责：

1. 把 `auth` 翻译成 `headers / requests params / cookies`
2. 把 `binary` 翻译成 `requests.data`

这里最重要的设计点是：

> `auth` 不应该流到 `Transport` 才处理  
> 它必须在请求构建阶段就被翻译掉

因为下游真正关心的不是“Bearer 还是 API Key”，下游关心的是：

- header 最后长什么样
- query 最后长什么样
- cookies 最后长什么样

### `PreparedRequest`

这次它新增了两类序列化能力：

1. 二进制请求体摘要
2. 最小敏感字段隐藏

注意，这里不是在做完整脱敏系统。  
完整脱敏仍然是 P2 事情。

当前做的是更小的边界控制：

> 不让请求快照把 `Authorization / token / password` 这种值原样直接打出来

## Why This Design

### 为什么 `auth` 不原样放进 `requests`

因为我们的 `auth` 结构是产品层语义，不是 `requests` 的原生协议。

例如：

```yaml
auth:
  type: bearer
  token: "${auth_token}"
```

这对框架用户来说很清楚，但 `requests` 根本不认这套对象。

所以它必须先在 [Engine/request_resolver.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/request_resolver.py) 里翻译成：

```python
headers["Authorization"] = "Bearer xxx"
```

同理：

- `basic` 要翻译成 `Authorization: Basic ...`
- `api_key in=header` 要翻译到 header
- `api_key in=query` 要翻译到 `requests params`
- `api_key in=cookie` 要翻译到 cookies

这一步做在 `RequestResolver`，意味着：

- `Executor` 不需要知道认证类型
- `Transport` 不需要知道认证类型
- `HistoryWriter` 也不需要知道认证类型

这就是比较干净的 dependency direction。

### 为什么 `binary` 和 `form_data(file)` 要明确分开

这两者看起来都和“文件”有关，但其实是两种完全不同的协议表达。

#### `form_data(file)`

是 multipart：

```text
field1=value1
file=<multipart part>
```

#### `binary`

是整个请求体本身就是文件内容：

```text
PUT /upload/xxx
<binary bytes>
```

如果把这两种能力混成同一路径，后面一定会出现这种问题：

- 明明用户想发整个文件流，结果被拼成 multipart
- 明明用户想发 multipart，结果被当成裸 bytes

所以这次明确分层：

- `form_data(file)` 走 multipart
- `binary` 走 `data=bytes`

## Problem Solved

这次主要解决了四个问题。

### 1. Cookie 不再依赖手写 `headers.Cookie`

现在 `cookies` 已经成为正式请求字段。

它的意义不是“requests 早就支持 cookies”，而是：

> 之前框架模型里没有把 cookies 作为一等输入  
> 现在它终于进入正式请求模型了

### 2. Auth 终于有统一入口

之前如果不同接口各自手写：

- `headers.Authorization`
- `headers.X-Token`
- `requests params.token`

框架层其实不知道这些是不是“认证”，也没法统一讲解和扩展。

现在有了正式入口：

```yaml
auth:
  type: ...
```

这样以后你做：

- 环境级鉴权模板
- 平台化认证表单
- 调试界面的 auth panel

才有清晰基础。

### 3. Binary 请求体有了独立通道

现在 [Engine/request_resolver.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/request_resolver.py) 里，`body_mode=binary` 会：

1. 读取本地文件
2. 放进 `kwargs["data"]`
3. 自动补 `Content-Type`（如果没有显式给）

这意味着它已经成为正式能力，而不是后续再靠“特殊 if 分支”补进去。

### 4. 请求快照不再明显暴露认证值

在 [Engine/results.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/results.py) 里，这次做了一个很小但重要的边界控制：

- `headers / requests params / cookies` 在序列化时，如果 key 明显是敏感字段，就替换成 `***`

例如：

- `Authorization`
- `X-Token`
- `auth_token`
- `password`

这不是完整脱敏系统，但足够避免“调试输出里直接把 token 打满屏”。

## Data Flow

### cookies

数据流：

```text
YAML request.cookies
  -> Composer 合成
  -> RequestResolver 写入 kwargs["cookies"]
  -> requests/session.request(...)
```

### bearer auth

数据流：

```text
YAML request.auth(type=bearer)
  -> Composer 合成
  -> RequestResolver._apply_auth()
  -> kwargs["headers"]["Authorization"] = "Bearer ..."
  -> requests/session.request(...)
```

### basic auth

数据流：

```text
YAML request.auth(type=basic)
  -> username:password
  -> base64 编码
  -> Authorization: Basic ...
```

### api_key auth

数据流：

```text
YAML request.auth(type=api_key, in=header/query/cookie)
  -> RequestResolver._apply_auth()
  -> 写入 headers / requests params / cookies
```

这里有一个明确规则：

> 如果 `api_key in=cookie` 和显式 `cookies` 写了同一个 key  
> 当前实现中 **auth 覆盖 cookies**

原因很简单：

- `cookies` 是先进入 kwargs 的
- `auth` 是后翻译进去的

这个规则不一定是唯一正确答案，但它是当前最稳定、最容易解释的答案。

### binary

数据流：

```text
YAML request.binary(source=path)
  -> RequestResolver._apply_binary()
  -> 读取 bytes
  -> kwargs["data"] = bytes
  -> 设置 Content-Type
  -> requests/session.request(...)
```

## Before vs After

### Before

- `cookies` 不是正式请求输入
- `auth` 没有统一入口
- `binary` 没有正式执行通道
- 请求快照容易直接暴露认证值

### After

- `cookies` 进入正式请求模型
- `auth` 有统一翻译入口
- `binary` 独立于 multipart
- 请求快照做了最小敏感值隐藏

## Trade-offs

### 1. `RequestResolver` 的职责又重了一点

因为它现在除了 URL、body，还要负责 auth 翻译。

但这是合理的，因为：

- 这些都属于“请求构建”
- 没必要现在为 auth 再拆一个 builder 抽象

### 2. 最小隐藏不是完整脱敏

当前只是：

- 对明显敏感 key 做 `***`

没有做：

- 深层递归脱敏
- 自定义敏感规则引擎
- Allure / JSONL / response 的统一脱敏体系

这是有意收缩范围。

### 3. Binary 仍只支持 `source=path`

没有做：

- `source=bytes`
- `source=base64`
- `source=url`
- `source=generated`

这和第二计划的文件上传取舍一致，先稳定再扩。

## Tests As Learning Tools

这次推荐你重点看这些测试：

- `cookies`：  
  [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py)

- `auth none / bearer / basic / api_key`：  
  [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py)

- `binary`：  
  [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py)

看测试时最值得盯住的变量是：

1. `executable.request`
2. `kwargs["headers"]`
3. `requests kwargs["params"]`
4. `kwargs["cookies"]`
5. `kwargs["data"]`
6. `prepared.to_dict()`

你会看到一个很稳定的模式：

```text
语义化 request
  -> RequestResolver 翻译
  -> requests kwargs
  -> 可读快照
```

## Reusable Pattern

这次可以沉淀出一个很重要的工程模式：

> 产品层允许语义化输入  
> 执行层只吃协议化结果  
> 输出层再做可读化处理

以后做：

- 环境级 auth template
- 更复杂的签名认证
- 请求调试面板

都应该继续沿这个模式走。

不要把“用户填写的语义化模型”和“requests 真正要吃的参数结构”混在一个层里。
