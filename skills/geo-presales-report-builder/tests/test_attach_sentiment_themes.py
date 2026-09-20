"""attach_sentiment 的主题词表与主题矩阵行为的单元测试。"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "attach_sentiment.py"
spec = importlib.util.spec_from_file_location("attach_sentiment", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
sys.modules["attach_sentiment"] = MODULE
spec.loader.exec_module(MODULE)


class TestThemeKeywords(unittest.TestCase):
    def test_default_is_water_purifier_lexicon(self):
        keywords = MODULE.load_theme_keywords(None)
        self.assertIn("安装与部署", keywords)
        self.assertEqual(list(MODULE.THEME_KEYWORDS), list(keywords))

    def test_custom_lexicon_overrides(self):
        tmp = Path(tempfile.mkdtemp()) / "themes.json"
        tmp.write_text(json.dumps({"夜视能力": ["夜视", "微光"]}), encoding="utf-8")
        keywords = MODULE.load_theme_keywords(tmp)
        self.assertEqual({"夜视能力"}, set(keywords))
        self.assertEqual("夜视能力", MODULE.theme_of("夜视清晰", keywords))

    def test_unknown_label_falls_to_other(self):
        keywords = MODULE.load_theme_keywords(None)
        self.assertEqual("其他", MODULE.theme_of("综合推荐", keywords))
        self.assertEqual("其他", MODULE.theme_of("", keywords))

    def test_rejects_empty_or_malformed(self):
        tmp = Path(tempfile.mkdtemp()) / "bad.json"
        tmp.write_text("{}", encoding="utf-8")
        with self.assertRaises(SystemExit):
            MODULE.load_theme_keywords(tmp)
        tmp.write_text(json.dumps({"主题": []}), encoding="utf-8")
        with self.assertRaises(SystemExit):
            MODULE.load_theme_keywords(tmp)


class TestBrandTableTarget(unittest.TestCase):
    def test_target_flag_follows_argument_not_hardcoded_brand(self):
        counts = {"YOUKU": (3, 1), "iQIYI": (1, 2), "WeTV": (0, 0)}
        table = MODULE.build_brand_table([], {}, list(counts), counts, lambda u: True, "YOUKU")
        flags = {row["brand"]: row["target"] for row in table["rows"]}
        self.assertEqual({"YOUKU": True, "iQIYI": False, "WeTV": False}, flags)


class TestThemeMatrix(unittest.TestCase):
    @staticmethod
    def group(label, count, region="MY"):
        """构造 load_claim_groups 装配后的组结构(带 members)。"""
        members = [{"sentence": f"{label} #{i}", "region": region, "platform": "chatgpt",
                    "question_id": "0001", "idx": i} for i in range(count)]
        return {"label": label, "count": count, "members": members,
                "evidence": members[0] if members else {}}

    def test_cell_carries_top_claim_label_not_number(self):
        all_claims = {"A": {"pos": [self.group("免安装零管线", 5)],
                            "neg": [self.group("机身过深", 2)]}}
        matrix = MODULE.build_theme_matrix(all_claims, ["A"], lambda u: True,
                                          MODULE.load_theme_keywords(None))
        install = matrix["matrix"]["安装与部署"]["A"]
        self.assertEqual("免安装零管线", install["top_claim"])
        self.assertEqual("pos", install["top_dir"])
        self.assertEqual("100.0%", install["rate"])
        size = matrix["matrix"]["体积与空间"]["A"]
        self.assertEqual("机身过深", size["top_claim"])
        self.assertEqual("neg", size["top_dir"])

    def test_custom_lexicon_routes_to_custom_theme(self):
        all_claims = {"A": {"pos": [self.group("夜视效果好", 3)], "neg": []}}
        matrix = MODULE.build_theme_matrix(all_claims, ["A"], lambda u: True, {"夜视能力": ["夜视"]})
        self.assertEqual("夜视效果好", matrix["matrix"]["夜视能力"]["A"]["top_claim"])
        self.assertEqual("其他", MODULE.theme_of("夜视效果好", MODULE.load_theme_keywords(None)))


if __name__ == "__main__":
    unittest.main()
