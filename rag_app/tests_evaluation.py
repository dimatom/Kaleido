from django.test import SimpleTestCase

from rag_app.evaluation_service import (
    build_evaluation_turns,
    indexing_config_changed,
    normalize_rag_config,
    validate_rag_config,
)


class EvaluationServiceTests(SimpleTestCase):
    def test_normalize_rag_config_fills_defaults(self):
        config = normalize_rag_config({"retrieval": {"rerank_top_k": 2}})

        self.assertEqual(config["retrieval"]["rerank_top_k"], 2)
        self.assertIn("chunk_size", config["indexing"])
        self.assertIn("ensemble_top_k", config["retrieval"])

    def test_validate_rag_config_rejects_invalid_overlap(self):
        with self.assertRaisesMessage(ValueError, "chunk_overlap 必须小于 chunk_size"):
            validate_rag_config({"indexing": {"chunk_size": 100, "chunk_overlap": 100}})

    def test_indexing_change_only_compares_chunk_settings(self):
        base = normalize_rag_config({})
        retrieval_only = normalize_rag_config({"retrieval": {"rerank_top_k": 2}})
        chunk_change = normalize_rag_config({"indexing": {"chunk_size": 600}})

        self.assertFalse(indexing_config_changed(base, retrieval_only))
        self.assertTrue(indexing_config_changed(base, chunk_change))

    def test_build_evaluation_turns_merges_messages_and_keeps_prior_history(self):
        messages = [
            {"type": "human", "data": {"content": "第一问"}},
            {"type": "ai", "data": {"content": "第一答"}},
            {"type": "human", "data": {"content": "第二"}},
            {"type": "human", "data": {"content": "问"}},
            {"type": "ai", "data": {"content": "旧答案"}},
            {"type": "ai", "data": {"content": "最终答案"}},
        ]

        turns = build_evaluation_turns(messages)

        self.assertEqual(len(turns), 2)
        self.assertEqual(turns[1]["question"], "第二\n问")
        self.assertEqual(turns[1]["ai_answer"], "最终答案")
        self.assertEqual(turns[1]["history_context"], [
            {"type": "human", "content": "第一问"},
            {"type": "ai", "content": "第一答"},
        ])
