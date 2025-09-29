import unittest

from backend.services import rerank
from backend.services import config

class DummyRerankTests(unittest.TestCase):
    def setUp(self):
        self.prev_enabled = config.RERANK_ENABLED
        self.prev_model = config.RERANK_MODEL
        self.prev_max = config.RERANK_MAX_CANDIDATES
        config.RERANK_ENABLED = True
        config.RERANK_MAX_CANDIDATES = 2

    def tearDown(self):
        config.RERANK_ENABLED = self.prev_enabled
        config.RERANK_MODEL = self.prev_model
        config.RERANK_MAX_CANDIDATES = self.prev_max
        rerank._model = None
        rerank._predict_scores = rerank._predict_scores_original

    def test_apply_rerank_reorders_candidates(self):
        candidates = [
            {"key": "a", "payload": {"doc_id": "1", "text": "поставщик и сроки"}},
            {"key": "b", "payload": {"doc_id": "2", "text": "другое"}},
            {"key": "c", "payload": {"doc_id": "3", "text": "поставщик"}},
        ]

        def fake_scores(query, texts):
            return [10.0, 1.0]

        rerank._predict_scores = fake_scores
        result = rerank.apply_rerank("поставщик", candidates)
        self.assertEqual(result[0]["key"], "a")

if not hasattr(rerank, "_predict_scores_original"):
    rerank._predict_scores_original = rerank._predict_scores

if __name__ == "__main__":
    unittest.main()
