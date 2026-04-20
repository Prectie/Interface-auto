from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class HostRule:
    host: str
    priority: int = 0
    apis: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    path_prefixes: List[str] = field(default_factory=list)
    default: bool = False


@dataclass
class EnvProfile:
    variables: Dict[str, Any] = field(default_factory=dict)
    hosts: Dict[str, str] = field(default_factory=dict)
    host_rules: List[HostRule] = field(default_factory=list)


@dataclass
class EnvironmentConfig:
    active_env: str
    envs: Dict[str, EnvProfile] = field(default_factory=dict)
    request_defaults: Dict[str, Any] = field(default_factory=dict)
    sensitive_keys: List[str] = field(default_factory=list)


@dataclass
class ApiTemplate:
    id: str
    meta: Dict[str, Any] = field(default_factory=dict)
    request: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    before_steps: List[Dict[str, Any]] = field(default_factory=list)
    after_steps: List[Dict[str, Any]] = field(default_factory=list)
    extract: List[Dict[str, Any]] = field(default_factory=list)
    assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ApiCase:
    id: str
    api: str
    meta: Dict[str, Any] = field(default_factory=dict)
    request: Dict[str, Any] = field(default_factory=dict)
    before_steps: List[Dict[str, Any]] = field(default_factory=list)
    after_steps: List[Dict[str, Any]] = field(default_factory=list)
    extract: List[Dict[str, Any]] = field(default_factory=list)
    assertions: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ScenarioStep:
    id: str
    use: str
    override: Dict[str, Any] = field(default_factory=dict)
    delay: Optional[float] = None


@dataclass
class Scenario:
    id: str
    env: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)
    steps: List[ScenarioStep] = field(default_factory=list)
    source: str = ""


@dataclass
class TestPlan:
    id: str
    meta: Dict[str, Any] = field(default_factory=dict)
    scenarios: List[str] = field(default_factory=list)
    cases: List[str] = field(default_factory=list)


@dataclass
class ProjectAssets:
    config: EnvironmentConfig
    apis: Dict[str, ApiTemplate] = field(default_factory=dict)
    cases: Dict[str, ApiCase] = field(default_factory=dict)
    scenarios: Dict[str, Scenario] = field(default_factory=dict)
    plans: Dict[str, TestPlan] = field(default_factory=dict)
