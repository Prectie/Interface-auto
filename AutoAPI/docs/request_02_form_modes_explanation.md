# AutoAPI 请求模型实现讲解 02

本文档对应第二个请求模型计划：`form_urlencoded + form_data(field/file)`。

目标不是只记录“改了什么”，而是帮助你理解这批代码在执行链里的职责、为什么这样设计，以及以后扩 `binary / auth / cookies` 时应该沿用什么思路。

## Code Role

这次改动涉及的核心模块只有三个：

1. `Core/composer.py`
2. `Engine/request_resolver.py`
3. `Engine/results.py`

它们的职责边界分别是：

### `Composer`

负责 **继承和覆盖**。

它只回答一个问题：

> `ApiTemplate`、`ApiCase`、`ScenarioStep.override` 叠在一起以后，最终请求字段是什么？

它不负责：

- 变量渲染
- path 拼接
- multipart 构建
- 文件读取
- 发送请求

### `RequestResolver`

负责 **把最终请求字段转换成可发送的 requests 参数**。

它回答的问题是：

> 合成后的 `request`，最终怎么变成 `method + url + kwargs`？

这次它新增支持：

- `body_mode=form_urlencoded`
- `body_mode=form_data`
- `form_data.kind=field`
- `form_data.kind=file`

### `PreparedRequest`

负责 **承载“已经可以发出去的请求”**，同时给 history / 错误输出提供一个更可读的快照。

这次它没有改变发送逻辑，但新增了：

- multipart 请求的可读摘要序列化

也就是：

> 真正发送时保留底层 multipart tuple  
> 打印和记录时转换成更容易读懂的结构

## Why This Design

### 为什么 `Composer` 也要改

因为如果 `Composer` 不认识 `form_urlencoded / form_data`，那这些字段就不会进入正式覆盖规则。

结果会出现两种坏情况：

1. case 写了 `form_data`，但步骤 override 不生效
2. YAML 看起来像支持了 `form_data`，实际执行链却只覆盖旧字段

所以这次先在 [Core/composer.py](/mnt/d/githubrepository/interface-auto/autoapi/Core/composer.py:14) 扩了：

- `EMPTY_BY_FIELD`
- `REQUEST_FIELDS`

本质上是把 `form_urlencoded / form_data` 纳入“正式请求字段集合”。

### 为什么 `RequestResolver` 要统一走 `body_mode`

因为请求体模式本来就应该只有一个入口。

如果继续保留这种分散式判断：

- 这里看旧产品层的 `body_type`
- 那里直接拼 `requests files`
- 另一处再临时写 `requests data`

那后面一旦加 `binary`、`auth`、`cookies`，请求构建逻辑会越来越碎。

这次的收口方式是：

1. 先读 `body_mode`
2. 再进入对应分支
3. 每个分支只处理自己的请求体构建逻辑

这样后面扩展时，只需要继续补分支，不用把已有分支再打散。

## Problem Solved

这次实际解决了三个问题。

### 1. `form_urlencoded` 终于有正式入口

现在 [Engine/request_resolver.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/request_resolver.py:146) 里，`body_mode=form_urlencoded` 会稳定映射到：

```python
kwargs["data"] = ...
```

这件事的意义是：

- 产品层用 `body_mode=form_urlencoded`
- requests 层仍然是 `data`

上层模型和底层库没有再混在一起。

### 2. `form_data` 不再是模糊的“未来能力”

现在 `form_data` 真正变成了代码里的正式模型。

支持两类 item：

- `kind=field`
- `kind=file`

其中 `kind=file` 当前正式用户结构已经收敛为：

- `name`
- `path`

并且统一走一个入口：

- [Engine/request_resolver.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/request_resolver.py:168)

这里的关键工程点是：

> 不把文本字段和文件字段拆成两套上层模型  
> 而是在输入层统一表达，到执行层再翻译成 multipart

### 3. multipart 历史输出变得可读

如果直接把 requests 的 multipart tuple 写到 history 或错误输出里，结构会很难读，例如：

```python
("file", ("demo.txt", b"...", "text/plain"))
```

这对调试请求发送层还行，但对框架使用者并不友好。

所以这次在 [Engine/results.py](/mnt/d/githubrepository/interface-auto/autoapi/Engine/results.py:19) 做了第二层处理：

- 发送时：保留真实 tuple
- 输出时：转成摘要结构

例如：

```json
{
  "field": "file",
  "kind": "file",
  "filename": "upload_demo.txt",
  "size": 20,
  "content_type": "text/plain"
}
```

这样用户看历史或错误上下文时，能直接知道：

- 字段名
- 是文本字段还是文件字段
- 文件名
- 大小
- MIME 类型

## Data Flow

这次最值得理解的是 data flow。

### form_urlencoded

数据流：

```text
YAML request.form_urlencoded
  -> Composer 合成
  -> RequestResolver 读取 body_mode=form_urlencoded
  -> kwargs["data"]
  -> requests/session.request(...)
```

### form_data(field)

数据流：

```text
YAML request.form_data
  -> Composer 合成
  -> RequestResolver._build_multipart_files()
  -> [("bizType", (None, "task")), ...]
  -> requests kwargs["files"]
  -> requests/session.request(...)
```

这里特意让纯字段 multipart 也走 `requests kwargs["files"]`，不是因为它是文件，而是因为：

> 如果只用 `data`，requests 默认会发 `x-www-form-urlencoded`，而不是 multipart。

所以这是一个实现层 trade-off：

- 产品层：仍叫 `form_data`
- 发送层：统一转成 multipart parts

### form_data(file)

数据流：

```text
YAML request.form_data(kind=file, path=...)
  -> RequestResolver._build_file_part()
  -> 读取本地文件 bytes
  -> (本地文件名, content_bytes, 推导出的 content_type)
  -> requests kwargs["files"]
  -> requests/session.request(...)
```

这里我没有把文件句柄直接塞给 `requests`，而是先读成 bytes。

原因很实际：

- 这样不需要把文件句柄生命周期跨模块传递
- 不需要在 Transport 再做 close 处理
- 对当前 P0/P1 规模更稳

代价是：

- 大文件会占更多内存

但当前计划明确只做最小稳定实现，这个 trade-off 是合理的。

## Before vs After

### Before

- `Composer` 只认识旧字段
- `RequestResolver` 还没有完整统一到新的 `body_mode` 分支式构建
- `form_data` 只是文档定义，不是执行能力
- multipart 请求的输出结构不友好

### After

- `Composer` 已把 `form_urlencoded / form_data` 纳入正式覆盖规则
- `RequestResolver` 已按 `body_mode` 分发请求体构建
- `form_data(field/file)` 已成为正式执行能力
- `PreparedRequest` 会把 multipart 输出转成可读摘要

## Trade-offs

这次设计有三个明确成本。

### 1. `RequestResolver` 更重了一点

因为它现在不仅做 URL 构建，还要做 multipart part 翻译。

但这是合理的，因为：

- 这些逻辑本来就属于“请求构建”
- 没必要为 P0/P1 再拆出一个单独的 multipart builder 抽象

### 2. 文件上传当前只要求 `path`

这是主动收缩范围。

没有把这些内容暴露成用户字段：

- 自定义上传文件名
- 自定义 content type
- 其它文件来源类型

这样做的好处是第二计划能尽快稳定，第三计划再继续扩。

### 3. 文件先读成 bytes

这让资源管理简单了，但不是大文件最优方案。

这属于：

- 当前阶段优先稳定
- 后续如果真的出现大文件上传场景，再单独优化

### 4. 真实服务验证与 synthetic 示例分层

这次有一个实际环境 trade-off：

- `examples/reading_house`
  - 适合做真实服务验证
  - 因为它的 host 是可访问的现成服务
  - 但它当前只覆盖公开 GET 接口和 `form_urlencoded` 登录

- `examples/p0_minimal`
  - 适合做 synthetic 单测
  - 因为它可以承载 `form_data(file)` 这种当前真实服务里没有现成接口的能力验证

所以当前策略不是“只保留一套示例”，而是明确分工：

- **真实联调用 `reading_house`**
- **请求模型边界测试继续用 `p0_minimal`**

这样做的理由是：

1. 不把“真实服务可达性”绑死到请求模型设计上
2. 不为了迁就现有服务，就把 `form_data(file)` 能力先砍掉
3. 让 integration verification 和 unit test 各自服务于不同目标

这是一个很典型的工程分层：

- `reading_house` 更像 integration example
- `p0_minimal` 更像 protocol-focused fixture

## Tests As Learning Tools

这次我特意把测试写成“可学习的断点样例”，你可以直接从这些测试理解实现。

推荐先看：

- [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py:232)
  - `form_urlencoded`
- [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py:255)
  - `form_data(field)`
- [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py:281)
  - `form_data(file)`
- [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py:304)
  - `form_data` step override
- [Tests/test_repository.py](/mnt/d/githubrepository/interface-auto/autoapi/Tests/test_repository.py:346)
  - `form_data(field + file)`

如果你打断点，最值得看的变量是：

1. `executable.request`
2. `rendered`
3. `kwargs`
4. `prepared.to_dict()`

顺序是：

```text
YAML 原始配置
  -> 合成后的 request
  -> 渲染后的 request
  -> requests kwargs
  -> 给 history / 错误输出看的摘要
```

## Reusable Pattern

这次最值得复用的工程模式是：

1. **上层模型先统一**
   - 例如 `form_data` 统一表达 field/file
2. **执行层再翻译**
   - 例如翻译成 requests multipart tuple
3. **日志层单独摘要化**
   - 不把底层结构原样暴露给用户

以后做：

- `binary`
- `auth`
- `cookies`

也应该继续按这个模式走。

不要一开始就直接围绕底层 requests 参数设计 YAML，因为那样长期一定会把产品模型和实现模型缠在一起。
