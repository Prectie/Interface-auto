# AutoAPI 决策记录

本文档记录 AutoAPI 的重要产品和架构决策。它回答“为什么这样定”，避免后续反复讨论或实现跑偏。

## 2026-04-17：P0/P1 阶段测试资产采用 YAML-first

背景：

AutoAPI 当前目标是轻量级接口自动化框架，优先完成 CLI、YAML、执行引擎、Allure 和结构化历史。

决策：

- P0/P1 阶段，`ApiTemplate`、`ApiCase`、`Scenario`、`TestPlan` 都以 YAML 作为资产源。
- 这些测试资产通过 Git 管理。
- 不把接口资产放进数据库。
- JSONL 或数据库只用于执行历史和报告趋势数据。

原因：

- YAML 便于阅读、diff、review 和回滚。
- 当前没有 Web UI 和团队协作后端，资产入库收益不高。
- 数据库存资产会提前引入服务端、迁移、备份、权限等复杂度。

影响：

- P0 实现应围绕 `Data/apis.yaml`、`Data/cases.yaml`、`Data/Scenarios/*.yaml`、`Data/plans.yaml`。
- 历史结果可以进入 `Reports/history/*.jsonl`。

## 2026-04-17：新结构不兼容旧 single.yaml / Flows

背景：

当前旧结构将接口定义、请求数据、断言、提取、依赖和 cleanup 混在 `Data/single.yaml` 中，flow 使用 `Data/Flows/*.yaml`。

决策：

- P0 新执行器只支持新结构。
- 不保留旧 `Data/single.yaml` 和 `Data/Flows/*.yaml` 兼容层。
- 可以后续提供一次性迁移脚本，但迁移后以新结构为准。

原因：

- 当前框架仍不成熟，优先保证新结构清晰。
- 保留旧兼容会增加 Repository、Validator、Executor 的复杂度。
- 旧结构的 `depends_on` 和 `cleanup` 与新产品模型冲突。

影响：

- P0 可以破坏式重构。
- 不需要为旧 `ApiItem` / `FlowBundle` 保留执行路径。

## 2026-04-17：接口定义升级为 ApiTemplate

背景：

接口定义不仅需要描述接口是什么，还希望复用默认前置、后置、提取和断言，减少每个 case 重复配置。

决策：

- AutoAPI 中的接口定义称为 `ApiTemplate`。
- `ApiTemplate` 是可执行接口模板，不是纯 OpenAPI definition。
- `ApiTemplate` 可以包含默认 `before_steps`、`after_steps`、`extract`、`assertions`。

原因：

- 默认 hooks / extract / assertions 可以在多个 case 中复用。
- case 未覆盖时可以继承模板默认配置。
- 比纯接口定义更符合当前框架定位。

影响：

- 后续 OpenAPI import 只能生成基础接口模板草稿。
- 正式执行逻辑从 `ApiTemplate + ApiCase + ScenarioStep override` 合成。

## 2026-04-17：case 不允许覆盖 method/path

背景：

case 是同一接口的不同测试变体，不应该改变接口本身。

决策：

- `ApiCase` 可以覆盖 `path_params`、`query`、`headers`、`cookies`、`auth`、`body_mode`、`form_data`、`form_urlencoded`、`raw`、`binary`、`extract`、`assertions`、`hooks`。
- `ApiCase` 禁止覆盖 `method` 和 `path`。
- `ScenarioStep override` 同样禁止覆盖 `method` 和 `path`。

原因：

- 保证接口路径和方法只来自 `ApiTemplate`。
- `ApiTemplate` 变更后，case 和 scenario 可以自然跟随。
- 避免 case 变成另一个接口。

影响：

- Resolver 需要在合成阶段保护 `method/path`。
- Validator 后续严格化时需要检查该规则。

## 2026-04-24：`form_data.kind=file` 收敛为极简模型

背景：

早期请求模型为了扩展性，把 `form_data.kind=file` 设计成 `source + path + filename + content_type`。但 AutoAPI 当前目标不是通用 API client，而是低认知负担的测试资产模型。对当前产品来说，这些字段大多属于传输层细节，而不是用户真正需要维护的配置。

决策：

- `form_data.kind=file` 正式用户字段只保留 `name + path`。
- `kind` 继续保留，取值固定为 `field / file`。
- 不再把 `source / filename / content_type` 作为 `form_data.kind=file` 的正式用户字段。

原因：

- 当前真实上传路径就是本地文件路径。
- 上传文件名默认取本地文件名，更符合平台实际使用方式。
- content type 属于 multipart 组装细节，不应增加 YAML 心智负担。

影响：

- PRD、示例资产、测试和讲解文档都要统一收敛。
- `RequestResolver` 内部仍可根据本地文件名推导 content type，但这属于实现细节。
- `binary` 仍保留自己的 `source/path/content_type` 结构，不受本决策影响。

## 2026-04-17：override 使用字段级整体覆盖

背景：

旧框架使用 `deep_merge`，dict 会递归合并。该规则对用户有认知成本。

决策：

- P0 新模型采用字段级整体覆盖。
- 未填写字段：继承上层。
- 字段已填写：整体覆盖上层。
- 字段为 null：显式清空。
- 字段内部不做 deep merge。

原因：

- 规则简单，用户容易理解。
- 避免 list、dict、scalar 使用不同合并规则。
- 即使覆盖时需要多写一点配置，也比隐式合并更可控。

影响：

- `Core/data_processing.py` 中的 `deep_merge` 不能作为新模型主合成逻辑。
- 需要新增字段级 resolver 或 composition 逻辑。

## 2026-04-17：host 只通过 Environment host_rules 解析

背景：

旧结构在 request 中写 `host`，用户希望 host 由全局环境统一管理，并按范围自动匹配。

决策：

- `ApiTemplate`、`ApiCase`、`ScenarioStep` 不出现 `host` 或 `host_key`。
- host 只在 Environment 中配置。
- 执行时根据 `host_rules` 解析 base_url。

匹配来源：

- `apis`
- `modules`
- `path_prefixes`
- `default`

原因：

- 避免 host 分散在多个资产层。
- 更接近平台化环境管理方式。
- 可以通过 priority 解决匹配优先级问题。

影响：

- `RequestResolver` 需要从 `host_rules` 解析 host。
- `method + path` 重复检查不依赖 request-level host。

## 2026-04-17：场景步骤直接引用全局唯一 ID

背景：

曾考虑使用 `case:case_xxx` 这种命名空间引用方式，但如果 ID 全局唯一，则前缀语法会增加噪音。

决策：

- 所有资产 ID 全局唯一。
- 引用时直接写 ID。
- P0 阶段，`scenario.steps[].use` 只允许引用 `case_` 开头的 ID。

示例：

```yaml
steps:
  - id: 启动业务
    use: case_start_task_success
```

原因：

- YAML 更简洁。
- ID 前缀已经能表达类型。
- 校验器可以根据字段语义和 ID 前缀检查引用合法性。

影响：

- 不使用 `case:`、`api:`、`scn:` 作为引用语法。
- 所有资产 ID 需要全局唯一。

## 2026-04-17：P0 阶段 ID 手写，后续再自动生成

背景：

当前没有平台或 CLI 生成 ID 的能力。

决策：

- P0 阶段 ID 由用户手写。
- 使用可读、稳定、语义化 ID。
- 推荐格式：
  - `api_start_task`
  - `case_start_task_success`
  - `scn_hanoi_main_flow`
  - `plan_hanoi_regression`

原因：

- 随机短 ID 或纯数字 ID 不适合当前 YAML 手写阶段。
- 语义化 ID 更容易阅读、引用和 CLI 调试。

影响：

- P2 可以提供 CLI 自动生成 stable ID。
- 未来平台内部可以有数据库主键，但 YAML 引用仍使用 stable ID。

## 2026-04-17：废弃接口级 depends_on

背景：

旧 `depends_on` 允许接口隐藏引用其他接口，导致场景实际执行链不直观。

决策：

- P0 移除接口级 `depends_on` 编排能力。
- 业务流程必须在 `Scenario.steps` 中显式编排。

原因：

- 场景应该清楚展示真实业务步骤。
- 隐式依赖链难以维护和调整。
- 中间步骤变化时，显式场景更容易修改。

影响：

- `Executor._run_depends_on` 不应进入新模型主执行链。
- 旧 `depends_on` 不做兼容。

## 2026-04-17：废弃旧 cleanup 字段

背景：

旧 single 和 flow 都支持 `cleanup`，但业务清理和兜底清理混在一起。

决策：

- P0 移除旧 `cleanup` 字段。
- 业务清理作为普通场景 step 显式编排。
- P1 再考虑 `before_steps`、`after_steps`、`finally_steps`。

原因：

- 显式步骤更清楚。
- cleanup 不应该隐藏业务流程。
- 兜底清理后续用统一 hooks 模型表达。

影响：

- `Executor._run_cleanup` 不应进入新模型主执行链。
- P0 不实现 `finally_steps`。

## 2026-04-17：P0 暂时关闭严格字段 schema 校验

背景：

当前旧 Validator 很严格，但新模型还在演进。如果一开始就做完整字段校验，会拖慢核心链路开发。

决策：

- P0 只保留 Validator 壳子和基础检查。
- 暂不做完整字段白名单、类型、枚举、request/extract/assertions/hooks schema 校验。

P0 保留检查：

- YAML 可读取。
- 全局 ID 唯一。
- 引用关系存在。
- `method + path` 重复。
- `host_rules` 基础冲突。

原因：

- 先跑通 Repository、Resolver、Executor、CLI 主链路。
- 等模型稳定后再补严格校验，避免反复改 schema。

影响：

- P2 再补严格字段校验。
- 新 Validator 需要保留扩展点。

## 2026-04-24：请求模型升级为 Postman / MeterSphere 风格标准

背景：

原始 P0 请求结构偏简化，主要围绕 `params/body_type/body/files`。继续沿这个方向加能力，会导致后续 `path_params`、`raw subtype`、`auth`、`cookies`、文件上传和纯二进制上传都只能用补丁方式接入。

决策：

- PRD 中的长期标准请求模型升级为：
  - `path_params`
  - `query`
  - `headers`
  - `cookies`
  - `auth`
  - `body_mode`
  - `form_data`
  - `form_urlencoded`
  - `raw`
  - `binary`
  - `timeout`
  - `verify`
  - `allow_redirects`
- `params` 在文档层统一改名为 `query`。
- `body_type` 在文档层统一改名为 `body_mode`。
- `path_params` 独立建模，不再混在 `path` 字符串拼接里。
- `raw` 使用 `raw + raw_type` 作为长期标准。
- `auth` 和 `cookies` 纳入请求模型标准结构。
- 文件上传长期主路径走 `form_data`。
- `form_data` 使用统一 item 结构，`kind=field|file`。
- 纯文件流请求长期走 `binary`。

## 2026-04-24：`raw` 非 JSON 子类型统一走 `requests data`

背景：

PRD 已经定义 `raw_type=json/text/xml/html/javascript`，但实现早期只支持 `json`。同时，`requests` 的 `json` 参数和 `data/files` 互斥，不能把“JSON body”和“其它原始文本 body”混在一个发送入口里。

决策：

- `raw_type=json` 继续映射到 `requests json`
- `raw_type=text/xml/html/javascript` 统一映射到 `requests data`
- 对 `text/xml/html/javascript` 自动补默认 `Content-Type`
- 若用户已显式写了 `headers.Content-Type`，执行层不覆盖用户值

默认 `Content-Type`：

- `text` -> `text/plain`
- `xml` -> `application/xml`
- `html` -> `text/html`
- `javascript` -> `application/javascript`

原因：

- 更符合 `requests` 的官方语义边界
- 能明确区分 JSON body 和其它原始文本 body
- 保持 `raw` 与 `form_data / form_urlencoded / binary` 的互斥规则清晰

影响：

- `RequestResolver` 的 `raw` 分支需要按 `raw_type` 分流
- 测试需要覆盖默认头、显式头不覆盖、非字符串 content 的稳定转换

原因：

- 更接近 Postman / MeterSphere 的使用心智。
- 请求结构分层更清晰，便于 CLI、YAML 和后续 Web UI 统一。
- 避免继续在旧抽象上堆补丁，降低后续扩展成本。
- 平台化后更容易做表单编辑、调试和导入映射。

影响：

- PRD 先定义完整标准，代码实现可以分阶段落地。
- 当前执行器如果仍只支持子集，也必须按这个长期标准演进，而不是继续扩旧字段。
- 相关示例、技术设计和后续导入能力都要围绕该模型收敛。

## 2026-04-24：执行完成后自动生成 Allure HTML 报告

背景：

之前的思路偏向“执行后由用户再手动执行命令生成 Allure 报告”。这会增加一次额外操作，不符合当前 CLI 工具的直接使用心智。

决策：

- 每次 `case/scenario/plan` 执行完成后，自动生成：
  - `Reports/allure-results/<run_id>/`
  - `Reports/allure-report/<run_id>/`
- CLI 直接输出 HTML 报告路径。
- 默认不自动打开浏览器。
- 如果 Allure CLI 缺失或 HTML 生成失败，只输出 warning，不改变真实测试执行状态。

原因：

- 报告是执行结果的一部分，应该自动产出，而不是依赖用户二次命令。
- 自动生成 HTML 更符合轻量 CLI 工具的使用体验。
- 报告生成失败不应掩盖真实测试状态。

影响：

- Allure 不再只是保留原始结果目录，还需要在执行完成后补一次 HTML 生成动作。
- CLI 输出中需要包含报告路径和 warning 信息。
- 错误处理要区分“执行失败”和“报告生成失败”。

## 2026-04-24：P1 / P2 优先级重排

背景：

当前 P0 主链路已经基本明确。部分原先放在 P1 的能力，虽然有价值，但并不影响下一阶段继续稳定核心模型和执行链，过早实现会分散注意力。

决策：

- P1 保留：
  - 场景级数据驱动
  - 场景级 `before_steps / after_steps / assertions`
  - `finally_steps`
  - action-only hooks
  - 公共断言 / 公共提取
- 下列能力移动到 P2：
  - `step 重试`
  - `step 失败继续`
  - `OpenAPI 导入`
  - `历史结果 SQLite`
  - `敏感变量脱敏`
  - `资产索引与影响分析`
  - `CLI 自动生成 stable ID`
  - `严格字段校验`

原因：

- 这些能力要么属于执行增强，要么属于产品化增强，要么属于平台化准备。
- 它们不是下一阶段把核心模型做稳的前置条件。
- 先缩小 P1 范围，可以减少多线并行带来的设计噪音。

影响：

- PRD、技术设计和后续 ExecPlan 都要按新的 P1/P2 边界排期。
- 严格字段校验和稳定 ID 生成不再默认视为近阶段能力。
- OpenAPI、SQLite、敏感脱敏、资产索引等能力后续统一归到产品化与平台化阶段处理。

## 2026-04-25：hooks 改为 action-only，废弃环境鉴权模板方向

背景：

之前的环境级 `setup_cases / teardown_cases / auth_profile` 和场景级 hooks 都支持通过 `use` 引用 case。这个方向会把业务接口调用藏进 hooks 或环境配置中，容易重新形成隐式链式编排，和“场景显式编排”的产品原则冲突。

决策：

- `Scenario.steps` 是唯一承载业务接口编排的位置。
- `ApiTemplate`、`ApiCase`、`Scenario` 的前置、后置和兜底 hooks 统一使用 action-only 模型。
- hooks 中不允许出现 `use`，不允许引用 `case` 或 `api`。
- 当前 action 第一批只实现 `wait`。
- `sql` 和 `script` 作为结构扩展点预留，暂不实现执行能力。
- action 内部如果需要把执行结果写回上下文，统一使用 `extract` 字段，保持和接口/用例/场景提取命名一致。
- 环境级 `setup_cases / teardown_cases / auth_profile / auth_profiles` 不再作为产品方向继续扩展，后续代码清理时移除。
- 登录、准备数据、清理数据等接口动作必须作为普通场景 step 显式排列。

影响：

- 已经实现的环境级鉴权模板属于临时方向偏差，需要通过新的清理计划移除。
- 已经实现的场景级 hooks 需要从 `ScenarioStep(use=case_id)` 改为 `HookStep(action=...)`。
- 文档中的 `setup` / `teardown` 只作为未来平台化生命周期术语保留，不进入当前 YAML 字段。

## 2026-04-25：P1 核心能力收口，后续显式进入 P2

背景：

Allure 自动 HTML、公共断言/提取、场景级数据驱动、场景级 hooks、`finally_steps`、action-only hooks、环境级 auth_profile 清理，以及企业常用断言/提取 source 扩展已经完成第一版，并由用户在 Windows `.venv` 环境中完成验证。

决策：

- 当前 P1 按已讨论范围收口。
- 后续不再以“补 P1 缺口”为名继续扩大执行器能力。
- 如果继续开发，应从 P2 清单中显式选择一个起点。
- P2 起点包括但不限于：
  - `step retry`
  - `step continue_on_error`
  - OpenAPI 导入
  - SQLite 历史
  - 敏感变量脱敏
  - 资产索引与影响分析
  - CLI 稳定 ID 生成
  - 严格字段校验
  - tag / priority 执行

原因：

- 当前核心模型已经能覆盖轻量级接口自动化框架的主要使用闭环。
- 继续推进的能力大多属于产品化、平台化或执行增强，需要单独评估优先级。
- 明确 P1 收口可以避免把 P2 能力静默混入当前阶段。

影响：

- 下一轮实现必须先明确选择 P2 目标，并创建对应 numbered ExecPlan。
- 文档和计划应把 P1 已完成能力与 P2 延后能力分开描述。
