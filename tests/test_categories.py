import os
import shutil
import sys
import types
import unittest

os.environ.setdefault("KEYWORD_INDEX_DIR", "./tmp_whoosh_test")
os.environ.setdefault("AUTO_DOC_TYPES", "true")


class _DummySentenceTransformer:
    def __init__(self, *_args, **_kwargs):
        pass

    def encode(self, text):
        return [0.0]

    def get_sentence_embedding_dimension(self):
        return 384


sys.modules.setdefault(
    "sentence_transformers",
    types.SimpleNamespace(SentenceTransformer=_DummySentenceTransformer),
)


from backend.services.categories import extract_doc_types_from_text, normalize_doc_type


class DocTypeExtractionTests(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        tmp_dir = os.environ["KEYWORD_INDEX_DIR"]
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_email_keywords(self):
        text = "Покажи email переписку с поставщиком"
        result = extract_doc_types_from_text(text)
        self.assertIn("email_correspondence", result)

    def test_protocol_keywords(self):
        text = "Нужен протокол заседания комитета"
        self.assertIn("protocols", extract_doc_types_from_text(text))

    def test_work_plan_keywords(self):
        text = "Какие планы и roadmap у проекта?"
        self.assertIn("work_plans", extract_doc_types_from_text(text))

    def test_normalize_alias(self):
        self.assertEqual(normalize_doc_type("email"), "email_correspondence")
        self.assertEqual(normalize_doc_type("presentations"), "presentations")


if __name__ == "__main__":
    unittest.main()
