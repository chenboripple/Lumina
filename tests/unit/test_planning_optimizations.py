import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) in sys.path:
    sys.path.remove(str(ROOT_DIR))

loaded_lumina = sys.modules.get("lumina")
if loaded_lumina is not None and not hasattr(loaded_lumina, "__path__"):
    del sys.modules["lumina"]

from lumina.content_filter import ContentFilter
from lumina.document_cluster import ClusterStrategy, DocumentClusterer
from lumina.executor import Executor
from lumina.planner import Planner


class TestPlanningOptimizations(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_dir.name

    def tearDown(self):
        if self.original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.original_home
        self.temp_dir.cleanup()

    def test_unreadable_pdf_is_filtered(self):
        content_filter = ContentFilter()
        content = "[PDF appears to be scanned/image-based. Text extraction limited. Consider using OCR.]\n� � � � �\n"

        result = content_filter.check(Path("invoice.pdf"), content)

        self.assertFalse(result.should_process)
        self.assertEqual(result.metadata["filter_type"], "unreadable_pdf")

    def test_sql_log_is_filtered(self):
        content_filter = ContentFilter()
        content = """update exp_claim_line set city_type = 'C' where id = 1;
update exp_claim_line set city_type = 'C' where id = 2;
update exp_claim_line set city_type = 'C' where id = 3;
update exp_claim_line set city_type = 'C' where id = 4;
commit;
"""

        result = content_filter.check(Path("exp_claim_line_updates.sql"), content)

        self.assertFalse(result.should_process)
        self.assertEqual(result.metadata["filter_type"], "low_knowledge_density")

    def test_project_directory_becomes_summary_cluster(self):
        project_dir = Path(self.temp_dir.name) / "HeliProto"
        project_dir.mkdir(parents=True, exist_ok=True)
        files = []
        for idx, suffix in enumerate([".ts", ".tsx", ".js", ".json", ".md", ".yaml"]):
            file_path = project_dir / f"module_{idx}{suffix}"
            file_path.write_text(f"content {idx}", encoding="utf-8")
            files.append(file_path)

        clusterer = DocumentClusterer()
        clusters, remaining = clusterer.cluster(files)

        self.assertTrue(any(cluster.metadata.get("overview_scope") == "project" for cluster in clusters))
        self.assertEqual(remaining, [])
        self.assertTrue(any(cluster.strategy == ClusterStrategy.SUMMARIZE_MULTIPLE for cluster in clusters))

    def test_planner_adds_global_overview_cluster(self):
        scan_dir = Path(self.temp_dir.name) / "scan"
        scan_dir.mkdir(parents=True, exist_ok=True)
        for idx in range(8):
            (scan_dir / f"doc_{idx}.md").write_text(f"# 标题 {idx}\n\n这是第 {idx} 份工作需求文档。", encoding="utf-8")

        planner = Planner(enable_clustering=False)
        files = planner.scan(str(scan_dir))
        plan = planner.plan(files)

        self.assertTrue(any(batch_file.metadata.get("overview_scope") == "global" for batch in plan.batches for batch_file in batch))

    def test_executor_prefers_clear_title_hint(self):
        executor = Executor.__new__(Executor)

        resolved = executor._resolve_note_title(
            "Collection: 202307",
            file_info=type("FileInfoStub", (), {"path": Path("Collection_202307.md"), "metadata": {"title_hint": "订单数据解析"}})(),
            parsed_data={"summary": "总结订单字段及处理规则。"},
        )

        self.assertEqual(resolved, "订单数据解析")


if __name__ == "__main__":
    unittest.main()