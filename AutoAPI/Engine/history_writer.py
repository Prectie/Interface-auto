from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from Engine.results import RunResult, StepResult


class HistoryWriter:
    """
      将 执行结果追加写入 JSONL 历史文件。
    """

    def __init__(self, history_dir: str | Path = "Reports/history"):
        # 保存历史目录，后续写文件前会自动创建。
        self.history_dir = Path(history_dir)

    def write_run(self, result: RunResult) -> None:
        # 确保历史目录存在。
        self.history_dir.mkdir(parents=True, exist_ok=True)
        # 先写 run 级摘要，再逐条写 step/case 结果。
        self._append_jsonl(self.history_dir / "runs.jsonl", self._run_payload(result))
        for step in result.steps:
            self._append_jsonl(self.history_dir / "results.jsonl", self._step_payload(result, step))

    def _run_payload(self, result: RunResult) -> dict:
        return {
            "run_id": result.run_id,
            "target_type": result.target_type,
            "target_id": result.target_id,
            "env": result.env,
            "status": result.status,
            "started_at": result.started_at,
            "ended_at": result.ended_at,
            "duration_ms": result.duration_ms,
            "passed_count": result.passed_count,
            "failed_count": result.failed_count,
            "error_count": result.error_count,
        }

    def _step_payload(self, result: RunResult, step: StepResult) -> dict:
        request = step.request.to_dict() if step.request else {}
        response = step.response.to_dict() if step.response else {}
        error = step.error
        error_context = getattr(error, "error_context", None)
        return {
            "run_id": result.run_id,
            "plan_id": result.target_id if result.target_type == "plan" else None,
            "scenario_id": step.scenario_id,
            "case_id": step.case_id,
            "api_id": step.api_id,
            "step_id": step.step_id,
            "dataset_name": step.dataset_name,
            "dataset_index": step.dataset_index,
            "status": step.status,
            "method": request.get("method"),
            "url": request.get("url"),
            "status_code": response.get("status_code"),
            "duration_ms": step.duration_ms,
            "context_snapshot": step.context_snapshot,
            "error_code": getattr(getattr(error_context, "error_code", None), "value", None),
            "error_message": str(error) if error else None,
        }

    def _append_jsonl(self, path: Path, payload: dict) -> None:
        # 每一行是一条 JSON，便于后续追加和流式读取。
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, ensure_ascii=False, default=str))
            file.write("\n")
