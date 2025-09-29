import os
import unittest

os.environ["CONTEXT_SNIPPET_MAX_CHARS"] = "120"

from backend.services import config
from backend.services.context import compress_text

config.CONTEXT_SNIPPET_MAX_CHARS = 120

class ContextCompressionTests(unittest.TestCase):
    def test_selects_keyword_sentence(self):
        text = "Первая фраза. Вторая фраза с поставщиком. Третья фраза."
        snippet = compress_text(text, "о поставщике")
        self.assertIn("поставщ", snippet.lower())

    def test_fallback_first_sentences(self):
        text = "Фраза один. Фраза два."
        snippet = compress_text(text, "ничего")
        self.assertTrue(snippet.startswith("Фраза один"))

    def test_truncates_long_text(self):
        text = "Предложение " * 50
        snippet = compress_text(text, "")
        self.assertLessEqual(len(snippet), 120)

if __name__ == "__main__":
    unittest.main()
