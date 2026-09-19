# -*- coding: utf-8 -*-
"""Unit tests: no database, no API calls, no production data."""
import importlib.util
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("document_ingest", ROOT / "07_ingest_documents.py")
ingest_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ingest_module)

import knowledge_tools


class KnowledgeCoreTests(unittest.TestCase):
    def test_chunk_ranges_reconstruct_and_overlap(self):
        text = ("مغایرت شاسی و صورت‌جلسه شمارش. " * 110).strip()
        chunks = list(ingest_module.chunks_from_text(text))
        self.assertGreater(len(chunks), 2)
        for start, end, piece in chunks:
            self.assertEqual(piece, text[start:end])
            self.assertLessEqual(len(piece), ingest_module.CHUNK_SIZE)
            self.assertGreater(end, start)
        self.assertEqual(chunks[0][0], 0)
        self.assertEqual(chunks[-1][1], len(text))
        for prev, following in zip(chunks, chunks[1:]):
            self.assertLess(following[0], prev[1])

    def test_query_token_normalization(self):
        terms = knowledge_tools._tokens("طبق دستورالعمل گمرك، تطبیق شاسي چگونه است؟")
        self.assertIn("دستورالعمل", terms)
        self.assertIn("تطبیق", terms)
        self.assertIn("شاسی", terms)
        self.assertNotIn("چگونه", terms) if "چگونه" in knowledge_tools.STOPWORDS else None

    def test_float32_cosine(self):
        vector = struct.pack("<fff", 1.0, 0.0, 0.0)
        self.assertAlmostEqual(
            knowledge_tools._cosine_from_bytes(vector, [1.0, 0.0, 0.0]), 1.0
        )
        self.assertAlmostEqual(
            knowledge_tools._cosine_from_bytes(vector, [0.0, 1.0, 0.0]), 0.0
        )
        self.assertEqual(
            knowledge_tools._cosine_from_bytes(vector, [1.0, 0.0]), 0.0
        )


if __name__ == "__main__":
    unittest.main()
