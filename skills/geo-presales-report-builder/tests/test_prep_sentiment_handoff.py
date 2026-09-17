"""prep_sentiment_handoff.py 的单元测试:拆批、回装、归纳校验。"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "prep_sentiment_handoff.py"

UNITS = [
    {"brand": "A", "region": "MY", "platform": "chatgpt", "question_id": "0001",
     "intent": "Discovery", "unit": "A is great"},
    {"brand": "B", "region": "SG", "platform": "gemini", "question_id": "0002",
     "intent": "Evaluation", "unit": "B is slow"},
    {"brand": "A", "region": "SG", "platform": "chatgpt", "question_id": "0003",
     "intent": "Competitor", "unit": "A beats B"},
]


def run_cmd(*argv):
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, argv)],
                          capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.units = self.tmp / "units.json"
        self.units.write_text(json.dumps({"units": UNITS}), encoding="utf-8")

    def write(self, rel, payload):
        path = self.tmp / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path


class TestSplit(Base):
    def test_split_by_brand_with_global_idx(self):
        result = run_cmd("split", "--units", self.units, "--brands", "A,B",
                         "--out-dir", self.tmp / "batches")
        self.assertEqual(0, result.returncode, result.stderr)
        rows = json.loads((self.tmp / "batches" / "A.json").read_text(encoding="utf-8"))
        self.assertEqual([0, 2], [r["idx"] for r in rows])
        self.assertEqual("A beats B", rows[1]["sentence"])


class TestAssemble(Base):
    def test_assemble_sorted_and_shaped(self):
        self.write("batches/A-labels.json", {"positive": [2, 0], "negative": []})
        result = run_cmd("assemble", "--units", self.units, "--labels-dir",
                         self.tmp / "batches", "--brands", "A",
                         "--out", self.tmp / "claims" / "judged-sentences.json")
        self.assertEqual(0, result.returncode, result.stderr)
        judged = json.loads((self.tmp / "claims" / "judged-sentences.json").read_text(encoding="utf-8"))
        self.assertEqual([0, 2], [r["idx"] for r in judged["A"]["positive"]])
        self.assertEqual("MY", judged["A"]["positive"][0]["region"])

    def test_assemble_rejects_wrong_brand_index(self):
        self.write("batches/A-labels.json", {"positive": [1], "negative": []})
        result = run_cmd("assemble", "--units", self.units, "--labels-dir",
                         self.tmp / "batches", "--brands", "A",
                         "--out", self.tmp / "claims" / "judged-sentences.json")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("属于品牌", result.stderr)

    def test_assemble_rejects_overlapping_labels(self):
        self.write("batches/A-labels.json", {"positive": [0], "negative": [0]})
        result = run_cmd("assemble", "--units", self.units, "--labels-dir",
                         self.tmp / "batches", "--brands", "A",
                         "--out", self.tmp / "claims" / "judged-sentences.json")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("重叠", result.stderr)


class TestCheckClaims(Base):
    def setUp(self):
        super().setUp()
        self.judged = self.write("claims/judged-sentences.json", {
            "A": {"positive": [{"idx": 0, "sentence": "A is great"},
                               {"idx": 2, "sentence": "A beats B"}],
                  "negative": []}})

    def test_valid_claims_pass(self):
        self.write("claims/A-claims.json", {
            "brand": "A",
            "positive": [{"label": "好", "count": 2, "indices": [0, 1],
                          "evidence": {"sentence": "A is great"}}],
            "negative": []})
        result = run_cmd("check-claims", "--judged", self.judged,
                         "--claims-dir", self.tmp / "claims")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_global_idx_misuse_is_caught(self):
        # Bewinch/Coway 实例:indices 误用全局 idx(2 越界于同方向数组)
        self.write("claims/A-claims.json", {
            "brand": "A",
            "positive": [{"label": "好", "count": 2, "indices": [0, 2],
                          "evidence": {"sentence": "A is great"}}],
            "negative": []})
        result = run_cmd("check-claims", "--judged", self.judged,
                         "--claims-dir", self.tmp / "claims")
        self.assertEqual(1, result.returncode)
        self.assertIn("越界", result.stdout)
        self.assertIn("不穷尽", result.stdout)

    def test_non_exhaustive_and_count_mismatch(self):
        self.write("claims/A-claims.json", {
            "brand": "A",
            "positive": [{"label": "好", "count": 3, "indices": [0],
                          "evidence": {"sentence": "A is great"}}],
            "negative": []})
        result = run_cmd("check-claims", "--judged", self.judged,
                         "--claims-dir", self.tmp / "claims")
        self.assertEqual(1, result.returncode)
        self.assertIn("不一致", result.stdout)
        self.assertIn("未归入任何组", result.stdout)


if __name__ == "__main__":
    unittest.main()
