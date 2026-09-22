"""Case 与品牌词表接入的通用性测试。

覆盖两条多品类/多语言实测踩到的坑（2026-09-22，YOUKU 泰国数据集）：
  * 题库主题是当地语言、Case 主题是中文，需要对得上；
  * 词表结构与 Case 名称写法不统一时，不能静默把元数据当成品牌、
    也不能把同一个品牌拆成两个对象（声量分母会被污染）。
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "build_report_data.py"
spec = importlib.util.spec_from_file_location("build_report_data", SCRIPT)
MODULE = importlib.util.module_from_spec(spec)
sys.modules["build_report_data"] = MODULE
spec.loader.exec_module(MODULE)


class TestCaseTopicLabels(unittest.TestCase):
    def write_case(self, payload):
        path = Path(tempfile.mkdtemp()) / "case.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def base(self, **extra):
        return {"品牌名称": "YOUKU", "官方域名": "https://youku.tv",
                "品类": "华语视频流媒体平台",
                "竞品 1": "iQIYI International", "竞品 1 官网域名": "https://iq.com",
                **extra}

    def test_topic_labels_are_read_from_case(self):
        case = MODULE.load_case(self.write_case(self.base(主题映射={
            "แพลตฟอร์มสตรีมมิ่งวิดีโอภาษาจีน": "华语视频平台"})))
        self.assertEqual({"แพลตฟอร์มสตรีมมิ่งวิดีโอภาษาจีน": "华语视频平台"}, case["topic_labels"])

    def test_missing_topic_labels_defaults_to_empty(self):
        case = MODULE.load_case(self.write_case(self.base()))
        self.assertEqual({}, case["topic_labels"])

    def test_malformed_topic_labels_rejected(self):
        with self.assertRaises(SystemExit):
            MODULE.load_case(self.write_case(self.base(主题映射=["not", "a", "dict"])))


class TestLexiconShapes(unittest.TestCase):
    def write(self, payload):
        path = Path(tempfile.mkdtemp()) / "lex.json"
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_canonical_brands_list(self):
        entries, _, status = MODULE.load_lexicon(self.write({"brands": [
            {"name": "Netflix", "aliases": ["Netflix", "เน็ตฟลิกซ์"], "type": "competitor_open"}]}))
        self.assertEqual("loaded", status)
        self.assertEqual(["Netflix"], [e["name"] for e in entries])

    def test_nested_brands_dict_keeps_aliases_and_ignores_metadata(self):
        """{"brands": {名: 别名}} 要能用，且 target/note/tiers 这类顶层元数据不能被当成品牌。"""
        entries, _, status = MODULE.load_lexicon(self.write({
            "target": "YOUKU", "note": "说明文字", "tiers": {"1_frozen": ["YOUKU"]},
            "brands": {"YOUKU": ["Youku", "优酷"], "Netflix": ["Netflix"]}}))
        self.assertEqual("loaded", status)
        names = sorted(e["name"] for e in entries)
        self.assertEqual(["Netflix", "YOUKU"], names)      # 没有 target/note/tiers
        youku = next(e for e in entries if e["name"] == "YOUKU")
        self.assertIn("优酷", youku["aliases"])


class TestNameTokensSubset(unittest.TestCase):
    def test_case_name_longer_than_lexicon_name_matches(self):
        self.assertTrue(MODULE._name_tokens_subset("iqiyi", "iqiyi international"))
        self.assertTrue(MODULE._name_tokens_subset("hbo", "hbo max"))

    def test_unrelated_or_partial_words_do_not_match(self):
        # Viu 是 ViuTV 的子串，但词元不同，不能并
        self.assertFalse(MODULE._name_tokens_subset("viu", "viutv"))
        self.assertFalse(MODULE._name_tokens_subset("netflix", "netflixjapan"))
        self.assertFalse(MODULE._name_tokens_subset("", "netflix"))

    def test_identical_tokens_not_treated_as_subset(self):
        """全等由上游的精确相等分支处理，这里不重复认。"""
        self.assertFalse(MODULE._name_tokens_subset("netflix", "netflix"))


class TestConfigMergesCompetitorByTokenSubset(unittest.TestCase):
    def test_lexicon_entry_folds_into_case_competitor(self):
        case = {"brand": "YOUKU", "official_domain": "youku.tv", "category": "",
                "competitors": [{"name": "iQIYI International", "domain": "iq.com"}],
                "topics_raw": "华语视频平台"}
        entries = [
            {"name": "iQIYI", "domains": [], "aliases": ["iQIYI", "爱奇艺"],
             "type": "competitor_open"},
            {"name": "Netflix", "domains": [], "aliases": ["Netflix"], "type": "competitor_open"},
        ]
        config = MODULE.build_config(case, ["华语视频平台"], entries, {})
        names = [o["canonical_name"] for o in config["objects"]]
        # iQIYI 并入配置竞品，不另起一个开放品牌对象
        self.assertNotIn("iQIYI", names)
        self.assertEqual(3, len(config["objects"]))          # target + competitor + Netflix
        competitor = next(o for o in config["objects"] if o["role"] == "competitor")
        self.assertIn("爱奇艺", competitor["aliases"])


if __name__ == "__main__":
    unittest.main()
