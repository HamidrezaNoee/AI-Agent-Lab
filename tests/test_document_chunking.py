# -*- coding: utf-8 -*-
"""Unit tests independent of OpenAI API and SQL Server."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "ingest_test_document", ROOT / "07_ingest_test_document.py"
)
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


class ChunkingTests(unittest.TestCase):
    def test_short_document(self):
        text = "نمونه آزمایشی"
        chunks = list(MOD.chunk_text(text))
        self.assertEqual(chunks, [(0, len(text), text)])

    def test_long_document_covers_all_words(self):
        text = " ".join("واحد گمرک پرونده باز" for _ in range(160))
        chunks = list(MOD.chunk_text(text))
        self.assertGreater(len(chunks), 1)
        self.assertEqual(chunks[0][0], 0)
        self.assertEqual(chunks[-1][1], len(text))
        for start, end, piece in chunks:
            self.assertTrue(piece)
            self.assertIn(piece, text[start:end])
            self.assertLessEqual(end - start, 900)
        for previous, current in zip(chunks, chunks[1:]):
            self.assertLess(current[0], previous[1])

    def test_reject_invalid_overlap(self):
        with self.assertRaises(ValueError):
            list(MOD.chunk_text("abc", 100, 100))

    def test_demo_document_is_explicitly_fictional(self):
        source = ROOT / "sample_docs" / "fictional_customs_workload.txt"
        body = MOD.extract_text(source)
        self.assertIn("ساختگی", body)
        self.assertIn("گمرکی", body)


if __name__ == "__main__":
    unittest.main()
