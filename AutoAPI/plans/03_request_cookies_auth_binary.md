# AutoAPI 请求模型实现计划 03

## 1. Purpose / Big Picture

完成后，AutoAPI 的执行链可以补齐第三批请求能力：

- `cookies`
- `auth`
- `binary`

用户可观察到的结果：

- Cookie 不再需要手写到 `headers.Cookie`。
- Bearer / Basic / API Key 认证拥有统一请求模型入口。
- 纯文件流上传可通过 `body_mode=binary` 进入执行链。

这是请求模型从“可用”走向“完整”的最后一段基础能力。

## 2. Scope

### In scope

- `cookies` 请求构建
- `auth.type=none`
- `auth.type=bearer`
- `auth.type=basic`
- `auth.type=api_key`
  - `in=header`
  - `in=query`
  - `in=cookie`
- `body_mode=binary`
- 对应 override、history、失败输出、最小测试和示例

### Out of scope

- 更复杂的认证模板编排
- 环境级鉴权模板执行器
- OAuth、Digest、签名算法
- 动态刷新 token
- 高级文件流生成策略
- 敏感字段脱敏正式实现

## 3. Progress

- [x] 阅读当前请求构建和失败输出中与 header/token 相关的逻辑
- [x] 实现 `cookies` 独立请求输入
- [x] 实现 `auth` 各类型映射
- [x] 实现 `binary` 请求体
- [x] 适配 override、history、失败输出
- [x] 补充样例与测试
- [x] 完成运行时验证并记录 retrospective

## 4. Surprises & Discoveries

- 认证信息进入请求模型后，失败输出和历史记录会更容易暴露敏感信息，因此虽然正式脱敏在 P2，本阶段也要避免明显泄漏扩大。
- `api_key in=cookie` 与显式 `cookies` 合并时，需要先约定冲突处理顺序。
- `binary` 需要与 `form_data(file)` 保持清晰边界，不能混成同一路径。
- 当前 shell 中不存在 `python` 命令，因此本轮仍无法在 WSL 侧直接完成 `validate` 和 `pytest` 运行时验证。
- 当前实现采用“最小敏感输出控制”，只在请求快照序列化阶段对明显敏感 key 做 `***`，没有扩展成完整脱敏系统。
- `reading_house` 适合做 auth 实流验证；`p0_minimal` 继续承载 cookies 和 binary 的 synthetic 测试。
- 用户已在 Windows `.venv` 中完成第三计划相关人工验证，结果通过。

## 5. Decision Log

当前沿用的已知决策：

- `cookies` 独立于 `headers`。
- `auth` 进入请求模型标准结构。
- 文件上传长期主路径走 `form_data`，纯文件流请求走 `binary`。
- 敏感字段脱敏正式能力在 P2，本计划只关注输入建模和基本输出边界。

本计划执行期间如果新增决策，需要同步到 `docs/decision_log.md`。

## 6. Context and Orientation

当前相关代码主要在：

- `Engine/request_resolver.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Utils/allure_reporter.py`
- `Core/composer.py`
- `examples/p0_minimal/Data/`
- `Tests/`

当前行为基线：

- 文档标准已经明确 `cookies/auth/binary`。
- 当前代码可能仍主要依赖 `headers` 和基础请求体能力。
- 这一阶段要避免为认证能力再引入一套散落在环境或 headers 里的隐式逻辑。

## 7. Plan of Work

先做 `cookies`，再做 `auth`，最后做 `binary`。

顺序：

1. 先让 `cookies` 成为独立请求输入。
2. 在此基础上实现 `auth` 的统一分发。
3. 最后补 `binary`，因为它对请求体路径影响最独立。
4. 统一补历史摘要、失败输出和测试。

## 8. Concrete Steps

预计修改文件：

- `Engine/request_resolver.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Utils/allure_reporter.py`
- `Core/composer.py`
- `Tests/test_repository.py` 或新增请求鉴权专项测试文件
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- 项目内用于测试的最小二进制样例文件

工作目录：

```text
/mnt/d/githubrepository/interface-auto/autoapi
```

预计命令：

```bash
python run.py validate --data examples/p0_minimal/Data
python -m pytest -q
```

人工验证重点：

- `cookies` 是否不再依赖手写 `headers.Cookie`。
- `auth` 各类型是否映射到正确位置。
- `binary` 是否与 `form_data(file)` 清晰分离。
- 失败输出是否避免把敏感信息完整回显。

## 9. Validation and Acceptance

完成标准：

- `python run.py validate --data examples/p0_minimal/Data` 通过。
- `python -m pytest -q` 通过，且至少新增覆盖：
  - `cookies`
  - `auth=bearer`
  - `auth=basic`
  - `auth=api_key(header/query/cookie)`
  - `binary`
  - 相关 override
- 人工验证中，`binary` 路径和认证输入能进入最终请求构建结果。

需要额外记录：

- `api_key in=cookie` 与显式 `cookies` 冲突时的最终规则。
- 当前阶段对敏感信息输出的最小控制措施。

## 10. Idempotence and Recovery

- 认证映射应保持单入口，避免同时保留多套 header 注入逻辑。
- `binary` 示例文件可以删除后重建。
- 如果发现认证与环境模板强耦合，必须先停下来更新范围说明，不能顺手把环境级鉴权模板一起做掉。

## 11. Outcomes & Retrospective

当前阶段结果：

- 已完成 `cookies` 正式请求输入。
- 已完成 `auth.type=none / bearer / basic / api_key(header/query/cookie)` 的请求构建翻译。
- 已完成 `body_mode=binary` 的请求构建。
- 已完成 `PreparedRequest` 的二进制摘要和最小敏感输出控制。
- 已补充 `reading_house` 的 auth 示例和 `p0_minimal` 的 cookies / auth / binary 测试资产。
- 已补充单独讲解文档：`docs/request_03_auth_binary_explanation.md`。

与计划偏差：

- 代码实现、静态检查和运行时验证均已完成。
- 运行时验证由用户在 Windows `.venv` 中执行。

验证结果：

- `git diff --check -- <相关文件>` 已通过。
- 用户已在 Windows `.venv` 中完成第三计划相关人工验证，结果通过。

剩余风险：

- 当前 binary 仍只支持 `source=path`。
- 当前最小敏感输出控制只覆盖请求快照，不等于完整脱敏体系。

下一步建议：

- 先由用户在 Windows `.venv` 中完成 validate / pytest / reading_house auth 验证。
- 若通过，再决定是否开始收口 `request` 模型后续清理或直接推进更高层能力。
