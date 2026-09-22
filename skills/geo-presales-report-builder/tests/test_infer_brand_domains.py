"""从引用来源推断开放品牌官网的测试。

判定必须保守：只有「引用注册域标签 == 品牌名/别名归一形式」才算高置信，
其余交给搜索/人工——乱猜会把别家官网算成竞品网站。
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "infer_brand_domains.py"
spec = importlib.util.spec_from_file_location("infer_brand_domains", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
sys.modules["infer_brand_domains"] = MODULE
spec.loader.exec_module(MODULE)

import collections  # noqa: E402


def hosts(*pairs):
    return collections.Counter(dict(pairs))


class TestInfer(unittest.TestCase):
    def brands(self):
        return [
            {"name": "YOUKU", "aliases": ["YOUKU", "优酷"], "official_domains": ["youku.tv"]},
            {"name": "Viu", "aliases": ["Viu"]},
            {"name": "Bilibili", "aliases": ["Bilibili", "哔哩哔哩", "B站"]},
            {"name": "Mango TV", "aliases": ["MangoTV", "Mango TV", "芒果TV", "芒果"]},
        ]

    def test_label_matching_finds_obvious_official_domains(self):
        inferred, _ = MODULE.infer(
            hosts(("viu.com", 41), ("bilibili.tv", 48), ("sub.bilibili.tv", 2)), self.brands())
        self.assertEqual(["viu.com"], inferred["Viu"])
        self.assertEqual(["bilibili.tv"], inferred["Bilibili"])

    def test_already_declared_domains_are_not_reinferred(self):
        inferred, _ = MODULE.infer(hosts(("youku.tv", 9), ("viu.com", 1)), self.brands())
        self.assertNotIn("YOUKU", inferred)          # 目标由 Case 决定，不重复推断

    def test_abbreviations_go_to_candidates_not_inference(self):
        """mgtv.com ↔ Mango TV 是缩写，归一后不相等，必须留给搜索/人工，不能硬猜。"""
        inferred, candidates = MODULE.infer(
            hosts(("mgtv.com", 78), ("w.mgtv.com", 12)), self.brands())
        self.assertNotIn("Mango TV", inferred)
        self.assertIn("mgtv.com", [c["domain"] for c in candidates])

    def test_generic_labels_are_not_matched(self):
        """tv / app 这类通用标签即使与别名同形也不认。"""
        brand = [{"name": "TV", "aliases": ["tv"]}]
        inferred, _ = MODULE.infer(hosts(("tv.com", 5)), brand)
        self.assertEqual({}, inferred)


class TestCollectHosts(unittest.TestCase):
    def test_collects_hosts_from_crawl_json(self):
        root = Path(tempfile.mkdtemp()) / "scraper.gemini" / "TH"
        root.mkdir(parents=True)
        (root / "0001.json").write_text(json.dumps({
            "task_result": {"content": "see https://viu.com/a and https://viu.com/b"},
            "source": [{"url": "https://www.mgtv.com/x"}],
        }, ensure_ascii=False), encoding="utf-8")
        counts = MODULE.collect_hosts(root.parent.parent)
        self.assertEqual(2, counts["viu.com"])
        self.assertEqual(1, counts["mgtv.com"])      # normalize_host 会去掉 www.


if __name__ == "__main__":
    unittest.main()
