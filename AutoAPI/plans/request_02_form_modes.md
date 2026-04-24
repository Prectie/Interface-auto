# AutoAPI 请求模型实现计划 02

## 1. Purpose / Big Picture

完成后，AutoAPI 的执行链可以正式支持表单类请求：

- `form_urlencoded`
- `form_data`（`field` / `file`）

用户可观察到的结果：

- 表单登录、multipart 纯字段、文件上传、文件 + 文本字段混合请求可以进入正式执行链。
- `form_data` 的长期抽象不再只是文档约定，而是代码层真实能力。
- 请求失败时，history 和调试输出能保留必要的表单结构信息。

## 2. Scope

### In scope

- `body_mode=form_urlencoded`
- `body_mode=form_data`
- `form_data.kind=field`
- `form_data.kind=file`
- `source=path` 的单文件上传
- `field + file` 混合请求
- 对应 override、history、失败输出、最小测试和示例

### Out of scope

- `binary`
- `cookies`
- `auth`
- `source=bytes/base64/generated/url`
- 多文件复杂策略优化
- MIME 自动探测
- 上传文件存在性严格 schema 校验

## 3. Progress

- [ ] 阅读当前 transport / request resolver 对 `data/files` 的已有支持
- [ ] 明确 `form_urlencoded` 到 `requests` kwargs 的映射
- [ ] 明确 `form_data(field/file)` 到 `requests` multipart 结构的映射
- [ ] 实现 `form_data` 渲染与字段级覆盖
- [ ] 适配失败输出与 history 摘要
- [ ] 补充文件上传示例与测试
- [ ] 完成验证并记录 retrospective

## 4. Surprises & Discoveries

- 当前文档已经规定 `files` 不再作为长期标准字段，代码实现需要避免再新增孤立 `files` 主路径。
- `form_data` 的长期标准是列表项结构，不能偷懒改回字典或直接绑死到底层 `requests` tuple 写法。
- Windows / WSL 路径差异可能影响文件上传测试，示例路径需要尽量保持项目内相对路径。

## 5. Decision Log

当前沿用的已知决策：

- 文件上传长期主路径走 `form_data`。
- `form_data` 使用统一 item 结构，`kind=field|file`。
- 纯文件流请求另走 `binary`，不在本计划内实现。
- override 继续使用字段级整体覆盖。

本计划执行期间如果新增决策，需要同步到 `docs/decision_log.md`。

## 6. Context and Orientation

当前相关代码主要在：

- `Engine/request_resolver.py`
- `Engine/transport.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Core/composer.py`
- `examples/p0_minimal/Data/`
- `Tests/`

当前行为基线：

- 旧代码历史上可能已有 `data/files` 残留，但新实现必须以 `body_mode + form_urlencoded/form_data` 为入口。
- 这一阶段本质是在“保留底层 requests 能力”的前提下，重写上层输入抽象。

## 7. Plan of Work

先做 `form_urlencoded`，因为它风险更低，完成后再做 `form_data`。

顺序：

1. 先把 `form_urlencoded` 映射到稳定请求构建逻辑。
2. 再把 `form_data.kind=field` 映射到 multipart。
3. 最后实现 `kind=file + source=path`。
4. 补充 override、历史摘要、失败输出和测试。

## 8. Concrete Steps

预计修改文件：

- `Engine/request_resolver.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Core/composer.py`
- `Tests/test_repository.py` 或新增请求体专项测试文件
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `examples/p0_minimal/Data/Scenarios/*.yaml`
- 项目内用于测试的最小上传样例文件

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

- `form_urlencoded` 是否进入正确请求体。
- `form_data(field)` 是否按 multipart 发送。
- `form_data(file)` 是否能读取项目内相对路径文件。
- 文件 + 文本字段混合时结构是否稳定。

## 9. Validation and Acceptance

完成标准：

- `python run.py validate --data examples/p0_minimal/Data` 通过。
- `python -m pytest -q` 通过，且至少新增覆盖：
  - `form_urlencoded`
  - `form_data(field)`
  - `form_data(file)`
  - `form_data(field + file)`
  - 对应 override 覆盖
- 人工验证中，请求失败输出能看到合理的 form 摘要，而不是完全丢失结构。

如果文件上传验证受本地服务或路径环境影响，需要明确记录是实现问题还是环境问题。

## 10. Idempotence and Recovery

- 示例文件可以重复使用和重建。
- `form_data` 映射应保持单入口，避免同时保留多个临时兼容路径。
- 如果文件上传部分引入平台差异问题，可先保留 `form_urlencoded + form_data(field)` 已完成状态，再单独修正 `file` 分支，但需要在计划中明确暂停点。

## 11. Outcomes & Retrospective

待实施后填写：

- 实际完成内容
- 与计划偏差
- 验证结果
- 剩余风险
- 下一步衔接 `request_03_cookies_auth_binary.md`
