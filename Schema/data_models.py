from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class HostRule:
    # host 保存的是 env.hosts 里的 key,而不是直接写死的 base_url,方便环境统一切换.
    host: str
    # priority 用于多个规则同时命中时做优先级裁决,数值越大优先级越高.
    priority: int = 0
    # apis 用于按 api_id 精确匹配 host,适合少量特殊接口单独路由.
    apis: List[str] = field(default_factory=list)
    # modules 用于按接口所属模块匹配 host,适合同一业务模块统一路由.
    modules: List[str] = field(default_factory=list)
    # path_prefixes 用于按请求 path 前缀匹配 host,适合按服务路径拆分.
    path_prefixes: List[str] = field(default_factory=list)
    # default 标记兜底规则,当前环境没有其它规则命中时使用.
    default: bool = False


@dataclass
class EnvProfile:
    # variables 是当前环境下参与 ${var} 渲染的变量池.
    variables: Dict[str, Any] = field(default_factory=dict)
    # hosts 保存 host key 到 base_url 的映射,实际 host 只能从这里解析.
    hosts: Dict[str, str] = field(default_factory=dict)
    # host_rules 保存当前环境的 host 选择规则,执行时由 HostResolver 使用.
    host_rules: List[HostRule] = field(default_factory=list)


@dataclass
class EnvironmentConfig:
    # active_env 指定默认执行环境,CLI 或场景未指定时使用它.
    active_env: str
    # envs 保存所有环境配置,key 是环境名.
    envs: Dict[str, EnvProfile] = field(default_factory=dict)
    # request_defaults 是所有请求都会继承的默认 requests 参数.
    request_defaults: Dict[str, Any] = field(default_factory=dict)
    # shared_extracts 保存项目级可复用的提取规则片段.
    shared_extracts: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    # shared_assertions 保存项目级可复用的断言规则片段.
    shared_assertions: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)


@dataclass
class ApiTemplate:
    # id 是全局唯一的接口模板 ID,由用户在 当前阶段手写维护.
    id: str
    # meta 保存展示和分类信息,不参与请求拼接的核心逻辑.
    meta: Dict[str, Any] = field(default_factory=dict)
    # request 保存接口模板请求定义,包含 method/path/header 等公共请求结构.
    request: Dict[str, Any] = field(default_factory=dict)
    # parameters 预留给字段定义和后续 schema 校验使用.
    parameters: Dict[str, Any] = field(default_factory=dict)
    # before_steps 是接口模板默认前置动作,用例可整体覆盖.
    before_steps: List[HookStep] = field(default_factory=list)
    # after_steps 是接口模板默认后置动作,用例可整体覆盖.
    after_steps: List[HookStep] = field(default_factory=list)
    # extract_ref 保存模板层引用的共享提取片段 ID 列表.
    extract_ref: List[str] = field(default_factory=list)
    # extract 是接口模板默认提取规则,用例可整体覆盖.
    extract: List[Dict[str, Any]] = field(default_factory=list)
    # assertions_ref 保存模板层引用的共享断言片段 ID 列表.
    assertions_ref: List[str] = field(default_factory=list)
    # assertions 是接口模板默认断言规则,用例可整体覆盖.
    assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiCase:
    # id 是全局唯一的接口用例 ID,场景步骤只能引用 case_ 开头的 ID.
    id: str
    # use 指向所属 ApiTemplate 的 ID, 与 ScenarioStep.use 同名同义,
    # 替代 v0.1 的 cases.<id>.api 字段（v0.2 schema 收敛, 详见 PRD §6 决策 4）.
    use: str
    # meta 保存用例自己的展示信息,覆盖模板展示信息时不影响请求逻辑.
    meta: Dict[str, Any] = field(default_factory=dict)
    # request 保存用例层覆盖的请求字段,禁止覆盖 method/path.
    request: Dict[str, Any] = field(default_factory=dict)
    # extract_ref 若在 YAML 中出现,则字段级整体替换模板默认引用列表.
    extract_ref: List[str] = field(default_factory=list)
    # extract 若在 YAML 中出现,则字段级整体替换模板默认值.
    extract: List[Dict[str, Any]] = field(default_factory=list)
    # assertions_ref 若在 YAML 中出现,则字段级整体替换模板默认引用列表.
    assertions_ref: List[str] = field(default_factory=list)
    # assertions 若在 YAML 中出现,则字段级整体替换模板默认值.
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    # provided_fields 记录 YAML 实际写过哪些字段,用于区分“未写”和“写了空值”.
    provided_fields: Set[str] = field(default_factory=set)


@dataclass
class ScenarioStep:
    # id 是场景内步骤展示 ID,用于报告和错误定位.
    id: str
    # use 直接引用全局 case ID,不使用 case:/api: 前缀；
    # 与 action 形成 XOR:每个 step 必须且只能填一个.
    use: Optional[str] = None
    # action 让 step 直接承载 wait/sql/script 内联动作, 与 use XOR;
    # 内核会沿用 _execute_action_hook 同一份执行器, 让"清理 case"与"清理 SQL"等价.
    action: Optional[Dict[str, Any]] = None
    # override 只在当前步骤生效,不回写被引用的 ApiCase.
    override: Dict[str, Any] = field(default_factory=dict)
    # delay 预留给步骤间等待,执行器可按需读取.
    delay: Optional[float] = None
    # always_run=True 让该 step 在前序失败后仍然被执行,
    # 用作"无论成功失败都要跑的清理步骤"承载点（PRD §6 决策 1）.
    always_run: bool = False
    # continue_on_error=True 允许该 step 失败后 scenario 继续向下执行,
    # 默认 False 维持 v0.1 "失败即停" 行为（PRD §6 决策 1）.
    continue_on_error: bool = False


@dataclass
class HookStep:
    # id 是 hook 动作展示 ID,用于报告和错误定位.
    id: str
    # action 保存 action-only hook 配置,例如 {"kind": "wait", "seconds": 1}.
    action: Dict[str, Any] = field(default_factory=dict)
    # delay 是动作执行前的可选等待,和 action.kind=wait 不同,属于调度层延迟.
    delay: Optional[float] = None
    # raw 保存 YAML 原始片段,Validator 用它识别 hooks 中误写的 use 等旧字段.
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ScenarioDataset:
    # name 是数据集展示名,也是报告和 history 的主要标识.
    name: str
    # variables 是该数据集本轮注入的初始业务变量.
    variables: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    # id 是全局唯一场景 ID.
    id: str
    # env 可覆盖默认 active_env；为空时执行侧使用配置默认环境.
    env: Optional[str] = None
    # meta 保存场景展示和分类信息.
    meta: Dict[str, Any] = field(default_factory=dict)
    # datasets 保存场景级数据驱动配置；为空时按单轮执行.
    datasets: List[ScenarioDataset] = field(default_factory=list)
    # before_steps 在每轮主流程前执行；仅承载辅助 action（wait/sql/script）.
    before_steps: List[HookStep] = field(default_factory=list)
    # steps 保存显式排列的业务步骤,顺序即执行顺序.
    # v0.2 起 steps[].always_run=True 取代 v0.1 的 finally_steps 兜底语义.
    steps: List[ScenarioStep] = field(default_factory=list)
    # after_steps 仅在主流程成功后执行；仅承载辅助 action（wait/sql/script）.
    after_steps: List[HookStep] = field(default_factory=list)
    # assertions_ref 保存场景层引用的共享断言片段 ID 列表.
    assertions_ref: List[str] = field(default_factory=list)
    # assertions 保存场景级断言,第一版只用于校验当前轮上下文变量.
    assertions: List[Dict[str, Any]] = field(default_factory=list)
    # source 记录场景来自哪个 YAML 文件,便于报错定位.
    source: str = ""


@dataclass
class TestPlan:
    # id 是全局唯一测试计划 ID.
    id: str
    # meta 保存测试计划展示和分类信息.
    meta: Dict[str, Any] = field(default_factory=dict)
    # scenarios 保存计划包含的场景 ID 列表.
    scenarios: List[str] = field(default_factory=list)
    # cases 保存计划直接包含的单接口用例 ID 列表.
    cases: List[str] = field(default_factory=list)


@dataclass
class ProjectAssets:
    # config 保存一次加载得到的完整环境配置.
    config: EnvironmentConfig
    # apis 保存所有 ApiTemplate,key 为 api_id.
    apis: Dict[str, ApiTemplate] = field(default_factory=dict)
    # cases 保存所有 ApiCase,key 为 case_id.
    cases: Dict[str, ApiCase] = field(default_factory=dict)
    # scenarios 保存所有 Scenario,key 为 scenario_id.
    scenarios: Dict[str, Scenario] = field(default_factory=dict)
    # plans 保存所有 TestPlan,key 为 plan_id.
    plans: Dict[str, TestPlan] = field(default_factory=dict)


@dataclass
class ExecutableCase:
    # case_id 记录执行对象来源的 ApiCase,便于报告和错误上下文定位.
    case_id: str
    # api_id 记录执行对象继承的 ApiTemplate.
    api_id: str
    # meta 是用例层展示信息的运行时快照.
    meta: Dict[str, Any] = field(default_factory=dict)
    # api_meta 是模板层展示信息的运行时快照,host_rules 会读取 module.
    api_meta: Dict[str, Any] = field(default_factory=dict)
    # request 是模板和用例按 覆盖规则合成后的请求结构.
    request: Dict[str, Any] = field(default_factory=dict)
    # before_steps 是合成后的前置动作.
    before_steps: List[HookStep] = field(default_factory=list)
    # after_steps 是合成后的后置动作.
    after_steps: List[HookStep] = field(default_factory=list)
    # extract_ref 是合成后的共享提取引用快照.
    extract_ref: List[str] = field(default_factory=list)
    # extract 是合成后的提取规则.
    extract: List[Dict[str, Any]] = field(default_factory=list)
    # assertions_ref 是合成后的共享断言引用快照.
    assertions_ref: List[str] = field(default_factory=list)
    # assertions 是合成后的断言规则.
    assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ExecutableStep:
    # scenario_id 记录当前步骤所属场景,便于报告和错误定位.
    scenario_id: str
    # step_id 记录场景步骤 ID.
    step_id: str
    # case_id 记录步骤最终引用的 ApiCase.
    case_id: str
    # api_id 记录步骤最终关联的 ApiTemplate.
    api_id: str
    # meta 是用例层展示信息经过场景步骤组合后的运行时快照.
    meta: Dict[str, Any] = field(default_factory=dict)
    # api_meta 是模板层展示信息,host 解析需要读取其中的 module.
    api_meta: Dict[str, Any] = field(default_factory=dict)
    # request 是模板、用例和步骤 override 合成后的最终请求结构.
    request: Dict[str, Any] = field(default_factory=dict)
    # before_steps 是步骤级 override 后的前置动作.
    before_steps: List[HookStep] = field(default_factory=list)
    # after_steps 是步骤级 override 后的后置动作.
    after_steps: List[HookStep] = field(default_factory=list)
    # extract_ref 是步骤级 override 后的共享提取引用快照.
    extract_ref: List[str] = field(default_factory=list)
    # extract 是步骤级 override 后的提取规则.
    extract: List[Dict[str, Any]] = field(default_factory=list)
    # assertions_ref 是步骤级 override 后的共享断言引用快照.
    assertions_ref: List[str] = field(default_factory=list)
    # assertions 是步骤级 override 后的断言规则.
    assertions: List[Dict[str, Any]] = field(default_factory=list)
