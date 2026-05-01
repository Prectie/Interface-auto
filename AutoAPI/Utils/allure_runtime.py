from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class AllureArtifacts:
    # results_dir 保存一次执行生成的 allure-results 目录.
    results_dir: Path
    # report_dir 保存同一 run_id 对应的 HTML 报告目录.
    report_dir: Path
    # html_generated 标识本次是否成功生成 HTML 报告.
    html_generated: bool
    # warning 保存非致命告警,例如 allure CLI 缺失.
    warning: Optional[str] = None


class AllureRuntimeReporter:
    """
      Allure HTML 报告生成器 (Phase B 后已不再生成 *-result.json):

      Phase B 切换到 allure-pytest 之后, 测试用例的 *-result.json 由 allure-pytest 在
      pytest 运行期内自动写入 alluredir, 本类只负责:
        1. 把已存在的 alluredir (allure-results) 转换为 HTML (调 ``allure generate``);
        2. 提供给 plugin / run.py 的 ``generate_html_for_run`` 一站式入口, 默认按
           ``<reports_root>/allure-results/<run_id>`` 与
           ``<reports_root>/allure-report/<run_id>`` 推导路径, 维持 v0.1 stdout 字面;
        3. 没有 allure CLI 时只返回 warning, 不抛异常, 不阻断主链路.

      已经废弃的 v0.1 API (依赖 ``allure_commons._core / lifecycle / logger / model2``):
        - export_run / write_results / _attach_json / _attach_text /
          _build_test_name / _build_step_name / _map_status /
          _build_status_details / _build_traceback_text / _to_epoch_ms
      它们在 Phase B 整体废弃, 由 ``pytest_autoapi`` 插件 + ``allure-pytest`` 替代.
    """

    def __init__(self, reports_root: str | Path = "Reports"):
        # 统一约定所有 Allure 产物都写在 Reports 目录下.
        self.reports_root = Path(reports_root)

    def generate_html_for_run(
        self,
        run_id: str,
        *,
        results_dir: Optional[Path] = None,
        report_dir: Optional[Path] = None,
    ) -> AllureArtifacts:
        """
          按 run_id 生成 HTML 报告的高层入口:

          - results_dir 缺省时回退到 ``self.reports_root/allure-results/<run_id>``;
          - report_dir 缺省时回退到 ``self.reports_root/allure-report/<run_id>``;
          - results_dir 不存在时, 直接返回 html_generated=False + warning, 不抛错;
          - 调用 ``generate_html_report`` 真正驱动 ``allure`` CLI;
          - 返回 AllureArtifacts, 字段含义与 v0.1 保持一致, 让 run.py 的
            stdout (allure_results / allure_report / allure_warning) 三行字面不变.
        """
        results_dir_path = Path(results_dir) if results_dir else self.reports_root / "allure-results" / run_id
        report_dir_path = Path(report_dir) if report_dir else self.reports_root / "allure-report" / run_id

        if not results_dir_path.exists():
            return AllureArtifacts(
                results_dir=results_dir_path,
                report_dir=report_dir_path,
                html_generated=False,
                warning=f"allure-results 目录不存在: {results_dir_path.as_posix()}",
            )

        html_generated, warning = self.generate_html_report(results_dir_path, report_dir_path)
        return AllureArtifacts(
            results_dir=results_dir_path,
            report_dir=report_dir_path,
            html_generated=html_generated,
            warning=warning,
        )

    def generate_html_report(self, results_dir: Path, report_dir: Path) -> tuple[bool, Optional[str]]:
        # 没有 allure CLI 时只返回 warning,不抛异常.
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
