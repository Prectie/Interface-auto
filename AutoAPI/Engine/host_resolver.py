from __future__ import annotations

from typing import List, Tuple

from Exceptions.AutoApiException import (
    ExceptionCode,
    RequestBuildException,
    build_api_exception_context,
)
from Schema.data_models import EnvProfile, HostRule


class HostResolver:
    def resolve_base_url(
        self,
        env: EnvProfile,
        *,
        api_id: str,
        module: str,
        path: str,
    ) -> str:
        # 先收集所有能匹配当前 api/module/path 的 host_rule。
        matches = self._match_rules(env.host_rules, api_id=api_id, module=module, path=path)
        # 没有任何规则命中时直接报错，避免请求在未知 host 上执行。
        if not matches:
            self._raise(
                reason=f"未匹配到 host_rule: api_id={api_id}, module={module}, path={path}",
                extra={"available_hosts": sorted(env.hosts.keys())},
            )

        # 命中多条规则时按 priority 倒序排序，最高优先级先参与裁决。
        matches.sort(key=lambda item: item[0].priority, reverse=True)
        # 取出最高优先级，后面只比较同优先级的候选规则。
        top_priority = matches[0][0].priority
        # 保留所有最高优先级规则，用于判断是否出现歧义。
        top_matches = [item for item in matches if item[0].priority == top_priority]
        # 同一优先级如果指向多个 host，就无法确定唯一 base_url。
        hosts = {rule.host for rule, _reason in top_matches}

        # 最高优先级下出现多个不同 host 时抛错，让用户调整 priority 或规则。
        if len(hosts) > 1:
            self._raise(
                reason="host_rules 最高优先级匹配到多个不同 host",
                extra={
                    "priority": top_priority,
                    "matches": [
                        {"host": rule.host, "reason": reason}
                        for rule, reason in top_matches
                    ],
                },
            )

        # 最高优先级且唯一的规则就是最终 host 选择结果。
        host_key = top_matches[0][0].host
        # host_rule 只能引用 env.hosts 中已声明的 key，避免拼接空地址。
        if host_key not in env.hosts:
            self._raise(
                reason=f"host_rules 引用的 host 不存在: {host_key}",
                extra={"available_hosts": sorted(env.hosts.keys())},
            )
        # 返回真实 base_url，调用方负责和 path 拼接。
        return env.hosts[host_key]

    def _match_rules(
        self,
        rules: List[HostRule],
        *,
        api_id: str,
        module: str,
        path: str,
    ) -> List[Tuple[HostRule, str]]:
        # matches 同时保存规则和命中原因，方便错误信息解释为什么匹配。
        matches: List[Tuple[HostRule, str]] = []
        # 按 YAML 中的规则逐条判断，单条规则命中后不再继续判断其它条件。
        for rule in rules:
            # api_id 精确匹配优先级最高，适合特殊接口单独路由。
            if api_id in rule.apis:
                matches.append((rule, "apis"))
                continue
            # module 匹配用于同一业务模块统一走同一 host。
            if module and module in rule.modules:
                matches.append((rule, "modules"))
                continue
            # path_prefixes 用于按接口路径前缀匹配后端服务。
            if any(path.startswith(prefix) for prefix in rule.path_prefixes):
                matches.append((rule, "path_prefixes"))
                continue
            # default 是兜底规则，只有没有更高 priority 规则时才会最终生效。
            if rule.default:
                matches.append((rule, "default"))
        # 返回全部候选项，最终优先级裁决放在 resolve_base_url 中完成。
        return matches

    def _raise(self, *, reason: str, extra=None):
        # 统一把 host_rules 问题包装成请求构建异常，便于执行器按请求失败处理。
        error_context = build_api_exception_context(
            error_code=ExceptionCode.REQUEST_BUILD_ERROR,
            message="host_rules 解析失败",
            reason=reason,
            hint="请检查 config.yaml 中当前环境的 hosts 和 host_rules",
            extra=extra or {},
        )
        raise RequestBuildException(error_context)


if __name__ == "__main__":
    from Exceptions.AutoApiException import RequestBuildException
    from Schema.data_models import EnvProfile, HostRule
    from Utils.print_pretty import print_rich

    resolver = HostResolver()

    env = EnvProfile(
        hosts={
            "default_service": "http://default.example.com",
            "user_service": "http://user.example.com",
            "book_service": "http://book.example.com",
            "order_service": "http://order.example.com",
        },
        host_rules=[
            # api_id 精确命中，priority 最高。
            HostRule(
                host="user_service",
                priority=100,
                apis=["api_login", "api_user_profile"],
            ),
            # module 命中。
            HostRule(
                host="book_service",
                priority=50,
                modules=["book"],
            ),
            # path_prefixes 命中。
            HostRule(
                host="order_service",
                priority=30,
                path_prefixes=["/order", "/pay"],
            ),
            # default 兜底。
            HostRule(
                host="default_service",
                priority=0,
                default=True,
            ),
        ],
    )

    cases = [
        {
            "name": "api_id 精确命中",
            "api_id": "api_login",
            "module": "",
            "path": "/anything",
        },
        {
            "name": "module 命中",
            "api_id": "api_unknown",
            "module": "book",
            "path": "/book/detail/1",
        },
        {
            "name": "path_prefixes 命中",
            "api_id": "api_unknown",
            "module": "",
            "path": "/order/create",
        },
        {
            "name": "default 兜底",
            "api_id": "api_unknown",
            "module": "",
            "path": "/other/path",
        },
    ]

    for item in cases:
        base_url = resolver.resolve_base_url(
            env,
            api_id=item["api_id"],
            module=item["module"],
            path=item["path"],
        )
        print_rich(
            {
                "case": item["name"],
                "input": item,
                "base_url": base_url,
            }
        )

    print("\n=== 异常观察: 没有任何 host_rule 命中 ===")
    env_no_default = EnvProfile(
        hosts={
            "user_service": "http://user.example.com",
        },
        host_rules=[
            HostRule(
                host="user_service",
                priority=100,
                apis=["api_login"],
            ),
        ],
    )

    try:
        resolver.resolve_base_url(
            env_no_default,
            api_id="api_unknown",
            module="unknown",
            path="/unknown",
        )
    except RequestBuildException as e:
        print(e)

    print("\n=== 异常观察: 同优先级命中多个不同 host ===")
    env_conflict = EnvProfile(
        hosts={
            "user_service": "http://user.example.com",
            "book_service": "http://book.example.com",
        },
        host_rules=[
            HostRule(
                host="user_service",
                priority=100,
                apis=["api_conflict"],
            ),
            HostRule(
                host="book_service",
                priority=100,
                modules=["book"],
            ),
        ],
    )

    try:
        resolver.resolve_base_url(
            env_conflict,
            api_id="api_conflict",
            module="book",
            path="/book/detail/1",
        )
    except RequestBuildException as e:
        print(e)

    print("\n=== 异常观察: host_rule 引用了不存在的 host key ===")
    env_missing_host = EnvProfile(
        hosts={
            "user_service": "http://user.example.com",
        },
        host_rules=[
            HostRule(
                host="missing_service",
                priority=100,
                apis=["api_missing_host"],
            ),
        ],
    )

    try:
        resolver.resolve_base_url(
            env_missing_host,
            api_id="api_missing_host",
            module="",
            path="/demo",
        )
    except RequestBuildException as e:
        print(e)
