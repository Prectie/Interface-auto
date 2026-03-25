1）executor.py 顶部 import 补 Set
放置上下文

找到这行：

from typing import Optional, Any, Dict, List

替换成：

from typing import Optional, Any, Dict, List, Set
2）在 Executor 类中新增“预检辅助方法”
放置上下文

把下面这组方法，加在 _build_suite_ctx() 后面，_run_auth_profile() 前面。
也就是放在执行主链方法前面，作为统一的预检辅助工具。

    def _collect_step_ref_api_ids(self, steps: Optional[List[Dict[str, Any]]]) -> List[str]:
        """
          从步骤列表中提取实际会执行的 ref api_id 列表

          规则:
            1. 仅收集 is_run 不为 False 的步骤
            2. 自动去重, 保留首次出现顺序
            3. 忽略空 ref
        :param steps: 步骤列表
        :return: 当前步骤列表中实际会触达的 ref api_id 列表
        """
        # 初始化结果列表, 用于按顺序收集 ref api_id
        ref_api_ids: List[str] = []
        # 初始化去重集合, 避免同一个 ref 重复收集
        exist_ref_api_ids: Set[str] = set()

        # 若步骤列表为空, 直接返回空列表
        if not steps:
            return ref_api_ids

        # 逐个遍历步骤项
        for step in steps:
            # 读取步骤开关, 不写默认执行
            is_run = step.get("is_run", True)
            # 若当前步骤显式关闭, 则直接跳过
            if not is_run:
                continue

            # 读取当前步骤引用的接口 id
            ref_api_id = str(step.get("ref", "")).strip()
            # 若 ref 为空, 则直接跳过
            if not ref_api_id:
                continue

            # 若当前 ref 尚未收集过, 则写入结果列表
            if ref_api_id not in exist_ref_api_ids:
                # 写入去重集合
                exist_ref_api_ids.add(ref_api_id)
                # 写入结果列表
                ref_api_ids.append(ref_api_id)

        # 返回当前步骤列表中实际会触达的 ref api_id 列表
        return ref_api_ids

    def _get_profile_steps_for_precheck(self, profile_name: str, yaml_location: str) -> List[Dict[str, Any]]:
        """
          读取公共依赖包步骤列表, 供执行前预检使用
        :param profile_name: 公共依赖包名称
        :param yaml_location: 当前触发读取动作的 YAML 定位路径
        :return: 当前公共依赖包对应的步骤列表
        """
        # 读取全部公共依赖包映射, 若不存在则按空 dict 处理
        profiles = self.repo.config.auth_profiles or {}
        # 若当前 profile 不存在, 直接抛统一异常
        if profile_name not in profiles:
            # 构建统一异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.VALIDATION_ERROR,  # 指定异常码为结构校验异常
                message="公共依赖包不存在",  # 指定异常主消息
                reason=f"auth_profile {profile_name!r} 不存在",  # 记录具体失败原因
                yaml_location=yaml_location,  # 标记触发该问题的 YAML 路径
                hint="请检查 config.yaml.auth_profiles 中是否已定义该公共依赖包",  # 给出修复建议
            )
            # 抛出结构校验异常
            raise ValidationException(error_context)

        # 读取当前公共依赖包对应的步骤列表
        profile_steps = profiles.get(profile_name) or []
        # 若步骤列表结构非法, 直接抛统一异常
        if not isinstance(profile_steps, list):
            # 构建统一异常上下文
            error_context = build_api_exception_context(
                error_code=ExceptionCode.VALIDATION_ERROR,  # 指定异常码为结构校验异常
                message="公共依赖包结构非法",  # 指定异常主消息
                reason=f"auth_profile {profile_name!r} 必须是步骤列表",  # 记录具体失败原因
                yaml_location=yaml_location,  # 标记当前 YAML 定位路径
                hint="请检查 config.yaml.auth_profiles.<name> 的结构是否为 list[step]",  # 给出修复建议
            )
            # 抛出结构校验异常
            raise ValidationException(error_context)

        # 返回当前公共依赖包步骤列表
        return profile_steps

    def _collect_api_child_refs_for_precheck(self, api: ApiItem) -> List[str]:
        """
          收集单个接口在执行展开图中的直接子节点

          当前规则:
            1. 先收集当前接口 auth_profile 展开的 ref 接口
            2. 再收集当前接口 depends_on 中的 ref 接口
            3. cleanup 不放在这里展开, cleanup 作为执行入口额外根节点处理
        :param api: 当前接口模板对象
        :return: 当前接口直接可达的子接口 id 列表
        """
        # 初始化当前接口直接子节点列表
        child_api_ids: List[str] = []
        # 初始化去重集合, 保证结果列表不重复
        exist_child_api_ids: Set[str] = set()

        # 若当前接口声明了公共依赖包, 则先收集该公共依赖包中的 ref 接口
        if api.auth_profile:
            # 读取当前接口声明的公共依赖包步骤列表
            profile_steps = self._get_profile_steps_for_precheck(
                profile_name=api.auth_profile,  # 传入公共依赖包名称
                yaml_location=f"single.yaml.apis.{api.api_id}.auth_profile"  # 标记当前 YAML 定位路径
            )
            # 从公共依赖包步骤列表中提取实际会执行的 ref api_id
            for ref_api_id in self._collect_step_ref_api_ids(profile_steps):
                # 若当前 ref api_id 尚未记录, 则写入结果
                if ref_api_id not in exist_child_api_ids:
                    # 写入去重集合
                    exist_child_api_ids.add(ref_api_id)
                    # 写入结果列表
                    child_api_ids.append(ref_api_id)

        # 再收集当前接口 depends_on 中的 ref 接口
        for ref_api_id in self._collect_step_ref_api_ids(api.depends_on):
            # 若当前 ref api_id 尚未记录, 则写入结果
            if ref_api_id not in exist_child_api_ids:
                # 写入去重集合
                exist_child_api_ids.add(ref_api_id)
                # 写入结果列表
                child_api_ids.append(ref_api_id)

        # 返回当前接口的直接子节点列表
        return child_api_ids

    def _precheck_cycle_from_roots(self, root_api_ids: List[str], yaml_location: str) -> None:
        """
          对当前可达子图执行环预检

          当前策略:
            1. 不是全库扫描, 只检查本次实际会触达的根节点展开图
            2. 检查范围同时覆盖 auth_profile 展开的 ref 与 depends_on 展开的 ref
            3. 使用 DFS + visiting/path 检测环, 并输出完整环路
        :param root_api_ids: 当前执行入口会触达的根接口 id 列表
        :param yaml_location: 当前执行入口对应的 YAML 定位路径
        :return: 无
        """
        # 初始化已完成集合, 用于剪枝, 避免重复遍历已确认无环的子图
        visited: Set[str] = set()
        # 初始化访问中集合, 用于检测当前 DFS 路径上的回边
        visiting: Set[str] = set()
        # 初始化当前 DFS 路径列表, 用于构建完整环路文本
        path: List[str] = []

        def dfs(current_api_id: str) -> None:
            """
              深度优先遍历当前接口的可达子图, 并检测是否存在环
            :param current_api_id: 当前正在遍历的接口 id
            :return: 无
            """
            # 若当前节点已在访问中集合内, 说明检测到环
            if current_api_id in visiting:
                # 计算当前环在路径列表中的起始下标
                cycle_start_index = path.index(current_api_id)
                # 截取完整环路, 并把当前节点再补到末尾, 形成闭环展示
                cycle_path = path[cycle_start_index:] + [current_api_id]
                # 构建统一异常上下文
                error_context = build_api_exception_context(
                    error_code=ExceptionCode.PIPELINE_ERROR,  # 指定异常码为执行管线异常
                    message="执行前依赖图预检失败",  # 指定异常主消息
                    reason=f"检测到循环依赖: {' -> '.join(cycle_path)}",  # 输出完整环路
                    yaml_location=yaml_location,  # 标记触发预检的位置
                    hint="请检查 auth_profile 与 depends_on 的互相引用关系, 消除环依赖后再执行",  # 给出修复建议
                )
                # 抛出统一管线异常
                raise PipelineException(error_context)

            # 若当前节点已完成遍历, 直接返回
            if current_api_id in visited:
                return

            # 将当前节点加入访问中集合
            visiting.add(current_api_id)
            # 将当前节点加入当前 DFS 路径
            path.append(current_api_id)

            # 读取当前接口模板对象
            current_api = self.repo.get_api(current_api_id)
            # 收集当前接口直接可达的子节点列表
            child_api_ids = self._collect_api_child_refs_for_precheck(current_api)

            # 逐个递归遍历当前接口的子节点
            for child_api_id in child_api_ids:
                # 深度优先递归进入子节点
                dfs(child_api_id)

            # 当前节点子图遍历完成后, 从路径尾部弹出当前节点
            path.pop()
            # 从访问中集合中移除当前节点
            visiting.remove(current_api_id)
            # 将当前节点加入已完成集合
            visited.add(current_api_id)

        # 逐个从根节点开始遍历当前可达子图
        for root_api_id in root_api_ids:
            # 忽略空根节点
            if not root_api_id:
                continue
            # 对当前根节点执行 DFS 环检测
            dfs(root_api_id)

    def _precheck_single_reachable_subgraph(self, api: ApiItem) -> None:
        """
          对单接口独立执行场景做执行前环预检
        :param api: 当前单接口模板对象
        :return: 无
        """
        # 初始化当前 single 执行入口根节点列表
        root_api_ids: List[str] = [api.api_id]

        # 若当前接口定义了 cleanup, 则把 cleanup.steps 里的 ref 也纳入当前可达子图根节点
        if api.cleanup:
            # 收集 cleanup.steps 中实际会执行的 ref 接口
            cleanup_root_api_ids = self._collect_step_ref_api_ids(api.cleanup.get("steps", []))
            # 逐个追加到根节点列表中
            for cleanup_root_api_id in cleanup_root_api_ids:
                # 若该根节点尚未出现, 则写入
                if cleanup_root_api_id not in root_api_ids:
                    root_api_ids.append(cleanup_root_api_id)

        # 对当前 single 实际可达子图执行环预检
        self._precheck_cycle_from_roots(
            root_api_ids=root_api_ids,  # 传入当前 single 的根节点列表
            yaml_location=f"single.yaml.apis.{api.api_id}"  # 标记当前 single 定位路径
        )

    def _precheck_flow_reachable_subgraph(self, flow) -> None:
        """
          对业务流执行场景做执行前环预检
        :param flow: 当前业务流对象
        :return: 无
        """
        # 初始化 flow 执行入口根节点列表
        root_api_ids: List[str] = []

        # 若当前 flow 声明了 flow 级公共依赖包, 则把该公共依赖包展开出的 ref 接口纳入根节点
        if flow.auth_profile:
            # 读取 flow.auth_profile 对应的步骤列表
            profile_steps = self._get_profile_steps_for_precheck(
                profile_name=flow.auth_profile,  # 传入 flow 声明的公共依赖包名称
                yaml_location=f"{flow.source or flow.flow_id}.auth_profile"  # 标记当前 flow.auth_profile 定位路径
            )
            # 收集 flow 级公共依赖包中实际会执行的 ref 接口
            for ref_api_id in self._collect_step_ref_api_ids(profile_steps):
                # 若根节点列表中尚未记录该接口, 则写入
                if ref_api_id not in root_api_ids:
                    root_api_ids.append(ref_api_id)

        # 收集 flow 主步骤中实际会执行的 ref 接口
        for step in flow.steps:
            # 读取当前步骤开关, 不写默认执行
            is_run = step.get("is_run", True)
            # 若当前步骤显式关闭, 则跳过
            if not is_run:
                continue

            # 读取当前步骤引用的接口 id
            ref_api_id = str(step.get("ref", "")).strip()
            # 若 ref 为空, 则跳过
            if not ref_api_id:
                continue

            # 若当前接口尚未写入根节点列表, 则追加
            if ref_api_id not in root_api_ids:
                root_api_ids.append(ref_api_id)

        # 若当前 flow 定义了 finally cleanup, 则把 cleanup.steps 中实际会执行的 ref 接口也纳入根节点
        if flow.cleanup:
            # 收集 flow.cleanup.steps 中实际会执行的 ref 接口
            cleanup_root_api_ids = self._collect_step_ref_api_ids(flow.cleanup.get("steps", []))
            # 逐个追加到根节点列表中
            for cleanup_root_api_id in cleanup_root_api_ids:
                # 若该根节点尚未出现, 则写入
                if cleanup_root_api_id not in root_api_ids:
                    root_api_ids.append(cleanup_root_api_id)

        # 对当前 flow 实际可达子图执行环预检
        self._precheck_cycle_from_roots(
            root_api_ids=root_api_ids,  # 传入当前 flow 根节点列表
            yaml_location=flow.source or flow.flow_id  # 标记当前 flow 定位路径
        )
3）在 run_single() 开头插入预检调用
放置上下文

在 run_single() 里，找到这段：

        # 根据接口id获取接口模板
        api = self.repo.get_api(api_id)
        # 根据执行器和single中is_run判断当前单接口当前是否允许运行
        should_run = self.repo.should_run_single_api(api_id=api_id)

改成：

        # 根据接口id获取接口模板
        api = self.repo.get_api(api_id)
        # 根据执行器和single中is_run判断当前单接口当前是否允许运行
        should_run = self.repo.should_run_single_api(api_id=api_id)
        # 若当前单接口需要执行, 则先对当前可达子图做执行前环预检
        if should_run:
            self._precheck_single_reachable_subgraph(api)
4）在 run_flow() 开头插入预检调用
放置上下文

在 run_flow() 里，找到这段：

        # 获取当前flow
        flow = self.repo.get_flow(flow_id)
        # 初始化结果对象, 只关注当前业务流结果
        result = FlowResult(flow_id=flow.flow_id, is_run=bool(flow.is_run))

在它下面、if not flow.is_run: 之前，插入：

        # 若当前 flow 允许运行, 则先对当前可达子图做执行前环预检
        if flow.is_run:
            self._precheck_flow_reachable_subgraph(flow)

最终应变成这样：

        # 获取当前flow
        flow = self.repo.get_flow(flow_id)
        # 初始化结果对象, 只关注当前业务流结果
        result = FlowResult(flow_id=flow.flow_id, is_run=bool(flow.is_run))
        # 若当前 flow 允许运行, 则先对当前可达子图做执行前环预检
        if flow.is_run:
            self._precheck_flow_reachable_subgraph(flow)
        # 判断当前flow中is_run值
        if not flow.is_run:
            return result
这一步改完后的效果

现在真正的执行顺序会变成：

run_single(api_id)

先加载接口模板

先检查当前 single 可达子图是否有环

没环才开始真正执行

运行时仍保留 _run_depends_on() 的 visiting_api_chain 作为兜底

run_flow(flow_id)

先加载 flow

先检查当前 flow 可达子图是否有环

没环才开始真正执行

运行时仍保留递归环检测作为兜底

当前预检已经覆盖的范围

这版代码已经覆盖了你前面拍板的范围：

depends_on

auth_profile 展开的 ref 接口

single.api.cleanup.steps

flow.cleanup.steps

也就是检查的是当前执行入口真正会触达的完整执行展开图，不是只盯着主流程