"""回答正文归一化的单元测试：平台残留文案与表格行处理。"""

import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_report_data.py"
spec = importlib.util.spec_from_file_location("build_report_data", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
sys.modules["build_report_data"] = MODULE
spec.loader.exec_module(MODULE)


class TestPlatformNoise(unittest.TestCase):
    def test_anchor_artefact_is_dropped_without_gluing_names(self):
        raw = f"AquaTru Carafe{MODULE.PRODUCT_VIEWER_NOISE}is a good pick"
        out = MODULE.normalize_answer_html(raw)
        self.assertNotIn(MODULE.PRODUCT_VIEWER_NOISE, out)
        # 必须断开而不是直接删除，否则两个词会粘成一个
        self.assertIn("Carafe", out)
        self.assertNotIn("Carafeis", out)

    def test_shared_constant_matches_lexicon_miner(self):
        spec2 = importlib.util.spec_from_file_location(
            "mine_brand_lexicon", SCRIPT.parent / "mine_brand_lexicon.py")
        mod2 = importlib.util.module_from_spec(spec2)
        sys.modules["mine_brand_lexicon"] = mod2
        spec2.loader.exec_module(mod2)
        self.assertEqual(MODULE.PRODUCT_VIEWER_NOISE, mod2.PRODUCT_VIEWER_NOISE)


class TestTableRowHandling(unittest.TestCase):
    def test_br_inside_table_row_becomes_separator_not_newline(self):
        raw = "| a | b<br>c |\n| d | e |"
        out = MODULE.normalize_answer_html(raw)
        self.assertIn("b / c", out)
        self.assertNotIn("b\nc", out)

    def test_br_outside_table_still_breaks_line(self):
        out = MODULE.normalize_answer_html("line one<br>line two")
        self.assertIn("\n", out)


if __name__ == "__main__":
    unittest.main()
