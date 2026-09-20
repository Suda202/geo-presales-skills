"""商品卡表格渲染回归测试。"""

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_report_data.py"


def load_builder():
    spec = importlib.util.spec_from_file_location("build_report_data_product_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestProductCardRendering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_builder()

    def test_pipe_in_product_name_keeps_columns_aligned(self):
        answer = """| id | goods | price | rating | merchants | picture |
|------|------|------|------|------|------|
| 1 | **Brand Model | Compact Edition** | RM 100 | ⭐ 4.8 | [RM 100 - Shop](https://example.com/p) | <img src=\"https://example.com/p.jpg\" /> |
"""
        rendered = self.builder.markdown_to_html(answer)
        self.assertEqual(rendered.count('class="product-card"'), 1)
        self.assertEqual(rendered.count("product-card-img"), 1)
        self.assertIn("Brand Model | Compact Edition", rendered)
        self.assertIn("RM 100", rendered)
        self.assertIn("⭐ 4.8", rendered)
        self.assertNotIn("**", rendered)

    def test_localized_product_headers_use_same_card_renderer(self):
        answer = """| id | 商品 | 价格 | 评分 | 商家 | 图片 |
|------|------|------|------|------|------|
| 1 | **Bewinch G3 台式 RO 净水器** | $593.11 | ⭐ 0.0 | [\\$593.11 - Bewinch](https://example.com/p) | <img src=\"https://example.com/p.jpg\" /> |
"""
        rendered = self.builder.markdown_to_html(answer)
        self.assertEqual(rendered.count('class="product-card"'), 1)
        self.assertEqual(rendered.count("product-card-img"), 1)
        self.assertIn("Bewinch G3 台式 RO 净水器", rendered)
        self.assertIn("$593.11", rendered)
        self.assertNotIn("**", rendered)


if __name__ == "__main__":
    unittest.main()
