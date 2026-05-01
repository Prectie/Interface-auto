import inspect
import logging
from pathlib import Path

try:
    # 优先使用 nb_log,保持项目原有日志格式和文件输出能力.
    from nb_log import get_logger as _get_logger
except ModuleNotFoundError:
    # 测试或轻量环境未安装 nb_log 时,回退到标准库 logging.
    _get_logger = None


class LoggerManager:
    """封装 nb_log.get_logger, 并自动按调用脚本目录划分日志存放"""
    __logger_map = {}

    @classmethod
    def get_logger(cls,
                   name: str = None,
                   log_level_int: int = 20,
                   is_add_stream_handler: bool = True,
                   formatter_template: int = 5,
                   log_file_handler_type: int = 2) -> logging.Logger:
        """
        功能说明:
            创建或复用一个 nb_log.Logger, 并将日志文件放在项目根 Log / 目录下:
                <name or default>.log
                <name or default>_error.log
        参数说明:
            name: 日志命名空间, 若 None 则取 "default"(最好别都用同一个name)
            ...: 其余参数同 nb_log, 详细说明见 nb_log 源码 get_logger()
        """

        # 1.获取项目根目录路径
        project_root = Path(__file__).resolve().parent.parent

        # 2.日志统一管理
        log_root = project_root / 'Log'
        log_root.mkdir(parents=True, exist_ok=True)

        # 3.日志命名空间与日志名
        logger_name = name or 'default'
        log_filename = f"{logger_name}.log"
        error_log_filename = f"{logger_name}_error.log"

        # 4.缓存 Key, 避免重复初始化
        cache_key = f"{logger_name}"
        if cache_key in cls.__logger_map:
            return cls.__logger_map[cache_key]

        # nb_log 不存在时使用标准库 logging,避免导入阶段直接失败.
        if _get_logger is None:
            # 通过 logger_name 复用 logging 全局 logger,保持和 nb_log 分支一致的命名.
            logger = logging.getLogger(logger_name)
            # 将调用方传入的日志级别同步到标准库 logger.
            logger.setLevel(log_level_int)
            # 只在需要控制台输出且当前 logger 没有 handler 时添加 StreamHandler.
            if is_add_stream_handler and not logger.handlers:
                # 标准库 fallback 只保证控制台可见,不额外模拟 nb_log 文件分流.
                handler = logging.StreamHandler()
                # 使用简洁格式,避免测试输出被 nb_log 专用格式依赖卡住.
                handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s:%(message)s"))
                # 将 handler 挂到 logger 上,后续缓存命中会复用同一个 handler.
                logger.addHandler(handler)
        else:
            # 7.调用nb_log.get_logger, 传入 log_path 和 文件名
            logger = _get_logger(
                name=logger_name,
                log_level_int=log_level_int,
                is_add_stream_handler=is_add_stream_handler,
                log_path=str(log_root),
                log_filename=log_filename,
                error_log_filename=error_log_filename,
                formatter_template=formatter_template,
                log_file_handler_type=log_file_handler_type
            )

        # 8.缓存并返回
        cls.__logger_map[cache_key] = logger
        return logger
