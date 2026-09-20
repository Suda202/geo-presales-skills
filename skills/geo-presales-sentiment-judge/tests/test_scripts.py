import csv
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.parse

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "sentiment_sentences.py")

spec = importlib.util.spec_from_file_location("sentiment_sentences", SCRIPT)
MOD = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MOD)


def make_case(root: str, tamper_prompt: bool = False) -> tuple[str, str]:
    questions = [
        {  # in scope, mentions brand with citation + table + FollowUp noise
            "question_id": "q-001", "analysis_type": "visibility,sentiment",
            "tags": ["Intent: Discovery"], "user_question": "แพลตฟอร์มใดดี",
        },
        {  # out of scope: category awareness has no analysis_type
            "question_id": "q-002",
            "tags": ["Intent: Category Awareness"], "user_question": "คืออะไร",
        },
        {  # in scope competitor
            "question_id": "q-003", "analysis_type": "sentiment",
            "tags": ["Intent: Competitor"], "user_question": "A หรือ B",
        },
    ]
    bank = os.path.join(root, "bank.json")
    json.dump({"questions": questions}, open(bank, "w"))

    crawl = os.path.join(root, "crawl")
    answers = {
        1: "แนะนำ **YOUKU** เลย ([Google Play][1])<FollowUp label=\"x\" query=\"y\"/>\n"
           "| แพลตฟอร์ม | จุดเด่น |\n|---|---|\n| YOUKU ดีมาก | iQIYI ก็มี youkuapp ไม่นับ |\n"
           "[1]: https://example.com \"Google Play\"",
        2: "YOUKU appears here but question is out of scope",
        3: "ผมเลือก iQIYI มากกว่า YOUKU เพราะซับดีกว่า\nประโยคที่ไม่มีแบรนด์",
    }
    for platform in ("chatgpt", "gemini"):
        outdir = os.path.join(crawl, f"scraper.{platform}", "TH")
        os.makedirs(outdir)
        for idx, text in answers.items():
            prompt = questions[idx - 1]["user_question"]
            if tamper_prompt and platform == "gemini" and idx == 1:
                prompt = "被改过的题面"
            json.dump({"status": "success",
                       "task_result": {"prompt": prompt, "result_text": text}},
                      open(os.path.join(outdir, f"{idx:04d}.json"), "w"))
    return bank, crawl


def run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, SCRIPT, *argv], capture_output=True, text=True)


LEXICON = {
    "brands": [
        {"name": "Bewinch", "aliases": ["Bewinch", "Bewinch G3"], "type": "target"},
        {"name": "Novita", "aliases": ["Novita"], "type": "competitor_configured"},
        {"name": "AquaTru", "aliases": ["AquaTru", "Aquatru"], "type": "competitor_open"},
    ]
}
BANK_CSV_HEADER = ["query", "question_zh", "topic", "diagnosis_intent", "tags", "question_types"]
BANK_CSV_ROW = ["Which purifier is best?", "哪个最好？", "净饮机", "discovery",
                "Intent: Discovery,Brand Scope: Non-Branded", "visibility,sentiment"]


def make_lexicon_case(root: str, prompt_mode: str = "rawurl") -> tuple[str, str, str]:
    """CSV bank + lexicon + one AIO/overview answer (uses task_result.content)."""
    bank = os.path.join(root, "bank.csv")
    with open(bank, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(BANK_CSV_HEADER)
        writer.writerow(BANK_CSV_ROW)
    lexicon = os.path.join(root, "lexicon.json")
    json.dump(LEXICON, open(lexicon, "w"))

    crawl = os.path.join(root, "crawl")
    outdir = os.path.join(crawl, "scraper.overview", "MY")
    os.makedirs(outdir)
    task = {"content": "**Bewinch** and Novita both work well here.\nAquaTru is cheaper."}
    if prompt_mode == "rawurl":
        task["metadata"] = {"rawUrl": "https://www.google.com/search?q="
                            + urllib.parse.quote(BANK_CSV_ROW[0]) + "&gl=MY"}
    elif prompt_mode == "field":
        task["prompt"] = BANK_CSV_ROW[0]
    # prompt_mode == "absent": neither prompt nor metadata
    json.dump({"status": "success", "task_result": task},
              open(os.path.join(outdir, "0001.json"), "w"))
    return bank, lexicon, crawl


class MultiBrandExtractTests(unittest.TestCase):
    def test_lexicon_mode_tags_each_unit_with_its_brand(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, lexicon, crawl = make_lexicon_case(root)
            out = os.path.join(root, "units.json")
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--lexicon", lexicon, "--output", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.load(open(out))
            meta = payload["meta"]
            # CSV bank: question_types drives scope; question_id = row number
            self.assertEqual(meta["scope_answers"], 1)
            self.assertEqual(meta["brand_mode"], "lexicon")
            # AIO answer body read from task_result.content
            texts = sorted({u["unit"] for u in payload["units"]})
            self.assertIn("AquaTru is cheaper.", texts)
            # two sentences mention >=1 brand -> 2 distinct units, 3 brand units
            self.assertEqual(meta["distinct_unit_count"], 2)
            self.assertEqual(meta["unit_count"], 3)
            self.assertEqual(meta["by_brand_type"],
                             {"competitor_configured": 1, "competitor_open": 1, "target": 1})
            self.assertEqual(meta["by_brand"],
                             {"Bewinch": 1, "Novita": 1, "AquaTru": 1})
            # the sentence naming two brands yields one unit per brand
            both = [u for u in payload["units"] if "both work well" in u["unit"]]
            self.assertEqual(sorted(u["brand"] for u in both), ["Bewinch", "Novita"])
            self.assertTrue(all(u["question_id"] == "0001" for u in payload["units"]))
            # region comes from scraper.<platform>/<REGION>/<NNNN>.json
            self.assertTrue(all(u["region"] == "MY" for u in payload["units"]))

    def test_question_recovered_from_rawurl_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, lexicon, crawl = make_lexicon_case(root, prompt_mode="rawurl")
            out = os.path.join(root, "units.json")
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--lexicon", lexicon, "--output", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.load(open(out))["meta"]["unverified_prompt_answers"], 0)
            self.assertNotIn("警告", proc.stderr)

    def test_missing_prompt_is_unverified_not_aborted(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, lexicon, crawl = make_lexicon_case(root, prompt_mode="absent")
            out = os.path.join(root, "units.json")
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--lexicon", lexicon, "--output", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.load(open(out))["meta"]["unverified_prompt_answers"], 1)
            self.assertIn("警告", proc.stderr)

    def test_aliases_mode_still_stamps_brand(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, crawl = make_case(root)
            out = os.path.join(root, "units.json")
            run("extract", "--bank", bank, "--crawl-dir", crawl,
                "--aliases", "YOUKU", "--brand", "YOUKU-TH", "--output", out)
            payload = json.load(open(out))
            self.assertEqual(payload["meta"]["brand_mode"], "aliases")
            self.assertTrue(all(u["brand"] == "YOUKU-TH" for u in payload["units"]))
            self.assertTrue(all(u["region"] == "TH" for u in payload["units"]))
            self.assertEqual(payload["meta"]["distinct_unit_count"],
                             payload["meta"]["unit_count"])

    def test_extract_requires_a_brand_source(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, crawl = make_case(root)
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--output", os.path.join(root, "u.json"))
            self.assertNotEqual(proc.returncode, 0)

    def test_compute_brand_filter_rejects_other_brands(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, lexicon, crawl = make_lexicon_case(root)
            units = os.path.join(root, "units.json")
            run("extract", "--bank", bank, "--crawl-dir", crawl,
                "--lexicon", lexicon, "--output", units)
            result = json.load(open(units))
            idx = {u["brand"]: i for i, u in enumerate(result["units"])}
            labels = os.path.join(root, "labels.json")
            json.dump({"positive": [idx["Bewinch"]], "negative": []}, open(labels, "w"))
            out_csv = os.path.join(root, "s.csv")
            proc = run("compute", "--units", units, "--labels", labels,
                       "--brand", "Bewinch", "--out-csv", out_csv)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            rows = list(csv.DictReader(open(out_csv, encoding="utf-8-sig")))
            self.assertEqual([r["brand"] for r in rows], ["Bewinch"])
            bad = os.path.join(root, "bad.json")
            json.dump({"positive": [idx["Novita"]], "negative": []}, open(bad, "w"))
            proc = run("compute", "--units", units, "--labels", bad,
                       "--brand", "Bewinch", "--out-csv", out_csv)
            self.assertNotEqual(proc.returncode, 0)


class ExtractTests(unittest.TestCase):
    def test_extract_scopes_decites_splits_and_filters(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, crawl = make_case(root)
            out = os.path.join(root, "units.json")
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--aliases", "YOUKU,优酷,ยูคุ", "--output", out)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.load(open(out))
            # scope: q-001 + q-003 on two platforms = 4 answers; q-002 excluded
            self.assertEqual(payload["meta"]["scope_answers"], 4)
            self.assertEqual(payload["meta"]["mentioned_answers"], 4)
            units = payload["units"]
            texts = [u["unit"] for u in units]
            # citation pill, FollowUp widget, ref-def line all stripped
            self.assertTrue(any(u == "แนะนำ **YOUKU** เลย" for u in texts), texts)
            self.assertFalse(any("Google Play" in u or "FollowUp" in u for u in texts))
            # table row split into cells; boundary guard: 'youkuapp' cell not matched
            self.assertIn("YOUKU ดีมาก", texts)
            self.assertNotIn("iQIYI ก็มี youkuapp ไม่นับ", texts)
            # brandless line filtered out
            self.assertFalse(any("ไม่มีแบรนด์" in u for u in texts))
            # per platform: q1 yields 2 units, q3 yields 1 -> 3 × 2 platforms
            self.assertEqual(len(units), 6)
            self.assertTrue(all(u["intent"] in {"Discovery", "Competitor"} for u in units))

    def test_extract_aborts_on_prompt_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank, crawl = make_case(root, tamper_prompt=True)
            proc = run("extract", "--bank", bank, "--crawl-dir", crawl,
                       "--aliases", "YOUKU", "--output", os.path.join(root, "u.json"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("题面完整性失败", proc.stderr)


class ComputeTests(unittest.TestCase):
    def _units(self, root: str) -> str:
        bank, crawl = make_case(root)
        out = os.path.join(root, "units.json")
        run("extract", "--bank", bank, "--crawl-dir", crawl,
            "--aliases", "YOUKU", "--output", out)
        return out

    def test_compute_rates_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            units = self._units(root)
            labels = os.path.join(root, "labels.json")
            json.dump({"positive": [0, 1], "negative": [2]}, open(labels, "w"))
            out_csv = os.path.join(root, "s.csv")
            metrics = os.path.join(root, "m.json")
            proc = run("compute", "--units", units, "--labels", labels,
                       "--out-csv", out_csv, "--out-metrics", metrics)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("正向率 = 2/3 = 66.7%", proc.stdout)
            rows = list(csv.DictReader(open(out_csv, encoding="utf-8-sig")))
            self.assertEqual(len(rows), 3)
            self.assertEqual([r["sentiment"] for r in rows], ["P", "P", "G"])
            data = json.load(open(metrics))
            self.assertAlmostEqual(data["positive_rate"], 2 / 3)
            self.assertEqual(data["funnel"]["scope_answers"], 4)

    def test_compute_rejects_overlap_and_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            units = self._units(root)
            for bad in ({"positive": [0], "negative": [0]},
                        {"positive": [999], "negative": []}):
                labels = os.path.join(root, "labels.json")
                json.dump(bad, open(labels, "w"))
                proc = run("compute", "--units", units, "--labels", labels,
                           "--out-csv", os.path.join(root, "s.csv"))
                self.assertNotEqual(proc.returncode, 0, bad)

    def test_compute_refuses_zero_denominator(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            units = self._units(root)
            labels = os.path.join(root, "labels.json")
            json.dump({"positive": [], "negative": []}, open(labels, "w"))
            proc = run("compute", "--units", units, "--labels", labels,
                       "--out-csv", os.path.join(root, "s.csv"))
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("无样本", proc.stderr)


class ComputeRegionKeyTests(unittest.TestCase):
    """同一平台、同一 idx 出现在两个区域时，含正负句的回答须按区域分别计数。

    采集按 scraper.<platform>/<REGION>/NNNN.json 分层，idx 是区域内编号，
    港/新同题回答 idx 相同。只以 (platform, idx) 去重会合并两地、低报回答数
    ——实测 Trip.Biz 港新报 38 条、实为 52 条。
    """

    def test_answers_with_pg_separates_regions(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            bank = os.path.join(root, "bank.json")
            json.dump({"questions": [
                {"question_id": "q-001", "analysis_type": "sentiment",
                 "tags": ["Intent: Discovery"], "user_question": "which is best"},
            ]}, open(bank, "w"))
            crawl = os.path.join(root, "crawl")
            for region in ("HK", "SG"):
                outdir = os.path.join(crawl, "scraper.gemini", region)
                os.makedirs(outdir)
                json.dump({"status": "success", "task_result": {
                    "prompt": "which is best",
                    "result_text": f"YOUKU is the best pick in {region}."}},
                    open(os.path.join(outdir, "0001.json"), "w"))

            units = os.path.join(root, "units.json")
            run("extract", "--bank", bank, "--crawl-dir", crawl,
                "--aliases", "YOUKU", "--output", units)

            labels = os.path.join(root, "labels.json")
            json.dump({"positive": [0, 1], "negative": []}, open(labels, "w"))
            metrics = os.path.join(root, "m.json")
            proc = run("compute", "--units", units, "--labels", labels,
                       "--out-csv", os.path.join(root, "s.csv"), "--out-metrics", metrics)

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.load(open(metrics))["funnel"]["answers_with_pg"], 2)
            self.assertIn("含正负句的回答 2 条", proc.stdout)


if __name__ == "__main__":
    unittest.main()
