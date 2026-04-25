from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import traceback
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from allure_commons._core import plugin_manager
from allure_commons.lifecycle import AllureLifecycle
from allure_commons.logger import AllureFileLogger
from allure_commons.model2 import Label, Parameter, Status, StatusDetails
from allure_commons.types import AttachmentType

from Engine.results import P0RunResult, P0StepResult
from Utils.allure_reporter import AllureReporter


@dataclass
class AllureArtifacts:
    # results_dir 保存一次执行生成的 allure-results 目录。
    results_dir: Path
    # report_dir 保存同一 run_id 对应的 HTML 报告目录。
    report_dir: Path
    # html_generated 标识本次是否成功生成 HTML 报告。
    html_generated: bool
    # warning 保存非致命告警，例如 allure CLI 缺失。
    warning: Optional[str] = None


class AllureRuntimeReporter:
    """
      负责把 P0 CLI 执行结果写成 allure-results，并尝试生成 HTML 报告。
    """

    def __init__(self, reports_root: str | Path = "Reports"):
        # 统一约定所有 Allure 产物都写在 Reports 目录下。
        self.reports_root = Path(reports_root)

    def export_run(self, result: P0RunResult) -> AllureArtifacts:
        # 每次 run 使用独立 run_id 目录，避免不同执行相互覆盖。
        results_dir = self.reports_root / "allure-results" / result.run_id
        report_dir = self.reports_root / "allure-report" / result.run_id

        # 先写原始 allure-results，再尝试生成 HTML。
        self.write_results(result, results_dir)
        html_generated, warning = self.generate_html_report(results_dir, report_dir)
        return AllureArtifacts(
            results_dir=results_dir,
            report_dir=report_dir,
            html_generated=html_generated,
            warning=warning,
        )

    def write_results(self, result: P0RunResult, results_dir: Path) -> None:
        # clean=True 保证同一 run_id 重试时不会残留旧结果。
        file_logger = AllureFileLogger(results_dir, clean=True)
        plugin_manager.register(file_logger, name=f"autoapi-allure-{result.run_id}")
        try:
            lifecycle = AllureLifecycle()
            test_uuid = f"run-{result.run_id}"
            started_ms = self._to_epoch_ms(result.started_at)
            step_cursor = started_ms

            with lifecycle.schedule_test_case(uuid=test_uuid) as test_result:
                # 统一写当前 run 对应的单个 Allure test case 元数据。
                test_result.name = self._build_test_name(result)
                test_result.fullName = f"AutoAPI.{result.target_type}.{result.target_id}"
                test_result.testCaseId = result.target_id
                test_result.historyId = hashlib.md5(
                    f"{result.target_type}:{result.target_id}".encode("utf-8")
                ).hexdigest()
                test_result.stage = "finished"
                test_result.status = self._map_status(result.status)
                test_result.statusDetails = self._build_status_details(result.error)
                test_result.start = started_ms
                test_result.stop = self._to_epoch_ms(result.ended_at)
                test_result.labels = [
                    Label(name="parentSuite", value="AutoAPI"),
                    Label(name="suite", value=result.target_type),
                    Label(name="subSuite", value=result.target_id),
                ]
                test_result.parameters = [
                    Parameter(name="run_id", value=result.run_id),
                    Parameter(name="target_type", value=result.target_type),
                    Parameter(name="target_id", value=result.target_id),
                    Parameter(name="env", value=result.env),
                ]

                # 先挂 run 级摘要，方便从报告首页直接看总结果。
                self._attach_json(
                    lifecycle,
                    parent_uuid=test_uuid,
                    name="P0 run 执行结果",
                    payload=result.to_dict(),
                )

                for index, step in enumerate(result.steps, start=1):
                    step_uuid = f"{test_uuid}-step-{index}"
                    with lifecycle.start_step(parent_uuid=test_uuid, uuid=step_uuid) as allure_step:
                        step_start = step_cursor
                        duration_ms = int(round(step.duration_ms or 0))
                        duration_ms = max(duration_ms, 1)
                        step_cursor += duration_ms

                        # 单个 step 的标题优先使用场景 step_id，其次回退到 case_id。
                        allure_step.name = self._build_step_name(step, index)
                        allure_step.status = self._map_status(step.status)
                        allure_step.statusDetails = self._build_status_details(step.error)
                        allure_step.stage = "finished"
                        allure_step.start = step_start
                        allure_step.stop = step_cursor

                        self._attach_json(
                            lifecycle,
                            parent_uuid=step_uuid,
                            name="请求快照",
                            payload=step.request.to_dict() if step.request else None,
                        )
                        self._attach_json(
                            lifecycle,
                            parent_uuid=step_uuid,
                            name="响应快照",
                            payload=step.response.to_dict() if step.response else None,
                        )
                        self._attach_json(
                            lifecycle,
                            parent_uuid=step_uuid,
                            name="提取结果",
                            payload=step.extract_out,
                        )
                        self._attach_json(
                            lifecycle,
                            parent_uuid=step_uuid,
                            name="断言结果",
                            payload=[item.to_dict() for item in step.assertions],
                        )
                        self._attach_json(
                            lifecycle,
                            parent_uuid=step_uuid,
                            name="上下文快照",
                            payload=step.context_snapshot,
                        )
                        if step.error is not None:
                            self._attach_text(
                                lifecycle,
                                parent_uuid=step_uuid,
                                name="异常摘要",
                                body=str(step.error),
                            )
                            self._attach_text(
                                lifecycle,
                                parent_uuid=step_uuid,
                                name="异常栈",
                                body=self._build_traceback_text(step.error),
                            )
                    lifecycle.stop_step(uuid=step_uuid)

            lifecycle.write_test_case(uuid=test_uuid)
            # 写环境信息和缺陷分类，保持与 PRD 一致。
            AllureReporter.write_environment_file(
                results_dir,
                {
                    "run_id": result.run_id,
                    "target_type": result.target_type,
                    "target_id": result.target_id,
                    "env": result.env,
                },
            )
            AllureReporter.write_categories_file(results_dir)
        finally:
            # 避免 logger 常驻到全局 plugin_manager，污染后续用例或下一次 CLI 执行。
            plugin_manager.unregister(plugin=file_logger)

    def generate_html_report(self, results_dir: Path, report_dir: Path) -> tuple[bool, Optional[str]]:
        # 没有 allure CLI 时只返回 warning，不抛异常。
        allure_bin = shutil.which("allure")
        if not allure_bin:
            return False, "allure CLI 未安装，已跳过 HTML 报告生成"

        completed = subprocess.run(
            [allure_bin, "generate", str(results_dir), "-o", str(report_dir), "--clean"],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
            return False, f"allure HTML 生成失败: {stderr}"
        return True, None

    def _attach_json(self, lifecycle: AllureLifecycle, *, parent_uuid: str, name: str, payload) -> None:
        # 空数据不挂附件，避免报告充斥无意义节点。
        if payload is None:
            return
        body = json.dumps(payload, ensure_ascii=False, indent=2, default=str)
        lifecycle.attach_data(
            uuid=uuid.uuid4().hex,
            body=body,
            name=name,
            attachment_type=AttachmentType.JSON,
            parent_uuid=parent_uuid,
        )

    def _attach_text(self, lifecycle: AllureLifecycle, *, parent_uuid: str, name: str, body: str) -> None:
        lifecycle.attach_data(
            uuid=uuid.uuid4().hex,
            body=body,
            name=name,
            attachment_type=AttachmentType.TEXT,
            parent_uuid=parent_uuid,
        )

    def _build_test_name(self, result: P0RunResult) -> str:
        return f"{result.target_type} | {result.target_id}"

    def _build_step_name(self, step: P0StepResult, index: int) -> str:
        # 让 Allure 中的 step 标题先显示场景 step_id，缺失时退化到 case_id。
        title = step.step_id or step.case_id
        return f"{index:02d}. {title}"

    def _map_status(self, status: str) -> str:
        status_map = {
            "passed": Status.PASSED,
            "failed": Status.FAILED,
            "error": Status.BROKEN,
        }
        return status_map.get(status, Status.UNKNOWN)

    def _build_status_details(self, error: Optional[BaseException]) -> Optional[StatusDetails]:
        if error is None:
            return None
        return StatusDetails(
            message=str(error),
            trace=self._build_traceback_text(error),
        )

    def _build_traceback_text(self, error: BaseException) -> str:
        return "".join(traceback.format_exception(type(error), error, error.__traceback__))

    def _to_epoch_ms(self, text: str) -> int:
        # 统一把 ISO 时间转换成 Allure 需要的毫秒时间戳。
        return int(datetime.fromisoformat(text).timestamp() * 1000)
