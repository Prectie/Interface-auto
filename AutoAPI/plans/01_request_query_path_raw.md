# AutoAPI 请求模型实现计划 01

## 1. Purpose / Big Picture

完成后，AutoAPI 的执行链可以稳定支持这组基础请求能力：

- `query`
- `path_params`
- `raw(json)`

用户可观察到的结果：

- `ApiTemplate / ApiCase / ScenarioStep override` 可以使用 `query` 和 `path_params`。
- `RequestResolver` 能基于 `path` + `path_params` 构建最终 URL。
- `raw(json)` 能作为正式请求体进入执行链。
- 历史结果和失败输出能反映这些字段的实际值。

这是后续完整请求模型实现的最小起点，也是最适合先落地的一批能力。

## 2. Scope

### In scope

- `RequestResolver` 支持：
  - `path`
  - `path_params`
  - `query`
  - `raw.raw_type=json`
- `Composer` / override 合成链对上述字段按字段级整体覆盖。
- `ApiCase`、`ScenarioStep.override` 使用上述字段时的执行链适配。
- 失败输出、history、Allure 附件中反映上述字段。
- 最小测试和最小样例补充。

### Out of scope

- `form_urlencoded`
- `form_data`
- `binary`
- `cookies`
- `auth`
- `raw(text/xml/html/javascript)`
- 场景级数据驱动
- step 重试 / step 失败继续
- 严格字段校验

## 3. Progress

- [x] 阅读当前 `RequestResolver / Composer / Executor` 代码
- [x] 梳理当前 `request` 输入结构与旧字段残留点
- [x] 实现 `path_params` 路径渲染
- [x] 实现 `query` 请求参数映射
- [x] 实现 `raw(json)` 请求体映射
- [x] 适配 case / scenario step override
- [x] 补充示例资产或测试样例
- [x] 完成运行时验证并记录 retrospective

## 4. Surprises & Discoveries

- 当前代码主链路已经迁移到 P0 新结构，但请求层仍可能保留旧 `params/body_type/body/files` 的内部假设。
- 当前文档标准已经升级为 `query/path_params/body_mode/raw`，实现时不能再继续围绕旧字段扩展。
- Windows `.venv` 可用于最终人工验证，WSL 不适合代跑项目虚拟环境。
- 当前 shell 中不存在 `python` 命令，因此本轮无法在 WSL 侧直接完成 `validate` 和 `pytest` 运行时验证。
- 用户已在 Windows `.venv` 中手动执行 `python run.py validate --data examples/p0_minimal/Data` 和 `python -m pytest -q`，结果均通过。

## 5. Decision Log

当前沿用的已知决策：

- 请求模型长期标准以 `docs/product_requirements.md` 为准。
- `override` 使用字段级整体覆盖，不做 deep merge。
- `method` 和 `path` 不允许被 case 或 step 改成另一个接口语义。
- `path` 模板来自 `ApiTemplate`，`path_params` 只负责替换占位符。

本计划执行期间如果新增决策，需要同步到 `docs/decision_log.md`。

## 6. Context and Orientation

当前相关代码主要在：

- `Core/composer.py`
- `Engine/request_resolver.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Utils/allure_reporter.py`
- `Schema/data_models.py`
- `examples/p0_minimal/Data/`

当前行为基线：

- 执行链已经支持新资产模型、基础 CLI、JSONL history 和 Allure。
- 请求模型文档已升级，但代码实现尚未完整跟上文档标准。
- 当前最稳妥的第一步是先把 URL 渲染和 `raw(json)` 打通，而不是一次做完整请求矩阵。

## 7. Plan of Work

先从请求解析入口收口，确认最终传给 `requests` 的 kwargs 结构，然后再补 override 和测试。

顺序：

1. 阅读 `RequestResolver` 和 `Composer`，找出旧字段残留。
2. 让 `path_params` 成为正式输入，统一完成路径占位符替换。
3. 让 `query` 成为正式请求参数输入。
4. 让 `raw(json)` 成为正式请求体输入。
5. 确认 case 和 scenario step 的 override 都能命中这三个字段。
6. 最后补 history、失败输出和测试。

## 8. Concrete Steps

预计修改文件：

- `Engine/request_resolver.py`
- `Core/composer.py`
- `Engine/executor.py`
- `Engine/history_writer.py`
- `Schema/data_models.py`（如有必要）
- `Tests/test_repository.py` 或新增更合适的请求模型测试文件
- `examples/p0_minimal/Data/apis.yaml`
- `examples/p0_minimal/Data/cases.yaml`
- `examples/p0_minimal/Data/Scenarios/*.yaml`

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

- `path` 中的 `{id}` 是否被正确替换。
- `query` 是否进入最终 URL。
- `raw(json)` 是否进入最终请求体。
- 失败输出里是否能看见渲染后的 request 摘要。

## 9. Validation and Acceptance

完成标准：

- `python run.py validate --data examples/p0_minimal/Data` 通过。
- `python -m pytest -q` 通过，且至少新增覆盖：
  - `path_params` 渲染
  - `query` 进入请求
  - `raw(json)` 映射
  - override 整体覆盖
- 人工执行 `case/scenario/plan` 时，请求构建不再依赖旧 `params/body_type` 命名。

如果 Windows `.venv` 之外的环境无法跑验证，需要记录原因，并由用户在 Windows 侧代跑。

## 10. Idempotence and Recovery

- 代码修改可重复执行，计划以最终文件内容为准。
- 示例 YAML 可重复调整，不涉及外部持久化状态。
- 如果请求模型测试失败，可回退到上一个可运行提交点后重新按步骤推进。
- 若发现当前实现必须同时引入 `form_urlencoded/form_data` 才能跑通，需要暂停并更新后续计划边界，不能静默扩范围。

## 11. Outcomes & Retrospective

当前阶段结果：

- 已完成 `Composer` 和 `RequestResolver` 对 `query / path_params / raw(json)` 的主链路适配。
- 已将 `examples/p0_minimal` 中的请求示例迁移到新字段。
- 已补充针对 `query/path_params/raw(json)` 的测试断言。

与计划偏差：

- 代码实现、静态检查和运行时验证均已完成。
- 运行时验证由用户在 Windows `.venv` 中执行。

验证结果：

- `git diff --check -- <相关文件>` 已通过。
- 用户在 Windows `.venv` 中执行 `python run.py validate --data examples/p0_minimal/Data`，结果通过。
- 用户在 Windows `.venv` 中执行 `python -m pytest -q`，结果通过。

剩余风险：

- 当前阶段只支持 `raw(json)`，还未进入 `form_urlencoded / form_data / binary / auth / cookies`。

下一步建议：

- 继续进入 `02_request_form_modes.md`。
