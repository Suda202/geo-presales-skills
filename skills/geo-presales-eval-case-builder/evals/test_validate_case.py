#!/usr/bin/env python3
"""Regression tests for deterministic Case validation rules."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "validate_case.py"
SPEC = importlib.util.spec_from_file_location("validate_case", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


BASE_BODY = """| 字段 | 填写内容 |
|---|---|
| 品牌名称 | Example Brand |
| 业务模式 | B2C |
| 品类 | 彩色宝石首饰 |
| 目标客户 | 日常佩戴首饰的消费者 |
| 痛点 | 天然彩色宝石价格昂贵，日常佩戴款式有限 |
| 使用场景 | 日常通勤佩戴，休闲聚会搭配 |
| 产品特性 | 培育彩色宝石，可日常佩戴的设计 |
| 差异化优势 | 兼顾彩色宝石外观和日常价格带 |
| 适用边界 | 适合日常佩戴且不以天然宝石收藏为目标的人群 |
| 主题 | {topics} |
| 官方域名 | https://example.com |
| 竞品 1 | Competitor One |
| 竞品 1 官网域名 | https://one.example |
| 竞品 2 | Competitor Two |
| 竞品 2 官网域名 | https://two.example |
| 竞品 3 | Competitor Three |
| 竞品 3 官网域名 | https://three.example |
"""


class TopicValidationTest(unittest.TestCase):
    def errors_for(self, topics: str) -> list[str]:
        return MODULE.validate_case(1, BASE_BODY.format(topics=topics))

    def test_accepts_concise_topic_names(self) -> None:
        self.assertEqual([], self.errors_for("彩色宝石首饰，日常佩戴宝石首饰"))

    def test_rejects_english_prompt_as_topic(self) -> None:
        errors = self.errors_for(
            "What are the best lab-grown colored gemstone jewelry brands for everyday wear?"
        )
        self.assertTrue(any("完整问题" in error for error in errors))
        self.assertTrue(any("Best / Top" in error for error in errors))

    def test_rejects_chinese_prompt_as_topic(self) -> None:
        errors = self.errors_for("哪些培育彩色宝石首饰品牌适合日常佩戴？")
        self.assertTrue(any("完整问题" in error for error in errors))


class VerticalIndustryValidationTest(unittest.TestCase):
    def test_accepts_blank_vertical_industry_for_b2c(self) -> None:
        errors = MODULE.validate_case(1, BASE_BODY.format(topics="彩色宝石首饰"))
        self.assertEqual([], errors)

    def test_rejects_vertical_industry_for_b2c(self) -> None:
        body = BASE_BODY.format(topics="彩色宝石首饰").replace(
            "| 品类 | 彩色宝石首饰 |",
            "| 品类 | 彩色宝石首饰 |\n| 垂直行业 | 珠宝零售 |",
        )
        errors = MODULE.validate_case(1, body)
        self.assertTrue(any("纯 B2C" in error for error in errors))


class CaseParsingTest(unittest.TestCase):
    def parse(self, markdown: str) -> list[str]:
        return [match.group("body") for match in MODULE.CASE_RE.finditer(markdown)]

    def test_accepts_heading_without_sequence_number(self) -> None:
        cases = self.parse(f"## Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n")
        self.assertEqual(1, len(cases))

    def test_keeps_legacy_numbered_heading_compatible(self) -> None:
        cases = self.parse(f"## 1. Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n")
        self.assertEqual(1, len(cases))

    def test_ignores_explanatory_second_level_heading(self) -> None:
        markdown = (
            "## 字段填写说明\n\n这里是说明，不是 Case。\n\n"
            f"## Example Brand\n\n{BASE_BODY.format(topics='彩色宝石首饰')}\n"
        )
        cases = self.parse(markdown)
        self.assertEqual(1, len(cases))


if __name__ == "__main__":
    unittest.main()
