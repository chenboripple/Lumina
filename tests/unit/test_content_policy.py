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
from lumina.executor import Executor, NoteOutput


class TestContentPolicy(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_home = os.environ.get("HOME")
        os.environ["HOME"] = self.temp_dir.name

        loaded_lumina = sys.modules.get("lumina")
        if loaded_lumina is not None and not hasattr(loaded_lumina, "__path__"):
            del sys.modules["lumina"]

        self.content_filter = ContentFilter()

    def tearDown(self):
        if self.original_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self.original_home
        self.temp_dir.cleanup()

    def test_filters_low_knowledge_density_reference_list(self):
        content = """员工号|手机号|订单号
100001|13800000000|PO202401010001
100002|13900000000|PO202401010002
100003|13700000000|PO202401010003
100004|13600000000|PO202401010004
"""

        result = self.content_filter.check(Path("employee_id_list.txt"), content)

        self.assertFalse(result.should_process)
        self.assertEqual(result.metadata["filter_type"], "low_knowledge_density")
        self.assertTrue(result.metadata["low_knowledge_density"])

    def test_downgrades_fact_heavy_content_without_overfiltering(self):
        content = """# 企业采购订单同步规则
本文说明订单同步接口的规则、约束、字段映射、异常处理和校验逻辑。

## 处理逻辑
- 当订单状态为已支付时，系统根据接口规则更新结算流程。
- 如果金额字段为空，触发校验策略并记录异常原因。
- 设计目标是沉淀可复用的流程和治理策略，而不是保留单笔样本。

## 示例记录
- 订单号: PO202401010001, 员工号: E102938, 手机号: 13812345678, 金额: 2580元
- 订单号: PO202401010002, 员工号: E102939, 邮箱: buyer@example.com, 金额: 3100元
"""

        result = self.content_filter.check(Path("purchase_rule.md"), content)
        sanitized, transform_meta = self.content_filter.sanitize_content(content, result.metadata)
        guidance = self.content_filter.build_processing_guidance(result.metadata)

        self.assertTrue(result.should_process)
        self.assertTrue(result.metadata["downgrade_sample_facts"])
        self.assertTrue(result.metadata["mask_sensitive"])
        self.assertIn("reusable rules", guidance)
        self.assertIn("样本事实已折叠", sanitized)
        self.assertEqual(transform_meta["collapsed_fact_lines"], 2)

    def test_masks_sensitive_fields_generically(self):
        text = """订单号: PO202401010001
邮箱: buyer@example.com
手机号: 13812345678
Statement ID=ABC123456789
"""

        masked = self.content_filter.mask_sensitive_text(text)

        self.assertNotIn("buyer@example.com", masked)
        self.assertNotIn("13812345678", masked)
        self.assertNotIn("PO202401010001", masked)
        self.assertNotIn("ABC123456789", masked)
        self.assertGreaterEqual(masked.count("[REDACTED]"), 3)
        self.assertIn("[REDACTED]", masked)

    def test_executor_applies_output_content_policy(self):
        executor = Executor.__new__(Executor)
        executor.content_filter = self.content_filter

        note = NoteOutput(
            title="订单 PO202401010001",
            content="联系人: 张三\n邮箱: buyer@example.com\n手机号: 13812345678",
            tags=["order-PO202401010001"],
            links=["mailto:buyer@example.com", "PO202401010001"],
            source="demo",
            metadata={},
        )

        updated = executor._apply_content_policy(
            note,
            {"mask_sensitive": True, "downgrade_sample_facts": False},
        )

        self.assertNotIn("buyer@example.com", updated.content)
        self.assertNotIn("13812345678", updated.content)
        self.assertNotIn("PO202401010001", updated.title)
        self.assertTrue(all("buyer@example.com" not in link for link in updated.links))
        self.assertTrue(updated.metadata["content_policy"]["mask_sensitive"])
        self.assertTrue(updated.metadata["content_policy"]["masked_sensitive"])


if __name__ == "__main__":
    unittest.main()