# AutoAPI 企业常用断言/提取 Source 扩展计划

## 1. Purpose / Big Picture

完成后，AutoAPI 的断言和提取能力更接近企业接口自动化常用平台：可以围绕状态码、响应头、响应体、响应文本、上下文变量和响应时间做断言；提取也可以从响应 JSON、响应头、响应文本和上下文中读取数据。

本轮只扩展 source 和 op，不做自定义脚本断言。

## 2. Scope

In scope:

- 扩展 assertion source：
  - `response_status`
  - `response_headers`
  - `response_json`
  - `response_text`
  - `context`
  - `response_time_ms`
- 扩展 extract source：
  - `response_json`
  - `response_headers`
  - `response_text`
  - `context`
- 扩展 assertion op：
  - `==`
  - `!=`
  - `>`
  - `>=`
  - `<`
  - `<=`
  - `contains`
  - `not_contains`
  - `starts_with`
  - `ends_with`
  - `empty`
  - `not_empty`
  - `regex`
  - `length_gt`
  - `length_gte`
  - `length_lt`
  - `length_lte`
  - `length_eq`
- 让标量 source 可以使用 `jsonpath: "$"` 读取自身，例如状态码和响应时间。
- 保留已有 op 兼容。

Out of scope:

- 不实现自定义脚本断言。
- 不实现 SQL/script action。
- 不做完整字段 schema 校验。
- 不做复杂 JSON Schema assertion。

## 3. Progress

- [x] T01 阅读当前 AssertionEngine / Extractor / JsonPathTool。
- [x] T02 扩展 JsonPathTool source 和标量读取能力。
- [x] T03 扩展 AssertionEngine op。
- [x] T04 补充 tests 覆盖企业常用断言和提取。
- [x] T05 更新示例或文档。
- [x] T06 运行验证并补充 retrospective。

## 4. Surprises & Discoveries

- `JsonPathTool` 已经支持 `response_status / response_headers / response_text / response_json / context`，但标量 source 还不能通过 jsonpath 自然读取。
- `response_time_ms` 尚未作为 source 暴露。
- `Extractor` 调用 `read_source` 时未传入上下文，导致 `source=context` 只能在断言中用，提取链路需要同步补上。

## 5. Decision Log

- 标量 source 使用 `jsonpath: "$"` 表示读取自身。
- 新 op 使用可读名称，例如 `not_contains / starts_with / length_gt`。
- 保留旧 op，例如 `== / != / contains / regex / exists`。
- 自定义脚本断言暂不进入本轮。

## 6. Context and Orientation

相关文件：

- `Engine/jsonpath_tool.py`
- `Engine/assertion_engine.py`
- `Engine/extractor.py`
- `Tests/test_repository.py`
- `docs/product_requirements.md`
- `docs/current_state.md`

## 7. Plan of Work

1. T02 在 `JsonPathTool.read_source` 中补 `response_time_ms`。
2. T02 在 `extract_jsonpath` 中支持 `expr="$"` 直接返回标量、字符串、数字、dict、list 自身。
3. T03 在 `AssertionEngine._eval_op` 中补齐企业常用 op。
4. T04 写单测覆盖：
   - status code 断言。
   - header 断言。
   - response_text 断言。
   - response_time_ms 断言。
   - length 系列断言。
   - response_headers / response_text / context 提取。
5. T05 更新 PRD/current_state。
6. T06 等用户在 Windows `.venv` 中运行验证。

## 8. Concrete Steps

工作目录：

```bash
/mnt/d/githubrepository/interface-auto/autoapi
```

预计修改文件：

- `Engine/jsonpath_tool.py`
- `Engine/assertion_engine.py`
- `Tests/test_repository.py`
- `docs/product_requirements.md`
- `docs/current_state.md`
- `plans/18_enterprise_assert_extract_sources.md`

预计命令：

```bash
python run.py validate --data examples/p0_minimal/Data
python run.py validate --data examples/reading_house/Data
python -m pytest -q
```

如果 WSL 中 `python` 不可用，由用户在 Windows `.venv` 中运行并回传结果。

## 9. Validation and Acceptance

必须验证：

- `response_status` 可以断言状态码。
- `response_headers` 可以断言响应头。
- `response_text` 可以断言响应文本。
- `response_time_ms` 可以断言响应耗时。
- `not_contains / starts_with / ends_with / empty / not_empty / length_*` 可用。
- `Extractor` 可从 headers/text/context 提取。

## 10. Idempotence and Recovery

- 本轮只扩展 source/op，不改执行编排。
- 如果新增 op 命名有争议，优先保留旧 op 兼容，再追加别名。
- 如果真实接口返回耗时不可控，单测使用 fake response 固定 elapsed。

## 11. Outcomes & Retrospective

- 已完成实现：
  - `JsonPathTool` 支持 `response_time_ms`。
  - `jsonpath: "$"` 可直接读取标量、字符串、dict、list 自身。
  - `Extractor` 支持从 `context` 读取。
  - `AssertionEngine` 支持 `not_contains / starts_with / ends_with / empty / not_empty / length_*`。
  - tests 覆盖状态码、响应头、响应文本、响应耗时、长度断言和 headers/text/context 提取。
  - PRD/current_state 已更新。
- 已运行：
  - `git diff --check -- Engine/jsonpath_tool.py Engine/assertion_engine.py Engine/extractor.py Tests/test_repository.py docs/product_requirements.md docs/current_state.md plans/18_enterprise_assert_extract_sources.md`
- 用户已在 Windows `.venv` 中完成验证并确认通过：
  - `python run.py validate --data examples/p0_minimal/Data`
  - `python run.py validate --data examples/reading_house/Data`
  - `python -m pytest -q`
