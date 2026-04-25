# AutoAPI 请求模型实现讲解 06

本文档对应 `plans/request_06_raw_subtypes.md`，讲的是为什么要把 `raw` 剩余子类型补齐，以及这批代码在执行链里怎么落下去。

## Code Role

这次主要只动一个核心模块：

1. `Engine/request_resolver.py`

另外补了两类配套内容：

- `examples/p0_minimal/Data/*` 最小示例
- `Tests/test_repository.py` 针对 `raw` 子类型的断言

职责边界很简单：

- `Composer` 仍只负责字段级覆盖
- `RequestResolver` 负责把 `raw.raw_type` 翻译成 `requests` 真正认识的低层参数

## Why This Design

关键点只有一个：

> `requests` 的 `json=` 和 `data=/files=` 不是同一个入口

所以 `raw` 必须在执行层分成两类：

- `raw_type=json` -> `kwargs["json"]`
- `raw_type=text/xml/html/javascript` -> `kwargs["data"]`

这样做的原因：

1. 符合 `requests` 的官方语义
2. 不把 JSON body 和其它原始文本 body 混在一起
3. 继续保持 `raw` 与 `form_data / form_urlencoded / binary` 的互斥规则

## Problem Solved

这次补齐后，`body_mode=raw` 不再只有 `json` 一条路。

现在正式支持：

- `raw(text)`
- `raw(xml)`
- `raw(html)`
- `raw(javascript)`

并且统一具备两条行为：

1. 自动补默认 `Content-Type`
2. 如果用户已经显式写了 `headers.Content-Type`，则不覆盖

## Data Flow

### raw(json)

```text
YAML request.raw(raw_type=json)
  -> RequestResolver
  -> kwargs["json"]
  -> requests/session.request(...)
```

### raw(text/xml/html/javascript)

```text
YAML request.raw(raw_type=text/xml/html/javascript)
  -> RequestResolver
  -> kwargs["data"]
  -> headers.setdefault("Content-Type", ...)
  -> requests/session.request(...)
```

这里特意用了 `setdefault(...)`，因为：

> 默认值应该只在用户没写时补进去  
> 用户显式写了头，就应该以用户值为准

## Defaults

默认 `Content-Type`：

- `text` -> `text/plain`
- `xml` -> `application/xml`
- `html` -> `text/html`
- `javascript` -> `application/javascript`

非字符串 `raw.content` 的处理：

- 当前统一走 `str(...)`

这样至少可以保证执行链稳定，不因为用户传了 `123`、`True` 这类值就直接炸掉。

## Tests As Learning Tools

这次最值得看的测试：

- `raw(text)` 默认头
- `raw(xml)` 默认头
- `raw(html)` 默认头
- `raw(javascript)` 默认头
- 显式 `Content-Type` 不被覆盖
- 非字符串 `raw.content` 被稳定转成字符串

这批测试的观察重点只有两个：

1. 最终写进的是 `kwargs["json"]` 还是 `kwargs["data"]`
2. `headers["Content-Type"]` 是默认补的，还是用户自己写的

## Trade-offs

这次有两个明确取舍：

1. `raw(text/xml/html/javascript)` 统一进 `kwargs["data"]`
   - 这是最贴近 `requests` 的实现
   - 也意味着它们不会再进入 `kwargs["json"]`

2. 非字符串内容统一 `str(...)`
   - 这是稳定优先的选择
   - 不是“最严格”的校验策略
   - 严格字段校验仍然留给后续阶段
